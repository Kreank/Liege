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
// F4c-Scope: Input → Intent (Klick = Move, SHIFT = Sprint, B = Build-Toggle).
//            Kamera-Follow auf den eigenen Spieler. Keine Pfadfindung im
//            Frontend — die `move`-Message ist schon das Pathfind-Intent
//            (Backend führt den Pfad).
//
// render-fix (2026-05-31):
//   1. Walk-Cycle aktiviert: `add.sprite` + `sprite.anims.play(...)` fuer
//      Kinds mit registrierter Walk-Animation. Movement-Tracker pro Pool
//      entscheidet `walk_<dir>` vs `idle`. NPC_FLIP_LR_KINDS-Workaround
//      fuer Kinds mit invertiert geliefertem West/Ost.
//   2. Wall-Auto-Tiling: type=='wall'|'fence' triggert Bitmask-Lookup gegen
//      4 Nachbarn -> Variant-Sprite-Key. Bei jedem Sync wird die Variante
//      neu berechnet, damit Add/Remove benachbarter Tiles korrekt anpassen.

import Phaser from 'phaser';
import type { Subscription } from 'rxjs';

import {
  ANIMATED_NPC_KINDS,
  CREATURE_KINDS,
  NPC_FLIP_LR_KINDS,
} from '../core/data/npc-sprites';
import {
  USABLE_STRUCTURE_TYPES,
  isHarvestableStructureType,
} from '../core/data/structures';
import { TILE, TILE_BY_ID, TILE_SIZE } from '../core/data/tiles';
import type { Chunk, Structure } from '../core/models/chunk.model';
import type { GroundItem } from '../core/models/item.model';
import type { NPC } from '../core/models/npc.model';
import type { OnlinePlayer } from '../core/models/player.model';
import type { ServerMessage } from '../core/models/ws-message.model';
import type { GameBridgeService } from '../core/services/game-bridge.service';
import type { AssetLoaderService } from './asset-loader.service';
import {
  WALK_DIRECTIONS,
  type WalkDirection,
} from './asset-loader.service';
import type { EffectAnimationsService } from './effect-animations.service';
import type { WalkAnimationsService } from './walk-animations.service';
import { COMBAT_FX } from './combat-fx';
import { DisasterOverlay } from './disaster-overlay';
import { setupInput } from './input';
import { SpritePool } from './sprite-pools';
import { VISUAL_EFFECTS } from './visual-effects';
import {
  buildStructureLookup,
  familyOf,
  wallMaskFor,
  wallSpriteKeyFor,
  type WallFamily,
} from './wall-tiler';

/** Init-Daten, die `PhaserGameComponent` per `scene.start('WorldScene',{...})` durchreicht. */
export interface WorldSceneInitData {
  readonly bridge: GameBridgeService;
  readonly assetLoader: AssetLoaderService;
  readonly walkAnimations: WalkAnimationsService;
  readonly effectAnimations: EffectAnimationsService;
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

/** Animation-Set fuer eine bekannte ANIMATED_NPC_KIND-Liste (O(1) Lookup). */
const ANIMATED_NPC_SET: ReadonlySet<string> = new Set(ANIMATED_NPC_KINDS);

/**
 * Movement-Tracker pro Sprite-Key. Speichert die zuletzt gesehene Tile-Position
 * plus den Frame-Stand zum Zeitpunkt der letzten Bewegung — wenn der Sprite N
 * Frames lang nicht mehr bewegt wurde, schalten wir auf Idle.
 */
interface MoveTrack {
  x: number;
  y: number;
  /** Zuletzt gespielte Direction (fuer Idle-Fallback). */
  dir: WalkDirection;
  /** `scene.game.loop.frame`-Wert beim letzten Move. */
  lastMoveFrame: number;
}

/** Idle-Schwelle in Frames (~10 Frames = 167 ms bei 60 FPS). */
const IDLE_AFTER_FRAMES = 10;

export class WorldScene extends Phaser.Scene {
  /** Bridge wird in `init()` aus den Scene-Start-Daten gesetzt. */
  private bridge!: GameBridgeService;
  /** Sprite-Registry (NPC-Walk-Frames, Player-Presets, statische Sprites). */
  private assetLoader!: AssetLoaderService;
  /** Phaser-Animation-Definitions (Walk/Idle). */
  private walkAnimations!: WalkAnimationsService;
  /** Phaser-Animation-Definitions (Spell-FX, Disaster-Layer) — G4. */
  private effectAnimations!: EffectAnimationsService;
  /** Disaster-Overlay (Tint, Particle-Emitter, Lightning-Bolts) — G4. */
  private disasterOverlay: DisasterOverlay | null = null;

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

