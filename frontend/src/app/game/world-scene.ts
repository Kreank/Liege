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
import { ANIMATED_MONSTER_WALK_SET } from '../core/data/monster-sprites';
import {
  STRUCTURE,
  USABLE_STRUCTURE_TYPES,
  isHarvestableStructureType,
} from '../core/data/structures';
import { NON_WALKABLE_TILES, TILE, TILE_BY_ID, TILE_SIZE } from '../core/data/tiles';
import type { Chunk, Structure } from '../core/models/chunk.model';
import type { GroundItem } from '../core/models/item.model';
import type { NPC } from '../core/models/npc.model';
import type { OnlinePlayer } from '../core/models/player.model';
import type { ServerMessage } from '../core/models/ws-message.model';
import type { GameBridgeService } from '../core/services/game-bridge.service';
import type { TooltipService } from '../core/services/tooltip.service';
import type { AssetLoaderService } from './asset-loader.service';
import {
  WALK_DIRECTIONS,
  type WalkDirection,
} from './asset-loader.service';
import type { EffectAnimationsService } from './effect-animations.service';
import type { WalkAnimationsService } from './walk-animations.service';
import { BiomeAmbient } from './biome-ambient';
import { COMBAT_FX } from './combat-fx';
import { DayNightOverlay } from './day-night-overlay';
import { DisasterOverlay } from './disaster-overlay';
import { DungeonRenderer } from './dungeon-renderer';
import { setupInput } from './input';
import { MobHpBars } from './mob-hp-bar';
import { NameLabels } from './name-labels';
import { NpcMoodIcons } from './npc-mood-icon';
import { NpcSpeechBubbles } from './npc-speech-bubble';
import { PlaceGhost } from './place-ghost';
import { QuestMarkerWorld } from './quest-marker-world';
import { SensePulse } from './sense-pulse';
import { SpritePool } from './sprite-pools';
import { VISUAL_EFFECTS } from './visual-effects';
import { WeatherParticles } from './weather-particles';
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
  /** H3.8 — TooltipService für Mob-Hover-Tooltips (optional, weil der
   *  externe MobHoverController in `phaser-game.component.ts` denselben
   *  Job macht — defensiv falls die WorldScene-interne Hover-Detection
   *  von einer parallelen Subagent-Edit überschrieben wird). */
  readonly tooltip?: TooltipService;
}

/** Render-Tiefen (Z-Order). */
const DEPTH = {
  TILES: 0,
  /** Gebäude-Boden (floor-Layer): über dem Welt-Tile, aber UNTER Objekten,
   *  Items, NPCs — damit Wände/Möbel/Items auf dem Boden stehen statt
   *  dahinter. */
  FLOOR: 2,
  GROUND_ITEMS: 5,
  STRUCTURES: 10,
  NPCS: 20,
  PLAYERS: 30,
  ME: 40,
} as const;

/** Versatz (Anteil von TILE_SIZE), um den Wand-/Tür-Sprites zur Gebäude-
 *  Außenseite geschoben werden, damit der zentrierte Wand-Streifen an der
 *  Außenkante seines Tiles sitzt. ~0.28 rückt den Streifenrand etwa auf die
 *  Tile-Kante. Bei Bedarf feinjustieren. */
const WALL_EDGE_SHIFT = 0.28;

/** Render-Skalierung für Wände/Türen (Vielfaches von TILE_SIZE). >1 lässt die
 *  zentrierten Streifen-Sprites überlappen, damit Ecken/Nähte nach dem
 *  Außen-Versatz schließen (Assets sind sonst „zu kurz"). Feinjustierbar. */
