// Talents + Spells (Backend-Vertrag).

export interface TalentNode {
  readonly id: string;
  readonly name: string;
  readonly description?: string;
  readonly tier: number;
  readonly cost: number;
  readonly requires?: readonly string[];
}

export interface TalentTree {
  readonly learned: readonly string[];
  readonly points: number;
  readonly tree?: readonly TalentNode[];
}

export interface SpellEntry {
  readonly id: string;
  readonly name: string;
  readonly description?: string;
  readonly mana_cost?: number;
  readonly cast_ms?: number;
  readonly tier?: number;
}

export interface SpellState {
  readonly catalog: readonly SpellEntry[];
  readonly learned: readonly string[];
}
