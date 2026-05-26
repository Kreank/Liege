"""Harvest-Logik mit Multi-Hit-Durability.

Jede natürliche Struktur hat eine `durability` (Anzahl Schläge bis zerstört).
Pro Schlag wird ein kleinerer `yield` ausgewürfelt (1-2 Items typisch).

Biome-aware yields: rare ores sind an Biome / Mountain-Nähe gekoppelt.
- Mountain-adjacent rocks → iron_ore + mythril chance
- Desert rocks → bone, gold_ore
- Snow rocks → crystal, silver_ore
- Plain grass rocks → nur stone + tiny iron chance"""

import random

# Tile-IDs (synchron mit world.py)
WATER, SAND, GRASS, FOREST, MOUNTAIN = 0, 1, 2, 3, 4
DESERT, JUNGLE, LAVA, SNOW, SWAMP = 5, 6, 7, 8, 9

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
    # — Farming-Drop 2026-05-26 —
    "strawberry_bush": 1, "blueberry_bush": 1, "blackberry_bush": 1, "raspberry_bush": 1,
    "apple_tree": 5, "pear_tree": 5, "plum_tree": 5, "cherry_tree": 5,
    "carrot_plant": 1, "potato_plant": 1, "cucumber_plant": 1, "tomato_plant": 1,
    "onion_plant": 1, "cabbage_plant": 1, "pumpkin_plant": 1, "corn_plant": 1,
    "wheat_seedling": 1, "wheat_grown": 1,
}

# Yield pro Schlag: [(item_kind, min, max, chance_in_pct), ...]
YIELD_PER_HIT = {
    "tree_oak":      [("wood", 1, 2, 100), ("apple", 0, 1, 35)],
    "tree_pine":     [("wood", 1, 2, 100)],
    "tree_dead":     [("wood", 1, 1, 100)],
    "tree_stump":    [("wood", 1, 1, 100)],
    "fallen_log":    [("wood", 1, 2, 100)],
    # Erze hier NICHT als Default — kommen via BONUS_YIELDS_BY_BIOME /
    # MOUNTAIN_ADJACENT_BONUS, sodass Mithril & Co. nur in passenden Gebieten
    # auftauchen und nicht irgendwo auf der Wiese.
    "rock_small":    [("stone", 1, 2, 100)],
    "rock_large":    [("stone", 1, 2, 100)],
    "rock_mossy":    [("stone", 1, 1, 100), ("herb", 0, 1, 20)],
    # Pflanzen droppen jetzt Pflanzenfaser statt direkt Stoff —
    # Stoff muss aus 3 Fasern an der Hand gewebt werden (recipe weave_cloth)
    "bush":          [("plant_fiber", 0, 1, 40), ("herb", 0, 1, 50), ("berries", 0, 1, 45)],
    "tall_grass":    [("plant_fiber", 1, 2, 80), ("wheat", 0, 1, 15)],
    "flowers":       [("plant_fiber", 0, 1, 30), ("herb", 1, 1, 100)],
    "mushrooms":     [("herb", 1, 1, 70), ("mushroom_food", 1, 2, 80)],
    "reeds":         [("plant_fiber", 1, 2, 100)],
    "lily_pads":     [("plant_fiber", 0, 1, 50), ("herb", 0, 1, 30)],
    "broken_cart":   [("wood", 1, 2, 100), ("iron_ore", 0, 1, 12)],
    "barrel":        [("wood", 1, 1, 100)],
    "crate":         [("wood", 1, 1, 100)],
    "sack":          [("plant_fiber", 1, 2, 80), ("cloth", 0, 1, 40)],
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
    "cactus":         [("herb", 1, 2, 100), ("plant_fiber", 0, 1, 40)],
    "desert_skull":   [("bone", 1, 2, 100)],
    "dry_bush":       [("plant_fiber", 1, 1, 70), ("wood", 0, 1, 30)],
    "jungle_flower":  [("herb", 1, 2, 100), ("plant_fiber", 0, 1, 30)],
    "jungle_vines":   [("plant_fiber", 1, 2, 100), ("herb", 0, 1, 30)],
    "palm_tree":      [("wood", 2, 3, 100), ("apple", 0, 1, 20)],
    "lava_rock":      [("stone", 1, 2, 100), ("crystal", 0, 1, 25)],
    "frozen_bush":    [("herb", 0, 1, 50), ("plant_fiber", 0, 1, 30)],
    "ice_crystal":    [("crystal", 1, 2, 100)],
    "snow_rock":      [("stone", 1, 2, 100)],
    "swamp_bubbles":  [("herb", 0, 1, 60)],
    "swamp_log":      [("wood", 1, 2, 100), ("mushroom_food", 0, 1, 30)],
    # — Farming-Drop 2026-05-26 — wilde Sträucher/Pflanzen/Obstbäume —
    "strawberry_bush":[("strawberry", 1, 3, 100), ("plant_fiber", 0, 1, 30), ("strawberry_seeds", 0, 1, 40)],
    "blueberry_bush": [("blueberry", 1, 3, 100), ("plant_fiber", 0, 1, 30), ("blueberry_seeds", 0, 1, 40)],
    "blackberry_bush":[("blackberry",1, 3, 100), ("plant_fiber", 0, 1, 30), ("blackberry_seeds",0, 1, 40)],
    "raspberry_bush": [("raspberry", 1, 3, 100), ("plant_fiber", 0, 1, 30), ("raspberry_seeds", 0, 1, 40)],
    "apple_tree":     [("apple", 1, 3, 100), ("wood", 1, 2, 100), ("apple_seeds", 0, 1, 30)],
    "pear_tree":      [("pear",  1, 3, 100), ("wood", 1, 2, 100), ("pear_seeds",  0, 1, 30)],
    "plum_tree":      [("plum",  1, 3, 100), ("wood", 1, 2, 100), ("plum_seeds",  0, 1, 30)],
    "cherry_tree":    [("cherry",1, 3, 100), ("wood", 1, 2, 100), ("cherry_seeds",0, 1, 30)],
    "carrot_plant":   [("carrot",   1, 2, 100), ("carrot_seeds",   0, 1, 35)],
    "potato_plant":   [("potato",   1, 2, 100), ("potato_seeds",   0, 1, 35)],
    "cucumber_plant": [("cucumber", 1, 2, 100), ("cucumber_seeds", 0, 1, 35)],
    "tomato_plant":   [("tomato",   1, 2, 100), ("tomato_seeds",   0, 1, 35)],
    "onion_plant":    [("onion",    1, 2, 100), ("onion_seeds",    0, 1, 35)],
    "cabbage_plant":  [("cabbage",  1, 1, 100), ("cabbage_seeds",  0, 1, 35)],
    "pumpkin_plant":  [("pumpkin",  1, 1, 100), ("pumpkin_seeds",  0, 1, 35)],
    "corn_plant":     [("corn",     1, 2, 100), ("corn_seeds",     0, 1, 35)],
    "wheat_seedling": [("plant_fiber", 0, 1, 80)],
    "wheat_grown":    [("wheat", 1, 2, 100), ("plant_fiber", 0, 1, 40)],
}

