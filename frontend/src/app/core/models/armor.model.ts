// Rüstungs-Stats — Spiegel von backend/item_stats.py ARMOR_STATS.

export interface ArmorStats {
  readonly defense: number;
  readonly weight: number;
  readonly block_chance?: number;
  readonly speed_bonus?: number;
  readonly crit_chance_bonus?: number;
}
