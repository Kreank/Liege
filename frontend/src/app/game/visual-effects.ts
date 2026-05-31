// VisualEffects — Handler für die `visual_effect`-WS-Frames vom Backend.
//
// Backend sendet `{ type:'visual_effect', kind:'poison_cloud'|'heal_pulse'|
// 'hit_spark'|…, x, y }`. Wir mappen `kind` auf eine vordefinierte
// Animation; wenn keine Spezial-Animation existiert, fallen wir auf einen
// generischen Sprite-Fade aus der `EFFECT_SPRITES`-Map (AssetLoader hat den
// Texture-Key bereits als `effect_<kind>` registriert).
//
// G4 (2026-05-31):
//   Multi-Frame-Pfad zuerst: wenn `EFFECT_ANIMATIONS[kind]` existiert UND
//   die Phaser-Animation `fx_<kind>` registriert ist, spawnen wir einen
//   Phaser.Sprite, spielen `fx_<kind>` einmal und zerstören den Sprite im
//   `animationcomplete`-Hook. Damit sehen Fireball/Lightning/Pestwolke
//   wie echte Effekte aus, nicht wie stehende Bilder mit Alpha-Tween.
//
// Fallback-Pfade (in Reihenfolge):
//   • hit_spark     — siehe `combat-fx.ts::spawnHitSpark` (existierende Logik)
//   • poison_cloud  — Tile-grosse grüne Wolke, alpha 0.6→0 / 1500ms
//   • heal_pulse    — grüner Ring, scale 0.5→2.0 / 500ms
//   • generic       — falls `effect_<kind>`-Texture existiert: scale 0.5→1.2,
//                     alpha 1→0 / 600ms; sonst console.warn + skip.

import Phaser from 'phaser';

import { WORLD_POLISH_ANIMS } from '../core/data/animations';
import { EFFECT_ANIMATIONS } from '../core/data/effect-sprites';
import type { WorldPolishAnim } from '../core/models/animation.model';
import { TILE_SIZE } from '../core/data/tiles';
import { COMBAT_FX } from './combat-fx';

const DEPTH_FX = 60;

// ─── World-Polish (wp_*) ──────────────────────────────────────────────────
// Backend sendet `visual_effect`-Frames mit `kind:'wp_<key>'` (Farming/Bau/
// Work-Overlays, 192×192). Diese mappen per `wp_`-Strip 1:1 auf die
// `WORLD_POLISH_ANIMS`-Keys. Frames werden ON-DEMAND geladen (GPU-Constraint),
// NICHT eager beim Boot — analog `biome-ambient.ts`.
//
// Asset-Pfad-Konvention:
//   /assets/animations/professional/world_polish/<category>/<key>/<key>_<NN>.png
//   <NN> = 1-indexiert, 2-stellig zero-padded.

const WORLD_POLISH_ASSET_BASE =
  '/assets/animations/professional/world_polish';

/** Lookup `key → WorldPolishAnim` (key ohne `wp_`-Prefix). */
const WORLD_POLISH_BY_KEY: Readonly<Record<string, WorldPolishAnim>> =
  Object.fromEntries(WORLD_POLISH_ANIMS.map((a) => [a.key, a]));

/** Keys, deren Frames bereits in den Loader eingereiht wurden (idempotent). */
const _wpRequested = new Set<string>();

const wpTexKey = (key: string, n: number): string =>
  `wp_anim_${key}_${String(n).padStart(2, '0')}`;
const wpAnimKey = (key: string): string => `wp_fx_${key}`;

/**
 * Set der schon einmal gewarnten unbekannten Kinds — vermeidet Console-Spam,
 * wenn das Backend einen Frame in jedem Tick raushaut.
 */
const _warnedMissingKinds = new Set<string>();

export const VISUAL_EFFECTS = {
  /** Dispatch nach kind. Akzeptiert raw `visual_effect`-Frame-Felder. */
  spawn(
    scene: Phaser.Scene,
    args: { readonly kind: string; readonly x: number; readonly y: number },
  ): void {
    const center = {
      x: args.x * TILE_SIZE + TILE_SIZE / 2,
      y: args.y * TILE_SIZE + TILE_SIZE / 2,
    };

    // ── World-Polish-Pfad (wp_*): on-demand geladene Workflow-Overlays. ──
    if (spawnWorldPolish(scene, args.kind, center)) return;

    // ── G4-Pfad: Multi-Frame-Anim, falls vorhanden + registriert. ────────
    if (spawnMultiFrameAnim(scene, args.kind, center.x, center.y)) return;

    // Legacy-Fallbacks (single-Frame).
    switch (args.kind) {
      case 'hit_spark':
        COMBAT_FX.spawnHitSpark(scene, center.x, center.y);
        return;
      case 'poison_cloud':
        spawnPoisonCloud(scene, center.x, center.y);
        return;
      case 'heal_pulse':
        spawnHealPulse(scene, center.x, center.y);
        return;
      default:
        spawnGeneric(scene, args.kind, center.x, center.y);
        return;
    }
  },
} as const;

