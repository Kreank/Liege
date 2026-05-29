"""Dungeon-Theme-System (Überarbeitung 2026-05-29).

Themes bestimmen Mob-Pool, Boss-Pool, Loot, Decor-Props, Fallen-Art, Tint
(Wand/Boden-Färbung, da keine themen-spezifischen Tile-Assets existieren) und
einen optionalen Ambient-Overlay. Der Layout-Generator (dungeon_world.py) ist
themen-agnostisch — das Theme bestimmt nur Befüllung + Optik.

Klassiker: crypt, mine, temple, ruin, cave
Biome-Themes (nach Eingangs-Biome gewählt): lava, ice, desert, jungle, bog
"""
import random
import logging

log = logging.getLogger("liege.dungeon_themes")


THEMES = {
    "crypt": {
        "label": "Krypta",
        "description": "Vergessene Grabkammern, kalt und still — Tote ruhen schlecht.",
        "mob_pool":  ["skeleton", "zombie", "bat", "bone_crawler"],
        "boss_pool": ["necromancer"],
        "loot_kinds": ["bone", "silver_ore", "scroll", "rune_stone", "amulet"],
        "rare_loot": ["spell_book", "ring"],
        "room_decor": ["sarcophagus", "wall_torch", "gravestone"],
        "trap_kinds": ["spike_trap", "poison_trap"],
        "wall_tint": 0x9a8fb0, "floor_tint": 0x8a8290,
        "ambient_color": "#3a2848", "ambient": None,
        "affix_themes": ["spectral", "soulbound"],
    },
    "mine": {
        "label": "Verlassene Mine",
        "description": "Tunnel voller Erz und Schemen vergangener Bergleute.",
        "mob_pool":  ["goblin", "rat", "spider", "crystal_beetle"],
        "boss_pool": ["ogre", "stone_golem"],
        "loot_kinds": ["iron_ore", "silver_ore", "gold_ore", "crystal", "stone"],
        "rare_loot": ["mythril_ore", "steel_ingot", "pickaxe"],
        "room_decor": ["barrel", "crate", "wall_torch"],
        "trap_kinds": ["spike_trap", "rockfall_trap"],
        "wall_tint": 0xb0a080, "floor_tint": 0xa09578,
        "ambient_color": "#403828", "ambient": None,
        "affix_themes": ["sharp", "stonebreaker"],
    },
    "temple": {
        "label": "Alter Tempel",
        "description": "Heilig oder verflucht — niemand weiß es noch genau.",
        "mob_pool":  ["skeleton", "gargoyle", "slime", "crystal_golem"],
        "boss_pool": ["minotaur", "necromancer"],
        "loot_kinds": ["scroll", "rune_stone", "crystal", "gold_ore", "amulet"],
        "rare_loot": ["spell_book", "staff", "wand"],
        "room_decor": ["altar", "brazier", "wall_torch", "statue_broken"],
        "trap_kinds": ["dart_trap", "spike_trap"],
        "wall_tint": 0xc8c0d0, "floor_tint": 0xb8b0c0,
        "ambient_color": "#403048", "ambient": None,
        "affix_themes": ["blazing", "godslayer", "ancient"],
    },
    "ruin": {
        "label": "Burgruine",
        "description": "Verfallene Mauern und vergessene Schätze des alten Reichs.",
        "mob_pool":  ["bandit", "wolf", "skeleton", "thief"],
        "boss_pool": ["bear", "ogre"],
        "loot_kinds": ["sword", "bow", "leather", "cloth", "gold_ore"],
        "rare_loot": ["chestplate", "helmet", "shield", "crossbow"],
        "room_decor": ["broken_cart", "rubble", "barrel", "wall_torch"],
        "trap_kinds": ["spike_trap", "dart_trap"],
        "wall_tint": 0xa8a090, "floor_tint": 0x988f7e,
        "ambient_color": "#403828", "ambient": None,
        "affix_themes": ["sharp", "swift", "fortified"],
    },
    "cave": {
        "label": "Tiefe Höhle",
        "description": "Feuchte Tropfsteine und Geräusche aus der Dunkelheit.",
        "mob_pool":  ["spider", "bat", "bear", "boar", "giant_spider"],
        "boss_pool": ["cave_bear", "bear"],
        "loot_kinds": ["herb", "mushroom_food", "crystal", "bone", "raw_meat"],
        "rare_loot": ["leather", "cloth"],
        "room_decor": ["bones_scatter", "rubble", "mushrooms"],
        "trap_kinds": ["spike_trap", "rockfall_trap"],
        "wall_tint": 0x8898a0, "floor_tint": 0x788890,
        "ambient_color": "#283038", "ambient": None,
        "affix_themes": ["frost", "swift_runner"],
    },
    # ── Biome-Themes ──────────────────────────────────────────────────────
    "lava": {
        "label": "Magmaschlund",
        "description": "Glühende Spalten, erstickende Hitze — hier lebt nur Feuer.",
        "mob_pool":  ["fire_imp", "ember_newt", "ember_rat", "shadow_bat"],
        "boss_pool": ["dragon_whelp", "hydra"],
        "loot_kinds": ["crystal", "gold_ore", "rune_stone", "bone"],
        "rare_loot": ["staff", "ring", "mythril_ore"],
        "room_decor": ["brazier", "wall_torch", "bones_scatter"],
        "trap_kinds": ["fire_trap", "spike_trap"],
        "wall_tint": 0xd07050, "floor_tint": 0xb05838,
        "ambient_color": "#5a1c10", "ambient": "volcanic_ash",
        "affix_themes": ["blazing", "ancient"],
    },
    "ice": {
        "label": "Frosthöhle",
        "description": "Ewiges Eis, beißende Kälte, glitzernde Todesfallen.",
        "mob_pool":  ["frost_sprite", "wolf", "dire_wolf", "bat"],
        "boss_pool": ["polar_bear", "cave_bear"],
        "loot_kinds": ["crystal", "silver_ore", "rune_stone", "leather"],
        "rare_loot": ["shield", "ring", "amulet"],
        "room_decor": ["wall_torch", "rubble", "bones_scatter"],
        "trap_kinds": ["frost_trap", "spike_trap"],
        "wall_tint": 0xbfe0f0, "floor_tint": 0xa8cce0,
        "ambient_color": "#1a3550", "ambient": None,
        "affix_themes": ["frost", "swift"],
    },
    "desert": {
        "label": "Sandgruft",
        "description": "Sonnenverbrannte Gänge unter dem Wüstensand, voller Schlangen.",
        "mob_pool":  ["cobra", "thorn_scarab", "bandit", "crystal_tick"],
        "boss_pool": ["basilisk", "manticore"],
        "loot_kinds": ["gold_ore", "scroll", "rune_stone", "cloth"],
        "rare_loot": ["amulet", "wand", "bow"],
        "room_decor": ["bones_scatter", "statue_broken", "gravestone"],
        "trap_kinds": ["dart_trap", "spike_trap"],
        "wall_tint": 0xe0c890, "floor_tint": 0xd0b878,
        "ambient_color": "#5a4520", "ambient": "desert_heat_haze",
        "affix_themes": ["sharp", "ancient"],
    },
    "jungle": {
        "label": "Überwucherte Ruine",
        "description": "Wurzeln sprengen das Mauerwerk, Gift tropft von den Ranken.",
        "mob_pool":  ["spider", "giant_spider", "boar", "thornling", "mushroom_imp"],
        "boss_pool": ["chimera", "treant"],
        "loot_kinds": ["herb", "mushroom_food", "crystal", "leather", "bone"],
        "rare_loot": ["staff", "ring", "cloth"],
        "room_decor": ["mushrooms", "rubble", "bones_scatter"],
        "trap_kinds": ["poison_trap", "spike_trap"],
        "wall_tint": 0x7faa66, "floor_tint": 0x6f9658,
        "ambient_color": "#1f3a1c", "ambient": "jungle_humidity_motes",
        "affix_themes": ["swift_runner", "ancient"],
    },
    "bog": {
        "label": "Sumpfgewölbe",
        "description": "Modriges Wasser, Faulgas und kriechendes Unheil.",
        "mob_pool":  ["slime", "slimelet", "spider", "thornling", "bat"],
        "boss_pool": ["bone_crawler", "treant"],
        "loot_kinds": ["herb", "mushroom_food", "bone", "cloth", "rune_stone"],
        "rare_loot": ["ring", "staff"],
        "room_decor": ["mushrooms", "bones_scatter", "rubble"],
        "trap_kinds": ["poison_trap", "spike_trap"],
        "wall_tint": 0x8aa07a, "floor_tint": 0x76906a,
        "ambient_color": "#23301f", "ambient": "swamp_mist",
        "affix_themes": ["frost", "swift_runner"],
    },
}

# Overworld-Tile-IDs (siehe world.py): WATER0 SAND1 GRASS2 FOREST3 MOUNTAIN4
# DESERT5 JUNGLE6 LAVA7 SNOW8 SWAMP9. → Theme nach Eingangs-Biome.
_BIOME_THEME = {
    1: "desert", 5: "desert",
    6: "jungle",
    7: "lava",
    8: "ice",
    9: "bog",
    4: "mine",
    3: "cave",
}
_GRASS_THEMES = ["crypt", "ruin", "temple"]


def theme_for_biome(tile_id: int, seed: int = 0) -> str:
    """Wählt ein Dungeon-Theme passend zum Overworld-Biome des Eingangs."""
    t = _BIOME_THEME.get(tile_id)
    if t:
        return t
    return _GRASS_THEMES[seed % len(_GRASS_THEMES)]


def list_themes() -> list[str]:
    return list(THEMES.keys())


def get_theme(theme_key: str) -> dict | None:
    return THEMES.get(theme_key)


def pick_theme_for_seed(seed: int) -> str:
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
    t = THEMES.get(theme_key)
    return t["description"] if t else "Ein unheimlicher Ort."
