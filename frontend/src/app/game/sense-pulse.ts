// SensePulse — kreisförmiger Pulse-Ring am Spieler bei `dungeon_sense` (H3.10).
//
// Backend feuert `dungeon_sense {dungeons: [{x, y, tier}]}` (kein expliziter
// `radius`-Feld — siehe ai_fragen.md H3.10). Visualisierung: ein Ring
// expandiert aus dem Player-Center mit dem Default-Sense-Radius (~70 Tiles
// Chebyshev), alpha 0.6 → 0, Dauer ~2 s.
//
// Trigger: `pulse(centerTile?)` — Caller (WorldScene) ruft das beim
// `dungeon_sense`-Event-Frame. Wenn die Player-Position später wechselt,
// folgt der Ring NICHT mit (Pulse ist ein einmaliges Snapshot-Visual).
//
// Mehrfach-Pulse: erlaubt — jeder Aufruf spawnt einen eigenen Ring. Bei
// rapider Backend-Wiederholung (z. B. Reaper bei Dungeon-Ablauf) sieht das
// nach einem "Radar-Sweep" aus, was visuell angemessen ist.

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';

/** Render-Depth: über Welt, knapp unter Combat-FX. */
const DEPTH_PULSE = 53;
/** Default-Sense-Radius in Tiles (Backend-Kommentar dungeon_director.py:128). */
const DEFAULT_SENSE_RANGE_TILES = 70;
/** Pulse-Dauer (ms). */
const PULSE_DURATION_MS = 2000;
/** Pulse-Startradius (px) — knapp größer als ein Tile, damit der Ring nicht
 *  als Punkt anfängt. */
const PULSE_START_RADIUS = TILE_SIZE * 0.5;
/** Start-Alpha; tweenen wir auf 0. */
const PULSE_START_ALPHA = 0.6;
/** Linien-Breite (px). */
const PULSE_LINE_WIDTH = 3;
/** Ring-Farbe (cyan-türkis — passt zum "magisches Spüren"-Stil). */
const PULSE_COLOR = 0x66ffee;

export class SensePulse {
  private readonly scene: Phaser.Scene;
  /** Aktive Pulse-Graphics (für Scene-Cleanup). */
  private readonly active = new Set<Phaser.GameObjects.Arc>();

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /**
   * Spawnt einen Pulse-Ring am gegebenen Tile (typischerweise Player-Pos).
   * `rangeTiles` ist optional — Default = 70 (siehe Backend-Konstante).
   */
  pulse(centerTileX: number, centerTileY: number, rangeTiles?: number): void {
    const range = Math.max(8, rangeTiles ?? DEFAULT_SENSE_RANGE_TILES);
    const cx = centerTileX * TILE_SIZE + TILE_SIZE / 2;
    const cy = centerTileY * TILE_SIZE + TILE_SIZE / 2;
    const maxRadius = range * TILE_SIZE;

    const ring = this.scene.add.circle(cx, cy, PULSE_START_RADIUS, PULSE_COLOR, 0);
    ring.setStrokeStyle(PULSE_LINE_WIDTH, PULSE_COLOR, PULSE_START_ALPHA);
    ring.setDepth(DEPTH_PULSE);
    this.active.add(ring);

    // Radius-Tween (linear), Alpha-Tween (Sine.easeOut für sanftes Ausfaden).
    this.scene.tweens.add({
      targets: ring,
      radius: maxRadius,
      duration: PULSE_DURATION_MS,
      ease: 'Cubic.easeOut',
      onUpdate: () => {
        // Phaser-Arc rendert sich aus `radius` neu, aber `setStrokeStyle`
        // mit Alpha greift nicht beim Tween der `strokeAlpha`-Property
        // (existiert nicht direkt) — daher tweenen wir den Container-Alpha
        // separat unten. Hier nur sicherstellen, dass setRadius greift.
        if (typeof (ring as Phaser.GameObjects.Arc & { setRadius?: (r: number) => void }).setRadius === 'function') {
          (ring as Phaser.GameObjects.Arc & { setRadius: (r: number) => void }).setRadius(ring.radius);
        }
      },
    });
    this.scene.tweens.add({
      targets: ring,
      alpha: 0,
      duration: PULSE_DURATION_MS,
      ease: 'Sine.easeOut',
      onComplete: () => {
        this.active.delete(ring);
        ring.destroy();
      },
    });
  }

  /** Convenience für den Event-Payload `dungeon_sense`. Pickt das größte
   *  `radius`-Feld der Dungeons (falls Backend später eines ergänzt) und
   *  fällt sonst auf den Default zurück. */
  pulseFromEvent(
    centerTileX: number,
    centerTileY: number,
    dungeons: readonly { readonly radius?: number }[] | undefined,
  ): void {
    let maxRange = 0;
    if (dungeons) {
      for (const d of dungeons) {
        if (typeof d.radius === 'number' && d.radius > maxRange) maxRange = d.radius;
      }
    }
    this.pulse(centerTileX, centerTileY, maxRange > 0 ? maxRange : undefined);
  }

  /** Scene-Shutdown — alle laufenden Pulses abbrechen. */
  destroyAll(): void {
    for (const ring of this.active) {
      this.scene.tweens.killTweensOf(ring);
      ring.destroy();
    }
    this.active.clear();
  }
}
