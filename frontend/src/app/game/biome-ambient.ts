// BiomeAmbient — viewport-füllendes, animiertes Biom-Ambient-Overlay.
//
// Verdrahtet die bisher toten `BIOME_AMBIENT_DEFS` + `BIOME_AMBIENT_BY_TILE`
// aus `core/data/animations.ts` mit echtem Rendering. Analog zu
// `weather-particles.ts`:
//   • Self-contained Klasse, Konstruktor `(scene)`, `update(tileId)` pro
//     Frame, `destroy()` beim Shutdown.
//   • Ein einzelnes Sprite, viewport-gebunden via `setScrollFactor(0)`,
//     eigener Depth (knapp unter Weather=60, damit Wetter darüber liegt).
//
// On-Demand-Loading (GPU-Constraint RTX 3070 8GB):
//   • Es werden NUR die Frames des gerade aktiven Bioms geladen — lazy, beim
//     ersten Wechsel auf dieses Biom (analog `ensureSingle` im
//     asset-loader.service). `scene.load.image(...)` + `scene.load.start()`
//     zur Laufzeit; die Phaser-Anim wird erst nach `complete` gebaut +
//     abgespielt.
//   • Frame-Pfad-Konvention: `/assets/animations/biomes/<id>_<n>.png`,
//     n ist 1-indexiert, NICHT null-gepadded.

import Phaser from 'phaser';

import {
  BIOME_AMBIENT_BY_TILE,
  BIOME_AMBIENT_FRAMES,
  BIOME_AMBIENT_MS,
} from '../core/data/animations';

/** Render-Depth: knapp unter Weather (DEPTH_WEATHER=60), damit Wetter-
 *  Partikel über dem Biom-Dunst liegen. */
const DEPTH_BIOME_AMBIENT = 58;

/** Asset-Basis-Pfad für Biom-Ambient-Frames. */
// Upgrade 2026-05-31: das höherwertige "professional"-Set (12 Frames pro Biom,
// je in eigenem Unterordner, Frames 2-stellig zero-padded) statt des einfachen
// 6-Frame-Flat-Sets. Pfad: <BASE>/<id>/<id>_<NN>.png
const BIOME_ASSET_BASE = '/assets/animations/professional/biomes';

const texKey = (id: string, frame: number): string => `__biome_${id}_${frame}`;
const animKey = (id: string): string => `__biome_anim_${id}`;

