// AssetLoaderService — zentrale Sprite-Registry für die Phaser-Scene.
//
// F-render-foundation (2026-05-30):
// Dieser Service hält die statischen Sprite-Manifests (NPC-Walks, Player-
// Presets, Monster-/Struktur-/Item-/Effect-PNGs) und füttert sie zum
// Phaser-Boot-Zeitpunkt in den `Phaser.Loader.LoaderPlugin`. Das löst das
// Foundation-Problem aus REFACTOR_NOTES §20 (Tile-Layer rendert, aber alle
// Mob-/Player-Sprites werden als Magenta-Fallback gerendert).
//
// Architektur-Idee: pro Sprite-Kind (NPC, Monster, Struktur, …) gibt es
// eine separate, statisch importierte Map<kind, path>. Subagent B liefert
// die `*_SPRITES`-Maps aus `core/data/` parallel — wir importieren defensiv
// (Stubs sind leere Maps, wenn B noch nicht fertig ist).
//
// Was hier NICHT gemacht wird:
//   • Phaser-Animations registrieren (das macht `WalkAnimationsService`,
//     der nach `preload()` läuft und die geladenen Frames in
//     `scene.anims.create(...)` einträgt).
//   • Sprite-Instances erzeugen (das macht `WorldScene` über die
//     `SpritePool`s).

import { Injectable } from '@angular/core';
import Phaser from 'phaser';

import {
  ANIMATED_NPC_KINDS,
  NPC_SPRITE,
  PRESET_WALK_CFG,
} from '../core/data/npc-sprites';
import {
  ANIMATED_MONSTER_WALK_SET,
  MONSTER_SPRITES,
  MONSTER_WALK_ASSET_BASE,
  MONSTER_WALK_FRAME_COUNT,
} from '../core/data/monster-sprites';
import { STRUCTURE_SPRITES } from '../core/data/structure-sprites';
import { ITEM_SPRITES } from '../core/data/item-sprites';
import {
  DUNGEON_FEATURE_ASSETS,
  DUNGEON_TILE_ASSETS,
} from '../core/data/dungeon-tiles';
import {
  DISASTER_LAYERS,
  EFFECT_ANIMATIONS,
  EFFECT_SPRITES,
  type DisasterLayerSpec,
  type EffectAnimationSpec,
} from '../core/data/effect-sprites';

/** Walk-Cycle-Frame-Set für ein Kind (NPC oder Player-Preset). */
export interface WalkCycleSpec {
  /** Phaser-Texture-Key-Präfix. Tatsächlicher Key pro Frame:
   *  `<keyPrefix>__<direction>_<n>` (z. B. `npc_walk_guard__down_1`). */
  readonly keyPrefix: string;
  /** Base-URL ohne trailing slash, z. B.
   *  `/assets/animations/characters/guard` */
  readonly baseUrl: string;
  /** Anzahl Frames pro Richtung (typisch 2 für die phase2-Packs). */
  readonly framesPerDirection: number;
  /** Ob es auch `idle_<n>.png`-Frames gibt. */
  readonly hasIdle: boolean;
}

/** Direction-Liste. Wird auch vom WalkAnimationsService konsumiert. */
export const WALK_DIRECTIONS = ['down', 'up', 'left', 'right'] as const;
export type WalkDirection = (typeof WALK_DIRECTIONS)[number];

/** Default-Frame-Count für die phase2/3/preset-Packs (2 Frames pro Richtung). */
const DEFAULT_FRAMES_PER_DIR = 2;

/** Frame-Rate der Legacy-33-Monster-Walk-Loops (8 Frames; ~9 FPS = ruhiger,
 *  fluessiger Gang ohne zu hektisch zu wirken). */
const MONSTER_WALK_FRAME_RATE = 9;

/** Default-Player-Preset-Key wenn `player.preset` null/leer. */
const DEFAULT_PLAYER_PRESET = 'wanderer_cloak';

@Injectable({ providedIn: 'root' })
export class AssetLoaderService {
  /** kind → Single-Image-Path (für statische Sprites). */
  private readonly singleSprites = new Map<string, string>();

  /** kind → Texture-Key (gleicher Wert wie der Map-Key in singleSprites,
   *  separat damit `textureKeyFor` schnell ist). */
  private readonly kindToTextureKey = new Map<string, string>();