  // ─── Movement-Tracker fuer Walk-Animations (render-fix 2026-05-31) ──
  /** Pro NPC-Key: letzte Position + Direction + Frame-Stamp. */
  private readonly npcTracks = new Map<string | number, MoveTrack>();
  /** Pro Player-Key: letzte Position + Direction + Frame-Stamp. */
  private readonly playerTracks = new Map<string | number, MoveTrack>();
  /** Strukturen-Lookup (x,y) -> Structure, fuer Wall-Auto-Tiling. Wird jeden
   *  Sync neu gebaut — das ist O(N), unkritisch bei <500 sichtbaren Strukturen. */
  private structureLookup: (x: number, y: number) => Structure | null = () => null;

  // ─── Kamera-Follow + Local Sprint-State (F4c) ────────────────────────
  /** Letzte Spieler-Tile-Position für Move-Intent-Deduplication. */
  private lastSentMoveTile: { x: number; y: number } | null = null;
  /** Lokaler Sprint-Zustand — wir senden nur on/off-Edges an den Server. */
  private sprintSent = false;
  /** Subscription auf den WS-Message-Stream (für transiente FX). */
  private fxSub: Subscription | null = null;
  /** Build-Mode lebt seit F-extras-3 als Signal in der `GameBridgeService`,
   *  damit die Angular-`BuildBarComponent` reagieren kann. Wir lesen pro
   *  Click den aktuellen Wert von dort. */

  constructor() {
    super({ key: 'WorldScene' });
  }

  // Phaser-Scene-Lifecycle-Hooks sind in den Typings nicht als Methoden
  // deklariert (Phaser fügt sie zur Laufzeit auf der Subclass-Instanz auf),
  // daher kein `override`-Keyword möglich.
  init(data: WorldSceneInitData): void {
    this.bridge = data.bridge;
    this.assetLoader = data.assetLoader;
    this.walkAnimations = data.walkAnimations;
    this.effectAnimations = data.effectAnimations;
  }

  preload(): void {
    // Tile-Texturen (F4a).
    for (const def of Object.values(TILE)) {
      this.load.image(def.sprite, `/assets/tiles/${this.tileFilename(def.sprite)}`);
    }
    // Statische Sprites (Monster/Struct/Item/Effect) + Walk-Cycle-Frames.
    // F-render-foundation (2026-05-30): zentralisiert über AssetLoaderService.
    this.assetLoader.preloadAll(this.load);
    // 404er soll die Scene NICHT crashen — Fallback-Rect rendert dann.
    this.load.on('loaderror', (file: Phaser.Loader.File) => {
      console.warn('[WorldScene] asset 404 — falling back to magenta rect:', file.key, file.url);
    });
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
      update: (s, p) => this.updatePlayerSprite(s, p),
      onRemove: (_, k) => this.playerTracks.delete(k),
    });
    this.npcPool = new SpritePool<NPC, Phaser.GameObjects.GameObject>({
      keyOf: (n) => n.id,
      create: (n) => this.createNpcSprite(n),
      update: (s, n) => this.updateNpcSprite(s, n),
      onRemove: (_, k) => this.npcTracks.delete(k),
    });
    this.structurePool = new SpritePool<Structure, Phaser.GameObjects.GameObject>({
      keyOf: (s) => s.id,
      create: (s) => this.createStructureSprite(s),
      update: (g, s) => this.updateStructureSprite(g, s),
    });
    this.groundItemPool = new SpritePool<GroundItem, Phaser.GameObjects.GameObject>({
      keyOf: (g) => g.id,
      create: (g) => this.createGroundItemSprite(g),
      update: (s, g) => this.updateMovableSprite(s, g.x, g.y),
    });

    // ─── Input → Intents ──────────────────────────────────────────────
    setupInput(this, {
      onTileClick: (pos) => this.handleTileClick(pos.x, pos.y),
      onSprintChange: (on) => this.handleSprintChange(on),
      onToggleBuildMode: () => {
        this.bridge.toggleBuildMode();
      },
    });

    // ─── Walk-Animations registrieren ─────────────────────────────────
    // Nach `preload()` sind alle Frame-Texturen im Cache — jetzt definieren
    // wir pro Kind × Richtung eine Phaser-Animation.
    this.walkAnimations.createAnimations(this);
    // G4: Spell-FX + Disaster-Layer-Anims registrieren.
    this.effectAnimations.createAnimations(this);
    // G4: Disaster-Overlay initialisieren (Tint/Particle/Bolt).
    this.disasterOverlay = new DisasterOverlay(this, this.effectAnimations);

