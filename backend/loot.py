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

    # — Welle 13 — Tiere —
    "stag":      [("raw_meat", 70), ("leather", 60), ("bone", 40)],
    "lynx":      [("raw_meat", 55), ("leather", 60), ("bone", 35)],
    "cougar":    [("raw_meat", 65), ("leather", 65), ("bone", 40)],
    "wolverine": [("raw_meat", 60), ("leather", 65), ("bone", 45)],
    "dire_wolf": [("raw_meat", 75), ("leather", 70), ("bone", 55)],
    "wolf_alpha":[("raw_meat", 80), ("leather", 75), ("bone", 60), ("silver_coin", 15)],
    "cave_bear": [("raw_meat", 85), ("leather", 75), ("bone", 70), ("herb", 10)],
    "polar_bear":[("raw_meat", 80), ("leather", 80), ("bone", 65), ("crystal", 8)],
    "crocodile": [("raw_meat", 70), ("leather", 80), ("bone", 60)],
    "cobra":     [("raw_meat", 30), ("leather", 50), ("herb", 25), ("mana_potion", 5)],
    # — Insekten / Kleinkram —
    "slimelet":  [("herb", 30), ("crystal", 12), ("mana_potion", 3)],
    "fae_mite":  [("cloth", 25), ("herb", 30), ("crystal", 10)],
    "gloom_moth":[("cloth", 30), ("herb", 25)],
    "ember_newt":[("bone", 20), ("crystal", 15), ("herb", 20)],
    "ember_rat": [("bone", 35), ("raw_meat", 40), ("cloth", 8)],
    "shadow_bat":[("bone", 45), ("leather", 25), ("raw_meat", 20)],
    "thorn_scarab":[("bone", 30), ("cloth", 20), ("crystal", 12)],
    "crystal_beetle":[("crystal", 50), ("bone", 20), ("silver_ore", 10)],
    "crystal_tick":[("crystal", 35), ("bone", 15)],
    # — Geister/Fae —
    "frost_sprite":[("crystal", 30), ("herb", 25), ("mana_potion", 8)],
    "fire_imp":  [("crystal", 20), ("iron_ore", 25), ("scroll", 8)],
    "mushroom_imp":[("herb", 50), ("mushroom_food", 35), ("cloth", 20)],
    "thornling": [("wood", 45), ("herb", 30), ("cloth", 15)],
    # — Pflanzlich/Treant —
    "treant":    [("wood", 90), ("herb", 35), ("apple", 30), ("crystal", 10)],
    # — Stein/Kristall —
    "stone_golem":[("stone", 90), ("iron_ore", 40), ("crystal", 20), ("silver_ore", 15)],
    "crystal_golem":[("crystal", 95), ("silver_ore", 30), ("gold_ore", 15), ("mythril_ore", 10)],
    "gargoyle":  [("stone", 60), ("crystal", 25), ("bone", 30)],
    "bone_crawler":[("bone", 90), ("cloth", 20), ("herb", 10)],
    # — Spinnen-Variante —
    "giant_spider":[("cloth", 80), ("bone", 50), ("crystal", 15), ("herb", 20)],
    # — Bosse — fette Drops mit Münzen + Equipment-Chance —
    "minotaur":  [("raw_meat", 60), ("leather", 60), ("bone", 60),
                  ("gold_coin", 25), ("silver_coin", 35), ("axe", 8)],
    "harpy":     [("leather", 50), ("bone", 40), ("silver_coin", 25),
                  ("cloth", 35), ("crystal", 15)],
    "basilisk":  [("leather", 80), ("bone", 60), ("crystal", 40),
                  ("mythril_ore", 15), ("gold_coin", 30), ("scroll", 15)],
    "chimera":   [("raw_meat", 70), ("leather", 70), ("bone", 60),
                  ("gold_coin", 40), ("crystal", 30), ("sword", 10)],
    "griffin":   [("leather", 75), ("bone", 50), ("gold_coin", 35),
                  ("crystal", 25), ("mythril_ore", 12)],
    "hydra":     [("raw_meat", 80), ("bone", 70), ("leather", 60),
                  ("gold_coin", 45), ("mythril_ore", 20), ("crystal", 40), ("scroll", 20)],
    "manticore": [("raw_meat", 65), ("leather", 65), ("bone", 55),
                  ("gold_coin", 35), ("crystal", 25), ("spear", 10)],

    # — Welle 14 — professional monster asset-drop (2026-05-26b) —
    # Vermin / Larva — wenig Loot, einfache Materialien
    "razorback_vermin":   [("raw_meat", 30), ("leather", 25), ("bone", 30)],
    "spined_abyss_larva": [("bone", 25), ("cloth", 20), ("herb", 20), ("crystal", 8)],
    # Mittlere Tiere
    "reed_walker":        [("raw_meat", 45), ("leather", 50), ("bone", 35), ("herb", 15)],
    "redland_scavenger":  [("raw_meat", 50), ("leather", 55), ("bone", 40), ("copper_coin", 15)],
    "mossback_warden":    [("wood", 50), ("herb", 40), ("leather", 30), ("crystal", 12)],
    # Undead / Magic
    "grave_wraith":       [("bone", 70), ("cloth", 40), ("scroll", 15), ("mana_potion", 12), ("silver_coin", 12)],
    "serpent_oracle":     [("leather", 50), ("scroll", 25), ("rune_stone", 15), ("crystal", 25),
                           ("mana_potion", 20), ("silver_coin", 18)],
    "urtikus_eye_fiend":  [("crystal", 35), ("herb", 25), ("scroll", 18), ("mana_potion", 15), ("bone", 30)],
    # Heavy beasts
    "mantis_chimera":     [("raw_meat", 60), ("leather", 65), ("bone", 50), ("dagger", 6)],
    "iron_spider":        [("iron_ore", 60), ("crystal", 25), ("bone", 20), ("steel_ingot", 15)],
    "dendroid_guardian":  [("wood", 95), ("herb", 40), ("apple", 25), ("crystal", 15), ("silver_coin", 12)],
    "blood_antler_drake": [("raw_meat", 70), ("leather", 75), ("bone", 65), ("gold_coin", 25), ("crystal", 20)],
    # Bosse — fette Drops mit Münzen + selten Equipment
    "kaiju_thornback":      [("raw_meat", 80), ("leather", 80), ("bone", 70),
                             ("gold_coin", 35), ("crystal", 25), ("mythril_ore", 10)],
    "void_eye_brute":       [("bone", 60), ("crystal", 50), ("scroll", 20), ("rune_stone", 15),
                             ("gold_coin", 35), ("mana_potion", 25), ("amulet", 6)],
    "frost_rune_boar_prime":[("raw_meat", 85), ("leather", 80), ("bone", 70),
                             ("crystal", 40), ("gold_coin", 40), ("rune_stone", 12),
                             ("mythril_ore", 15)],
    "magma_shell_devourer": [("stone", 70), ("crystal", 50), ("iron_ore", 50),
                             ("gold_ore", 25), ("mythril_ore", 20), ("gold_coin", 45),
                             ("steel_ingot", 30)],
    "rockshell_colossus":   [("stone", 95), ("crystal", 60), ("iron_ore", 55),
                             ("silver_ore", 30), ("gold_ore", 20), ("mythril_ore", 25),
                             ("gold_coin", 50), ("chestplate", 8)],
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


