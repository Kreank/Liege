// Item-Beschreibungen, Kategorie- + Qualität-Übersetzungen.
// Portiert aus frontend/legacy/app.js Z. 974-1043.
import type { ItemCategory, ItemQuality } from '../models/item.model';

/** Tooltip-Beschreibung pro Item-Kind. */
export const ITEM_DESC: Readonly<Record<string, string>> = {
  // Waffen
  sword:         'Eine ausgewogene Klinge. Zuverlässig im Nahkampf.',
  axe:           'Bauernkriegsaxt. Hart auf Holz, härter auf Gegner.',
  bow:           'Langbogen mit Hanfsehne. Trifft auf 5 Felder.',
  staff:         'Magisches Holz, mit Runen verziert. Verstärkt Zauber.',
  wand:          'Kurzer Zauberstab — schneller als ein Stab, weniger Wucht.',
  greatsword:    'Zweihänder. Träge, aber jeder Treffer sitzt.',
  spear:         'Reichweiten-Waffe. Hält Bestien auf Distanz.',
  crossbow:      'Aufwendig gespannt, präzise — 6 Felder Reichweite.',
  throwing_knife:'Mehrere kleine Klingen zum Werfen. Hohe Krit-Chance.',
  mace:          'Stumpfe Wucht — durchschlägt Rüstung leichter.',
  scythe:        'Sense — eigentlich Bauernwerkzeug, in der Schlacht tödlich.',
  dagger:        'Kurze, scharfe Klinge. Sehr schnell, sehr kritisch.',
  // Rüstung
  helmet:        'Schützt den Kopf vor stumpfen Schlägen.',
  chestplate:    'Brustpanzer — schwer, aber rettet Leben.',
  shield:        'Holz- oder Eisenschild. Erhöht Defense.',
  boots:         'Stiefel — leichter Schutz, bisschen mehr Tempo.',
  ring:          'Schmuckstück mit verborgener Macht.',
  amulet:        'Anhänger gegen das Böse — oder zumindest verspricht es das.',
  // Werkzeug
  pickaxe:       'Spitzhacke — beschleunigt Bergbau enorm.',
  shovel:        'Schaufel — gut zum Sammeln und Buddeln.',
  hammer:        'Schmiedehammer — beschleunigt das Bauen.',
  hoe:           'Hacke — für die Landwirtschaft.',
  // Verbrauchsgegenstände
  health_potion: 'Heilkraut + Kristall. Stellt 30 HP wieder her.',
  mana_potion:   'Bläuliche Flüssigkeit. Füllt 30 Mana auf.',
  herb:          'Frisches Kraut — kann gegessen oder gebraut werden.',
  torch:         'Fackel — leuchtet in dunklen Höhlen und Dungeons.',
  food_ration:   'Trockenfleisch + Brot in einem Paket. Sehr haltbar.',
  // Nahrung
  apple:         'Knackiger Apfel. Etwas Sättigung.',
  berries:       'Süße Waldbeeren. Schnelle Energie.',
  wheat:         'Roher Weizen — verarbeitet ergibt Brot.',
  bread:         'Frisch gebackenes Brot. Sättigt sehr lange.',
  raw_meat:      'Rohes Fleisch — besser kochen, sonst Bauchweh.',
  cooked_meat:   'Gebratenes Fleisch. Heilt und sättigt zugleich.',
  fish:          'Frischer Fisch. Gegart noch besser.',
  mushroom_food: 'Pilz-Mahl — solide Sättigung, lange haltbar.',
  // Magie
  spell_book:    'Buch mit Feuerball-Zauber. Beim Lernen wird es Teil von dir.',
  scroll:        'Schriftrolle mit "Magisches Geschoss". Lernbar.',
  rune_stone:    'Stein mit Heilrune. Lernbar — gibt blessed-Status.',
  // Rohstoffe
  wood:          'Allzweck-Holz aus Bäumen. Stapelbar bis 500.',
  stone:         'Bruchstein vom Bergbau. Stapelbar bis 500.',
  iron_ore:      'Eisenerz — am Amboss zu Stahl schmiedbar.',
  gold_ore:      'Goldnugget. Wertvolles Erz — beim Händler gegen Münzen verkaufbar.',
  silver_ore:    'Silbererz — wertvoll, magisch leitend.',
  mythril_ore:   'Sagenhaftes Mythril. Sehr selten.',
  steel_ingot:   'Stahlbarren — Hauptmaterial für hochwertige Waffen.',
  crystal:       'Kristall mit arkanen Eigenschaften.',
  bone:          'Knochen — Material für rituelle Arbeiten.',
  cloth:         'Stoff — für Kleidung und Sackware.',
  leather:       'Gegerbtes Leder — robust, aber leicht.',
};

/** Deutsche Übersetzung für Item-Kategorien. */
export const CATEGORY_DE: Readonly<Record<ItemCategory, string>> = {
  weapon:     'Waffe',
  armor:      'Rüstung',
  jewelry:    'Schmuck',
  consumable: 'Verbrauchsgegenstand',
  food:       'Nahrung',
  magic:      'Magie',
  tool:       'Werkzeug',
  resource:   'Rohstoff',
  material:   'Material',
  lore:       'Lore',
  trophy:     'Trophäe',
  quest:      'Quest-Item',
  ammo:       'Munition',
};

export const QUALITY_DE: Readonly<Record<ItemQuality, string>> = {
  rough:      'grob',
  normal:     'normal',
  fine:       'fein',
  masterwork: 'meisterhaft',
  legendary:  'legendär',
};

/** Quality-Icons für Tooltips (nicht jede Qualität hat ein Icon). */
export const QUALITY_ICONS: Readonly<Partial<Record<ItemQuality, string>>> = {
  fine:       '✨',
  masterwork: '🌟',
  legendary:  '👑',
  rough:      '⚠️',
};

/** Quality → Pro-Sprite-Rarity Mapping (semantisch identische 5 Stufen). */
export const QUALITY_TO_RARITY: Readonly<Record<ItemQuality, string>> = {
  rough:      'poor',
  normal:     'common',
  fine:       'rare',
  masterwork: 'very_rare',
  legendary:  'legendary',
};

/** Kategorien ohne Qualität (rendern als 'rough'/grau). */
export const NO_QUALITY_CATEGORIES: ReadonlySet<ItemCategory> = new Set<ItemCategory>([
  'resource', 'food', 'consumable', 'magic',
  'material', 'lore', 'trophy', 'quest', 'ammo',
]);

/** Frontend-Quality-Multiplikatoren (Damage/Defense bei nicht-rolled Stats). */
export const QUALITY_MULT_FE: Readonly<Record<ItemQuality, number>> = {
  rough: 0.75, normal: 1.0, fine: 1.15, masterwork: 1.3, legendary: 1.5,
};

/** Münz-Icon-Paths. */
export const COIN_ICON = {
  gold:   '/assets/currency/coin_gold.png',
  silver: '/assets/currency/coin_silver.png',
  copper: '/assets/currency/coin_copper.png',
} as const;
