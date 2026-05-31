// PlaceGhost — semi-transparentes Preview-Sprite am Cursor im Build-Mode (H2.16).
//
// Wenn `bridge.buildMode()` aktiv ist und ein `selectedStructure()` gesetzt
// ist, folgt ein halbtransparentes Preview-Sprite dem Maus-Cursor (Tile-
// snapped). Farbe:
//   • grün  — Tile frei (keine Struktur, kein NPC, kein Player am Tile).
//   • rot   — Tile blockiert (Struktur am Tile, Safe-Zone-Hint kommt vom
//             Backend nicht direkt; wir prüfen NUR Struktur-Kollision, das
//             vermeidet false-negatives — Backend wird beim Place-Click
//             ggf. eine echte Validierung machen und einen Toast schicken).
//
// Implementation:
//   • Ein einziger Sprite/Rectangle als "Ghost" — Texture wird gewechselt
//     wenn `selectedStructure` ändert (über `setStructureKind`).
//   • Position pro `update()` aus dem letzten Pointer-Move (Phaser-Pointer-
//     World-Koords, in Tile umgerechnet).
//   • Hide wenn Build-Mode aus oder kein Strukturtyp gewählt.

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';
import type { Structure } from '../core/models/chunk.model';
import type { AssetLoaderService } from './asset-loader.service';

/** Alpha-Wert für das Preview-Sprite. */
const GHOST_ALPHA = 0.4;
/** Render-Depth: über Strukturen, unter Combat-FX. */
const DEPTH_GHOST = 48;
/** Tint-Farben für valid/invalid. */
const TINT_VALID = 0x66ff88;
const TINT_INVALID = 0xff4444;

/** Pointer-Lookup-Funktion. Caller (WorldScene) übergibt eine, die den
 *  aktuellen Phaser-Pointer (mit Welt-Koords) liefert. */
export type PointerProvider = () => Phaser.Input.Pointer | null;

/** Snapshot-Provider — gibt die aktuellen Strukturen für Kollisions-Check. */
export type StructuresProvider = () => readonly Structure[];

export class PlaceGhost {
  private readonly scene: Phaser.Scene;
  private readonly assetLoader: AssetLoaderService;
  private readonly pointerProvider: PointerProvider;
  private readonly structuresProvider: StructuresProvider;

  private ghost: Phaser.GameObjects.GameObject | null = null;
  /** Aktueller Strukturtyp (für Sprite-Refresh-Diff). */
  private currentKind: string | null = null;
  /** Letzter Tile-State (visible + tile + valid) für Diff-basiertes Re-Draw. */
  private lastVisible = false;
  private lastTileX = Number.NaN;
  private lastTileY = Number.NaN;
  private lastValid = false;

  constructor(
    scene: Phaser.Scene,
    assetLoader: AssetLoaderService,
    pointerProvider: PointerProvider,
    structuresProvider: StructuresProvider,
  ) {
    this.scene = scene;
    this.assetLoader = assetLoader;
    this.pointerProvider = pointerProvider;
    this.structuresProvider = structuresProvider;
  }

  /**
   * Pro Frame: Build-Mode + Strukturtyp prüfen, Ghost positionieren oder
   * verstecken. `buildMode` / `selectedKind` werden vom Caller frisch aus
   * den Bridge-Signals gelesen — wir vermeiden eine eigene Effect-Sub.
   */
  update(buildMode: boolean, selectedKind: string | null): void {
    if (!buildMode || !selectedKind) {
      this.hide();
      return;
    }
    // Strukturtyp gewechselt → Sprite neu bauen.
    if (selectedKind !== this.currentKind) {
      this.rebuildGhost(selectedKind);
      this.currentKind = selectedKind;
    }
    const ptr = this.pointerProvider();
    if (!ptr) {
      this.hide();
      return;
    }
    const tileX = Math.floor(ptr.worldX / TILE_SIZE);
    const tileY = Math.floor(ptr.worldY / TILE_SIZE);
    const blocked = this.isBlocked(tileX, tileY);
    const valid = !blocked;
    this.show(tileX, tileY, valid);
  }

  /** Sauber abräumen (Scene-Shutdown). */
  destroy(): void {
    if (this.ghost) {
      this.ghost.destroy();
      this.ghost = null;
    }
    this.currentKind = null;
    this.lastVisible = false;
  }

  // ─── Internals ──────────────────────────────────────────────────────

  private rebuildGhost(kind: string): void {
    if (this.ghost) {
      this.ghost.destroy();
      this.ghost = null;
    }
    // AssetLoader liefert einen Texture-Key oder null.
    const tex = this.assetLoader.textureKeyFor(kind) ?? `struct_${kind}`;
    let obj: Phaser.GameObjects.GameObject;
    if (this.scene.textures.exists(tex)) {
      const img = this.scene.add.image(0, 0, tex);
      img.setDisplaySize(TILE_SIZE, TILE_SIZE);
      obj = img;
    } else {
      // Fallback: kleines Rectangle in Tile-Größe.
      obj = this.scene.add.rectangle(0, 0, TILE_SIZE, TILE_SIZE, 0xffffff, 0.5);
    }
    const withSetters = obj as Phaser.GameObjects.GameObject & {
      setAlpha?: (a: number) => void;
      setDepth?: (d: number) => void;
      setOrigin?: (x: number, y: number) => void;
      setVisible?: (v: boolean) => void;
    };
    withSetters.setAlpha?.(GHOST_ALPHA);
    withSetters.setDepth?.(DEPTH_GHOST);
    withSetters.setOrigin?.(0.5, 0.5);
    withSetters.setVisible?.(false); // Bis erster Update-Call sichtbar.
    this.ghost = obj;
    this.lastVisible = false;
    this.lastTileX = Number.NaN;
    this.lastTileY = Number.NaN;
    this.lastValid = false;
  }

  private show(tileX: number, tileY: number, valid: boolean): void {
    if (!this.ghost) return;
    const cx = tileX * TILE_SIZE + TILE_SIZE / 2;
    const cy = tileY * TILE_SIZE + TILE_SIZE / 2;
    // Diff-Skip: gleiche Position + gleiche Validität → kein Re-Apply.
    if (
      this.lastVisible &&
      this.lastTileX === tileX &&
      this.lastTileY === tileY &&
      this.lastValid === valid
    ) {
      return;
    }
    const withSetters = this.ghost as Phaser.GameObjects.GameObject & {
      x?: number; y?: number;
      setTint?: (tint: number) => void;
      setVisible?: (v: boolean) => void;
    };
    withSetters.x = cx;
    withSetters.y = cy;
    withSetters.setTint?.(valid ? TINT_VALID : TINT_INVALID);
    withSetters.setVisible?.(true);
    this.lastVisible = true;
    this.lastTileX = tileX;
    this.lastTileY = tileY;
    this.lastValid = valid;
  }

  private hide(): void {
    if (!this.ghost) return;
    if (!this.lastVisible) return;
    const withSetters = this.ghost as Phaser.GameObjects.GameObject & {
      setVisible?: (v: boolean) => void;
    };
    withSetters.setVisible?.(false);
    this.lastVisible = false;
  }

  /** Tile-Belegungs-Check: Struktur an (x,y)? Sehr schmal — Backend macht
   *  die echte Place-Validierung (Safe-Zone, Owner-Check, …) bei `place_structure`. */
  private isBlocked(tileX: number, tileY: number): boolean {
    const structures = this.structuresProvider();
    for (const s of structures) {
      if (s.x === tileX && s.y === tileY) return true;
    }
    return false;
  }
}