  /**
   * On-Demand-Single-Sprites (Monster / Item / Struktur): diese kinds werden
   * NICHT mehr eager im `preloadAll` geladen, sondern erst wenn ein Entity
   * dieses Kinds in Sichtweite kommt (`ensureSingle`). Spart ~825 HTTP-
   * Requests + GPU-Texturen beim Boot (GPU-Constraint RTX 3070 8GB).
   *
   * Wert ist das `[textureKey, path]`-Paar, damit `ensureSingle` ohne
   * weitere Map-Lookups arbeiten kann.
   */
  private readonly onDemandSingles = new Map<string, readonly [string, string]>();

  /** Texture-Keys, die per `ensureSingle` bereits in den Loader eingereiht
   *  wurden — verhindert Doppel-Requests. */
  private readonly requestedSingles = new Set<string>();

  /** Monster-Walk-Kinds, deren 8 Frames bereits per `ensureMonsterWalk` in
   *  den Loader eingereiht wurden (idempotent, verhindert Doppel-Requests). */
  private readonly requestedMonsterWalks = new Set<string>();

  /** Monster-Walk-Kinds, deren Phaser-Walk-Anim bereits gebaut wurde. */
  private readonly builtMonsterWalks = new Set<string>();

  /** Walk-Cycles pro Kind (NPC, Player-Preset). */
  private readonly walkCycles = new Map<string, WalkCycleSpec>();

  /** Effect-Multi-Frame-Anims (G4): kind → spec. Pro Spec gibt es ein
   *  Texture pro Frame mit Key `effect_anim_<kind>_<NN>`. */
  private readonly effectAnims = new Map<string, EffectAnimationSpec>();

  /** Disaster-Layer-Anims (G4): layer-key → spec. Texture-Keys
   *  `disaster_anim_<layer>_<NN>`. */
  private readonly disasterLayers = new Map<string, DisasterLayerSpec>();

  constructor() {
    this.loadStaticManifests();
    this.loadNpcWalkCycles();
    this.loadPlayerPresetWalkCycles();
    this.loadEffectAnimations();
    this.loadDisasterLayers();
  }

  // ─── Public API ─────────────────────────────────────────────────────

  /** Liefert den Phaser-Texture-Key für ein Kind, oder `null` falls keine
   *  statische Registry vorliegt (→ WorldScene fällt auf Magenta-Rect). */
  textureKeyFor(kind: string): string | null {
    return this.kindToTextureKey.get(kind) ?? null;
  }

  /**
   * On-Demand-Load eines Single-Sprites (Monster / Item / Struktur). Wird von
   * den `create*`-Sprite-Factories in `WorldScene` pro neuem Entity gerufen —
   * muss also idempotent + billig sein.
   *
   * Lädt die Textur für `kind` nur dann, wenn:
   *   • `kind` als On-Demand-Single registriert ist (sonst no-op — Walk-Cycle-
   *     Kinds & Eager-Core liefen schon durch `preloadAll`),
   *   • die Textur noch nicht im TextureManager existiert,
   *   • und noch nicht angefordert wurde (`requestedSingles`-Guard).
   *
   * Phaser erlaubt `load.image(...)` + `load.start()` zur Laufzeit; läuft
   * gerade ein Load, wird der neue Eintrag in dieselbe Queue gehängt.
   * `WorldScene` swappt die Fallback-Textur via `load.on('filecomplete', …)`
   * bzw. beim nächsten `update*`-Sync auf das fertige Image.
   */
  ensureSingle(scene: Phaser.Scene, kind: string): void {
    const entry = this.onDemandSingles.get(kind);
    if (!entry) return;
    const [key, path] = entry;
    if (this.requestedSingles.has(key)) return;
    if (scene.textures.exists(key)) {
      this.requestedSingles.add(key);
      return;
    }
    this.requestedSingles.add(key);
    scene.load.image(key, path);
    // `start()` ist no-op wenn der Loader schon läuft; sonst startet er die
    // (ggf. wachsende) Queue. Mehrfaches Aufrufen ist von Phaser abgesichert.
    if (!scene.load.isLoading()) {
      scene.load.start();
    }
  }

