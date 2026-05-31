// Item-Gewichte für Inventar-Display.
// Portiert aus frontend/legacy/app.js Z. 1079-1105.
import type { ItemCategory } from '../models/item.model';

// Welle 21: Gewicht pro Item-Kategorie (Default-Fallback per Item-Kind möglich).
export const ITEM_WEIGHT_BY_CATEGORY: Readonly<Record<ItemCategory, number>> = {
  resource:   0.5,
  food:       0.3,
  consumable: 0.4,
  magic:      0.8,
  jewelry:    0.2,
  weapon:     4.0,    // Default für Waffen ohne weight-Override
  armor:      5.0,    // Default für Rüstung ohne weight-Override
  tool:       2.0,
  // 31.05 — neue Drop-Kategorien
  material:   0.5,    // wie resource
  lore:       0.3,    // leichte Schriften/Splitter
  trophy:     0.6,    // Schädel/Banner/etc.
  quest:      0.3,    // Karten-Fragmente, Kapseln
  ammo:       0.05,   // Pfeile/Bolzen sehr leicht (pro Stück)
};

export const ITEM_WEIGHT_OVERRIDES: Readonly<Record<string, number>> = {
  copper_coin: 0.02, silver_coin: 0.02, gold_coin: 0.02,
  herb: 0.1, plant_fiber: 0.15,
  bone: 0.4, cloth: 0.2, leather: 0.4, wood: 0.6, stone: 1.0,
  iron_ore: 1.2, silver_ore: 1.2, gold_ore: 1.5, mythril_ore: 1.0, crystal: 0.8,
  steel_ingot: 1.5, iron_ingot: 1.3, copper_ingot: 1.2, silver_ingot: 1.4,
  gold_ingot: 1.8, mithril_ingot: 1.0, adamant_ingot: 2.0,
  platinum_ingot: 1.6, tungsten_ingot: 2.2, crystal_ingot: 1.0,
  // Waffen — leichter/schwerer als Default
  dagger: 1.5, throwing_knife: 0.8, wand: 1.0, sword: 4.0,
  axe: 5.5, mace: 6.0, spear: 3.5, greatsword: 9.0, scythe: 7.0,
  bow: 2.5, crossbow: 6.0, staff: 3.0,
  // Container
  wooden_bucket: 2.5, iron_bucket: 4.0, leather_waterskin: 1.5,
  wooden_watering_can: 3.0, iron_watering_can: 5.0,
};

// Ground-Display-Scale pro Item-Kategorie (Sprites sind alle 64×64, aber Münzen
// sind klein, Schwerter groß).
export const ITEM_GROUND_SCALE_BY_CATEGORY: Readonly<Record<ItemCategory, number>> = {
  resource:   0.55,
  food:       0.55,
  consumable: 0.55,
  magic:      0.65,
  jewelry:    0.45,
  weapon:     0.85,
  armor:      0.75,
  tool:       0.70,
  // 31.05 — neue Drop-Kategorien
  material:   0.55,
  lore:       0.55,
  trophy:     0.65,
  quest:      0.55,
  ammo:       0.45,
};

export const ITEM_GROUND_SCALE_OVERRIDES: Readonly<Record<string, number>> = {
  // Münzen — kleine Real-Größe
  copper_coin: 0.35,
  silver_coin: 0.35,
  gold_coin:   0.35,
  // Kleine Pflanzen-Items
  herb:          0.50,
  berries:       0.45,
  mushroom_food: 0.50,
  // Große Zweihänder
  greatsword: 1.00,
  scythe:     0.95,
  spear:      0.95,
  staff:      0.95,
  bow:        0.95,
  crossbow:   0.90,
};