def _roll_drop_count(tier: int = 2) -> int:
    """Tier-skaliertes Drop-Count.
    Tier 1 (trash): überwiegend 0-1 Drops.
    Tier 2 (normal): default 0-3.
    Tier 3 (elite): 1-3, häufiger 2-3.
    Tier 4 (boss): garantiert 2-4 Drops."""
    if tier <= 1:
        return random.choices([0, 1, 2], weights=[25, 60, 15], k=1)[0]
    if tier == 2:
        return random.choices([0, 1, 2, 3], weights=DROP_COUNT_WEIGHTS, k=1)[0]
    if tier == 3:
        return random.choices([1, 2, 3], weights=[30, 50, 20], k=1)[0]
    return random.choices([2, 3, 4], weights=[40, 45, 15], k=1)[0]


def roll_loot(kind: str) -> list[str]:
    """Returnt 0-4 Item-Kinds die dieses Creature droppt (ohne Duplikate
    aus der Standard-Tabelle). Anzahl skaliert mit Monster-Tier."""
    table = LOOT_TABLE.get(kind, [])
    # Tier aus den Combat-Stats holen (Default 2 wenn unbekannt)
    try:
        import combat as _c
        tier = _c.creature_stats(kind).get("tier", 2)
    except Exception:
        tier = 2
    drops: list[str] = []
    n = _roll_drop_count(tier)
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
