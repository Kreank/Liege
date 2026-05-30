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

/** Schule des Zaubers — Spellbook-Tabs filtern darauf. */
export type SpellSchool = 'healer' | 'mage';

/** Spell-Definitions-Eintrag aus dem Backend-Catalog (siehe
 *  `backend/spells.py::SPELLS`). */
export interface SpellEntry {
  readonly id: string;
  readonly name: string;
  readonly description?: string;
  readonly mana_cost?: number;
  readonly cast_time_ms?: number;
  readonly cooldown_ms?: number;
  readonly skill_req?: number;
  readonly icon_path?: string;
  readonly school?: SpellSchool;
  readonly target_kind?: 'self' | 'group' | 'enemy' | 'tile' | 'downed';
  readonly tier?: number;
}

export interface SpellState {
  readonly catalog: readonly SpellEntry[];
  readonly learned: readonly string[];
}
