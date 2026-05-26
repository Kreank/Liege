"""Loot-Tabellen für besiegte Creatures.

Drop-Count gewichtet:
  10% nichts, 45% 1 Drop, 40% 2 Drops, 5% 3 Drops.

Pro Drop wird gewichtet aus der jeweiligen LOOT_TABLE gezogen.
Duplikate werden vermieden (jeder kind kommt max einmal vor in einem
Kill, außer der Pool ist zu klein).

Bandits haben ein Special-Schema: zusätzlich zu den 0-3 Drops bekommen
sie garantiert eine Münze (gewichtet copper/silver/gold) und können
ihr equipped Item droppen.
"""

import random

# Drop-Count gewichtet (0/1/2/3)
DROP_COUNT_WEIGHTS = [10, 45, 40, 5]

LOOT_TABLE = {
    # — Tiere —
    "boar": [
        ("raw_meat", 60), ("leather", 50), ("bone", 40),
    ],
    "wolf": [
        ("raw_meat", 60), ("leather", 55), ("bone", 50), ("herb", 5),
    ],
    "bear": [
        ("raw_meat", 70), ("leather", 70), ("bone", 60), ("herb", 15),
        ("crystal", 5),
    ],
    "rat": [
        ("raw_meat", 50), ("bone", 40), ("cloth", 10),
    ],
    "bat": [
        ("bone", 50), ("leather", 30), ("raw_meat", 25),
    ],
    # — Monster —
    "spider": [
        ("cloth", 50), ("bone", 30), ("crystal", 8), ("herb", 15),
    ],
    "slime": [
        ("herb", 50), ("crystal", 30), ("mana_potion", 5), ("cloth", 10),
    ],
    "goblin": [
        ("bone", 50), ("cloth", 30), ("wood", 40), ("copper_coin", 25),
        ("herb", 10),
    ],
    "skeleton": [
        ("bone", 80), ("iron_ore", 20), ("silver_ore", 8), ("copper_coin", 15),
    ],
    "zombie": [
        ("bone", 70), ("cloth", 40), ("raw_meat", 20), ("herb", 8),
    ],
    # — Bosse —
    "ogre": [
        ("bone", 80), ("iron_ore", 50), ("steel_ingot", 30),
        ("gold_coin", 35), ("silver_coin", 30), ("chestplate", 8),
    ],
    "necromancer": [
        ("bone", 70), ("scroll", 40), ("rune_stone", 20), ("spell_book", 10),
        ("crystal", 30), ("amulet", 15), ("mana_potion", 25), ("gold_coin", 25),
    ],
    "dragon_whelp": [
        ("gold_coin", 60), ("mythril_ore", 25), ("steel_ingot", 30),
        ("crystal", 40), ("scroll", 15), ("gold_coin", 50),
    ],
    # Bandit hat zusätzlich Special-Loot via roll_special_loot
    "bandit": [
        ("cloth", 50), ("leather", 30), ("health_potion", 8), ("herb", 10),
    ],
}

# Münz-Gewichte für Banditen — Bronze sehr häufig, Gold selten
BANDIT_COIN_WEIGHTS = [
    ("copper_coin", 60),
    ("silver_coin", 30),
    ("gold_coin",   10),
]

# Mögliche equipped-Items die ein Bandit zusätzlich droppen kann
BANDIT_EQUIPMENT = [
    ("sword", 30), ("dagger", 25), ("bow", 15), ("axe", 10),
    ("leather", 0),  # platzhalter — equipment-Slots können auch enthalten sein
    ("helmet", 8), ("boots", 8), ("health_potion", 15),
]


def _pick_weighted(items: list[tuple[str, int]]) -> str | None:
    """Pickt einen kind aus [(kind, weight), …]. None wenn leer/keine Treffer."""
    if not items:
        return None
    kinds = [k for k, _ in items]
    weights = [w for _, w in items]
    if sum(weights) <= 0:
        return None
    return random.choices(kinds, weights=weights, k=1)[0]


def _roll_drop_count() -> int:
    return random.choices([0, 1, 2, 3], weights=DROP_COUNT_WEIGHTS, k=1)[0]


def roll_loot(kind: str) -> list[str]:
    """Returnt 0-3 Item-Kinds die dieses Creature droppt (ohne Duplikate
    aus der Standard-Tabelle)."""
    table = LOOT_TABLE.get(kind, [])
    drops: list[str] = []
    n = _roll_drop_count()
    if n > 0 and table:
        # Ziehe n unterschiedliche kinds gewichtet
        pool = list(table)
        for _ in range(min(n, len(pool))):
            picked = _pick_weighted(pool)
            if picked is None:
                break
            drops.append(picked)
            pool = [(k, w) for k, w in pool if k != picked]

    # Bandit-Special: garantierte Münze + ggf. equipped Item
    if kind == "bandit":
        coin = _pick_weighted(BANDIT_COIN_WEIGHTS)
        if coin:
            drops.append(coin)
        # 40% Chance dass er zusätzlich was Equipped-mäßiges droppt
        if random.random() < 0.40:
            extra = _pick_weighted([(k, w) for k, w in BANDIT_EQUIPMENT if w > 0])
            if extra:
                drops.append(extra)

    return drops
