// DungeonRenderer — eigene Tile-Map + Feature-Layer für Dungeon-Floors.
//
// Welle H1-A (2026-05-31): Wenn der Spieler in einem Dungeon ist, soll der
// `WorldScene` die Overworld-Chunk-Tiles ausblenden und stattdessen den
// Dungeon-Floor rendern. Floor kommt vom Backend als 2D-Array von Tile-IDs
// (siehe `dungeon_world.py`); Features (Truhen, Decor, getriggerte Fallen)
// liegen daneben in einer separaten Liste.
//
// Warum NICHT die `chunks`-Signal-Replacement-Variante (Plan §8 H1.10)?
//   • Dungeon-Tile-IDs (0=Wand…) ≠ Overworld-Tile-IDs (0=Wasser…). Ein
//     Mapping wäre verlustbehaftet.
//   • Separate Pools + Tile-Layer halten den Mode-Wechsel sauber: beim
//     `dungeon_exit` einfach `clear()` + Overworld-Layer wieder
//     einblenden, kein Mix-Zustand mehr.
//
// Lifecycle:
//   • `show(state)`: rendert Floor + Features + Fade-In.
//   • `swap(state)`: gleiches wie show, aber mit kurzem Fade-Out → render →
//     Fade-In für Floor-Wechsel.
//   • `hide()`: räumt komplett ab (Exit → Overworld).
//   • `markChestOpened(x,y)`: Sprite-Swap auf eine geöffnete Truhe.

import Phaser from 'phaser';

import {
  DUNGEON_FALLBACK_COLORS,
  DUNGEON_FEATURE_SPRITES,
  DUNGEON_TILE,
  DUNGEON_TILE_SPRITE,
} from '../core/data/dungeon-tiles';
import { TILE_SIZE } from '../core/data/tiles';

/** Eingehende Floor-Daten aus `dungeon_enter` / `dungeon_floor_change`. */
export interface DungeonFloorState {
  readonly id: number | string;
  readonly name?: string;
  readonly floorIdx: number;
  readonly floorCount: number;
  readonly size: number;
  readonly tiles: readonly (readonly number[])[];
  readonly spawn: { readonly x: number; readonly y: number };
  /** Features: Truhen (mit opened-Flag), getriggerte Fallen, Decor. */
  readonly features?: {
    readonly chests?: readonly { readonly x: number; readonly y: number; readonly opened?: boolean }[];
    readonly traps?: readonly { readonly x: number; readonly y: number; readonly kind?: string }[];
    readonly decor?: readonly { readonly x: number; readonly y: number; readonly kind: string }[];
  };
}

/** Render-Tiefen für die Dungeon-Layer (passt zu `world-scene.ts::DEPTH`). */
const DEPTH = {
  TILES:    1,
  DECOR:    3,
  FEATURES: 6,
  FADE:     999, // Vor allem anderen
} as const;

/** Fade-Animation-Dauer in ms (ai_fragen.md H1.11). */
export const DUNGEON_FADE_MS = 200;

export class DungeonRenderer {
  private readonly scene: Phaser.Scene;

  /** Container für alle Tile-Images. Wird komplett destroyed bei hide(). */
  private tileContainer: Phaser.GameObjects.Container | null = null;
  /** Container für Feature-Sprites (Chests, Decor, Traps). */
  private featureContainer: Phaser.GameObjects.Container | null = null;
  /** Lookup (x,y) → Feature-Sprite — für `markChestOpened` u. a. */
  private featureLookup = new Map<string, Phaser.GameObjects.GameObject>();
  /** Fullscreen-Schwarz-Overlay für Fade. Persistent (über Mode-Wechsel hinaus). */
  private fadeRect: Phaser.GameObjects.Rectangle | null = null;
  /** Aktiver Floor-State — null wenn nicht im Dungeon. */
  private current: DungeonFloorState | null = null;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /** Liefert den aktuellen Floor-State (oder null wenn aus). */
  active(): DungeonFloorState | null {
    return this.current;
  }

  /**
   * Erstmaliges Anzeigen (dungeon_enter): kurzer Fade-In von schwarz auf
   * den fertig gerenderten Floor.
   */
  show(state: DungeonFloorState): void {
    this.clearAll();
    this.current = state;
    this.renderFloor(state);
    this.renderFeatures(state);
    this.fadeFromBlack();
  }

