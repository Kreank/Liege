// Player-State-Modelle (Backend-Vertrag — snake_case wie WS-Payload).

/** Pro Body-Part HP-Snapshot (Welle 28 — Body-Damage-System). */
export interface BodyPart {
  readonly name: string;
  readonly hp: number;
  readonly max_hp: number;
  readonly damaged?: boolean;
}

/** Attribut-Snapshot — 12 deutsche Slugs (Backend ws/character.py
 *  VALID_ATTRS). Alle optional weil Backend nur die allokierten Slugs
 *  sendet (z.B. {stärke: 3, weisheit: 2}, alle anderen 0). */
export interface PlayerAttributes {
  readonly stärke?: number;
  readonly ausdauer?: number;
  readonly energie?: number;
  readonly intelligenz?: number;
  readonly weisheit?: number;
  readonly ausweichen?: number;
  readonly geschick?: number;
  readonly verteidigung?: number;
  readonly charisma?: number;
  readonly krit_rate?: number;
  readonly krit_schaden?: number;
  readonly schleichen?: number;
  /** Punkte, die noch zu verteilen sind. */
  readonly unspent?: number;
}

/** Alle 12 Attribut-Slugs als Konstante (Reihenfolge = UI-Reihenfolge). */
export const ATTRIBUTE_KEYS = [
  'stärke', 'geschick', 'ausdauer', 'energie',
  'intelligenz', 'weisheit', 'verteidigung', 'ausweichen',
  'krit_rate', 'krit_schaden', 'charisma', 'schleichen',
] as const;
export type AttributeKey = (typeof ATTRIBUTE_KEYS)[number];

/** Stat-Sheet (abgeleitete Werte aus Attributen + Equipment). */
export interface PlayerStats {
  readonly damage?: number;
  readonly defense?: number;
  readonly crit_chance?: number;
  readonly crit_damage?: number;
  readonly attack_speed?: number;
  readonly move_speed?: number;
  readonly carry_weight?: number;
  readonly mana_regen?: number;
  readonly hp_regen?: number;
}

/** Skill-Eintrag (Welle 8 — Skill-XP-System). */
export interface SkillEntry {
  readonly level: number;
  readonly xp: number;
  readonly xp_next: number;
}

/** Voller Player-Snapshot. */
export interface PlayerSnapshot {
  readonly player_id: number;
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
  readonly x: number;
  readonly y: number;
  readonly power_tier?: number;
  readonly body_parts?: readonly BodyPart[];
  readonly attributes?: PlayerAttributes;
  readonly stats?: PlayerStats;
  readonly skills?: Readonly<Record<string, SkillEntry>>;
  readonly preset?: string | null;
  readonly is_downed?: boolean;
  readonly is_resting?: boolean;
  readonly is_sprinting?: boolean;
}

/** Online-Player-Eintrag (für Renderer; nur die Anzeige-Felder). */
export interface OnlinePlayer {
  readonly player_id: number;
  readonly name: string;
  readonly x: number;
  readonly y: number;
  readonly preset?: string | null;
  readonly hp?: number;
  readonly max_hp?: number;
}

/** Status-Effekt-Eintrag (Buffs/Debuffs). */
export interface StatusEffect {
  readonly id: string;
  readonly kind: string;
  readonly label?: string;
  readonly remaining_ms?: number;
  readonly stacks?: number;
}
