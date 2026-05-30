// Item-Tabelle ITEM + Pro-Sprite-Maps.
// Portiert aus frontend/legacy/app.js Z. 1539-2228.
// 1:1-Spiegel der Default-Asset-Paths; kein Verhalten (kein itemAssetPath, etc.).
import type { ItemDef, ItemRarity } from '../models/item.model';

const OP = '/assets/professional/original_pack_2026_05_27/icons_128';

/** Item-Tabelle: Kind → ItemDef. */
export const ITEM: Readonly<Record<string, ItemDef>> = {
  sword:          { name: 'Schwert',        sprite: 'item_sword',          category: 'weapon', slot: 'weapon', path: `${OP}/black_guard_longsword.png` },
  axe:            { name: 'Axt',            sprite: 'item_axe',            category: 'weapon', slot: 'weapon', path: `${OP}/old_execution_axe.png` },
  bow:            { name: 'Bogen',          sprite: 'item_bow',            category: 'weapon', slot: 'weapon', path: `${OP}/ashwood_recurve_bow.png` },
  staff:          { name: 'Stab',           sprite: 'item_staff',          category: 'weapon', slot: 'weapon', path: `${OP}/red_oak_staff.png` },
  wand:           { name: 'Zauberstab',     sprite: 'item_wand',           category: 'weapon', slot: 'weapon', path: `${OP}/red_oak_staff.png` },
  greatsword:     { name: 'Großschwert',    sprite: 'item_greatsword',     category: 'weapon', slot: 'weapon', path: `${OP}/cleaver_greatsword.png` },
  spear:          { name: 'Speer',          sprite: 'item_spear',          category: 'weapon', slot: 'weapon', path: `${OP}/plain_war_spear.png` },
  crossbow:       { name: 'Armbrust',       sprite: 'item_crossbow',       category: 'weapon', slot: 'weapon', path: `${OP}/stormbow_crossbow.png` },
  throwing_knife: { name: 'Wurfmesser',     sprite: 'item_throwing_knife', category: 'weapon', slot: 'weapon', path: `${OP}/hooked_ritual_dagger.png` },
  mace:           { name: 'Streitkolben',   sprite: 'item_mace',           category: 'weapon', slot: 'weapon', path: `${OP}/iron_mace.png` },
  scythe:         { name: 'Sense',          sprite: 'item_scythe',         category: 'weapon', slot: 'weapon', path: `${OP}/graveyard_scythe.png` },
  dagger:         { name: 'Dolch',          sprite: 'item_dagger',         category: 'weapon', slot: 'weapon', path: `${OP}/hooked_ritual_dagger.png` },
  // Welle 27 — neue Waffen-Kinds
  katana:         { name: 'Katana',         sprite: 'item_katana',         category: 'weapon', slot: 'weapon', path: '/assets/equipment/weapons/professional/reference_based/icons_128/steel_katana.png' },
  halberd:        { name: 'Hellebarde',     sprite: 'item_halberd',        category: 'weapon', slot: 'weapon', path: '/assets/equipment/weapons/professional/reference_based/icons_128/raven_halberd.png' },
  trident:        { name: 'Dreizack',       sprite: 'item_trident',        category: 'weapon', slot: 'weapon', path: '/assets/equipment/weapons/professional/reference_based/icons_128/amethyst_trident.png' },
  lance:          { name: 'Stoßlanze',      sprite: 'item_lance',          category: 'weapon', slot: 'weapon', path: '/assets/equipment/weapons/professional/reference_based/icons_128/demon_slayer_lance.png' },
  runeblade:      { name: 'Runenklinge',    sprite: 'item_runeblade',      category: 'weapon', slot: 'weapon', path: '/assets/equipment/weapons/professional/reference_based/icons_128/obsidian_runeblade.png' },
  twinblade:      { name: 'Doppelklinge',   sprite: 'item_twinblade',      category: 'weapon', slot: 'weapon', path: '/assets/equipment/weapons/professional/reference_based/icons_128/ice_and_night_blades.png' },
  sickle_weapon:  { name: 'Kampfsichel',    sprite: 'item_sickle_weapon',  category: 'weapon', slot: 'weapon', path: '/assets/equipment/weapons/professional/reference_based/icons_128/iron_hook_sickle.png' },
  // Rüstung
  helmet:         { name: 'Helm',           sprite: 'item_helmet',         category: 'armor',  slot: 'helmet',     path: `${OP}/crested_hoplite_helm.png` },
  chestplate:     { name: 'Brustpanzer',    sprite: 'item_chestplate',     category: 'armor',  slot: 'chestplate', path: `${OP}/wandering_knight_armor.png` },
  gloves:         { name: 'Handschuhe',     sprite: 'item_gloves',         category: 'armor',  slot: 'gloves',     path: `${OP}/thief_buckled_gloves.png` },
  shield:         { name: 'Schild',         sprite: 'item_shield',         category: 'armor',  slot: 'shield',     path: `${OP}/ornate_guard_shield.png` },
  boots:          { name: 'Stiefel',        sprite: 'item_boots',          category: 'armor',  slot: 'boots',      path: `${OP}/dwarven_field_boots.png` },
  ring:           { name: 'Ring',           sprite: 'item_ring',           category: 'jewelry',slot: 'ring',       path: '/assets/equipment/jewelry/ring.png' },
  amulet:         { name: 'Amulett',        sprite: 'item_amulet',         category: 'jewelry',slot: 'amulet',     path: '/assets/equipment/jewelry/amulet.png' },
  // Verbrauchsgegenstände
  health_potion:         { name: 'Heiltrank',          sprite: 'item_health_potion',         category: 'consumable', path: `${OP}/health_potion.png` },
  mana_potion:           { name: 'Manatrank',          sprite: 'item_mana_potion',           category: 'consumable', path: `${OP}/mana_potion.png` },
  greater_health_potion: { name: 'Großer Heiltrank',   sprite: 'item_greater_health_potion', category: 'consumable', path: '/assets/consumables/potions/greater_health_potion.png' },
  greater_mana_potion:   { name: 'Großer Manatrank',   sprite: 'item_greater_mana_potion',   category: 'consumable', path: '/assets/consumables/potions/greater_mana_potion.png' },
  antidote_potion:       { name: 'Gegengift',          sprite: 'item_antidote_potion',       category: 'consumable', path: `${OP}/antidote_potion.png` },
  fire_resist_potion:    { name: 'Feuerwiderstand',    sprite: 'item_fire_resist_potion',    category: 'consumable', path: `${OP}/fire_resist_potion.png` },
  frost_resist_potion:   { name: 'Frostwiderstand',    sprite: 'item_frost_resist_potion',   category: 'consumable', path: '/assets/consumables/potions/frost_resist_potion.png' },
  invisibility_potion:   { name: 'Unsichtbarkeit',     sprite: 'item_invisibility_potion',   category: 'consumable', path: '/assets/consumables/potions/invisibility_potion.png' },
  poison_potion:         { name: 'Gifttrank',          sprite: 'item_poison_potion',         category: 'consumable', path: '/assets/consumables/potions/poison_potion.png' },
  speed_potion:          { name: 'Geschwindigkeit',    sprite: 'item_speed_potion',          category: 'consumable', path: '/assets/consumables/potions/speed_potion.png' },
  stamina_potion:        { name: 'Ausdauer',           sprite: 'item_stamina_potion',        category: 'consumable', path: `${OP}/stamina_potion.png` },
  strength_potion:       { name: 'Stärke',             sprite: 'item_strength_potion',       category: 'consumable', path: '/assets/consumables/potions/strength_potion.png' },
  herb:           { name: 'Kraut',          sprite: 'item_herb',          category: 'consumable', path: `${OP}/herb_bundle.png` },
  torch:          { name: 'Fackel',         sprite: 'item_torch',         category: 'consumable', path: `${OP}/torch.png` },
  food_ration:    { name: 'Proviant',       sprite: 'item_food_ration',   category: 'food',       path: '/assets/consumables/food_ration.png' },
  // Nahrung
  apple:          { name: 'Apfel',          sprite: 'item_apple',         category: 'food', path: '/assets/food/apple.png' },
  berries:        { name: 'Beeren',         sprite: 'item_berries',       category: 'food', path: '/assets/food/berries.png' },
  wheat:          { name: 'Weizen',         sprite: 'item_wheat',         category: 'food', path: '/assets/food/wheat.png' },
  bread:          { name: 'Brot',           sprite: 'item_bread',         category: 'food', path: `${OP}/bread_loaf.png` },
  raw_meat:       { name: 'Rohes Fleisch',  sprite: 'item_raw_meat',      category: 'food', path: '/assets/food/raw_meat.png' },
  cooked_meat:    { name: 'Gebratenes Fleisch', sprite: 'item_cooked_meat', category: 'food', path: `${OP}/cooked_meat.png` },
  fish:           { name: 'Fisch',          sprite: 'item_fish',          category: 'food', path: '/assets/food/fish.png' },
  mushroom_food:  { name: 'Pilz-Mahl',      sprite: 'item_mushroom_food', category: 'food', path: '/assets/food/mushroom_food.png' },
  // Farming-Drop 2026-05-26
  strawberry:     { name: 'Erdbeere',       sprite: 'item_strawberry',    category: 'food', path: '/assets/food/strawberry.png' },
  blueberry:      { name: 'Blaubeere',      sprite: 'item_blueberry',     category: 'food', path: '/assets/food/blueberry.png' },
  blackberry:     { name: 'Brombeere',      sprite: 'item_blackberry',    category: 'food', path: '/assets/food/blackberry.png' },
  raspberry:      { name: 'Himbeere',       sprite: 'item_raspberry',     category: 'food', path: '/assets/food/raspberry.png' },
  pear:           { name: 'Birne',          sprite: 'item_pear',          category: 'food', path: '/assets/food/pear.png' },
  plum:           { name: 'Pflaume',        sprite: 'item_plum',          category: 'food', path: '/assets/food/plum.png' },
  cherry:         { name: 'Kirsche',        sprite: 'item_cherry',        category: 'food', path: '/assets/food/cherry.png' },
  carrot:         { name: 'Karotte',        sprite: 'item_carrot',        category: 'food', path: '/assets/food/carrot.png' },
  potato:         { name: 'Kartoffel',      sprite: 'item_potato',        category: 'food', path: '/assets/food/potato.png' },
  cucumber:       { name: 'Gurke',          sprite: 'item_cucumber',      category: 'food', path: '/assets/food/cucumber.png' },
  tomato:         { name: 'Tomate',         sprite: 'item_tomato',        category: 'food', path: '/assets/food/tomato.png' },
  onion:          { name: 'Zwiebel',        sprite: 'item_onion',         category: 'food', path: '/assets/food/onion.png' },
  cabbage:        { name: 'Kohl',           sprite: 'item_cabbage',       category: 'food', path: '/assets/food/cabbage.png' },
  pumpkin:        { name: 'Kürbis',         sprite: 'item_pumpkin',       category: 'food', path: '/assets/food/pumpkin.png' },
  corn:           { name: 'Mais',           sprite: 'item_corn',          category: 'food', path: '/assets/food/corn.png' },
  garlic:         { name: 'Knoblauch',      sprite: 'item_garlic',        category: 'food', path: '/assets/food/garlic.png' },
  grapes_blue:    { name: 'Blaue Trauben',  sprite: 'item_grapes_blue',   category: 'food', path: '/assets/food/grapes_blue.png' },
  grapes_green:   { name: 'Grüne Trauben',  sprite: 'item_grapes_green',  category: 'food', path: '/assets/food/grapes_green.png' },
  // Samen
  strawberry_seeds: { name: 'Erdbeer-Samen',  sprite: 'item_strawberry_seeds', category: 'resource', path: '/assets/seeds/strawberry_seeds.png' },
  blueberry_seeds:  { name: 'Blaubeer-Samen', sprite: 'item_blueberry_seeds',  category: 'resource', path: '/assets/seeds/blueberry_seeds.png' },
  blackberry_seeds: { name: 'Brombeer-Samen', sprite: 'item_blackberry_seeds', category: 'resource', path: '/assets/seeds/blackberry_seeds.png' },
  raspberry_seeds:  { name: 'Himbeer-Samen',  sprite: 'item_raspberry_seeds',  category: 'resource', path: '/assets/seeds/raspberry_seeds.png' },
  apple_seeds:      { name: 'Apfelkerne',     sprite: 'item_apple_seeds',      category: 'resource', path: '/assets/seeds/apple_seeds.png' },
  pear_seeds:       { name: 'Birnenkerne',    sprite: 'item_pear_seeds',       category: 'resource', path: '/assets/seeds/pear_seeds.png' },
  plum_seeds:       { name: 'Pflaumenkerne',  sprite: 'item_plum_seeds',       category: 'resource', path: '/assets/seeds/plum_seeds.png' },
  cherry_seeds:     { name: 'Kirschkerne',    sprite: 'item_cherry_seeds',     category: 'resource', path: '/assets/seeds/cherry_seeds.png' },
  carrot_seeds:     { name: 'Karotten-Samen', sprite: 'item_carrot_seeds',     category: 'resource', path: '/assets/seeds/carrot_seeds.png' },
  potato_seeds:     { name: 'Kartoffel-Saat', sprite: 'item_potato_seeds',     category: 'resource', path: '/assets/seeds/potato_seeds.png' },
  cucumber_seeds:   { name: 'Gurken-Samen',   sprite: 'item_cucumber_seeds',   category: 'resource', path: '/assets/seeds/cucumber_seeds.png' },
  tomato_seeds:     { name: 'Tomaten-Samen',  sprite: 'item_tomato_seeds',     category: 'resource', path: '/assets/seeds/tomato_seeds.png' },
  onion_seeds:      { name: 'Zwiebel-Samen',  sprite: 'item_onion_seeds',      category: 'resource', path: '/assets/seeds/onion_seeds.png' },
  cabbage_seeds:    { name: 'Kohl-Samen',     sprite: 'item_cabbage_seeds',    category: 'resource', path: '/assets/seeds/cabbage_seeds.png' },
  pumpkin_seeds:    { name: 'Kürbis-Samen',   sprite: 'item_pumpkin_seeds',    category: 'resource', path: '/assets/seeds/pumpkin_seeds.png' },
  corn_seeds:       { name: 'Mais-Samen',     sprite: 'item_corn_seeds',       category: 'resource', path: '/assets/seeds/corn_seeds.png' },
  // Magie
  spell_book:     { name: 'Feuerball-Buch', sprite: 'item_spell_book', category: 'magic', path: '/assets/magic/spell_book.png' },
  scroll:         { name: 'Schriftrolle',   sprite: 'item_scroll',     category: 'magic', path: '/assets/magic/scroll.png' },
  rune_stone:     { name: 'Heilrune',       sprite: 'item_rune_stone', category: 'magic', path: '/assets/magic/rune_stone.png' },
  // Welle 34b — dedizierte Lore-/Key-Item-Icons
  research_scroll: { name: 'Forschungs-Schriftrolle', sprite: 'item_research_scroll', category: 'consumable', path: '/assets/professional/additional_assets_2026_05_29_v2/lore_items/icons_128/research_scroll.png' },
  research_tome:   { name: 'Forschungs-Folianten',    sprite: 'item_research_tome',   category: 'consumable', path: '/assets/professional/additional_assets_2026_05_29_v2/lore_items/icons_128/research_tome.png' },
  dungeon_map:     { name: 'Verlies-Karte',           sprite: 'item_dungeon_map',     category: 'magic',      path: '/assets/professional/additional_assets_2026_05_29_v2/lore_items/icons_128/dungeon_map.png' },
  rift_lore:       { name: 'Risskunde',               sprite: 'item_rift_lore',       category: 'magic',      path: '/assets/professional/additional_assets_2026_05_29_v2/lore_items/icons_128/rift_lore.png' },
  kings_seal:      { name: 'Königliches Siegel',      sprite: 'item_kings_seal',      category: 'magic',      path: '/assets/professional/additional_assets_2026_05_29_v2/lore_items/icons_128/kings_seal.png' },
  // Werkzeug
  pickaxe:        { name: 'Spitzhacke',  sprite: 'item_pickaxe',       category: 'tool', slot: 'tool', path: '/assets/tools/pickaxe.png' },
  shovel:         { name: 'Schaufel',    sprite: 'item_shovel',        category: 'tool', slot: 'tool', path: '/assets/tools/shovel.png' },
  hammer:         { name: 'Hammer',      sprite: 'item_hammer',        category: 'tool', slot: 'tool', path: '/assets/tools/hammer.png' },
  hoe:            { name: 'Hacke',       sprite: 'item_hoe',           category: 'tool', slot: 'tool', path: '/assets/tools/hoe.png' },
  sickle:         { name: 'Sichel',      sprite: 'item_sickle',        category: 'tool', slot: 'tool', path: '/assets/tools/sickle.png' },
  wooden_bucket:       { name: 'Holzeimer',      sprite: 'item_wooden_bucket',       category: 'tool', slot: 'tool', path: '/assets/tools/wooden_bucket.png' },
  iron_bucket:         { name: 'Eisen-Eimer',    sprite: 'item_iron_bucket',         category: 'tool', slot: 'tool', path: '/assets/tools/iron_bucket.png' },
  wooden_watering_can: { name: 'Holz-Gießkanne', sprite: 'item_wooden_watering_can', category: 'tool', slot: 'tool', path: '/assets/tools/wooden_watering_can.png' },
  iron_watering_can:   { name: 'Eisen-Gießkanne',sprite: 'item_iron_watering_can',   category: 'tool', slot: 'tool', path: '/assets/tools/iron_watering_can.png' },
  leather_waterskin:   { name: 'Wasserschlauch', sprite: 'item_leather_waterskin',   category: 'tool', slot: 'tool', path: '/assets/tools/leather_waterskin.png' },
  // Rohstoffe
  wood:           { name: 'Holz',        sprite: 'item_wood',          category: 'resource', path: `${OP}/wood_logs.png` },
  stone:          { name: 'Stein',       sprite: 'item_stone',         category: 'resource', path: `${OP}/rough_stone.png` },
  iron_ore:       { name: 'Eisenerz',    sprite: 'item_iron_ore',      category: 'resource', path: `${OP}/iron_ore.png` },
  gold_ore:       { name: 'Golderz',     sprite: 'item_gold_ore',      category: 'resource', path: `${OP}/gold_ore.png` },
  silver_ore:     { name: 'Silbererz',   sprite: 'item_silver_ore',    category: 'resource', path: '/assets/resources/silver_ore.png' },
  mythril_ore:    { name: 'Mythril',     sprite: 'item_mythril_ore',   category: 'resource', path: '/assets/resources/mythril_ore.png' },
  steel_ingot:    { name: 'Stahlbarren',   sprite: 'item_steel_ingot',    category: 'resource', path: '/assets/resources/steel_ingot.png' },
  iron_ingot:     { name: 'Eisenbarren',   sprite: 'item_iron_ingot',     category: 'resource', path: '/assets/resources/iron_ingot.png' },
  copper_ingot:   { name: 'Kupferbarren',  sprite: 'item_copper_ingot',   category: 'resource', path: '/assets/resources/copper_ingot.png' },
  silver_ingot:   { name: 'Silberbarren',  sprite: 'item_silver_ingot',   category: 'resource', path: '/assets/resources/silver_ingot.png' },
  gold_ingot:     { name: 'Goldbarren',    sprite: 'item_gold_ingot',     category: 'resource', path: '/assets/resources/gold_ingot.png' },
  mithril_ingot:  { name: 'Mithrilbarren', sprite: 'item_mithril_ingot',  category: 'resource', path: '/assets/resources/mithril_ingot.png' },
  adamant_ingot:  { name: 'Adamantbarren', sprite: 'item_adamant_ingot',  category: 'resource', path: '/assets/resources/adamant_ingot.png' },
  platinum_ingot: { name: 'Platinbarren',  sprite: 'item_platinum_ingot', category: 'resource', path: '/assets/resources/platinum_ingot.png' },
  tungsten_ingot: { name: 'Wolframbarren', sprite: 'item_tungsten_ingot', category: 'resource', path: '/assets/resources/tungsten_ingot.png' },
  crystal_ingot:  { name: 'Kristallbarren',sprite: 'item_crystal_ingot',  category: 'resource', path: '/assets/resources/crystal_ingot.png' },
  crystal:        { name: 'Kristall',    sprite: 'item_crystal',        category: 'resource', path: `${OP}/blue_crystal.png` },
  bone:           { name: 'Knochen',     sprite: 'item_bone',           category: 'resource', path: `${OP}/bone_fragments.png` },
  cloth:          { name: 'Stoff',       sprite: 'item_cloth',          category: 'resource', path: `${OP}/cloth_bolt.png` },
  cloth_green:    { name: 'Grüner Stoff',sprite: 'item_cloth_green',    category: 'resource', path: '/assets/resources/cloth_green.png' },
  plant_fiber:    { name: 'Pflanzenfaser',sprite: 'item_plant_fiber',   category: 'resource', path: '/assets/resources/cloth.png' },
  leather:        { name: 'Leder',       sprite: 'item_leather',        category: 'resource', path: `${OP}/leather_roll.png` },
  copper_coin:    { name: 'Kupfermünze', sprite: 'item_copper_coin',    category: 'resource', path: '/assets/currency/coin_copper.png' },
  silver_coin:    { name: 'Silbermünze', sprite: 'item_silver_coin',    category: 'resource', path: '/assets/currency/coin_silver.png' },
  gold_coin:      { name: 'Goldmünze',   sprite: 'item_gold_coin',      category: 'resource', path: '/assets/currency/coin_gold.png' },
  // — Asset-Drop 2026-05-27b: Animal-Products —
  wool_fleece:     { name: 'Wollvlies',       sprite: 'item_wool_fleece',     category: 'resource', path: '/assets/resources/animal_products/wool_fleece.png' },
  wool_shearing:   { name: 'Schurwolle',      sprite: 'item_wool_shearing',   category: 'resource', path: '/assets/resources/animal_products/wool_shearing_bundle.png' },
  wool_cloth_roll: { name: 'Wollstoff-Rolle', sprite: 'item_wool_cloth_roll', category: 'resource', path: '/assets/resources/animal_products/wool_cloth_roll.png' },
  yarn_ball:       { name: 'Wollknäuel',      sprite: 'item_yarn_ball',       category: 'resource', path: '/assets/resources/animal_products/yarn_ball.png' },
  hide_raw:        { name: 'Rohe Tierhaut',   sprite: 'item_hide_raw',        category: 'resource', path: '/assets/resources/animal_products/hide_raw.png' },
  leather_bundle:  { name: 'Leder-Bündel',    sprite: 'item_leather_bundle',  category: 'resource', path: '/assets/resources/animal_products/leather_bundle.png' },
  feathers:        { name: 'Federn',          sprite: 'item_feathers',        category: 'resource', path: '/assets/resources/animal_products/feathers.png' },
  manure:          { name: 'Mist',            sprite: 'item_manure',          category: 'resource', path: '/assets/resources/animal_products/manure_pile.png' },
  wax_block:       { name: 'Wachsblock',      sprite: 'item_wax_block',       category: 'resource', path: '/assets/resources/animal_products/wax_block.png' },
  candle_bundle:   { name: 'Kerzen-Bündel',   sprite: 'item_candle_bundle',   category: 'resource', path: '/assets/resources/animal_products/candle_bundle.png' },
  feed_sack:       { name: 'Futter-Sack',     sprite: 'item_feed_sack',       category: 'resource', path: '/assets/resources/animal_products/feed_sack.png' },
  animal_bedding:  { name: 'Tierstreu',       sprite: 'item_animal_bedding',  category: 'resource', path: '/assets/resources/animal_products/animal_bedding_straw.png' },
  // — Asset-Drop 2026-05-27b: Dairy / Processed Food —
  milk_bucket:    { name: 'Eimer Milch',     sprite: 'item_milk_bucket',    category: 'food', path: '/assets/food/dairy/milk_bucket.png' },
  milk_jug:       { name: 'Milch-Krug',      sprite: 'item_milk_jug',       category: 'food', path: '/assets/food/dairy/milk_jug.png' },
  cream_bowl:     { name: 'Sahne',           sprite: 'item_cream_bowl',     category: 'food', path: '/assets/food/dairy/cream_bowl.png' },
  curds_bowl:     { name: 'Quark',           sprite: 'item_curds_bowl',     category: 'food', path: '/assets/food/dairy/curds_bowl.png' },
  butter_pat:     { name: 'Butter',          sprite: 'item_butter_pat',     category: 'food', path: '/assets/food/dairy/butter_pat.png' },
  cheese_wedge:   { name: 'Käsestück',       sprite: 'item_cheese_wedge',   category: 'food', path: '/assets/food/dairy/cheese_wedge.png' },
  cheese_wheel:   { name: 'Käserad',         sprite: 'item_cheese_wheel',   category: 'food', path: '/assets/food/dairy/cheese_wheel.png' },
  egg:            { name: 'Ei',              sprite: 'item_egg',            category: 'food', path: '/assets/food/dairy/egg.png' },
  egg_basket:     { name: 'Eier-Korb',       sprite: 'item_egg_basket',     category: 'food', path: '/assets/food/dairy/egg_basket.png' },
  flour_sack:     { name: 'Mehl-Sack',       sprite: 'item_flour_sack',     category: 'resource', path: '/assets/food/processed/flour_sack.png' },
  grain_sack:     { name: 'Getreide-Sack',   sprite: 'item_grain_sack',     category: 'resource', path: '/assets/food/processed/grain_sack.png' },
  oat_sack:       { name: 'Hafer-Sack',      sprite: 'item_oat_sack',       category: 'resource', path: '/assets/food/processed/oat_sack.png' },
  salt_bag:       { name: 'Salz-Beutel',     sprite: 'item_salt_bag',       category: 'resource', path: '/assets/food/processed/salt_bag.png' },
  lard_pot:       { name: 'Schmalztopf',     sprite: 'item_lard_pot',       category: 'food',     path: '/assets/food/processed/lard_pot.png' },
  salted_meat:    { name: 'Pökelfleisch',    sprite: 'item_salted_meat',    category: 'food',     path: '/assets/food/processed/salted_meat.png' },
  smoked_meat:    { name: 'Räucherfleisch',  sprite: 'item_smoked_meat',    category: 'food',     path: '/assets/food/processed/smoked_meat.png' },
  sausage:        { name: 'Wurst',           sprite: 'item_sausage',        category: 'food',     path: '/assets/food/processed/sausage.png' },
  dried_fish:     { name: 'Trockenfisch',    sprite: 'item_dried_fish',     category: 'food',     path: '/assets/food/processed/dried_fish_bundle.png' },
  honey_jar:      { name: 'Honigglas',       sprite: 'item_honey_jar',      category: 'food',     path: '/assets/food/processed/honey_jar.png' },
  animal_feed:    { name: 'Tierfutter',      sprite: 'item_animal_feed',    category: 'resource', path: '/assets/food/processed/animal_feed.png' },
  cheese_crate:   { name: 'Käse-Kiste',      sprite: 'item_cheese_crate',   category: 'resource', path: '/assets/food/processed/cheese_crate.png' },
  // — Asset-Drop 2026-05-27b: Neue Werkzeuge —
  pitchfork:      { name: 'Heugabel',        sprite: 'item_pitchfork',      category: 'tool',     slot: 'tool', path: '/assets/tools/pitchfork.png' },
  rope_coil:      { name: 'Seil-Rolle',      sprite: 'item_rope_coil',      category: 'resource', path: '/assets/tools/rope_coil.png' },
};

