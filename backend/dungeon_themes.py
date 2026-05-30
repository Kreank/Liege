"""Dungeon-Theme-System (Welle 35 — 2026-05-30).

Themes bestimmen Mob-Pool, Boss-Pool, Loot, Decor-Props, Fallen-Art, Tint
(Wand/Boden-Färbung, da keine themen-spezifischen Tile-Assets existieren) und
einen optionalen Ambient-Overlay. Der Layout-Generator (dungeon_world.py) ist
themen-agnostisch — das Theme bestimmt nur Befüllung + Optik.

Pools enthalten `creature_*`-Slugs aus dem 128-er Manifest
(`assets/monsters/generated_longlist/manifest.json`), die von
`monster_longlist.py` ins Combat-System eingespeist werden (siehe
`combat.py:744` — `_ml.DAMAGE/HP/STAT_OVERRIDES/BOSS_KINDS`).

Klassiker:    crypt, mine, temple, ruin, cave
Biome-Themes: lava, ice, desert, jungle, bog
"""
import random
import logging

log = logging.getLogger("liege.dungeon_themes")


THEMES = {
    "crypt": {
        "label": "Krypta",
        "description": "Vergessene Grabkammern, kalt und still — Tote ruhen schlecht.",
        "mob_pool":  [
            "creature_shambling_corpse",
            "creature_plague_walker",
            "creature_rotmaw",
            "creature_husk_runner",
            "creature_bone_skirmisher",
            "creature_bone_archer",
            "creature_armored_revenant",
            "creature_grave_drinker_ghoul",
            "creature_wailing_specter",
            "creature_lantern_wight",
        ],
        "boss_pool": [
            "creature_crypt_lord",
            "creature_lich_archivist",
            "creature_vampire_lordling",
            "creature_ossuary_titan",
            "creature_boss_dungeon_undying_king",
        ],
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
        "mob_pool":  [
            "creature_clay_homunculus",
            "creature_bone_ossuary_construct",
            "creature_runic_jar",
            "creature_stone_elemental_lumbering",
            "creature_iron_sentinel",
            "creature_dragon_pup_litter",
        ],
        "boss_pool": [
            "creature_grindstone_golem",
            "creature_voidforge_juggernaut",
            "creature_chromatic_drake_blue",
        ],
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
        "mob_pool":  [
            "creature_will_o_wisp",
            "creature_fire_elemental_small",
            "creature_water_elemental_brine",
            "creature_eyeless_pilgrim",
            "creature_hollow_marrow_serpent",
            "creature_inverted_pilgrim_swarm",
            "creature_star_mote_imp",
            "creature_fae_changeling",
            "creature_arcane_orrery_guardian",
        ],
        "boss_pool": [
            "creature_thing_in_the_well",
            "creature_choir_of_mouths",
            "creature_geometry_horror",
            "creature_drowned_cathedral_thing",
            "creature_boss_coast_kraken_arm",
        ],
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
        "mob_pool":  [
            "creature_road_brigand",
            "creature_brigand_archer",
            "creature_brigand_brute",
            "creature_smoke_bandit",
            "creature_deserter_soldier",
            "creature_slaver_with_chain",
            "creature_pit_dog_handler",
            "creature_pit_dog",
            "creature_grin_goblin_scrapper",
            "creature_grin_goblin_shaman",
            "creature_warboar_mount",
            "creature_blood_kin_warrior",
            "creature_blood_kin_screamer",
            "creature_silent_cultist",
            "creature_chittering_spider_nest",
            "creature_hobgoblin_legionnaire",
            "creature_orgrim_basher",
            "creature_witch_hunter_renegade",
            "creature_swamp_witch",
        ],
        "boss_pool": [
            "creature_brigand_captain",
            "creature_grin_goblin_warchief",
            "creature_void_speaker",
            "creature_boss_capital_traitor_general",
        ],
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
        "mob_pool":  [
            "creature_chittering_spider_nest",
            "creature_giant_centipede",
            "creature_panther_shade",
            "creature_dragon_whelp",
            "creature_dragon_pup_litter",
        ],
        "boss_pool": [
            "creature_wyrmling_basilisk",
            "creature_ancient_dragon_lord",
        ],
        "loot_kinds": ["herb", "mushroom_food", "crystal", "bone", "raw_meat"],
        "rare_loot": ["leather", "cloth"],
        "room_decor": ["bones_scatter", "rubble", "mushrooms"],
        "trap_kinds": ["spike_trap", "rockfall_trap"],
        "wall_tint": 0x8898a0, "floor_tint": 0x788890,
        "ambient_color": "#283038", "ambient": None,
        "affix_themes": ["frost", "stonebreaker"],
    },
    # ── Biome-Themes ──────────────────────────────────────────────────────
    "lava": {
        "label": "Magmaschlund",
        "description": "Glühende Spalten, erstickende Hitze — hier lebt nur Feuer.",
        "mob_pool":  [
            "creature_ember_wasp",
            "creature_fire_elemental_small",
            "creature_ash_druid",
            "creature_will_o_wisp",
            "creature_lightning_djinn",
            "creature_star_mote_imp",
        ],
        "boss_pool": [
            "creature_fire_elemental_lord",
            "creature_starlight_unicorn_corrupt",
            "creature_chromatic_drake_red",
            "creature_boss_volcano_smith_demon",
        ],
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
        "mob_pool":  [
            "creature_thornback_hare",
            "creature_glacier_lynx",
            "creature_iron_horn_aurochs",
            "creature_dryad_hunter",
            "creature_runic_jar",
        ],
        "boss_pool": [
            "creature_glacier_juggernaut_bear",
            "creature_frost_revenant_yeti",
            "creature_chromatic_drake_white",
            "creature_boss_mountain_avalanche_giant",
            "creature_boss_sky_bound_roc",
        ],
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
        "mob_pool":  [
            "creature_ember_wasp",
            "creature_dune_strider",
            "creature_hyena_pack_leader",
            "creature_normal_hyena",
            "creature_wyrmling_basilisk",
        ],
        "boss_pool": [
            "creature_dune_terror_worm",
            "creature_canyon_wyrm",
            "creature_boss_desert_pharaoh_revenant",
        ],
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
        "mob_pool":  [
            "creature_carrion_crow",
            "creature_thornback_hare",
            "creature_burrow_grub",
            "creature_glass_wing_moth",
            "creature_briar_imp",
            "creature_dire_wolf",
            "creature_silverback_boar",
            "creature_panther_shade",
            "creature_brigand_archer",
            "creature_treant_warden",
            "creature_dryad_hunter",
        ],
        "boss_pool": [
            "creature_grove_stag_corrupted",
            "creature_chromatic_drake_green",
            "creature_boss_forest_old_mother",
        ],
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
        "mob_pool":  [
            "creature_marsh_rat_swarm",
            "creature_giant_centipede",
            "creature_blood_leech_cluster",
            "creature_bog_toad",
            "creature_grasping_kelp",
            "creature_swamp_otter_clan",
            "creature_mire_drowner",
            "creature_riverbank_crocodilian",
            "creature_water_elemental_brine",
        ],
        "boss_pool": [
            "creature_thornmaw",
            "creature_marsh_naga",
            "creature_bog_titan_elk",
            "creature_chromatic_drake_black",
            "creature_boss_swamp_witchking",
            "creature_boss_river_kelpie_queen",
        ],
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

# Generic fallback wenn ein Theme keinen Pool hat — verlässlicher
# creature_*-Slug aus dem 128-er Pool (vs. das alte "skeleton" das nicht
# mehr existiert seit Welle 35).
_DEFAULT_FALLBACK_MOB = "creature_shambling_corpse"


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
        return _DEFAULT_FALLBACK_MOB
    pool = t["boss_pool"] if is_boss else t["mob_pool"]
    return random.choice(pool) if pool else _DEFAULT_FALLBACK_MOB


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
