"""Overworld-Monster-Pool — 30 `overworld_*`-Mobs daten-getrieben.

Pendant zu `monster_longlist.py` (Dungeon-Pool). Liest das Manifest unter
`assets/monsters/overworld_pool/manifest.json` und kombiniert es mit
hard-codierten Stats/Biome-Profilen aus `overworld_monster.md`.

`combat.py` und `npc_worker.py` mergen die exportierten Tabellen in ihre
Laufzeit-Maps — daher KEIN direkter Import in andere Module nötig.

Tag/Nacht: `NIGHT_ONLY_KINDS` enthält die Mobs, die nur nachts spawnen
sollen (Undead). Mumie ist davon ausgenommen (Wüste, immer). `respawn_loop`
filtert die night-only-Kinds via `time_system.is_night()`.
"""
import json
import logging
import os

log = logging.getLogger("liege.overworld_monster_pool")

# Biome-IDs (Duplikat zu world.py — wie monster_longlist.py).
WATER, SAND, GRASS, FOREST, MOUNTAIN = 0, 1, 2, 3, 4
DESERT, JUNGLE, LAVA, SNOW, SWAMP = 5, 6, 7, 8, 9

_BASE = os.path.join(os.path.dirname(__file__), "..", "assets", "monsters", "overworld_pool")
_MANIFEST = os.path.join(_BASE, "manifest.json")

