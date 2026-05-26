"""Einfache Crafting-Rezepte pro Station.

Jedes Rezept hat optional ein `material`-Feld — wenn gesetzt, wird das
gecraftete Item mit diesem Material gespeichert, und das Frontend rendert
das entsprechende material-spezifische Sprite (z.B. sword_1h_iron.png).
"""

RECIPES = {
    # Hand-Crafting — überall ohne Werkbank möglich. Basis-Werkzeuge die
    # man am Anfang braucht, plus Faser→Stoff-Verarbeitung.
    "hand": [
        {"id": "wooden_axe",     "name": "Holzaxt",       "output": "axe",
         "material": "wood",
         "inputs": [("wood", 2), ("stone", 1)]},
        {"id": "wooden_pickaxe", "name": "Holzspitzhacke","output": "pickaxe",
         "inputs": [("wood", 2), ("stone", 2)]},
        {"id": "wooden_hammer",  "name": "Holzhammer",    "output": "hammer",
         "inputs": [("wood", 3), ("stone", 1)]},
        {"id": "wooden_sickle",  "name": "Holzsichel",    "output": "sickle",
         "inputs": [("wood", 2), ("stone", 1)]},
        # Faser → Stoff
        {"id": "weave_cloth",    "name": "Stoff weben",   "output": "cloth",
         "inputs": [("plant_fiber", 3)]},
        # Knochenamulett auch ohne Werkbank
        {"id": "bone_amulet_hand","name": "Knochenamulett","output": "amulet",
         "inputs": [("bone", 2), ("plant_fiber", 2)]},
    ],
    "workbench": [
        {"id": "wooden_sword",  "name": "Holzschwert",  "output": "sword",
         "material": "wood",
         "inputs": [("wood", 3)]},
        {"id": "stone_axe",     "name": "Steinaxt",     "output": "axe",
         "material": "wood",
         "inputs": [("wood", 2), ("stone", 2)]},
        {"id": "wooden_bow",    "name": "Holzbogen",    "output": "bow",
         "material": "wood",
         "inputs": [("wood", 3), ("cloth", 1)]},
        {"id": "wooden_shield", "name": "Holzschild",   "output": "shield",
         "material": "wood",
         "inputs": [("wood", 4)]},
        # Cloth-Armor (Magier-Tier 0)
        {"id": "cloth_helm",    "name": "Stoffkappe",   "output": "helmet",
         "material": "cloth",
         "inputs": [("cloth", 3)]},
        {"id": "cloth_chest",   "name": "Stoffrobe",    "output": "chestplate",
         "material": "cloth",
         "inputs": [("cloth", 5)]},
        # Leather-Armor
        {"id": "leather_helm",  "name": "Lederhelm",    "output": "helmet",
         "material": "leather",
         "inputs": [("leather", 2)]},
        {"id": "leather_boots", "name": "Lederstiefel", "output": "boots",
         "material": "leather",
         "inputs": [("leather", 2)]},
        # Fur-Armor (Survival-Tier 0)
        {"id": "fur_helm",      "name": "Pelzkappe",    "output": "helmet",
         "material": "fur",
         "inputs": [("leather", 1), ("cloth", 1)]},
        {"id": "fur_boots",     "name": "Pelzstiefel",  "output": "boots",
         "material": "fur",
         "inputs": [("leather", 1), ("cloth", 1)]},
        # Schmuck (kein material)
        {"id": "bone_amulet",   "name": "Knochenamulett","output": "amulet",
         "inputs": [("bone", 2), ("cloth", 1)]},
        # Sichel / Steinpickaxe — minimale Tools ohne Ingots, damit man ohne
        # geschmolzenes Metall ins Holzfäller-/Sammler-Game einsteigen kann
        # Sichel als Tool (Ernten von Gras/Pflanzen) — günstige Anfangswaffe-Alternative
        {"id": "wooden_sickle", "name": "Holzsichel",   "output": "sickle",
         "inputs": [("wood", 2), ("stone", 1)]},
        # scythe als Waffe (zweihänder) — größere Variante
        {"id": "wooden_scythe", "name": "Sense",        "output": "scythe",
         "material": "wood",
         "inputs": [("wood", 3), ("stone", 1)]},
        {"id": "stone_pickaxe","name": "Steinspitzhacke","output": "pickaxe",
         "inputs": [("wood", 2), ("stone", 3)]},
    ],
    "furnace": [
        # Ingot-Schmelze (nur was wir als Erz haben)
        {"id": "smelt_iron",     "name": "Eisen schmelzen",    "output": "iron_ingot",
         "inputs": [("iron_ore", 1)]},
        {"id": "smelt_steel",    "name": "Stahl schmieden",    "output": "steel_ingot",
         "inputs": [("iron_ore", 2)]},
        {"id": "smelt_silver",   "name": "Silber schmelzen",   "output": "silver_ingot",
         "inputs": [("silver_ore", 1)]},
        {"id": "smelt_gold",     "name": "Gold schmelzen",     "output": "gold_ingot",
         "inputs": [("gold_ore", 1)]},
        {"id": "smelt_mithril",  "name": "Mithril schmieden",  "output": "mithril_ingot",
         "inputs": [("mythril_ore", 1)]},
        # Tränke / Kochen
        {"id": "smelt_health",  "name": "Heiltrank brauen", "output": "health_potion",
         "inputs": [("herb", 3), ("crystal", 1)]},
        {"id": "smelt_mana",    "name": "Manatrank brauen", "output": "mana_potion",
         "inputs": [("herb", 2), ("silver_ore", 1)]},
        {"id": "bake_bread",    "name": "Brot backen",      "output": "bread",
         "inputs": [("wheat", 3)]},
        {"id": "cook_meat",     "name": "Fleisch garen",    "output": "cooked_meat",
         "inputs": [("raw_meat", 1), ("wood", 1)]},
        {"id": "cook_fish",     "name": "Fisch garen",      "output": "cooked_meat",
         "inputs": [("fish", 1), ("wood", 1)]},
    ],
    "anvil": [
        # Tier 2 — Eisen
        {"id": "iron_sword",    "name": "Eisenschwert", "output": "sword",
         "material": "iron",
         "inputs": [("iron_ingot", 2), ("wood", 1)]},
        {"id": "iron_helm",     "name": "Eisenhelm",    "output": "helmet",
         "material": "iron",
         "inputs": [("iron_ingot", 2)]},
        {"id": "iron_chest",    "name": "Eisenpanzer",  "output": "chestplate",
         "material": "iron",
         "inputs": [("iron_ingot", 3)]},
        {"id": "iron_shield",   "name": "Eisenschild",  "output": "shield",
         "material": "iron",
         "inputs": [("iron_ingot", 2), ("wood", 1)]},
        {"id": "iron_boots",    "name": "Eisenstiefel", "output": "boots",
         "material": "iron",
         "inputs": [("iron_ingot", 2)]},
        {"id": "iron_axe",      "name": "Eisenaxt",     "output": "axe",
         "material": "iron",
         "inputs": [("iron_ingot", 2), ("wood", 1)]},
        # Tier 3 — Stahl (legendäres Eisen)
        {"id": "steel_sword",   "name": "Stahlschwert", "output": "sword",
         "material": "steel",
         "inputs": [("steel_ingot", 2), ("wood", 1)]},
        {"id": "steel_chest",   "name": "Stahlpanzer",  "output": "chestplate",
         "material": "steel",
         "inputs": [("steel_ingot", 3)]},
        # Tier 4 — Silber (anti-undead)
        {"id": "silver_sword",  "name": "Silberschwert", "output": "sword",
         "material": "silver",
         "inputs": [("silver_ingot", 2), ("wood", 1)]},
        {"id": "silver_helm",   "name": "Silberhelm",    "output": "helmet",
         "material": "silver",
         "inputs": [("silver_ingot", 2)]},
        # Tier 5 — Gold (prestige)
        {"id": "gold_helm",     "name": "Goldhelm",      "output": "helmet",
         "material": "gold",
         "inputs": [("gold_ingot", 2)]},
        {"id": "gold_chest",    "name": "Goldpanzer",    "output": "chestplate",
         "material": "gold",
         "inputs": [("gold_ingot", 3)]},
        # Tier 6 — Mithril (endgame)
        {"id": "mithril_sword", "name": "Mithrilschwert","output": "sword",
         "material": "mithril",
         "inputs": [("mithril_ingot", 2), ("wood", 1)]},
        {"id": "mithril_chest", "name": "Mithrilpanzer", "output": "chestplate",
         "material": "mithril",
         "inputs": [("mithril_ingot", 3)]},
        # Tools (kein material — keine Asset-Varianten)
        {"id": "make_pickaxe",  "name": "Spitzhacke schmieden", "output": "pickaxe",
         "inputs": [("steel_ingot", 2), ("wood", 1)]},
        {"id": "make_hammer",   "name": "Hammer schmieden",     "output": "hammer",
         "inputs": [("steel_ingot", 1), ("wood", 2)]},
        {"id": "make_shovel",   "name": "Schaufel schmieden",   "output": "shovel",
         "inputs": [("steel_ingot", 1), ("wood", 1)]},
        {"id": "make_hoe",      "name": "Hacke schmieden",      "output": "hoe",
         "inputs": [("steel_ingot", 1), ("wood", 2)]},
    ],
}


def get_recipes(station: str) -> list[dict]:
    return RECIPES.get(station, [])


def find_recipe(station: str, recipe_id: str) -> dict | None:
    for r in RECIPES.get(station, []):
        if r["id"] == recipe_id:
            return r
    return None
