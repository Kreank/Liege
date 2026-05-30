"""Crafting-Rezepte pro Station.

Jedes Rezept hat:
  id, name, output (item-kind), category (UI-Gruppierung), inputs (list of (kind, count))
  optional: material (sprite-variant hint)

Tier-Modell (was kann ich wo herstellen?):
  hand:      Tier 0–1 (Holz + Stein), Fasern→Stoff, einfaches Knochenamulett
  workbench: Tier 2 — verarbeitete Materialien (Stoff-/Leder-/Pelz-Rüstung, Bogen, Sense)
  furnace:   Erze schmelzen, Tränke, Kochen
  anvil:     Tier 3+ — Metallverarbeitung (Eisen, Stahl, Silber, Gold, Mithril)

Kategorien (für UI-Tabs):
  weapon, armor, tool, jewelry, consumable, food, material, magic
"""

RECIPES = {
    # ─────────────────────────────────────────────────────────────────
    # HAND — überall ohne Station möglich. Tier 0 (Holz) + Tier 1 (Stein).
    # ─────────────────────────────────────────────────────────────────
    "hand": [
        # — Waffen Holz —
        {"id": "wooden_sword",  "name": "Holzschwert",  "output": "sword",  "category": "weapon",
         "material": "wood", "inputs": [("wood", 3)]},
        {"id": "wooden_shield", "name": "Holzschild",   "output": "shield", "category": "armor",
         "material": "wood", "inputs": [("wood", 4)]},
        {"id": "wooden_club",   "name": "Holzknüppel",  "output": "mace",   "category": "weapon",
         "material": "wood", "inputs": [("wood", 2)]},
        {"id": "wooden_spear",  "name": "Holzspeer",    "output": "spear",  "category": "weapon",
         "material": "wood", "inputs": [("wood", 3), ("stone", 1)]},

        # — Werkzeug Holz —
        {"id": "wooden_axe",     "name": "Holzaxt",       "output": "axe",     "category": "tool",
         "material": "wood", "inputs": [("wood", 2), ("stone", 1)]},
        {"id": "wooden_pickaxe", "name": "Holzspitzhacke","output": "pickaxe", "category": "tool",
         "material": "wood", "inputs": [("wood", 2), ("stone", 2)]},
        {"id": "wooden_hammer",  "name": "Holzhammer",    "output": "hammer",  "category": "tool",
         "material": "wood", "inputs": [("wood", 3), ("stone", 1)]},
        {"id": "wooden_sickle",  "name": "Holzsichel",    "output": "sickle",  "category": "tool",
         "material": "wood", "inputs": [("wood", 2), ("stone", 1)]},

        # — Waffen Stein (Tier-Max ohne Werkbank) —
        {"id": "stone_sword",   "name": "Steinschwert",  "output": "sword",   "category": "weapon",
         "material": "stone", "inputs": [("wood", 2), ("stone", 3)]},
        {"id": "stone_dagger",  "name": "Steindolch",    "output": "dagger",  "category": "weapon",
         "material": "stone", "inputs": [("wood", 1), ("stone", 2)]},
        {"id": "stone_spear",   "name": "Steinspeer",    "output": "spear",   "category": "weapon",
         "material": "stone", "inputs": [("wood", 2), ("stone", 3)]},

        # — Werkzeug Stein —
        {"id": "stone_axe",     "name": "Steinaxt",       "output": "axe",     "category": "tool",
         "material": "stone", "inputs": [("wood", 2), ("stone", 3)]},
        {"id": "stone_pickaxe", "name": "Steinspitzhacke","output": "pickaxe", "category": "tool",
         "material": "stone", "inputs": [("wood", 2), ("stone", 3)]},
        {"id": "stone_hammer",  "name": "Steinhammer",    "output": "hammer",  "category": "tool",
         "material": "stone", "inputs": [("wood", 3), ("stone", 3)]},

        # — Material —
        {"id": "weave_cloth",   "name": "Stoff weben",    "output": "cloth",   "category": "material",
         "inputs": [("plant_fiber", 3)]},

        # — Schmuck (einfach) —
        {"id": "bone_amulet_hand","name": "Knochenamulett (roh)","output": "amulet","category": "jewelry",
         "inputs": [("bone", 2), ("plant_fiber", 2)]},
    ],

    # ─────────────────────────────────────────────────────────────────
    # WORKBENCH — Tier 2: verarbeitete Materialien (Stoff/Leder/Pelz/Bogen).
    # Keine Holz-/Steinwaffen mehr (die laufen jetzt im Hand-Tier).
    # ─────────────────────────────────────────────────────────────────
    "workbench": [
        # — Bogen + Zweihänder —
        {"id": "wooden_bow",    "name": "Holzbogen",    "output": "bow",    "category": "weapon",
         "material": "wood", "inputs": [("wood", 3), ("cloth", 1)]},
        {"id": "wooden_scythe", "name": "Sense",        "output": "scythe", "category": "weapon",
         "material": "wood", "inputs": [("wood", 3), ("stone", 1)]},

        # — Cloth-Armor (Tier 0 für Magier) —
        {"id": "cloth_helm",    "name": "Stoffkappe",   "output": "helmet",     "category": "armor",
         "material": "cloth", "inputs": [("cloth", 3)]},
        {"id": "cloth_chest",   "name": "Stoffrobe",    "output": "chestplate", "category": "armor",
         "material": "cloth", "inputs": [("cloth", 5)]},

        # — Leather-Armor —
        {"id": "leather_helm",  "name": "Lederhelm",    "output": "helmet", "category": "armor",
         "material": "leather", "inputs": [("leather", 2)]},
        {"id": "leather_boots", "name": "Lederstiefel", "output": "boots",  "category": "armor",
         "material": "leather", "inputs": [("leather", 2)]},

        # — Fur-Armor (Survival-Tier) —
        {"id": "fur_helm",      "name": "Pelzkappe",    "output": "helmet", "category": "armor",
         "material": "fur", "inputs": [("leather", 1), ("cloth", 1)]},
        {"id": "fur_boots",     "name": "Pelzstiefel",  "output": "boots",  "category": "armor",
         "material": "fur", "inputs": [("leather", 1), ("cloth", 1)]},

        # — Schmuck (poliertes Amulett) —
        {"id": "bone_amulet",   "name": "Knochenamulett","output": "amulet","category": "jewelry",
         "inputs": [("bone", 2), ("cloth", 1)]},
    ],

    # ─────────────────────────────────────────────────────────────────
    # FURNACE — Schmelze, Tränke, Kochen.
    # ─────────────────────────────────────────────────────────────────
    "furnace": [
        # — Ingots — gegated nach Schmiede-Tier
        {"id": "smelt_iron",    "name": "Eisen schmelzen",   "output": "iron_ingot",    "category": "material",
         "inputs": [("iron_ore", 1)], "requires": "smithing_basics"},
        {"id": "smelt_steel",   "name": "Stahl schmieden",   "output": "steel_ingot",   "category": "material",
         "inputs": [("iron_ore", 2)], "requires": "smithing_advanced"},
        {"id": "smelt_silver",  "name": "Silber schmelzen",  "output": "silver_ingot",  "category": "material",
         "inputs": [("silver_ore", 1)], "requires": "smithing_advanced"},
        {"id": "smelt_gold",    "name": "Gold schmelzen",    "output": "gold_ingot",    "category": "material",
         "inputs": [("gold_ore", 1)], "requires": "mastersmithing"},
        {"id": "smelt_mithril", "name": "Mithril schmieden", "output": "mithril_ingot", "category": "material",
         "inputs": [("mythril_ore", 1)], "requires": "mastersmithing"},

        # — Tränke — gegated nach Alchemie
        {"id": "brew_health",  "name": "Heiltrank brauen", "output": "health_potion", "category": "consumable",
         "inputs": [("herb", 3), ("crystal", 1)], "requires": "alchemy_basics"},
        {"id": "brew_mana",    "name": "Manatrank brauen", "output": "mana_potion",   "category": "consumable",
         "inputs": [("herb", 2), ("silver_ore", 1)], "requires": "alchemy_basics"},

        # — Kochen — gegated nach Landwirtschaft
        {"id": "bake_bread",   "name": "Brot backen",      "output": "bread",       "category": "food",
         "inputs": [("wheat", 3)], "requires": "agriculture"},
        {"id": "cook_meat",    "name": "Fleisch garen",    "output": "cooked_meat", "category": "food",
         "inputs": [("raw_meat", 1), ("wood", 1)], "requires": "agriculture"},
        {"id": "cook_fish",    "name": "Fisch garen",      "output": "cooked_meat", "category": "food",
         "inputs": [("fish", 1), ("wood", 1)], "requires": "agriculture"},
    ],

    # ─────────────────────────────────────────────────────────────────
    # ANVIL — Tier 3+ Metallverarbeitung. Braucht Ingots aus dem Furnace.
    # ─────────────────────────────────────────────────────────────────
    "anvil": [
        # — Tier 2 Eisen → smithing_basics —
        {"id": "iron_sword",  "name": "Eisenschwert", "output": "sword",      "category": "weapon",
         "material": "iron", "inputs": [("iron_ingot", 2), ("wood", 1)], "requires": "smithing_basics"},
        {"id": "iron_axe",    "name": "Eisenaxt",     "output": "axe",        "category": "tool",
         "material": "iron", "inputs": [("iron_ingot", 2), ("wood", 1)], "requires": "smithing_basics"},
        {"id": "iron_helm",   "name": "Eisenhelm",    "output": "helmet",     "category": "armor",
         "material": "iron", "inputs": [("iron_ingot", 2)], "requires": "smithing_basics"},
        {"id": "iron_chest",  "name": "Eisenpanzer",  "output": "chestplate", "category": "armor",
         "material": "iron", "inputs": [("iron_ingot", 3)], "requires": "smithing_basics"},
        {"id": "iron_shield", "name": "Eisenschild",  "output": "shield",     "category": "armor",
         "material": "iron", "inputs": [("iron_ingot", 2), ("wood", 1)], "requires": "smithing_basics"},
        {"id": "iron_boots",  "name": "Eisenstiefel", "output": "boots",      "category": "armor",
         "material": "iron", "inputs": [("iron_ingot", 2)], "requires": "smithing_basics"},

        # — Tier 3 Stahl → smithing_advanced —
        {"id": "steel_sword", "name": "Stahlschwert", "output": "sword",      "category": "weapon",
         "material": "steel", "inputs": [("steel_ingot", 2), ("wood", 1)], "requires": "smithing_advanced"},
        {"id": "steel_chest", "name": "Stahlpanzer",  "output": "chestplate", "category": "armor",
         "material": "steel", "inputs": [("steel_ingot", 3)], "requires": "smithing_advanced"},

        # — Tier 4 Silber → smithing_advanced —
        {"id": "silver_sword","name": "Silberschwert","output": "sword",  "category": "weapon",
         "material": "silver", "inputs": [("silver_ingot", 2), ("wood", 1)], "requires": "smithing_advanced"},
        {"id": "silver_helm", "name": "Silberhelm",   "output": "helmet", "category": "armor",
         "material": "silver", "inputs": [("silver_ingot", 2)], "requires": "smithing_advanced"},

        # — Tier 5 Gold → mastersmithing —
        {"id": "gold_helm",   "name": "Goldhelm",     "output": "helmet",     "category": "armor",
         "material": "gold", "inputs": [("gold_ingot", 2)], "requires": "mastersmithing"},
        {"id": "gold_chest",  "name": "Goldpanzer",   "output": "chestplate", "category": "armor",
         "material": "gold", "inputs": [("gold_ingot", 3)], "requires": "mastersmithing"},

        # — Tier 6 Mithril → mastersmithing —
        {"id": "mithril_sword","name": "Mithrilschwert","output": "sword",      "category": "weapon",
         "material": "mithril", "inputs": [("mithril_ingot", 2), ("wood", 1)], "requires": "mastersmithing"},
        {"id": "mithril_chest","name": "Mithrilpanzer", "output": "chestplate", "category": "armor",
         "material": "mithril", "inputs": [("mithril_ingot", 3)], "requires": "mastersmithing"},

        # — Metall-Werkzeug → smithing_advanced —
        {"id": "make_pickaxe", "name": "Spitzhacke schmieden", "output": "pickaxe", "category": "tool",
         "inputs": [("steel_ingot", 2), ("wood", 1)], "requires": "smithing_advanced"},
        {"id": "make_hammer",  "name": "Hammer schmieden",     "output": "hammer",  "category": "tool",
         "inputs": [("steel_ingot", 1), ("wood", 2)], "requires": "smithing_advanced"},
        {"id": "make_shovel",  "name": "Schaufel schmieden",   "output": "shovel",  "category": "tool",
         "inputs": [("steel_ingot", 1), ("wood", 1)], "requires": "smithing_advanced"},
        {"id": "make_hoe",     "name": "Hacke schmieden",      "output": "hoe",     "category": "tool",
         "inputs": [("steel_ingot", 1), ("wood", 2)], "requires": "smithing_advanced"},

        # ── Welle 27: neue Waffen-Kinds ─────────────────────────────────────
        # Tier 2-3 Iron/Steel verfügbar via smithing_basics/advanced
        {"id": "iron_katana",  "name": "Eisen-Katana", "output": "katana", "category": "weapon",
         "material": "iron", "inputs": [("iron_ingot", 3), ("wood", 1)], "requires": "smithing_basics"},
        {"id": "iron_halberd", "name": "Eisen-Hellebarde", "output": "halberd", "category": "weapon",
         "material": "iron", "inputs": [("iron_ingot", 2), ("wood", 3)], "requires": "smithing_basics"},
        {"id": "iron_trident", "name": "Eisen-Dreizack", "output": "trident", "category": "weapon",
         "material": "iron", "inputs": [("iron_ingot", 2), ("wood", 2)], "requires": "smithing_basics"},
        {"id": "iron_lance",   "name": "Eisen-Lanze",   "output": "lance",   "category": "weapon",
         "material": "iron", "inputs": [("iron_ingot", 2), ("wood", 4)], "requires": "smithing_basics"},
        {"id": "iron_twinblade","name": "Eisen-Doppelklinge","output": "twinblade","category": "weapon",
         "material": "iron", "inputs": [("iron_ingot", 3), ("wood", 1), ("leather", 1)],
         "requires": "smithing_basics"},
        {"id": "iron_sickle",  "name": "Kampf-Sichel",  "output": "sickle_weapon", "category": "weapon",
         "material": "iron", "inputs": [("iron_ingot", 1), ("wood", 1)], "requires": "smithing_basics"},
        # Tier 4+ Runeblade: Mithril + magic_basics-Forschung
        {"id": "mithril_runeblade", "name": "Mithril-Runenklinge", "output": "runeblade",
         "category": "weapon", "material": "mithril",
         "inputs": [("mithril_ingot", 2), ("wood", 1), ("crystal", 1)],
         "requires": "mastersmithing"},
        # Steel-Variants als Upgrade-Tier (smithing_advanced)
        {"id": "steel_katana", "name": "Stahl-Katana", "output": "katana", "category": "weapon",
         "material": "steel", "inputs": [("steel_ingot", 3), ("wood", 1)], "requires": "smithing_advanced"},
        {"id": "steel_halberd","name": "Stahl-Hellebarde","output": "halberd","category": "weapon",
         "material": "steel", "inputs": [("steel_ingot", 2), ("wood", 3)], "requires": "smithing_advanced"},

        # ── Welle 35: Monster-Drop-Crafting (Knochen-/Drachen-/Konstrukt-Waffen) ──
        # Knochen-Waffen (frühes Necromancy-Flair, billiger als Stahl)
        {"id": "craft_bone_dagger",    "name": "Knochendolch",        "output": "bone_dagger",    "category": "weapon",
         "inputs": [("bone", 5), ("wood", 2)]},
        {"id": "craft_bone_spear",     "name": "Knochenspeer",        "output": "bone_spear",     "category": "weapon",
         "inputs": [("bone", 8), ("wood", 3)]},
        {"id": "craft_bone_staff",     "name": "Knochenstab",         "output": "bone_staff",     "category": "weapon",
         "inputs": [("bone", 6), ("wood", 1)]},
        {"id": "craft_bone_warhammer", "name": "Knochen-Streithammer","output": "bone_warhammer", "category": "weapon",
         "inputs": [("bone", 10), ("stone", 4)]},
        # Drachen-Schmiede (Premium-Equipment, requires smithing_advanced)
        {"id": "drake_chestplate",     "name": "Drachenschuppen-Panzer", "output": "chestplate",   "category": "armor",
         "material": "steel", "inputs": [("drake_scale", 5), ("crude_steel_ingot", 2)],
         "requires": "smithing_advanced"},
        {"id": "drake_shield",         "name": "Drachenschuppen-Schild", "output": "shield",       "category": "armor",
         "material": "steel", "inputs": [("drake_scale", 3), ("wood", 2)],
         "requires": "smithing_advanced"},
        {"id": "dragontooth_spear",    "name": "Drachenzahn-Speer",   "output": "spear",          "category": "weapon",
         "material": "iron", "inputs": [("dragon_tooth", 3), ("wood", 1)],
         "requires": "smithing_advanced"},
        {"id": "dragontooth_dagger",   "name": "Drachenzahn-Dolch",   "output": "dagger",         "category": "weapon",
         "material": "iron", "inputs": [("dragon_tooth", 2), ("wood", 1)],
         "requires": "smithing_advanced"},
        {"id": "dragonhorn_hammer",    "name": "Drachenhorn-Hammer",  "output": "bone_warhammer", "category": "weapon",
         "inputs": [("dragon_horn", 2), ("bone", 3)],
         "requires": "smithing_advanced"},
        # Konstrukt-Crafting (Granit-Stein-Rüstung)
        {"id": "granite_chestplate",   "name": "Granit-Panzer",       "output": "chestplate",     "category": "armor",
         "material": "stone", "inputs": [("granite_core", 2), ("stone", 10)],
         "requires": "smithing_basics"},
    ],
}

