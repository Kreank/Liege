"""Harvest-Logik mit Multi-Hit-Durability.

Jede natürliche Struktur hat eine `durability` (Anzahl Schläge bis zerstört).
Pro Schlag wird ein kleinerer `yield` ausgewürfelt (1-2 Items typisch).
Später wird Werkzeug-Equip die Schläge reduzieren und/oder Yield erhöhen."""

import random

# Durability (Anzahl Schläge bis Struktur weg). Default 1 wenn nicht hier gelistet.
DURABILITY = {
    # Bäume — robuster als Stümpfe
    "tree_oak":      5,
    "tree_pine":     4,
    "tree_dead":     2,
    "tree_stump":    1,
    "fallen_log":    2,
    # Felsen — der „dicke" Fall vom User
    "rock_small":    2,
    "rock_large":    5,
    "rock_mossy":    4,
    # Pflanzen — 1 Schlag reicht
    "bush":          1,
    "tall_grass":    1,
    "flowers":       1,
    "mushrooms":     1,
    "reeds":         1,
    "lily_pads":     1,
    # Settlement-Reste
    "broken_cart":   3,
    "barrel":        2,
    "crate":         2,
    "sack":          1,
    "fence":         1,
    # Ruinen
    "ruin_pillar":   4,
    "rubble":        1,
    "statue_broken": 3,
    # Wasser-Wracks
    "shipwreck":     6,
    "dock_straight": 2,
    "wooden_bridge": 3,
    # Neue Deko
    "camp_tent":     2,
    "cooking_pot":   1,
    "bones_scatter": 1,
    "gravestone":    3,
    "dock_corner":   2,
    "boat_small":    4,
    "anchor":        2,
    "fishing_net":   1,
    "driftwood":     1,
    # Welle 12 — Biome-Props
    "cactus":         3,
    "desert_skull":   1,
    "dry_bush":       1,
    "jungle_flower":  1,
    "jungle_vines":   2,
    "palm_tree":      5,
    "lava_rock":      4,
    "frozen_bush":    1,
    "ice_crystal":    3,
    "snow_rock":      3,
    "swamp_bubbles":  1,
    "swamp_log":      2,
}

# Yield pro Schlag: [(item_kind, min, max, chance_in_pct), ...]
YIELD_PER_HIT = {
    "tree_oak":      [("wood", 1, 2, 100), ("apple", 0, 1, 35)],
    "tree_pine":     [("wood", 1, 2, 100)],
    "tree_dead":     [("wood", 1, 1, 100)],
    "tree_stump":    [("wood", 1, 1, 100)],
    "fallen_log":    [("wood", 1, 2, 100)],
    "rock_small":    [("stone", 1, 2, 100), ("iron_ore", 0, 1, 10)],
    "rock_large":    [("stone", 1, 2, 100), ("iron_ore", 0, 1, 15), ("silver_ore", 0, 1, 5)],
    "rock_mossy":    [("stone", 1, 1, 100), ("crystal", 0, 1, 8),  ("herb", 0, 1, 20)],
    "bush":          [("herb", 0, 1, 50), ("cloth", 0, 1, 30), ("berries", 0, 1, 45)],
    "tall_grass":    [("cloth", 1, 1, 80), ("herb", 0, 1, 20), ("wheat", 0, 1, 15)],
    "flowers":       [("herb", 1, 1, 100)],
    "mushrooms":     [("herb", 1, 1, 70), ("mushroom_food", 1, 2, 80)],
    "reeds":         [("cloth", 1, 1, 100)],
    "lily_pads":     [("herb", 0, 1, 50)],
    "broken_cart":   [("wood", 1, 2, 100), ("iron_ore", 0, 1, 12)],
    "barrel":        [("wood", 1, 1, 100)],
    "crate":         [("wood", 1, 1, 100)],
    "sack":          [("cloth", 1, 1, 100)],
    "fence":         [("wood", 1, 1, 100)],
    "ruin_pillar":   [("stone", 1, 1, 100)],
    "rubble":        [("stone", 1, 1, 100)],
    "statue_broken": [("stone", 1, 1, 100)],
    "shipwreck":     [("wood", 1, 2, 100), ("cloth", 0, 1, 30), ("gold_ore", 0, 1, 8)],
    "dock_straight": [("wood", 1, 1, 100)],
    "wooden_bridge": [("wood", 1, 2, 100)],
    # Neue Deko-Harvests
    "camp_tent":     [("cloth", 2, 3, 100), ("wood", 0, 1, 50)],
    "cooking_pot":   [("iron_ore", 1, 1, 100), ("stone", 0, 1, 30)],
    "bones_scatter": [("bone", 1, 2, 100)],
    "gravestone":    [("stone", 1, 2, 100), ("bone", 0, 1, 40)],
    "dock_corner":   [("wood", 1, 2, 100)],
    "boat_small":    [("wood", 2, 4, 100), ("cloth", 0, 1, 40)],
    "anchor":        [("iron_ore", 1, 2, 100)],
    "fishing_net":   [("cloth", 1, 2, 100), ("fish", 1, 2, 80)],
    "driftwood":     [("wood", 1, 1, 100)],
    # Welle 12 — Biome-Props
    "cactus":         [("herb", 1, 2, 100), ("cloth", 0, 1, 30)],
    "desert_skull":   [("bone", 1, 2, 100)],
    "dry_bush":       [("cloth", 1, 1, 70), ("wood", 0, 1, 30)],
    "jungle_flower":  [("herb", 1, 2, 100)],
    "jungle_vines":   [("cloth", 1, 2, 100), ("herb", 0, 1, 30)],
    "palm_tree":      [("wood", 2, 3, 100), ("apple", 0, 1, 20)],
    "lava_rock":      [("stone", 1, 2, 100), ("crystal", 0, 1, 25), ("iron_ore", 0, 1, 30)],
    "frozen_bush":    [("herb", 0, 1, 50), ("cloth", 0, 1, 30)],
    "ice_crystal":    [("crystal", 1, 2, 100)],
    "snow_rock":      [("stone", 1, 2, 100), ("crystal", 0, 1, 15)],
    "swamp_bubbles":  [("herb", 0, 1, 60)],
    "swamp_log":      [("wood", 1, 2, 100), ("mushroom_food", 0, 1, 30)],
}

HARVESTABLE_TYPES = set(YIELD_PER_HIT.keys())


def is_harvestable(structure_type: str) -> bool:
    return structure_type in HARVESTABLE_TYPES


def initial_durability(structure_type: str) -> int:
    return DURABILITY.get(structure_type, 1)


def roll_hit_yield(structure_type: str) -> list[str]:
    """Returnt die Items eines einzelnen Schlags. Kann leer sein."""
    entries = YIELD_PER_HIT.get(structure_type)
    if not entries:
        return []
    out: list[str] = []
    for kind, mn, mx, chance in entries:
        if random.randint(1, 100) > chance:
            continue
        count = random.randint(mn, mx)
        out.extend([kind] * count)
    return out
