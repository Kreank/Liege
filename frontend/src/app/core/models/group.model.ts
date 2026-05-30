// Party/Raid-Modelle (Backend-Vertrag).

/** Loot-Rule für die Gruppe. */
export type LootRule =
  | 'free_for_all'
  | 'leader_decides'
  | 'round_robin'
  | 'need_before_greed';

/** Mitglied einer Gruppe. */
export interface GroupMember {
  readonly player_id: number;
  readonly name: string;
  readonly is_leader: boolean;
  readonly online: boolean;
  readonly x?: number;
  readonly y?: number;
  readonly hp?: number;
  readonly max_hp?: number;
}

/** Gruppen-Snapshot (Party oder Raid). */
export interface Group {
  readonly group_id: number;
  readonly kind: 'party' | 'raid';
  readonly leader_id: number;
  readonly members: readonly GroupMember[];
  readonly loot_rule: LootRule;
}

/** Eingehende Gruppen-Einladung. */
export interface GroupInvite {
  readonly group_id: number;
  readonly inviter_name: string;
  readonly group_size: number;
  readonly kind?: 'party' | 'raid';
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
