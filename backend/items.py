import db

# Original-Pack 2026-05-27 — hand-painted 128×128 Inventar-Icons.
# Default-Sprites für die meisten Items kommen aus diesem Pool.
_OP = "/assets/professional/original_pack_2026_05_27/icons_128"
# Inspired-Pack 2026-05-27 — Default-Sprite-Upgrade pro Weapon-Kind.
_INSP = "/assets/equipment/weapons/professional/inspired_2026_05_27/icons_128"
# Reference-Based — Defaults für die spezialisierten Welle-29d-Waffen.
_REF = "/assets/equipment/weapons/professional/reference_based/icons_128"
# Armor reference_based — Slot+Rarity-getaggter Pool für alle 5 Slots.
_ARM = "/assets/equipment/armor/professional/reference_based/icons_128"

# Asset-Pfade pro Item-Kind und Metadaten
ITEM_KINDS = {
    # Waffen — Default-Sprites aus inspired_2026_05_27 (hochwertig painterly)
    "sword":         {"category": "weapon", "name": "Schwert",       "slot": "weapon", "sprite": f"{_INSP}/iron_vigil_longsword.png"},
    "axe":           {"category": "weapon", "name": "Axt",           "slot": "weapon", "sprite": f"{_INSP}/oxhide_execution_axe.png"},
    "bow":           {"category": "weapon", "name": "Bogen",         "slot": "weapon", "sprite": f"{_INSP}/thornwood_recurve_bow.png"},
    "staff":         {"category": "weapon", "name": "Stab",          "slot": "weapon", "sprite": f"{_INSP}/emberroot_staff.png"},
    "wand":          {"category": "weapon", "name": "Zauberstab",    "slot": "weapon", "sprite": f"{_INSP}/bramble_witch_wand.png"},
    "greatsword":    {"category": "weapon", "name": "Großschwert",   "slot": "weapon", "sprite": f"{_INSP}/quarry_cleaver_greatsword.png"},
    "spear":         {"category": "weapon", "name": "Speer",         "slot": "weapon", "sprite": f"{_INSP}/duskpoint_war_spear.png"},
    "crossbow":      {"category": "weapon", "name": "Armbrust",      "slot": "weapon", "sprite": f"{_INSP}/siegewood_crossbow.png"},
    "throwing_knife":{"category": "weapon", "name": "Wurfmesser",    "slot": "weapon", "sprite": f"{_INSP}/paired_ravencut_knives.png"},
    "mace":          {"category": "weapon", "name": "Streitkolben",  "slot": "weapon", "sprite": f"{_INSP}/oathbound_iron_mace.png"},
    "scythe":        {"category": "weapon", "name": "Sense",         "slot": "weapon", "sprite": f"{_INSP}/gravebriar_scythe.png"},
    "dagger":        {"category": "weapon", "name": "Dolch",         "slot": "weapon", "sprite": f"{_INSP}/crescent_hook_dagger.png"},
    # Welle 27 (2026-05-27) — neue Waffen-Kinds aus reference_based-Pack
    "katana":        {"category": "weapon", "name": "Katana",        "slot": "weapon", "sprite": "/assets/equipment/weapons/professional/reference_based/icons_128/steel_katana.png"},
    "halberd":       {"category": "weapon", "name": "Hellebarde",    "slot": "weapon", "sprite": "/assets/equipment/weapons/professional/reference_based/icons_128/raven_halberd.png"},
    "trident":       {"category": "weapon", "name": "Dreizack",      "slot": "weapon", "sprite": "/assets/equipment/weapons/professional/reference_based/icons_128/amethyst_trident.png"},
    "lance":         {"category": "weapon", "name": "Stoßlanze",     "slot": "weapon", "sprite": "/assets/equipment/weapons/professional/reference_based/icons_128/demon_slayer_lance.png"},
    "runeblade":     {"category": "weapon", "name": "Runenklinge",   "slot": "weapon", "sprite": "/assets/equipment/weapons/professional/reference_based/icons_128/obsidian_runeblade.png"},
    "twinblade":     {"category": "weapon", "name": "Doppelklinge",  "slot": "weapon", "sprite": "/assets/equipment/weapons/professional/reference_based/icons_128/ice_and_night_blades.png"},
    "sickle_weapon": {"category": "weapon", "name": "Kampfsichel",   "slot": "weapon", "sprite": "/assets/equipment/weapons/professional/reference_based/icons_128/iron_hook_sickle.png"},
    # Rüstung — Default-Sprites aus reference_based-Pack (slot+rarity tagged)
    "helmet":     {"category": "armor", "name": "Helm",         "slot": "helmet",     "sprite": f"{_ARM}/crested_hoplite_helm.png"},
    "chestplate": {"category": "armor", "name": "Brustpanzer",  "slot": "chestplate", "sprite": f"{_ARM}/wandering_knight_armor.png"},
    "gloves":     {"category": "armor", "name": "Handschuhe",   "slot": "gloves",     "sprite": f"{_ARM}/thief_buckled_gloves.png"},
    "shield":     {"category": "armor", "name": "Schild",       "slot": "shield",     "sprite": f"{_ARM}/ornate_guard_shield.png"},
    "boots":      {"category": "armor", "name": "Stiefel",      "slot": "boots",      "sprite": f"{_ARM}/dwarven_field_boots.png"},
    # Schmuck
    "ring":   {"category": "jewelry", "name": "Ring",           "slot": "ring",   "sprite": "/assets/equipment/jewelry/ring.png"},
    "amulet": {"category": "jewelry", "name": "Amulett",        "slot": "amulet", "sprite": "/assets/equipment/jewelry/amulet.png"},
    # Consumables
    "health_potion":         {"category": "consumable", "name": "Heiltrank",         "sprite": f"{_OP}/health_potion.png"},
    "mana_potion":           {"category": "consumable", "name": "Manatrank",         "sprite": f"{_OP}/mana_potion.png"},
    "greater_health_potion": {"category": "consumable", "name": "Großer Heiltrank",  "sprite": "/assets/consumables/potions/greater_health_potion.png"},
    "greater_mana_potion":   {"category": "consumable", "name": "Großer Manatrank",  "sprite": "/assets/consumables/potions/greater_mana_potion.png"},
    "antidote_potion":       {"category": "consumable", "name": "Gegengift",         "sprite": f"{_OP}/antidote_potion.png"},
    "fire_resist_potion":    {"category": "consumable", "name": "Feuerwiderstand",   "sprite": f"{_OP}/fire_resist_potion.png"},
    "frost_resist_potion":   {"category": "consumable", "name": "Frostwiderstand",   "sprite": "/assets/consumables/potions/frost_resist_potion.png"},
    "invisibility_potion":   {"category": "consumable", "name": "Unsichtbarkeit",    "sprite": "/assets/consumables/potions/invisibility_potion.png"},
    "poison_potion":         {"category": "consumable", "name": "Gifttrank",         "sprite": "/assets/consumables/potions/poison_potion.png"},
    "speed_potion":          {"category": "consumable", "name": "Geschwindigkeit",   "sprite": "/assets/consumables/potions/speed_potion.png"},
    "stamina_potion":        {"category": "consumable", "name": "Ausdauer",          "sprite": f"{_OP}/stamina_potion.png"},
    "strength_potion":       {"category": "consumable", "name": "Stärke",            "sprite": "/assets/consumables/potions/strength_potion.png"},
    "herb":                  {"category": "consumable", "name": "Kraut",             "sprite": f"{_OP}/herb_bundle.png"},
    "torch":                 {"category": "consumable", "name": "Fackel",            "sprite": f"{_OP}/torch.png"},
    "food_ration":           {"category": "food",       "name": "Proviant",          "sprite": "/assets/consumables/food_ration.png"},
    # Food
    "apple":          {"category": "food", "name": "Apfel",       "sprite": "/assets/food/apple.png"},
    "berries":        {"category": "food", "name": "Beeren",      "sprite": "/assets/food/berries.png"},
    "wheat":          {"category": "food", "name": "Weizen",      "sprite": "/assets/food/wheat.png"},
    "bread":          {"category": "food", "name": "Brot",        "sprite": f"{_OP}/bread_loaf.png"},
    "raw_meat":       {"category": "food", "name": "Rohes Fleisch","sprite": "/assets/food/raw_meat.png"},
    "cooked_meat":    {"category": "food", "name": "Gebratenes Fleisch","sprite": f"{_OP}/cooked_meat.png"},
    "fish":           {"category": "food", "name": "Fisch",       "sprite": "/assets/food/fish.png"},
    "mushroom_food":  {"category": "food", "name": "Pilz-Mahl",   "sprite": "/assets/food/mushroom_food.png"},
    # — Farming-Drop 2026-05-26 —
    # Beeren
    "strawberry":     {"category": "food", "name": "Erdbeere",    "sprite": "/assets/food/strawberry.png"},
    "blueberry":      {"category": "food", "name": "Blaubeere",   "sprite": "/assets/food/blueberry.png"},
    "blackberry":     {"category": "food", "name": "Brombeere",   "sprite": "/assets/food/blackberry.png"},
    "raspberry":      {"category": "food", "name": "Himbeere",    "sprite": "/assets/food/raspberry.png"},
    # Obstbäume
    "pear":           {"category": "food", "name": "Birne",       "sprite": "/assets/food/pear.png"},
    "plum":           {"category": "food", "name": "Pflaume",     "sprite": "/assets/food/plum.png"},
    "cherry":         {"category": "food", "name": "Kirsche",     "sprite": "/assets/food/cherry.png"},
    # Feldfrüchte
    "carrot":         {"category": "food", "name": "Karotte",     "sprite": "/assets/food/carrot.png"},
    "potato":         {"category": "food", "name": "Kartoffel",   "sprite": "/assets/food/potato.png"},
    "cucumber":       {"category": "food", "name": "Gurke",       "sprite": "/assets/food/cucumber.png"},
    "tomato":         {"category": "food", "name": "Tomate",      "sprite": "/assets/food/tomato.png"},
    "onion":          {"category": "food", "name": "Zwiebel",     "sprite": "/assets/food/onion.png"},
    "cabbage":        {"category": "food", "name": "Kohl",        "sprite": "/assets/food/cabbage.png"},
    "pumpkin":        {"category": "food", "name": "Kürbis",      "sprite": "/assets/food/pumpkin.png"},
    "corn":           {"category": "food", "name": "Mais",        "sprite": "/assets/food/corn.png"},
    # Welle 16 — neue Pflanzen (2026-05-26g)
    "garlic":         {"category": "food", "name": "Knoblauch",   "sprite": "/assets/food/garlic.png"},
    "grapes_blue":    {"category": "food", "name": "Blaue Trauben","sprite": "/assets/food/grapes_blue.png"},
    "grapes_green":   {"category": "food", "name": "Grüne Trauben","sprite": "/assets/food/grapes_green.png"},
    # Saatgut (resource — anpflanzbar)
    "strawberry_seeds":{"category":"resource","name":"Erdbeer-Samen",   "sprite":"/assets/seeds/strawberry_seeds.png"},
    "blueberry_seeds": {"category":"resource","name":"Blaubeer-Samen",  "sprite":"/assets/seeds/blueberry_seeds.png"},
    "blackberry_seeds":{"category":"resource","name":"Brombeer-Samen",  "sprite":"/assets/seeds/blackberry_seeds.png"},
    "raspberry_seeds": {"category":"resource","name":"Himbeer-Samen",   "sprite":"/assets/seeds/raspberry_seeds.png"},
    "apple_seeds":     {"category":"resource","name":"Apfelkerne",      "sprite":"/assets/seeds/apple_seeds.png"},
    "pear_seeds":      {"category":"resource","name":"Birnenkerne",     "sprite":"/assets/seeds/pear_seeds.png"},
    "plum_seeds":      {"category":"resource","name":"Pflaumenkerne",   "sprite":"/assets/seeds/plum_seeds.png"},
    "cherry_seeds":    {"category":"resource","name":"Kirschkerne",     "sprite":"/assets/seeds/cherry_seeds.png"},
    "carrot_seeds":    {"category":"resource","name":"Karotten-Samen",  "sprite":"/assets/seeds/carrot_seeds.png"},
    "potato_seeds":    {"category":"resource","name":"Kartoffel-Saat",  "sprite":"/assets/seeds/potato_seeds.png"},
    "cucumber_seeds":  {"category":"resource","name":"Gurken-Samen",    "sprite":"/assets/seeds/cucumber_seeds.png"},
    "tomato_seeds":    {"category":"resource","name":"Tomaten-Samen",   "sprite":"/assets/seeds/tomato_seeds.png"},
    "onion_seeds":     {"category":"resource","name":"Zwiebel-Samen",   "sprite":"/assets/seeds/onion_seeds.png"},
    "cabbage_seeds":   {"category":"resource","name":"Kohl-Samen",      "sprite":"/assets/seeds/cabbage_seeds.png"},
    "pumpkin_seeds":   {"category":"resource","name":"Kürbis-Samen",    "sprite":"/assets/seeds/pumpkin_seeds.png"},
    "corn_seeds":      {"category":"resource","name":"Mais-Samen",      "sprite":"/assets/seeds/corn_seeds.png"},
    # Magic — Spells (über cast_spell castbar)
    "spell_book": {"category": "magic", "name": "Feuerball-Buch", "sprite": "/assets/magic/spell_book.png"},
    "scroll":     {"category": "magic", "name": "Schriftrolle",   "sprite": "/assets/magic/scroll.png"},
    "rune_stone": {"category": "magic", "name": "Heilrune",       "sprite": "/assets/magic/rune_stone.png"},
    # Welle 29d — neue Spell-Items
    "ice_scroll":         {"category": "magic", "name": "Eis-Schriftrolle",   "sprite": "/assets/animations/spells/ice_spell_impact_peak.png"},
    "wind_slash_scroll":  {"category": "magic", "name": "Wind-Schriftrolle",  "sprite": "/assets/animations/spells/wind_slash_icon.png"},
    "holy_shield_scroll": {"category": "magic", "name": "Heiliger Schild",    "sprite": "/assets/animations/spells/holy_shield_icon.png"},
    # Welle 22 — Forschungs-Items (geben Pool-Punkte beim Use)
    "research_scroll": {"category": "consumable", "name": "Forschungs-Schriftrolle", "sprite": "/assets/magic/scroll.png"},
    "research_tome":   {"category": "consumable", "name": "Forschungs-Folianten",    "sprite": "/assets/magic/spell_book.png"},
    # Welle 30c — Tech-Prints für Late-Game-Research-Nodes
    # Werden beim Node-Unlock consumed. Drop-Quellen: Boss-Loot, Quest-Rewards,
    # Ruinen-Truhen. Sprites aus tech_prints_2026_05_28-Pack.
    "mithril_plans":   {"category": "magic", "name": "Mithril-Pläne",      "sprite": "/assets/magic/professional/tech_prints_2026_05_28/icons_128/mithril_plans.png"},
    "ancient_scroll":  {"category": "magic", "name": "Antike Schriftrolle","sprite": "/assets/magic/professional/tech_prints_2026_05_28/icons_128/ancient_scroll.png"},
    "dragon_skull":    {"category": "magic", "name": "Drachenschädel",     "sprite": "/assets/magic/professional/tech_prints_2026_05_28/icons_128/dragon_skull.png"},
    "gods_tablet":     {"category": "magic", "name": "Götter-Tablet",      "sprite": "/assets/magic/professional/tech_prints_2026_05_28/icons_128/gods_tablet.png"},
    "alchemy_codex":   {"category": "magic", "name": "Alchemisten-Kodex",  "sprite": "/assets/magic/professional/tech_prints_2026_05_28/icons_128/alchemy_codex.png"},
    "runic_tablet":    {"category": "magic", "name": "Runen-Tablet",       "sprite": "/assets/magic/professional/tech_prints_2026_05_28/icons_128/runic_tablet.png"},
    "healing_codex":   {"category": "magic", "name": "Heiler-Kodex",       "sprite": "/assets/magic/professional/tech_prints_2026_05_28/icons_128/healing_codex.png"},
    "trade_ledger":    {"category": "magic", "name": "Handelsbuch",        "sprite": "/assets/magic/professional/tech_prints_2026_05_28/icons_128/trade_ledger.png"},
    # Tools — skill-spezifischer Bonus beim Equipping
    "pickaxe": {"category": "tool", "name": "Spitzhacke", "slot": "tool", "sprite": "/assets/tools/pickaxe.png"},
    "shovel":  {"category": "tool", "name": "Schaufel",   "slot": "tool", "sprite": "/assets/tools/shovel.png"},
    "hammer":  {"category": "tool", "name": "Hammer",     "slot": "tool", "sprite": "/assets/tools/hammer.png"},
    "hoe":     {"category": "tool", "name": "Hacke",      "slot": "tool", "sprite": "/assets/tools/hoe.png"},
    "sickle":  {"category": "tool", "name": "Sichel",     "slot": "tool", "sprite": "/assets/tools/sickle.png"},
    # Welle 16 — Wasser-Tools (Buckets / Watering Cans / Waterskin)
    "wooden_bucket":       {"category": "tool", "name": "Holzeimer",      "slot": "tool", "sprite": "/assets/tools/wooden_bucket.png"},
    "iron_bucket":         {"category": "tool", "name": "Eisen-Eimer",    "slot": "tool", "sprite": "/assets/tools/iron_bucket.png"},
    "wooden_watering_can": {"category": "tool", "name": "Holz-Gießkanne", "slot": "tool", "sprite": "/assets/tools/wooden_watering_can.png"},
    "iron_watering_can":   {"category": "tool", "name": "Eisen-Gießkanne","slot": "tool", "sprite": "/assets/tools/iron_watering_can.png"},
    "leather_waterskin":   {"category": "tool", "name": "Wasserschlauch", "slot": "tool", "sprite": "/assets/tools/leather_waterskin.png"},
    # Ressourcen
    "wood":         {"category": "resource", "name": "Holz",          "sprite": f"{_OP}/wood_logs.png"},
    "stone":        {"category": "resource", "name": "Stein",         "sprite": f"{_OP}/rough_stone.png"},
    "iron_ore":     {"category": "resource", "name": "Eisenerz",      "sprite": f"{_OP}/iron_ore.png"},
    "gold_ore":     {"category": "resource", "name": "Golderz",       "sprite": f"{_OP}/gold_ore.png"},
    "silver_ore":   {"category": "resource", "name": "Silbererz",     "sprite": "/assets/resources/silver_ore.png"},
    "mythril_ore":  {"category": "resource", "name": "Mythril",       "sprite": "/assets/resources/mythril_ore.png"},
    # Ingots — Outputs vom Furnace, Inputs für Anvil-Rezepte
    "steel_ingot":   {"category": "resource", "name": "Stahlbarren",   "sprite": "/assets/resources/steel_ingot.png"},
    "iron_ingot":    {"category": "resource", "name": "Eisenbarren",   "sprite": "/assets/resources/iron_ingot.png"},
    "copper_ingot":  {"category": "resource", "name": "Kupferbarren",  "sprite": "/assets/resources/copper_ingot.png"},
    "silver_ingot":  {"category": "resource", "name": "Silberbarren",  "sprite": "/assets/resources/silver_ingot.png"},
    "gold_ingot":    {"category": "resource", "name": "Goldbarren",    "sprite": "/assets/resources/gold_ingot.png"},
    "mithril_ingot": {"category": "resource", "name": "Mithrilbarren", "sprite": "/assets/resources/mithril_ingot.png"},
    "adamant_ingot": {"category": "resource", "name": "Adamantbarren", "sprite": "/assets/resources/adamant_ingot.png"},
    "platinum_ingot":{"category": "resource", "name": "Platinbarren",  "sprite": "/assets/resources/platinum_ingot.png"},
    "tungsten_ingot":{"category": "resource", "name": "Wolframbarren", "sprite": "/assets/resources/tungsten_ingot.png"},
    "crystal_ingot": {"category": "resource", "name": "Kristallbarren","sprite": "/assets/resources/crystal_ingot.png"},
    "crystal":      {"category": "resource", "name": "Kristall",      "sprite": f"{_OP}/blue_crystal.png"},
    "bone":         {"category": "resource", "name": "Knochen",       "sprite": f"{_OP}/bone_fragments.png"},
    "cloth":        {"category": "resource", "name": "Stoff",         "sprite": f"{_OP}/cloth_bolt.png"},
    "cloth_green":  {"category": "resource", "name": "Grüner Stoff",  "sprite": "/assets/resources/cloth_green.png"},
    "plant_fiber":  {"category": "resource", "name": "Pflanzenfaser", "sprite": "/assets/resources/cloth.png"},
    "leather":      {"category": "resource", "name": "Leder",         "sprite": f"{_OP}/leather_roll.png"},
    "copper_coin":  {"category": "resource", "name": "Kupfermünze",   "sprite": "/assets/currency/coin_copper.png"},
    "silver_coin":  {"category": "resource", "name": "Silbermünze",   "sprite": "/assets/currency/coin_silver.png"},
    "gold_coin":    {"category": "resource", "name": "Goldmünze",     "sprite": "/assets/currency/coin_gold.png"},
    # — Asset-Drop 2026-05-27b: Animal-Products (Drops von Nutztieren) —
    "wool_fleece":      {"category": "resource", "name": "Wollvlies",        "sprite": "/assets/resources/animal_products/wool_fleece.png"},
    "wool_shearing":    {"category": "resource", "name": "Schurwolle",       "sprite": "/assets/resources/animal_products/wool_shearing_bundle.png"},
    "wool_cloth_roll":  {"category": "resource", "name": "Wollstoff-Rolle",  "sprite": "/assets/resources/animal_products/wool_cloth_roll.png"},
    "yarn_ball":        {"category": "resource", "name": "Wollknäuel",       "sprite": "/assets/resources/animal_products/yarn_ball.png"},
    "hide_raw":         {"category": "resource", "name": "Rohe Tierhaut",    "sprite": "/assets/resources/animal_products/hide_raw.png"},
    "leather_bundle":   {"category": "resource", "name": "Leder-Bündel",     "sprite": "/assets/resources/animal_products/leather_bundle.png"},
    "feathers":         {"category": "resource", "name": "Federn",           "sprite": "/assets/resources/animal_products/feathers.png"},
    "manure":           {"category": "resource", "name": "Mist",             "sprite": "/assets/resources/animal_products/manure_pile.png"},
    "wax_block":        {"category": "resource", "name": "Wachsblock",       "sprite": "/assets/resources/animal_products/wax_block.png"},
    "candle_bundle":    {"category": "resource", "name": "Kerzen-Bündel",    "sprite": "/assets/resources/animal_products/candle_bundle.png"},
    "feed_sack":        {"category": "resource", "name": "Futter-Sack",      "sprite": "/assets/resources/animal_products/feed_sack.png"},
    "animal_bedding":   {"category": "resource", "name": "Tierstreu",        "sprite": "/assets/resources/animal_products/animal_bedding_straw.png"},
    # — Asset-Drop 2026-05-27b: Dairy-Food + verarbeitete Lebensmittel —
    "milk_bucket":      {"category": "food", "name": "Eimer Milch",          "sprite": "/assets/food/dairy/milk_bucket.png"},
    "milk_jug":         {"category": "food", "name": "Milch-Krug",           "sprite": "/assets/food/dairy/milk_jug.png"},
    "cream_bowl":       {"category": "food", "name": "Sahne",                "sprite": "/assets/food/dairy/cream_bowl.png"},
    "curds_bowl":       {"category": "food", "name": "Quark",                "sprite": "/assets/food/dairy/curds_bowl.png"},
    "butter_pat":       {"category": "food", "name": "Butter",               "sprite": "/assets/food/dairy/butter_pat.png"},
    "cheese_wedge":     {"category": "food", "name": "Käsestück",            "sprite": "/assets/food/dairy/cheese_wedge.png"},
    "cheese_wheel":     {"category": "food", "name": "Käserad",              "sprite": "/assets/food/dairy/cheese_wheel.png"},
    "egg":              {"category": "food", "name": "Ei",                   "sprite": "/assets/food/dairy/egg.png"},
    "egg_basket":       {"category": "food", "name": "Eier-Korb",            "sprite": "/assets/food/dairy/egg_basket.png"},
    # Processed Food (Vorräte)
    "flour_sack":       {"category": "resource", "name": "Mehl-Sack",        "sprite": "/assets/food/processed/flour_sack.png"},
    "grain_sack":       {"category": "resource", "name": "Getreide-Sack",    "sprite": "/assets/food/processed/grain_sack.png"},
    "oat_sack":         {"category": "resource", "name": "Hafer-Sack",       "sprite": "/assets/food/processed/oat_sack.png"},
    "salt_bag":         {"category": "resource", "name": "Salz-Beutel",      "sprite": "/assets/food/processed/salt_bag.png"},
    "lard_pot":         {"category": "food",     "name": "Schmalztopf",      "sprite": "/assets/food/processed/lard_pot.png"},
    "salted_meat":      {"category": "food",     "name": "Pökelfleisch",     "sprite": "/assets/food/processed/salted_meat.png"},
    "smoked_meat":      {"category": "food",     "name": "Räucherfleisch",   "sprite": "/assets/food/processed/smoked_meat.png"},
    "sausage":          {"category": "food",     "name": "Wurst",            "sprite": "/assets/food/processed/sausage.png"},
    "dried_fish":       {"category": "food",     "name": "Trockenfisch",     "sprite": "/assets/food/processed/dried_fish_bundle.png"},
    "honey_jar":        {"category": "food",     "name": "Honigglas",        "sprite": "/assets/food/processed/honey_jar.png"},
    "animal_feed":      {"category": "resource", "name": "Tierfutter",       "sprite": "/assets/food/processed/animal_feed.png"},
    "cheese_crate":     {"category": "resource", "name": "Käse-Kiste",       "sprite": "/assets/food/processed/cheese_crate.png"},
    # — Asset-Drop 2026-05-27b: Neue Werkzeuge —
    "pitchfork":        {"category": "tool", "name": "Heugabel",         "slot": "tool", "sprite": "/assets/tools/pitchfork.png"},
    "rope_coil":        {"category": "resource", "name": "Seil-Rolle",       "sprite": "/assets/tools/rope_coil.png"},
}

