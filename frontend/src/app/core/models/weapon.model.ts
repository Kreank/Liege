// Waffen-Stats — Spiegel von backend/item_stats.py WEAPON_STATS.

export interface WeaponStats {
  readonly dmg: number;
  readonly speed: number;
  readonly crit: number;
  readonly crit_mult: number;
  readonly range: number;
  readonly two_h: boolean;
  readonly armor_pen?: number;
  readonly cleave?: boolean;
}
