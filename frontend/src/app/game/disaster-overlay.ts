// DisasterOverlay — globale Disaster-Visuals für die WorldScene (G4).
//
// Backend-Signale:
//   • `disaster_started { kind, x?, y? }` — z. B. `bloodmoon`, `pestilence`,
//     `wildfire`, `dying_sun`, `thunderstorm`, `scorching_heat`, `ash_rain`.
//   • `disaster_ended { kind }` — Effekt entfernen.
//   • `earthquake_shake { intensity, duration_ms }` — Camera-Shake
//     (direkt in WorldScene gehandhabt, nicht hier).
//   • `lightning_strike { x, y }` — Bolt-Animation am Tile (siehe
//     `spawnLightningBolt`).
//
// Rendering-Schema:
//   • Bloodmoon / dying_sun: Vollbild-Rectangle in der UI-Camera mit Alpha-
//     Tint (rot bzw. orange-dunkel). Skaliert mit Viewport.
//   • Pestilence: grüne Particle-Bursts auf zufälligen Tiles im Viewport
//     (alle ~1.2 s ein neuer Burst). Verschwindet bei `disaster_ended`.
//   • Wildfire: Globaler Smoke-Tint + Ember-Bursts; keine fire_tile-
//     Strukturen werden gerendert (kommt vom Backend als Struktur-Snapshot).
//   • Thunderstorm: Dunkler grau-blauer Tint; Lightning kommt als
//     separates `lightning_strike`-Event pro Bolt.
//   • Lightning-Bolt: spielt `fx_disaster_thunderstorm_strike` am Tile +
//     kurzer weißer Vollbild-Flash + Hook-Punkt für SFX (TODO).

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';
import type { EffectAnimationsService } from './effect-animations.service';

/** Tint-Konfiguration pro Disaster-Kind. */
interface DisasterTintCfg {
  /** Hex-Farbe (0xRRGGBB). */
  readonly color: number;
  /** Alpha 0..1. */
  readonly alpha: number;
}

const TINT_CFG: Readonly<Record<string, DisasterTintCfg>> = {
  bloodmoon:     { color: 0x880000, alpha: 0.32 },
  dying_sun:     { color: 0x553311, alpha: 0.40 },
  thunderstorm:  { color: 0x2030a0, alpha: 0.18 },
  scorching_heat:{ color: 0xff8844, alpha: 0.16 },
  ash_rain:      { color: 0x444444, alpha: 0.22 },
  wildfire:      { color: 0xaa3300, alpha: 0.18 },
};

/** Layer-Keys pro Disaster-Kind für Particle/Tile-Anims. */
const PARTICLE_LAYERS: Readonly<Record<string, readonly string[]>> = {
  pestilence:    ['pestilence_drift', 'pestilence_bubble'],
  wildfire:      ['wildfire_smoke', 'wildfire_ember'],
  ash_rain:      ['ash_rain_flake'],
  scorching_heat:['scorching_heat_shimmer'],
  locust_swarm:  ['locust_swarm_density'],
};

/** Lightning-Flash-Dauer. */
const LIGHTNING_FLASH_MS = 180;

/** Particle-Spawn-Intervall (ms) für anhaltende Disaster. */
const PARTICLE_TICK_MS = 1200;

/** Max gleichzeitige Particle-Sprites pro Layer (Performance-Cap). */
const PARTICLE_MAX = 18;

/** Render-Depth-Konstanten (Overlay liegt über allem ausser UI). */
const DEPTH_PARTICLE = 55;
const DEPTH_BOLT = 65;
const DEPTH_TINT = 70;
const DEPTH_FLASH = 80;

export class DisasterOverlay {
  /** Aktive Disasters: kind → Cleanup-Funktion. */
  private readonly active = new Map<string, () => void>();

  constructor(
    private readonly scene: Phaser.Scene,
    private readonly effectAnims: EffectAnimationsService,
  ) {}

  /** Backend-Event `disaster_started`. */
  startDisaster(kind: string, _hint: { readonly x: number | null; readonly y: number | null }): void {
    if (this.active.has(kind)) {
      // Bereits aktiv (Backend-Re-Send) — alten Cleanup laufen lassen + neu starten.
      this.endDisaster(kind);
    }
    const cleanups: (() => void)[] = [];

    const tint = TINT_CFG[kind];
    if (tint) {
      cleanups.push(this.spawnFullscreenTint(tint));
    }

    const layers = PARTICLE_LAYERS[kind];
    if (layers && layers.length > 0) {
      cleanups.push(this.startParticleEmitter(layers));
    }

    if (kind === 'thunderstorm') {
      // Backend triggert ggf. zusätzlich `lightning_strike`-Events; nichts
      // weiter zu tun hier (Tint ist über TINT_CFG abgedeckt).
    }

    if (kind === 'bloodmoon' || kind === 'dying_sun') {
      // Subtile Slow-Pulse-Animation auf dem Tint (atmen).
      // Aktuell rein statisch — Pulse-Erweiterung folgt bei Bedarf.
    }

    this.active.set(kind, () => {
      for (const fn of cleanups) {
        try { fn(); } catch (e) { console.warn('[disaster] cleanup error', e); }
      }
    });
  }

  /** Backend-Event `disaster_ended`. */
  endDisaster(kind: string): void {
    const cleanup = this.active.get(kind);
    if (!cleanup) return;
    this.active.delete(kind);
    cleanup();
  }

