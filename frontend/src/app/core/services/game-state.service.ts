// GameStateService — die Single Source of Truth für UI-Zustände.
//
// Abonniert `WebSocketService.messages$` und befüllt Angular-Signals nach
// Message-Type. UI-Komponenten lesen diese Signals (read-only) und reagieren
// per Change-Detection. Schreibend bewegen sich nur die hier definierten
// Message-Handler — Components senden Intents direkt über `WebSocketService`.
//
// F3-Scope: Spiegelung des Legacy-`handleMsg`-Switch-Statements für die
// Message-Types, die State-Updates auslösen. UI-Side-Effects (Sound, Visual-
// Effects, Toasts, Camera-Shake) bleiben außen vor — die wandern in F4ff. in
// die jeweils zuständige Component bzw. einen separaten `FeedbackService`.
//
// Logging-Politik: Unbekannte Message-Types loggen wir mit `console.warn`
// einmalig pro Type — hilft beim Debugging, ohne den Console-Stream zu
// fluten (siehe `_unknownWarned`-Set).

import { Injectable, inject, signal } from '@angular/core';

import type { Chunk, DungeonMarker, Structure, WorldEvent } from '../models/chunk.model';
import type { Group, GroupInvite } from '../models/group.model';
import type { GroundItem, InventoryItem } from '../models/item.model';
import type { NPC } from '../models/npc.model';
import type {
  OnlinePlayer,
  PlayerAttributes,
  PlayerSnapshot,
  PlayerStats,
  StatusEffect,
} from '../models/player.model';
import type { Bill } from '../models/bill.model';
import type { FactionReputation, Quest, QuestObjective } from '../models/quest.model';
import type {
  ResearchAge,
  ResearchBranch,
  ResearchNode,
} from '../models/research.model';
import type { SpellEntry, SpellState, TalentTree } from '../models/talent.model';
import type { TimeSnapshot, WeatherSnapshot } from '../models/time.model';
import type {
  InitMessage,
  ServerMessage,
  UnknownServerMessage,
} from '../models/ws-message.model';
import { isInitMessage } from '../models/ws-message.model';
import { ToastService } from './toast.service';
import { WebSocketService } from './websocket.service';

/**
 * Lokaler Alias: nach dem `isInitMessage`-Narrowing reduziert sich der Type
 * auf `UnknownServerMessage`, weil das die zweite Variante des Diskriminator-
 * Unions ist. Mit dieser Hilfs-Alias haben Felder wie `msg['x']` eine echte
 * `unknown`-Signatur statt `never`.
 */
type GenericMsg = UnknownServerMessage;

/** Helper-Lookup für `inventory_update`-Format-A (Slot-Move löscht alte Slot-
 *  Markierung am vorherigen Item). */
function _stripPreviousSlot(
  items: readonly InventoryItem[],
  incoming: InventoryItem,
): InventoryItem[] {
  if (!incoming.equipped_slot) return items.slice();
  return items.map((it) => {
    if (it.id === incoming.id) return it;
    if (it.equipped_slot === incoming.equipped_slot) {
      return { ...it, equipped_slot: null };
    }
    return it;
  });
}

@Injectable({ providedIn: 'root' })
export class GameStateService {
  private readonly ws = inject(WebSocketService);
  private readonly toast = inject(ToastService);

  // ─── Spieler-State ────────────────────────────────────────────────────
  readonly player = signal<PlayerSnapshot | null>(null);
  readonly stats = signal<PlayerStats | null>(null);
  readonly attributes = signal<PlayerAttributes | null>(null);
  readonly statusEffects = signal<readonly StatusEffect[]>([]);

  // ─── Inventar + Wallet ───────────────────────────────────────────────
  readonly inventory = signal<readonly InventoryItem[]>([]);
  readonly walletCopper = signal<number>(0);

  // ─── Party + Loot ────────────────────────────────────────────────────
  readonly party = signal<Group | null>(null);
  readonly partyInvites = signal<readonly GroupInvite[]>([]);
  /** Aktiver Loot-Roll (F12 — Overlay). Genau einer aktiv zur Zeit; Backend
   *  serialisiert das im `loot_rolls`-Modul. */
  readonly activeLootRoll = signal<{
    readonly roll_id: number;
    readonly item: { readonly kind: string; readonly quantity?: number; readonly quality?: string };
    readonly expires_in_s: number;
    readonly started_at_ms: number;
  } | null>(null);

  // ─── Quests + Factions ───────────────────────────────────────────────
  readonly quests = signal<readonly Quest[]>([]);
  readonly factions = signal<readonly FactionReputation[]>([]);

  // ─── Talents + Spells ────────────────────────────────────────────────
  readonly talents = signal<TalentTree | null>(null);
  readonly spells = signal<SpellState>({ catalog: [], learned: [] });
  /** Aktiver Cast — F13. Backend sendet `cast_started`, `cast_interrupted`,
   *  `cast_finished`. Während gecastet wird, ist die Cast-Bar sichtbar. */
  readonly activeCast = signal<{
    readonly spell_id: string;
    readonly started_at_ms: number;
    readonly duration_ms: number;
  } | null>(null);

  /** Spell-Cooldowns (H2.4) — Map `spell_id` → absolute Endzeit (`Date.now()`-
   *  Basis). Befüllt aus `cast_finished {spell_id, cooldown_ms}`. Konsumenten
   *  (Hotbar) lesen lazy: `(endMs - Date.now()) / 1000`, ignorieren Einträge
   *  mit Rest ≤ 0. Kein eigener Cleanup-Tick — Map bleibt klein (max ~10
   *  Spells), abgelaufene Einträge werden beim nächsten `cast_finished` für
   *  denselben Spell überschrieben.
   *
   *  Read-only von außen — gesetzt nur aus `_handleCastFinished`. */
  readonly spellCooldowns = signal<ReadonlyMap<string, number>>(new Map());

  // ─── H2.6 — Container-Action-Target-Mode ────────────────────────────
  //
  // Bei Container-Items (Eimer/Gießkanne/Wasserschlauch) muss der Spieler
  // für `fill_container` (Wasser-Tile / Brunnen) und `water_plant`
  // (farm_plot) ein Ziel-Tile picken. Das Chest-Panel triggert diesen
  // Mode mit `beginContainerAction({...})`; das
  // `<app-container-action-overlay>` (Schwester zu spell-target-overlay)
  // intercepted den nächsten Click und sendet den passenden Intent.
  readonly containerAction = signal<{
    readonly action: 'fill_container' | 'water_plant';
    readonly item_id: number;
    readonly item_name: string;
  } | null>(null);

  // ─── H2.3 — Spell-Target-Selection-Mode ──────────────────────────────
  //
  // Wenn der Spieler im Spellbook einen Spell mit `target_kind ∈
  // {single, aoe, ground, group, downed}` cassen möchte, geht das nicht
  // direkt — der Cast braucht ein konkretes Ziel (`target_npc_id` oder
  // `target_x`/`target_y`). Wir gehen dann in den Target-Selection-Mode:
  //   • `castingSpell` zeigt den Spell-Catalog-Eintrag, auf den gewartet
  //     wird (für Range-Indicator + Cursor-Hint).
  //   • Das `<app-spell-target-overlay>` intercepted den nächsten Click,
  //     rechnet Bildschirm → Tile-Koord um, sendet den `cast_spell`-Intent
  //     und resettet das Signal.
  //   • ESC cancelt → `cancelSpellTarget()`.
  //  `target_kind='self'` fällt direkt im Spellbook durch (kein Target
  //  nötig, sendet sofort).
  readonly castingSpell = signal<SpellEntry | null>(null);

  // ─── Welt-Zustand (für Renderer in F4) ───────────────────────────────
  readonly time = signal<TimeSnapshot | null>(null);
  readonly weather = signal<WeatherSnapshot | null>(null);
  readonly chunks = signal<readonly Chunk[]>([]);
  readonly structures = signal<readonly Structure[]>([]);
  readonly dungeons = signal<readonly DungeonMarker[]>([]);
  readonly npcsVisible = signal<readonly NPC[]>([]);
  readonly itemsGround = signal<readonly GroundItem[]>([]);
  readonly events = signal<readonly WorldEvent[]>([]);
  readonly players = signal<Readonly<Record<string, OnlinePlayer>>>({});
  /** Aktuell laufende Disaster (H1.17). Backend tracked das in `disaster_state`;
   *  Frontend hält nur die `kind`-Strings für UI-Indikatoren. Patches durch
   *  `disaster_started` / `disaster_ended`; Init-Snapshot über
   *  `init.active_disasters`. */
  readonly activeDisasters = signal<ReadonlySet<string>>(new Set());

  // ─── Dungeon-Kontext (H1-C / H1.5, H1.12) ────────────────────────────
  /** True wenn der Spieler in einer Dungeon-Instanz ist (Gegenstück zur
   *  Overworld). Subagent A (H1.10/H1.11) toggled das beim `dungeon_enter`/
   *  `dungeon_exit`-Handler. Click-Routing in `world-scene.ts::handleTileClick`
   *  nutzt das, um Dungeon-spezifische Intents (z. B. `dungeon_chest`) zu
   *  senden statt der Overworld-Defaults. */
  readonly inDungeon = signal<boolean>(false);
  /** Feature-Tiles im aktuellen Dungeon-Floor, die als Truhe klickbar sind.
   *  Befüllt von Subagent A aus `dungeon_enter`/`dungeon_floor_change`.
   *  Click-Routing matched Tile-Pos gegen diese Liste → `dungeon_chest`-
   *  Intent. `opened`-Flag verhindert Re-Trigger auf bereits geleerte
   *  Truhen (Backend lehnt das ohnehin ab, aber Toast-Spam vermeiden). */
  readonly dungeonChests = signal<readonly {
    readonly x: number;
    readonly y: number;
    readonly opened: boolean;
  }[]>([]);

  // ─── Interaktions-Modals (F-extras-1) ────────────────────────────────
  /** Aktive NPC-Konversation (Dialog-Panel). */
  readonly activeDialog = signal<{
    readonly npc_id: number;
    readonly npc_name: string;
    readonly npc_kind: string;
    readonly backstory: string;
    /** Lokaler Verlauf — vom Dialog-Panel gepflegt. */
    readonly history: readonly { readonly side: 'user' | 'npc'; readonly text: string; readonly typing?: boolean }[];
    readonly waiting: boolean;
  } | null>(null);

