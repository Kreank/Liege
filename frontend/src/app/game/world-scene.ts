// WorldScene — Phaser-Scene, die NUR rendert und Input → Intent übersetzt.
//
// Strikte Trennung zum Legacy-Monolithen:
//   • State kommt aus `bridge.state` (= GameStateService) per Signal-Read.
//   • Eingaben (Klick, Tasten, Touch) werden zu `bridge.sendIntent(...)`.
//   • KEIN `innerHTML`, KEIN `getElementById`, KEINE DOM-Manipulation.
//   • UI-Panels (Inventar, Hotbar, Skills, …) sind hier nicht zuständig —
//     siehe `legacy-stubs.ts` (F5-F15 wandert sie nach Angular).
//
// F4a-Scope (dieser Commit):
//   • Asset-Preload für die zehn Biome-Tiles (TILE_BY_ID).
//   • TileLayer: rendert die Chunks aus `state.chunks()` als Phaser-Images.
//   • Wiederholtes Lesen pro `update()` — der Tile-Layer wird nur bei
//     Chunk-Liste-Änderung (Identitäts-Check) neu aufgebaut, weil die
//     Signals immutable neue Arrays zurückgeben.
//
// F4b kommt: Sprites (Spieler/NPC/Struktur/Ground-Items).
// F4c kommt: Klick→Move, Tasten, Kamera-Follow.

import Phaser from 'phaser';

import { TILE, TILE_BY_ID, TILE_SIZE } from '../core/data/tiles';
import type { Chunk } from '../core/models/chunk.model';
import type { GameBridgeService } from '../core/services/game-bridge.service';

/** Init-Daten, die `PhaserGameComponent` per `scene.start('WorldScene',{...})` durchreicht. */
export interface WorldSceneInitData {
  readonly bridge: GameBridgeService;
}

export class WorldScene extends Phaser.Scene {
  /** Bridge wird in `init()` aus den Scene-Start-Daten gesetzt. */
  private bridge!: GameBridgeService;

  /** Container für alle Tile-Images, einer pro Chunk (key `"cx,cy"`). */
  private readonly chunkContainers = new Map<string, Phaser.GameObjects.Container>();

  /** Letzter gerenderter Chunk-Array-Identity-Check (vermeidet Re-Render bei No-Op). */
  private lastChunksRef: readonly Chunk[] | null = null;

  /** Chunk-Größe vom Backend (kommt mit `init`-Message, default 32). */
  private chunkSize = 32;

  constructor() {
    super({ key: 'WorldScene' });
  }

  // Phaser-Scene-Lifecycle-Hooks sind in den Typings nicht als Methoden
  // deklariert (Phaser fügt sie zur Laufzeit auf der Subclass-Instanz auf),
  // daher kein `override`-Keyword möglich.
  init(data: WorldSceneInitData): void {
    this.bridge = data.bridge;
  }

  preload(): void {
    // Nur die Tile-Texturen für F4a. Sprites/Strukturen folgen in F4b.
    // Pfade sind absolut (`/assets/...`) — FastAPI mountet das Verzeichnis.
    for (const def of Object.values(TILE)) {
      this.load.image(def.sprite, `/assets/tiles/${this.tileFilename(def.sprite)}`);
    }
  }

  /** `tile_grass` → `grass.png`. */
  private tileFilename(spriteKey: string): string {
    return spriteKey.replace(/^tile_/, '') + '.png';
  }

  create(): void {
    this.cameras.main.setBackgroundColor('#0a0a0f');
    // Aus der `init`-Snapshot (im GameStateService gesetzt) holen wir die
    // Chunk-Größe. Default 32 stimmt für aktuelles Backend.
    const size = this.bridge.state.chunkSize();
    if (size > 0) this.chunkSize = size;
  }

  override update(_time: number, _delta: number): void {
    // Pro Frame: prüfen, ob die Chunk-Liste sich identitätsmäßig geändert
    // hat (Signal liefert immutable Arrays). Wenn ja → Layer rebuild.
    // Günstiger Identity-Check; kein Deep-Equal.
    const chunks = this.bridge.state.chunks();
    if (chunks !== this.lastChunksRef) {
      this.lastChunksRef = chunks;
      this.syncTileLayer(chunks);
    }
  }

  // ─── Tile-Layer-Rendering ──────────────────────────────────────────────

  /**
   * Inkrementeller Rebuild: neue Chunks → Container anlegen; entfernte
   * Chunks → Container destroyen. Vorhandene Container bleiben unverändert
   * (Identity-Vergleich am Chunk selbst entscheidet ob ein Re-Layout nötig
   * wäre — aktuell verzichten wir auf Per-Chunk-Diff, das Backend sendet
   * Chunks als einmaliges Snapshot bzw. neue Chunks am Rand).
   */
  private syncTileLayer(chunks: readonly Chunk[]): void {
    const seen = new Set<string>();
    for (const ch of chunks) {
      const key = `${ch.cx},${ch.cy}`;
      seen.add(key);
      if (this.chunkContainers.has(key)) continue;
      this.renderChunk(ch);
    }
    // Entfernte Chunks räumen (kommt im Backend selten vor — hauptsächlich
    // wenn der Server eine Chunk-Range invalidiert).
    for (const [key, container] of this.chunkContainers) {
      if (!seen.has(key)) {
        container.destroy();
        this.chunkContainers.delete(key);
      }
    }
  }

  /** Baut den Tile-Container für einen einzelnen Chunk. */
  private renderChunk(chunk: Chunk): void {
    const baseX = chunk.cx * this.chunkSize * TILE_SIZE;
    const baseY = chunk.cy * this.chunkSize * TILE_SIZE;
    const container = this.add.container(baseX, baseY);
    container.setDepth(0);   // Tile-Layer ganz unten.

    for (let ty = 0; ty < chunk.tiles.length; ty++) {
      const row = chunk.tiles[ty];
      if (!row) continue;
      for (let tx = 0; tx < row.length; tx++) {
        const id = row[tx];
        if (id == null) continue;
        const def = TILE_BY_ID[id];
        if (!def) continue;
        const img = this.add.image(
          tx * TILE_SIZE + TILE_SIZE / 2,
          ty * TILE_SIZE + TILE_SIZE / 2,
          def.sprite,
        );
        // Tiles sind Quadrate; ohne explizite Size-Anpassung skaliert Phaser
        // sie 1:1 — falls die Quelle nicht exakt TILE_SIZE ist, gleichmäßig
        // strecken.
        img.setDisplaySize(TILE_SIZE, TILE_SIZE);
        container.add(img);
      }
    }
    this.chunkContainers.set(`${chunk.cx},${chunk.cy}`, container);
  }
}
