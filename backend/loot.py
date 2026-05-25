"""Loot-Tabellen für besiegte Creatures.

Jede Creature hat eine gewichtete Liste möglicher Drops. Wenn besiegt, werden
1-2 zufällige Items aus der Tabelle gedroppt."""

import random

LOOT_TABLE = {
    "goblin": [
        ("bone", 50), ("cloth", 30), ("wood", 40), ("gold_ore", 15), ("herb", 10),
    ],
    "wolf": [
        ("bone", 60), ("leather", 50), ("raw_meat", 60), ("cloth", 20), ("herb", 5),
    ],
    "skeleton": [
        ("bone", 80), ("iron_ore", 20), ("silver_ore", 8), ("sword", 3),
    ],
    "spider": [
        ("cloth", 50), ("bone", 30), ("crystal", 8), ("herb", 15),
    ],
    "slime": [
        ("herb", 50), ("crystal", 30), ("mana_potion", 5), ("cloth", 10),
    ],
    # Welle 3 — neue Creatures
    "rat": [
        ("bone", 40), ("raw_meat", 50), ("cloth", 10),
    ],
    "bat": [
        ("bone", 50), ("leather", 30), ("raw_meat", 25),
    ],
    "zombie": [
        ("bone", 70), ("cloth", 40), ("raw_meat", 20), ("herb", 8),
    ],
    "bandit": [
        ("cloth", 50), ("gold_ore", 35), ("sword", 8), ("bow", 5),
        ("leather", 30), ("health_potion", 6),
    ],
    "boar": [
        ("raw_meat", 80), ("leather", 60), ("bone", 50),
    ],
    "bear": [
        ("raw_meat", 90), ("leather", 80), ("bone", 60), ("herb", 15),
        ("crystal", 5),
    ],
    # Bosse — fette Loot-Drops
    "ogre": [
        ("bone", 80), ("iron_ore", 50), ("steel_ingot", 30),
        ("sword", 15), ("axe", 15), ("chestplate", 8), ("gold_ore", 30),
    ],
    "necromancer": [
        ("bone", 70), ("scroll", 40), ("rune_stone", 20), ("spell_book", 10),
        ("crystal", 30), ("amulet", 15), ("mana_potion", 25),
    ],
    "dragon_whelp": [
        ("gold_ore", 60), ("mythril_ore", 25), ("steel_ingot", 30),
        ("sword", 10), ("staff", 10), ("crystal", 40), ("scroll", 15),
    ],
}


def roll_loot(kind: str) -> list[str]:
    """Returnt 1-2 Item-Kinds die dieses Creature droppt."""
    table = LOOT_TABLE.get(kind, [])
    if not table:
        return []
    num_drops = random.choices([1, 2], weights=[2, 1], k=1)[0]
    kinds = [k for k, _ in table]
    weights = [w for _, w in table]
    return random.choices(kinds, weights=weights, k=num_drops)
