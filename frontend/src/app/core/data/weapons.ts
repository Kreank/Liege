// Waffen-Daten — portiert aus frontend/legacy/app.js Z. 1046-1067, 1741.
// WEAPON_STATS spiegelt backend/item_stats.py (Welle 19 Stat-Rebalance).
import type { WeaponStats } from '../models/weapon.model';

// Welle 33: Waffen-Reichweite (Tiles), spiegelt backend/item_stats.WEAPON_STATS.
export const WEAPON_RANGE: Readonly<Record<string, number>> = {
  sword: 1, axe: 1, mace: 1, dagger: 1, scythe: 1, greatsword: 1,
  spear: 2,
  bow: 5, crossbow: 6, throwing_knife: 3,
  staff: 4, wand: 4,
};

// Welle 35: Volle Waffen-Stats für Tooltips.
export const WEAPON_STATS: Readonly<Record<string, WeaponStats>> = {
  dagger:        { dmg: 6,  speed: 1.8,  crit: 0.22, crit_mult: 2.5, range: 1, two_h: false },
  sword:         { dmg: 11, speed: 1.0,  crit: 0.06, crit_mult: 1.5, range: 1, two_h: false },
  axe:           { dmg: 15, speed: 0.85, crit: 0.05, crit_mult: 1.7, range: 1, two_h: false, armor_pen: 0.10 },
  mace:          { dmg: 13, speed: 0.80, crit: 0.03, crit_mult: 1.6, range: 1, two_h: false, armor_pen: 0.35 },
  throwing_knife:{ dmg: 6,  speed: 1.6,  crit: 0.15, crit_mult: 2.0, range: 3, two_h: false },
  wand:          { dmg: 7,  speed: 1.3,  crit: 0.10, crit_mult: 1.5, range: 4, two_h: false },
  greatsword:    { dmg: 26, speed: 0.65, crit: 0.07, crit_mult: 1.9, range: 1, two_h: true },
  spear:         { dmg: 13, speed: 1.0,  crit: 0.08, crit_mult: 1.6, range: 2, two_h: true },
  scythe:        { dmg: 18, speed: 0.70, crit: 0.08, crit_mult: 1.9, range: 1, two_h: true, cleave: true },
  bow:           { dmg: 10, speed: 1.0,  crit: 0.10, crit_mult: 1.6, range: 5, two_h: true },
  crossbow:      { dmg: 22, speed: 0.50, crit: 0.15, crit_mult: 1.9, range: 6, two_h: true, armor_pen: 0.30 },
  staff:         { dmg: 9,  speed: 1.0,  crit: 0.08, crit_mult: 1.5, range: 4, two_h: true },
};

export const WEAPON_MATERIALS = [
  'wood', 'copper', 'iron', 'steel', 'silver', 'gold',
  'mithril', 'adamant', 'platinum', 'tungsten', 'crystal',
] as const;
export type WeaponMaterial = (typeof WEAPON_MATERIALS)[number];