  /**
   * On-Demand-Loader + Anim-Build fuer einen Legacy-33-Monster-Walk-Cycle
   * (8 nicht-direktionale Frames). Analog zu `BiomeAmbient.ensureFrames`:
   *
   *   • NICHTS wird eager beim Boot geladen (32×8 = 256 Frames wuerden den
   *     Boot-Lag wieder einfuehren, GPU-Constraint RTX 3070 8GB).
   *   • Erst wenn ein Monster dieses Kinds erscheint, werden die 8 Frames in
   *     den Loader eingereiht; die Phaser-Anim `monster_walk_<kind>` wird erst
   *     nach `complete` gebaut (Frames muessen im TextureManager existieren).
   *
   * Idempotent: Mehrfach-Aufrufe pro Kind sind ein No-op. Liefert sofort, wenn
   * `kind` kein animiertes Monster ist.
   *
   * Hier in `AssetLoaderService`, weil dieser Service bereits das gesamte
   * On-Demand-Asset-Lifecycle besitzt (`ensureSingle`) UND die Walk-Cycle-
   * Anim-Specs haelt — der `WalkAnimationsService` baut dagegen nur EAGER aus
   * bereits vorgeladenen Texturen und passt fuer den Lazy-Pfad nicht.
   */
  ensureMonsterWalk(scene: Phaser.Scene, kind: string): void {
    if (!ANIMATED_MONSTER_WALK_SET.has(kind)) return;
    if (this.requestedMonsterWalks.has(kind)) {
      // Frames evtl. schon da (z. B. aus dem Cache) → Anim ggf. nachbauen.
      this.buildMonsterWalkAnim(scene, kind);
      return;
    }
    this.requestedMonsterWalks.add(kind);

    let queued = 0;
    for (let n = 1; n <= MONSTER_WALK_FRAME_COUNT; n++) {
      const key = this.monsterWalkTextureKey(kind, n);
      if (scene.textures.exists(key)) continue;
      scene.load.image(
        key,
        `${MONSTER_WALK_ASSET_BASE}/${kind}/walk_${pad2(n)}.png`,
      );
      queued++;
    }

    if (queued === 0) {
      // Alle Frames bereits im Cache → direkt bauen.
      this.buildMonsterWalkAnim(scene, kind);
      return;
    }

    // Nach Abschluss des aktuellen Load-Batches die Anim bauen (idempotent).
    scene.load.once(Phaser.Loader.Events.COMPLETE, () =>
      this.buildMonsterWalkAnim(scene, kind),
    );
    if (!scene.load.isLoading()) scene.load.start();
  }

  /** Texture-Key fuer ein einzelnes Monster-Walk-Frame (1-indexiert). */
  monsterWalkTextureKey(kind: string, n: number): string {
    return `__mwalk_${kind}_${pad2(n)}`;
  }

  /** Anim-Key fuer den Monster-Walk-Loop eines Kinds. */
  monsterWalkAnimKey(kind: string): string {
    return `monster_walk_${kind}`;
  }

  /** True, sobald die Walk-Anim `monster_walk_<kind>` gebaut + abspielbar ist. */
  monsterWalkReady(kind: string): boolean {
    return this.builtMonsterWalks.has(kind);
  }

  /**
   * Baut die Phaser-Anim `monster_walk_<kind>` (8 Frames, repeat -1), sobald
   * alle Frame-Texturen geladen sind. Idempotent.
   */
  private buildMonsterWalkAnim(scene: Phaser.Scene, kind: string): void {
    if (this.builtMonsterWalks.has(kind)) return;

    const frames: Phaser.Types.Animations.AnimationFrame[] = [];
    for (let n = 1; n <= MONSTER_WALK_FRAME_COUNT; n++) {
      const key = this.monsterWalkTextureKey(kind, n);
      if (!scene.textures.exists(key)) return; // noch nicht alle da → spaeter
      frames.push({ key });
    }

    const animKey = this.monsterWalkAnimKey(kind);
    if (!scene.anims.exists(animKey)) {
      scene.anims.create({
        key: animKey,
        frames,
        frameRate: MONSTER_WALK_FRAME_RATE,
        repeat: -1,
      });
    }
    this.builtMonsterWalks.add(kind);
  }

  /** Liefert den Walk-Cycle-Spec für ein Kind. Nutzt der
   *  `WalkAnimationsService` um Phaser-Anims zu definieren. */
  walkCycleFor(kind: string): WalkCycleSpec | null {
    return this.walkCycles.get(kind) ?? null;
  }

  /** Liefert alle registrierten Walk-Cycle-Kinds. */
  allWalkCycleKinds(): readonly string[] {
    return [...this.walkCycles.keys()];
  }