  /** Truhe (chest_open / chest_add / chest_remove). */
  readonly activeChest = signal<{
    readonly chest_id: number;
    readonly items: readonly { readonly id: number; readonly kind: string; readonly name: string; readonly quantity?: number; readonly quality?: string }[];
  } | null>(null);

  /** Crafting-Station mit Rezeptliste (crafting_open). */
  readonly activeCrafting = signal<{
    readonly station: string;
    readonly recipes: readonly {
      readonly output: string;
      readonly category?: string;
      readonly requires?: string | null;
      readonly inputs: readonly { readonly kind: string; readonly quantity: number }[];
    }[];
  } | null>(null);

  /** Aktives Quest-Board-Angebot (quest_board_open). H1.6. */
  readonly activeQuestBoard = signal<{
    readonly board_id: number;
    readonly offers: readonly {
      readonly template_id: string;
      readonly title: string;
      readonly description?: string;
      readonly quest_type?: string;
      readonly objective?: Readonly<Record<string, unknown>>;
      readonly reward?: Readonly<Record<string, number | string>>;
      readonly tier?: number;
    }[];
  } | null>(null);

  /** Letzter NPC-Quest-Status (`npc_quest_status` aus `query_npc_quests`).
   *  Dialog-Panel rendert das als „Verfügbare Quests"-Sektion (H1.8). */
  readonly activeNpcQuestStatus = signal<{
    readonly npc_id: number;
    readonly offers: readonly {
      readonly template_id: string;
      readonly title: string;
      readonly description?: string;
      readonly tier?: number;
    }[];
    readonly turnins: readonly { readonly quest_id: number; readonly title: string }[];
  } | null>(null);

  /** Händler-Tab (trade_open). */
  readonly activeTrade = signal<{
    readonly npc_id: number;
    readonly npc_name: string;
    readonly coins: number;
    readonly offerings: readonly {
      readonly kind: string;
      readonly name: string;
      readonly price: number;
      readonly sprite_path?: string;
    }[];
  } | null>(null);

  // ─── Downed-State (F15) ──────────────────────────────────────────────
  /** Wenn der Spieler im Down-State ist, der absolute ms-Zeitstempel, ab dem
   *  er sich auto-respawnen kann. Wird auf `player_downed` gesetzt, auf
   *  `player_respawned` geleert. */
  readonly downedExpiresAt = signal<number | null>(null);

  // ─── Chat (F14) ──────────────────────────────────────────────────────
  readonly chatLog = signal<readonly {
    readonly id: number;
    readonly kind: 'player' | 'group' | 'system' | 'error' | 'self';
    readonly from?: string;
    readonly text: string;
  }[]>([]);

  // ─── Research (F-extras-2) ───────────────────────────────────────────
  /** Research-Tree: Node-Map + Pool + Branch/Age-Definitionen. */
  readonly research = signal<{
    readonly nodes: Readonly<Record<string, ResearchNode>>;
    readonly pool: number;
    readonly branches: readonly ResearchBranch[];
    readonly ages: readonly ResearchAge[];
  }>({ nodes: {}, pool: 0, branches: [], ages: [] });

  // ─── Bills (F-extras-2) ──────────────────────────────────────────────
  /** Aktive Workshop-Aufträge (alle Stationen). UI filtert pro Station. */
  readonly bills = signal<readonly Bill[]>([]);

  // ─── Sign-Inspect (F-extras-3) ───────────────────────────────────────
  /** Aktives Sign-Inspect-Modal (Welle 51 — Schild-Lese-Modal). */
  readonly activeSignInspect = signal<{
    readonly slug: string;
    readonly label: string;
  } | null>(null);

  // ─── Dungeon-Floor-State (Welle H1-A — H1.10 / H1.11) ────────────────
  /** Aktiver Dungeon-Floor (rich state für den `DungeonRenderer` in der
   *  Phaser-Scene). Null wenn der Spieler in der Overworld ist. Wird von
   *  `dungeon_enter` / `dungeon_floor_change` gesetzt, von `dungeon_exit`
   *  / `dungeon_collapsed` geleert. Parallel pflegen wir `inDungeon` und
   *  `dungeonChests` (oben), die das Click-Routing in der WorldScene
   *  nutzt. */
  readonly dungeonFloor = signal<{
    readonly id: number | string;
    readonly name?: string;
    readonly floorIdx: number;
    readonly floorCount: number;
    readonly size: number;
    readonly tiles: readonly (readonly number[])[];
    readonly spawn: { readonly x: number; readonly y: number };
    /** Theme-Daten (Tints, Label, Ambient) aus `dungeon_floor_payload`. */
    readonly theme?: string;
    readonly themeData?: {
      readonly label?: string;
      readonly wall_tint?: string | number | null;
      readonly floor_tint?: string | number | null;
      readonly ambient_color?: string | number | null;
      readonly ambient?: string | null;
    };
    /** Sichtbare Features (Truhen, getriggerte Fallen, Decor). */
    readonly features?: {
      readonly chests?: readonly { readonly x: number; readonly y: number; readonly opened?: boolean }[];
      readonly traps?: readonly { readonly x: number; readonly y: number; readonly kind?: string }[];
      readonly decor?: readonly { readonly x: number; readonly y: number; readonly kind: string }[];
    };
    /** Versions-Token (monotonic): inkrementiert pro `dungeon_enter` /
     *  `dungeon_floor_change`. Der Phaser-Renderer beobachtet den Wert
     *  und triggert dann den Floor-Re-Render (statt nur Signal-Identity,
     *  das stabil bliebe, wenn Backend zweimal denselben Floor schickt). */
    readonly version: number;
  } | null>(null);

  /** Dungeon-Sense-Pulse (kurzlebig): wenn der Spieler ein Sense-Item
   *  benutzt, sendet das Backend Dungeon-Positionen im Radius. Wird von
   *  der Minimap-Komponente konsumiert (Pulse-Animation für 5s, H3.10
   *  Polish-Task). Wir füttern das Signal hier bereits, damit alle sechs
   *  dungeon_*-Frames atomar in einem Commit landen. */
  readonly dungeonSensePulse = signal<{
    readonly at_ms: number;
    readonly dungeons: readonly { readonly x: number; readonly y: number; readonly radius?: number }[];
  } | null>(null);

  /** Monotonic version-token für `dungeonFloor.version`. */
  private _dungeonVersion = 0;

  // ─── Meta ────────────────────────────────────────────────────────────
  readonly worldSeed = signal<number | string | null>(null);
  readonly chunkSize = signal<number>(32);
  readonly needsCharacterCreation = signal<boolean>(false);
  private _nextChatId = 1;

  /** Tracking, welche unbekannten Types wir schon gewarnt haben (1× je Type). */
  private readonly _unknownWarned = new Set<string>();

  constructor() {
    // Subscribe lebenslang (Service ist root-singleton → kein Cleanup nötig).
    this.ws.messages$.subscribe((msg) => this._dispatch(msg));
  }

  // ─── Dispatch ─────────────────────────────────────────────────────────

  private _dispatch(msg: GenericMsg): void {
    if (isInitMessage(msg)) {
      this._handleInit(msg);
      return;
    }
    // `ServerMessage` IST `UnknownServerMessage` (Bag-Type) — kein Else-
    // Narrowing nötig, der `init`-Pfad ist oben behandelt.
    this._dispatchGeneric(msg);
  }

