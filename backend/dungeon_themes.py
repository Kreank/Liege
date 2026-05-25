"""Dungeon-Theme-System (Recherche-Empfehlung).

5 Themes mit eigenen Mob-Pools, Loot-Pools, Room-Tags, Atmosphäre.
Layout-Generator bleibt themen-agnostisch (BSP in dungeon_world.py);
Theme bestimmt nur die Befüllung.

Themes:
    crypt    — Untote (skeleton, zombie, necromancer), Bone/Necrotic-Loot
    mine     — Goblins + Felsen-Insekten, Ore/Crystal-Loot
    temple   — Konstrukte + Kultisten, Holy/Arcane-Loot
    ruin     — Banditen + Wölfe, Gold/Equipment-Loot
    cave     — Spinnen + Bären, Cloth/Bone/Mushroom-Loot
"""
import random
import logging

log = logging.getLogger("liege.dungeon_themes")


THEMES = {
    "crypt": {
        "label": "Krypta",
        "description": "Vergessene Grabkammern, kalt und still — Tote ruhen schlecht.",
        "mob_pool":       ["skeleton", "zombie", "bat"],
        "boss_pool":      ["necromancer"],
        "loot_kinds":     ["bone", "silver_ore", "scroll", "rune_stone", "amulet"],
        "rare_loot":      ["spell_book", "ring"],
        "room_decor":     ["sarcophagus", "wall_torch", "gravestone"],
        "ambient_color":  "#3a2848",
        "affix_themes":   ["spectral", "soulbound"],
    },
    "mine": {
        "label": "Verlassene Mine",
        "description": "Tunnel voller Erz und Schemen vergangener Bergleute.",
        "mob_pool":       ["goblin", "rat", "spider"],
        "boss_pool":      ["ogre"],
        "loot_kinds":     ["iron_ore", "silver_ore", "gold_ore", "crystal", "stone"],
        "rare_loot":      ["mythril_ore", "steel_ingot", "pickaxe"],
        "room_decor":     ["barrel", "crate", "wall_torch"],
        "ambient_color":  "#403828",
        "affix_themes":   ["sharp", "stonebreaker"],
    },
    "temple": {
        "label": "Alter Tempel",
        "description": "Heilig oder verflucht — niemand weiß es noch genau.",
        "mob_pool":       ["skeleton", "zombie", "slime"],
        "boss_pool":      ["necromancer", "ogre"],
        "loot_kinds":     ["scroll", "rune_stone", "crystal", "gold_ore", "amulet"],
        "rare_loot":      ["spell_book", "staff", "wand"],
        "room_decor":     ["altar", "brazier", "wall_torch", "statue_broken"],
        "ambient_color":  "#403048",
        "affix_themes":   ["blazing", "godslayer", "ancient"],
    },
    "ruin": {
        "label": "Burgruine",
        "description": "Verfallene Mauern und vergessene Schätze des alten Reichs.",
        "mob_pool":       ["bandit", "wolf", "skeleton"],
        "boss_pool":      ["bear"],
        "loot_kinds":     ["sword", "bow", "leather", "cloth", "gold_ore"],
        "rare_loot":      ["chestplate", "helmet", "shield", "crossbow"],
        "room_decor":     ["broken_cart", "fence", "treasure_chest"],
        "ambient_color":  "#403828",
        "affix_themes":   ["sharp", "swift", "fortified"],
    },
    "cave": {
        "label": "Tiefe Höhle",
        "description": "Feuchte Tropfsteine und Geräusche aus der Dunkelheit.",
        "mob_pool":       ["spider", "bat", "bear", "boar"],
        "boss_pool":      ["bear"],
        "loot_kinds":     ["herb", "mushroom_food", "crystal", "bone", "raw_meat"],
        "rare_loot":      ["leather", "cloth"],
        "room_decor":     ["bones_scatter", "rubble", "mushrooms"],
        "ambient_color":  "#283038",
        "affix_themes":   ["frost", "swift_runner"],
    },
}


def list_themes() -> list[str]:
    return list(THEMES.keys())


def get_theme(theme_key: str) -> dict | None:
    return THEMES.get(theme_key)


def pick_theme_for_seed(seed: int) -> str:
    """Deterministisch Theme aus Seed wählen."""
    keys = list(THEMES.keys())
    return keys[seed % len(keys)]


def random_mob_for_theme(theme_key: str, is_boss: bool = False) -> str:
    t = THEMES.get(theme_key)
    if not t:
        return "skeleton"
    pool = t["boss_pool"] if is_boss else t["mob_pool"]
    return random.choice(pool) if pool else "skeleton"


def random_loot_for_theme(theme_key: str, rare: bool = False) -> str:
    t = THEMES.get(theme_key)
    if not t:
        return "bone"
    pool = t["rare_loot"] if rare else t["loot_kinds"]
    return random.choice(pool) if pool else "bone"


def random_decor_for_theme(theme_key: str) -> str:
    t = THEMES.get(theme_key)
    if not t:
        return "wall_torch"
    return random.choice(t["room_decor"]) if t["room_decor"] else "wall_torch"


def theme_lore_prompt(theme_key: str) -> str:
    """Theme-Beschreibung für LLM-Prompts (Region-History etc.)."""
    t = THEMES.get(theme_key)
    return t["description"] if t else "Ein unheimlicher Ort."
