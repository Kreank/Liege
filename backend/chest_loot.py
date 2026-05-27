"""Loot-Tables pro Chest-Typ (Welt / Dungeon / Boss / Bandit-Camp).

Skyrim-inspiriertes Container-System mit Diablo-artiger Rarity-Verteilung.
Anders als bei Mob-Drops (loot.py) ist hier Equipment die Haupt-Belohnung,
plus Coins und Consumables. Welche Equipment-Kinds + welche Quality kommt,
hängt vom Chest-Typ ab.

Roll-Schema pro Chest:
    1. Roll Coin-Loot       (jeder Chest hat etwas Münzen)
    2. Roll 1-N Equipment   (nach Chest-Tier)
    3. Roll 0-N Consumables (potions, scrolls, herbs)
    4. Roll Bonus-Resource  (geringe Chance)
    5. Roll Magic-Item      (sehr geringe Chance)

Quality der Equipment-Drops folgt einem gewichteten Random per Chest-Typ.
"""

import random

# ─── Equipment-Pool ───────────────────────────────────────────────────────
# Alle Equipment-Kinds die in Chests droppen können (kein scythe etc., weil
# Bauern-Werkzeug, kein chest-loot). Magic-Slots als jewelry: ring/amulet.
EQUIPMENT_WEAPONS = [
    "sword", "axe", "bow", "staff", "wand", "greatsword", "spear",
    "crossbow", "throwing_knife", "mace", "dagger",
]
EQUIPMENT_ARMOR = ["helmet", "chestplate", "gloves", "shield", "boots"]
EQUIPMENT_JEWELRY = ["ring", "amulet"]
EQUIPMENT_ALL = EQUIPMENT_WEAPONS + EQUIPMENT_ARMOR + EQUIPMENT_JEWELRY

MAGIC_ITEMS = ["scroll", "rune_stone", "spell_book"]

CONSUMABLE_ITEMS = [
    ("health_potion",  40),
    ("mana_potion",    30),
    ("greater_health_potion",  8),
    ("greater_mana_potion",    6),
    ("antidote_potion", 8),
    ("stamina_potion",  10),
    ("fire_resist_potion",  4),
    ("frost_resist_potion", 4),
    ("speed_potion",        4),
    ("strength_potion",     4),
    ("invisibility_potion", 2),
    ("poison_potion",       3),
    ("herb",   25),
    ("torch",  20),
]

# Crafting-Resources die in Chests landen können (kein wood/stone — die kommen
# vom Boden / Resource-Nodes, in Chests wären sie Verschwendung).
CHEST_RESOURCES = [
    ("iron_ore",     15), ("silver_ore",   10), ("gold_ore",      8),
    ("mythril_ore",  3),  ("crystal",      10), ("steel_ingot",   8),
    ("iron_ingot",   12), ("silver_ingot", 6),  ("gold_ingot",    4),
    ("mithril_ingot",2),  ("cloth",        10), ("leather",       12),
    ("bone",         8),
]

# Coin-Distribution je Chest-Typ (gewichtet welche Münze + Anzahl)
COIN_TABLES = {
    "world":   [("copper_coin", 70), ("silver_coin", 25), ("gold_coin", 5)],
    "bandit":  [("copper_coin", 60), ("silver_coin", 30), ("gold_coin", 10)],
    "dungeon": [("copper_coin", 40), ("silver_coin", 45), ("gold_coin", 15)],
    "boss":    [("silver_coin", 30), ("gold_coin", 70)],
}

# ─── Equipment-Quality-Verteilung pro Chest-Typ ────────────────────────────
# Welche Item-Quality bekommt das Equipment? Höhere Tiers = bessere Items.
EQUIPMENT_QUALITY_WEIGHTS = {
    "world":   [("rough", 25), ("normal", 60), ("fine", 12), ("masterwork", 3),  ("legendary", 0)],
    "bandit":  [("rough", 15), ("normal", 55), ("fine", 22), ("masterwork", 7),  ("legendary", 1)],
    "dungeon": [("rough", 5),  ("normal", 35), ("fine", 35), ("masterwork", 20), ("legendary", 5)],
    "boss":    [("rough", 0),  ("normal", 10), ("fine", 35), ("masterwork", 40), ("legendary", 15)],
}

