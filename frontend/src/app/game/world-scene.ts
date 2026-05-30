// WorldScene — Phaser-Scene, die NUR rendert und Input → Intent übersetzt.
//
// Strikte Trennung zum Legacy-Monolithen:
//   • State kommt aus `bridge.state` (= GameStateService) per Signal-Read.
//   • Eingaben (Klick, Tasten, Touch) werden zu `bridge.sendIntent(...)`.
//   • KEIN `innerHTML`, KEIN `getElementById`, KEINE DOM-Manipulation.
//   • UI-Panels (Inventar, Hotbar, Skills, …) sind hier nicht zuständig —
//     siehe `legacy-stubs.ts` (F5-F15 wandert sie nach Angular).
//
// F4a-Scope: Tile-Layer rendert Chunks aus `state.chunks()`.
// F4b-Scope: Sprite-Pools für Player / NPCs / Strukturen / Ground-Items.
//            Fallback-Sprites (Phaser-Graphics Rect) wenn das echte Texture
//            nicht im Cache ist — strikte Asset-Vollständigkeit kommt erst
//            mit der UI-Migration (F5+).
// F4c kommt: Klick→Move, Tasten, Kamera-Follow.

import Phaser from 'phaser';

import { TILE, TILE_BY_ID, TILE_SIZE } from '../core/data/tiles';
import type { Chunk, Structure } from '../core/models/chunk.model';
import type { GroundItem } from '../core/models/item.model';
import type { NPC } from '../core/models/npc.model';
import type { OnlinePlayer } from '../core/models/player.model';
import type { GameBridgeService } from '../core/services/game-bridge.service';
import { SpritePool } from './sprite-pools';

/** Init-Daten, die `PhaserGameComponent` per `scene.start('WorldScene',{...})` durchreicht. */
export interface WorldSceneInitData {
  readonly bridge: GameBridgeService;
}

/** Render-Tiefen (Z-Order). */
const DEPTH = {
  TILES: 0,
  GROUND_ITEMS: 5,
  STRUCTURES: 10,
  NPCS: 20,
  PLAYERS: 30,
  ME: 40,
} as const;

/** Fallback-Farben pro Sprite-Familie wenn das Texture nicht geladen ist. */
const FALLBACK_COLORS = {
  npc: 0xff5599,
  player: 0x55aaff,
  structure: 0x886644,
  groundItem: 0xeeee44,
} as const;

export class WorldScene extends Phaser.Scene {
  /** Bridge wird in `init()` aus den Scene-Start-Daten gesetzt. */
  private bridge!: GameBridgeService;

  // ─── Tile-Layer ─────────────────────────────────────────────────────
  private readonly chunkContainers = new Map<string, Phaser.GameObjects.Container>();
  private lastChunksRef: readonly Chunk[] | null = null;
  private chunkSize = 32;

  // ─── Sprite-Pools (F4b) ────────────────────────────────────────────
  /** Spieler-Sprites (key = player_id as string). Eigener Spieler hat
   *  zusätzliches Depth + Tint. */
  private playerPool!: SpritePool<OnlinePlayer, Phaser.GameObjects.GameObject>;
  private lastPlayersRef: Readonly<Record<string, OnlinePlayer>> | null = null;

  /** NPC- und Creature-Sprites. */
  private npcPool!: SpritePool<NPC, Phaser.GameObjects.GameObject>;
  private lastNpcsRef: readonly NPC[] | null = null;

  /** Strukturen (Mauern, Truhen, Möbel, Dekos). */
  private structurePool!: SpritePool<Structure, Phaser.GameObjects.GameObject>;
  private lastStructuresRef: readonly Structure[] | null = null;

  /** Ground-Items (Loot der Welt). */
  private groundItemPool!: SpritePool<GroundItem, Phaser.GameObjects.GameObject>;
  private lastGroundItemsRef: readonly GroundItem[] | null = null;

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
    // Nur die Tile-Texturen für F4a. Sprites/Strukturen folgen in F4b —
    // bzw. nutzen Fallback-Rect, wenn das Texture nicht geladen ist (siehe
    // `getOrFallback*`-Helpers unten).
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
    const size = this.bridge.state.chunkSize();
    if (size > 0) this.chunkSize = size;

