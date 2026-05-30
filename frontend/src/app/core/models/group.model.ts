// Party/Raid-Modelle (Backend-Vertrag).
//
// Backend-Quelle: `backend/groups.py::group_snapshot` →
//   { id, kind: 'party'|'raid_small'|'raid_large', leader: <name>, name,
//     loot_rule, your_role, members: [{name, role, sub_party, online, x, y}] }
// Invite: `backend/ws/social.py::handle_group_invite` →
//   { invite_id, group_id, from, kind, expires_at } (Legacy nutzt id-Feld
//   serverseitig — der Renderer im Frontend liest hier `invite_id`).

/** Loot-Rule für die Gruppe. */
export type LootRule =
  | 'free_for_all'
  | 'leader_decides'
  | 'round_robin'
  | 'need_before_greed';

/** Gruppen-Art — Backend-Kind: party / raid_small / raid_large. */
export type GroupKind = 'party' | 'raid_small' | 'raid_large';

/** Mitglieds-Rolle im Backend-Snapshot. */
export type GroupRole = 'leader' | 'assist' | 'member';

/** Mitglied einer Gruppe (Player-Name als ID — siehe Backend). */
export interface GroupMember {
  readonly name: string;
  readonly role: GroupRole;
  readonly sub_party: number;
  readonly online: boolean;
  readonly x?: number | null;
  readonly y?: number | null;
  /** Optional — wird vom Backend noch nicht geliefert, vom HUD nur konsumiert
   *  falls vorhanden. */
  readonly hp?: number;
  readonly max_hp?: number;
  readonly mana?: number;
  readonly max_mana?: number;
}

/** Gruppen-Snapshot. */
export interface Group {
  readonly id: number;
  readonly kind: GroupKind;
  /** Leader-Player-Name (kein numerischer ID — Legacy-Vertrag). */
  readonly leader: string;
  readonly name?: string | null;
  readonly loot_rule: LootRule;
  /** Rolle des eigenen Spielers in dieser Gruppe. */
  readonly your_role: GroupRole;
  readonly members: readonly GroupMember[];
}

/** Eingehende Gruppen-Einladung. */
export interface GroupInvite {
  readonly invite_id: number;
  readonly group_id: number;
  readonly from: string;
  readonly kind: GroupKind;
  readonly expires_at?: string;
}

/** Loot-Roll-Overlay-State. */
export interface LootRollState {
  readonly roll_id: number;
  readonly item: {
    readonly kind: string;
    readonly quantity?: number;
    readonly quality?: string;
  };
  readonly votes: Readonly<Record<number, 'need' | 'greed' | 'pass'>>;
  readonly expires_at_ms?: number;
}
