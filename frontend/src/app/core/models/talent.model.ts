// Talents + Spells (Backend-Vertrag).

export interface TalentNode {
  readonly id: string;
  readonly name: string;
  readonly description?: string;
  readonly tier: number;
  readonly cost: number;
  readonly requires?: readonly string[];
  /** Mindest-Skill-Level (Backend `skill_min`). Tier-2-Talente brauchen z.B. 8. */
  readonly skill_min?: number;
  /** Vom Backend vorberechneter Status (learned/available/needs_points/locked),
   *  berücksichtigt skill_min + prereq + Punkte. Die UI nutzt ihn bevorzugt,
   *  damit kein „Lernen"-Button erscheint, den das Backend ablehnt. */
  readonly status?: string;
}

export interface TalentTree {
  readonly learned: readonly string[];
  readonly points: number;
  readonly tree?: readonly TalentNode[];
}

/** Schule des Zaubers — Spellbook-Tabs filtern darauf. */
export type SpellSchool = 'healer' | 'mage';

/** Mögliche Werte von `target_kind` (Backend-Vertrag, siehe
 *  `backend/spells.py::SPELLS`). H2.3 routet darauf:
 *    • `self`         → kein Pick, direkt casten.
 *    • `group`        → kein Pick (alle nahen Gruppen-Member werden
 *                       serverseitig betroffen). Direkt casten.
 *    • `single`       → NPC-Pick (Enemy/Friendly).
 *    • `aoe`          → Tile-Pick (Ground-Center für Radius-Effekt).
 *    • `ground`       → Tile-Pick.
 *    • `downed`       → Pick auf einen downed Mitspieler (Single-Pick).
 *  Legacy-Werte `enemy`/`tile` werden vom Frontend defensiv akzeptiert,
 *  auch wenn das Backend sie aktuell nicht emittiert. */
export type SpellTargetKind =
  | 'self'
  | 'group'
  | 'single'
  | 'aoe'
  | 'ground'
  | 'downed'
  | 'enemy'
  | 'tile';

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
  /** Welle 53: Zauber-Kategorie (grund/flaeche/heilung/schutz/fluch) — das
   *  Spellbook gruppiert danach statt nach Schule. */
  readonly category?: string;
  readonly target_kind?: SpellTargetKind;
  /** Maximale Cast-Entfernung in Tiles (Backend `range`). H2.3 Range-Circle. */
  readonly range?: number;
  /** Wirkradius für AoE-Spells in Tiles (Backend `radius`). */
  readonly radius?: number;
  readonly tier?: number;
}

export interface SpellState {
  readonly catalog: readonly SpellEntry[];
  readonly learned: readonly string[];
}
