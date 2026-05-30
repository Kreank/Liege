"""Item-Definitionen für Monster-Drops (Welle 35).

Pendant zu `items.py`-ITEM_KINDS — hält die 146 Slugs, die durch
`overworld_monster_pool.LOOT` und `monster_longlist.LOOT` (Slug-Overrides)
neu ins Loot-System eingespeist wurden.

`items.py` mergt diese Map am Ende per `ITEM_KINDS.setdefault(...)` —
bestehende Definitionen werden NICHT überschrieben.

Konvention:
- `category`: bestimmt UI-Tab im Inventar + Sortier-Reihenfolge.
- `sprite`: Pfad-Platzhalter unter `/assets/items/monster_drops/<slug>.png`.
  Assets sind noch nicht generiert — bis dahin rendert das Frontend einen
  Fallback. Beim Asset-Gen muss nur das PNG dort abgelegt werden.
- `slot`: nur für Equipment relevant.

Use-Effekte (Trinken/Essen/Casten) sind hier bewusst NICHT verdrahtet —
die kommen separat in `items.py` bzw. dem `use_item`-Handler, wenn der
User Mechaniken pro Item entscheidet. Aktuell: Material-Items sind reines
Trade/Crafting-Material; Boss-Trophäen werden für NPC-Bounty-Quests genutzt.
"""

# Pfad-Konvention für noch nicht generierte Drop-Icons.
_DROP = "/assets/items/monster_drops"