# Pro Mob: hp, dmg, speed, defense, aggro_range, tier, group_min, group_max,
# biomes (Set), is_boss, night_only.
# Werte 1:1 aus overworld_monster.md.
_STATS: dict[str, dict] = {
    # ── Undead (Section 1) ──
    "overworld_undead_shambler": {
        "hp": 35, "dmg": 6, "speed": 0.6, "defense": 0, "aggro": 5, "tier": 1,
        "group": (2, 4),
        "biomes": {GRASS, FOREST, JUNGLE, SWAMP, DESERT, SNOW},
        "is_boss": False, "night_only": True,
        "name": "Wandelnder Toter",
    },
    "overworld_undead_skeleton_warrior": {
        "hp": 28, "dmg": 9, "speed": 1.0, "defense": 2, "aggro": 6, "tier": 1,
        "group": (1, 3),
        "biomes": {GRASS, FOREST, SWAMP, SNOW},
        "is_boss": False, "night_only": True,
        "name": "Skelett-Krieger",
    },
    "overworld_undead_skeleton_archer": {
        "hp": 22, "dmg": 11, "speed": 0.9, "defense": 1, "aggro": 8, "tier": 1,
        "group": (1, 2),
        "biomes": {GRASS, FOREST, SWAMP, SNOW},
        "is_boss": False, "night_only": True,
        "name": "Skelett-Bogenschütze",
    },
    "overworld_undead_wight_lantern": {
        "hp": 50, "dmg": 12, "speed": 0.7, "defense": 3, "aggro": 5, "tier": 2,
        "group": (1, 1),
        "biomes": {GRASS, FOREST, SWAMP},
        "is_boss": False, "night_only": True,
        "name": "Laternen-Wight",
    },
    "overworld_undead_ghoul_stalker": {
        "hp": 40, "dmg": 10, "speed": 1.4, "defense": 1, "aggro": 4, "tier": 2,
        "group": (1, 2),
        "biomes": {SWAMP, JUNGLE},
        "is_boss": False, "night_only": True,
        "name": "Pirschender Ghul",
    },
    "overworld_undead_desert_mummy": {
        "hp": 55, "dmg": 8, "speed": 0.5, "defense": 4, "aggro": 4, "tier": 2,
        "group": (1, 2),
        "biomes": {DESERT},
        "is_boss": False, "night_only": False,  # Wüste: Tag UND Nacht
        "name": "Wüsten-Mumie",
    },
    # ── Goblinoid (Section 2) ──
    "overworld_goblin_scout": {
        "hp": 18, "dmg": 5, "speed": 1.3, "defense": 0, "aggro": 4, "tier": 1,
        "group": (3, 5),
        "biomes": {FOREST, GRASS},
        "is_boss": False, "night_only": False,
        "name": "Goblin-Späher",
    },
    "overworld_goblin_warrior": {
        "hp": 32, "dmg": 8, "speed": 1.0, "defense": 1, "aggro": 5, "tier": 1,
        "group": (1, 2),
        "biomes": {FOREST, GRASS},
        "is_boss": False, "night_only": False,
        "name": "Goblin-Krieger",
    },
    "overworld_goblin_shaman": {
        "hp": 25, "dmg": 6, "speed": 0.9, "defense": 0, "aggro": 6, "tier": 1,
        "group": (1, 1),
        "biomes": {FOREST, GRASS},
        "is_boss": False, "night_only": False,
        "name": "Goblin-Schamane",
    },
    "overworld_hobgoblin_legionnaire": {
        "hp": 70, "dmg": 14, "speed": 0.8, "defense": 5, "aggro": 6, "tier": 3,
        "group": (2, 3),
        "biomes": {SNOW, FOREST},
        "is_boss": False, "night_only": False,
        "name": "Hobgoblin-Legionär",
    },
    "overworld_orgrim_basher": {
        "hp": 110, "dmg": 22, "speed": 0.7, "defense": 4, "aggro": 7, "tier": 3,
        "group": (1, 1),
        "biomes": {SNOW, FOREST},
        "is_boss": True, "night_only": False,
        "name": "Orgrim-Schläger",
    },
    # ── Räuber (Section 3) ──
    "overworld_brigand_footpad": {
        "hp": 45, "dmg": 12, "speed": 1.0, "defense": 2, "aggro": 6, "tier": 2,
        "group": (1, 2),
        "biomes": {GRASS, FOREST, DESERT, JUNGLE},
        "is_boss": False, "night_only": False,
        "name": "Wegelagerer",
    },
    "overworld_brigand_archer": {
        "hp": 40, "dmg": 14, "speed": 1.1, "defense": 1, "aggro": 8, "tier": 2,
        "group": (1, 1),
        "biomes": {GRASS, FOREST, DESERT, JUNGLE},
        "is_boss": False, "night_only": False,
        "name": "Räuber-Bogenschütze",
    },
    "overworld_brigand_captain": {
        "hp": 95, "dmg": 18, "speed": 0.9, "defense": 4, "aggro": 7, "tier": 3,
        "group": (1, 1),
        "biomes": {GRASS, FOREST, DESERT, JUNGLE},
        "is_boss": True, "night_only": False,
        "name": "Räuber-Hauptmann",
    },
    "overworld_witch_hunter_renegade": {
        "hp": 65, "dmg": 16, "speed": 0.95, "defense": 3, "aggro": 7, "tier": 3,
        "group": (1, 1),
        "biomes": {GRASS, FOREST},
        "is_boss": False, "night_only": False,
        "name": "Abtrünniger Hexenjäger",
    },
    # ── Wild-Magie / Fae (Section 4) ──
    "overworld_will_o_wisp": {
        "hp": 12, "dmg": 4, "speed": 1.5, "defense": 0, "aggro": 4, "tier": 1,
        "group": (1, 3),
        "biomes": {SWAMP},
        "is_boss": False, "night_only": True,
        "name": "Irrlicht",
    },
    "overworld_briar_imp": {
        "hp": 20, "dmg": 7, "speed": 1.2, "defense": 1, "aggro": 3, "tier": 1,
        "group": (1, 2),
        "biomes": {FOREST, JUNGLE},
        "is_boss": False, "night_only": False,
        "name": "Dornen-Kobold",
    },
    "overworld_dryad_hunter": {
        "hp": 55, "dmg": 14, "speed": 1.0, "defense": 2, "aggro": 7, "tier": 2,
        "group": (1, 2),
        "biomes": {FOREST, JUNGLE},
        "is_boss": False, "night_only": False,
        "name": "Dryaden-Jägerin",
    },
    "overworld_mire_drowner": {
        "hp": 65, "dmg": 11, "speed": 0.5, "defense": 2, "aggro": 4, "tier": 2,
        "group": (1, 1),
        "biomes": {SWAMP},
        "is_boss": False, "night_only": False,
        "name": "Sumpf-Ziehende",
    },
    "overworld_swamp_witch_solo": {
        "hp": 75, "dmg": 13, "speed": 0.8, "defense": 2, "aggro": 6, "tier": 3,
        "group": (1, 1),
        "biomes": {SWAMP},
        "is_boss": False, "night_only": False,
        "name": "Sumpfhexe",
    },
    # ── Biome-Apex (Section 5) ──
    "overworld_apex_thornback_wolf": {
        "hp": 90, "dmg": 16, "speed": 1.3, "defense": 3, "aggro": 7, "tier": 3,
        "group": (1, 1),
        "biomes": {FOREST, JUNGLE},
        "is_boss": False, "night_only": False,
        "name": "Dornenrücken-Wolf",
    },
    "overworld_apex_silverback_boar": {
        "hp": 110, "dmg": 18, "speed": 1.1, "defense": 4, "aggro": 8, "tier": 3,
        "group": (1, 1),
        "biomes": {GRASS},
        "is_boss": False, "night_only": False,
        "name": "Silberrücken-Eber",
    },
    "overworld_apex_panther_shade": {
        "hp": 80, "dmg": 20, "speed": 1.6, "defense": 2, "aggro": 5, "tier": 3,
        "group": (1, 1),
        "biomes": {FOREST, JUNGLE},
        "is_boss": False, "night_only": True,  # Dämmerung+Nacht
        "name": "Schattenpanther",
    },
    "overworld_apex_glacier_lynx": {
        "hp": 75, "dmg": 14, "speed": 1.4, "defense": 2, "aggro": 6, "tier": 3,
        "group": (1, 1),
        "biomes": {SNOW},
        "is_boss": False, "night_only": False,
        "name": "Gletscher-Luchs",
    },
    "overworld_apex_dune_strider": {
        "hp": 70, "dmg": 13, "speed": 1.7, "defense": 1, "aggro": 6, "tier": 3,
        "group": (1, 1),
        "biomes": {DESERT},
        "is_boss": False, "night_only": False,
        "name": "Dünenläufer",
    },
    "overworld_apex_swamp_otter_clan": {
        "hp": 35, "dmg": 8, "speed": 1.2, "defense": 1, "aggro": 5, "tier": 2,
        "group": (3, 3),
        "biomes": {SWAMP},
        "is_boss": False, "night_only": False,
        "name": "Sumpf-Otter-Clan",
    },
    "overworld_apex_ridge_drake": {
        "hp": 130, "dmg": 20, "speed": 0.9, "defense": 5, "aggro": 7, "tier": 4,
        "group": (1, 1),
        "biomes": {SNOW, FOREST},
        "is_boss": True, "night_only": False,
        "name": "Felsdrache",
    },
    "overworld_apex_cliff_kraken_arm": {
        "hp": 150, "dmg": 22, "speed": 0.0, "defense": 6, "aggro": 4, "tier": 4,
        "group": (1, 1),
        "biomes": {SAND},  # Küste über Sand-Tile
        "is_boss": True, "night_only": False,
        "name": "Klippen-Kraken-Arm",
    },
    # ── Aberrant (Section 6) ──
    "overworld_aberrant_eyeless_pilgrim": {
        "hp": 60, "dmg": 12, "speed": 1.0, "defense": 2, "aggro": 99, "tier": 3,
        "group": (1, 1),
        "biomes": {GRASS, FOREST, DESERT, JUNGLE, SWAMP, SNOW},
        "is_boss": False, "night_only": False,
        "name": "Augenloser Pilger",
    },
    "overworld_aberrant_star_mote_imp": {
        "hp": 30, "dmg": 10, "speed": 1.2, "defense": 0, "aggro": 5, "tier": 2,
        "group": (2, 3),
        "biomes": {GRASS, FOREST, DESERT},
        "is_boss": False, "night_only": False,
        "name": "Sternsplitter-Wesen",
    },
}