# Welle 35: Monster-Drop-Recipes nach Station angehängt (statt das große
# Dict-Literal oben weiter aufzublähen, hier append-style — gleicher Effekt).

# ── HAND ──────────────────────────────────────────────────────────────
RECIPES["hand"] += [
    # Pelz/Leder-Verarbeitung (auch ohne Webstuhl möglich)
    {"id": "tan_wolf_pelt",      "name": "Wolfsfell gerben",     "output": "crude_leather", "category": "material",
     "inputs": [("wolf_pelt", 2)]},
    {"id": "tan_shadow_pelt",    "name": "Schattenfell gerben",  "output": "leather",       "category": "material",
     "inputs": [("shadow_pelt", 1)]},
    # Fletching: Federn → Pfeile
    {"id": "fletch_arrows",      "name": "Pfeile fletchen",      "output": "arrow",         "category": "material",
     "inputs": [("dune_feather", 5), ("wood", 2)]},
    # Roh-Schamanen-Stock aus Schädel + Stoff
    {"id": "craft_shaman_stick", "name": "Schamanen-Stock",      "output": "shaman_stick",  "category": "weapon",
     "inputs": [("skull", 1), ("cloth", 2), ("wood", 1)]},
]

# ── WORKBENCH (Loom-Ersatz) ───────────────────────────────────────────
RECIPES["workbench"] += [
    # Otter-Felle → Stoffrolle
    {"id": "weave_otter_cloth",  "name": "Otterstoff weben",     "output": "cloth",         "category": "material",
     "inputs": [("otter_pelt", 3)]},
    # Arktis-Pelz + Stoff → warme Brustrüstung (fur-flavored)
    {"id": "fur_chest_arctic",   "name": "Pelz-Brustpanzer",     "output": "chestplate",    "category": "armor",
     "material": "fur", "inputs": [("arctic_pelt", 1), ("cloth", 2)]},
]

