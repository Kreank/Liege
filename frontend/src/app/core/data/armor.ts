// Rüstungs-Daten — portiert aus frontend/legacy/app.js Z. 1068-1074, 1743.
import type { ArmorStats } from '../models/armor.model';

export const ARMOR_STATS: Readonly<Record<string, ArmorStats>> = {
  helmet:     { defense: 8,  weight: 3 },
  chestplate: { defense: 22, weight: 8 },
  gloves:     { defense: 4,  weight: 1, crit_chance_bonus: 0.01 },
  shield:     { defense: 15, weight: 5, block_chance: 0.15 },
  boots:      { defense: 6,  weight: 2, speed_bonus: 0.05 },
};

export const ARMOR_MATERIALS = [
  'cloth', 'leather', 'fur', 'copper', 'iron', 'silver',
  'gold', 'mithril', 'adamant', 'platinum', 'tungsten', 'crystal',
] as const;
export type ArmorMaterial = (typeof ARMOR_MATERIALS)[number];