    // ─── Kamera-Setup ─────────────────────────────────────────────────
    // Welt-Bounds erst sobald `init` durch ist und Spawn bekannt; vorerst
    // keine Bounds (Phaser-Default = unbegrenzt). Die Follow-Logik im
    // `update()` setzt die Kamera auf die Spieler-Position.
    this.cameras.main.setRoundPixels(true);

    // ─── FX-Wiring: WS → Damage-Numbers, Sparks, Death, visual_effect ──
    this.fxSub = this.bridge.messages$.subscribe((msg) => this.handleFxMessage(msg));

    // Scene-Shutdown räumt Subscription auf (Phaser-Hook).
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.fxSub?.unsubscribe();
      this.fxSub = null;
    });
    this.events.once(Phaser.Scenes.Events.DESTROY, () => {
      this.fxSub?.unsubscribe();
      this.fxSub = null;
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
      // Lookup-Map fuer Wall-Auto-Tiling neu bauen, BEVOR der Pool synct,
      // damit `updateStructureSprite` einen aktuellen Nachbar-Snapshot sieht.
      this.structureLookup = buildStructureLookup(structures);
      this.structurePool.sync(structures);
    }
    const groundItems = this.bridge.state.itemsGround();
    if (groundItems !== this.lastGroundItemsRef) {
      this.lastGroundItemsRef = groundItems;
      this.groundItemPool.sync(groundItems);
    }

    // ─── Idle-Detection: Sprites die seit IDLE_AFTER_FRAMES nicht mehr
    // bewegt wurden, auf Idle-Anim schalten. NPC/Player getrennt, damit der
    // Map-Iter ohne Type-Cast funktioniert.
    const frameNow = this.game.loop.frame;
    for (const [key, track] of this.npcTracks) {
      if (frameNow - track.lastMoveFrame < IDLE_AFTER_FRAMES) continue;
      const sprite = this.npcPool.get(key);
      if (!sprite) continue;
      this.playIdleIfPossible(sprite, this.npcKindFor(key));
    }
    for (const [key, track] of this.playerTracks) {
      if (frameNow - track.lastMoveFrame < IDLE_AFTER_FRAMES) continue;
      const sprite = this.playerPool.get(key);
      if (!sprite) continue;
      this.playIdleIfPossible(sprite, this.playerPresetFor(key));
    }

    // ─── Kamera-Follow auf den eigenen Spieler ─────────────────────────
    // Wir lesen die kanonische Position aus `state.player()` (nicht den
    // Pool-Sprite), damit Kamera auch dann folgt, wenn das Sprite (noch)
    // nicht im Pool ist (Edge-Case: kurz vor erstem `players`-Update).
    const me = this.bridge.state.player();
    if (me) {
      const px = me.x * TILE_SIZE + TILE_SIZE / 2;
      const py = me.y * TILE_SIZE + TILE_SIZE / 2;
      this.cameras.main.centerOn(px, py);
    }
  }

  // ─── Input-Handler (F4c) ──────────────────────────────────────────────

  /**
   * Klick auf Tile → entscheide kontextuell:
   *   1. NPC am Ziel? → talk_to_npc (friendly) bzw. attack_npc (hostile).
   *   2. Ground-Item am Ziel? → pick_item.
   *   3. Struktur am Ziel? → use_structure (Tür, Chest, Bed, Stairs …).
   *   4. Sonst: move-Intent zum Ziel.
   *
   * Backend macht die eigentliche Pfadfindung / Validierung. Das Frontend
   * sendet nur das Intent — die Antwort kommt als `player_moved`/„closed".
   *
   * F4c-Limit: Wir prüfen nur Ziel-Tile-Kollisionen, kein Hover-Highlight.
   * Build-Mode-Place-Click (mit Rotation) kommt mit der Build-Bar-Migration
   * (F5+: `build-bar` in legacy-stubs.ts).
   */
  private handleTileClick(tileX: number, tileY: number): void {
    // ─── Build-Mode-Pfad ─────────────────────────────────────────────────
    // Klick auf leeres Tile → `place_structure`. Klick auf belegtes Tile
    // fällt durch in die Default-Logik (so kann man auch im Build-Mode
    // bestehende Strukturen abreißen/benutzen).
    if (this.bridge.buildMode()) {
      const structures = this.bridge.state.structures();
      const blocked = structures.some((s) => s.x === tileX && s.y === tileY);
      if (!blocked) {
        const structType = this.bridge.selectedStructure();
        if (!structType) {
          // Kein Strukturtyp gewählt — Toast in den Chat-Stream.
          this.bridge.state.appendChat({
            kind: 'system',
            text: 'Bau-Modus: Keine Struktur ausgewählt.',
          });
          return;
        }
        this.bridge.sendPlaceStructure({
          x: tileX,
          y: tileY,
          structure_type: structType,
          material: this.bridge.selectedMaterial(),
          rotation: this.bridge.placeRotation(),
        });
        return;
      }
      // Tile blockiert → fällt durch zur Default-Logik unten.
    }

    // 1) NPC? Hostile → attack, friendly → talk.
    const npcs = this.bridge.state.npcsVisible();
    const npcHere = npcs.find((n) => n.x === tileX && n.y === tileY);
    if (npcHere) {
      if (this.isHostileNpc(npcHere)) {
        this.bridge.sendAttackNpc(npcHere.id);
      } else {
        this.bridge.sendTalkToNpc(npcHere.id);
      }
      return;
    }

    // 2) Ground-Item?
    const groundItems = this.bridge.state.itemsGround();
    const itemHere = groundItems.find((g) => g.x === tileX && g.y === tileY);
    if (itemHere) {
      this.bridge.sendPickItem(itemHere.id);
      return;
    }

    // 3) Struktur? Harvest-bar (Tree/Stone/Ore/Wall/Door/Crop) → attack,
    //    sonst use (Bett/Brunnen/Schild/Truhe/…).
    const structures = this.bridge.state.structures();
    const structHere = structures.find((s) => s.x === tileX && s.y === tileY);
    if (structHere) {
      if (this.shouldAttackStructure(structHere.type)) {
        this.bridge.sendAttackStructure(tileX, tileY);
      } else {
        this.bridge.sendUseStructure(tileX, tileY);
      }
      return;
    }

    // 4) Move-Intent. Dedup: gleicher Ziel-Tile innerhalb derselben
    // Click-Sequenz → nicht erneut senden (Spam-Schutz, Legacy-Verhalten).
    if (
      this.lastSentMoveTile &&
      this.lastSentMoveTile.x === tileX &&
      this.lastSentMoveTile.y === tileY
    ) {
      return;
    }
    this.lastSentMoveTile = { x: tileX, y: tileY };
    this.bridge.sendMove(tileX, tileY);
  }

  /**
   * Hostile-Check für NPCs. Wir bevorzugen das `hostile`-Flag aus dem
   * Backend-Snapshot; wenn das Feld fehlt (Legacy-NPCs ohne explizites Flag),
   * fallen wir auf das CREATURE_KINDS-Set zurück. Friendly-Default für alles
   * andere — der Server lehnt `attack_npc` auf Friendlies ab, aber unser
   * UX-Default ist Dialog.
   */
  private isHostileNpc(n: { readonly kind: string; readonly hostile?: boolean }): boolean {
    if (n.hostile === true) return true;
    if (n.hostile === false) return false;
    return CREATURE_KINDS.has(n.kind);
  }

  /**
   * Harvest vs Use. Use-Strukturen (USABLE_STRUCTURE_TYPES) gewinnen — Truhen,
   * Betten, Brunnen, Quest-Boards. Alles andere mit Harvest-Präfix
   * (`tree_*`, `wall*`, `door_*`, `*_plant`, …) → attack.
   */
  private shouldAttackStructure(type: string): boolean {
    if (USABLE_STRUCTURE_TYPES.has(type)) return false;
    if (type.startsWith('sign_')) return false; // Schild → use_structure (read).
    return isHarvestableStructureType(type);
  }

  private handleSprintChange(on: boolean): void {
    if (on === this.sprintSent) return;
    this.sprintSent = on;
    this.bridge.sendSprint(on);
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
   * Generischer Helper fuer STATISCHE Sprites: gibt entweder ein `Image`
   * (Texture vorhanden) oder ein gefärbtes `Rectangle` (Fallback) zurück.
   * Beide sind `GameObjects.GameObject` — der gemeinsame Typ für die Pool.
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

  /**
   * Animated-Sprite-Factory: erzeugt einen Phaser-Sprite (statt Image) und
   * spielt sofort die Idle-Animation, falls registriert. Fallt auf
   * spriteOrFallback zurueck wenn weder Texture noch Anim existiert.
   * `animKindKey` ist der Walk-Cycle-Kind-Key (z. B. `wanderer`).
   */
  private animatedSpriteOrFallback(
    textureKey: string,
    animKindKey: string,
    fallbackColor: number,
    sizePx: number,
  ): Phaser.GameObjects.GameObject {
    if (this.textures.exists(textureKey)) {
      const sprite = this.add.sprite(0, 0, textureKey);
      sprite.setDisplaySize(sizePx, sizePx);
      const idleKey = this.walkAnimations.idleAnimKey(animKindKey);
      if (this.anims.exists(idleKey)) {
        sprite.anims.play(idleKey, true);
      }
      return sprite;
    }
    return this.spriteOrFallback(textureKey, fallbackColor, sizePx);
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
    // F-render-foundation: Player nutzt Walk-Cycle-Frame `idle_1` des Presets
    // als Standbild. Wenn der `preset` null/leer ist, resolved der
    // AssetLoader auf `wanderer_cloak` (Default).
    const preset = this.assetLoader.resolvePlayerPreset(p.preset);
    const tex = `player_${preset}_idle`;
    const obj = this.animatedSpriteOrFallback(tex, preset, FALLBACK_COLORS.player, TILE_SIZE);
    const isMe = this.bridge.state.player()?.player_id === p.player_id;
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = isMe
      ? DEPTH.ME
      : DEPTH.PLAYERS;
    return obj;
  }

  private updatePlayerSprite(obj: Phaser.GameObjects.GameObject, p: OnlinePlayer): void {
    this.updateMovableSprite(obj, p.x, p.y);
    const preset = this.assetLoader.resolvePlayerPreset(p.preset);
    this.handleWalkAnim(obj, this.playerTracks, String(p.player_id), preset, p.x, p.y);
  }

  private createNpcSprite(n: NPC): Phaser.GameObjects.GameObject {
    // F-render-foundation: AssetLoader hat für jedes ANIMATED_NPC_KINDS-Kind
    // ein Idle-Frame als `npc_<kind>`-Texture geladen. Wir prüfen erst
    // sprite_variant (z. B. bandit_axe), dann den Standard-Key.
    const variantTex = n.sprite_variant ? `npc_${n.sprite_variant}` : null;
    const baseTex = this.assetLoader.textureKeyFor(n.kind) ?? `npc_${n.kind}`;
    const tex = variantTex && this.textures.exists(variantTex) ? variantTex : baseTex;
    // Animated path: bevorzuge die Variant (bandit_axe) wenn sie eine
    // registrierte Walk-Anim hat — sonst der Basis-Kind (bandit). So
    // bekommen Equip-Varianten ihren eigenen Walk-Cycle statt der Generic.
    const animKind = this.npcAnimKind(n);
    const obj = animKind
      ? this.animatedSpriteOrFallback(tex, animKind, FALLBACK_COLORS.npc, TILE_SIZE)
      : this.spriteOrFallback(tex, FALLBACK_COLORS.npc, TILE_SIZE);
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = DEPTH.NPCS;
    return obj;
  }

  private updateNpcSprite(obj: Phaser.GameObjects.GameObject, n: NPC): void {
    this.updateMovableSprite(obj, n.x, n.y);
    const animKind = this.npcAnimKind(n);
    if (animKind) {
      this.handleWalkAnim(obj, this.npcTracks, n.id, animKind, n.x, n.y);
    }
  }

  /** Resolve Walk-Anim-Kind: bevorzuge `sprite_variant` falls registriert. */
  private npcAnimKind(n: NPC): string | null {
    if (n.sprite_variant && ANIMATED_NPC_SET.has(n.sprite_variant)) {
      return n.sprite_variant;
    }
    if (ANIMATED_NPC_SET.has(n.kind)) {
      return n.kind;
    }
    return null;
  }

  private createStructureSprite(s: Structure): Phaser.GameObjects.GameObject {
    const key = this.structureSpriteKeyFor(s);
    const tex = this.assetLoader.textureKeyFor(key) ?? `struct_${key}`;
    const obj = this.spriteOrFallback(tex, FALLBACK_COLORS.structure, TILE_SIZE);
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = DEPTH.STRUCTURES;
    return obj;
  }

  /**
   * Strukturen werden bei jedem Sync neu aktualisiert. Fuer Wall/Fence
   * berechnen wir die Bitmask gegen die aktuellen Nachbarn und tauschen
   * ggf. die Texture — dadurch passen sich Wand-Segmente korrekt an, wenn
   * der User in derselben Linie ein weiteres Tile platziert.
   */
  private updateStructureSprite(obj: Phaser.GameObjects.GameObject, s: Structure): void {
    this.updateMovableSprite(obj, s.x, s.y);
    const family = familyOf(s.type, s.material ?? null);
    if (!family) return; // nur Wall/Fence brauchen Re-Tiling
    const key = this.structureSpriteKeyFor(s);
    const tex = this.assetLoader.textureKeyFor(key) ?? `struct_${key}`;
    // Nur echte Image-Sprites haben `setTexture`. Rectangle-Fallbacks
    // ignorieren wir — das Magenta-Rect bleibt bis das Asset da ist.
    const maybeImage = obj as Phaser.GameObjects.GameObject & {
      setTexture?: (key: string) => void;
      texture?: Phaser.Textures.Texture;
    };
    if (typeof maybeImage.setTexture === 'function' && this.textures.exists(tex)) {
      if (maybeImage.texture?.key !== tex) {
        maybeImage.setTexture(tex);
      }
    }
  }

  /**
   * Ermittelt den STRUCTURE_SPRITES-Schluessel fuer eine Strukur. Fuer
   * Wall/Fence wird die 4-Nachbarn-Bitmask berechnet und ueber
   * WALL_MASK_TO_VARIANT auf eine Variante gemappt (z. B.
   * `wall_stone_corner_ne`). Fuer alle anderen Typen: einfach `s.type`.
   */
  private structureSpriteKeyFor(s: Structure): string {
    const family: WallFamily | null = familyOf(s.type, s.material ?? null);
    if (!family) return s.type;
    const mask = wallMaskFor(s.x, s.y, this.structureLookup, family);
    return wallSpriteKeyFor(family, mask);
  }

  private createGroundItemSprite(g: GroundItem): Phaser.GameObjects.GameObject {
    // F-render-foundation: AssetLoader kennt den Item-Key aus ITEM_SPRITES
    // (Subagent B). Pro-Asset-Pipeline (Quality/Cosmetic-Skin) kommt mit
    // dem Inventar-Panel (F7).
    const tex = this.assetLoader.textureKeyFor(g.kind) ?? `item_${g.kind}`;
    const obj = this.spriteOrFallback(tex, FALLBACK_COLORS.groundItem, TILE_SIZE * 0.5);
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = DEPTH.GROUND_ITEMS;
    return obj;
  }

  // ─── Walk-Cycle-Handling (render-fix 2026-05-31) ────────────────────

  /**
   * Vergleicht aktuelle Position mit Tracker, berechnet Direction, spielt
   * die passende Walk-Animation. Beachtet NPC_FLIP_LR_KINDS — Kinds in der
   * Liste sind west/ost-vertauscht ausgeliefert, daher spielen wir
   * `walk_right` mit `setFlipX(true)` statt `walk_left` (sieht sonst
   * verkehrt aus, Audit Welle 29e).
   */
  private handleWalkAnim(
    obj: Phaser.GameObjects.GameObject,
    tracks: Map<string | number, MoveTrack>,
    key: string | number,
    kind: string,
    x: number,
    y: number,
  ): void {
    const prev = tracks.get(key);
    if (!prev) {
      tracks.set(key, { x, y, dir: 'down', lastMoveFrame: this.game.loop.frame });
      return;
    }
    const dx = x - prev.x;
    const dy = y - prev.y;
    if (dx === 0 && dy === 0) return; // keine Bewegung → Idle-Detection laeuft separat
    const dir = directionFor(dx, dy, prev.dir);
    prev.x = x;
    prev.y = y;
    prev.dir = dir;
    prev.lastMoveFrame = this.game.loop.frame;
    this.playWalkAnim(obj, kind, dir);
  }

  /** Spielt `<kind>_walk_<dir>`, ggf. mit Flip fuer NPC_FLIP_LR_KINDS. */
  private playWalkAnim(
    obj: Phaser.GameObjects.GameObject,
    kind: string,
    dir: WalkDirection,
  ): void {
    const sprite = obj as Phaser.GameObjects.GameObject & {
      anims?: Phaser.Animations.AnimationState;
      setFlipX?: (flip: boolean) => void;
    };
    if (!sprite.anims) return; // Image/Rectangle → keine Anim

    let effectiveDir = dir;
    let flipX = false;
    if (NPC_FLIP_LR_KINDS.has(kind)) {
      // West/Ost sind invertiert geliefert: 'left' -> spiele 'right' + Flip,
      // 'right' -> spiele 'left' + Flip. North/South unbeeinflusst.
      if (dir === 'left') { effectiveDir = 'right'; flipX = true; }
      else if (dir === 'right') { effectiveDir = 'left'; flipX = true; }
    }
    sprite.setFlipX?.(flipX);

    const animKey = this.walkAnimations.walkAnimKey(kind, effectiveDir);
    if (this.anims.exists(animKey)) {
      sprite.anims.play(animKey, true);
    }
  }

  /** Spielt die Idle-Animation falls vorhanden. No-op fuer Rects/Images. */
  private playIdleIfPossible(obj: Phaser.GameObjects.GameObject, kind: string | null): void {
    if (!kind) return;
    const sprite = obj as Phaser.GameObjects.GameObject & {
      anims?: Phaser.Animations.AnimationState;
    };
    if (!sprite.anims) return;
    const idleKey = this.walkAnimations.idleAnimKey(kind);
    if (!this.anims.exists(idleKey)) return;
    // `play(key, true)` = ignoreIfPlaying → kein Restart, wenn Idle schon laeuft.
    sprite.anims.play(idleKey, true);
  }

  /** Liefert den Walk-Anim-Kind eines NPC (Variant bevorzugt) aus dem
   *  aktuellen npcsVisible()-Snapshot. Nötig für die Idle-Detection. */
  private npcKindFor(id: string | number): string | null {
    const npcs = this.bridge.state.npcsVisible();
    const idNum = typeof id === 'string' ? Number(id) : id;
    const npc = npcs.find((n) => n.id === idNum);
    if (!npc) return null;
    return this.npcAnimKind(npc);
  }

  /** Liefert das Player-Preset aus dem aktuellen players()-Snapshot. */
  private playerPresetFor(key: string | number): string | null {
    const players = this.bridge.state.players();
    const p = players[String(key)];
    if (!p) return null;
    return this.assetLoader.resolvePlayerPreset(p.preset);
  }

  // ─── FX-Handler (WS-Stream → Phaser-Animations) ─────────────────────

  /**
   * Dispatch transienter Server-Events auf die FX-Layer. State-Updates
   * (HP, Position) macht der `GameStateService` parallel — wir lesen hier
   * nur die Delta-Felder (dmg, amount), die nach dem Frame verloren wären.
   */
  private handleFxMessage(msg: ServerMessage): void {
    switch (msg.type) {
      case 'npc_damaged':
        this.fxNpcDamaged(msg);
        return;
      case 'npc_died':
        this.fxNpcDied(msg);
        return;
      case 'player_damaged':
        this.fxPlayerDamaged(msg);
        return;
      case 'player_healed':
        this.fxPlayerHealed(msg);
        return;
      case 'structure_damaged':
        this.fxStructureDamaged(msg);
        return;
      case 'structure_removed':
        this.fxStructureRemoved(msg);
        return;
      case 'visual_effect':
        this.fxVisualEffect(msg);
        return;
      case 'disaster_started':
        this.fxDisasterStarted(msg);
        return;
      case 'disaster_ended':
        this.fxDisasterEnded(msg);
        return;
      case 'earthquake_shake':
        this.fxEarthquake(msg);
        return;
      case 'lightning_strike':
        this.fxLightningStrike(msg);
        return;
      default:
        return;
    }
  }

  private fxDisasterStarted(msg: ServerMessage): void {
    const kind = msg['kind'] as string | undefined;
    if (!kind || !this.disasterOverlay) return;
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    this.disasterOverlay.startDisaster(kind, { x: x ?? null, y: y ?? null });
  }

  private fxDisasterEnded(msg: ServerMessage): void {
    const kind = msg['kind'] as string | undefined;
    if (!kind || !this.disasterOverlay) return;
    this.disasterOverlay.endDisaster(kind);
  }

  private fxEarthquake(msg: ServerMessage): void {
    const intensity = (msg['intensity'] as number | undefined) ?? 0.01;
    const durationMs = (msg['duration_ms'] as number | undefined) ?? 600;
    this.cameras.main.shake(durationMs, Math.min(0.05, intensity));
  }

  private fxLightningStrike(msg: ServerMessage): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (x == null || y == null || !this.disasterOverlay) return;
    this.disasterOverlay.spawnLightningBolt(x, y);
  }

  private fxNpcDamaged(msg: ServerMessage): void {
    const npcId = msg['npc_id'] as number | undefined;
    const dmg = msg['dmg'] as number | undefined;
    if (npcId == null) return;
    // Position aus dem aktuellen NPC-Snapshot — der Sprite kann im Pool
    // schon weiter gewandert sein als der zuletzt vom State gerenderte
    // Wert. Wir nehmen den State, das passt zum Sprite-Tween.
    const npc = this.bridge.state.npcsVisible().find((n) => n.id === npcId);
    if (!npc) return;
    const center = COMBAT_FX.tileCenter(npc.x, npc.y);
    COMBAT_FX.spawnHitSpark(this, center.x, center.y);
    if (dmg != null && dmg > 0) {
      COMBAT_FX.spawnFloatingNumber(this, {
        x: center.x,
        y: center.y,
        text: `-${dmg}`,
        kind: 'phys',
      });
    }
  }

  private fxNpcDied(msg: ServerMessage): void {
    const npcId = msg['npc_id'] as number | undefined;
    if (npcId == null) return;
    // Sprite aus dem Pool detachen, damit der nächste sync() es nicht
    // zusätzlich destroyed (State entfernt den NPC ebenfalls in diesem Tick).
    const sprite = this.npcPool.detach(npcId);
    if (!sprite) return;
    // Aktuelle Sprite-Position aus dem Transform lesen — robuster als
    // erneuter State-Lookup nach dem State-Update.
    const withXY = sprite as Phaser.GameObjects.GameObject & { x: number; y: number };
    COMBAT_FX.spawnDeathFade(this, sprite, {
      x: withXY.x,
      y: withXY.y,
      onDone: () => {
        sprite.destroy();
        this.npcTracks.delete(npcId);
      },
    });
  }

  private fxPlayerDamaged(msg: ServerMessage): void {
    const dmg = msg['dmg'] as number | undefined;
    const me = this.bridge.state.player();
    if (!me) return;
    const center = COMBAT_FX.tileCenter(me.x, me.y);
    if (dmg != null && dmg > 0) {
      COMBAT_FX.spawnFloatingNumber(this, {
        x: center.x,
        y: center.y,
        text: `-${dmg}`,
        kind: 'phys',
      });
      COMBAT_FX.spawnHitSpark(this, center.x, center.y);
      COMBAT_FX.screenShake(this, dmg);
    }
  }

  private fxPlayerHealed(msg: ServerMessage): void {
    const amount = msg['amount'] as number | undefined;
    const me = this.bridge.state.player();
    if (!me) return;
    const center = COMBAT_FX.tileCenter(me.x, me.y);
    if (amount != null && amount > 0) {
      COMBAT_FX.spawnFloatingNumber(this, {
        x: center.x,
        y: center.y,
        text: `+${amount}`,
        kind: 'heal',
      });
    }
  }

  private fxStructureDamaged(msg: ServerMessage): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (x == null || y == null) return;
    const center = COMBAT_FX.tileCenter(x, y);
    COMBAT_FX.spawnHitSpark(this, center.x, center.y);
  }

  private fxStructureRemoved(msg: ServerMessage): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (x == null || y == null) return;
    // Kleiner Particle-Burst beim Wegnehmen — Sprite selbst wird vom
    // structurePool.sync() im nächsten Tick destroyed.
    const center = COMBAT_FX.tileCenter(x, y);
    for (let i = 0; i < 5; i++) {
      const ang = (i / 5) * Math.PI * 2;
      const dot = this.add.circle(center.x, center.y, 3, 0xddccaa, 0.9);
      dot.setDepth(60);
      this.tweens.add({
        targets: dot,
        x: center.x + Math.cos(ang) * 20,
        y: center.y + Math.sin(ang) * 20,
        alpha: 0,
        duration: 400,
        ease: 'Cubic.easeOut',
        onComplete: () => dot.destroy(),
      });
    }
  }

  private fxVisualEffect(msg: ServerMessage): void {
    const kind = msg['kind'] as string | undefined;
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (!kind || x == null || y == null) return;
    VISUAL_EFFECTS.spawn(this, { kind, x, y });
  }
}

/**
 * Mapped (dx, dy) auf 4-Wege-Direction. Bei diagonalem Move dominiert die
 * groessere Komponente; bei Gleichstand bleibt die vorherige Direction.
 */
function directionFor(dx: number, dy: number, prev: WalkDirection): WalkDirection {
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  if (ax === 0 && ay === 0) return prev;
  if (ax > ay) return dx > 0 ? 'right' : 'left';
  if (ay > ax) return dy > 0 ? 'down' : 'up';
  // Gleichstand (diagonale Schritte): vertikal vorziehen wenn moeglich.
  return dy > 0 ? 'down' : 'up';
}

// Silence "unused import" warning fuer WALK_DIRECTIONS — wir nutzen den Type
// `WalkDirection` aktiv, aber das Symbol nur indirekt ueber Service-Calls.
void WALK_DIRECTIONS;