  /** Liefert die Effect-Animation-Spec für ein Kind oder null. */
  effectAnimationFor(kind: string): EffectAnimationSpec | null {
    return this.effectAnims.get(kind) ?? null;
  }

  /** Iterator über alle Effect-Anim-Specs (für die FX-Animations-Registry). */
  allEffectAnimations(): readonly EffectAnimationSpec[] {
    return [...this.effectAnims.values()];
  }

  /** Iterator über alle Disaster-Layer-Specs. */
  allDisasterLayers(): readonly DisasterLayerSpec[] {
    return [...this.disasterLayers.values()];
  }

  /** Liefert die Disaster-Layer-Specs für einen Disaster-Kind. */
  disasterLayersFor(kind: string): readonly DisasterLayerSpec[] {
    const layers = DISASTER_LAYERS[kind];
    return layers ?? [];
  }

  /** Texture-Key-Konvention für Effect-Anim-Frame. */
  effectFrameKey(kind: string, frameIdx1: number): string {
    return `effect_anim_${kind}_${pad2(frameIdx1)}`;
  }

  /** Texture-Key-Konvention für Disaster-Layer-Frame. */
  disasterFrameKey(layerKey: string, frameIdx1: number): string {
    return `disaster_anim_${layerKey}_${pad2(frameIdx1)}`;
  }

  /** Resolved den effektiven Player-Preset-Key (Default wenn null/leer). */
  resolvePlayerPreset(preset: string | null | undefined): string {
    if (!preset) return DEFAULT_PLAYER_PRESET;
    return this.walkCycles.has(preset) ? preset : DEFAULT_PLAYER_PRESET;
  }

  /**
   * Füttert alle registrierten Assets in den Phaser-Loader. Wird vom
   * `WorldScene.preload()` einmalig aufgerufen.
   *
   * Defensive: 404er (z. B. fehlende Walk-Frames) loggt Phaser als Warning;
   * die `WorldScene.spriteOrFallback()`-Logik prüft danach
   * `scene.textures.exists(key)` und fällt auf das Magenta-Rect zurück.
   */
  preloadAll(loader: Phaser.Loader.LoaderPlugin): void {
    // 1) Single-Sprites — EAGER-Core: NPC-Idle, Player-Presets, Dungeon-Tiles,
    //    Effekt-Singles. Monster/Item/Struktur-Singles (`onDemandSingles`)
    //    werden HIER übersprungen und erst per `ensureSingle()` geladen, sobald
    //    ein Entity dieses Kinds erscheint — spart ~825 Boot-Requests/Texturen.
    for (const [kind, path] of this.singleSprites) {
      if (this.onDemandSingles.has(kind)) continue;
      const key = this.kindToTextureKey.get(kind);
      if (!key) continue;
      // Phaser ist tolerant: wenn der Key schon im TextureManager ist,
      // wird der Reload übersprungen. Schützt vor Doppel-Boot in HMR.
      if (!loader.textureManager.exists(key)) {
        loader.image(key, path);
      }
    }

    // 2) Walk-Cycles (NPCs + Player-Presets): pro Richtung pro Frame.
    for (const [, spec] of this.walkCycles) {
      this.preloadWalkCycle(loader, spec);
    }

    // 3) Effect-Multi-Frame-Anims (G4).
    for (const [, spec] of this.effectAnims) {
      this.preloadEffectAnim(loader, spec);
    }

    // 4) Disaster-Layer-Anims (G4).
    for (const [, spec] of this.disasterLayers) {
      this.preloadDisasterLayer(loader, spec);
    }
  }

  // ─── Private: Registry-Loaders ──────────────────────────────────────