# ── FURNACE (Kitchen + Alchemy + Smelting) ────────────────────────────
RECIPES["furnace"] += [
    # — Kitchen: Mob-Fleisch garen —
    {"id": "cook_dark_meat",     "name": "Dunkles Fleisch garen","output": "cooked_meat",   "category": "food",
     "inputs": [("dark_meat", 2), ("wood", 1)], "requires": "agriculture"},
    {"id": "cook_tentacle",      "name": "Tentakel garen",       "output": "cooked_meat",   "category": "food",
     "inputs": [("tentacle_meat", 1), ("wood", 1)], "requires": "agriculture"},
    {"id": "cook_strider",       "name": "Strider-Filet garen",  "output": "cooked_meat",   "category": "food",
     "inputs": [("strider_meat", 1), ("wood", 1)], "requires": "agriculture"},
    {"id": "salt_pork",          "name": "Schweinerücken salzen","output": "cooked_meat",   "category": "food",
     "inputs": [("pork_loin", 1), ("salt_lump", 1), ("wood", 1)], "requires": "agriculture"},

    # — Alchemy: Element-Glands → Resist-Tränke —
    {"id": "brew_fire_resist_gland",  "name": "Feuerwiderstand (Drüse)", "output": "fire_resist_potion",  "category": "consumable",
     "inputs": [("fire_gland", 1), ("herb", 2)], "requires": "alchemy_basics"},
    {"id": "brew_frost_resist_gland", "name": "Frostwiderstand (Drüse)", "output": "frost_resist_potion", "category": "consumable",
     "inputs": [("frost_gland", 1), ("herb", 2)], "requires": "alchemy_basics"},
    {"id": "brew_antidote_gland",     "name": "Gegengift (Drüse)",       "output": "antidote_potion",     "category": "consumable",
     "inputs": [("poison_gland", 1), ("herb", 2)], "requires": "alchemy_basics"},

    # — Alchemy: Essenzen → Tränke/Scrolls —
    {"id": "brew_fire_resist_essence",  "name": "Feuerwiderstand (Essenz)", "output": "fire_resist_potion",  "category": "consumable",
     "inputs": [("essence_fire", 1), ("mana_potion", 1)], "requires": "alchemy_basics"},
    {"id": "brew_frost_resist_essence", "name": "Frostwiderstand (Essenz)", "output": "frost_resist_potion", "category": "consumable",
     "inputs": [("essence_frost", 1), ("mana_potion", 1)], "requires": "alchemy_basics"},
    {"id": "brew_water_health",         "name": "Heiltrank (Wasser-Essenz)","output": "health_potion",       "category": "consumable",
     "inputs": [("essence_water", 1), ("herb", 2)], "requires": "alchemy_basics"},
    {"id": "brew_lightning_speed",      "name": "Geschwindigkeitstrank",    "output": "speed_potion",        "category": "consumable",
     "inputs": [("essence_lightning", 1), ("mana_potion", 1)], "requires": "alchemy_basics"},
    {"id": "brew_arcane_mana",          "name": "Manatrank (Arkane Essenz)","output": "mana_potion",         "category": "consumable",
     "inputs": [("essence_arcane", 2)], "requires": "alchemy_basics"},
    {"id": "brew_dryad_health",         "name": "Heiltrank (Dryaden-Saft)", "output": "health_potion",       "category": "consumable",
     "inputs": [("dryad_sap", 1), ("herb", 2)], "requires": "alchemy_basics"},
    {"id": "brew_frostdust_resist",     "name": "Frostwiderstand (Staub)",  "output": "frost_resist_potion", "category": "consumable",
     "inputs": [("frost_dust", 1), ("mana_potion", 1)], "requires": "alchemy_basics"},
    {"id": "brew_astral_mana",          "name": "Manatrank (Astralstaub)",  "output": "mana_potion",         "category": "consumable",
     "inputs": [("astral_dust", 3)], "requires": "alchemy_basics"},

    # — Magie-Output aus Essenzen —
    {"id": "scribe_void_scroll", "name": "Leere-Schriftrolle",   "output": "scroll",        "category": "magic",
     "inputs": [("void_essence", 1), ("bone", 3)], "requires": "alchemy_basics"},
    {"id": "craft_soul_amulet",  "name": "Seelen-Amulett",       "output": "amulet",        "category": "jewelry",
     "inputs": [("soul_essence", 1), ("bone", 5)], "requires": "alchemy_basics"},
    {"id": "craft_wisp_torch",   "name": "Irrlicht-Fackel",      "output": "torch",         "category": "consumable",
     "inputs": [("wisp_essence", 1), ("cloth", 2)], "requires": "alchemy_basics"},

    # — Dragon-Heart Transmutation (super-rare) —
    {"id": "transmute_mythril",  "name": "Mythril-Transmutation","output": "mythril_ingot", "category": "material",
     "inputs": [("dragon_heart", 1), ("fire_gland", 1), ("frost_gland", 1), ("storm_gland", 1)],
     "requires": "mastersmithing"},
]