def _validate_against_manifest() -> None:
    """Sanity-Check: alle _STATS-Keys müssen im Manifest stehen und umgekehrt."""
    try:
        m = json.load(open(_MANIFEST, encoding="utf-8"))
    except Exception:
        log.exception("overworld_pool: Manifest laden fehlgeschlagen")
        return
    manifest_ids = {it["id"] for it in m.get("items", [])}
    stats_ids = set(_STATS.keys())
    missing_in_stats = manifest_ids - stats_ids
    missing_in_manifest = stats_ids - manifest_ids
    if missing_in_stats:
        log.warning("overworld_pool: %d Manifest-IDs ohne Stats: %s",
                    len(missing_in_stats), sorted(missing_in_stats))
    if missing_in_manifest:
        log.warning("overworld_pool: %d Stats ohne Manifest-Eintrag: %s",
                    len(missing_in_manifest), sorted(missing_in_manifest))
    if not missing_in_stats and not missing_in_manifest:
        log.info("overworld_pool: %d Mobs, Stats und Manifest synchron.",
                 len(stats_ids))


def _build():
    kinds, damage, hp, overrides = [], {}, {}, {}
    spawn, boss, names, night_only = {}, set(), {}, set()
    for kid, s in _STATS.items():
        kinds.append(kid)
        damage[kid] = s["dmg"]
        hp[kid] = s["hp"]
        overrides[kid] = {
            "defense": s["defense"],
            "speed": round(s["speed"], 2),
            "tier": s["tier"],
            "aggro_range": s["aggro"],
        }
        names[kid] = s["name"]
        spawn[kid] = {"group": s["group"], "biomes": set(s["biomes"])}
        if s["is_boss"]:
            boss.add(kid)
        if s["night_only"]:
            night_only.add(kid)
    return dict(KINDS=kinds, DAMAGE=damage, HP=hp, STAT_OVERRIDES=overrides,
                SPAWN_PROFILE=spawn, BOSS_KINDS=boss, NAMES=names,
                NIGHT_ONLY=night_only)


_validate_against_manifest()
_data = _build()
KINDS = _data["KINDS"]
DAMAGE = _data["DAMAGE"]
HP = _data["HP"]
STAT_OVERRIDES = _data["STAT_OVERRIDES"]
SPAWN_PROFILE = _data["SPAWN_PROFILE"]
BOSS_KINDS = _data["BOSS_KINDS"]
NAMES = _data["NAMES"]
NIGHT_ONLY = _data["NIGHT_ONLY"]
