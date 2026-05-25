"""Einfache Crafting-Rezepte pro Station."""

RECIPES = {
    "workbench": [
        {"id": "wooden_sword",  "name": "Holzschwert",  "output": "sword",
         "inputs": [("wood", 3)]},
        {"id": "stone_axe",     "name": "Steinaxt",     "output": "axe",
         "inputs": [("wood", 2), ("stone", 2)]},
        {"id": "wooden_bow",    "name": "Holzbogen",    "output": "bow",
         "inputs": [("wood", 3), ("cloth", 1)]},
        {"id": "leather_helm",  "name": "Lederhelm",    "output": "helmet",
         "inputs": [("leather", 2)]},
        {"id": "leather_boots", "name": "Lederstiefel", "output": "boots",
         "inputs": [("leather", 2)]},
        {"id": "wooden_shield", "name": "Holzschild",   "output": "shield",
         "inputs": [("wood", 4)]},
        {"id": "bone_amulet",   "name": "Knochenamulett","output": "amulet",
         "inputs": [("bone", 2), ("cloth", 1)]},
    ],
    "furnace": [
        {"id": "smelt_steel",   "name": "Stahl schmieden", "output": "steel_ingot",
         "inputs": [("iron_ore", 2)]},
        {"id": "smelt_health",  "name": "Heiltrank brauen","output": "health_potion",
         "inputs": [("herb", 3), ("crystal", 1)]},
        {"id": "smelt_mana",    "name": "Manatrank brauen","output": "mana_potion",
         "inputs": [("herb", 2), ("silver_ore", 1)]},
        # Kochen
        {"id": "bake_bread",    "name": "Brot backen",     "output": "bread",
         "inputs": [("wheat", 3)]},
        {"id": "cook_meat",     "name": "Fleisch garen",   "output": "cooked_meat",
         "inputs": [("raw_meat", 1), ("wood", 1)]},
        {"id": "cook_fish",     "name": "Fisch garen",     "output": "cooked_meat",
         "inputs": [("fish", 1), ("wood", 1)]},
    ],
    "anvil": [
        {"id": "iron_chest",    "name": "Eisenpanzer",  "output": "chestplate",
         "inputs": [("steel_ingot", 3)]},
        {"id": "iron_helm",     "name": "Eisenhelm",    "output": "helmet",
         "inputs": [("steel_ingot", 2)]},
        {"id": "iron_sword",    "name": "Eisenschwert", "output": "sword",
         "inputs": [("steel_ingot", 2), ("wood", 1)]},
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