// Welle 19/26 — Pro-Sprite-Set (rarity-spezifische Asset-IDs).
export const PRO_RARITIES: readonly ItemRarity[] = ['poor','common','rare','very_rare','legendary'];

/** Pro-Weapon-Map: Kind → (Rarity-Slug → Asset-ID). `default` ist Fallback. */
export const PRO_WEAPON_MAP: Readonly<Record<string, Readonly<Record<string, string>>>> = {
  sword: {
    default: 'iron_vigil_longsword',
    poor: 'silver_straightsword',
    common: 'iron_vigil_longsword',   // Welle 29c — Inspired-Pack
    rare: 'crescent_saber',
    very_rare: 'thorn_blackblade',
    legendary: 'wolf_end_redblade',
  },
  greatsword: {
    default: 'quarry_cleaver_greatsword',
    poor: 'cleaver_greatsword',
    common: 'quarry_cleaver_greatsword',
    rare: 'rose_glass_sword',
    very_rare: 'azure_glaive',
    legendary: 'crimson_twinblade',
  },
  axe: {
    default: 'oxhide_execution_axe',
    poor: 'iron_hatchet',
    common: 'oxhide_execution_axe',
    rare: 'blue_crescent_axe',
    very_rare: 'flame_cleaver_axe',
    legendary: 'flame_cleaver_axe',
  },
  bow: {
    default: 'thornwood_recurve_bow',
    poor: 'ashwood_recurve_bow',
    common: 'thornwood_recurve_bow',
    rare: 'ebony_longbow',
    very_rare: 'goldleaf_bow',
    legendary: 'gandiva_bow',
  },
  crossbow: {
    default: 'siegewood_crossbow',
    poor: 'ashwood_recurve_bow',
    common: 'siegewood_crossbow',
    rare: 'stormbow',
    very_rare: 'goldleaf_bow',
    legendary: 'gandiva_bow',
  },
  spear: {
    default: 'duskpoint_war_spear',
    poor: 'plain_war_spear',
    common: 'duskpoint_war_spear',
    rare: 'raven_halberd',
    very_rare: 'bloodpoint_lance',
    legendary: 'amethyst_trident',
  },
  staff: {
    default: 'emberroot_staff',
    poor: 'red_oak_staff',
    common: 'emberroot_staff',
    rare: 'white_magus_staff',
    very_rare: 'white_magus_staff',
    legendary: 'white_magus_staff',
  },
  wand: {
    default: 'bramble_witch_wand',
    poor: 'red_oak_staff',
    common: 'bramble_witch_wand',
    rare: 'bramble_witch_wand',
    very_rare: 'white_magus_staff',
    legendary: 'white_magus_staff',
  },
  scythe: {
    default: 'gravebriar_scythe',
    poor: 'iron_hook_sickle',
    common: 'gravebriar_scythe',
    rare: 'graveyard_scythe',
    very_rare: 'chain_reaper',
    legendary: 'void_reaper_scythe',
  },
  dagger: {
    default: 'crescent_hook_dagger',
    poor: 'hooked_ritual_dagger',
    common: 'crescent_hook_dagger',
    rare: 'crescent_hook_dagger',
    very_rare: 'blackthorn_shard',
    legendary: 'ice_and_night_blades',
  },
  throwing_knife: {
    default: 'paired_ravencut_knives',
    poor: 'bloodtalon_throwers',
    common: 'paired_ravencut_knives',
    rare: 'paired_ravencut_knives',
    very_rare: 'bloodtalon_throwers',
    legendary: 'bloodtalon_throwers',
  },
  mace: {
    default: 'oathbound_iron_mace',
    poor: 'iron_hatchet',
    common: 'oathbound_iron_mace',
    rare: 'oathbound_iron_mace',
    very_rare: 'flame_cleaver_axe',
    legendary: 'flame_cleaver_axe',
  },
  // ── Welle 27 — Neue Waffen-Kinds ──────────────────────────────────────
  katana: {
    default: 'steel_katana',
    poor: 'plain_aruming_sword',
    common: 'steel_katana',
    rare: 'crescent_saber',
    very_rare: 'thorn_blackblade',
    legendary: 'wolf_end_redblade',
  },
  halberd: {
    default: 'raven_halberd',
    poor: 'plain_war_spear',
    common: 'raven_halberd',
    rare: 'azure_glaive',
    very_rare: 'raven_halberd',
    legendary: 'azure_glaive',
  },
  trident: {
    default: 'amethyst_trident',
    poor: 'plain_war_spear',
    common: 'ruby_spear',
    rare: 'amethyst_trident',
    very_rare: 'amethyst_trident',
    legendary: 'amethyst_trident',
  },
  lance: {
    default: 'demon_slayer_lance',
    poor: 'plain_war_spear',
    common: 'sunspike_lance',
    rare: 'bloodpoint_lance',
    very_rare: 'demon_slayer_lance',
    legendary: 'demon_slayer_lance',
  },
  runeblade: {
    default: 'obsidian_runeblade',
    poor: 'plain_aruming_sword',
    common: 'silver_straightsword',
    rare: 'obsidian_runeblade',
    very_rare: 'obsidian_runeblade',
    legendary: 'obsidian_runeblade',
  },
  twinblade: {
    default: 'ice_and_night_blades',
    poor: 'hooked_ritual_dagger',
    common: 'blackthorn_shard',
    rare: 'ice_and_night_blades',
    very_rare: 'ice_and_night_blades',
    legendary: 'crimson_twinblade',
  },
  sickle_weapon: {
    default: 'iron_hook_sickle',
    poor: 'iron_hook_sickle',
    common: 'iron_hook_sickle',
    rare: 'iron_hook_sickle',
    very_rare: 'chain_reaper',
    legendary: 'void_reaper_scythe',
  },
};

