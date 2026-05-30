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
import type Phaser from 'phaser';

import {
  ANIMATED_NPC_KINDS,
  NPC_SPRITE,
  PRESET_WALK_CFG,
} from '../core/data/npc-sprites';
import { MONSTER_SPRITES } from '../core/data/monster-sprites';
import { STRUCTURE_SPRITES } from '../core/data/structure-sprites';
import { ITEM_SPRITES } from '../core/data/item-sprites';
import { EFFECT_SPRITES } from '../core/data/effect-sprites';

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

/** Default-Player-Preset-Key wenn `player.preset` null/leer. */
const DEFAULT_PLAYER_PRESET = 'wanderer_cloak';

@Injectable({ providedIn: 'root' })
export class AssetLoaderService {
  /** kind → Single-Image-Path (für statische Sprites). */
  private readonly singleSprites = new Map<string, string>();

  /** kind → Texture-Key (gleicher Wert wie der Map-Key in singleSprites,
   *  separat damit `textureKeyFor` schnell ist). */
  private readonly kindToTextureKey = new Map<string, string>();

  /** Walk-Cycles pro Kind (NPC, Player-Preset). */
  private readonly walkCycles = new Map<string, WalkCycleSpec>();

  constructor() {
    this.loadStaticManifests();
    this.loadNpcWalkCycles();
    this.loadPlayerPresetWalkCycles();
  }

  // ─── Public API ─────────────────────────────────────────────────────

  /** Liefert den Phaser-Texture-Key für ein Kind, oder `null` falls keine
   *  statische Registry vorliegt (→ WorldScene fällt auf Magenta-Rect). */
  textureKeyFor(kind: string): string | null {
    return this.kindToTextureKey.get(kind) ?? null;
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
    // 1) Single-Sprites (Monster, Strukturen, Items, Effekte).
    for (const [kind, path] of this.singleSprites) {
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
  }

  // ─── Private: Registry-Loaders ──────────────────────────────────────

  /**
   * Importiert die statischen `*_SPRITES`-Maps aus `core/data/`. Wenn
   * Subagent B noch keine Einträge eingetragen hat, sind die Maps leer
   * und nichts wird registriert — das ist OK, der Fallback greift.
   */
  private loadStaticManifests(): void {
    // Monster: key = kind (NPC_SPRITE.sprite-Konvention)
    for (const [kind, path] of Object.entries(MONSTER_SPRITES)) {
      this.registerSingle(kind, kind, path);
    }
    // Strukturen: key = `struct_<type>` (siehe WorldScene.createStructureSprite)
    for (const [type, path] of Object.entries(STRUCTURE_SPRITES)) {
      this.registerSingle(type, `struct_${type}`, path);
    }
    // Items: key = `item_<kind>` (siehe WorldScene.createGroundItemSprite)
    for (const [kind, path] of Object.entries(ITEM_SPRITES)) {
      this.registerSingle(kind, `item_${kind}`, path);
    }
    // Effekte: key = `effect_<kind>` (Convention, wird in einer späteren
    // Welle vom Effect-Renderer konsumiert).
    for (const [kind, path] of Object.entries(EFFECT_SPRITES)) {
      this.registerSingle(kind, `effect_${kind}`, path);
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

  // ─── Private: Helpers ───────────────────────────────────────────────

  /** Registriert ein Single-Sprite (PNG → Texture). */
  private registerSingle(kind: string, textureKey: string, path: string): void {
    this.singleSprites.set(kind, path);
    this.kindToTextureKey.set(kind, textureKey);
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
