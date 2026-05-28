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
    ],
}


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