EQUIP_SLOTS = ["weapon", "helmet", "chestplate", "gloves", "shield", "boots", "ring", "amulet", "tool"]

# Welle 36: stackable Kategorien (gleich-kind-items mergen in einer Row mit quantity)
STACKABLE_CATEGORIES = frozenset({"resource", "food", "consumable", "magic"})

# Issue: Stack-Limits pro Kategorie
STACK_LIMITS = {
    "resource":   500,   # Holz, Stein, Erz, Knochen, Stoff, Leder, Fasern …
    "food":       150,   # Materialien (verarbeitbar)
    "consumable": 25,    # Tränke, Kräuter
    "magic":      25,    # Schriftrollen, Runen
}

def is_stackable(category: str) -> bool:
    return category in STACKABLE_CATEGORIES

def stack_limit_for(category: str) -> int:
    """Maximum quantity einer Stack-Row (überlauf → neue Row)."""
    return STACK_LIMITS.get(category, 1)


def _row_to_dict(row) -> dict:
    out = {
        "id":            row["id"],
        "kind":          row["kind"],
        "name":          row["name"],
        "category":      row["category"],
        "quality":       row["quality"],
        "x":             row["x"],
        "y":             row["y"],
        "owner":         row["owner"],
        "equipped_slot": row["equipped_slot"],
        "created_at":    row["created_at"].isoformat(),
        "quantity":      1,
    }
    try:
        if "quantity" in row.keys() and row["quantity"]:
            out["quantity"] = int(row["quantity"])
    except (KeyError, IndexError):
        pass
    # Welle 17: Container-Charges
    try:
        if "charges" in row.keys():
            out["charges"] = int(row["charges"] or 0)
    except (KeyError, IndexError):
        pass
    # Welle 19: Affixes + Unique-Naming, falls Spalten existieren
    try:
        if "affixes" in row.keys():
            aff = row["affixes"]
            if aff:
                import json as _json
                out["affixes"] = _json.loads(aff) if isinstance(aff, str) else aff
        if "unique_name" in row.keys() and row["unique_name"]:
            out["unique_name"] = row["unique_name"]
        if "flavor" in row.keys() and row["flavor"]:
            out["flavor"] = row["flavor"]
    except (KeyError, IndexError, TypeError):
        pass
    # Material-Feld (für sprite-resolution im Frontend)
    try:
        if "material" in row.keys() and row["material"]:
            out["material"] = row["material"]
    except (KeyError, IndexError):
        pass
    # Welle 23: Per-Instance rolled_stats (damage_min/max, speed, crit, …)
    try:
        if "rolled_stats" in row.keys():
            rs = row["rolled_stats"]
            if rs:
                import json as _json
                out["rolled_stats"] = _json.loads(rs) if isinstance(rs, str) else rs
    except (KeyError, IndexError, TypeError):
        pass
    # Welle 25: Cosmetic-Skin-Slug (für visuelles Variants-Pool-Rendering).
    try:
        if "cosmetic_skin" in row.keys() and row["cosmetic_skin"]:
            out["cosmetic_skin"] = row["cosmetic_skin"]
    except (KeyError, IndexError):
        pass
    return out