  /**
   * Floor-Wechsel (dungeon_floor_change): kurzer Fade-Out auf schwarz,
   * dann Re-Render + Fade-In. Async-Animation; der Caller darf parallel
   * den Player-Spawn setzen, das passiert "während es schwarz ist".
   */
  swap(state: DungeonFloorState): void {
    this.current = state;
    this.fadeToBlack(() => {
      this.clearLayers();
      this.renderFloor(state);
      this.renderFeatures(state);
      this.fadeFromBlack();
    });
  }

  /** Komplett verlassen (dungeon_exit): clear + state = null. */
  hide(): void {
    this.clearAll();
    this.current = null;
  }

  /**
   * Sprite-Swap für eine geöffnete Truhe (dungeon_chest_opened).
   * Findet das vorhandene Chest-Sprite über das Lookup, tint+Alpha
   * runter — bis ein dedizierter "open"-Sprite nachgeliefert wird.
   */
  markChestOpened(x: number, y: number): void {
    const key = `${x},${y}`;
    const sprite = this.featureLookup.get(key);
    if (!sprite) return;
    // Tint+Alpha als "geöffnet"-Indikator (siehe ai_fragen.md H2.14
    // Default-Approach; H2.14 selbst hebt das später).
    const withTintAlpha = sprite as Phaser.GameObjects.GameObject & {
      setTint?: (tint: number) => void;
      setAlpha?: (alpha: number) => void;
      setTexture?: (key: string) => void;
    };
    // TODO H2.14: dediziertes "open"-Sprite — bis dahin Tint+Alpha als
    // visueller Indikator (ai_fragen.md Eintrag dungeon-chest-open).
    withTintAlpha.setTint?.(0x665544);
    withTintAlpha.setAlpha?.(0.55);
  }

  // ─── Render-Internals ───────────────────────────────────────────────

  private renderFloor(state: DungeonFloorState): void {
    const container = this.scene.add.container(0, 0);
    container.setDepth(DEPTH.TILES);
    for (let ty = 0; ty < state.tiles.length; ty++) {
      const row = state.tiles[ty];
      if (!row) continue;
      for (let tx = 0; tx < row.length; tx++) {
        const id = row[tx];
        if (id == null) continue;
        const obj = this.buildTileSprite(id, tx, ty);
        container.add(obj);
      }
    }
    this.tileContainer = container;
  }

  private buildTileSprite(
    tileId: number,
    tx: number,
    ty: number,
  ): Phaser.GameObjects.GameObject {
    const cx = tx * TILE_SIZE + TILE_SIZE / 2;
    const cy = ty * TILE_SIZE + TILE_SIZE / 2;
    const textureKey = DUNGEON_TILE_SPRITE[tileId];
    if (textureKey && this.scene.textures.exists(textureKey)) {
      const img = this.scene.add.image(cx, cy, textureKey);
      img.setDisplaySize(TILE_SIZE, TILE_SIZE);
      return img;
    }
    // Fallback-Rect (dunkles Grau für Wand, schwarz für Boden — KEIN
    // Magenta, weil das den Dungeon-Look kaputt machen würde).
    const fallback = DUNGEON_FALLBACK_COLORS[tileId] ?? 0x14121a;
    const rect = this.scene.add.rectangle(cx, cy, TILE_SIZE, TILE_SIZE, fallback, 1);
    // Treppen kriegen zusätzlich eine Outline, damit sie sichtbar bleiben
    // auch ohne dediziertes Sprite.
    if (tileId === DUNGEON_TILE.STAIRS_UP || tileId === DUNGEON_TILE.STAIRS_DOWN) {
      rect.setStrokeStyle(2, 0xffe080, 0.85);
    }
    return rect;
  }