  private _dispatchGeneric(msg: GenericMsg): void {
    switch (msg.type) {
      // ─── Player ────────────────────────────────────────────────────
      case 'player_moved':         this._handlePlayerMoved(msg); break;
      case 'player_joined':        this._handlePlayerJoined(msg); break;
      case 'player_left':          this._handlePlayerLeft(msg); break;
      case 'player_damaged':       this._patchPlayer({ hp: msg['hp'] as number, max_hp: msg['max_hp'] as number }); break;
      case 'player_healed':        this._patchPlayer({ hp: msg['hp'] as number, max_hp: msg['max_hp'] as number }); break;
      case 'player_mana':          this._patchPlayer({ mana: msg['mana'] as number, max_mana: msg['max_mana'] as number }); break;
      case 'player_needs':         this._handlePlayerNeeds(msg); break;
      case 'player_downed':        this._handlePlayerDowned(msg); break;
      case 'player_respawned':     this._handlePlayerRespawned(msg); break;
      case 'player_died':          /* nur Toast — kein Self-State */ break;
      case 'player_downed_visible':
      case 'player_revived_visible':
        // Visualisierung in F4 — State-Service ignoriert.
        break;
      case 'body_part_damaged':    this._handleBodyPartDamaged(msg); break;
      case 'sprint_state':         this._patchPlayer({ is_sprinting: msg['on'] === true }); break;
      case 'rest_start':           this._patchPlayer({ is_resting: true }); break;
      case 'rest_end':             this._patchPlayer({ is_resting: false }); break;
      case 'attributes_update':
      case 'attrs_update':         this._handleAttributesUpdate(msg); break;
      case 'status_effects':       this._handleStatusEffects(msg); break;

      // ─── Inventar ──────────────────────────────────────────────────
      case 'inventory_add':        this._handleInventoryAdd(msg); break;
      case 'inventory_update':     this._handleInventoryUpdate(msg); break;
      case 'inventory_remove':     this._handleInventoryRemove(msg); break;
      case 'inventory_full_refresh': this._handleInventoryFullRefresh(msg); break;
      case 'wallet_update':        this._handleWalletUpdate(msg); break;
      case 'trade_coins':          this._handleWalletUpdate(msg); break;

      // ─── NPCs + Items am Boden ─────────────────────────────────────
      case 'npc_spawned':          this._handleNpcSpawned(msg); break;
      case 'npc_moved':            this._handleNpcMoved(msg); break;
      case 'npc_damaged':          this._handleNpcDamaged(msg); break;
      case 'npc_died':             this._handleNpcDied(msg); break;
      case 'npc_reply':            this._handleNpcReply(msg); break;
      case 'npc_attacked':
      case 'npc_goal':
      case 'npc_speech':
      case 'npc_mood':
        // UI-Side-Effects (Sprechblase, Mood-Icon) — kein State-Update.
        break;
      case 'npc_quest_status':     this._handleNpcQuestStatus(msg); break;

      case 'item_spawned':         this._handleItemSpawned(msg); break;
      case 'item_picked_up':       this._handleItemPickedUp(msg); break;

      // ─── Strukturen ────────────────────────────────────────────────
      case 'structure_placed':     this._handleStructurePlaced(msg); break;
      case 'structure_replaced':   this._handleStructureReplaced(msg); break;
      case 'structure_removed':    this._handleStructureRemoved(msg); break;
      case 'structure_damaged':    this._handleStructureDamaged(msg); break;
      case 'structure_repaired':   this._handleStructureDamaged(msg); break;
      case 'structure_upgraded':   this._handleStructureUpgraded(msg); break;

      // ─── Chunks + Welt ─────────────────────────────────────────────
      case 'chunks':               this._handleChunks(msg); break;
      case 'event':                this._handleEvent(msg); break;
      case 'world_event':          this._handleWorldEvent(msg); break;
      case 'weather':              this._handleWeather(msg); break;

      // ─── Zeit (H1.18) ──────────────────────────────────────────────
      // Backend sendet aktuell `time_update` (siehe backend/time_system.py).
      // Anhang B des Frontend-Implementation-Plans warnt vor einem
      // `time_tick`-Mismatch — wir handlen defensiv beide Strings auf den
      // selben Branch, damit ein etwaiges Backend-Rename oder ein paralleles
      // Frame-Format nicht stillschweigend versickert.
      case 'time_update':
      case 'time_tick':            this._handleTimeUpdate(msg); break;

      // ─── Party / Loot ───────────────────────────────────────────────
      case 'group_state':          this.party.set((msg['group'] as Group | null) ?? null); break;
      case 'group_invite_received': this._handleGroupInviteReceived(msg); break;
      case 'group_invite_sent':    /* nur Sender-Feedback */ break;
      case 'group_disbanded':      this.party.set(null); break;
      case 'group_kicked':         this.party.set(null); break;
      case 'group_member_left':    /* group_state folgt auf dem Fuß */ break;
      case 'group_member_online':
      case 'group_member_offline':
        this._handleGroupMemberStatus(msg);
        break;
      case 'group_converted':      this._handleGroupConverted(msg); break;
      case 'group_chat':           this._handleGroupChat(msg); break;
      case 'group_error':          this._toastError(msg, 'Gruppen-Aktion fehlgeschlagen'); break;
      case 'raid_error':           this._toastError(msg, 'Raid-Aktion fehlgeschlagen'); break;
      case 'raid_started':         this._handleRaidStarted(msg); break;
      case 'loot_roll_started':    this._handleLootRollStarted(msg); break;
      case 'loot_roll_resolved':   this.activeLootRoll.set(null); break;
      case 'loot_roll_voted':
      case 'loot_rule_changed':
        // loot_voted: nur Live-Vote-Count, der Overlay zeigt das nicht; das
        // Lootrule-Update wird vom späteren Party-Settings-Panel konsumiert.
        break;
      case 'loot_vote_error':      this._toastError(msg, 'Loot-Vote ungültig'); break;

      // ─── Quests + Factions ──────────────────────────────────────────
      case 'quests_update':        this._handleQuestsUpdate(msg); break;
      case 'quest_new':            this._handleQuestNew(msg); this._toastQuestNew(msg); break;
      case 'quest_progress':       this._handleQuestProgress(msg); this._toastQuestProgress(msg); break;
      case 'quest_closed':         this._handleQuestClosed(msg); this._toastQuestClosed(msg); break;
      case 'factions_update':      this._handleFactionsUpdate(msg); break;
      case 'quest_board_open':     this._handleQuestBoardOpen(msg); break;

      // ─── Talents + Spells ───────────────────────────────────────────
      case 'talents_update':       this._handleTalentsUpdate(msg); break;
      case 'talent_learned':       this._handleTalentLearned(msg); this._toastTalentLearned(msg); break;
      case 'spell_learned':        this._handleSpellLearned(msg); this._toastSpellLearned(msg); break;
      case 'cast_started':         this._handleCastStarted(msg); break;
      case 'cast_interrupted':     this.activeCast.set(null); break;
      case 'cast_finished':        this._handleCastFinished(msg); break;

      // ─── Crafting / Trade / Bills / Research ────────────────────────
      case 'crafting_open':        this._handleCraftingOpen(msg); break;
      case 'trade_open':           this._handleTradeOpen(msg); break;
      case 'chest_open':           this._handleChestOpen(msg); break;
      case 'chest_add':            this._handleChestAdd(msg); break;
      case 'chest_remove':         this._handleChestRemove(msg); break;
      case 'sign_inspect':         this._handleSignInspect(msg); break;
      case 'bills_update':         this._handleBillsUpdate(msg); break;
      case 'bill_progress':        this._handleBillProgress(msg); break;
      case 'bill_done':            this._handleBillDone(msg); break;
      case 'bill_blocked':         this._handleBillBlocked(msg); break;
      case 'research_update':      this._handleResearchUpdate(msg); break;
      case 'research_pool_update': this._handleResearchPoolUpdate(msg); break;
      case 'skill_xp':             /* Floating-Text, kein persistent state hier */ break;

      // ─── Disaster (H1.17 — Start/End-Toast + activeDisasters-Set) ───
      case 'disaster_started':     this._handleDisasterStarted(msg); break;
      case 'disaster_ended':       this._handleDisasterEnded(msg); break;

      // ─── Dungeons (Welle H1-A — H1.10 / H1.11) ─────────────────────
      case 'dungeon_enter':         this._handleDungeonEnter(msg); break;
      case 'dungeon_floor_change':  this._handleDungeonFloorChange(msg); break;
      case 'dungeon_exit':          this._handleDungeonExit(msg); break;
      case 'dungeon_collapsed':     this._handleDungeonCollapsed(msg); break;
      case 'dungeon_sense':         this._handleDungeonSense(msg); break;
      case 'dungeon_chest_opened':  this._handleDungeonChestOpened(msg); break;

      // ─── Misc-FX (UI-Side-Effects, kein State) ─────────────────────
      case 'trap_triggered':
      case 'lightning_strike':
      case 'earthquake_shake':
      case 'visual_effect':
      case 'character_name_check':
        // Reine UI-/Audio-Effekte oder Modals — keine Signals zu updaten.
        break;

      case 'chat':                 this._handleChat(msg); break;

      // ─── Spieler-Lifecycle-Toasts (H1.23) ──────────────────────────
      // `player_respawned` ist oben schon gehandelt (Down-State-Clear); der
      // Toast lebt direkt im Handler, damit kein Duplicate-Case entsteht.
      // `character_created` triggert hier nur den Erfolgs-Toast; der State
      // wird via folgendem `init`-Frame ohnehin neu aufgebaut.
      case 'character_created':    this.toast.show('Charakter erstellt.', 'success'); break;

      // ─── Backend-Toast (H1.22 — vorher No-op, jetzt aktiv) ────────
      case 'toast':                this._handleBackendToast(msg); break;

      default:
        this._warnUnknown(msg.type);
        break;
    }
  }

  // ─── Handlers ─────────────────────────────────────────────────────────

  private _handleInit(msg: InitMessage): void {
    this.needsCharacterCreation.set(msg.needs_character_creation);
    this.worldSeed.set(msg.world_seed);
    this.chunkSize.set(msg.chunk_size);

    this.player.set({
      player_id: msg.player_id,
      hp: msg.hp,
      max_hp: msg.max_hp,
      mana: msg.mana,
      max_mana: msg.max_mana,
      hunger: msg.hunger,
      max_hunger: msg.max_hunger,
      stamina: msg.stamina,
      max_stamina: msg.max_stamina,
      thirst: msg.thirst,
      max_thirst: msg.max_thirst,
      x: msg.spawn.x,
      y: msg.spawn.y,
      power_tier: msg.power_tier,
      body_parts: msg.body_parts,
      attributes: msg.attributes,
      stats: msg.stats,
      skills: msg.skills,
      preset: msg.preset,
    });
    if (msg.stats) this.stats.set(msg.stats);
    if (msg.attributes) this.attributes.set(msg.attributes);

    this.inventory.set(msg.inventory);
    this.walletCopper.set(msg.wallet_copper);
    this.players.set(msg.players);
    this.chunks.set(msg.chunks);
    this.structures.set(msg.structures);
    this.dungeons.set(msg.dungeons);
    this.npcsVisible.set(msg.npcs);
    this.itemsGround.set(msg.items_ground);
    this.events.set(msg.events);

    if (msg.time) this.time.set(msg.time);
    if (msg.quests) this.quests.set(msg.quests);
    if (msg.factions) this.factions.set(msg.factions);
    if (msg.talents) this.talents.set(msg.talents);
    // Backend sendet `spell_catalog` als dict (kind → def). Wir bauen daraus
    // einen Array mit `id`-Feld, damit UI über ein einheitliches Format
    // iterieren kann.
    const catalogDict = msg.spell_catalog ?? {};
    const catalog: SpellEntry[] = Object.entries(catalogDict).map(
      ([id, def]) => ({ id, ...def }),
    );
    this.spells.set({
      catalog,
      learned: msg.learned_spells ?? [],
    });

    this.party.set(msg.group ?? null);
    this.partyInvites.set(msg.group_invites ?? []);

    // H1.16 — Init-Snapshot der aktiven Welt-Disaster (Bloodmoon, Pestilence,
    // …). Inkrementelle Patches kommen über `disaster_started`/`disaster_ended`.
    const initDisasters = msg.active_disasters ?? [];
    this.activeDisasters.set(new Set(initDisasters.map((d) => d.kind)));

    // Welle 22+30: research kommt als {nodes,pool,branches,ages} oder als
    // platter nodes-dict (Legacy-Format, frontend/legacy/app.js Z. 5080-5089).
    if (msg.research && typeof msg.research === 'object') {
      const rObj = msg.research as Record<string, unknown>;
      if ('nodes' in rObj) {
        this.research.set({
          nodes: (rObj['nodes'] as Readonly<Record<string, ResearchNode>>) ?? {},
          pool: (rObj['pool'] as number | undefined) ?? 0,
          branches: (rObj['branches'] as readonly ResearchBranch[] | undefined) ?? [],
          ages: (rObj['ages'] as readonly ResearchAge[] | undefined) ?? [],
        });
      } else {
        // Legacy: msg.research IST das Nodes-Dict
        this.research.set({
          nodes: msg.research as Readonly<Record<string, ResearchNode>>,
          pool: 0,
          branches: [],
          ages: [],
        });
      }
    }
  }