const WALL_RENDER_SCALE = 1.32;

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
  /** Tooltip-Service (Mob-Hover, H3.8). Optional — falls null, übernimmt
   *  der externe MobHoverController in phaser-game.component.ts. */
  private tooltip: TooltipService | null = null;
  /** Disaster-Overlay (Tint, Particle-Emitter, Lightning-Bolts) — G4. */
  private disasterOverlay: DisasterOverlay | null = null;
  /** Welle H2-A: Mob-HP-Bars über NPC-Sprites (H2.2). */
  private mobHpBars: MobHpBars | null = null;
  private nameLabels: NameLabels | null = null;
  /** Welle H2-A: NPC-Sprechblasen (H2.11). */
  private speechBubbles: NpcSpeechBubbles | null = null;
  /** Welle H2-A: Place-Ghost-Preview im Build-Mode (H2.16). */
  private placeGhost: PlaceGhost | null = null;
  /** Welle H2-A: Tag/Nacht-Tint-Overlay (H2.23). */
  private dayNightOverlay: DayNightOverlay | null = null;
  /** Welle H3-A: Quest-Marker über Ziel-NPCs (H3.5). */
  private questMarkers: QuestMarkerWorld | null = null;
  /** Welle H3-A: Mood-Icon über NPCs (H3.6). */
  private moodIcons: NpcMoodIcons | null = null;
  /** Welle H3-A: Sense-Pulse-Ring bei `dungeon_sense` (H3.10). */
  private sensePulse: SensePulse | null = null;
  /** Welle H3-A: Wetter-Partikel (H3.14). */
  private weatherParticles: WeatherParticles | null = null;
  private biomeAmbient: BiomeAmbient | null = null;

  // ─── Tile-Layer ─────────────────────────────────────────────────────
  private readonly chunkContainers = new Map<string, Phaser.GameObjects.Container>();
  private lastChunksRef: readonly Chunk[] | null = null;
  private chunkSize = 32;
  /** Overworld-Tile-Layer sichtbar? Wird auf `false` gesetzt, sobald der
   *  Spieler einen Dungeon betritt — Overworld-Chunks bleiben im Speicher
   *  (keine Re-Render-Kosten beim Exit), nur ihre Container werden
   *  unsichtbar geschaltet. */
  private overworldTilesVisible = true;

  // ─── Dungeon-Mode (Welle H1-A — H1.10 / H1.11) ─────────────────────
  /** Eigener Renderer für Dungeon-Floors. Lebt parallel zum Overworld-
   *  Tile-Layer; wird durch das `dungeonFloor()`-Signal in `update()`
   *  getriggert. */
  private dungeonRenderer: DungeonRenderer | null = null;
  /** Letzte gesehene Floor-Version (`dungeonFloor.version`), um
   *  `show()` vs `swap()` zu entscheiden und Doppel-Rerender zu vermeiden. */
  private lastDungeonVersion = 0;
  /** Letzte Dungeon-ID — wenn sie wechselt, ist es ein neuer Eintritt
   *  (show + Fade-In). Bei gleicher ID + neuer Version: Floor-Wechsel
   *  innerhalb desselben Dungeons (swap mit Fade-Out/In). */
  private lastDungeonId: number | string | null = null;

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
  /** Bug 31.05 Smooth-Move: erster Kamera-Frame snapt instant; danach
   *  lerpt der Update-Tick weich auf die Player-Pos zu. Ohne den Flag
   *  würde der Spawn-Frame auch lerped → Kamera fliegt anfangs ein. */
  private cameraInit = false;
  /** Letzte Spieler-Tile-Position für Move-Intent-Deduplication. */
  private lastSentMoveTile: { x: number; y: number } | null = null;
  /** Lokaler Sprint-Zustand — wir senden nur on/off-Edges an den Server. */
  private sprintSent = false;
  /** True, sobald das Backend uns wegen Erschöpfung gestoppt hat. Bleibt
   *  gesetzt, bis der Spieler Shift los- und neu drückt — sonst würde der
   *  Pixel-Tick mit dem ersten regenerierten Stamina-Punkt sofort wieder
   *  sprinten (Flicker). */
  private sprintBlocked = false;
  /** Letzter beobachteter Wert von `state.sprintExhaustEpoch()` — Edge-
   *  Detection für `sprintBlocked = true`. */
  private lastSprintExhaustEpoch = 0;

  // ─── Pixel-Movement (Legacy-Style, 31.05) ────────────────────────────
  /** Eigene Player-Pixel-Pos (Welt-Koord). Init bei erstem state.player(). */
  private myPx = 0;
  private myPy = 0;
  /** Init-Flag: erst nach erstem player()-Update läuft die Pixel-Sim. */
  private myPosInit = false;
  /** Held-State der Richtungstasten — wird vom Input-Modul gefüllt. */
  private heldKeys: Readonly<{
    up: boolean; down: boolean; left: boolean; right: boolean; sprint: boolean;
  }> = { up: false, down: false, left: false, right: false, sprint: false };
  /** Move-Speed in Pixel/Sekunde (Legacy-Wert). Sprint = ×1.5. */
  private readonly moveSpeed = 240;
  private readonly sprintMult = 1.5;
  /** Kollisions-Hitbox: 4-Ecken-Check mit Halb-Kantenlänge. Deutlich kleiner
   *  als ein halber Tile, damit sich Bewegung nicht "verklemmt" anfühlt und
   *  der Spieler durch enge Lücken rutscht ("forgiveness"). 0.44 war zu groß
   *  (≈28px-Box, fast volle Kachel) → fühlte sich nach unsichtbaren Wänden an;
   *  0.30 ≈ 19px-Box. */
  private readonly collisionHalf = TILE_SIZE * 0.30;
  /** Letzte Frame-Zeit für dt-Berechnung. */
  private lastUpdateTime = 0;
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
    this.tooltip = data.tooltip ?? null;
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
      update: (s, g) => {
        this.updateMovableSprite(s, g.x, g.y);
        // Fallback→echte Textur swappen, sobald das on-demand-Item-Asset da ist.
        this.trySwapFallbackTexture(s);
      },
    });

    // ─── Input → Intents ──────────────────────────────────────────────
    // Pixel-Movement (Legacy-Style): setupInput trackt nur held-state, der
    // update-Tick rechnet Pixel-Delta + Kollisions-Check selbst aus.
    const inputHandle = setupInput(this, {
      onTileClick: (pos) => this.handleTileClick(pos.x, pos.y),
      onSprintChange: (on) => this.handleSprintChange(on),
      onToggleBuildMode: () => {
        this.bridge.toggleBuildMode();
      },
    });
    this.heldKeys = inputHandle.keys;

    // ─── H3.8 — Mob-Hover-Tooltip ─────────────────────────────────────
    // Einfacher Pointer-Move-Listener auf der Scene. Statt jeden NPC-Sprite
    // einzeln auf `setInteractive` zu setzen (würde mit Build-Mode-/Tile-
    // Click-Routing kollidieren), berechnen wir aus dem Pointer die Tile-
    // Koord und matchen gegen den `npcsVisible`-Snapshot. O(N) pro Move-
    // Event ist akzeptabel — typisch <50 sichtbare NPCs auf dem Screen.
    this.input.on(Phaser.Input.Events.POINTER_MOVE, (pointer: Phaser.Input.Pointer) => {
      this.handleNpcHover(pointer);
    });
    // Pointer verlässt das Game-Canvas → Mob-Tooltip aus. Vermeidet Stale-
    // State, wenn der User die Maus über ein UI-Panel zieht.
    this.input.on(Phaser.Input.Events.POINTER_OUT, () => {
      if (this.tooltip?.activeMob()) this.tooltip.hide();
    });

    // ─── Walk-Animations registrieren ─────────────────────────────────
    // Nach `preload()` sind alle Frame-Texturen im Cache — jetzt definieren
    // wir pro Kind × Richtung eine Phaser-Animation.
    this.walkAnimations.createAnimations(this);
    // G4: Spell-FX + Disaster-Layer-Anims registrieren.
    this.effectAnimations.createAnimations(this);
    // G4: Disaster-Overlay initialisieren (Tint/Particle/Bolt).
    this.disasterOverlay = new DisasterOverlay(this, this.effectAnimations);
    // Welle H1-A: Dungeon-Renderer (Tile-Layer + Feature-Sprites). Aktiv
    // nur wenn `state.dungeonFloor()` non-null ist (siehe update()).
    this.dungeonRenderer = new DungeonRenderer(this);
    // Welle H2-A: Mob-HP-Bars + NPC-Sprechblasen + Place-Ghost + Tag/Nacht.
    this.mobHpBars = new MobHpBars(this);
    this.nameLabels = new NameLabels(this);
    this.speechBubbles = new NpcSpeechBubbles(this);
    this.placeGhost = new PlaceGhost(
      this,
      this.assetLoader,
      () => this.input.activePointer ?? null,
      () => this.bridge.state.structures(),
    );
    this.dayNightOverlay = new DayNightOverlay(this);
    // Welle H3-A: Polish-Visuals (Quest-Marker, Mood-Icons, Sense-Pulse, Wetter).
    this.questMarkers = new QuestMarkerWorld(this);
    this.moodIcons = new NpcMoodIcons(this);
    this.sensePulse = new SensePulse(this);
    this.weatherParticles = new WeatherParticles(this);
    this.biomeAmbient = new BiomeAmbient(this);

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
      this.mobHpBars?.destroyAll();
      this.speechBubbles?.destroyAll();
      this.placeGhost?.destroy();
      this.dayNightOverlay?.destroy();
      this.questMarkers?.destroyAll();
      this.moodIcons?.destroyAll();
      this.sensePulse?.destroyAll();
      this.weatherParticles?.destroy();
      this.biomeAmbient?.destroy();
    });
    this.events.once(Phaser.Scenes.Events.DESTROY, () => {
      this.fxSub?.unsubscribe();
      this.fxSub = null;
      this.mobHpBars?.destroyAll();
      this.speechBubbles?.destroyAll();
      this.placeGhost?.destroy();
      this.dayNightOverlay?.destroy();
      this.questMarkers?.destroyAll();
      this.moodIcons?.destroyAll();
      this.sensePulse?.destroyAll();
      this.weatherParticles?.destroy();
      this.biomeAmbient?.destroy();
    });
  }

  override update(time: number, _delta: number): void {
    // Pro Frame: prüfen, ob die State-Listen sich identitätsmäßig geändert
    // haben (Signals liefern immutable Arrays). Identity-Check ist O(1) —
    // ein Deep-Diff würde dem 60-FPS-Budget schaden.

    // ─── Welle H1-A: Dungeon-Mode-Switch zuerst ───────────────────────
    // Reihenfolge ist wichtig: wir prüfen ZUERST den Mode-Wechsel, damit
    // der Overworld-Tile-Sync danach den Visibility-Flip kennt (statt
    // einen verwaisten Container für einen unsichtbaren Layer zu bauen).
    this.syncDungeonMode();

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

    // ─── Pixel-Movement + Kamera (Legacy myPx/myPy) ────────────────────
    // Der eigene Spieler läuft kontinuierlich in Pixeln. Server bekommt
    // nur Tile-Updates beim Überqueren der Tile-Grenze. Andere Spieler
    // bleiben tile-snap (kommen ja nur per WS-Echo rein).
    const me = this.bridge.state.player();
    if (me) {
      this.tickPixelMovement(me, time);
      const cam = this.cameras.main;
      if (!this.cameraInit) {
        cam.centerOn(this.myPx, this.myPy);
        this.cameraInit = true;
      } else {
        const curX = cam.scrollX + cam.width / 2;
        const curY = cam.scrollY + cam.height / 2;
        const dx = this.myPx - curX;
        const dy = this.myPy - curY;
        if (dx * dx + dy * dy > (TILE_SIZE * 4) * (TILE_SIZE * 4)) {
          cam.centerOn(this.myPx, this.myPy);
        } else {
          // 0.25 ist aggressiv genug, damit die Kamera dem schnellen
          // Sprint noch folgt, ohne zu zittern.
          cam.centerOn(curX + dx * 0.25, curY + dy * 0.25);
        }
      }
      // Eigenes Sprite im Pool auf Pixel-Pos ziehen — überschreibt das
      // tile-snap-Setzen aus updatePlayerSprite.
      const meSprite = this.playerPool.get(String(me.player_id));
      if (meSprite) {
        const s = meSprite as Phaser.GameObjects.GameObject & { x: number; y: number };
        s.x = this.myPx;
        s.y = this.myPy;
      }
    }

    // ─── Welle H2-A: Overlay-Updates pro Frame ─────────────────────────
    // HP-Bars und Sprech-Bubbles ans aktuelle NPC-Snapshot anhängen
    // (Bewegung folgt dem Sprite).
    if (this.mobHpBars) this.mobHpBars.syncPositions(npcs);
    if (this.speechBubbles) this.speechBubbles.syncPositions(npcs);
    // Issue 31.05 #5: Name-Labels über Spieler + Friendly-NPCs
    if (this.nameLabels) {
      const players = Object.values(this.bridge.state.players());
      const selfId = this.bridge.state.player()?.player_id;
      // Label an die ECHTE Sprite-Pixel-Position binden (self = myPx/myPy via
      // Pixel-Movement, andere = interpolierte Pool-Sprites) — sonst hinkt das
      // Label der Server-Tile-Position hinterher und springt.
      this.nameLabels.sync(
        players, npcs,
        selfId !== undefined ? String(selfId) : undefined,
        (kind, id) => {
          const sprite = (kind === 'player'
            ? this.playerPool.get(String(id))
            : this.npcPool.get(id)) as
            (Phaser.GameObjects.GameObject & { x: number; y: number }) | undefined;
          return sprite ? { x: sprite.x, y: sprite.y } : undefined;
        },
      );
    }
    // Place-Ghost: Cursor-Tracking + Build-Mode-Sichtbarkeit.
    if (this.placeGhost) {
      this.placeGhost.update(
        this.bridge.buildMode(),
        this.bridge.selectedStructure(),
      );
    }
    // Tag/Nacht-Tint: phase aus dem time-Signal lesen.
    if (this.dayNightOverlay) {
      const t = this.bridge.state.time();
      this.dayNightOverlay.setPhase(t?.phase);
    }

    // ─── Welle H3-A: Polish-Overlays ─────────────────────────────────
    // Quest-Marker: über NPCs, die Ziel einer aktiven/completed Quest sind.
    // Mood-Icons: folgen den NPCs (Reset via WS-Stream-Sub).
    // Weather-Particles: lesen weather()-Signal pro Frame (no-op bei clear).
    if (this.questMarkers) {
      this.questMarkers.update(
        this.bridge.state.quests(),
        npcs,
        time,
      );
    }
    if (this.moodIcons) this.moodIcons.syncPositions(npcs);
    if (this.weatherParticles) this.weatherParticles.update(this.bridge.state.weather());
    this.biomeAmbient?.update(this.currentBiomeTileId());
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

  /**
   * H3.8 — Mob-Hover: Pointer-Position → Tile-Koord → NPC-Lookup.
   * Wenn ein NPC unter dem Pointer ist, zeigen wir den Mob-Tooltip am
   * Bildschirm-Pointer (nicht Welt-Koord!) an; sonst hiden wir ihn (nur
   * wenn aktuell ein Mob-Tooltip läuft — Item-Tooltips bleiben unberührt).
   *
   * Pinned-Tooltips bleiben — der TooltipService selbst gated `move`/`hide`
   * darauf, hier muss man nichts extra prüfen.
   */
  private handleNpcHover(pointer: Phaser.Input.Pointer): void {
    if (!this.tooltip) return; // externer MobHoverController übernimmt
    const tileX = Math.floor(pointer.worldX / TILE_SIZE);
    const tileY = Math.floor(pointer.worldY / TILE_SIZE);
    const npcs = this.bridge.state.npcsVisible();
    const npc = npcs.find((n) => n.x === tileX && n.y === tileY);
    if (npc) {
      this.tooltip.showMob(npc, pointer.x, pointer.y);
    } else if (this.tooltip.activeMob()) {
      this.tooltip.hide();
    }
  }

  private handleTileClick(tileX: number, tileY: number): void {
    // ─── Build-Mode-Pfad ─────────────────────────────────────────────────
    // Klick auf leeres Tile → `place_structure`. Klick auf belegtes Tile
    // fällt durch in die Default-Logik (so kann man auch im Build-Mode
    // bestehende Strukturen abreißen/benutzen).
    if (this.bridge.buildMode()) {
      const structures = this.bridge.state.structures();
      // `floor` lebt im floor-Layer (siehe village_spawner) und blockiert
      // Object-Layer-Placements NICHT — nur object-Layer-Strukturen zählen.
      const blocked = structures.some(
        (s) => s.x === tileX && s.y === tileY && s.type !== 'floor',
      );
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

    // 0) Dungeon-Truhe (H1.5)? Im Dungeon (state.inDungeon()) werden Truhen
    //    NICHT als Struktur geführt, sondern als Feature im Dungeon-Floor-
    //    Payload. Wir matchen die Tile-Pos gegen `dungeonChests` (Subagent A
    //    füllt die Liste beim `dungeon_enter`-Handler). Bereits geöffnete
    //    Truhen werden übersprungen — Backend würde ohnehin ablehnen, aber
    //    das erspart einen sinnlosen Roundtrip + Toast-Spam.
    if (this.bridge.state.inDungeon()) {
      const chests = this.bridge.state.dungeonChests();
      const chest = chests.find((c) => c.x === tileX && c.y === tileY);
      if (chest && !chest.opened) {
        this.bridge.sendDungeonChest(tileX, tileY);
        return;
      }
    }

    // 1) NPC? Hostile → attack, merchant → trade, friendly → Dialog lokal.
    //    H1.8: Wir senden NICHT mehr `talk_to_npc` mit leerer Message (das
    //    Backend droppt silent). Stattdessen öffnet ein Click den Dialog
    //    lokal — der erste Send-Roundtrip läuft, sobald der Spieler etwas
    //    in das Input-Feld tippt und Enter drückt.
    const npcs = this.bridge.state.npcsVisible();
    const npcHere = npcs.find((n) => n.x === tileX && n.y === tileY);
    if (npcHere) {
      if (this.isHostileNpc(npcHere)) {
        this.bridge.sendAttackNpc(npcHere.id);
      } else if (this.isMerchantNpc(npcHere)) {
        // Händler: direkt Handels-Modal öffnen (Subagent C / H1.13 bauen
        // das Trade-Panel-Sell-Tab). Backend antwortet mit `trade_open`.
        this.bridge.sendIntent({ type: 'open_trade', npc_id: npcHere.id });
      } else {
        // Friendly → Dialog lokal öffnen. Kein WS-Frame nötig — der Server
        // bekommt erst beim ersten Send (Enter im Input) Bescheid.
        this.bridge.state.openDialog({
          npc_id: npcHere.id,
          npc_name: npcHere.name ?? npcHere.kind,
          npc_kind: npcHere.kind,
          backstory: '',
        });
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

    // 3) Struktur? Harvest-bar (Tree/Stone/Ore/Wall/Crop) → attack,
    //    Tür → toggle_door (H1.12), sonst use (Bett/Brunnen/Schild/Truhe/…).
    const structures = this.bridge.state.structures();
    // Object-Layer bevorzugen: `floor` ist ein passives Boden-Tile (liegt
    // oft UNTER Türen/Wänden/Möbeln, siehe village_spawner._place_house).
    // Ohne Filter würde `find` häufig den Boden zurückgeben und der Klick
    // ginge als `use_structure` auf den Floor — Tür-Toggle/Wall-Attack
    // würden nie ausgelöst.
    const structsHere = structures.filter((s) => s.x === tileX && s.y === tileY);
    const structHere =
      structsHere.find((s) => s.type !== 'floor') ?? structsHere[0];
    if (structHere) {
      if (isDoorType(structHere.type)) {
        // H1.12 — Tür-Toggle via separates Intent. Backend antwortet mit
        // `structure_replaced` (door_open ↔ door_closed); Renderer macht
        // den Sprite-Swap.
        this.bridge.sendToggleDoor(tileX, tileY);
      } else if (this.shouldAttackStructure(structHere.type)) {
        this.bridge.sendAttackStructure(tileX, tileY);
      } else {
        this.bridge.sendUseStructure(tileX, tileY);
      }
      return;
    }

    // 4) Angrenzendes Wasser-Tile? → direkt aus dem See trinken.
    //    Linksklick auf ein Wasser-Tile im Umkreis von 1 Feld sendet
    //    `drink_water_tile {x, y}` (Backend prüft Distanz + Tile-Typ erneut
    //    und stillt den Durst). Spart den Umweg „Eimer füllen → trinken",
    //    wenn man nur schnell den Durst stillen will.
    const myTx = Math.floor(this.myPx / TILE_SIZE);
    const myTy = Math.floor(this.myPy / TILE_SIZE);
    const cheb = Math.max(Math.abs(tileX - myTx), Math.abs(tileY - myTy));
    if (cheb <= 1 && this.tileIdAt(tileX, tileY) === TILE.WATER.id) {
      this.bridge.sendIntent({ type: 'drink_water_tile', x: tileX, y: tileY });
      return;
    }

    // 5) Leeres Tile: KEIN Klick-zum-Bewegen (Design-Entscheidung 2026-05-31).
    // Bewegung läuft ausschließlich über WASD (Pixel-Movement). Linksklick ist
    // reine Interaktion/Angriff auf Objekte/NPCs; trifft der Klick nichts,
    // passiert nichts. (Rechtsklick ist für eine spätere Aktion reserviert.)
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
    // Welle H bug 31.05 #4: creature_*-Pool (128 Slugs aus monster_longlist)
    // ist nicht im statischen CREATURE_KINDS-Set. Prefix-Check fängt das ab.
    // overworld_*-Pool ist explizit drin, aber Doppel-Check schadet nicht.
    if (n.kind.startsWith('creature_')) return true;
    if (n.kind.startsWith('overworld_')) return true;
    return CREATURE_KINDS.has(n.kind);
  }

  /**
   * Merchant-Detection (H1.8/H1.13). Backend hat keinen `is_merchant`-Flag;
   * stattdessen ist der NPC-Kind `merchant` (siehe core/data/npc-sprites.ts).
   * Weibliche Variante `merchant_female` ist ebenfalls Händler. Erweiterbar,
   * sobald Backend mehr Händler-Slugs einführt.
   */
  private isMerchantNpc(n: { readonly kind: string }): boolean {
    return n.kind === 'merchant' || n.kind === 'merchant_female';
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

  private handleSprintChange(shiftHeld: boolean): void {
    // Wir senden nicht direkt — der Pixel-Tick gated `effectiveSprint`
    // an Stamina/Block und schickt den Intent dann selbst. Hier nur
    // den Erschöpfungs-Block aufheben, wenn der Spieler Shift loslässt
    // (Edge: Backend hat per `sprint_state {exhausted}` blockiert, neuer
    // Druck soll wieder funktionieren sobald Stamina da ist).
    if (!shiftHeld) {
      this.sprintBlocked = false;
    }
  }

  // ─── Pixel-Movement (Legacy myPx/myPy, 31.05) ──────────────────────────
  //
  // Jeden Frame: lese held-keys, baue Velocity-Vektor, achsen-separater
  // Kollisions-Check (slide-along-wall), update myPx/myPy. Wenn die
  // Tile-Pos sich geändert hat, sende `move`-Intent + patche optimistisch
  // `state.player()` damit andere Logik (Kamera, Walk-Anim, Quest-Marker)
  // den Move sofort sieht — Backend bestätigt per `player_moved` und
  // _handlePlayerMoved konvergiert.
  private tickPixelMovement(
    me: {
      readonly player_id: number | string;
      readonly x: number;
      readonly y: number;
      readonly stamina?: number;
    },
    timeMs: number,
  ): void {
    // Erster Frame: Pixel-Pos aus Server-Tile initialisieren.
    if (!this.myPosInit) {
      this.myPx = me.x * TILE_SIZE + TILE_SIZE / 2;
      this.myPy = me.y * TILE_SIZE + TILE_SIZE / 2;
      this.myPosInit = true;
      this.lastUpdateTime = timeMs;
      return;
    }
    // Server-Reconcile: Wenn das Backend uns sehr weit verschoben hat
    // (Teleport, Floor-Wechsel, Respawn), folge dem Server statt am
    // alten Pixel-State festzuhalten.
    const serverPx = me.x * TILE_SIZE + TILE_SIZE / 2;
    const serverPy = me.y * TILE_SIZE + TILE_SIZE / 2;
    const drx = serverPx - this.myPx;
    const dry = serverPy - this.myPy;
    if (drx * drx + dry * dry > (TILE_SIZE * 3) * (TILE_SIZE * 3)) {
      this.myPx = serverPx;
      this.myPy = serverPy;
    }

    // dt in Sekunden, gegen Lag-Spikes auf 100ms gecappt.
    const dt = Math.min(0.1, (timeMs - this.lastUpdateTime) / 1000);
    this.lastUpdateTime = timeMs;
    if (dt <= 0) return;

    // Velocity aus held-keys.
    let vx = 0, vy = 0;
    if (this.heldKeys.left)  vx -= 1;
    if (this.heldKeys.right) vx += 1;
    if (this.heldKeys.up)    vy -= 1;
    if (this.heldKeys.down)  vy += 1;
    if (vx === 0 && vy === 0) return;
    const mag = Math.hypot(vx, vy);
    if (mag > 1) { vx /= mag; vy /= mag; }

    // Sprint-Gate: Backend-Erschöpfung → Block (bis Shift losgelassen);
    // ohne Stamina → kein Sprint. Edge-Detect über Exhaust-Epoch.
    const exhaustEpoch = this.bridge.state.sprintExhaustEpoch();
    if (exhaustEpoch !== this.lastSprintExhaustEpoch) {
      this.lastSprintExhaustEpoch = exhaustEpoch;
      this.sprintBlocked = true;
    }
    const stamina = me.stamina ?? 0;
    const effectiveSprint =
      this.heldKeys.sprint && !this.sprintBlocked && stamina > 0;
    if (effectiveSprint !== this.sprintSent) {
      this.sprintSent = effectiveSprint;
      this.bridge.sendSprint(effectiveSprint);
    }
    const speed = this.moveSpeed * (effectiveSprint ? this.sprintMult : 1);
    const dpx = vx * speed * dt;
    const dpy = vy * speed * dt;

    // Achsen-separat: slide along walls.
    if (dpx !== 0) {
      const nx = this.myPx + dpx;
      if (this.canMoveTo(nx, this.myPy)) this.myPx = nx;
    }
    if (dpy !== 0) {
      const ny = this.myPy + dpy;
      if (this.canMoveTo(this.myPx, ny)) this.myPy = ny;
    }

    // Tile-Wechsel? → Server informieren + optimistisch state patchen.
    const newTileX = Math.floor(this.myPx / TILE_SIZE);
    const newTileY = Math.floor(this.myPy / TILE_SIZE);
    if (newTileX !== me.x || newTileY !== me.y) {
      this.bridge.sendMove(newTileX, newTileY);
      // Optimistic patch — sonst rechnet die nächste tickPixelMovement-
      // Iteration `me.x` immer noch alt und der Server-Reconcile-Check
      // schießt zurück. Wir mutieren das Signal direkt (interner Sync;
      // ein dedizierter setOwnPosition-API-Wrapper wäre overkill).
      const state = this.bridge.state;
      const cur = state.player();
      if (cur) {
        state.player.set({ ...cur, x: newTileX, y: newTileY });
      }
    }

    // ─── Walk-Anim: Direction aus Velocity, nicht aus Tile-Delta ───────
    // handleWalkAnim greift nur bei Tile-Wechsel; während der Pixel-Sim
    // bewegt sich der Sprite innerhalb eines Tiles. Wir feuern direkt
    // gegen den Anim-Pfad mit der aktuellen Richtung aus vx/vy.
    const meKey = String(me.player_id);
    const meSprite = this.playerPool.get(meKey);
    if (meSprite) {
      const preset = this.playerPresetFor(meKey);
      if (preset) {
        const dir = directionFor(vx, vy, 'down');
        this.playWalkAnim(meSprite, preset, dir);
      }
      const track = this.playerTracks.get(meKey);
      if (track) track.lastMoveFrame = this.game.loop.frame;
    }
  }

  /** 4-Ecken-Hitbox prüft die Tile-Walkability auf alle Ecken. Erlaubt
   *  Slide-along-Wall in Verbindung mit achsen-separater Anwendung. */
  private canMoveTo(px: number, py: number): boolean {
    // Escape-Ventil: steckt der Spieler schon in einem blockierenden
    // Tile (z.B. weil eine Mauer NACH ihm dorthin platziert wurde),
    // Kollisions-Check aussetzen damit er sich rausbewegen kann.
    const curTx = Math.floor(this.myPx / TILE_SIZE);
    const curTy = Math.floor(this.myPy / TILE_SIZE);
    if (!this.isTileWalkable(curTx, curTy)) return true;
    const h = this.collisionHalf;
    const corners: ReadonlyArray<readonly [number, number]> = [
      [px - h, py - h], [px + h, py - h],
      [px - h, py + h], [px + h, py + h],
    ];
    for (const [cx, cy] of corners) {
      const tx = Math.floor(cx / TILE_SIZE);
      const ty = Math.floor(cy / TILE_SIZE);
      if (!this.isTileWalkable(tx, ty)) return false;
    }
    return true;
  }

  /** Frontend-Walkability-Check: lädt Chunk-Tile + Struktur-Block-Flag.
   *  Im Dungeon wäre eine andere Quelle nötig — solange die Pixel-Sim
   *  nur Overworld gilt, ist das OK; dort fällt der collision-check
   *  zurück auf den Backend-Reject (langsamer, aber funktional). */
  private isTileWalkable(tx: number, ty: number): boolean {
    // Dungeon: kein lokaler Walkability-Layer im Frontend verfügbar,
    // also alles freigeben — Backend rejects landen im Snap-Back.
    if (this.bridge.state.dungeonFloor()) return true;
    const chunks = this.bridge.state.chunks();
    const cx = Math.floor(tx / this.chunkSize);
    const cy = Math.floor(ty / this.chunkSize);
    const chunk = chunks.find((c) => c.cx === cx && c.cy === cy);
    if (!chunk) return false; // noch nicht geladen → vorerst blockieren
    const localX = tx - cx * this.chunkSize;
    const localY = ty - cy * this.chunkSize;
    const row = chunk.tiles[localY];
    if (!row) return false;
    const tile = row[localX];
    if (tile == null) return false;
    if (NON_WALKABLE_TILES.has(tile)) return false;
    // Strukturen mit `blocking: true` blockieren ebenfalls.
    // WICHTIG: KEIN `break` nach der ersten Struktur — seit Boden unter den
    // Wänden liegt, hat ein Wand-Tile ZWEI Strukturen (floor + wall). Der
    // Boden blockt nicht; bräche die Schleife beim Boden ab, liefe man durch
    // die Wand. Wir prüfen daher ALLE Strukturen am Tile.
    const structures = this.bridge.state.structures();
    for (const s of structures) {
      if (s.x !== tx || s.y !== ty) continue;
      const def = STRUCTURE[s.type];
      if (def?.blocking) return false;
    }
    return true;
  }

  /** Liefert die Terrain-Tile-ID an einer Welt-Tile-Koordinate — oder `null`,
   *  wenn der Chunk noch nicht geladen ist oder wir im Dungeon sind (dort gibt
   *  es keinen lokalen Tile-Layer). Mirror des Chunk-Lookups aus
   *  `isTileWalkable`; wird fürs Wasser-Trinken (`drink_water_tile`) genutzt. */
  private tileIdAt(tx: number, ty: number): number | null {
    if (this.bridge.state.dungeonFloor()) return null;
    const chunks = this.bridge.state.chunks();
    const cx = Math.floor(tx / this.chunkSize);
    const cy = Math.floor(ty / this.chunkSize);
    const chunk = chunks.find((c) => c.cx === cx && c.cy === cy);
    if (!chunk) return null;
    const row = chunk.tiles[ty - cy * this.chunkSize];
    if (!row) return null;
    const tile = row[tx - cx * this.chunkSize];
    return tile == null ? null : tile;
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
    // Welle H1-A: Sichtbarkeit der neuen Chunks an den aktuellen Mode
    // anpassen. Falls wir gerade im Dungeon sind, sollen frisch
    // gerenderte Overworld-Chunks (z. B. nach Backend-Lazy-Spawn)
    // unsichtbar bleiben bis zum Exit.
    if (!this.overworldTilesVisible) {
      for (const container of this.chunkContainers.values()) {
        container.setVisible(false);
      }
    }
  }

  /**
   * Welle H1-A — H1.10 / H1.11: Dungeon-Mode-Wechsel.
   *
   * Liest `state.dungeonFloor()` und schaltet die Scene zwischen
   * Overworld-Layer und `DungeonRenderer` um:
   *   • Eintritt (Overworld → Dungeon):   Overworld-Chunks hide() +
   *                                       NPC/Item/Struct-Pools clearen +
   *                                       `dungeonRenderer.show(floor)`.
   *   • Floor-Wechsel (Dungeon → Dungeon, gleiche ID):
   *                                       `dungeonRenderer.swap(floor)` +
   *                                       NPC/Item/Struct-Pools clearen.
   *   • Exit (Dungeon → Overworld):       `dungeonRenderer.hide()` +
   *                                       Overworld-Chunks show().
   *
   * Pool-Clearing ist Pflicht: Backend sendet beim `dungeon_exit` eine
   * NPC-Liste, die nur die Overworld-Mobs enthält — der `npcsVisible`-
   * Sync entfernt die Dungeon-Mobs implizit. Strukturen/Items werden
   * aber NICHT vom Backend re-synct → wir blenden ihre Container-Layer
   * über die Sichtbarkeit der Pools per Sprite-Hide weg. (Die Datenliste
   * `state.structures()` ändert sich nicht, wenn der Spieler in einen
   * Dungeon geht; sie blieben sonst sichtbar mitten im Wand-Layer.)
   */
  private syncDungeonMode(): void {
    if (!this.dungeonRenderer) return;
    const floor = this.bridge.state.dungeonFloor();
    const wasInDungeon = this.lastDungeonId !== null;
    const isInDungeon = floor !== null;

    if (!isInDungeon) {
      if (wasInDungeon) {
        // Exit → Overworld
        this.dungeonRenderer.hide();
        this.setOverworldVisible(true);
        this.lastDungeonId = null;
        this.lastDungeonVersion = 0;
      }
      return;
    }

    // floor !== null
    const enteringNew = floor.id !== this.lastDungeonId;
    const versionChanged = floor.version !== this.lastDungeonVersion;
    if (!enteringNew && !versionChanged) return;

    if (!wasInDungeon || enteringNew) {
      // Eintritt (Overworld → Dungeon) ODER Wechsel zwischen Dungeons
      // (unwahrscheinlich, aber defensiv: anderer Dungeon → wie Eintritt).
      this.setOverworldVisible(false);
      this.dungeonRenderer.show(floor);
    } else {
      // Gleicher Dungeon, neuer Floor → swap mit Fade-Animation.
      this.dungeonRenderer.swap(floor);
    }
    this.lastDungeonId = floor.id;
    this.lastDungeonVersion = floor.version;
  }

  /**
   * Zentraler Schalter für die Sichtbarkeit der Overworld-Sprites.
   * Struktur- und Ground-Item-Pools werden mit-gehided, damit Overworld-
   * Objekte nicht durch die Dungeon-Wände scheinen. Die NPC-Pool bleibt
   * ungetoggled — die Liste wird parallel vom GameStateService durch die
   * Dungeon-Floor-Mobs ersetzt (`_handleDungeonEnter` setzt `npcsVisible`
   * auf die Floor-NPCs aus der `dungeon_enter`-Payload).
   */
  private setOverworldVisible(visible: boolean): void {
    this.overworldTilesVisible = visible;
    for (const container of this.chunkContainers.values()) {
      container.setVisible(visible);
    }
    this.structurePool.setAllVisible(visible);
    this.groundItemPool.setAllVisible(visible);
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
    // On-Demand-Loading (Lag-Fix 2026-05-31): das Ziel-Asset ist evtl. noch
    // im Flug. Statt eines nicht-swappbaren Rectangles geben wir ein `Image`
    // mit einer generierten Platzhalter-Textur (Fallback-Farbe) zurück. Das
    // hat `setTexture`, sodass der `update*`-Pfad die echte Textur einsetzen
    // kann, sobald sie geladen ist. Der Magenta-/Kategorie-Debug-Look bleibt.
    const placeholderKey = this.fallbackTextureKey(fallbackColor);
    const img = this.add.image(0, 0, placeholderKey);
    img.setDisplaySize(sizePx, sizePx);
    // Merkt sich Ziel-Key + Größe für den Texture-Swap im update*-Pfad.
    const tagged = img as Phaser.GameObjects.Image & {
      __pendingTex?: string;
      __spriteSize?: number;
    };
    tagged.__pendingTex = textureKey;
    tagged.__spriteSize = sizePx;
    // WICHTIG: Statische Pools (Strukturen, Ground-Items) werden NUR bei
    // Signal-Reference-Wechsel neu gesynct (siehe update(): `if (structures
    // !== this.lastStructuresRef)`). Nach dem on-demand-Load ändert sich der
    // Reference NICHT → `update*` läuft nicht mehr → der Swap dort würde nie
    // greifen und das Sprite bliebe für immer ein Fallback-Quadrat. Daher
    // hängen wir uns direkt ans Lade-Ende GENAU dieser Textur und swappen
    // dann dieses konkrete Sprite. (Bewegliche Entities synct der bewegungs-
    // getriebene Signal-Wechsel ohnehin; dort ist es redundant, aber billig.)
    this.load.once(
      `filecomplete-image-${textureKey}`,
      () => this.trySwapFallbackTexture(img),
    );
    return img;
  }

  /**
   * Liefert (und erzeugt bei Bedarf einmalig) eine kleine, einfarbige
   * Platzhalter-Textur für die gegebene Fallback-Farbe. Wird als swappbares
   * Image-Fallback genutzt, solange das echte On-Demand-Asset noch lädt.
   */
  private fallbackTextureKey(color: number): string {
    const key = `__fallback_${color.toString(16)}`;
    if (!this.textures.exists(key)) {
      const g = this.add.graphics();
      g.fillStyle(color, 0.85);
      g.fillRect(0, 0, 8, 8);
      g.lineStyle(2, 0x000000, 0.6);
      g.strokeRect(0, 0, 8, 8);
      g.generateTexture(key, 8, 8);
      g.destroy();
    }
    return key;
  }

  /**
   * Swappt die Platzhalter-Textur eines Fallback-Images auf das echte Asset,
   * sobald `__pendingTex` im TextureManager verfügbar ist. No-op für echte
   * Image-Sprites (kein `__pendingTex`) und für Sprites ohne `setTexture`.
   */
  private trySwapFallbackTexture(obj: Phaser.GameObjects.GameObject): void {
    const tagged = obj as Phaser.GameObjects.Image & {
      __pendingTex?: string;
      __spriteSize?: number;
      setTexture?: (key: string) => void;
      setDisplaySize?: (w: number, h: number) => void;
    };
    // Sprite könnte bereits zerstört sein (Struktur/Item entfernt, bevor die
    // on-demand-Textur fertig lud) — der `filecomplete`-Listener feuert dann
    // trotzdem einmal. Nach destroy() ist `scene` null → kein setTexture.
    if (!tagged.scene) return;
    const tex = tagged.__pendingTex;
    if (!tex) return;
    if (!this.textures.exists(tex)) return;
    if (typeof tagged.setTexture !== 'function') return;
    tagged.setTexture(tex);
    const size = tagged.__spriteSize ?? TILE_SIZE;
    tagged.setDisplaySize?.(size, size);
    tagged.__pendingTex = undefined;
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
   *  Rectangle, Container (alle haben `x`/`y`-Setter über Transform).
   *
   *  `smooth=true` (Player/NPC): Tile-Wechsel werden per Linear-Tween über
   *  ~THROTTLE-Dauer geglättet, statt tile-snap zu jumpen. Das gibt den
   *  alten Legacy-Smooth-Look — der Server schickt nur alle ~120ms ein
   *  neues Tile, dazwischen interpoliert der Client. Großer Sprung
   *  (Teleport/Dungeon-Floor → >2 Tiles) ignoriert den Tween und snapt
   *  instant, sonst würde der Spieler über den halben Screen "fliegen".
   */
  private updateMovableSprite(
    obj: Phaser.GameObjects.GameObject,
    tileX: number,
    tileY: number,
    smooth = false,
  ): void {
    const t = obj as Phaser.GameObjects.GameObject & {
      x: number; y: number; __posInit?: boolean;
    };
    const targetX = tileX * TILE_SIZE + TILE_SIZE / 2;
    const targetY = tileY * TILE_SIZE + TILE_SIZE / 2;
    if (!smooth || !t.__posInit) {
      t.x = targetX;
      t.y = targetY;
      t.__posInit = true;
      return;
    }
    if (t.x === targetX && t.y === targetY) return;
    const ddx = targetX - t.x;
    const ddy = targetY - t.y;
    if (ddx * ddx + ddy * ddy > (TILE_SIZE * 2) * (TILE_SIZE * 2)) {
      t.x = targetX;
      t.y = targetY;
      return;
    }
    this.tweens.killTweensOf(obj);
    this.tweens.add({
      targets: obj,
      x: targetX,
      y: targetY,
      duration: 140,
      ease: 'Linear',
    });
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
    // Eigener Spieler: Pixel-Sim im update-Tick setzt die Position. Wir
    // markieren das Sprite nur als initialisiert (sonst snapt der erste
    // updateMovableSprite-Call die Pos auf das Tile-Center) und lassen
    // den Tween weg. Andere Spieler bekommen smooth Tile-Interpolation.
    const meId = this.bridge.state.player()?.player_id;
    if (meId !== undefined && String(meId) === String(p.player_id)) {
      (obj as Phaser.GameObjects.GameObject & { __posInit?: boolean }).__posInit = true;
    } else {
      this.updateMovableSprite(obj, p.x, p.y, /*smooth*/ true);
    }
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
    let obj: Phaser.GameObjects.GameObject;
    if (animKind) {
      // (a) Animierter NPC-Walk-Cycle (4-direktional) bleibt EAGER.
      obj = this.animatedSpriteOrFallback(tex, animKind, FALLBACK_COLORS.npc, TILE_SIZE);
    } else if (ANIMATED_MONSTER_WALK_SET.has(n.kind)) {
      // (c) Animiertes Monster (Legacy-33-Walk, 8 Frames, nicht-direktional).
      // Frames werden on-demand geladen + Anim erst nach `complete` gebaut.
      obj = this.createMonsterWalkSprite(n.kind);
    } else {
      // (b) Nicht-animierter Pfad: Monster-/NPC-Single-Sprite on-demand laden.
      this.assetLoader.ensureSingle(this, n.kind);
      if (n.sprite_variant) this.assetLoader.ensureSingle(this, n.sprite_variant);
      obj = this.spriteOrFallback(tex, FALLBACK_COLORS.npc, TILE_SIZE);
    }
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth = DEPTH.NPCS;
    return obj;
  }

  private updateNpcSprite(obj: Phaser.GameObjects.GameObject, n: NPC): void {
    this.updateMovableSprite(obj, n.x, n.y, /*smooth*/ true);
    const animKind = this.npcAnimKind(n);
    if (animKind) {
      this.handleWalkAnim(obj, this.npcTracks, n.id, animKind, n.x, n.y);
    } else if (ANIMATED_MONSTER_WALK_SET.has(n.kind)) {
      this.handleMonsterWalkAnim(obj, n.id, n.kind, n.x, n.y);
    } else {
      // Nicht-animierter Pfad: Fallback-Textur auf das (ggf. nachgeladene)
      // echte Single-Sprite swappen, sobald verfügbar.
      this.trySwapFallbackTexture(obj);
    }
  }

  /**
   * (c) Erzeugt das Sprite fuer ein animiertes Legacy-33-Monster. Wir legen es
   * direkt als `Phaser.GameObjects.Sprite` an (nicht Image), damit die spaeter
   * gebaute Walk-Anim ohne Re-Texturieren greifen kann. Solange die 8 Frames
   * noch laden:
   *   • erstes Walk-Frame vorhanden → als Standbild (idle = walk_01),
   *   • sonst Single-Sprite (legacy_33 96px) on-demand laden + als Platzhalter,
   *   • sonst Fallback-Farbtextur.
   * In allen Faellen greift die Anim, sobald `ensureMonsterWalk` `complete` ist.
   */
  private createMonsterWalkSprite(kind: string): Phaser.GameObjects.GameObject {
    // 8 Walk-Frames on-demand laden + Anim nach `complete` bauen.
    this.assetLoader.ensureMonsterWalk(this, kind);

    const frame0 = this.assetLoader.monsterWalkTextureKey(kind, 1);
    let startTex: string;
    if (this.textures.exists(frame0)) {
      startTex = frame0;
    } else {
      // Single-Sprite als Platzhalter, bis die Walk-Frames da sind.
      this.assetLoader.ensureSingle(this, kind);
      const single = this.assetLoader.textureKeyFor(kind) ?? `npc_${kind}`;
      startTex = this.textures.exists(single)
        ? single
        : this.fallbackTextureKey(FALLBACK_COLORS.npc);
    }
    const sprite = this.add.sprite(0, 0, startTex);
    sprite.setDisplaySize(TILE_SIZE, TILE_SIZE);
    return sprite;
  }

  /**
   * (c) Bewegungs-getriebenes Abspielen des Monster-Walk-Loops. Analog zu
   * `handleWalkAnim`, aber nicht-direktional: bei Tile-Delta ≠ 0 spielt die
   * Anim, bei Stillstand frieren wir sie auf dem ersten Frame ein (idle =
   * walk_01). Horizontaler Flip je nach dx-Richtung (Frames schauen fix in
   * eine Richtung). Idle-Handling liegt bewusst HIER drin (nicht im globalen
   * update()-Loop), da `npcAnimKind` Monster nicht kennt.
   */
  private handleMonsterWalkAnim(
    obj: Phaser.GameObjects.GameObject,
    id: string | number,
    kind: string,
    x: number,
    y: number,
  ): void {
    const sprite = obj as Phaser.GameObjects.GameObject & {
      anims?: Phaser.Animations.AnimationState;
      setFlipX?: (flip: boolean) => void;
      setTexture?: (key: string) => void;
      setDisplaySize?: (w: number, h: number) => void;
      texture?: Phaser.Textures.Texture;
    };
    if (!sprite.anims) return; // Fallback-Rect → keine Anim

    const animKey = this.assetLoader.monsterWalkAnimKey(kind);
    const ready = this.assetLoader.monsterWalkReady(kind) && this.anims.exists(animKey);

    // Bewegung gegen den Tracker bestimmen (eigene Map, gleiche Semantik wie
    // handleWalkAnim — wird via onRemove mit dem Pool aufgeraeumt).
    const prev = this.npcTracks.get(id);
    let moving = false;
    if (!prev) {
      this.npcTracks.set(id, { x, y, dir: 'down', lastMoveFrame: this.game.loop.frame });
    } else {
      const dx = x - prev.x;
      const dy = y - prev.y;
      if (dx !== 0 || dy !== 0) {
        moving = true;
        if (dx !== 0) sprite.setFlipX?.(dx < 0); // Frames schauen nach rechts
        prev.x = x;
        prev.y = y;
        prev.lastMoveFrame = this.game.loop.frame;
      }
    }

    if (!ready) {
      // Anim noch nicht fertig: sobald das erste Walk-Frame existiert, als
      // Standbild zeigen (Platzhalter/Single-Sprite ersetzen) — kein Magenta.
      const frame0 = this.assetLoader.monsterWalkTextureKey(kind, 1);
      if (this.textures.exists(frame0) && sprite.texture?.key !== frame0) {
        sprite.setTexture?.(frame0);
        sprite.setDisplaySize?.(TILE_SIZE, TILE_SIZE);
      }
      return;
    }

    if (moving) {
      sprite.anims.play(animKey, true); // ignoreIfPlaying → kein Restart
    } else {
      // Stillstand: Anim auf erstem Frame einfrieren (idle = walk_01).
      if (sprite.anims.isPlaying) {
        sprite.anims.stop();
        sprite.setTexture?.(this.assetLoader.monsterWalkTextureKey(kind, 1));
        sprite.setDisplaySize?.(TILE_SIZE, TILE_SIZE);
      }
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
    // On-Demand: Struktur-Single-Sprite (inkl. Wall-Variant-Key) laden.
    this.assetLoader.ensureSingle(this, key);
    const tex = this.assetLoader.textureKeyFor(key) ?? `struct_${key}`;
    const obj = this.spriteOrFallback(tex, FALLBACK_COLORS.structure, TILE_SIZE);
    // floor-Layer rendert UNTER dem object-Layer (Wände/Möbel/Items darüber).
    (obj as Phaser.GameObjects.GameObject & { depth: number }).depth =
      s.type === 'floor' ? DEPTH.FLOOR : DEPTH.STRUCTURES;
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
    // Wände/Türen an die AUSSENKANTE ihres Tiles versetzen (siehe Helper).
    this.applyWallEdgeOffset(obj, s);
    // Textur für den AKTUELLEN Typ/Variante neu auflösen. Deckt zwei Fälle ab:
    //   • Tür-Toggle (door_wood → door_wood_open): `structure_replaced` ersetzt
    //     die Struktur bei gleicher id → Pool ruft update() → hier muss der
    //     Sprite auf das neue Sprite wechseln (sonst bleibt die Tür optisch zu).
    //   • Wall/Fence-Re-Tiling: Variant-Key ändert sich, wenn nebenan platziert
    //     wird (structureSpriteKeyFor berechnet die Bitmask).
    const key = this.structureSpriteKeyFor(s);
    this.swapStructureTexture(obj, key);
    // Wände/Türen etwas größer rendern, damit die zentrierten Streifen an
    // Ecken/Nähten überlappen und keine Lücken bleiben (nach swapStructureTexture,
    // da setTexture die DisplaySize zurücksetzt).
    if (s.type === 'wall' || isDoorType(s.type)) {
      const sz = TILE_SIZE * WALL_RENDER_SCALE;
      const o = obj as Phaser.GameObjects.GameObject & {
        setDisplaySize?: (w: number, h: number) => void;
        setAngle?: (deg: number) => void;
      };
      o.setDisplaySize?.(sz, sz);
      // Tür-Orientierung: Tür-Assets sind für horizontale Wände (N/S) gezeichnet.
      // In einer VERTIKALEN Wand (E/W) muss die Tür um 90° gedreht werden. Eine
      // vertikale Wand erkennt man daran, dass die Gebäude-Außenseite LINKS oder
      // RECHTS liegt (dort fehlt eine Struktur → null), die Wand-Linie also oben/
      // unten weiterläuft.
      if (isDoorType(s.type)) {
        const lk = this.structureLookup;
        const verticalWall = !lk(s.x - 1, s.y) || !lk(s.x + 1, s.y);
        o.setAngle?.(verticalWall ? 90 : 0);
      }
    }
  }

  /**
   * Verschiebt Wand-/Tür-Sprites um einen festen Betrag zur GEBÄUDE-AUSSENSEITE,
   * sodass der zentrierte Wand-Streifen an der Außenkante seines Tiles sitzt.
   * Damit deckt die Wand den äußeren Teil des Boden-Tiles ab (kein Boden-Überstand
   * nach außen) und schließt innen bündig an den Boden an (keine Gras-Lücke).
   *
   * Außenseite = orthogonaler Nachbar OHNE Struktur (außerhalb des Gebäude-
   * Footprints; Innenseite hat Boden/Objekt). Ecken → diagonaler Versatz.
   */
  private applyWallEdgeOffset(obj: Phaser.GameObjects.GameObject, s: Structure): void {
    if (s.type !== 'wall' && !isDoorType(s.type)) return;
    const lk = this.structureLookup;
    const SH = TILE_SIZE * WALL_EDGE_SHIFT;
    let ox = 0;
    let oy = 0;
    if (!lk(s.x - 1, s.y)) ox -= SH; // außen links  → nach links
    if (!lk(s.x + 1, s.y)) ox += SH; // außen rechts → nach rechts
    if (!lk(s.x, s.y - 1)) oy -= SH; // außen oben   → nach oben
    if (!lk(s.x, s.y + 1)) oy += SH; // außen unten  → nach unten
    if (ox === 0 && oy === 0) return;
    const t = obj as Phaser.GameObjects.GameObject & { x: number; y: number };
    t.x += ox;
    t.y += oy;
  }

  /**
   * Setzt die Struktur-Textur auf den zu `key` gehörenden Sprite. Lädt das
   * Asset bei Bedarf on-demand und swappt entweder sofort (schon im Cache)
   * oder beim Lade-Ende. Der `filecomplete`-Listener wird nur EINMAL pro
   * Ziel-Textur registriert (sonst sammelt sich pro Sync-Frame ein Listener).
   */
  private swapStructureTexture(obj: Phaser.GameObjects.GameObject, key: string): void {
    this.assetLoader.ensureSingle(this, key);
    const tex = this.assetLoader.textureKeyFor(key) ?? `struct_${key}`;
    const img = obj as Phaser.GameObjects.GameObject & {
      setTexture?: (key: string) => void;
      setDisplaySize?: (w: number, h: number) => void;
      texture?: Phaser.Textures.Texture;
      __pendingTex?: string;
      __spriteSize?: number;
    };
    if (typeof img.setTexture !== 'function') return; // (sollte nie: Fallback ist Image)
    if (this.textures.exists(tex)) {
      if (img.texture?.key !== tex) {
        img.setTexture(tex);
        const size = img.__spriteSize ?? TILE_SIZE;
        img.setDisplaySize?.(size, size);
      }
      img.__pendingTex = undefined;
      return;
    }
    // Ziel-Asset noch im Flug: beim Lade-Ende swappen. Nur registrieren, wenn
    // sich das Ziel geändert hat (verhindert Listener-Akkumulation pro Frame).
    if (img.__pendingTex !== tex) {
      img.__pendingTex = tex;
      this.load.once(
        `filecomplete-image-${tex}`,
        () => this.trySwapFallbackTexture(obj),
      );
    }
  }

  /**
   * Ermittelt den STRUCTURE_SPRITES-Schluessel fuer eine Strukur. Fuer
   * Wall/Fence wird die 4-Nachbarn-Bitmask berechnet und ueber
   * WALL_MASK_TO_VARIANT auf eine Variante gemappt (z. B.
   * `wall_stone_corner_ne`). Fuer alle anderen Typen: einfach `s.type`.
   */
  /**
   * Tile-ID des Boden-Tiles unter dem eigenen Spieler — Quelle für das
   * Biom-Ambient-Overlay. Liefert `null`, wenn kein Spieler / kein geladener
   * Chunk / Dungeon (dort gibt es keinen Overworld-Biom-Tile). Eigener
   * Chunk-Lookup (parallel zu `isTileWalkable`, ohne dessen Movement-Pfad
   * anzufassen).
   */
  private currentBiomeTileId(): number | null {
    if (this.bridge.state.dungeonFloor()) return null;
    const me = this.bridge.state.player();
    if (!me) return null;
    const chunks = this.bridge.state.chunks();
    const cx = Math.floor(me.x / this.chunkSize);
    const cy = Math.floor(me.y / this.chunkSize);
    const chunk = chunks.find((c) => c.cx === cx && c.cy === cy);
    if (!chunk) return null;
    const row = chunk.tiles[me.y - cy * this.chunkSize];
    if (!row) return null;
    return row[me.x - cx * this.chunkSize] ?? null;
  }

  private structureSpriteKeyFor(s: Structure): string {
    // Boden: material-spezifisches, NAHTLOSES Tile (floor_wood/stone/straw)
    // statt structures/floor.png (das hatte einen transparenten Rand → Lücken).
    if (s.type === 'floor') {
      const mat = s.material ?? 'wood';
      const key = `floor_${mat}`;
      // Defensiv: nur bekannte Materialien; sonst Holz als Default.
      return key === 'floor_wood' || key === 'floor_stone' || key === 'floor_straw'
        ? key
        : 'floor_wood';
    }
    const family: WallFamily | null = familyOf(s.type, s.material ?? null);
    if (!family) return s.type;
    const mask = wallMaskFor(s.x, s.y, this.structureLookup, family);
    return wallSpriteKeyFor(family, mask);
  }

  private createGroundItemSprite(g: GroundItem): Phaser.GameObjects.GameObject {
    // F-render-foundation: AssetLoader kennt den Item-Key aus ITEM_SPRITES
    // (Subagent B). Pro-Asset-Pipeline (Quality/Cosmetic-Skin) kommt mit
    // dem Inventar-Panel (F7).
    // On-Demand: Item-Single-Sprite laden, sobald ein GroundItem erscheint.
    this.assetLoader.ensureSingle(this, g.kind);
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
      case 'trap_triggered':
        this.fxTrapTriggered(msg);
        return;
      case 'npc_speech':
        this.fxNpcSpeech(msg);
        return;
      case 'inventory_add':
      case 'item_picked_up':
        this.fxAutoPickup(msg);
        return;
      case 'dungeon_chest_opened':
        this.fxDungeonChestOpened(msg);
        return;
      case 'npc_mood':
        this.fxNpcMood(msg);
        return;
      case 'dungeon_sense':
        this.fxDungeonSense(msg);
        return;
      case 'structure_repaired':
        this.fxStructureRepaired(msg);
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
    // H2.2 — HP-Bar: Backend-Frame trägt frische `hp`/`max_hp`-Werte.
    // Wir bevorzugen die Frame-Werte (sie sind aktueller als der nächste
    // npcsVisible-Snapshot, der erst im Folge-Tick kommt).
    const frameHp = msg['hp'] as number | undefined;
    const frameMaxHp = msg['max_hp'] as number | undefined;
    const hp = frameHp ?? npc.hp;
    const maxHp = frameMaxHp ?? npc.max_hp;
    if (this.mobHpBars && typeof hp === 'number' && typeof maxHp === 'number') {
      this.mobHpBars.noteDamage(npcId, hp, maxHp, npc.x, npc.y);
    }
  }

  private fxNpcDied(msg: ServerMessage): void {
    const npcId = msg['npc_id'] as number | undefined;
    if (npcId == null) return;
    // H2.2 — HP-Bar mit-aufräumen (Sprite-Pool gibt kein Death-Event raus).
    this.mobHpBars?.removeFor(npcId);
    // H2.11 — Sprechblase mit-aufräumen.
    this.speechBubbles?.removeFor(npcId);
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

  /**
   * H2.1 — Trap-Triggered. Backend feuert `{type:'trap_triggered', x, y,
   * kind, dmg, text}` an den Spieler selbst (Dungeon-Falle ausgelöst).
   * Kind-spezifischer FX:
   *   • spike_trap   → hit_spark (rote Spitze)
   *   • poison_trap  → poison_cloud (grüne Wolke)
   *   • fire_trap    → fireball_explosion (Multi-Frame-Anim falls registriert)
   *   • frost_trap   → frost_impact / hit_spark-Fallback
   *   • dart_trap    → hit_spark
   *   • rockfall_trap→ hit_spark
   * Außerdem: Toast mit Trap-Label + Damage (Backend liefert `text`).
   */
  private fxTrapTriggered(msg: ServerMessage): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    const kind = (msg['kind'] as string | undefined) ?? 'spike_trap';
    const dmg = msg['dmg'] as number | undefined;
    const text = msg['text'] as string | undefined;
    if (x == null || y == null) return;
    const fxKind = TRAP_FX_KIND[kind] ?? 'hit_spark';
    VISUAL_EFFECTS.spawn(this, { kind: fxKind, x, y });
    // Zusätzlich ein roter Damage-Float am Spieler-Tile-Center, damit der
    // Spieler den HP-Verlust sofort sieht (analog `fxPlayerDamaged`).
    if (dmg != null && dmg > 0) {
      const center = COMBAT_FX.tileCenter(x, y);
      COMBAT_FX.spawnFloatingNumber(this, {
        x: center.x,
        y: center.y,
        text: `-${dmg}`,
        kind: 'phys',
      });
    }
    // Toast — bevorzugt den Backend-Text (enthält Emoji + Beschreibung),
    // hängen den Schaden an, falls vorhanden.
    const toastText = text
      ? (dmg != null && dmg > 0 ? `${text} (-${dmg})` : text)
      : `⚠ Falle ausgelöst${dmg != null && dmg > 0 ? ` (-${dmg})` : ''}`;
    this.bridge.showToast(toastText, 'warn', 5000);
  }

  /**
   * H2.11 — NPC-Sprechblase. Backend feuert `{type:'npc_speech', npc_id,
   * text, delay_ms?}` aus dem npc_chatter-Worker. Bubble bleibt 8 s
   * sichtbar, dann fade.
   */
  private fxNpcSpeech(msg: ServerMessage): void {
    const npcId = msg['npc_id'] as number | undefined;
    const text = msg['text'] as string | undefined;
    if (npcId == null || !text) return;
    const delayMs = (msg['delay_ms'] as number | undefined) ?? 0;
    this.speechBubbles?.show(npcId, text, delayMs);
  }

  /**
   * H2.5 — Auto-Pickup-Floating-Text. Bei `inventory_add` ODER
   * `item_picked_up` (während Bewegung) zeigen wir einen kurzen `+N kind`-
   * Float am Spieler. Wir hören auf BEIDE Frames, weil `item_picked_up`
   * Broadcast ist (auch andere Spieler) — wir filtern auf den eigenen
   * Player. `inventory_add` ist Self-only, also immer erlaubt.
   */
  private fxAutoPickup(msg: ServerMessage): void {
    const me = this.bridge.state.player();
    if (!me) return;
    // item_picked_up ist Broadcast → nur reagieren wenn `by === own player`.
    if (msg.type === 'item_picked_up') {
      const by = msg['by'] as number | string | undefined;
      if (by != null && String(by) !== String(me.player_id)) return;
    }
    // Text-Bestimmung: bevorzugt `item.name` / `item.kind` / `item.quantity`.
    const item = msg['item'] as {
      readonly kind?: string; readonly name?: string; readonly quantity?: number;
    } | undefined;
    let label = 'Item';
    let qty = 1;
    if (item) {
      label = item.name ?? item.kind ?? 'Item';
      qty = item.quantity ?? 1;
    } else {
      // `item_picked_up` ohne `item`-Feld? Backend sendet `kind` separat
      // (Welle 25 Audit hat das beobachtet). Defensiv fallen wir auf
      // generisches "+1" zurück.
      const kind = msg['kind'] as string | undefined;
      if (kind) label = kind;
    }
    const center = COMBAT_FX.tileCenter(me.x, me.y);
    COMBAT_FX.spawnFloatingNumber(this, {
      x: center.x,
      // Etwas höher als Damage-Floats, damit beide nebeneinander lesbar bleiben.
      y: center.y - 18,
      text: `+${qty} ${label}`,
      kind: 'heal',
    });
    // Sound-Hook (TODO H4): noch nicht implementiert, nur Log.
    // eslint-disable-next-line no-console
    console.log('[pickup-sfx]', label, qty);
  }

  /**
   * H2.14 — Dungeon-Chest-Sprite-Swap. State-Service hat den `opened`-Flag
   * bereits gepatcht (siehe `_handleDungeonChestOpened`), aber der
   * DungeonRenderer rendert die Floor-Features nur bei `show()`/`swap()`
   * neu — nicht bei jedem Tick. Wir triggern den Swap explizit über den
   * `markChestOpened`-Hook am Renderer.
   */
  private fxDungeonChestOpened(msg: ServerMessage): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (x == null || y == null) return;
    this.dungeonRenderer?.markChestOpened(x, y);
  }

  /**
   * H3.6 — NPC-Mood. Backend feuert `npc_mood {npc_id, mood_value,
   * mental_state}` aus dem `npc_mood`-Worker bei jedem State-Wechsel.
   * Wir rendern Emoji nur für abnormale Zustände (sad/fleeing/berserk);
   * `normal` entfernt das Icon (siehe ai_fragen.md H3.6).
   */
  private fxNpcMood(msg: ServerMessage): void {
    if (!this.moodIcons) return;
    const npcId = msg['npc_id'] as number | undefined;
    const mentalState = msg['mental_state'] as string | undefined;
    if (npcId == null || !mentalState) return;
    this.moodIcons.setMood(npcId, mentalState);
  }

  /**
   * H3.10 — Sense-Pulse. Backend feuert `dungeon_sense {dungeons:[...]}`
   * bei Sense-Item-Nutzung (oder Reaper-Refresh). Wir spawnen einen
   * Pulse-Ring am Player-Tile mit Default-Radius 70 Tiles. Liste der
   * Dungeons wird ignoriert für das Visual (Minimap konsumiert sie
   * separat über das `dungeonSensePulse`-Signal).
   */
  private fxDungeonSense(msg: ServerMessage): void {
    if (!this.sensePulse) return;
    const me = this.bridge.state.player();
    if (!me) return;
    const dungeons = msg['dungeons'] as readonly { readonly radius?: number }[] | undefined;
    this.sensePulse.pulseFromEvent(me.x, me.y, dungeons);
  }

  /**
   * H3.12 — Repair-Heal-Pulse. Backend feuert `structure_repaired
   * {x, y, durability, max_durability, by}` nach erfolgreicher Reparatur.
   * Visual: grüner Pulse-Ring an der Struktur, expandiert und faded
   * innerhalb ~600 ms. Inline-FX analog `fxStructureRemoved` (siehe
   * ai_fragen.md H3.12).
   */
  private fxStructureRepaired(msg: ServerMessage): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (x == null || y == null) return;
    const center = COMBAT_FX.tileCenter(x, y);
    const ring = this.add.circle(center.x, center.y, 6, 0x55ee66, 0);
    ring.setStrokeStyle(3, 0x55ee66, 0.85);
    ring.setDepth(60);
    this.tweens.add({
      targets: ring,
      radius: 28,
      duration: 600,
      ease: 'Cubic.easeOut',
      onUpdate: () => {
        // Phaser-Arc-Radius-Update sicherstellen.
        const r = ring as Phaser.GameObjects.Arc & {
          setRadius?: (radius: number) => void;
        };
        if (typeof r.setRadius === 'function') r.setRadius(ring.radius);
      },
    });
    this.tweens.add({
      targets: ring,
      alpha: 0,
      duration: 600,
      ease: 'Sine.easeOut',
      onComplete: () => ring.destroy(),
    });
    // Zusätzlich kleiner grüner Heal-Float (analog player_healed).
    COMBAT_FX.spawnFloatingNumber(this, {
      x: center.x,
      y: center.y - 8,
      text: '+repair',
      kind: 'heal',
    });
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

/**
 * H1.12 — Tür-Erkennung für Click-Routing. Backend-Strukturtypen:
 *   door_wood, door_iron, door_stone, door_reinforced,
 *   door_wood_open, door_iron_open, door_stone_open,
 *   garden_gate_ew_closed, garden_gate_ew_open,
 *   garden_gate_ns_closed, garden_gate_ns_open,
 *   fence_gate_farm
 * Alles davon wird per `toggle_door {x, y}` umgeschaltet. Backend antwortet
 * mit `structure_replaced` (Sprite-Swap).
 */
function isDoorType(type: string): boolean {
  if (type.startsWith('door_')) return true;
  if (type.startsWith('garden_gate_')) return true;
  if (type === 'fence_gate_farm') return true;
  return false;
}

/**
 * H2.1 — Trap-Kind → visual_effect-Kind. Wenn ein registriertes Multi-Frame-
 * FX existiert (z. B. `fireball_explosion`), bevorzugen wir das. Sonst
 * fällt der `VISUAL_EFFECTS.spawn`-Dispatcher auf den generischen
 * Sprite-Fade zurück (siehe visual-effects.ts::spawnGeneric).
 */
const TRAP_FX_KIND: Readonly<Record<string, string>> = {
  spike_trap: 'hit_spark',
  dart_trap: 'hit_spark',
  rockfall_trap: 'hit_spark',
  poison_trap: 'poison_cloud',
  fire_trap: 'fireball_explosion',
  frost_trap: 'frost_impact',
};