# ── ANVIL (zusätzliche Drachen-/Konstrukt-Recipes oben schon angehängt) ──
RECIPES["anvil"] += [
    # Mechanik-Pickaxe aus Uhrwerk-Zahnrädern
    {"id": "clockwork_pickaxe",  "name": "Uhrwerk-Spitzhacke",   "output": "pickaxe",       "category": "tool",
     "inputs": [("clockwork_gear", 5), ("wood", 1)], "requires": "smithing_advanced"},
    # Phylakterie-Splitter → Necro-Amulett
    {"id": "phylactery_amulet",  "name": "Phylakterie-Amulett",  "output": "amulet",        "category": "jewelry",
     "inputs": [("phylactery_shard", 1), ("crystal", 1)], "requires": "smithing_advanced"},

    # Gems & Pearls → Schmuck
    {"id": "pearl_amulet",       "name": "Perlen-Amulett",       "output": "amulet",        "category": "jewelry",
     "inputs": [("pearl_great", 3)]},
    {"id": "mire_pearl_ring",    "name": "Morast-Perlenring",    "output": "ring",          "category": "jewelry",
     "inputs": [("mire_pearl", 2)]},
    {"id": "river_pearl_ring",   "name": "Fluss-Perlenring",     "output": "ring",          "category": "jewelry",
     "inputs": [("river_pearl", 2)]},
    {"id": "brine_pearl_ring",   "name": "Sole-Perlenring",      "output": "ring",          "category": "jewelry",
     "inputs": [("brine_pearl", 2)]},
    {"id": "fuse_crystal_shards","name": "Kristall fügen",       "output": "crystal",       "category": "material",
     "inputs": [("crystal_shard", 5)]},
    {"id": "refine_sand_crystal","name": "Sandkristall raffinieren","output": "crystal",    "category": "material",
     "inputs": [("sand_crystal", 1), ("crystal", 1)]},
]