  // ── Player ──

  private _patchPlayer(patch: Partial<PlayerSnapshot>): void {
    const cur = this.player();
    if (!cur) return;
    this.player.set({ ...cur, ...patch });
  }

  private _handlePlayerMoved(msg: GenericMsg): void {
    const id = String(msg['player_id']);
    const x = msg['x'] as number;
    const y = msg['y'] as number;
    const cur = this.players();
    const existing = cur[id];
    if (!existing) return;
    this.players.set({ ...cur, [id]: { ...existing, x, y } });
  }

  private _handlePlayerJoined(msg: GenericMsg): void {
    const id = String(msg['player_id']);
    const entry: OnlinePlayer = {
      player_id: msg['player_id'] as number,
      name: (msg['name'] as string) ?? id,
      x: msg['x'] as number,
      y: msg['y'] as number,
      preset: (msg['preset'] as string | null) ?? null,
    };
    this.players.set({ ...this.players(), [id]: entry });
  }

  private _handlePlayerLeft(msg: GenericMsg): void {
    const id = String(msg['player_id']);
    const cur = { ...this.players() };
    delete cur[id];
    this.players.set(cur);
  }

  private _handlePlayerNeeds(msg: GenericMsg): void {
    this._patchPlayer({
      hunger: msg['hunger'] as number | undefined ?? this.player()?.hunger ?? 0,
      thirst: msg['thirst'] as number | undefined ?? this.player()?.thirst ?? 0,
      stamina: msg['stamina'] as number | undefined ?? this.player()?.stamina ?? 0,
      max_hunger: msg['max_hunger'] as number | undefined ?? this.player()?.max_hunger ?? 0,
      max_thirst: msg['max_thirst'] as number | undefined ?? this.player()?.max_thirst ?? 0,
      max_stamina: msg['max_stamina'] as number | undefined ?? this.player()?.max_stamina ?? 0,
    });
  }

  private _handlePlayerRespawned(msg: GenericMsg): void {
    this._patchPlayer({
      hp: msg['hp'] as number,
      max_hp: msg['max_hp'] as number,
      x: msg['x'] as number,
      y: msg['y'] as number,
      is_downed: false,
    });
    this.downedExpiresAt.set(null);
    // H1.23 — Lifecycle-Feedback. Wir packen den Toast direkt hier, damit
    // der Dispatch keinen Duplicate-Case mit dem oben definierten
    // `case 'player_respawned'` braucht.
    this.toast.show('Du wurdest wiederbelebt.', 'info');
  }

  private _handlePlayerDowned(msg: GenericMsg): void {
    this._patchPlayer({ is_downed: true });
    const dur = (msg['duration_s'] as number | undefined) ?? 30;
    this.downedExpiresAt.set(Date.now() + dur * 1000);
  }

  private _handleBodyPartDamaged(msg: GenericMsg): void {
    const part = msg['part'] as string | undefined;
    const hp = msg['hp'] as number | undefined;
    const max = msg['max_hp'] as number | undefined;
    if (!part || hp == null || max == null) return;
    const cur = this.player();
    if (!cur || !cur.body_parts) return;
    const next = cur.body_parts.map((bp) =>
      bp.name === part ? { ...bp, hp, max_hp: max, damaged: hp < max } : bp,
    );
    this._patchPlayer({ body_parts: next });
  }

  private _handleAttributesUpdate(msg: GenericMsg): void {
    const attrs = msg['attributes'] as PlayerAttributes | undefined;
    if (attrs) {
      this.attributes.set(attrs);
      this._patchPlayer({ attributes: attrs });
    }
    const stats = msg['stats'] as PlayerStats | undefined;
    if (stats) {
      this.stats.set(stats);
      this._patchPlayer({ stats });
    }
  }

  private _handleStatusEffects(msg: GenericMsg): void {
    const effects = msg['effects'] as readonly StatusEffect[] | undefined;
    this.statusEffects.set(effects ?? []);
  }

  // ── Inventory ──

  private _handleInventoryAdd(msg: GenericMsg): void {
    const item = msg['item'] as InventoryItem | undefined;
    if (!item) return;
    const cur = this.inventory();
    const idx = cur.findIndex((it) => it.id === item.id);
    if (idx >= 0) {
      const next = cur.slice();
      next[idx] = item;
      this.inventory.set(next);
    } else {
      this.inventory.set([...cur, item]);
    }
  }

  private _handleInventoryUpdate(msg: GenericMsg): void {
    const cur = this.inventory();
    // Format A: voll {item: {...}} (z. B. equipped_slot Change)
    const item = msg['item'] as InventoryItem | undefined;
    if (item) {
      let next: InventoryItem[];
      if (item.equipped_slot) {
        next = _stripPreviousSlot(cur, item);
      } else {
        next = cur.slice();
      }
      const idx = next.findIndex((it) => it.id === item.id);
      if (idx >= 0) next[idx] = item;
      else next.push(item);
      this.inventory.set(next);
      return;
    }
    // Format B: schlank {item_id, quantity} (Stack-Decrement)
    const itemId = msg['item_id'] as number | undefined;
    const quantity = msg['quantity'] as number | undefined;
    if (itemId != null && quantity != null) {
      const next = cur.map((it) =>
        it.id === itemId ? { ...it, quantity } : it,
      );
      this.inventory.set(next);
    }
  }

  private _handleInventoryRemove(msg: GenericMsg): void {
    const itemId = msg['item_id'] as number | undefined;
    if (itemId == null) return;
    this.inventory.set(this.inventory().filter((it) => it.id !== itemId));
  }

  private _handleInventoryFullRefresh(msg: GenericMsg): void {
    const items = msg['inventory'] as readonly InventoryItem[] | undefined;
    if (items) this.inventory.set(items);
  }

  private _handleWalletUpdate(msg: GenericMsg): void {
    const copper = msg['wallet_copper'] as number | undefined ?? msg['copper'] as number | undefined;
    if (copper != null) {
      this.walletCopper.set(copper);
      // Wenn der Trade-Modal offen ist, das Coin-Display dort mitziehen.
      const trade = this.activeTrade();
      if (trade) this.activeTrade.set({ ...trade, coins: copper });
    }
  }

  // ── NPCs + Ground-Items ──

  private _handleNpcSpawned(msg: GenericMsg): void {
    const npc = msg['npc'] as NPC | undefined;
    if (!npc) return;
    this.npcsVisible.set([...this.npcsVisible(), npc]);
  }

  private _handleNpcMoved(msg: GenericMsg): void {
    const id = msg['npc_id'] as number | undefined;
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (id == null || x == null || y == null) return;
    this.npcsVisible.set(
      this.npcsVisible().map((n) => (n.id === id ? { ...n, x, y } : n)),
    );
  }

  private _handleNpcDamaged(msg: GenericMsg): void {
    const id = msg['npc_id'] as number | undefined;
    const hp = msg['hp'] as number | undefined;
    const maxHp = msg['max_hp'] as number | undefined;
    if (id == null) return;
    this.npcsVisible.set(
      this.npcsVisible().map((n) =>
        n.id === id ? { ...n, hp: hp ?? n.hp, max_hp: maxHp ?? n.max_hp } : n,
      ),
    );
  }

  private _handleNpcDied(msg: GenericMsg): void {
    const id = msg['npc_id'] as number | undefined;
    if (id == null) return;
    this.npcsVisible.set(this.npcsVisible().filter((n) => n.id !== id));
  }

  private _handleItemSpawned(msg: GenericMsg): void {
    const item = msg['item'] as GroundItem | undefined;
    if (!item) return;
    this.itemsGround.set([...this.itemsGround(), item]);
  }

  private _handleItemPickedUp(msg: GenericMsg): void {
    const id = msg['item_id'] as number | undefined;
    if (id == null) return;
    this.itemsGround.set(this.itemsGround().filter((g) => g.id !== id));
  }

  // ── Strukturen ──

  private _handleStructurePlaced(msg: GenericMsg): void {
    const s = msg['structure'] as Structure | undefined;
    if (!s) return;
    this.structures.set([...this.structures(), s]);
  }

  private _handleStructureReplaced(msg: GenericMsg): void {
    const s = msg['structure'] as Structure | undefined;
    if (!s) return;
    const next = this.structures().filter(
      (cur) => !(cur.x === s.x && cur.y === s.y),
    );
    next.push(s);
    this.structures.set(next);
  }

