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
import type { FactionReputation, Quest } from '../models/quest.model';
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
      case 'npc_quest_status':
        // UI-Side-Effects (Sprechblase, Mood-Icon) — kein State-Update.
        break;

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
      case 'weather':              this._handleWeather(msg); break;

      // ─── Zeit ───────────────────────────────────────────────────────
      case 'time_update':          this._handleTimeUpdate(msg); break;

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
      case 'group_error':
      case 'raid_error':           /* Toast — kein State */ break;
      case 'raid_started':         /* Visual-Event */ break;
      case 'loot_roll_started':    this._handleLootRollStarted(msg); break;
      case 'loot_roll_resolved':   this.activeLootRoll.set(null); break;
      case 'loot_roll_voted':
      case 'loot_rule_changed':
        // loot_voted: nur Live-Vote-Count, der Overlay zeigt das nicht; das
        // Lootrule-Update wird vom späteren Party-Settings-Panel konsumiert.
        break;

      // ─── Quests + Factions ──────────────────────────────────────────
      case 'quests_update':        this._handleQuestsUpdate(msg); break;
      case 'quest_new':            this._handleQuestNew(msg); break;
      case 'quest_progress':       this._handleQuestProgress(msg); break;
      case 'quest_closed':         this._handleQuestClosed(msg); break;
      case 'factions_update':      this._handleFactionsUpdate(msg); break;
      case 'quest_board_open':     /* UI-Trigger */ break;

      // ─── Talents + Spells ───────────────────────────────────────────
      case 'talents_update':       this._handleTalentsUpdate(msg); break;
      case 'talent_learned':       this._handleTalentLearned(msg); break;
      case 'spell_learned':        this._handleSpellLearned(msg); break;
      case 'cast_started':         this._handleCastStarted(msg); break;
      case 'cast_interrupted':
      case 'cast_finished':        this.activeCast.set(null); break;

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

      // ─── Dungeons / Disasters / Misc ────────────────────────────────
      case 'dungeon_enter':
      case 'dungeon_exit':
      case 'dungeon_floor_change':
      case 'dungeon_collapsed':
      case 'dungeon_sense':
      case 'dungeon_chest_opened':
      case 'trap_triggered':
      case 'disaster_started':
      case 'disaster_ended':
      case 'lightning_strike':
      case 'earthquake_shake':
      case 'visual_effect':
      case 'chat':                 this._handleChat(msg); break;
      case 'character_created':
      case 'character_name_check':
      case 'toast':
        // Reine UI-/Audio-Effekte oder Modals — keine Signals zu updaten.
        break;

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
    // sich selbst.
    this.events.set([...this.events(), ev]);
  }

  private _handleWeather(msg: GenericMsg): void {
    const kind = msg['kind'] as string | undefined;
    const intensity = msg['intensity'] as number | undefined;
    if (!kind) return;
    this.weather.set({ kind, intensity: intensity ?? 0 });
  }

  private _handleTimeUpdate(msg: GenericMsg): void {
    const t = msg['time'] as TimeSnapshot | undefined;
    if (t) this.time.set(t);
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
    this.activeDialog.set({
      npc_id: args.npc_id,
      npc_name: args.npc_name,
      npc_kind: args.npc_kind,
      backstory: args.backstory,
      history: [],
      waiting: false,
    });
  }

  closeDialog(): void { this.activeDialog.set(null); }

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

  // ── Misc ──

  private _warnUnknown(type: string): void {
    if (this._unknownWarned.has(type)) return;
    this._unknownWarned.add(type);
    // eslint-disable-next-line no-console
    console.warn('Unknown WS type:', type);
  }
}