  /**
   * Importiert die statischen `*_SPRITES`-Maps aus `core/data/`. Wenn
   * Subagent B noch keine Einträge eingetragen hat, sind die Maps leer
   * und nichts wird registriert — das ist OK, der Fallback greift.
   */
  private loadStaticManifests(): void {
    // Monster: key = kind (NPC_SPRITE.sprite-Konvention).
    // On-Demand: erst laden wenn ein Monster dieses Kinds erscheint.
    for (const [kind, path] of Object.entries(MONSTER_SPRITES)) {
      this.registerSingle(kind, kind, path, /*onDemand*/ true);
    }
    // Strukturen: key = `struct_<type>` (siehe WorldScene.createStructureSprite).
    // On-Demand.
    for (const [type, path] of Object.entries(STRUCTURE_SPRITES)) {
      this.registerSingle(type, `struct_${type}`, path, /*onDemand*/ true);
    }
    // Items: key = `item_<kind>` (siehe WorldScene.createGroundItemSprite).
    // On-Demand.
    for (const [kind, path] of Object.entries(ITEM_SPRITES)) {
      this.registerSingle(kind, `item_${kind}`, path, /*onDemand*/ true);
    }
    // Effekte: key = `effect_<kind>` (Convention, wird in einer späteren
    // Welle vom Effect-Renderer konsumiert).
    for (const [kind, path] of Object.entries(EFFECT_SPRITES)) {
      this.registerSingle(kind, `effect_${kind}`, path);
    }
    // Welle H1-A: Dungeon-Tiles + Feature-Sprites. Key === Asset-Manifest-Key
    // (z. B. `dungeon_tile_wall`), Pfad direkt aus dem Manifest.
    for (const [key, path] of Object.entries(DUNGEON_TILE_ASSETS)) {
      this.registerSingle(key, key, path);
    }
    for (const [key, path] of Object.entries(DUNGEON_FEATURE_ASSETS)) {
      this.registerSingle(key, key, path);
    }
  }

  /**
   * NPC-Walk-Cycles: für jedes Kind in `ANIMATED_NPC_KINDS` registrieren
   * wir 4 Richtungen × 2 Frames + 2 Idle-Frames (= 10 PNGs pro Kind).
   * Asset-Pfad-Konvention (phase2/3-Packs):
   *   /assets/animations/characters/<kind>/walk_<dir>_<n>.png
   *   /assets/animations/characters/<kind>/idle_<n>.png
   */
  private loadNpcWalkCycles(): void {
    for (const kind of ANIMATED_NPC_KINDS) {
      this.walkCycles.set(kind, {
        keyPrefix: `npc_walk_${kind}`,
        baseUrl: `/assets/animations/characters/${kind}`,
        framesPerDirection: DEFAULT_FRAMES_PER_DIR,
        hasIdle: true,
      });
      // Idle-Frame-1 wird zusätzlich als "Standbild"-Texture für nicht-
      // animierte Render-Pfade registriert — Key folgt der NPC_SPRITE.sprite-
      // Konvention (z. B. `npc_guard`). Damit hat der Pool sofort ein
      // sichtbares Sprite, auch wenn keine Walk-Anim aktiv ist.
      //
      // Welle render-fix (2026-05-31): NICHT mehr `${kind}__idle` als Map-Key
      // verwenden — das war ein toter Eintrag, denn `textureKeyFor(n.kind)`
      // sucht nach `kind`, nicht nach `${kind}__idle`. Stattdessen direkt
      // `kind` als Key registrieren, damit ANIMATED_NPC_KINDS auch im
      // statischen Render-Pfad eine valide Texture haben. Wenn MONSTER_SPRITES
      // einen Eintrag fuer denselben Key hat (z. B. `bandit`), gewinnt der
      // hier (NPC-Idle ist konsistenter mit dem Walk-Cycle als das alte
      // legacy_33 96px-Asset).
      const npcSprite = NPC_SPRITE[kind];
      if (npcSprite) {
        this.registerSingle(
          kind,
          npcSprite.sprite,
          `/assets/animations/characters/${kind}/idle_1.png`,
        );
      }
    }
  }

  /**
   * Player-Preset-Walk-Cycles (6 Presets aus `PRESET_WALK_CFG`).
   * Asset-Pfad: /assets/animations/player_presets/<preset>/walk_<dir>_<n>.png
   *
   * Die Texture-Key-Konvention `player_<preset>_idle` matched mit der
   * bestehenden `createPlayerSprite`-Logik in `world-scene.ts`. Plus eine
   * `player_default`-Fallback-Texture für preset==null.
   */
  private loadPlayerPresetWalkCycles(): void {
    const presets = Object.keys(PRESET_WALK_CFG);
    for (const preset of presets) {
      this.walkCycles.set(preset, {
        keyPrefix: `player_walk_${preset}`,
        baseUrl: `/assets/animations/player_presets/${preset}`,
        framesPerDirection: DEFAULT_FRAMES_PER_DIR,
        hasIdle: true,
      });
      // Single-Idle-Texture für die WorldScene-Fallback-Resolution.
      this.registerSingle(
        `${preset}__idle`,
        `player_${preset}_idle`,
        `/assets/animations/player_presets/${preset}/idle_1.png`,
      );
    }
    // Default-Player-Texture (wenn preset null/leer in `state.player()`).
    this.registerSingle(
      '__player_default__',
      'player_default',
      `/assets/animations/player_presets/${DEFAULT_PLAYER_PRESET}/idle_1.png`,
    );
  }