/**
 * G4 Multi-Frame-Anim-Pfad. Returnt true wenn die Animation gespielt wurde
 * (Caller skippt dann die Fallbacks).
 */
function spawnMultiFrameAnim(
  scene: Phaser.Scene,
  kind: string,
  x: number,
  y: number,
): boolean {
  const spec = EFFECT_ANIMATIONS[kind];
  if (!spec) return false;
  const animKey = `fx_${kind}`;
  if (!scene.anims.exists(animKey)) return false;

  // Erstes Frame als Boot-Texture (Phaser braucht eine valide initiale Texture).
  const firstFrameKey = `effect_anim_${kind}_01`;
  if (!scene.textures.exists(firstFrameKey)) return false;

  const sprite = scene.add.sprite(x, y, firstFrameKey);
  sprite.setOrigin(0.5, 0.5);
  sprite.setDepth(DEPTH_FX);
  const size = TILE_SIZE * spec.tileScale;
  sprite.setDisplaySize(size, size);
  sprite.once('animationcomplete', () => sprite.destroy());
  sprite.anims.play(animKey);
  return true;
}

/**
 * World-Polish-Pfad. Akzeptiert sowohl `wp_<key>` als auch nackten `<key>`.
 * Returnt true, wenn `kind` ein bekannter World-Polish-Effekt ist (Caller
 * skippt dann alle weiteren Fallbacks + den Generic-Warn). Frames werden
 * on-demand geladen; auch der ERSTE Trigger erscheint (leicht verzögert um
 * die Ladezeit).
 */
function spawnWorldPolish(
  scene: Phaser.Scene,
  kind: string,
  center: { readonly x: number; readonly y: number },
): boolean {
  const key = kind.startsWith('wp_') ? kind.slice(3) : kind;
  const spec = WORLD_POLISH_BY_KEY[key];
  if (!spec) return false;

  const animKey = wpAnimKey(key);

  // Anim schon registriert → sofort One-Shot spawnen.
  if (scene.anims.exists(animKey)) {
    playWorldPolishSprite(scene, key, spec, center);
    return true;
  }

  // Sonst: Frames on-demand laden + nach `complete` Anim bauen & abspielen.
  ensureWorldPolishFrames(scene, key, spec, center);
  return true;
}

/** Reiht die Frames eines World-Polish-Keys in den Loader ein (idempotent)
 *  und spielt nach `complete` einen One-Shot an `center` ab. */
function ensureWorldPolishFrames(
  scene: Phaser.Scene,
  key: string,
  spec: WorldPolishAnim,
  center: { readonly x: number; readonly y: number },
): void {
  const dir = `${WORLD_POLISH_ASSET_BASE}/${spec.category}/${key}`;

  if (!_wpRequested.has(key)) {
    _wpRequested.add(key);
    let queued = 0;
    for (let n = 1; n <= spec.frames; n++) {
      const texKey = wpTexKey(key, n);
      if (scene.textures.exists(texKey)) continue;
      const nn = String(n).padStart(2, '0');
      scene.load.image(texKey, `${dir}/${key}_${nn}.png`);
      queued++;
    }
    if (queued > 0) {
      scene.load.once(Phaser.Loader.Events.COMPLETE, () =>
        buildWorldPolishAnimAndPlay(scene, key, spec, center),
      );
      if (!scene.load.isLoading()) scene.load.start();
      return;
    }
  }

  // Frames bereits angefordert/im Cache → direkt bauen + abspielen.
  buildWorldPolishAnimAndPlay(scene, key, spec, center);
}

/** Baut die Phaser-Anim für `key` (idempotent) und spielt einen One-Shot. */
function buildWorldPolishAnimAndPlay(
  scene: Phaser.Scene,
  key: string,
  spec: WorldPolishAnim,
  center: { readonly x: number; readonly y: number },
): void {
  // Alle Frame-Texturen müssen existieren — sonst (404) Effekt überspringen.
  for (let n = 1; n <= spec.frames; n++) {
    if (!scene.textures.exists(wpTexKey(key, n))) return;
  }

  const animKey = wpAnimKey(key);
  if (!scene.anims.exists(animKey)) {
    const frames = [];
    for (let n = 1; n <= spec.frames; n++) {
      frames.push({ key: wpTexKey(key, n) });
    }
    scene.anims.create({
      key: animKey,
      frames,
      frameRate: spec.fps,
      repeat: spec.looping ? -1 : 0,
    });
  }
  playWorldPolishSprite(scene, key, spec, center);
}

