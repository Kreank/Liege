// Quest-/Faction-Modelle (Backend-Vertrag).

export type QuestState = 'active' | 'completed' | 'failed' | 'available';

export interface QuestObjective {
  readonly kind: string;
  readonly target?: string;
  readonly progress: number;
  readonly required: number;
  readonly done: boolean;
}

export interface Quest {
  readonly quest_id: number;
  readonly template_id?: string;
  readonly title: string;
  readonly description?: string;
  readonly state: QuestState;
  readonly giver_npc_id?: number;
  /** Optionaler Ziel-NPC (für Deliver/Turn-in). Backend setzt das beim
   *  `quest_turn_in`-Hook auf den Receiver-NPC (`quests.py::ensure_…`). */
  readonly target_npc_id?: number;
  readonly objectives: readonly QuestObjective[];
  readonly rewards?: Readonly<Record<string, number | string>>;
  readonly is_main?: boolean;
}

/** Fraktions-Reputation-Eintrag. */
export interface FactionReputation {
  readonly faction_id: string;
  readonly goodwill: number;
  readonly tier?: string;
}
