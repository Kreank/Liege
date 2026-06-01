// Waffen-Daten — portiert aus frontend/legacy/app.js Z. 1046-1067, 1741.
// WEAPON_STATS spiegelt backend/item_stats.py (Welle 19 Stat-Rebalance).
import type { WeaponStats } from '../models/weapon.model';

// Welle 33: Waffen-Reichweite (Tiles), spiegelt backend/item_stats.WEAPON_STATS.
export const WEAPON_RANGE: Readonly<Record<string, number>> = {
  sword: 1, axe: 1, mace: 1, dagger: 1, scythe: 1, greatsword: 1,
  spear: 2,
  bow: 5, crossbow: 6, throwing_knife: 3,
  staff: 4, wand: 4,
  katana: 1, halberd: 2, lance: 3, runeblade: 1, sickle_weapon: 1,
  trident: 2, twinblade: 1,
  rusty_sword: 1, iron_sword: 1, iron_spear: 2, bone_dagger: 1, bone_spear: 2,
  bone_staff: 4, bone_warhammer: 1, shaman_stick: 4, worn_bow: 5,
  living_wood_bow: 5, demon_forge_hammer: 1,
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
  // Welle 51: erweiterte Waffen (Spiegel von backend/item_stats.WEAPON_STATS) —
  // ohne diese Einträge zeigten katana/halberd/… keine Basis-Stats im Tooltip.
  katana:        { dmg: 18, speed: 0.95, crit: 0.16, crit_mult: 2.2, range: 1, two_h: true },
  halberd:       { dmg: 19, speed: 0.65, crit: 0.06, crit_mult: 1.7, range: 2, two_h: true, cleave: true },
  lance:         { dmg: 21, speed: 0.55, crit: 0.10, crit_mult: 2.0, range: 3, two_h: true, armor_pen: 0.15 },
  runeblade:     { dmg: 12, speed: 1.0,  crit: 0.10, crit_mult: 2.0, range: 1, two_h: false },
  sickle_weapon: { dmg: 9,  speed: 1.25, crit: 0.14, crit_mult: 1.9, range: 1, two_h: false },
  trident:       { dmg: 11, speed: 1.1,  crit: 0.08, crit_mult: 1.7, range: 2, two_h: false, armor_pen: 0.10 },
  twinblade:     { dmg: 7,  speed: 1.7,  crit: 0.20, crit_mult: 2.3, range: 1, two_h: true },
  // Welle 51: Monster-Drop-Waffen (Spiegel von backend/item_stats.WEAPON_STATS) —
  // hatten vorher keine Stats.
  rusty_sword:       { dmg: 8,  speed: 1.0,  crit: 0.05, crit_mult: 1.4, range: 1, two_h: false },
  iron_sword:        { dmg: 13, speed: 1.0,  crit: 0.06, crit_mult: 1.5, range: 1, two_h: false },
  iron_spear:        { dmg: 15, speed: 1.0,  crit: 0.07, crit_mult: 1.6, range: 2, two_h: true },
  bone_dagger:       { dmg: 6,  speed: 1.7,  crit: 0.20, crit_mult: 2.3, range: 1, two_h: false },
  bone_spear:        { dmg: 12, speed: 1.0,  crit: 0.07, crit_mult: 1.6, range: 2, two_h: true },
  bone_staff:        { dmg: 9,  speed: 1.0,  crit: 0.07, crit_mult: 1.5, range: 4, two_h: true },
  bone_warhammer:    { dmg: 17, speed: 0.70, crit: 0.04, crit_mult: 1.7, range: 1, two_h: true, armor_pen: 0.30 },
  shaman_stick:      { dmg: 8,  speed: 1.2,  crit: 0.08, crit_mult: 1.5, range: 4, two_h: false },
  worn_bow:          { dmg: 8,  speed: 0.90, crit: 0.08, crit_mult: 1.5, range: 5, two_h: true },
  living_wood_bow:   { dmg: 13, speed: 1.0,  crit: 0.12, crit_mult: 1.7, range: 5, two_h: true },
  demon_forge_hammer:{ dmg: 22, speed: 0.60, crit: 0.05, crit_mult: 1.9, range: 1, two_h: true, armor_pen: 0.35 },
};

export const WEAPON_MATERIALS = [
  'wood', 'copper', 'iron', 'steel', 'silver', 'gold',
  'mithril', 'adamant', 'platinum', 'tungsten', 'crystal',
] as const;
export type WeaponMaterial = (typeof WEAPON_MATERIALS)[number];