# ─── Chest-Konfiguration ──────────────────────────────────────────────────
# Pro chest_type: wie viele Items kommen rein (gewichtete Anzahl)?
CHEST_CONFIG = {
    "world": {
        "coins":       (1, 3),     # min/max coin-stacks
        "equipment":   (0, 1),     # selten Equipment
        "consumables": (1, 2),
        "resources":   (1, 2),
        "magic_chance": 0.05,      # 5% Chance auf Magic-Item
        "weapon_pool": EQUIPMENT_WEAPONS,
        "armor_pool":  EQUIPMENT_ARMOR,
    },
    "bandit": {
        "coins":       (2, 4),     # Räuber haben viel Geld
        "equipment":   (1, 2),
        "consumables": (1, 2),
        "resources":   (0, 1),
        "magic_chance": 0.02,
        # Banditen führen einfache Waffen, keine Magie
        "weapon_pool": ["sword", "axe", "bow", "crossbow", "spear", "dagger", "mace"],
        "armor_pool":  ["helmet", "chestplate", "gloves", "boots"],
    },
    "dungeon": {
        "coins":       (2, 5),
        "equipment":   (1, 3),
        "consumables": (2, 4),
        "resources":   (1, 3),
        "magic_chance": 0.20,
        "weapon_pool": EQUIPMENT_WEAPONS,
        "armor_pool":  EQUIPMENT_ARMOR,
    },
    "boss": {
        "coins":       (3, 6),
        "equipment":   (2, 3),     # garantiert Equipment
        "consumables": (2, 4),
        "resources":   (2, 4),
        "magic_chance": 0.50,      # halbe Chance auf Magic
        "weapon_pool": EQUIPMENT_WEAPONS,
        "armor_pool":  EQUIPMENT_ARMOR,
    },
}


def _weighted_choice(table: list[tuple[str, int]],
                     rng: random.Random | None = None) -> str:
    """Pick aus [(item, weight), ...] gewichtet."""
    r = rng or random
    items, weights = zip(*table)
    return r.choices(items, weights=weights, k=1)[0]


def _coin_quantity(coin_kind: str, chest_type: str,
                   rng: random.Random | None = None) -> int:
    """Wie viele Münzen in einem Coin-Stack?"""
    r = rng or random
    base = {
        "copper_coin": (3, 15),
        "silver_coin": (1, 8),
        "gold_coin":   (1, 3),
    }.get(coin_kind, (1, 5))
    mult = {"world": 1.0, "bandit": 1.2, "dungeon": 1.5, "boss": 2.5}.get(chest_type, 1.0)
    lo, hi = base
    return max(1, int(round(r.randint(lo, hi) * mult)))


def roll_chest_loot(chest_type: str = "world",
                    rng: random.Random | None = None) -> list[dict]:
    """Rollt komplettes Loot eines Chests. Returns list of:
        {"kind": "sword", "quality": "fine", "quantity": 1}
    Quantity > 1 nur für stackable items (coins, resources, consumables).

    chest_type: "world" | "bandit" | "dungeon" | "boss"
    """
    r = rng or random
    cfg = CHEST_CONFIG.get(chest_type) or CHEST_CONFIG["world"]
    quality_table = EQUIPMENT_QUALITY_WEIGHTS.get(chest_type,
                                                   EQUIPMENT_QUALITY_WEIGHTS["world"])
    coin_table = COIN_TABLES.get(chest_type, COIN_TABLES["world"])
    out: list[dict] = []

    # 1) Coins (Münzen)
    coin_stacks = r.randint(*cfg["coins"])
    for _ in range(coin_stacks):
        coin = _weighted_choice(coin_table, r)
        out.append({
            "kind":     coin,
            "quality":  "normal",
            "quantity": _coin_quantity(coin, chest_type, r),
        })

    # 2) Equipment (Weapons + Armor + Jewelry)
    eq_count = r.randint(*cfg["equipment"])
    for _ in range(eq_count):
        # 50% weapon, 35% armor, 15% jewelry
        roll = r.random()
        if roll < 0.50:
            pool = cfg.get("weapon_pool", EQUIPMENT_WEAPONS)
        elif roll < 0.85:
            pool = cfg.get("armor_pool", EQUIPMENT_ARMOR)
        else:
            pool = EQUIPMENT_JEWELRY
        out.append({
            "kind":     r.choice(pool),
            "quality":  _weighted_choice(quality_table, r),
            "quantity": 1,
        })

    # 3) Consumables (potions, herbs, torch)
    cons_count = r.randint(*cfg["consumables"])
    for _ in range(cons_count):
        out.append({
            "kind":     _weighted_choice(CONSUMABLE_ITEMS, r),
            "quality":  "normal",
            "quantity": 1,
        })

    # 4) Crafting-Resources (ores, ingots, cloth, leather)
    res_count = r.randint(*cfg["resources"])
    for _ in range(res_count):
        out.append({
            "kind":     _weighted_choice(CHEST_RESOURCES, r),
            "quality":  "normal",
            "quantity": r.randint(1, 4),
        })

    # 5) Magic-Item (scroll/rune_stone/spell_book) — chance-based
    if r.random() < cfg["magic_chance"]:
        out.append({
            "kind":     r.choice(MAGIC_ITEMS),
            "quality":  "normal",
            "quantity": 1,
        })

    return out


def chest_type_for_location(location: str | None,
                            tier: int | None = None) -> str:
    """Helper: maps a location-string to chest_type.

    location:
      - "world"       → "world"  (default)
      - "bandit_camp" → "bandit"
      - "dungeon"     → "dungeon" (tier>=3) oder "boss" wenn tier == "boss"
      - "boss"        → "boss"
    """
    if location in ("boss", "boss_room"):
        return "boss"
    if location == "bandit_camp":
        return "bandit"
    if location and location.startswith("dungeon"):
        if tier is not None and tier == 0:
            return "boss"
        return "dungeon"
    return "world"