  /** Backend-Event `lightning_strike { x, y }` — Bolt am Tile + Flash. */
  spawnLightningBolt(tileX: number, tileY: number): void {
    const cx = tileX * TILE_SIZE + TILE_SIZE / 2;
    const cy = tileY * TILE_SIZE + TILE_SIZE / 2;
    const animKey = this.effectAnims.disasterAnimKey('thunderstorm_strike');
    const firstFrame = `disaster_anim_thunderstorm_strike_01`;
    if (this.scene.anims.exists(animKey) && this.scene.textures.exists(firstFrame)) {
      const sprite = this.scene.add.sprite(cx, cy, firstFrame);
      sprite.setOrigin(0.5, 0.9); // Bolt steht auf dem Tile
      sprite.setDepth(DEPTH_BOLT);
      sprite.setDisplaySize(TILE_SIZE * 2.0, TILE_SIZE * 4.0);
      sprite.once(Phaser.Animations.Events.ANIMATION_COMPLETE, () => sprite.destroy());
      sprite.anims.play(animKey);
    } else {
      // Fallback: heller Strich als Graphics-Line.
      const g = this.scene.add.graphics({ x: cx, y: cy });
      g.lineStyle(4, 0xfff8c0, 1);
      g.lineBetween(0, -TILE_SIZE * 4, 0, TILE_SIZE * 0.5);
      g.setDepth(DEPTH_BOLT);
      this.scene.tweens.add({
        targets: g,
        alpha: 0,
        duration: 300,
        onComplete: () => g.destroy(),
      });
    }
    this.spawnFlash();
    // Sound-Hook: noch nicht implementiert, nur Log.
    // eslint-disable-next-line no-console
    console.log('[disaster] lightning_strike', { x: tileX, y: tileY });
  }

  // ─── Internals ───────────────────────────────────────────────────────

  /** Vollbild-Rectangle in der Haupt-Kamera, mit Alpha-Tint. */
  private spawnFullscreenTint(cfg: DisasterTintCfg): () => void {
    const cam = this.scene.cameras.main;
    const rect = this.scene.add.rectangle(0, 0, cam.width, cam.height, cfg.color, cfg.alpha);
    rect.setOrigin(0, 0);
    rect.setDepth(DEPTH_TINT);
    rect.setScrollFactor(0); // Fix an Viewport, scrollt nicht mit Kamera.
    // Resize-Listener, damit der Tint bei Window-Resize mitwächst.
    const onResize = (): void => {
      rect.setSize(cam.width, cam.height);
    };
    this.scene.scale.on(Phaser.Scale.Events.RESIZE, onResize);
    return () => {
      this.scene.scale.off(Phaser.Scale.Events.RESIZE, onResize);
      rect.destroy();
    };
  }

  /**
   * Spawnt periodisch Partikel-Sprites mit den gegebenen Disaster-Layer-Anims
   * an zufälligen Tiles im sichtbaren Kamera-Viewport. Sprites laufen einmal
   * durch und zerstören sich; das Tick-Intervall hält max PARTICLE_MAX
   * gleichzeitige Sprites pro Layer.
   */
  private startParticleEmitter(layerKeys: readonly string[]): () => void {
    const liveSprites = new Set<Phaser.GameObjects.Sprite>();
    const tick = (): void => {
      const cam = this.scene.cameras.main;
      const viewW = cam.width;
      const viewH = cam.height;
      const wx = cam.scrollX;
      const wy = cam.scrollY;
      // Spawne 1-2 Sprites pro Layer pro Tick.
      for (const layerKey of layerKeys) {
        if (liveSprites.size >= PARTICLE_MAX) continue;
        const animKey = this.effectAnims.disasterAnimKey(layerKey);
        const firstFrame = `disaster_anim_${layerKey}_01`;
        if (!this.scene.anims.exists(animKey) || !this.scene.textures.exists(firstFrame)) continue;
        const x = wx + Math.random() * viewW;
        const y = wy + Math.random() * viewH;
        const sprite = this.scene.add.sprite(x, y, firstFrame);
        sprite.setOrigin(0.5, 0.5);
        sprite.setDepth(DEPTH_PARTICLE);
        sprite.setDisplaySize(TILE_SIZE * 1.5, TILE_SIZE * 1.5);
        sprite.setAlpha(0.7);
        liveSprites.add(sprite);
        sprite.anims.play({ key: animKey, repeat: 2 });
        sprite.once(Phaser.Animations.Events.ANIMATION_COMPLETE, () => {
          this.scene.tweens.add({
            targets: sprite,
            alpha: 0,
            duration: 400,
            onComplete: () => {
              liveSprites.delete(sprite);
              sprite.destroy();
            },
          });
        });
      }
    };
    const timer = this.scene.time.addEvent({
      delay: PARTICLE_TICK_MS,
      loop: true,
      callback: tick,
    });
    tick(); // Initial-Spawn.
    return () => {
      timer.remove();
      for (const s of liveSprites) s.destroy();
      liveSprites.clear();
    };
  }

  /** Kurzer weißer Vollbild-Flash (Lightning). */
  private spawnFlash(): void {
    const cam = this.scene.cameras.main;
    const flash = this.scene.add.rectangle(0, 0, cam.width, cam.height, 0xffffff, 0.6);
    flash.setOrigin(0, 0);
    flash.setDepth(DEPTH_FLASH);
    flash.setScrollFactor(0);
    this.scene.tweens.add({
      targets: flash,
      alpha: 0,
      duration: LIGHTNING_FLASH_MS,
      ease: 'Quad.easeOut',
      onComplete: () => flash.destroy(),
    });
  }
}
