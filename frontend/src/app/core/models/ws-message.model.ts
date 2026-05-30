// WS-Message-Diskriminator. Backend sendet pro Frame ein JSON-Objekt mit
// einem `type`-String — alle anderen Felder sind type-abhängig.

import type { Chunk, DungeonMarker, Structure, WorldEvent } from './chunk.model';
import type { Group, GroupInvite } from './group.model';
import type {
  GroundItem,
  InventoryItem,
} from './item.model';
import type { NPC } from './npc.model';
import type {
  OnlinePlayer,
  PlayerAttributes,
  PlayerSnapshot,
  PlayerStats,
  SkillEntry,
  StatusEffect,
} from './player.model';
import type { FactionReputation, Quest } from './quest.model';
import type { SpellEntry, TalentNode } from './talent.model';
import type { TimeSnapshot, WeatherSnapshot } from './time.model';

/**
 * `init`-Snapshot (Server → Client) — der komplette initiale World-State.
 * Wird einmal pro Verbindung gesendet (siehe WS_PROTOCOL.md §Lifecycle).
 */
export interface InitMessage {
  readonly type: 'init';
  readonly player_id: number;
  readonly needs_character_creation: boolean;
  readonly preset: string | null;
  readonly world_seed: number | string;
  readonly chunk_size: number;
  readonly chunks: readonly Chunk[];
  readonly players: Readonly<Record<string, OnlinePlayer>>;
  readonly structures: readonly Structure[];
  readonly dungeons: readonly DungeonMarker[];
  readonly events: readonly WorldEvent[];
  readonly npcs: readonly NPC[];
  readonly items_ground: readonly GroundItem[];
  readonly inventory: readonly InventoryItem[];
  readonly wallet_copper: number;
  readonly spawn: { readonly x: number; readonly y: number };
  readonly hp: number;
  readonly max_hp: number;
  readonly mana: number;
  readonly max_mana: number;
  readonly hunger: number;
  readonly max_hunger: number;
  readonly stamina: number;
  readonly max_stamina: number;
  readonly thirst: number;
  readonly max_thirst: number;
  readonly skills?: Readonly<Record<string, SkillEntry>>;
  readonly body_parts?: PlayerSnapshot['body_parts'];
  readonly research?: unknown;
  readonly time?: TimeSnapshot;
  readonly quests?: readonly Quest[];
  readonly factions?: readonly FactionReputation[];
  readonly attributes?: PlayerAttributes;
  readonly active_disasters?: readonly { readonly kind: string; readonly intensity?: number }[];
  readonly stats?: PlayerStats;
  readonly power_tier?: number;
  /** Backend sendet einen Dict (kind→def) ohne `id`-Feld pro Eintrag. */
  readonly spell_catalog?: Readonly<Record<string, Omit<SpellEntry, 'id'>>>;
  readonly learned_spells?: readonly string[];
  readonly talents?: {
    readonly learned: readonly string[];
    readonly points: number;
    readonly tree?: readonly TalentNode[];
  };
  readonly group?: Group | null;
  readonly group_invites?: readonly GroupInvite[];
}

/**
 * Generischer Server-Message-Typ. Wir typen `init` voll aus (siehe
 * `InitMessage`) und alle anderen Messages werden über diesen Bag-Type mit
 * String-Index-Signatur gelesen — strict TS akzeptiert `msg['feld']` als
 * `unknown` ohne implicit-any-Error.
 *
 * Architektur-Entscheidung: Wir nutzen KEINEN Union `InitMessage |
 * UnknownServerMessage`, weil das Union-Narrowing nach `isInitMessage` TS
 * strukturell nicht auf den Else-Pfad reduzieren kann (`InitMessage` hat
 * keine Index-Signatur, also keine Substruktur-Beziehung zu
 * `UnknownServerMessage`). Stattdessen ist `ServerMessage` der Bag-Type;
 * `InitMessage` ist eine zusätzliche Vollform, in die per Type-Guard gecastet
 * werden kann.
 */
export interface UnknownServerMessage {
  readonly type: string;
  readonly [key: string]: unknown;
}

/** Server → Client: Bag-Type mit `type`-Diskriminator. */
export type ServerMessage = UnknownServerMessage;

/** Client → Server: jeder Frame hat `type` + optional zusätzliche Felder. */
export interface ClientIntent {
  readonly type: string;
  readonly [key: string]: unknown;
}

/** Verbindungs-Status für UI-Bindings. */
export type ConnectionStatus = 'connecting' | 'open' | 'closed' | 'reconnecting';

/** Type-Guard, der einen Bag-Frame in die voll-getypte `InitMessage` narrowt. */
export function isInitMessage(msg: ServerMessage): msg is ServerMessage & InitMessage {
  return msg.type === 'init';
}