export class BiomeAmbient {
  private readonly scene: Phaser.Scene;
  /** Das Overlay-Sprite (lazy beim ersten aktiven Biom angelegt). */
  private sprite: Phaser.GameObjects.Sprite | null = null;
  /** Aktuell sichtbare/abgespielte Biom-Def-ID (zum Diffen). */
  private currentId: string | null = null;
  /** Biom-IDs, deren Frames bereits in den Loader eingereiht wurden. */
  private readonly requested = new Set<string>();
  /** Biom-IDs, deren Phaser-Anim bereits gebaut + fertig geladen ist. */
  private readonly ready = new Set<string>();
  /** Resize-Listener (für Cleanup). */
  private readonly onResize: () => void;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
    this.onResize = (): void => this.resizeSprite();
    this.scene.scale.on(Phaser.Scale.Events.RESIZE, this.onResize);
  }

  /**
   * Pro Frame: aus `tileId` das aktive Biom + Alpha bestimmen.
   *   • kein Mapping (tileId null / nicht in der Map) → Overlay ausblenden.
   *   • Biom-Wechsel → on-demand laden + anschließend abspielen.
   */
  update(tileId: number | null): void {
    const entry = tileId == null ? undefined : BIOME_AMBIENT_BY_TILE[tileId];

    if (!entry) {
      // Kein Biom unter dem Spieler → ausblenden, KEIN Rebuild.
      if (this.sprite && this.sprite.visible) this.sprite.setVisible(false);
      this.currentId = null;
      return;
    }

    if (entry.id !== this.currentId) {
      this.currentId = entry.id;
      this.activate(entry.id, entry.alpha);
    } else if (this.sprite) {
      // Gleiches Biom — nur Sichtbarkeit/Alpha sicherstellen (z.B. nach einer
      // ausgeblendeten Phase ohne Biom).
      if (!this.sprite.visible && this.ready.has(entry.id)) {
        this.sprite.setVisible(true);
      }
      this.sprite.setAlpha(entry.alpha);
    }
  }

  /** Scene-Shutdown — Sprite + Listener wegräumen. */
  destroy(): void {
    this.scene.scale.off(Phaser.Scale.Events.RESIZE, this.onResize);
    if (this.sprite) {
      this.sprite.destroy();
      this.sprite = null;
    }
    this.currentId = null;
    this.requested.clear();
    this.ready.clear();
  }

  // ─── Internals ────────────────────────────────────────────────────────

  /** Aktiviert das Biom `id`: Anim sofort abspielen wenn schon fertig,
   *  sonst Frames on-demand laden und nach `complete` abspielen. */
  private activate(id: string, alpha: number): void {
    if (this.ready.has(id)) {
      this.play(id, alpha);
      return;
    }
    this.ensureFrames(id);
    // Wenn beim load-complete dieses Biom noch aktiv ist → abspielen.
    // (`update()` setzt currentId; bis dahin Overlay aus.)
    if (this.sprite && this.sprite.visible) this.sprite.setVisible(false);
  }

  /** Reiht die Frames eines Bioms in den Phaser-Loader ein (idempotent) und
   *  baut nach `complete` die Anim. */
  private ensureFrames(id: string): void {
    if (this.requested.has(id)) return;
    this.requested.add(id);

    const frameCount = BIOME_AMBIENT_FRAMES[id] ?? 0;
    if (frameCount <= 0) return;

    let queued = 0;
    for (let n = 1; n <= frameCount; n++) {
      const key = texKey(id, n);
      if (this.scene.textures.exists(key)) continue;
      const nn = String(n).padStart(2, '0');
      this.scene.load.image(key, `${BIOME_ASSET_BASE}/${id}/${id}_${nn}.png`);
      queued++;
    }

    const finish = (): void => this.buildAnimAndMaybePlay(id);

    if (queued === 0) {
      // Alle Frames bereits im Cache → direkt bauen.
      finish();
      return;
    }

    // Nach Abschluss des aktuellen Load-Batches die Anim bauen. `complete`
    // feuert für die gesamte Queue; wir bauen idempotent.
    this.scene.load.once(Phaser.Loader.Events.COMPLETE, finish);
    if (!this.scene.load.isLoading()) this.scene.load.start();
  }

  /** Baut die Phaser-Anim für `id` (idempotent) und spielt sie ab, sofern
   *  das Biom noch das aktive ist. */
  private buildAnimAndMaybePlay(id: string): void {
    const frameCount = BIOME_AMBIENT_FRAMES[id] ?? 0;
    if (frameCount <= 0) return;

    // Alle Frame-Texturen müssen existieren — sonst (404) Biom überspringen.
    for (let n = 1; n <= frameCount; n++) {
      if (!this.scene.textures.exists(texKey(id, n))) return;
    }

    if (!this.scene.anims.exists(animKey(id))) {
      const frames = [];
      for (let n = 1; n <= frameCount; n++) {
        frames.push({ key: texKey(id, n) });
      }
      const ms = BIOME_AMBIENT_MS[id] ?? 100;
      this.scene.anims.create({
        key: animKey(id),
        frames,
        frameRate: 1000 / ms,
        repeat: -1,
      });
    }
    this.ready.add(id);

    // Nur abspielen, wenn das Biom noch aktiv ist (Spieler könnte inzwischen
    // weitergelaufen sein).
    if (this.currentId === id) {
      const alpha = BIOME_AMBIENT_BY_TILE[this.tileIdFor(id)]?.alpha ?? 0.2;
      this.play(id, alpha);
    }
  }

  /** Liefert irgendeine Tile-ID, die auf `id` mappt (für Alpha-Lookup beim
   *  verspäteten load-complete). Fällt auf -1 zurück. */
  private tileIdFor(id: string): number {
    for (const [tile, def] of Object.entries(BIOME_AMBIENT_BY_TILE)) {
      if (def.id === id) return Number(tile);
    }
    return -1;
  }

  /** Spielt die (fertige) Anim auf dem viewport-füllenden Sprite. */
  private play(id: string, alpha: number): void {
    const sprite = this.ensureSprite();
    sprite.setVisible(true);
    sprite.setAlpha(alpha);
    sprite.play(animKey(id), true);
    this.resizeSprite();
  }

  /** Lazy: Overlay-Sprite anlegen (erst beim ersten aktiven Biom). */
  private ensureSprite(): Phaser.GameObjects.Sprite {
    if (this.sprite) return this.sprite;
    const cam = this.scene.cameras.main;
    const sprite = this.scene.add.sprite(cam.width / 2, cam.height / 2, '');
    sprite.setOrigin(0.5, 0.5);
    sprite.setScrollFactor(0);
    sprite.setDepth(DEPTH_BIOME_AMBIENT);
    sprite.setVisible(false);
    this.sprite = sprite;
    return sprite;
  }

  /** Sprite auf Viewport-Größe ziehen + zentrieren. */
  private resizeSprite(): void {
    if (!this.sprite) return;
    const cam = this.scene.cameras.main;
    this.sprite.setPosition(cam.width / 2, cam.height / 2);
    this.sprite.setDisplaySize(cam.width, cam.height);
  }
}