/** Spawnt einen One-Shot-Sprite an `center`, spielt die Anim ab und räumt
 *  ihn anschließend wieder weg. */
function playWorldPolishSprite(
  scene: Phaser.Scene,
  key: string,
  spec: WorldPolishAnim,
  center: { readonly x: number; readonly y: number },
): void {
  const firstFrameKey = wpTexKey(key, 1);
  if (!scene.textures.exists(firstFrameKey)) return;

  const sprite = scene.add.sprite(center.x, center.y, firstFrameKey);
  sprite.setOrigin(0.5, 0.5);
  sprite.setDepth(DEPTH_FX);
  sprite.setDisplaySize(TILE_SIZE * 1.5, TILE_SIZE * 1.5);
  sprite.anims.play(wpAnimKey(key));

  if (spec.looping) {
    // Looping-Keys (künftige ambient/social) nicht ewig leben lassen.
    scene.time.delayedCall(1500, () => {
      sprite.anims.stop();
      sprite.destroy();
    });
  } else {
    sprite.once('animationcomplete', () => sprite.destroy());
  }
}

/** Grüne, Tile-grosse Wolke (Legacy-Fallback). */
function spawnPoisonCloud(scene: Phaser.Scene, x: number, y: number): void {
  const texKey = 'effect_poison_cloud';
  let obj: Phaser.GameObjects.GameObject & {
    setOrigin?: (x: number, y: number) => void;
    setDepth?: (d: number) => void;
    setAlpha?: (a: number) => void;
    setDisplaySize?: (w: number, h: number) => void;
  };
  if (scene.textures.exists(texKey)) {
    const img = scene.add.image(x, y, texKey);
    img.setDisplaySize(TILE_SIZE * 1.5, TILE_SIZE * 1.5);
    obj = img;
  } else {
    obj = scene.add.circle(x, y, TILE_SIZE * 0.7, 0x66cc44, 0.6);
  }
  obj.setOrigin?.(0.5, 0.5);
  obj.setDepth?.(DEPTH_FX);
  obj.setAlpha?.(0.6);
  scene.tweens.add({
    targets: obj,
    alpha: { from: 0.6, to: 0 },
    duration: 1500,
    ease: 'Cubic.easeOut',
    onComplete: () => obj.destroy(),
  });
}

/** Grüner Ring, der nach aussen pulst (Legacy-Fallback). */
function spawnHealPulse(scene: Phaser.Scene, x: number, y: number): void {
  const texKey = 'effect_heal_pulse';
  let obj: Phaser.GameObjects.GameObject & {
    setOrigin?: (x: number, y: number) => void;
    setDepth?: (d: number) => void;
    setScale?: (s: number) => void;
    setAlpha?: (a: number) => void;
  };
  if (scene.textures.exists(texKey)) {
    obj = scene.add.image(x, y, texKey);
  } else {
    // Fallback: Doppel-Ring (innen heller, aussen Outline).
    const g = scene.add.graphics({ x, y });
    g.lineStyle(4, 0x88ff88, 0.9);
    g.strokeCircle(0, 0, TILE_SIZE * 0.4);
    obj = g;
  }
  obj.setOrigin?.(0.5, 0.5);
  obj.setDepth?.(DEPTH_FX);
  obj.setScale?.(0.5);
  scene.tweens.add({
    targets: obj,
    scale: { from: 0.5, to: 2.0 },
    alpha: { from: 1, to: 0 },
    duration: 500,
    ease: 'Quad.easeOut',
    onComplete: () => obj.destroy(),
  });
}

/**
 * Generischer Sprite-Fade. Sucht nach `effect_<kind>`-Texture; wenn nicht
 * vorhanden, einmaliger console.warn + skip.
 */
function spawnGeneric(
  scene: Phaser.Scene,
  kind: string,
  x: number,
  y: number,
): void {
  const texKey = `effect_${kind}`;
  if (!scene.textures.exists(texKey)) {
    if (!_warnedMissingKinds.has(kind)) {
      _warnedMissingKinds.add(kind);
      // eslint-disable-next-line no-console
      console.warn('[visual_effect] no sprite for kind, skipping:', kind);
    }
    return;
  }
  const img = scene.add.image(x, y, texKey);
  img.setOrigin(0.5, 0.5);
  img.setDepth(DEPTH_FX);
  img.setScale(0.5);
  scene.tweens.add({
    targets: img,
    scale: { from: 0.5, to: 1.2 },
    alpha: { from: 1, to: 0 },
    duration: 600,
    ease: 'Quad.easeOut',
    onComplete: () => img.destroy(),
  });
}
