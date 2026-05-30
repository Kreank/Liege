// CombatFx — Damage-Numbers, Hit-Sparks, Death-Animationen, Screen-Shake
// und Heal-Pulse für die WorldScene.
//
// Architektur: die WorldScene hört über `WebSocketService.messages$` (durch
// `GameBridgeService.state` weitergereicht) auf die Server-Events und ruft
// dann eine der `CombatFx`-Methoden mit der Phaser-Scene als Ziel. Die FX
// nutzen nur den Phaser-Scene-Context — keine Angular-Signals, keine DOM-
// Manipulation.
//
// Warum Phaser-Text statt einer Angular-`floating-numbers`-Component:
//   • Welt-Koordinaten: Numbers müssen sich mit der Kamera mitscrollen.
//     Eine DOM-Overlay-Komponente müsste pro Frame Welt→Screen umrechnen,
//     was bei vielen gleichzeitigen Numbers zu Layout-Thrashing führt.
//   • Z-Sorting: Phaser-Text-Objekte sitzen im gleichen Depth-Stack wie
//     die Sprites — eine `Container.bringToTop()`-Geste reicht.
//   • Bundle-Size: kein extra Angular-Component-Code, kein CD-Trigger pro
//     FX-Spawn.
//
// Tween-Defaults (alle Werte in ms):
//   damage-number: 800ms float-up + fade-out
//   hit-spark:     300ms scale 0→1→0
//   poison-cloud:  1500ms alpha 0.6→0
//   heal-pulse:    500ms scale 0.5→2.0
//   death-fade:    600ms alpha+scale → destroy
//   screen-shake:  200ms, intensity proportional zum Damage (cap 0.02)

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';

/** Farbcodierung für Floating-Numbers. */
export type FloatingNumberKind = 'phys' | 'dot' | 'heal' | 'crit';

const COLOR_FOR_KIND: Readonly<Record<FloatingNumberKind, string>> = {
  phys: '#ffffff',
  dot:  '#d33', // rot für DOT/Gift/Fire
  heal: '#5e5',
  crit: '#fc3',
};

/** Render-Depth für Combat-FX. Höher als alles andere (Player = 40). */
const DEPTH_FX = 60;

/** Tween-Dauer für Damage-Numbers (ms). */
const FLOAT_DURATION_MS = 800;
/** Vertikaler Floating-Hub in Pixeln (positiv = nach oben). */
const FLOAT_OFFSET_PX = 36;

export const COMBAT_FX = {
  /**
   * Floating-Number am übergebenen Sprite-Center (oder Tile-Center, wenn
   * `sprite` null ist). Selbst-zerstörend nach Tween-Ende.
   */
  spawnFloatingNumber(
    scene: Phaser.Scene,
    args: {
      readonly x: number;
      readonly y: number;
      readonly text: string;
      readonly kind: FloatingNumberKind;
    },
  ): void {
    const color = COLOR_FOR_KIND[args.kind];
    const text = scene.add.text(args.x, args.y - 8, args.text, {
      fontFamily: 'Arial, sans-serif',
      fontSize: '20px',
      color,
      stroke: '#000000',
      strokeThickness: 3,
    });
    text.setOrigin(0.5, 0.5);
    text.setDepth(DEPTH_FX);
    scene.tweens.add({
      targets: text,
      y: args.y - 8 - FLOAT_OFFSET_PX,
      alpha: { from: 1, to: 0 },
      duration: FLOAT_DURATION_MS,
      ease: 'Cubic.easeOut',
      onComplete: () => text.destroy(),
    });
  },

  /**
   * Kurzer Hit-Spark am Tile (kleiner Stern, scale 0→1→0 über 300ms).
   * Wenn `effect_hit_spark`-Texture geladen ist, wird sie genutzt; sonst
   * ein helles Phaser-Circle als Fallback.
   */
  spawnHitSpark(scene: Phaser.Scene, x: number, y: number): void {
    const texKey = 'effect_hit_spark';
    const sprite: Phaser.GameObjects.GameObject & {
      setOrigin?: (x: number, y: number) => void;
      setDepth?: (d: number) => void;
      setScale?: (s: number) => void;
      setAlpha?: (a: number) => void;
    } = scene.textures.exists(texKey)
      ? scene.add.image(x, y, texKey)
      : scene.add.circle(x, y, 10, 0xffe680, 1);
    sprite.setOrigin?.(0.5, 0.5);
    sprite.setDepth?.(DEPTH_FX);
    sprite.setScale?.(0.2);
    scene.tweens.add({
      targets: sprite,
      scale: { from: 0.2, to: 1.0 },
      alpha: { from: 1, to: 0 },
      duration: 300,
      ease: 'Cubic.easeOut',
      onComplete: () => sprite.destroy(),
    });
  },

  /**
   * Death-Fade: scale 1→0.5, alpha 1→0, dann `onDone()` (Pool-Entfernen).
   * Wirft ein paar weisse Partikel mit, falls die Scene aktiv ist.
   */
  spawnDeathFade(
    scene: Phaser.Scene,
    sprite: Phaser.GameObjects.GameObject,
    args: { readonly x: number; readonly y: number; readonly onDone: () => void },
  ): void {
    const tweenTarget = sprite as Phaser.GameObjects.GameObject & {
      alpha?: number;
      scale?: number;
    };
    scene.tweens.add({
      targets: tweenTarget,
      alpha: 0,
      scale: 0.5,
      duration: 600,
      ease: 'Cubic.easeIn',
      onComplete: () => args.onDone(),
    });
    // 4 kleine weisse Punkte fly-out
    for (let i = 0; i < 4; i++) {
      const angle = (i / 4) * Math.PI * 2 + Math.random() * 0.3;
      const dot = scene.add.circle(args.x, args.y, 3, 0xffffff, 0.9);
      dot.setDepth(DEPTH_FX);
      scene.tweens.add({
        targets: dot,
        x: args.x + Math.cos(angle) * 24,
        y: args.y + Math.sin(angle) * 24,
        alpha: 0,
        duration: 450,
        ease: 'Cubic.easeOut',
        onComplete: () => dot.destroy(),
      });
    }
  },

  /**
   * Kamera-Shake. Intensity skaliert mit `dmg`: cap bei 0.02 (sehr
   * sichtbar, aber nicht motion-sickness-trigger).
   */
  screenShake(scene: Phaser.Scene, dmg: number): void {
    if (dmg <= 10) return;
    const intensity = Math.min(0.02, dmg / 500);
    scene.cameras.main.shake(200, intensity);
  },

  /** Tile-Zentrum in Welt-Pixel. */
  tileCenter(tileX: number, tileY: number): { readonly x: number; readonly y: number } {
    return {
      x: tileX * TILE_SIZE + TILE_SIZE / 2,
      y: tileY * TILE_SIZE + TILE_SIZE / 2,
    };
  },
} as const;