export const PRO_ARMOR_SLOTS = ['helmet','chestplate','shield','boots','gloves'] as const;
export type ProArmorSlot = (typeof PRO_ARMOR_SLOTS)[number];

/** Pro-Armor-Map: Slot → (Rarity → Asset-ID). */
export const PRO_ARMOR_MAP: Readonly<Record<ProArmorSlot, Readonly<Record<string, string>>>> = {
  helmet: {
    default:   'crested_hoplite_helm',
    poor:      'crested_hoplite_helm',
    common:    'crested_hoplite_helm',
    rare:      'crested_hoplite_helm',
    very_rare: 'crowned_steel_helm',
    legendary: 'templar_visor_helm',
  },
  chestplate: {
    default:   'wandering_knight_armor',
    poor:      'grey_landsknecht_armor',
    common:    'wandering_knight_armor',
    rare:      'mercenary_plate_cuirass',
    very_rare: 'samurai_war_armor',
    legendary: 'samurai_war_armor',
  },
  gloves: {
    default:   'thief_buckled_gloves',
    poor:      'black_leather_glove',
    common:    'thief_buckled_gloves',
    rare:      'stone_guard_gauntlets',
    very_rare: 'noble_gilded_gloves',
    legendary: 'void_claw_gauntlets',
  },
  shield: {
    default:   'ornate_guard_shield',
    poor:      'ornate_guard_shield',
    common:    'ornate_guard_shield',
    rare:      'ornate_guard_shield',
    very_rare: 'ornate_guard_shield',
    legendary: 'ornate_guard_shield',
  },
  boots: {
    default:   'dwarven_field_boots',
    poor:      'wrapped_ranger_boots',
    common:    'dwarven_field_boots',
    rare:      'middle_earth_plate_boots',
    very_rare: 'middle_earth_plate_boots',
    legendary: 'ember_wolf_greaves',
  },
};