    this.playerPool = new SpritePool<OnlinePlayer, Phaser.GameObjects.GameObject>({
      keyOf: (p) => String(p.player_id),
      create: (p) => this.createPlayerSprite(p),
      update: (s, p) => this.updateMovableSprite(s, p.x, p.y),
    });
    this.npcPool = new SpritePool<NPC, Phaser.GameObjects.GameObject>({
      keyOf: (n) => n.id,
      create: (n) => this.createNpcSprite(n),
      update: (s, n) => this.updateMovableSprite(s, n.x, n.y),
    });
    this.structurePool = new SpritePool<Structure, Phaser.GameObjects.GameObject>({
      keyOf: (s) => s.id,
      create: (s) => this.createStructureSprite(s),
      update: (g, s) => this.updateMovableSprite(g, s.x, s.y),
    });
    this.groundItemPool = new SpritePool<GroundItem, Phaser.GameObjects.GameObject>({
      keyOf: (g) => g.id,
      create: (g) => this.createGroundItemSprite(g),
      update: (s, g) => this.updateMovableSprite(s, g.x, g.y),
    });
  }

  override update(_time: number, _delta: number): void {
    // Pro Frame: prüfen, ob die State-Listen sich identitätsmäßig geändert
    // haben (Signals liefern immutable Arrays). Identity-Check ist O(1) —
    // ein Deep-Diff würde dem 60-FPS-Budget schaden.
    const chunks = this.bridge.state.chunks();
    if (chunks !== this.lastChunksRef) {
      this.lastChunksRef = chunks;
      this.syncTileLayer(chunks);
    }
    const players = this.bridge.state.players();
    if (players !== this.lastPlayersRef) {
      this.lastPlayersRef = players;
      this.playerPool.sync(Object.values(players));
    }
    const npcs = this.bridge.state.npcsVisible();
    if (npcs !== this.lastNpcsRef) {
      this.lastNpcsRef = npcs;
      this.npcPool.sync(npcs);
    }
    const structures = this.bridge.state.structures();
    if (structures !== this.lastStructuresRef) {
      this.lastStructuresRef = structures;
      this.structurePool.sync(structures);
    }
    const groundItems = this.bridge.state.itemsGround();
    if (groundItems !== this.lastGroundItemsRef) {
      this.lastGroundItemsRef = groundItems;
      this.groundItemPool.sync(groundItems);
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
    for (const [key, container] of this.chunkContainers) {
      if (!seen.has(key)) {
        container.destroy();
        this.chunkContainers.delete(key);
      }
    }
  }

  private renderChunk(chunk: Chunk): void {
    const baseX = chunk.cx * this.chunkSize * TILE_SIZE;
    const baseY = chunk.cy * this.chunkSize * TILE_SIZE;
    const container = this.add.container(baseX, baseY);
    container.setDepth(DEPTH.TILES);

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
        img.setDisplaySize(TILE_SIZE, TILE_SIZE);
        container.add(img);
      }
    }
    this.chunkContainers.set(`${chunk.cx},${chunk.cy}`, container);
  }

  // ─── Sprite-Factories (F4b) ────────────────────────────────────────

  /**
   * Generischer Helper: gibt entweder ein `Image` (Texture vorhanden) oder
   * ein gefärbtes `Rectangle` (Fallback) zurück. Beide sind
   * `GameObjects.GameObject` — der gemeinsame Typ für die Pool.
   */
  private spriteOrFallback(
    textureKey: string,
    fallbackColor: number,
    sizePx: number,
  ): Phaser.GameObjects.GameObject {
    if (this.textures.exists(textureKey)) {
      const img = this.add.image(0, 0, textureKey);
      img.setDisplaySize(sizePx, sizePx);
      return img;
    }
    const rect = this.add.rectangle(0, 0, sizePx, sizePx, fallbackColor, 0.85);
    rect.setStrokeStyle(2, 0x000000, 0.6);
    return rect;
  }

  /** Position auf Sprite anwenden — funktioniert für Image, Sprite,
   *  Rectangle, Container (alle haben `x`/`y`-Setter über Transform). */
  private updateMovableSprite(
    obj: Phaser.GameObjects.GameObject,
    tileX: number,
    tileY: number,
  ): void {
    const withTransform = obj as Phaser.GameObjects.GameObject & { x: number; y: number };
    withTransform.x = tileX * TILE_SIZE + TILE_SIZE / 2;
    withTransform.y = tileY * TILE_SIZE + TILE_SIZE / 2;
  }

  private createPlayerSprite(p: OnlinePlayer): Phaser.GameObjects.GameObject {
    // Legacy nutzt walking-anim aus PRESET_WALK_CFG mit 4 Richtungen × 2 Frames.
    // F4b: Standbild aus Preset-Texture (falls geladen), sonst blauer Rect-
    // Fallback. Walk-Anim kommt mit F4c (Input + Bewegungs-Tracking) oder
    // einer F4c-Subphase.
    const tex = p.preset ? `player_${p.preset}_idle` : 'player_default';
    const obj = this.spriteOrFallback(tex, FALLBACK_COLORS.player, TILE_SIZE);
    const isMe = this.bridge.state.player()?.player_id === p.player_id;
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = isMe
      ? DEPTH.ME
      : DEPTH.PLAYERS;
    return obj;
  }

  private createNpcSprite(n: NPC): Phaser.GameObjects.GameObject {
    // Texture-Key folgt Legacy-Konvention: `npc_<kind>` für humans,
    // `monster_<kind>` für creatures, `animal_<kind>` für Nutztiere.
    // Wir versuchen `npc_<kind>` zuerst; Fallback ist ein roter Rect.
    const tex = n.sprite_variant ?? `npc_${n.kind}`;
    const obj = this.spriteOrFallback(tex, FALLBACK_COLORS.npc, TILE_SIZE);
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = DEPTH.NPCS;
    return obj;
  }

  private createStructureSprite(s: Structure): Phaser.GameObjects.GameObject {
    // Strukturen-Texture-Key folgt Legacy: `struct_<type>`. Bei Wänden mit
    // Material-Variant würde Legacy `wall_<material>_<bitmask>` nutzen — das
    // ist F4-out-of-scope (Wall-Auto-Tiling kommt in F-final oder als
    // separate Render-Subphase).
    const tex = `struct_${s.type}`;
    const obj = this.spriteOrFallback(tex, FALLBACK_COLORS.structure, TILE_SIZE);
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = DEPTH.STRUCTURES;
    return obj;
  }

  private createGroundItemSprite(g: GroundItem): Phaser.GameObjects.GameObject {
    // Item-Texture-Key folgt Legacy: `item_<kind>`. Legacy nutzt eine
    // Item-Path-Map (ITEM[kind].sprite, plus Pro-Asset-Pools). F4b verzichtet
    // darauf und fällt auf den Fallback zurück — die Pro-Asset-Pipeline
    // wandert mit dem Inventar-Panel (F7) komplett ins UI.
    const tex = `item_${g.kind}`;
    const obj = this.spriteOrFallback(tex, FALLBACK_COLORS.groundItem, TILE_SIZE * 0.5);
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = DEPTH.GROUND_ITEMS;
    return obj;
  }
}