# ──────────────────────────────────────────────────────────────────────────────
# 1. MATERIALS — Pelts, Knochen, Häute, Erze (Crafting-Basis)
# ──────────────────────────────────────────────────────────────────────────────
_MATERIALS = {
    # Felle pro Biome
    "wolf_pelt":         {"category": "material", "name": "Wolfsfell",         "sprite": f"{_DROP}/wolf_pelt.png"},
    "arctic_pelt":       {"category": "material", "name": "Arktis-Fell",       "sprite": f"{_DROP}/arctic_pelt.png"},
    "shadow_pelt":       {"category": "material", "name": "Schatten-Fell",     "sprite": f"{_DROP}/shadow_pelt.png"},
    "otter_pelt":        {"category": "material", "name": "Otter-Fell",        "sprite": f"{_DROP}/otter_pelt.png"},
    "crude_leather":     {"category": "material", "name": "Rohes Leder",       "sprite": f"{_DROP}/crude_leather.png"},
    # Knochen / Skelett-Teile
    "skull":             {"category": "material", "name": "Schädel",           "sprite": f"{_DROP}/skull.png"},
    "sinew":             {"category": "material", "name": "Sehne",             "sprite": f"{_DROP}/sinew.png"},
    "swift_sinew":       {"category": "material", "name": "Flinke Sehne",      "sprite": f"{_DROP}/swift_sinew.png"},
    "fang":              {"category": "material", "name": "Fangzahn",          "sprite": f"{_DROP}/fang.png"},
    "horn":              {"category": "material", "name": "Horn",              "sprite": f"{_DROP}/horn.png"},
    "thorn_fang":        {"category": "material", "name": "Dornen-Fang",       "sprite": f"{_DROP}/thorn_fang.png"},
    "frost_fang":        {"category": "material", "name": "Frost-Fang",        "sprite": f"{_DROP}/frost_fang.png"},
    "panther_claw":      {"category": "material", "name": "Panther-Klaue",     "sprite": f"{_DROP}/panther_claw.png"},
    "claw_fragment":     {"category": "material", "name": "Klauen-Splitter",   "sprite": f"{_DROP}/claw_fragment.png"},
    "boar_tusk":         {"category": "material", "name": "Eber-Stoßzahn",     "sprite": f"{_DROP}/boar_tusk.png"},
    "silver_bristle":    {"category": "material", "name": "Silber-Borste",     "sprite": f"{_DROP}/silver_bristle.png"},
    "iron_horn":         {"category": "material", "name": "Eisen-Horn",        "sprite": f"{_DROP}/iron_horn.png"},
    "corrupted_antler":  {"category": "material", "name": "Verderbtes Geweih", "sprite": f"{_DROP}/corrupted_antler.png"},
    "titan_antler":      {"category": "material", "name": "Titan-Geweih",      "sprite": f"{_DROP}/titan_antler.png"},
    "titan_femur":       {"category": "material", "name": "Titan-Oberschenkel","sprite": f"{_DROP}/titan_femur.png"},
    "giant_femur":       {"category": "material", "name": "Riesen-Oberschenkel","sprite": f"{_DROP}/giant_femur.png"},
    "spider_eye":        {"category": "material", "name": "Spinnen-Auge",      "sprite": f"{_DROP}/spider_eye.png"},
    "vampire_fang":      {"category": "material", "name": "Vampir-Reißzahn",   "sprite": f"{_DROP}/vampire_fang.png"},
    "dune_feather":      {"category": "material", "name": "Dünen-Feder",       "sprite": f"{_DROP}/dune_feather.png"},
    "roc_feather":       {"category": "material", "name": "Roc-Feder",         "sprite": f"{_DROP}/roc_feather.png"},
    "roc_talon":         {"category": "material", "name": "Roc-Kralle",        "sprite": f"{_DROP}/roc_talon.png"},
    "wing_membrane":     {"category": "material", "name": "Flügelhaut",        "sprite": f"{_DROP}/wing_membrane.png"},
    # Stoff
    "tattered_cloth":    {"category": "material", "name": "Zerrissener Stoff", "sprite": f"{_DROP}/tattered_cloth.png"},
    "damp_cloth":        {"category": "material", "name": "Klamme Stoffbahn",  "sprite": f"{_DROP}/damp_cloth.png"},
    "ancient_silk":      {"category": "material", "name": "Antike Seide",      "sprite": f"{_DROP}/ancient_silk.png"},
    "ancient_bandage":   {"category": "material", "name": "Antike Bandage",    "sprite": f"{_DROP}/ancient_bandage.png"},
    "dream_silk":        {"category": "material", "name": "Traumseide",        "sprite": f"{_DROP}/dream_silk.png"},
    # Erze / Ingots
    "crude_steel_ingot": {"category": "material", "name": "Roher Stahlbarren", "sprite": f"{_DROP}/crude_steel_ingot.png"},
    "mythril_ingot":     {"category": "material", "name": "Mythril-Barren",    "sprite": f"{_DROP}/mythril_ingot.png"},
    "starfall_ingot":    {"category": "material", "name": "Sternenfall-Barren","sprite": f"{_DROP}/starfall_ingot.png"},
    "polished_stone":    {"category": "material", "name": "Polierter Stein",   "sprite": f"{_DROP}/polished_stone.png"},
    "salt_lump":         {"category": "material", "name": "Salzklumpen",       "sprite": f"{_DROP}/salt_lump.png"},
    # Spezial-Mats für Drachen-/Boss-Crafting
    "naga_scale":        {"category": "material", "name": "Naga-Schuppe",      "sprite": f"{_DROP}/naga_scale.png"},
    "wyrm_scale":        {"category": "material", "name": "Wyrm-Schuppe",      "sprite": f"{_DROP}/wyrm_scale.png"},
    "worm_chitin":       {"category": "material", "name": "Wurm-Chitin",       "sprite": f"{_DROP}/worm_chitin.png"},
    "kelpie_mane":       {"category": "material", "name": "Kelpie-Mähne",      "sprite": f"{_DROP}/kelpie_mane.png"},
    "kraken_ink":        {"category": "material", "name": "Kraken-Tinte",      "sprite": f"{_DROP}/kraken_ink.png"},
    "plant_fiber":       {"category": "material", "name": "Pflanzenfaser",     "sprite": f"{_DROP}/plant_fiber.png"},
    "briar_thorn":       {"category": "material", "name": "Dorn aus dem Gestrüpp","sprite": f"{_DROP}/briar_thorn.png"},
    "thornmaw_seed":     {"category": "material", "name": "Thornmaw-Samen",    "sprite": f"{_DROP}/thornmaw_seed.png"},
    "clockwork_gear":    {"category": "material", "name": "Uhrwerk-Zahnrad",   "sprite": f"{_DROP}/clockwork_gear.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 2. FOOD — Fleisch-Varianten (Hunger-Restore + ggf. Side-Effects)
# ──────────────────────────────────────────────────────────────────────────────
_FOOD = {
    "rotten_flesh":   {"category": "food", "name": "Faules Fleisch",   "sprite": f"{_DROP}/rotten_flesh.png"},  # Hunger + Krankheits-Risiko
    "dark_meat":      {"category": "food", "name": "Dunkles Fleisch",  "sprite": f"{_DROP}/dark_meat.png"},
    "pork_loin":      {"category": "food", "name": "Schweinerücken",   "sprite": f"{_DROP}/pork_loin.png"},
    "strider_meat":   {"category": "food", "name": "Strider-Filet",    "sprite": f"{_DROP}/strider_meat.png"},
    "tentacle_meat":  {"category": "food", "name": "Tentakel-Fleisch", "sprite": f"{_DROP}/tentacle_meat.png"},
    "herb_bundle":    {"category": "food", "name": "Kräuterbündel",    "sprite": f"{_DROP}/herb_bundle.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 3. DRAGON_PARTS — Premium-Crafting für High-Tier-Equipment
# ──────────────────────────────────────────────────────────────────────────────
_DRAGON = {
    "drake_scale":   {"category": "material", "name": "Drachen-Schuppe", "sprite": f"{_DROP}/drake_scale.png"},
    "drake_horn":    {"category": "material", "name": "Drachen-Horn",    "sprite": f"{_DROP}/drake_horn.png"},
    "dragon_tooth":  {"category": "material", "name": "Drachenzahn",     "sprite": f"{_DROP}/dragon_tooth.png"},
    "dragon_horn":   {"category": "material", "name": "Großes Drachen-Horn","sprite": f"{_DROP}/dragon_horn.png"},
    "dragon_heart":  {"category": "trophy",   "name": "Drachenherz",     "sprite": f"{_DROP}/dragon_heart.png"},
    # Element-Glands (für element-spezifische Spells/Tränke)
    "fire_gland":      {"category": "material", "name": "Feuer-Drüse",      "sprite": f"{_DROP}/fire_gland.png"},
    "frost_gland":     {"category": "material", "name": "Frost-Drüse",      "sprite": f"{_DROP}/frost_gland.png"},
    "acid_gland":      {"category": "material", "name": "Säure-Drüse",      "sprite": f"{_DROP}/acid_gland.png"},
    "poison_gland":    {"category": "material", "name": "Gift-Drüse",       "sprite": f"{_DROP}/poison_gland.png"},
    "storm_gland":     {"category": "material", "name": "Sturm-Drüse",      "sprite": f"{_DROP}/storm_gland.png"},
    "emerald_egg":   {"category": "trophy",   "name": "Smaragd-Ei",      "sprite": f"{_DROP}/emerald_egg.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 4. ESSENCES / MAGIC — Crafting-Reagenzien für Tränke und Spells
# ──────────────────────────────────────────────────────────────────────────────
_ESSENCES = {
    "essence_arcane":    {"category": "material", "name": "Arkane Essenz",    "sprite": f"{_DROP}/essence_arcane.png"},
    "essence_fire":      {"category": "material", "name": "Feuer-Essenz",     "sprite": f"{_DROP}/essence_fire.png"},
    "essence_frost":     {"category": "material", "name": "Frost-Essenz",     "sprite": f"{_DROP}/essence_frost.png"},
    "essence_water":     {"category": "material", "name": "Wasser-Essenz",    "sprite": f"{_DROP}/essence_water.png"},
    "essence_lightning": {"category": "material", "name": "Blitz-Essenz",     "sprite": f"{_DROP}/essence_lightning.png"},
    "essence_storm":     {"category": "material", "name": "Sturm-Essenz",     "sprite": f"{_DROP}/essence_storm.png"},
    "soul_essence":      {"category": "material", "name": "Seelen-Essenz",    "sprite": f"{_DROP}/soul_essence.png"},
    "void_essence":      {"category": "material", "name": "Leere-Essenz",     "sprite": f"{_DROP}/void_essence.png"},
    "sleep_essence":     {"category": "material", "name": "Schlaf-Essenz",    "sprite": f"{_DROP}/sleep_essence.png"},
    "wisp_essence":      {"category": "material", "name": "Irrlicht-Essenz",  "sprite": f"{_DROP}/wisp_essence.png"},
    "frost_dust":        {"category": "material", "name": "Frost-Staub",      "sprite": f"{_DROP}/frost_dust.png"},
    "astral_dust":       {"category": "material", "name": "Astral-Staub",     "sprite": f"{_DROP}/astral_dust.png"},
    "dryad_sap":         {"category": "material", "name": "Dryaden-Saft",     "sprite": f"{_DROP}/dryad_sap.png"},
    "ghoul_tongue":      {"category": "material", "name": "Ghul-Zunge",       "sprite": f"{_DROP}/ghoul_tongue.png"},
    "imp_eye":           {"category": "material", "name": "Kobold-Auge",      "sprite": f"{_DROP}/imp_eye.png"},
    "aberrant_eye":      {"category": "material", "name": "Aberrantes Auge",  "sprite": f"{_DROP}/aberrant_eye.png"},
    "forehead_eye":      {"category": "lore",     "name": "Stirn-Auge",       "sprite": f"{_DROP}/forehead_eye.png"},
    "fire_core":         {"category": "material", "name": "Feuer-Kern",       "sprite": f"{_DROP}/fire_core.png"},
    "granite_core":      {"category": "material", "name": "Granit-Kern",      "sprite": f"{_DROP}/granite_core.png"},
    "glowing_core":      {"category": "material", "name": "Glühender Kern",   "sprite": f"{_DROP}/glowing_core.png"},
    "magma_heart":       {"category": "trophy",   "name": "Magma-Herz",       "sprite": f"{_DROP}/magma_heart.png"},
    "avalanche_core":    {"category": "trophy",   "name": "Lawinen-Kern",     "sprite": f"{_DROP}/avalanche_core.png"},
    "ossuary_core":      {"category": "trophy",   "name": "Ossuar-Kern",      "sprite": f"{_DROP}/ossuary_core.png"},
    "phylactery_shard":  {"category": "material", "name": "Phylakterie-Splitter","sprite": f"{_DROP}/phylactery_shard.png"},
    "old_god_shard":     {"category": "lore",     "name": "Alter-Gott-Splitter","sprite": f"{_DROP}/old_god_shard.png"},
    "sanity_shard":      {"category": "material", "name": "Verstand-Splitter","sprite": f"{_DROP}/sanity_shard.png"},
    "impossible_angle":  {"category": "material", "name": "Unmöglicher Winkel","sprite": f"{_DROP}/impossible_angle.png"},
    "storm_glass":       {"category": "material", "name": "Sturm-Glas",       "sprite": f"{_DROP}/storm_glass.png"},
    "soul_lantern_shard":{"category": "material", "name": "Seelenlaternen-Scherbe","sprite": f"{_DROP}/soul_lantern_shard.png"},
    "night_shard":       {"category": "material", "name": "Nacht-Splitter",   "sprite": f"{_DROP}/night_shard.png"},
    "glacier_eye":       {"category": "material", "name": "Gletscher-Auge",   "sprite": f"{_DROP}/glacier_eye.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 5. GEMS / PEARLS — kostbare Tausch-/Crafting-Items
# ──────────────────────────────────────────────────────────────────────────────
_GEMS = {
    "pearl_great":    {"category": "material", "name": "Große Perle",     "sprite": f"{_DROP}/pearl_great.png"},
    "mire_pearl":     {"category": "material", "name": "Morast-Perle",    "sprite": f"{_DROP}/mire_pearl.png"},
    "river_pearl":    {"category": "material", "name": "Fluss-Perle",     "sprite": f"{_DROP}/river_pearl.png"},
    "brine_pearl":    {"category": "material", "name": "Sole-Perle",      "sprite": f"{_DROP}/brine_pearl.png"},
    "crystal_shard":  {"category": "material", "name": "Kristall-Splitter","sprite": f"{_DROP}/crystal_shard.png"},
    "sand_crystal":   {"category": "material", "name": "Sand-Kristall",   "sprite": f"{_DROP}/sand_crystal.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 6. WEAPONS — Spec-Weapons aus Mob-Drops (Lower Tier vs items.py-Defaults)
# ──────────────────────────────────────────────────────────────────────────────
_WEAPONS = {
    "rusty_sword":        {"category": "weapon", "name": "Verrostetes Schwert", "slot": "weapon", "sprite": f"{_DROP}/rusty_sword.png"},
    "iron_sword":         {"category": "weapon", "name": "Eisenschwert",       "slot": "weapon", "sprite": f"{_DROP}/iron_sword.png"},
    "iron_spear":         {"category": "weapon", "name": "Eisenspeer",         "slot": "weapon", "sprite": f"{_DROP}/iron_spear.png"},
    "bone_dagger":        {"category": "weapon", "name": "Knochendolch",       "slot": "weapon", "sprite": f"{_DROP}/bone_dagger.png"},
    "bone_spear":         {"category": "weapon", "name": "Knochenspeer",       "slot": "weapon", "sprite": f"{_DROP}/bone_spear.png"},
    "bone_staff":         {"category": "weapon", "name": "Knochenstab",        "slot": "weapon", "sprite": f"{_DROP}/bone_staff.png"},
    "bone_warhammer":     {"category": "weapon", "name": "Knochen-Streithammer","slot": "weapon", "sprite": f"{_DROP}/bone_warhammer.png"},
    "shaman_stick":       {"category": "weapon", "name": "Schamanen-Stock",    "slot": "weapon", "sprite": f"{_DROP}/shaman_stick.png"},
    "worn_bow":           {"category": "weapon", "name": "Abgenutzter Bogen",  "slot": "weapon", "sprite": f"{_DROP}/worn_bow.png"},
    "living_wood_bow":    {"category": "weapon", "name": "Lebendholz-Bogen",   "slot": "weapon", "sprite": f"{_DROP}/living_wood_bow.png"},
    "demon_forge_hammer": {"category": "weapon", "name": "Dämonen-Schmiedehammer","slot": "weapon","sprite": f"{_DROP}/demon_forge_hammer.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 7. ARMOR — Spec-Armor-Pieces aus Mob-Drops
# ──────────────────────────────────────────────────────────────────────────────
_ARMOR = {
    "iron_helm":            {"category": "armor", "name": "Eisenhelm",       "slot": "helmet",     "sprite": f"{_DROP}/iron_helm.png"},
    "leather_armor_piece":  {"category": "armor", "name": "Lederrüstungs-Teil","slot": "chestplate","sprite": f"{_DROP}/leather_armor_piece.png"},
    "noble_cloak":          {"category": "armor", "name": "Adels-Umhang",    "slot": "chestplate", "sprite": f"{_DROP}/noble_cloak.png"},
    "pilgrim_robe":         {"category": "armor", "name": "Pilger-Robe",     "slot": "chestplate", "sprite": f"{_DROP}/pilgrim_robe.png"},
    "pharaoh_mask":         {"category": "armor", "name": "Pharaonen-Maske", "slot": "helmet",     "sprite": f"{_DROP}/pharaoh_mask.png"},
    "undying_crown":        {"category": "armor", "name": "Untote Krone",    "slot": "helmet",     "sprite": f"{_DROP}/undying_crown.png"},
    "witchking_crown":      {"category": "armor", "name": "Hexenkönig-Krone","slot": "helmet",     "sprite": f"{_DROP}/witchking_crown.png"},
    "warchief_crown":       {"category": "armor", "name": "Kriegshäuptlings-Krone","slot": "helmet","sprite": f"{_DROP}/warchief_crown.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 8. JEWELRY — Amulette und Siegel (oft Quest- oder Lore-relevant)
# ──────────────────────────────────────────────────────────────────────────────
_JEWELRY = {
    "consecrated_amulet": {"category": "jewelry", "name": "Geweihtes Amulett",  "slot": "amulet", "sprite": f"{_DROP}/consecrated_amulet.png"},
    "scarab_amulet":      {"category": "jewelry", "name": "Skarabäus-Amulett",  "slot": "amulet", "sprite": f"{_DROP}/scarab_amulet.png"},
    "blood_chalice":      {"category": "jewelry", "name": "Blut-Kelch",         "slot": "amulet", "sprite": f"{_DROP}/blood_chalice.png"},
    "inquisitor_signet":  {"category": "jewelry", "name": "Inquisitor-Siegel",  "slot": "ring",   "sprite": f"{_DROP}/inquisitor_signet.png"},
    "crypt_signet":       {"category": "jewelry", "name": "Krypta-Siegel",      "slot": "ring",   "sprite": f"{_DROP}/crypt_signet.png"},
    "traitor_signet":     {"category": "jewelry", "name": "Verräter-Siegel",    "slot": "ring",   "sprite": f"{_DROP}/traitor_signet.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 9. AMMO — Pfeile / Bolzen für Range-Weapons
# ──────────────────────────────────────────────────────────────────────────────
_AMMO = {
    "arrow":            {"category": "ammo", "name": "Pfeil",            "sprite": f"{_DROP}/arrow.png"},
    "evergreen_arrow":  {"category": "ammo", "name": "Immergrün-Pfeil",  "sprite": f"{_DROP}/evergreen_arrow.png"},
    "silver_bolt":      {"category": "ammo", "name": "Silber-Bolzen",    "sprite": f"{_DROP}/silver_bolt.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 10. TROPHIES / QUEST-ITEMS — Bounty-Tropies, Quest-Triggers
# ──────────────────────────────────────────────────────────────────────────────
_TROPHIES = {
    "goblin_ear":             {"category": "trophy", "name": "Goblin-Ohr",            "sprite": f"{_DROP}/goblin_ear.png"},
    "orgrim_skull":           {"category": "trophy", "name": "Orgrim-Schädel",        "sprite": f"{_DROP}/orgrim_skull.png"},
    "captain_banner":         {"category": "trophy", "name": "Hauptmann-Banner",      "sprite": f"{_DROP}/captain_banner.png"},
    "boss_trophy":            {"category": "trophy", "name": "Boss-Trophäe",          "sprite": f"{_DROP}/boss_trophy.png"},
    "crude_map_fragment":     {"category": "quest",  "name": "Karten-Fragment",       "sprite": f"{_DROP}/crude_map_fragment.png"},
    "drowner_lock_of_hair":   {"category": "quest",  "name": "Ziehenden-Haarlocke",   "sprite": f"{_DROP}/drowner_lock_of_hair.png"},
    "living_toad":            {"category": "quest",  "name": "Lebende Kröte",         "sprite": f"{_DROP}/living_toad.png"},
    "messenger_capsule":      {"category": "quest",  "name": "Boten-Kapsel",          "sprite": f"{_DROP}/messenger_capsule.png"},
    "stolen_pouch":           {"category": "quest",  "name": "Gestohlener Beutel",    "sprite": f"{_DROP}/stolen_pouch.png"},
    "well_idol":              {"category": "quest",  "name": "Brunnen-Idol",          "sprite": f"{_DROP}/well_idol.png"},
    "plague_phial":           {"category": "quest",  "name": "Pest-Phiole",           "sprite": f"{_DROP}/plague_phial.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 11. CONSUMABLES / ALCHEMY — Brewables aus Mob-Drops
# ──────────────────────────────────────────────────────────────────────────────
_CONSUMABLES = {
    "witch_brew":     {"category": "consumable", "name": "Hexenbräu",        "sprite": f"{_DROP}/witch_brew.png"},
}

# ──────────────────────────────────────────────────────────────────────────────
# 12. LORE — einmalige Welt-Geheimnisse, Sammler-Items
# ──────────────────────────────────────────────────────────────────────────────
_LORE = {
    "lore_fragment":          {"category": "lore", "name": "Lore-Fragment",            "sprite": f"{_DROP}/lore_fragment.png"},
    "unique_lore_item":       {"category": "lore", "name": "Einzigartiges Lore-Stück", "sprite": f"{_DROP}/unique_lore_item.png"},
    "white_pilgrim_token":    {"category": "lore", "name": "Weißer Pilger-Stein",      "sprite": f"{_DROP}/white_pilgrim_token.png"},
    "tech_print":             {"category": "lore", "name": "Tech-Druck",               "sprite": f"{_DROP}/tech_print.png"},
    "dark_grimoire":          {"category": "lore", "name": "Dunkles Grimoire",         "sprite": f"{_DROP}/dark_grimoire.png"},
    "ancient_treasure":       {"category": "lore", "name": "Antiker Schatz",           "sprite": f"{_DROP}/ancient_treasure.png"},
    "star_mote_shard":        {"category": "lore", "name": "Stern-Splitter",           "sprite": f"{_DROP}/star_mote_shard.png"},
}


# ──────────────────────────────────────────────────────────────────────────────
# Zusammenführung — wird von items.py per setdefault gemerged.
# ──────────────────────────────────────────────────────────────────────────────
DROP_ITEMS: dict[str, dict] = {}
for _src in (_MATERIALS, _FOOD, _DRAGON, _ESSENCES, _GEMS, _WEAPONS,
             _ARMOR, _JEWELRY, _AMMO, _TROPHIES, _CONSUMABLES, _LORE):
    DROP_ITEMS.update(_src)