/** Welche Kinds nutzen das pro-rarity Sprite-Set. */
export const RARITY_WEAPONS: ReadonlySet<string> = new Set([
  'sword','greatsword','axe','spear','bow','crossbow',
  'dagger','mace','staff','wand','scythe','throwing_knife',
  // Welle 27 — neue Kinds
  'katana','halberd','trident','lance','runeblade',
  'twinblade','sickle_weapon',
]);

// Welle 29c — Inspired-Pack-Slugs
export const INSPIRED_WEAPON_SLUGS: ReadonlySet<string> = new Set([
  'iron_vigil_longsword', 'quarry_cleaver_greatsword', 'oxhide_execution_axe',
  'thornwood_recurve_bow', 'siegewood_crossbow', 'duskpoint_war_spear',
  'emberroot_staff', 'bramble_witch_wand', 'gravebriar_scythe',
  'crescent_hook_dagger', 'paired_ravencut_knives', 'oathbound_iron_mace',
]);

// Welle 27 — Ancient-Blade-Pool (legendary sword-likes).
export const ANCIENT_BLADE_POOL: readonly string[] = [
  'black_knight_wespon', 'fantasy_ev_ganin_sword_dark_souls_inspired',
  'stylized_blades_arthur_malagon_01', 'stylized_blades_arthur_malagon_02',
  'stylized_blades_arthur_malagon_03', 'stylized_blades_arthur_malagon_04',
  'stylized_blades_arthur_malagon_05', 'stylized_blades_arthur_malagon_06',
  'stylized_blades_arthur_malagon_07', 'stylized_blades_arthur_malagon_08',
  'stylized_blades_arthur_malagon_09', 'stylized_blades_arthur_malagon_10',
  'swordtember_final_five_arthur_malagon_01', 'swordtember_final_five_arthur_malagon_03',
  'swordtember_final_five_arthur_malagon_09', 'swordtember_final_five_arthur_malagon_10',
  'swordtember_final_five_arthur_malagon_15', 'swordtember_final_five_arthur_malagon_16',
  'swordtember_final_five_arthur_malagon_17', 'swordtember_final_five_arthur_malagon_18',
  'swordtember_final_five_arthur_malagon_19', 'swordtember_final_five_arthur_malagon_20',
  'swordtember_final_five_arthur_malagon_21', 'swordtember_final_five_arthur_malagon_22',
  'swordtember_final_five_arthur_malagon_23', 'swordtember_final_five_arthur_malagon_24',
  // Welle 25
  'swordtember_final_five_arthur_malagon_25', 'swordtember_final_five_arthur_malagon_26',
  'swordtember_final_five_arthur_malagon_27', 'swordtember_final_five_arthur_malagon_28',
  'swordtember_final_five_arthur_malagon_29', 'swordtember_final_five_arthur_malagon_30',
];