  /**
   * Registriert alle Multi-Frame-Effect-Anims aus EFFECT_ANIMATIONS.
   * Pro Effect-Kind landet die Spec in `effectAnims`; die einzelnen Frames
   * werden beim Phaser-Preload als `effect_anim_<kind>_<NN>` geladen.
   */
  private loadEffectAnimations(): void {
    for (const [kind, spec] of Object.entries(EFFECT_ANIMATIONS)) {
      this.effectAnims.set(kind, spec);
    }
  }

  /** Registriert alle Disaster-Layer-Anims aus DISASTER_LAYERS. */
  private loadDisasterLayers(): void {
    for (const layers of Object.values(DISASTER_LAYERS)) {
      for (const spec of layers) {
        this.disasterLayers.set(spec.key, spec);
      }
    }
  }

  // ─── Private: Helpers ───────────────────────────────────────────────

  /** Registriert ein Single-Sprite (PNG → Texture).
   *  `onDemand=true`: NICHT eager in `preloadAll` laden, sondern erst per
   *  `ensureSingle` wenn ein Entity dieses Kinds erscheint. */
  private registerSingle(
    kind: string,
    textureKey: string,
    path: string,
    onDemand = false,
  ): void {
    this.singleSprites.set(kind, path);
    this.kindToTextureKey.set(kind, textureKey);
    if (onDemand) {
      this.onDemandSingles.set(kind, [textureKey, path]);
    } else {
      // Eager-Registrierung gewinnt: überschreibt einen früheren on-demand-
      // Eintrag desselben kinds (z. B. animierte NPC-Kinds, die auch in
      // MONSTER_SPRITES stehen — deren Idle-Frame bleibt eager geladen).
      this.onDemandSingles.delete(kind);
    }
  }

  /** Lädt alle Frames einer Effect-Anim (`effect_anim_<kind>_<NN>`). */
  private preloadEffectAnim(
    loader: Phaser.Loader.LoaderPlugin,
    spec: EffectAnimationSpec,
  ): void {
    for (let n = 1; n <= spec.frameCount; n++) {
      const key = this.effectFrameKey(spec.kind, n);
      if (loader.textureManager.exists(key)) continue;
      loader.image(key, `${spec.baseUrl}/${spec.prefix}${pad2(n)}.png`);
    }
  }

  /** Lädt alle Frames einer Disaster-Layer-Anim. */
  private preloadDisasterLayer(
    loader: Phaser.Loader.LoaderPlugin,
    spec: DisasterLayerSpec,
  ): void {
    for (let n = 1; n <= spec.frameCount; n++) {
      const key = this.disasterFrameKey(spec.key, n);
      if (loader.textureManager.exists(key)) continue;
      loader.image(key, `${spec.baseUrl}/${spec.prefix}${pad2(n)}.png`);
    }
  }

  /** Lädt alle Frames eines Walk-Cycles (8 walk + optional 2 idle). */
  private preloadWalkCycle(
    loader: Phaser.Loader.LoaderPlugin,
    spec: WalkCycleSpec,
  ): void {
    for (const dir of WALK_DIRECTIONS) {
      for (let n = 1; n <= spec.framesPerDirection; n++) {
        const key = `${spec.keyPrefix}__${dir}_${n}`;
        if (loader.textureManager.exists(key)) continue;
        loader.image(key, `${spec.baseUrl}/walk_${dir}_${n}.png`);
      }
    }
    if (spec.hasIdle) {
      for (let n = 1; n <= spec.framesPerDirection; n++) {
        const key = `${spec.keyPrefix}__idle_${n}`;
        if (loader.textureManager.exists(key)) continue;
        loader.image(key, `${spec.baseUrl}/idle_${n}.png`);
      }
    }
  }
}

/** Format eine 1-indexierte Zahl als 2-stelligen String (`5` → `05`). */
function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}