  private _handleStructureRemoved(msg: GenericMsg): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (x == null || y == null) return;
    this.structures.set(
      this.structures().filter((s) => !(s.x === x && s.y === y)),
    );
  }

  private _handleStructureDamaged(msg: GenericMsg): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    const hp = msg['durability'] as number | undefined;
    const maxHp = msg['max_durability'] as number | undefined;
    if (x == null || y == null) return;
    this.structures.set(
      this.structures().map((s) =>
        s.x === x && s.y === y
          ? { ...s, hp: hp ?? s.hp, max_hp: maxHp ?? s.max_hp }
          : s,
      ),
    );
  }

  private _handleStructureUpgraded(msg: GenericMsg): void {
    const s = msg['structure'] as Structure | undefined;
    if (!s) return;
    this._handleStructureReplaced(msg);
  }

  // ── Welt ──

  private _handleChunks(msg: GenericMsg): void {
    const incoming = msg['chunks'] as readonly Chunk[] | undefined;
    if (!incoming || incoming.length === 0) return;
    // Merge: Chunks mit gleicher (cx,cy) ersetzen, neue dazu.
    const map = new Map<string, Chunk>();
    for (const c of this.chunks()) map.set(`${c.cx},${c.cy}`, c);
    for (const c of incoming) map.set(`${c.cx},${c.cy}`, c);
    this.chunks.set(Array.from(map.values()));
  }

  private _handleEvent(msg: GenericMsg): void {
    const ev = msg['event'] as WorldEvent | undefined;
    if (!ev) return;
    // Frontend hält letzte ~50 Events — der Renderer/Chronik-Panel limitiert
    // sich selbst. Wir schneiden hart ab, damit der Signal-Array nicht in
    // Long-Sessions ins Megabyte-Volume rutscht.
    const nextEvents = [...this.events(), ev];
    if (nextEvents.length > 50) nextEvents.splice(0, nextEvents.length - 50);
    this.events.set(nextEvents);
  }

  /**
   * H1.14 — `world_event`-Handler. Backend (event_worker, dungeon_director,
   * inventory.py) sendet das Frame mit `{kind, text, x?, y?}` (siehe z. B.
   * backend/ws/inventory.py:337 für `dungeon_spawned`). Wir spiegeln das in
   * den `events`-Signal-Stream (für Chronik-Panel, Subagent C H1.15) und
   * triggern bei hoher Severity zusätzlich einen Toast.
   *
   * Severity-Ableitung: Backend hat aktuell KEIN `severity`-Feld auf
   * `world_event` — wir leiten heuristisch ab, ob es ein Disaster-/Raid-
   * Event ist (Toast = warn) oder ein neutrales Highlight (kein Toast,
   * Chronik-Eintrag genügt). Sobald das Backend `severity` explizit mit-
   * schickt, greift der Cast oben.
   */
  private _handleWorldEvent(msg: GenericMsg): void {
    const kind = (msg['kind'] as string | undefined) ?? 'world_event';
    const text = msg['text'] as string | undefined;
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    const severity = msg['severity'] as string | undefined;
    // Synthetisches WorldEvent-Objekt bauen — Backend liefert die Felder
    // flach, wir bauen sie in die kanonische `WorldEvent`-Form, damit
    // Chronik + Init-Snapshot dasselbe Format konsumieren.
    const ev: WorldEvent = {
      id: `we_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      kind,
      title: text,
      description: text,
      ts: new Date().toISOString(),
      x,
      y,
    };
    const nextEvents = [...this.events(), ev];
    if (nextEvents.length > 50) nextEvents.splice(0, nextEvents.length - 50);
    this.events.set(nextEvents);

    // H2.22 — Toast-Trigger: Severity >= medium ODER Disaster-/Raid-
    // Heuristik (wenn Backend KEIN severity mitschickt). Schwellwert
    // `medium` weil die Spec sagt „high severity" — wir interpretieren
    // großzügig (medium-or-higher), damit selten benutzte Backend-Strings
    // wie `medium`/`major`/`warning`/`critical` alle einen Toast triggern.
    if (!text) return;
    const sev = severity?.toLowerCase();
    const toastSeverities = new Set([
      'medium', 'high', 'major', 'critical', 'severe', 'warning',
    ]);
    const isHighSeverity = sev != null && toastSeverities.has(sev);
    const isImportantKind =
      /disaster|raid|invasion|bloodmoon|wildfire|earthquake|collapse|dungeon_spawned/i.test(kind);
    if (isHighSeverity || isImportantKind) {
      // Kind-Bezogene Toast-Farbe: critical → error, sonst warn.
      const kindLevel: 'error' | 'warn' =
        sev === 'critical' || sev === 'severe' ? 'error' : 'warn';
      this.toast.show(text, kindLevel, 6000);
    }
  }

  private _handleWeather(msg: GenericMsg): void {
    const kind = msg['kind'] as string | undefined;
    const intensity = msg['intensity'] as number | undefined;
    if (!kind) return;
    this.weather.set({ kind, intensity: intensity ?? 0 });
  }

  private _handleTimeUpdate(msg: GenericMsg): void {
    // H1.18 — Backend sendet sowohl `{type:'time_update', **snap}` (flach,
    // Felder direkt auf msg, siehe backend/time_system.py) als auch — laut
    // WS_PROTOCOL.md Anhang B — alternativ `{type:'time_tick', time:{...}}`.
    // Wir akzeptieren beide Formen, damit ein etwaiges Frame-Format-Drift
    // nicht den Tag/Nacht-Cycle abreißen lässt.
    const nested = msg['time'] as TimeSnapshot | undefined;
    if (nested && typeof nested === 'object') {
      this.time.set(nested);
      return;
    }
    const hour = msg['hour'];
    const day = msg['day'];
    if (typeof hour === 'number' || typeof day === 'number') {
      const cur = this.time();
      const snap: TimeSnapshot = {
        day: (day as number | undefined) ?? cur?.day ?? 0,
        hour: (hour as number | undefined) ?? cur?.hour ?? 0,
        minute: (msg['minute'] as number | undefined) ?? cur?.minute ?? 0,
        phase: (msg['phase'] as TimeSnapshot['phase'] | undefined) ?? cur?.phase,
        is_blood_moon: (msg['is_blood_moon'] as boolean | undefined) ?? cur?.is_blood_moon,
      };
      this.time.set(snap);
    }
  }

  // ── Party ──

  private _handleGroupInviteReceived(msg: GenericMsg): void {
    // Backend-Format (ws/social.py::handle_group_invite): die Felder liegen
    // flach im Frame: invite_id, group_id, from, kind, expires_at.
    const inviteId = msg['invite_id'] as number | undefined;
    const groupId = msg['group_id'] as number | undefined;
    const from = msg['from'] as string | undefined;
    const kind = msg['kind'] as GroupInvite['kind'] | undefined;
    if (inviteId == null || groupId == null || !from || !kind) {
      // Defensiv: alternativ verschachteltes invite-Objekt (Legacy-Format).
      const inv = msg['invite'] as GroupInvite | undefined;
      if (inv) this.partyInvites.set([...this.partyInvites(), inv]);
      return;
    }
    const invite: GroupInvite = {
      invite_id: inviteId,
      group_id: groupId,
      from,
      kind,
      expires_at: msg['expires_at'] as string | undefined,
    };
    this.partyInvites.set([...this.partyInvites(), invite]);
  }

  /** Entfernt eine Einladung aus dem State (UI hat sie beantwortet). */
  consumeInvite(inviteId: number): void {
    this.partyInvites.set(
      this.partyInvites().filter((i) => i.invite_id !== inviteId),
    );
  }

  private _handleLootRollStarted(msg: GenericMsg): void {
    const rollId = msg['roll_id'] as number | undefined;
    const item = msg['item'] as {
      readonly kind: string;
      readonly quantity?: number;
      readonly quality?: string;
    } | undefined;
    if (rollId == null || !item) return;
    this.activeLootRoll.set({
      roll_id: rollId,
      item,
      expires_in_s: (msg['expires_in_s'] as number | undefined) ?? 20,
      started_at_ms: Date.now(),
    });
  }

  clearLootRoll(): void {
    this.activeLootRoll.set(null);
  }

  private _handleGroupMemberStatus(msg: GenericMsg): void {
    const cur = this.party();
    // Backend nennt das Feld `player_name` (oder `name`), nicht `player_id`.
    const playerName =
      (msg['player_name'] as string | undefined) ??
      (msg['name'] as string | undefined);
    if (!cur || !playerName) return;
    const online = msg.type === 'group_member_online';
    const next: Group = {
      ...cur,
      members: cur.members.map((m) =>
        m.name === playerName ? { ...m, online } : m,
      ),
    };
    this.party.set(next);
  }

  private _handleGroupConverted(msg: GenericMsg): void {
    const cur = this.party();
    if (!cur) return;
    const kind = msg['kind'] as Group['kind'] | undefined;
    if (!kind) return;
    this.party.set({ ...cur, kind });
  }

  /**
   * H2.13 — `raid_started` Welt-Event + Toast. Backend (raid_director +
   * `raid_trigger_manual`-Handler) broadcastet `{type:'raid_started', tier,
   * wave?, by?, x?, y?}` an alle Spieler im Umfeld. Wir spiegeln das in den
   * `events`-Stream (für die Chronik-Komponente, H1.15) und zeigen
   * zusätzlich einen Warn-Toast — der Spieler MUSS das mitkriegen, sonst
   * stehen plötzlich Tier-5-Mobs auf dem Hof.
   */
  private _handleRaidStarted(msg: GenericMsg): void {
    const tier = msg['tier'] as number | undefined;
    const wave = msg['wave'] as number | undefined;
    const by = msg['by'] as string | undefined;
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;

    // Toast-Text: kompakt, aber alle relevanten Infos.
    const parts: string[] = ['⚔️ Raid startet'];
    if (tier != null) parts.push(`T${tier}`);
    if (wave != null) parts.push(`Welle ${wave}`);
    if (by) parts.push(`(${by})`);
    const text = parts.join(' ');
    this.toast.show(text, 'warn', 8000);

    // Chronik-Eintrag — analog `_handleWorldEvent`-Form, damit das Panel
    // einheitlich rendert. ID + ISO-Timestamp lokal, weil Backend kein
    // `event`-Wrapper-Frame nachschickt.
    const ev: WorldEvent = {
      id: `raid_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      kind: 'raid_started',
      title: text,
      description: text,
      ts: new Date().toISOString(),
      x,
      y,
    };
    const nextEvents = [...this.events(), ev];
    if (nextEvents.length > 50) nextEvents.splice(0, nextEvents.length - 50);
    this.events.set(nextEvents);
  }

  // ── Quests + Factions ──

  private _handleQuestsUpdate(msg: GenericMsg): void {
    const quests = msg['quests'] as readonly Quest[] | undefined;
    if (quests) this.quests.set(quests);
  }

  private _handleQuestNew(msg: GenericMsg): void {
    const q = msg['quest'] as Quest | undefined;
    if (!q) return;
    this.quests.set([...this.quests(), q]);
  }

  private _handleQuestProgress(msg: GenericMsg): void {
    const q = msg['quest'] as Quest | undefined;
    if (!q) return;
    this.quests.set(
      this.quests().map((cur) => (cur.quest_id === q.quest_id ? q : cur)),
    );
  }

  private _handleQuestClosed(msg: GenericMsg): void {
    const id = msg['quest_id'] as number | undefined;
    if (id == null) return;
    this.quests.set(this.quests().filter((q) => q.quest_id !== id));
  }

  private _handleFactionsUpdate(msg: GenericMsg): void {
    const facs = msg['factions'] as readonly FactionReputation[] | undefined;
    if (facs) this.factions.set(facs);
  }

  // ── Talents + Spells ──

  private _handleTalentsUpdate(msg: GenericMsg): void {
    const tree = msg['talents'] as TalentTree | undefined;
    if (tree) this.talents.set(tree);
  }

  private _handleTalentLearned(msg: GenericMsg): void {
    const tree = msg['talents'] as TalentTree | undefined;
    if (tree) {
      this.talents.set(tree);
      return;
    }
    const learnedId = msg['talent_id'] as string | undefined;
    if (!learnedId) return;
    const cur = this.talents();
    if (!cur) return;
    if (cur.learned.includes(learnedId)) return;
    this.talents.set({ ...cur, learned: [...cur.learned, learnedId] });
  }

  private _handleCastStarted(msg: GenericMsg): void {
    const spellId = msg['spell_id'] as string | undefined;
    const duration = msg['cast_time_ms'] as number | undefined;
    if (!spellId) return;
    this.activeCast.set({
      spell_id: spellId,
      duration_ms: duration ?? 0,
      started_at_ms: Date.now(),
    });
  }

  /** H2.4 — `cast_finished {spell_id?, cooldown_ms?}`. Räumt den aktiven
   *  Cast ab UND schreibt den Cooldown in `spellCooldowns`, falls Backend
   *  einen Wert mitschickt. Hotbar liest den Rest lazy per `Date.now()`. */
  private _handleCastFinished(msg: GenericMsg): void {
    this.activeCast.set(null);
    const spellId = msg['spell_id'] as string | undefined;
    const cooldownMs = msg['cooldown_ms'] as number | undefined;
    if (!spellId || !cooldownMs || cooldownMs <= 0) return;
    const next = new Map(this.spellCooldowns());
    next.set(spellId, Date.now() + cooldownMs);
    this.spellCooldowns.set(next);
  }

  // ── H2.3 — Spell-Target-Selection-Mode ──

  /** Vom Spellbook (bzw. Hotbar in F-final) aufgerufen, wenn ein Spell
   *  mit `target_kind ∈ {single, aoe, ground, group, downed}` gecastet
   *  werden soll. Setzt das Signal — das `<app-spell-target-overlay>`
   *  pickt es auf und rendert seinen Click-Intercept-Layer. */
  beginSpellTargeting(spell: SpellEntry): void {
    this.castingSpell.set(spell);
  }

  /** Cancelt einen offenen Target-Pick (ESC oder programmatisch nach
   *  erfolgreichem Cast). */
  cancelSpellTarget(): void {
    this.castingSpell.set(null);
  }

  // ── H2.6 — Container-Action-Target-Mode ──

  /** Vom Chest-Panel aufgerufen für Container-Aktionen, die einen Tile-
   *  Target brauchen (Auffüllen am Wasser, Gießen auf Acker). */
  beginContainerAction(args: {
    readonly action: 'fill_container' | 'water_plant';
    readonly item_id: number;
    readonly item_name: string;
  }): void {
    this.containerAction.set(args);
  }

  cancelContainerAction(): void {
    this.containerAction.set(null);
  }

  private _handleSpellLearned(msg: GenericMsg): void {
    const learned = msg['learned'] as readonly string[] | undefined;
    if (learned) {
      this.spells.set({ ...this.spells(), learned });
      return;
    }
    const id = msg['spell_id'] as string | undefined;
    if (!id) return;
    const cur = this.spells();
    if (cur.learned.includes(id)) return;
    this.spells.set({ ...cur, learned: [...cur.learned, id] });
  }

  // ── Interaktions-Modals (F-extras-1) ──

  /** Vom Dialog-Panel aufgerufen, wenn der Spieler einen NPC anspricht. */
  openDialog(args: {
    readonly npc_id: number;
    readonly npc_name: string;
    readonly npc_kind: string;
    readonly backstory: string;
  }): void {
    // Stale Quest-Status vom vorherigen NPC verwerfen — sonst zeigt das
    // Dialog-Panel beim Sprecher-Wechsel kurz die alten Offers (H1.8).
    const prev = this.activeDialog();
    if (!prev || prev.npc_id !== args.npc_id) {
      this.activeNpcQuestStatus.set(null);
    }
    this.activeDialog.set({
      npc_id: args.npc_id,
      npc_name: args.npc_name,
      npc_kind: args.npc_kind,
      backstory: args.backstory,
      history: [],
      waiting: false,
    });
  }

  closeDialog(): void {
    this.activeDialog.set(null);
    this.activeNpcQuestStatus.set(null);
  }

  /** Erweitert den Dialog-Verlauf um eine Bubble. */
  appendDialogBubble(side: 'user' | 'npc', text: string, opts?: { readonly typing?: boolean }): void {
    const cur = this.activeDialog();
    if (!cur) return;
    this.activeDialog.set({
      ...cur,
      history: [...cur.history, { side, text, typing: opts?.typing }],
    });
  }

  /** Setzt das `waiting`-Flag (während Server-Reply pending ist). */
  setDialogWaiting(waiting: boolean): void {
    const cur = this.activeDialog();
    if (!cur) return;
    this.activeDialog.set({ ...cur, waiting });
  }

  private _handleNpcReply(msg: GenericMsg): void {
    const cur = this.activeDialog();
    if (!cur) return;
    const text = msg['text'] as string | undefined;
    if (!text) return;
    // Letzte typing-Bubble durch die echte Antwort ersetzen, sonst anhängen.
    const idx = [...cur.history].reverse().findIndex((b) => b.typing && b.side === 'npc');
    let history: typeof cur.history;
    if (idx >= 0) {
      const realIdx = cur.history.length - 1 - idx;
      const next = cur.history.slice();
      next[realIdx] = { side: 'npc', text };
      history = next;
    } else {
      history = [...cur.history, { side: 'npc', text }];
    }
    this.activeDialog.set({ ...cur, history, waiting: false });
  }

  closeChest(): void { this.activeChest.set(null); }
  closeCrafting(): void { this.activeCrafting.set(null); }
  closeTrade(): void { this.activeTrade.set(null); }
  closeQuestBoard(): void { this.activeQuestBoard.set(null); }

  private _handleQuestBoardOpen(msg: GenericMsg): void {
    const boardId = msg['board_id'] as number | undefined;
    if (boardId == null) return;
    const offers = (msg['offers'] as readonly {
      readonly template_id: string;
      readonly title: string;
      readonly description?: string;
      readonly quest_type?: string;
      readonly objective?: Readonly<Record<string, unknown>>;
      readonly reward?: Readonly<Record<string, number | string>>;
      readonly tier?: number;
    }[] | undefined) ?? [];
    this.activeQuestBoard.set({ board_id: boardId, offers });
  }

  private _handleNpcQuestStatus(msg: GenericMsg): void {
    const npcId = msg['npc_id'] as number | undefined;
    if (npcId == null) return;
    const offers = (msg['offers'] as readonly {
      readonly template_id: string;
      readonly title: string;
      readonly description?: string;
      readonly tier?: number;
    }[] | undefined) ?? [];
    const turnins = (msg['turnins'] as readonly {
      readonly quest_id: number;
      readonly title: string;
    }[] | undefined) ?? [];
    this.activeNpcQuestStatus.set({ npc_id: npcId, offers, turnins });
  }

  /** Wird vom Dialog-Panel beim Öffnen/Schließen aufgerufen, damit stale
   *  `npc_quest_status`-Daten nicht zwischen NPC-Wechseln durchblutet
   *  werden (H1.8). */
  clearNpcQuestStatus(): void { this.activeNpcQuestStatus.set(null); }

  private _handleChestOpen(msg: GenericMsg): void {
    const id = msg['chest_id'] as number | undefined;
    const items = msg['items'] as readonly { readonly id: number; readonly kind: string; readonly name: string; readonly quantity?: number; readonly quality?: string }[] | undefined;
    if (id == null) return;
    this.activeChest.set({ chest_id: id, items: items ?? [] });
  }

  private _handleChestAdd(msg: GenericMsg): void {
    const cur = this.activeChest();
    if (!cur) return;
    const cid = msg['chest_id'] as number | undefined;
    if (cid !== cur.chest_id) return;
    const item = msg['item'] as { readonly id: number; readonly kind: string; readonly name: string; readonly quantity?: number; readonly quality?: string } | undefined;
    if (!item) return;
    this.activeChest.set({ ...cur, items: [...cur.items, item] });
  }

  private _handleChestRemove(msg: GenericMsg): void {
    const cur = this.activeChest();
    if (!cur) return;
    const cid = msg['chest_id'] as number | undefined;
    if (cid !== cur.chest_id) return;
    const itemId = msg['item_id'] as number | undefined;
    if (itemId == null) return;
    this.activeChest.set({ ...cur, items: cur.items.filter((it) => it.id !== itemId) });
  }

  private _handleCraftingOpen(msg: GenericMsg): void {
    const station = msg['station'] as string | undefined;
    const recipes = msg['recipes'] as readonly {
      readonly output: string;
      readonly category?: string;
      readonly requires?: string | null;
      readonly inputs: readonly { readonly kind: string; readonly quantity: number }[];
    }[] | undefined;
    if (!station) return;
    this.activeCrafting.set({ station, recipes: recipes ?? [] });
  }

  private _handleTradeOpen(msg: GenericMsg): void {
    const npcId = msg['npc_id'] as number | undefined;
    if (npcId == null) return;
    this.activeTrade.set({
      npc_id: npcId,
      npc_name: (msg['npc_name'] as string | undefined) ?? '',
      coins: (msg['coins'] as number | undefined) ?? 0,
      offerings: (msg['offerings'] as readonly {
        readonly kind: string;
        readonly name: string;
        readonly price: number;
        readonly sprite_path?: string;
      }[] | undefined) ?? [],
    });
  }

  // ── Chat (F14) ──

  /** Begrenzte Ring-Größe — vermeidet Memory-Blow-up bei Long-Sessions. */
  private static readonly CHAT_MAX = 200;

  private _handleChat(msg: GenericMsg): void {
    const from = msg['from'] as string | undefined;
    const text = msg['text'] as string | undefined;
    if (!text) return;
    this._pushChat({ kind: 'player', from, text });
  }

  private _handleGroupChat(msg: GenericMsg): void {
    const from = msg['from'] as string | undefined;
    const text = msg['text'] as string | undefined;
    if (!text) return;
    this._pushChat({ kind: 'group', from, text });
  }

  /** Wird vom Chat-Panel verwendet, um lokale System-/Error-/Self-Linien
   *  einzufügen. */
  appendChat(entry: {
    readonly kind: 'system' | 'error' | 'self';
    readonly from?: string;
    readonly text: string;
  }): void {
    this._pushChat(entry);
  }

  private _pushChat(entry: {
    readonly kind: 'player' | 'group' | 'system' | 'error' | 'self';
    readonly from?: string;
    readonly text: string;
  }): void {
    const id = this._nextChatId++;
    const next = [...this.chatLog(), { id, ...entry }];
    if (next.length > GameStateService.CHAT_MAX) {
      next.splice(0, next.length - GameStateService.CHAT_MAX);
    }
    this.chatLog.set(next);
  }

  // ── Research (F-extras-2) ──

  private _handleResearchUpdate(msg: GenericMsg): void {
    const cur = this.research();
    // Fehler-Branch (not_enough_points): nur Pool aktualisieren, Nodes
    // unverändert (Legacy frontend/legacy/app.js Z. 5998-6001).
    if (msg['error'] === 'not_enough_points') {
      const pool = msg['pool'] as number | undefined;
      if (pool != null) this.research.set({ ...cur, pool });
      return;
    }
    const nodeId = msg['node_id'] as string | undefined;
    const points = msg['points'] as number | undefined;
    const done = msg['done'] as boolean | undefined;
    const pool = msg['pool'] as number | undefined;
    if (!nodeId) {
      if (pool != null) this.research.set({ ...cur, pool });
      return;
    }
    const node = cur.nodes[nodeId];
    if (!node) {
      if (pool != null) this.research.set({ ...cur, pool });
      return;
    }
    const updatedNode: ResearchNode = {
      ...node,
      points: points ?? node.points,
      done: done ?? node.done,
    };
    const nextNodes: Record<string, ResearchNode> = { ...cur.nodes, [nodeId]: updatedNode };
    // Wenn dieser Knoten fertig wurde, alle Folge-Knoten available schalten
    // (Legacy frontend/legacy/app.js Z. 6010-6013).
    if (done) {
      for (const [otherId, other] of Object.entries(cur.nodes)) {
        if (otherId === nodeId) continue;
        const prereqs = other.prereq ?? [];
        if (prereqs.includes(nodeId) && !other.available) {
          nextNodes[otherId] = { ...other, available: true };
        }
      }
    }
    this.research.set({
      ...cur,
      nodes: nextNodes,
      pool: pool ?? cur.pool,
    });
  }

  private _handleResearchPoolUpdate(msg: GenericMsg): void {
    const pool = msg['pool'] as number | undefined;
    if (pool == null) return;
    this.research.set({ ...this.research(), pool });
  }

  // ── Bills (F-extras-2) ──

  private _handleBillsUpdate(msg: GenericMsg): void {
    const bills = msg['bills'] as readonly Bill[] | undefined;
    this.bills.set(bills ?? []);
  }

  private _handleBillProgress(msg: GenericMsg): void {
    const billId = msg['bill_id'] as number | undefined;
    const completed = msg['completed'] as number | undefined;
    const target = msg['target'] as number | undefined;
    if (billId == null) return;
    this.bills.set(
      this.bills().map((b) =>
        b.id === billId
          ? {
              ...b,
              completed: completed ?? b.completed,
              target_count: target ?? b.target_count,
              status: 'active',
            }
          : b,
      ),
    );
  }

  private _handleBillDone(msg: GenericMsg): void {
    const billId = msg['bill_id'] as number | undefined;
    if (billId == null) return;
    this.bills.set(this.bills().filter((b) => b.id !== billId));
  }

  private _handleBillBlocked(msg: GenericMsg): void {
    const billId = msg['bill_id'] as number | undefined;
    if (billId == null) return;
    this.bills.set(
      this.bills().map((b) => (b.id === billId ? { ...b, status: 'blocked' } : b)),
    );
  }

  // ── Sign-Inspect (F-extras-3) ──

  private _handleSignInspect(msg: GenericMsg): void {
    const slug = msg['slug'] as string | undefined;
    if (!slug) return;
    const label = (msg['label'] as string | undefined) ?? slug;
    this.activeSignInspect.set({ slug, label });
  }

  closeSignInspect(): void { this.activeSignInspect.set(null); }

  // ── Dungeons (Welle H1-A — H1.10 / H1.11) ──
  //
  // 6 Frames vom Backend:
  //   • dungeon_enter         — Floor-0-Betreten (mit tiles, spawn, features)
  //   • dungeon_floor_change  — Treppe rauf/runter (gleicher Floor-State,
  //                              neue tiles + neuer spawn)
  //   • dungeon_exit          — Treppe Floor-0 hoch → zurück zur Overworld
  //   • dungeon_collapsed     — Dungeon ist abgelaufen / eingestürzt;
  //                              Spieler wird vom Backend zur Overworld
  //                              gebeamt (Toast als visuelles Feedback)
  //   • dungeon_sense         — Spüre-Item: kurzlebige Position-Liste
  //                              (Minimap-Pulse, H3.10)
  //   • dungeon_chest_opened  — Truhe geöffnet (Sprite-Swap im Floor)
  //
  // Architektur: Wir aktualisieren mehrere parallele Signals (statt eines
  // großen Bündels), damit unterschiedliche Konsumenten unabhängig auf das
  // reagieren können was sie interessiert:
  //   • dungeonFloor      → Phaser-Renderer (tile-map + features layer)
  //   • inDungeon         → Click-Routing in WorldScene (Subagent C)
  //   • dungeonChests     → dito (für `dungeon_chest`-Intent-Auswahl)
  //   • dungeonSensePulse → Minimap-Component (Polish, H3.10)
  //
  // Außerdem: bei `dungeon_enter` / `floor_change` / `exit` setzen wir
  // die Spieler-Position direkt, damit der Phaser-Player-Sprite + Kamera
  // ohne Verzögerung am Spawn stehen.

  private _handleDungeonEnter(msg: GenericMsg): void {
    const floor = this._buildDungeonFloorFromMsg(msg);
    if (!floor) return;
    this.dungeonFloor.set(floor);
    this.inDungeon.set(true);
    this._syncDungeonChestsFromFloor(floor);
    this._patchPlayer({ x: floor.spawn.x, y: floor.spawn.y });
    // Backend liefert `npcs` (NUR die Floor-Mobs) als Feld im Frame
    // (siehe `dungeon_floor_payload`). Overworld-NPCs müssen weg, damit
    // sie nicht durch die Wände des Dungeons hindurchscheinen.
    const npcs = msg['npcs'] as readonly NPC[] | undefined;
    if (npcs) this.npcsVisible.set(npcs);
  }

  private _handleDungeonFloorChange(msg: GenericMsg): void {
    const floor = this._buildDungeonFloorFromMsg(msg);
    if (!floor) return;
    this.dungeonFloor.set(floor);
    this.inDungeon.set(true);
    this._syncDungeonChestsFromFloor(floor);
    this._patchPlayer({ x: floor.spawn.x, y: floor.spawn.y });
    const npcs = msg['npcs'] as readonly NPC[] | undefined;
    if (npcs) this.npcsVisible.set(npcs);
  }

  private _handleDungeonExit(msg: GenericMsg): void {
    this.dungeonFloor.set(null);
    this.inDungeon.set(false);
    this.dungeonChests.set([]);
    const spawn = msg['spawn'] as { readonly x?: number; readonly y?: number } | undefined;
    if (spawn?.x != null && spawn?.y != null) {
      this._patchPlayer({ x: spawn.x, y: spawn.y });
    }
    // Backend sendet `chunks` als Feld direkt im dungeon_exit-Frame —
    // den selben Merge nutzen wie der normale `chunks`-Handler.
    const chunks = msg['chunks'] as readonly Chunk[] | undefined;
    if (chunks && chunks.length > 0) {
      const map = new Map<string, Chunk>();
      for (const c of this.chunks()) map.set(`${c.cx},${c.cy}`, c);
      for (const c of chunks) map.set(`${c.cx},${c.cy}`, c);
      this.chunks.set(Array.from(map.values()));
    }
    // Backend liefert auch `npcs` (Overworld-NPCs in der Nähe des Exit-
    // Punkts) — voll ersetzen, weil die NPCs des Dungeon-Floors weg sind.
    const npcs = msg['npcs'] as readonly NPC[] | undefined;
    if (npcs) this.npcsVisible.set(npcs);
  }

  private _handleDungeonCollapsed(msg: GenericMsg): void {
    // H2.15 — Dungeon-Collapsed-Notification. Backend hat den Spieler
    // bereits zur Overworld zurückgebeamt (dungeon_director cleanup); wir
    // räumen lokal den Dungeon-State auf und informieren über Toast UND
    // Chronik. Die Toast-Duration ist 8s — sonst wundert sich der Spieler,
    // warum er plötzlich im Wald steht, weil er es vielleicht verpasst hat.
    this.dungeonFloor.set(null);
    this.inDungeon.set(false);
    this.dungeonChests.set([]);
    const name = (msg['name'] as string | undefined) ?? 'Dungeon';
    const text = `💥 Dungeon „${name}" eingestürzt — du wurdest hinausgeworfen`;
    this.toast.show(text, 'warn', 8000);
    // Auch in die Chronik, damit der Spieler es nachschlagen kann.
    const ev: WorldEvent = {
      id: `dc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      kind: 'dungeon_collapsed',
      title: text,
      description: text,
      ts: new Date().toISOString(),
    };
    const nextEvents = [...this.events(), ev];
    if (nextEvents.length > 50) nextEvents.splice(0, nextEvents.length - 50);
    this.events.set(nextEvents);
  }

  private _handleDungeonSense(msg: GenericMsg): void {
    const dungeons = msg['dungeons'] as readonly {
      readonly x: number; readonly y: number; readonly radius?: number;
    }[] | undefined;
    if (!dungeons) return;
    this.dungeonSensePulse.set({
      at_ms: Date.now(),
      dungeons,
    });
  }

  private _handleDungeonChestOpened(msg: GenericMsg): void {
    const x = msg['x'] as number | undefined;
    const y = msg['y'] as number | undefined;
    if (x == null || y == null) return;
    // Click-Routing-Signal aktualisieren — die Truhe ist nicht mehr
    // klickbar (oder soll als „leer" angezeigt werden).
    this.dungeonChests.set(
      this.dungeonChests().map((c) =>
        c.x === x && c.y === y ? { ...c, opened: true } : c,
      ),
    );
    // Den rich-floor-state ebenfalls patchen, damit der Phaser-Renderer
    // beim nächsten Snapshot den Sprite-Swap macht (auch falls er gerade
    // einen vollen Re-Render auslöst).
    const cur = this.dungeonFloor();
    if (!cur || !cur.features?.chests) return;
    const nextChests = cur.features.chests.map((c) =>
      c.x === x && c.y === y ? { ...c, opened: true } : c,
    );
    this.dungeonFloor.set({
      ...cur,
      features: { ...cur.features, chests: nextChests },
    });
  }

  /** Baut den rich `dungeonFloor`-State aus einem `dungeon_enter` /
   *  `dungeon_floor_change`-Frame. Validiert die Pflichtfelder; bei
   *  fehlenden Feldern → null (Frame wird ignoriert, defensiv). */
  private _buildDungeonFloorFromMsg(
    msg: GenericMsg,
  ): ReturnType<typeof this.dungeonFloor> | null {
    const id = msg['dungeon_id'] as number | string | undefined;
    const tiles = msg['tiles'] as readonly (readonly number[])[] | undefined;
    const spawn = msg['spawn'] as { readonly x?: number; readonly y?: number } | undefined;
    const size = msg['size'] as number | undefined;
    const floorIdx = msg['floor_idx'] as number | undefined;
    const floorCount = msg['floor_count'] as number | undefined;
    if (id == null || !tiles || !spawn || spawn.x == null || spawn.y == null
        || size == null || floorIdx == null) {
      return null;
    }
    this._dungeonVersion += 1;
    return {
      id,
      name: msg['name'] as string | undefined,
      floorIdx,
      floorCount: floorCount ?? 1,
      size,
      tiles,
      spawn: { x: spawn.x, y: spawn.y },
      theme: msg['theme'] as string | undefined,
      themeData: msg['theme_data'] as {
        readonly label?: string;
        readonly wall_tint?: string | number | null;
        readonly floor_tint?: string | number | null;
        readonly ambient_color?: string | number | null;
        readonly ambient?: string | null;
      } | undefined,
      features: msg['features'] as {
        readonly chests?: readonly { readonly x: number; readonly y: number; readonly opened?: boolean }[];
        readonly traps?: readonly { readonly x: number; readonly y: number; readonly kind?: string }[];
        readonly decor?: readonly { readonly x: number; readonly y: number; readonly kind: string }[];
      } | undefined,
      version: this._dungeonVersion,
    };
  }

  /** Synct das schmale `dungeonChests`-Signal (Click-Routing) aus dem
   *  rich `dungeonFloor`-State. */
  private _syncDungeonChestsFromFloor(
    floor: NonNullable<ReturnType<typeof this.dungeonFloor>>,
  ): void {
    const chests = floor.features?.chests ?? [];
    this.dungeonChests.set(
      chests.map((c) => ({ x: c.x, y: c.y, opened: c.opened === true })),
    );
  }

  // ── Disaster (H1.16, H1.17) ──

  private _handleDisasterStarted(msg: GenericMsg): void {
    const kind = msg['kind'] as string | undefined;
    if (!kind) return;
    const next = new Set(this.activeDisasters());
    next.add(kind);
    this.activeDisasters.set(next);
    // H1.17 — Start-Toast. Idempotent — falls Backend zusätzlich einen `toast`
    // sendet, kriegt der Spieler zwei Hinweise, das ist sichtbar harmlos.
    this.toast.show(`⚠️ ${_disasterLabel(kind)} beginnt`, 'warn', 6000);
  }

  private _handleDisasterEnded(msg: GenericMsg): void {
    const kind = msg['kind'] as string | undefined;
    if (!kind) return;
    const next = new Set(this.activeDisasters());
    next.delete(kind);
    this.activeDisasters.set(next);
    this.toast.show(`✓ ${_disasterLabel(kind)} vorbei`, 'success', 4000);
  }

  // ── Toast-Triggers (H1.22 + H1.23) ──

  /**
   * H1.22 — Backend-`toast`-Frame durchreichen. Backend sendet `{type:'toast',
   * text:'...', kind?:'info'|'warn'|'error'|'success'}`. Vorher war der Case
   * ein expliziter No-op, dadurch versickerten >150 Toast-Strings pro Session.
   */
  private _handleBackendToast(msg: GenericMsg): void {
    const text = msg['text'] as string | undefined;
    if (!text) return;
    const rawKind = msg['kind'] as string | undefined;
    // Backend nutzt freie Strings; wir mappen alles außerhalb unseres
    // Type-Sets defensiv auf `info`, damit der Toast trotzdem rauskommt.
    const kind: 'info' | 'success' | 'warn' | 'error' =
      rawKind === 'success' || rawKind === 'warn' || rawKind === 'error'
        ? rawKind
        : 'info';
    this.toast.show(text, kind);
  }

  /**
   * Generischer Error-Toast-Builder für group/raid/loot-Fehler (H1.23).
   * Backend sendet typischerweise `{reason, ...}`; wir bauen einen lesbaren
   * Text aus `text`/`reason`/`detail` + Fallback-Label.
   */
  private _toastError(msg: GenericMsg, fallback: string): void {
    const text =
      (msg['text'] as string | undefined) ??
      (msg['reason'] as string | undefined) ??
      (msg['detail'] as string | undefined);
    this.toast.show(text ? `${fallback}: ${text}` : fallback, 'error');
  }

  /** Quest-New-Toast — wertet `quest.title` aus dem Backend-Frame aus. */
  private _toastQuestNew(msg: GenericMsg): void {
    const q = msg['quest'] as { readonly title?: string } | undefined;
    const title = q?.title ?? (msg['title'] as string | undefined);
    this.toast.show(title ? `📜 Neue Quest: ${title}` : '📜 Neue Quest erhalten.', 'success');
  }

  /**
   * H2.9 — Quest-Progress-Toast. Backend sendet `quest_progress` bei JEDEM
   * Objektiv-Tick (1/5, 2/5, …) — wir filtern auf Milestones:
   *   • Bei 25/50/75 % einer Objective
   *   • Bei Objective-Completion (done == true)
   *   • Bei 100 % der Quest (alle Objectives done) — falls Backend kein
   *     separates `quest_closed` schickt
   * Sonst kein Toast (vermeidet Spam bei „Töte 50 Wölfe").
   *
   * Wir ermitteln das „aktuell relevante" Objektiv heuristisch: das letzte
   * nicht-fertige plus den frischen Progress-Wert. Backend liefert manchmal
   * eine flache Form (`progress`, `required`, `objective`), manchmal das
   * volle Quest-Objekt — wir handeln defensiv beide.
   */
  private _toastQuestProgress(msg: GenericMsg): void {
    const q = msg['quest'] as
      | { readonly title?: string; readonly objectives?: readonly QuestObjective[] }
      | undefined;
    const title = q?.title ?? (msg['title'] as string | undefined);
    if (!title) return;

    // Flache Form bevorzugen, wenn vorhanden — sie zeigt die FRISCH
    // veränderte Objective an, die im Quest-Objekt nicht eindeutig wäre.
    const flatProgress = msg['progress'] as number | undefined;
    const flatRequired = msg['required'] as number | undefined;
    const flatDone = msg['done'] as boolean | undefined;
    const flatObjective = msg['objective'] as string | undefined;

    let progress: number | undefined = flatProgress;
    let required: number | undefined = flatRequired;
    let done: boolean | undefined = flatDone;
    let objectiveLabel: string | undefined = flatObjective;

    // Fallback: aus Quest-Objekt das letzte aktive Objective herauslesen.
    if (progress == null || required == null) {
      const objs = q?.objectives ?? [];
      // „aktuell relevant" = erstes nicht-fertiges, sonst letztes.
      const obj = objs.find((o) => !o.done) ?? objs[objs.length - 1];
      if (obj) {
        progress = obj.progress;
        required = obj.required;
        done = obj.done;
        objectiveLabel = obj.target ?? obj.kind;
      }
    }
    if (progress == null || required == null || required <= 0) return;

    // Milestone-Check: nur 25/50/75 % oder Objective-Done.
    const pct = Math.floor((progress / required) * 100);
    const isMilestone = pct === 25 || pct === 50 || pct === 75;
    const isComplete = done === true || progress >= required;
    if (!isMilestone && !isComplete) return;

    const label = objectiveLabel ? ` (${objectiveLabel})` : '';
    const text = `📋 ${title}${label}: ${progress}/${required}`;
    // Complete → success, sonst info (kurze Anzeige, niedrige Aufmerksamkeit).
    this.toast.show(text, isComplete ? 'success' : 'info', 3000);
  }

  /** Quest-Closed-Toast. */
  private _toastQuestClosed(msg: GenericMsg): void {
    const q = msg['quest'] as { readonly title?: string } | undefined;
    const title = q?.title ?? (msg['title'] as string | undefined);
    this.toast.show(
      title ? `Quest abgeschlossen: ${title}` : 'Quest abgeschlossen!',
      'success',
    );
  }

  /** Spell-Learned-Toast. Backend liefert je nach Pfad `spell_id` oder
   *  `spell_name`; wir fallen auf den `id`-String zurück. */
  private _toastSpellLearned(msg: GenericMsg): void {
    const name =
      (msg['spell_name'] as string | undefined) ??
      (msg['name'] as string | undefined) ??
      (msg['spell_id'] as string | undefined);
    if (!name) return;
    this.toast.show(`Du hast ${name} gelernt.`, 'success');
  }

  /** Talent-Learned-Toast. */
  private _toastTalentLearned(msg: GenericMsg): void {
    const name =
      (msg['talent_name'] as string | undefined) ??
      (msg['name'] as string | undefined) ??
      (msg['talent_id'] as string | undefined);
    if (!name) return;
    this.toast.show(`Talent gelernt: ${name}`, 'success');
  }

  // ── Misc ──

  private _warnUnknown(type: string): void {
    if (this._unknownWarned.has(type)) return;
    this._unknownWarned.add(type);
    // eslint-disable-next-line no-console
    console.warn('Unknown WS type:', type);
  }
}

// ─── Helpers (Modul-lokal) ─────────────────────────────────────────────

/** Disaster-Kind → Deutsche UI-Bezeichnung für Toasts und Tooltips. */
function _disasterLabel(kind: string): string {
  const map: Readonly<Record<string, string>> = {
    bloodmoon: 'Blutmond',
    dying_sun: 'Sterbende Sonne',
    thunderstorm: 'Gewittersturm',
    scorching_heat: 'Sengende Hitze',
    ash_rain: 'Aschenregen',
    wildfire: 'Waldbrand',
    pestilence: 'Pestilenz',
    locust_swarm: 'Heuschreckenschwarm',
    toxic_fog: 'Giftnebel',
  };
  return map[kind] ?? kind;
}