# Marker-Sentinel entfernt das leere Append-Hilfs-Dict-Konstrukt.


# Kategorien-Reihenfolge fürs Frontend (gleiche Sortierung wie hier).
CATEGORY_ORDER = ["weapon", "armor", "tool", "jewelry", "consumable", "food", "material", "magic"]
CATEGORY_LABELS = {
    "weapon":     "Waffen",
    "armor":      "Rüstung",
    "tool":       "Werkzeug",
    "jewelry":    "Schmuck",
    "consumable": "Verbrauch",
    "food":       "Speisen",
    "material":   "Material",
    "magic":      "Magie",
}


def _ensure_category(recipe: dict) -> dict:
    """Backfill 'category' from output-kind, falls in einem Rezept vergessen."""
    if "category" in recipe:
        return recipe
    try:
        from items import ITEM_KINDS
        cat = ITEM_KINDS.get(recipe["output"], {}).get("category", "material")
        # 'resource' als Crafting-Output ist konzeptuell 'material'
        recipe["category"] = "material" if cat == "resource" else cat
    except Exception:
        recipe["category"] = "material"
    return recipe


def get_recipes(station: str) -> list[dict]:
    return [_ensure_category(r) for r in RECIPES.get(station, [])]


def find_recipe(station: str, recipe_id: str) -> dict | None:
    for r in RECIPES.get(station, []):
        if r["id"] == recipe_id:
            return _ensure_category(r)
    return None