export const ANCIENT_BLADE_KINDS: ReadonlySet<string> = new Set([
  'sword', 'greatsword', 'katana', 'runeblade', 'twinblade',
]);

export const ANCIENT_BLADE_CHANCE = 0.40;

// Quellordner pro Kind für Backend-gerollte cosmetic_skin-Slugs.
// Spiegelt backend/skin_pools.py:SKIN_DIR_BY_KIND.
export const SKIN_DIR_BY_KIND: Readonly<Record<string, string>> = {
  sword:      'equipment/weapons/professional/from_neu_pro',
  greatsword: 'equipment/weapons/professional/from_neu_pro',
  staff:      'equipment/weapons/professional/inspired_arcane_2026_05_27',
  wand:       'equipment/weapons/professional/inspired_arcane_2026_05_27',
  helmet:     'equipment/armor/professional/reference_based',
  chestplate: 'equipment/armor/professional/reference_based',
  gloves:     'equipment/armor/professional/reference_based',
  boots:      'equipment/armor/professional/reference_based',
  shield:     'equipment/armor/professional/reference_based',
};

/** Slugs zum Preloaden pro Kind (cosmetic_skin-Pools). */
export const SKIN_POOL_PRELOAD: Readonly<Record<string, readonly string[]>> = {
  staff: [
    'frost_crystal_staff', 'sun_reliquary_staff', 'living_thorn_staff',
    'void_smoke_war_staff', 'turquoise_rune_staff', 'bone_eye_necromancer_staff',
    'violet_orb_focus_staff', 'antler_blossom_witch_staff', 'blue_arcane_axe_staff',
  ],
  wand: [
    'pale_moon_wand', 'brass_oracle_scepter', 'amethyst_root_wand',
    'twisted_black_iron_wand', 'green_seedling_wand', 'ember_priest_rod',
  ],
  helmet: [
    'crested_hoplite_helm', 'black_knight_helm',
    'winged_crusader_helm', 'winged_knight_helm', 'crowned_steel_helm',
    'templar_visor_helm', 'plague_doctor_helm', 'antlered_dark_helm',
  ],
  chestplate: [
    'grey_landsknecht_armor', 'black_tactical_armor',
    'green_hooded_mantle', 'wandering_knight_armor',
    'mercenary_plate_cuirass', 'linothorax_cuirass',
    'spiked_war_cuirass', 'samurai_war_armor',
  ],
  gloves: [
    'black_leather_glove', 'thief_buckled_gloves', 'heavy_iron_gauntlet',
    'stone_guard_gauntlets', 'fur_cuffed_brawler_gloves', 'black_thievery_gloves',
    'noble_gilded_gloves', 'void_claw_gauntlets',
  ],
  boots: [
    'wrapped_ranger_boots', 'dwarven_field_boots',
    'black_iron_greaves', 'runeplate_greaves', 'middle_earth_plate_boots',
    'ember_wolf_greaves',
  ],
  shield: ['ornate_guard_shield'],
};