# Welle 23: Modul-globaler Pointer auf die zentrale ItemManager-Instanz,
# damit Module wie village_spawner (die kein item_manager als Parameter
# bekommen) Chests befüllen können. Wird von main.py beim Boot gesetzt.
_global_item_manager: "ItemManager | None" = None

def set_global_item_manager(mgr: "ItemManager") -> None:
    global _global_item_manager
    _global_item_manager = mgr


class ItemManager:
    async def spawn_on_ground(self, kind: str, x: int, y: int,
                              material: str | None = None,
                              quality_kind: str = "normal") -> dict | None:
        cfg = ITEM_KINDS.get(kind)
        if cfg is None:
            return None
        # Welle 23: Per-Instance Stats für Equipment-Ground-Drops (Boss-Drops).
        # Resources/Consumables/Food bekommen kein rolled_stats.
        import item_stats as _istats
        import json as _json
        import skin_pools as _sp
        rolled = _istats.roll_base_stats(kind, quality_kind)
        rolled_json = _json.dumps(rolled) if rolled else None
        cosmetic = _sp.roll_skin(kind, quality_kind)
        row = await db.pool().fetchrow(
            "INSERT INTO items (kind, name, category, x, y, material, quality, rolled_stats, cosmetic_skin) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9) "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, material, rolled_stats, cosmetic_skin",
            kind, cfg["name"], cfg["category"], x, y, material, quality_kind, rolled_json, cosmetic,
        )
        return _row_to_dict(row)

    async def get_on_ground(self) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin, charges "
            "FROM items WHERE owner IS NULL"
        )
        return [_row_to_dict(r) for r in rows]

    async def get_at(self, x: int, y: int) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin, charges "
            "FROM items WHERE x = $1 AND y = $2 AND owner IS NULL",
            x, y,
        )
        return [_row_to_dict(r) for r in rows]

    async def get_inventory(self, player_name: str) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin, charges "
            "FROM items WHERE owner = $1 ORDER BY id",
            player_name,
        )
        return [_row_to_dict(r) for r in rows]

    async def pickup(self, item_id: int, player_name: str) -> dict | None:
        # Erst das Ground-Item laden, um zu prüfen ob stackable
        ground = await db.pool().fetchrow(
            "SELECT kind, category, quality, quantity FROM items "
            "WHERE id = $1 AND owner IS NULL", item_id,
        )
        if ground is None:
            return None
        # Wenn stackable & quality=normal → in existing stack mergen (Stack-Limit beachten)
        if is_stackable(ground["category"]) and ground["quality"] == "normal":
            limit = stack_limit_for(ground["category"])
            existing = await db.pool().fetchrow(
                "UPDATE items SET quantity = quantity + $3 "
                "WHERE id = (SELECT id FROM items WHERE owner = $1 AND kind = $2 "
                "  AND quality = 'normal' AND equipped_slot IS NULL "
                "  AND (affixes IS NULL OR affixes = 'null'::jsonb) "
                "  AND quantity + $3 <= $4 "
                "  ORDER BY id LIMIT 1) "
                "RETURNING id, kind, name, category, quality, x, y, owner, "
                "equipped_slot, created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin",
                player_name, ground["kind"], int(ground["quantity"] or 1), limit,
            )
            if existing:
                # Ground-Item löschen
                await db.pool().execute("DELETE FROM items WHERE id = $1", item_id)
                return _row_to_dict(existing)
        # Sonst normale Pickup
        row = await db.pool().fetchrow(
            "UPDATE items SET x = NULL, y = NULL, owner = $2 "
            "WHERE id = $1 AND owner IS NULL "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin",
            item_id, player_name,
        )
        return _row_to_dict(row) if row else None

    async def drop(self, item_id: int, player_name: str, x: int, y: int) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = NULL, equipped_slot = NULL, x = $3, y = $4 "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material, rolled_stats, cosmetic_skin",
            item_id, player_name, x, y,
        )
        return _row_to_dict(row) if row else None

    async def equip(self, item_id: int, player_name: str,
                     to_slot: str | None = None) -> dict | None:
        """Welle 23 — Dual-Wield: optionaler to_slot-Override.

        Default: nutzt cfg.slot vom Item. Wenn to_slot='shield' UND das
        Item ist eine 1-Hand-Waffe → Waffe geht in Off-Hand statt Schild.
        Wenn main-Waffe two_handed wird, Off-Hand wird zuerst ausgezogen.
        """
        item = await db.pool().fetchrow(
            "SELECT kind FROM items WHERE id = $1 AND owner = $2",
            item_id, player_name,
        )
        if item is None:
            return None
        cfg = ITEM_KINDS.get(item["kind"])
        if cfg is None or "slot" not in cfg:
            return None
        slot = cfg["slot"]
        kind = item["kind"]

        # Dual-Wield: 1H-Waffe in Off-Hand (shield-slot) wenn angefordert
        if to_slot == "shield" and cfg.get("category") == "weapon":
            import item_stats as _is
            if _is.is_two_handed(kind):
                return None  # 2H-Waffe kann nicht in Off-Hand
            slot = "shield"

        # Wenn main-weapon two_handed wird → Off-Hand ausziehen
        if slot == "weapon":
            import item_stats as _is
            if _is.is_two_handed(kind):
                await db.pool().execute(
                    "UPDATE items SET equipped_slot = NULL "
                    "WHERE owner = $1 AND equipped_slot = 'shield'",
                    player_name,
                )
        # Wenn 1H-Waffe in Off-Hand kommt + main ist 2H → main ausziehen
        if slot == "shield" and cfg.get("category") == "weapon":
            import item_stats as _is
            main_row = await db.pool().fetchrow(
                "SELECT kind FROM items WHERE owner = $1 "
                "AND equipped_slot = 'weapon' LIMIT 1",
                player_name,
            )
            if main_row and _is.is_two_handed(main_row["kind"]):
                await db.pool().execute(
                    "UPDATE items SET equipped_slot = NULL "
                    "WHERE owner = $1 AND equipped_slot = 'weapon'",
                    player_name,
                )

        # Vorher anderen Item im Ziel-Slot ausziehen
        await db.pool().execute(
            "UPDATE items SET equipped_slot = NULL "
            "WHERE owner = $1 AND equipped_slot = $2",
            player_name, slot,
        )
        row = await db.pool().fetchrow(
            "UPDATE items SET equipped_slot = $3 "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, "
            "equipped_slot, created_at, affixes, unique_name, flavor, material, rolled_stats, cosmetic_skin",
            item_id, player_name, slot,
        )
        return _row_to_dict(row) if row else None

    async def unequip(self, item_id: int, player_name: str) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET equipped_slot = NULL "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material, rolled_stats, cosmetic_skin",
            item_id, player_name,
        )
        return _row_to_dict(row) if row else None

    async def consume(self, item_id: int, player_name: str) -> dict | None:
        """Verbraucht EIN Consumable/Food.
        - Stack mit quantity > 1: decrement, Item bleibt mit neuer quantity.
        - Stack mit quantity = 1 (oder non-stack): Row gelöscht.
        Return-Dict bekommt zusätzlich `stack_remaining` (0 = gelöscht, >0 = neue qty)."""
        # Erst: Stack mit quantity > 1 → decrement
        row = await db.pool().fetchrow(
            "UPDATE items SET quantity = quantity - 1 "
            "WHERE id = $1 AND owner = $2 "
            "AND category IN ('consumable', 'food') "
            "AND quantity > 1 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin",
            item_id, player_name,
        )
        if row:
            d = _row_to_dict(row)
            d["stack_remaining"] = int(row["quantity"])
            return d
        # Sonst: einzelnes Item (qty = 1 oder non-stack) → delete
        row = await db.pool().fetchrow(
            "DELETE FROM items WHERE id = $1 AND owner = $2 "
            "AND category IN ('consumable', 'food') "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, material, rolled_stats, cosmetic_skin",
            item_id, player_name,
        )
        if row:
            d = _row_to_dict(row)
            d["stack_remaining"] = 0
            return d
        return None

    # — Stack-Split / Merge ————————————————————————————————————————————————————

    async def split_stack(self, item_id: int, player_name: str,
                          amount: int) -> tuple[dict, dict] | None:
        """Nimmt `amount` aus einem Stack heraus in eine neue Row.
        Returns (updated_original, new_row) oder None bei ungültiger Operation."""
        if amount < 1:
            return None
        row = await db.pool().fetchrow(
            "SELECT kind, name, category, quality, quantity, equipped_slot, "
            "affixes, unique_name, flavor, material "
            "FROM items WHERE id = $1 AND owner = $2", item_id, player_name,
        )
        if row is None or row["equipped_slot"] is not None:
            return None
        cur_qty = int(row["quantity"] or 1)
        if amount >= cur_qty:
            return None  # Ergäbe leere Original-Row
        updated = await db.pool().fetchrow(
            "UPDATE items SET quantity = quantity - $2 WHERE id = $1 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin",
            item_id, amount,
        )
        new_row = await db.pool().fetchrow(
            "INSERT INTO items (kind, name, category, owner, quality, quantity, "
            "material, affixes, unique_name, flavor) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin",
            row["kind"], row["name"], row["category"], player_name, row["quality"],
            amount, row["material"], row["affixes"], row["unique_name"], row["flavor"],
        )
        return (_row_to_dict(updated), _row_to_dict(new_row))

    async def merge_stacks(self, player_name: str, kind: str,
                           quality: str = "normal") -> dict | None:
        """Konsolidiert alle Stacks gleichen kinds/qualities ins erste Row bis
        zum Stack-Limit; überschüssige rows bleiben mit Rest-quantity.
        Returns ein zusammenfassendes Dict {merged_rows, deleted_ids, kept_ids} oder None."""
        cfg = ITEM_KINDS.get(kind)
        if cfg is None or not is_stackable(cfg["category"]):
            return None
        limit = stack_limit_for(cfg["category"])
        rows = await db.pool().fetch(
            "SELECT id, quantity FROM items "
            "WHERE owner = $1 AND kind = $2 AND quality = $3 "
            "  AND equipped_slot IS NULL "
            "  AND (affixes IS NULL OR affixes = 'null'::jsonb) "
            "ORDER BY id",
            player_name, kind, quality,
        )
        if len(rows) < 2:
            return None
        # Greedy fill: erste Row als Ziel, weitere Rows hineinleeren bis voll
        target_id = rows[0]["id"]
        target_qty = int(rows[0]["quantity"])
        deleted_ids: list[int] = []
        kept_ids: list[int] = [target_id]
        for r in rows[1:]:
            src_id = r["id"]
            src_qty = int(r["quantity"])
            capacity = limit - target_qty
            if capacity >= src_qty:
                target_qty += src_qty
                deleted_ids.append(src_id)
            elif capacity > 0:
                target_qty = limit
                # target voll-schreiben
                await db.pool().execute(
                    "UPDATE items SET quantity = $2 WHERE id = $1",
                    target_id, target_qty,
                )
                # source bekommt rest
                new_src_qty = src_qty - capacity
                await db.pool().execute(
                    "UPDATE items SET quantity = $2 WHERE id = $1",
                    src_id, new_src_qty,
                )
                # source wird neues target (Rest könnte noch wachsen)
                target_id = src_id
                target_qty = new_src_qty
                kept_ids.append(target_id)
            else:
                # target schon voll — source wird neues target
                target_id = src_id
                target_qty = src_qty
                kept_ids.append(target_id)
        # Final target schreiben
        await db.pool().execute(
            "UPDATE items SET quantity = $2 WHERE id = $1", target_id, target_qty,
        )
        if deleted_ids:
            await db.pool().execute(
                "DELETE FROM items WHERE id = ANY($1::bigint[])", deleted_ids,
            )
        return {"deleted_ids": deleted_ids, "kept_ids": kept_ids}

    # — Chest-Storage —————————————————————————————————————————————————————————

    async def get_chest_contents(self, chest_id: int) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin, charges "
            "FROM items WHERE owner = $1 ORDER BY id",
            f"chest:{chest_id}",
        )
        return [_row_to_dict(r) for r in rows]

    async def transfer_to_chest(self, item_id: int, player_name: str, chest_id: int) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = $3, equipped_slot = NULL "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material, rolled_stats, cosmetic_skin",
            item_id, player_name, f"chest:{chest_id}",
        )
        return _row_to_dict(row) if row else None

    async def populate_chest(self, chest_id: int, chest_type: str = "world") -> int:
        """Welle 23: Befüllt eine bestehende chest-Structure mit Loot.
        Returns Anzahl gespawnter Items. Idempotent: macht NICHTS wenn der
        Chest schon Inhalte hat (avoid double-population).
        """
        import chest_loot, item_stats, json as _json
        existing = await db.pool().fetchval(
            "SELECT COUNT(*) FROM items WHERE owner = $1",
            f"chest:{chest_id}",
        )
        if existing and existing > 0:
            return 0
        rolls = chest_loot.roll_chest_loot(chest_type)
        owner = f"chest:{chest_id}"
        count = 0
        for r in rolls:
            kind = r["kind"]
            quality_k = r["quality"]
            qty = max(1, int(r.get("quantity", 1)))
            cfg = ITEM_KINDS.get(kind)
            if cfg is None:
                continue
            # Resources/Consumables/Currency: stack-merge falls möglich
            if is_stackable(cfg["category"]) and quality_k == "normal":
                # Existing stack im chest? UPDATE quantity
                merged = await db.pool().fetchrow(
                    "UPDATE items SET quantity = quantity + $3 "
                    "WHERE id = (SELECT id FROM items WHERE owner = $1 AND kind = $2 "
                    "  AND quality = 'normal' AND quantity < $4 LIMIT 1) "
                    "RETURNING id",
                    owner, kind, qty, stack_limit_for(cfg["category"]),
                )
                if merged:
                    count += 1
                    continue
            # Equipment: rolled_stats per-instance + cosmetic_skin aus Pool
            import skin_pools as _sp
            rolled = item_stats.roll_base_stats(kind, quality_k)
            rolled_json = _json.dumps(rolled) if rolled else None
            cosmetic = _sp.roll_skin(kind, quality_k)
            await db.pool().execute(
                "INSERT INTO items (kind, name, category, owner, quality, quantity, rolled_stats, cosmetic_skin) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)",
                kind, cfg["name"], cfg["category"], owner, quality_k, qty, rolled_json, cosmetic,
            )
            count += 1
        return count

    async def transfer_from_chest(self, item_id: int, chest_id: int, player_name: str) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = $3 "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material, rolled_stats, cosmetic_skin",
            item_id, f"chest:{chest_id}", player_name,
        )
        return _row_to_dict(row) if row else None

    # — Crafting ——————————————————————————————————————————————————————————————

    async def count_owned_by_kind(self, player_name: str) -> dict[str, int]:
        """Anzahl Items pro Kind im Inventar (mit Stacking: SUM(quantity))."""
        rows = await db.pool().fetch(
            "SELECT kind, SUM(quantity)::INTEGER AS c FROM items "
            "WHERE owner = $1 AND equipped_slot IS NULL GROUP BY kind",
            player_name,
        )
        return {r["kind"]: int(r["c"]) for r in rows}

    async def consume_one(self, player_name: str, kind: str) -> bool:
        """Verbraucht EIN Item dieses Kinds. Stacking-aware: bei stackable Items
        wird quantity-=1, bei nicht-stackable die Row gelöscht."""
        # Erst stack mit quantity > 1 finden und verringern
        row = await db.pool().fetchrow(
            "UPDATE items SET quantity = quantity - 1 "
            "WHERE id = (SELECT id FROM items WHERE owner = $1 AND kind = $2 "
            "  AND equipped_slot IS NULL AND quantity > 1 ORDER BY id LIMIT 1) "
            "RETURNING id",
            player_name, kind,
        )
        if row:
            return True
        # Sonst Row mit quantity = 1 löschen
        row = await db.pool().fetchrow(
            "DELETE FROM items WHERE id = ("
            "  SELECT id FROM items WHERE owner = $1 AND kind = $2 "
            "  AND equipped_slot IS NULL ORDER BY id LIMIT 1"
            ") RETURNING id",
            player_name, kind,
        )
        return row is not None

    async def create_for_player(self, kind: str, player_name: str,
                                quality_kind: str = "normal",
                                material: str | None = None) -> dict | None:
        cfg = ITEM_KINDS.get(kind)
        if cfg is None:
            return None
        # Resources haben keine echte Qualität — quality immer 'normal' damit
        # Stack-Merge funktioniert (sonst landen rough-iron-ingots in eigenen
        # Rows statt im Stack mit normal-iron-ingots).
        if cfg["category"] == "resource":
            quality_kind = "normal"
        # Welle 36: Wenn stackable und Quality=normal → in existing stack mergen
        # (Resources/Food/Consumables haben kein material — stack-merge unverändert)
        if is_stackable(cfg["category"]) and quality_kind == "normal":
            limit = stack_limit_for(cfg["category"])
            existing = await db.pool().fetchrow(
                "UPDATE items SET quantity = quantity + 1 "
                "WHERE id = (SELECT id FROM items WHERE owner = $1 AND kind = $2 "
                "  AND quality = 'normal' AND equipped_slot IS NULL "
                "  AND (affixes IS NULL OR affixes = 'null'::jsonb) "
                "  AND quantity < $3 "
                "  ORDER BY id LIMIT 1) "
                "RETURNING id, kind, name, category, quality, x, y, owner, "
                "equipped_slot, created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin",
                player_name, kind, limit,
            )
            if existing:
                return _row_to_dict(existing)
        # Welle 23: pro Equipment-Instanz Basis-Stats rollen.
        import item_stats as _istats
        import json as _json
        import skin_pools as _sp
        rolled = _istats.roll_base_stats(kind, quality_kind)
        rolled_json = _json.dumps(rolled) if rolled else None
        cosmetic = _sp.roll_skin(kind, quality_kind)
        row = await db.pool().fetchrow(
            "INSERT INTO items (kind, name, category, owner, quality, quantity, material, rolled_stats, cosmetic_skin) "
            "VALUES ($1, $2, $3, $4, $5, 1, $6, $7::jsonb, $8) "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin",
            kind, cfg["name"], cfg["category"], player_name, quality_kind, material, rolled_json, cosmetic,
        )
        return _row_to_dict(row)