  private renderFeatures(state: DungeonFloorState): void {
    const container = this.scene.add.container(0, 0);
    container.setDepth(DEPTH.FEATURES);
    this.featureLookup.clear();
    const feats = state.features;
    if (feats?.decor) {
      for (const d of feats.decor) {
        const sprite = this.buildFeatureSprite(this.featureSpriteKey(d.kind), d.x, d.y, 0x806040);
        container.add(sprite);
        this.featureLookup.set(`${d.x},${d.y}`, sprite);
      }
    }
    if (feats?.chests) {
      for (const c of feats.chests) {
        const key = c.opened
          ? DUNGEON_FEATURE_SPRITES.chest_opened
          : DUNGEON_FEATURE_SPRITES.chest_closed;
        const sprite = this.buildFeatureSprite(key, c.x, c.y, 0xc0a040);
        container.add(sprite);
        this.featureLookup.set(`${c.x},${c.y}`, sprite);
        if (c.opened) {
          // Visuell "geöffnet": Tint+Alpha runter (siehe markChestOpened).
          const withTintAlpha = sprite as Phaser.GameObjects.GameObject & {
            setTint?: (tint: number) => void;
            setAlpha?: (alpha: number) => void;
          };
          if (key === DUNGEON_FEATURE_SPRITES.chest_closed) {
            withTintAlpha.setTint?.(0x665544);
            withTintAlpha.setAlpha?.(0.55);
          }
        }
      }
    }
    if (feats?.traps) {
      for (const t of feats.traps) {
        const sprite = this.buildFeatureSprite(
          DUNGEON_FEATURE_SPRITES.trap, t.x, t.y, 0xc04040,
        );
        container.add(sprite);
        this.featureLookup.set(`${t.x},${t.y}`, sprite);
      }
    }
    this.featureContainer = container;
  }

  private buildFeatureSprite(
    textureKey: string,
    tx: number,
    ty: number,
    fallbackColor: number,
  ): Phaser.GameObjects.GameObject {
    const cx = tx * TILE_SIZE + TILE_SIZE / 2;
    const cy = ty * TILE_SIZE + TILE_SIZE / 2;
    if (this.scene.textures.exists(textureKey)) {
      const img = this.scene.add.image(cx, cy, textureKey);
      img.setDisplaySize(TILE_SIZE, TILE_SIZE);
      return img;
    }
    // Fallback: kleines Rect ~70% Größe, damit die Tile-Farbe drumherum
    // sichtbar bleibt.
    const size = TILE_SIZE * 0.7;
    const rect = this.scene.add.rectangle(cx, cy, size, size, fallbackColor, 0.85);
    rect.setStrokeStyle(1, 0xffffff, 0.4);
    return rect;
  }

  /** Decor-Kind → Sprite-Key. Unbekannte Kinds fallen auf "altar" zurück. */
  private featureSpriteKey(kind: string): string {
    const lower = kind.toLowerCase();
    if (lower in DUNGEON_FEATURE_SPRITES) {
      return DUNGEON_FEATURE_SPRITES[lower as keyof typeof DUNGEON_FEATURE_SPRITES];
    }
    return DUNGEON_FEATURE_SPRITES.altar;
  }

  // ─── Fade-Animation (ai_fragen.md H1.11: 200ms Default) ───────────

  private ensureFadeRect(): Phaser.GameObjects.Rectangle {
    if (this.fadeRect) return this.fadeRect;
    const cam = this.scene.cameras.main;
    const rect = this.scene.add.rectangle(
      cam.scrollX + cam.width / 2,
      cam.scrollY + cam.height / 2,
      cam.width * 2,
      cam.height * 2,
      0x000000,
      0,
    );
    rect.setDepth(DEPTH.FADE);
    rect.setScrollFactor(0);
    this.fadeRect = rect;
    return rect;
  }

  private fadeFromBlack(): void {
    const rect = this.ensureFadeRect();
    rect.setAlpha(1);
    this.scene.tweens.add({
      targets: rect,
      alpha: 0,
      duration: DUNGEON_FADE_MS,
      ease: 'Cubic.easeOut',
    });
  }

  private fadeToBlack(onMidpoint: () => void): void {
    const rect = this.ensureFadeRect();
    rect.setAlpha(0);
    this.scene.tweens.add({
      targets: rect,
      alpha: 1,
      duration: DUNGEON_FADE_MS,
      ease: 'Cubic.easeIn',
      onComplete: () => onMidpoint(),
    });
  }

  // ─── Cleanup ─────────────────────────────────────────────────────────

  private clearLayers(): void {
    if (this.tileContainer) {
      this.tileContainer.destroy(true);
      this.tileContainer = null;
    }
    if (this.featureContainer) {
      this.featureContainer.destroy(true);
      this.featureContainer = null;
    }
    this.featureLookup.clear();
  }

  private clearAll(): void {
    this.clearLayers();
    if (this.fadeRect) {
      this.fadeRect.destroy();
      this.fadeRect = null;
    }
  }
}