// Pro Armor-Asset hat eine canonical Rarity (im Manifest).
export const PRO_ARMOR_RARITY_OF: Readonly<Record<string, ItemRarity>> = {
  // common
  grey_landsknecht_armor: 'common', black_tactical_armor: 'common',
  green_hooded_mantle: 'common', wandering_knight_armor: 'common',
  wrapped_ranger_boots: 'common', dwarven_field_boots: 'common',
  thief_buckled_gloves: 'common', heavy_iron_gauntlet: 'common',
  // rare
  crested_hoplite_helm: 'rare', black_knight_helm: 'rare',
  mercenary_plate_cuirass: 'rare', linothorax_cuirass: 'rare',
  black_iron_greaves: 'rare', runeplate_greaves: 'rare', middle_earth_plate_boots: 'rare',
  stone_guard_gauntlets: 'rare', fur_cuffed_brawler_gloves: 'rare', black_thievery_gloves: 'rare',
  // very_rare
  winged_crusader_helm: 'very_rare', winged_knight_helm: 'very_rare', crowned_steel_helm: 'very_rare',
  spiked_war_cuirass: 'very_rare', samurai_war_armor: 'very_rare',
  noble_gilded_gloves: 'very_rare', ornate_guard_shield: 'very_rare',
  // legendary
  templar_visor_helm: 'legendary', plague_doctor_helm: 'legendary', antlered_dark_helm: 'legendary',
  ember_wolf_greaves: 'legendary', void_claw_gauntlets: 'legendary',
  // poor
  black_leather_glove: 'poor',
};