# ─── Welle 17 — Container-Charges (Wasser-Eimer/Gießkanne/Wasserschlauch) ─
WATER_CONTAINER_CAPACITY = {
    "wooden_bucket":       1,
    "iron_bucket":         2,    # größer / haltbarer
    "leather_waterskin":   3,    # tragbar, mehrere Schlücke
    "wooden_watering_can": 4,
    "iron_watering_can":   6,
}

def container_capacity(kind: str) -> int:
    return WATER_CONTAINER_CAPACITY.get(kind, 0)

def is_water_container(kind: str) -> bool:
    return kind in WATER_CONTAINER_CAPACITY


async def set_charges(item_id: int, owner: str, charges: int) -> dict | None:
    """Setzt die charges eines Container-Items absolut. Returns updated row."""
    row = await db.pool().fetchrow(
        "UPDATE items SET charges = GREATEST(0, $1) "
        "WHERE id = $2 AND owner = $3 "
        "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
        "created_at, affixes, unique_name, flavor, quantity, material, rolled_stats, cosmetic_skin, charges",
        charges, item_id, owner,
    )
    return _row_to_dict(row) if row else None


async def add_charges(item_id: int, owner: str, delta: int) -> dict | None:
    """Inkrementelle Änderung; clamp auf 0..capacity."""
    cur = await db.pool().fetchrow(
        "SELECT kind, charges FROM items WHERE id = $1 AND owner = $2",
        item_id, owner,
    )
    if cur is None:
        return None
    cap = container_capacity(cur["kind"])
    new_charges = max(0, min(cap, (cur["charges"] or 0) + delta))
    return await set_charges(item_id, owner, new_charges)