HARVESTABLE_TYPES = set(YIELD_PER_HIT.keys())


# Bonus-Yields die NUR in bestimmten Biomes greifen (additiv zum default).
# Pattern: (biome_id, structure_type) → [(kind, min, max, chance_pct), …]
BONUS_YIELDS_BY_BIOME = {
    # Wüste: Knochen + selten Gold
    (DESERT, "rock_small"): [("bone", 0, 1, 15)],
    (DESERT, "rock_large"): [("bone", 0, 1, 30), ("gold_ore", 0, 1, 4)],
    (DESERT, "statue_broken"): [("bone", 0, 1, 25), ("gold_ore", 0, 1, 8)],
    (DESERT, "gravestone"): [("bone", 0, 1, 40)],
    (DESERT, "bones_scatter"): [("bone", 1, 2, 60)],
    # Schnee: Kristall + Silber
    (SNOW, "rock_small"): [("crystal", 0, 1, 8)],
    (SNOW, "rock_large"): [("crystal", 0, 1, 15), ("silver_ore", 0, 1, 8)],
    (SNOW, "ice_crystal"): [("crystal", 1, 2, 50)],
    (SNOW, "snow_rock"): [("crystal", 0, 1, 20), ("silver_ore", 0, 1, 5)],
    # Wald-Moos: extra Kräuter / Pilze
    (FOREST, "rock_mossy"): [("herb", 0, 1, 25), ("mushroom_food", 0, 1, 15)],
    (FOREST, "bush"): [("berries", 0, 1, 35)],
    # Jungle: extra Kräuter / Vines
    (JUNGLE, "rock_mossy"): [("herb", 0, 1, 30)],
    (JUNGLE, "jungle_flower"): [("herb", 1, 2, 80)],
    # Sumpf: Pilze + Knochen
    (SWAMP, "swamp_log"): [("mushroom_food", 0, 1, 25)],
    (SWAMP, "bones_scatter"): [("bone", 1, 2, 50)],
}

# Mountain-adjacent (= mindestens 1 Nachbar-Tile ist MOUNTAIN) — gibt Zugang
# zu Eisen und sehr selten Mithril. Das macht "in den Bergen Erze suchen"
# zum echten Spielmechanik-Reward statt "irgendwo auf der Wiese random ore".
MOUNTAIN_ADJACENT_BONUS = {
    "rock_small": [("iron_ore", 0, 1, 18)],
    "rock_large": [("iron_ore", 0, 1, 30), ("mythril_ore", 0, 1, 4)],
    "rock_mossy": [("iron_ore", 0, 1, 12)],
    "snow_rock":  [("iron_ore", 0, 1, 25), ("silver_ore", 0, 1, 10)],
    "lava_rock":  [("iron_ore", 0, 1, 35), ("mythril_ore", 0, 1, 8),
                   ("crystal", 0, 1, 20)],
}


def is_harvestable(structure_type: str) -> bool:
    return structure_type in HARVESTABLE_TYPES


def initial_durability(structure_type: str) -> int:
    return DURABILITY.get(structure_type, 1)


def roll_hit_yield(structure_type: str, biome: int | None = None,
                   mountain_adjacent: bool = False) -> list[str]:
    """Returnt die Items eines einzelnen Schlags. Kann leer sein.
    Optional biome (tile-id) + mountain_adjacent flag fügen biome-spezifische
    Bonus-Drops hinzu."""
    entries = list(YIELD_PER_HIT.get(structure_type, []))
    if biome is not None:
        entries.extend(BONUS_YIELDS_BY_BIOME.get((biome, structure_type), []))
    if mountain_adjacent:
        entries.extend(MOUNTAIN_ADJACENT_BONUS.get(structure_type, []))
    if not entries:
        return []
    out: list[str] = []
    for kind, mn, mx, chance in entries:
        if random.randint(1, 100) > chance:
            continue
        count = random.randint(mn, mx)
        out.extend([kind] * count)
    return out
