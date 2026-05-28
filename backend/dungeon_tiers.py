"""Dungeon-Tier-Konfiguration — Welle 32.

5 Tiers von Klein bis Raid40. Pro Tier:
  - Lifetime-Range (Sekunden): wie lange existiert der Dungeon nach Spawn
  - Floor-Count-Range: pro Floor eigene Map
  - Map-Size: Tile-Kantenlänge pro Floor
  - Mob-Density: wie viele Mobs pro Floor
  - Mob-Tier-Multiplikator: härtere Mobs in höheren Tiers
  - Boss-Count: Wieviele Boss-Mobs (auf letzter Floor garantiert)
  - Loot-Boost: Wieviel besseren Loot pro Floor
  - Theme-Pool: welche dungeon_themes.THEMES sind passend
"""
import random
from typing import Optional

# Tier-IDs
TIER_SMALL    = 1   # 2-4h
TIER_MEDIUM   = 2   # 16-24h
TIER_LARGE    = 3   # 24-48h
TIER_RAID20   = 4   # 3-5 Tage
TIER_RAID40   = 5   # 4-7 Tage


# Seconds per tier — (min, max) range
LIFETIME_S = {
    TIER_SMALL:  (2 * 3600,   4 * 3600),       # 2-4 h
    TIER_MEDIUM: (16 * 3600,  24 * 3600),      # 16-24 h
    TIER_LARGE:  (24 * 3600,  48 * 3600),      # 24-48 h
    TIER_RAID20: (3 * 86400,  5 * 86400),      # 3-5 d
    TIER_RAID40: (4 * 86400,  7 * 86400),      # 4-7 d
}

FLOOR_COUNT = {
    TIER_SMALL:  (1, 2),
    TIER_MEDIUM: (3, 4),
    TIER_LARGE:  (5, 7),
    TIER_RAID20: (8, 10),
    TIER_RAID40: (12, 15),
}

# Floor-Map-Edge-Size pro Tier — höhere Tiers haben größere Maps
FLOOR_SIZE = {
    TIER_SMALL:  24,
    TIER_MEDIUM: 32,
    TIER_LARGE:  40,
    TIER_RAID20: 48,
    TIER_RAID40: 56,
}

# Mob-Anzahl pro Floor — skaliert mit Tier
MOBS_PER_FLOOR = {
    TIER_SMALL:  (4, 7),
    TIER_MEDIUM: (8, 12),
    TIER_LARGE:  (12, 18),
    TIER_RAID20: (16, 24),
    TIER_RAID40: (22, 32),
}

# Boss-Anzahl auf letzter Floor (min 1, sonst nicht garantiert)
BOSS_COUNT = {
    TIER_SMALL:  1,
    TIER_MEDIUM: 1,
    TIER_LARGE:  1,
    TIER_RAID20: 2,
    TIER_RAID40: 3,
}

# Mob-HP-Multiplikator — Tier 1 = 1x, Tier 5 = 2.5x
MOB_HP_MULT = {
    TIER_SMALL:  1.0,
    TIER_MEDIUM: 1.3,
    TIER_LARGE:  1.6,
    TIER_RAID20: 2.0,
    TIER_RAID40: 2.5,
}

# Tier-Bezeichner für UI
TIER_LABEL = {
    TIER_SMALL:  "Kleines Verlies",
    TIER_MEDIUM: "Mittleres Verlies",
    TIER_LARGE:  "Großes Verlies",
    TIER_RAID20: "Raid (20er)",
    TIER_RAID40: "Großraid (40er)",
}

# Welche Themes sind welchem Tier zugeordnet
TIER_THEMES = {
    TIER_SMALL:  ["mine", "cave"],
    TIER_MEDIUM: ["crypt", "ruin", "cave"],
    TIER_LARGE:  ["crypt", "temple", "ruin"],
    TIER_RAID20: ["temple", "crypt"],
    TIER_RAID40: ["temple"],
}

# Quest-Reward-Items die einen Dungeon-Eingang spawnen können
# (verlinkt mit items.py: dungeon_map_* werden in Phase 3 als consumables hinzugefügt)
TIER_KEY_ITEM = {
    TIER_LARGE:  "dungeon_map",            # T3 via Quest-Reward
    TIER_RAID20: "rift_lore",              # T4 Raid20 via Boss-Loot oder Event
    TIER_RAID40: "kings_seal",             # T5 Raid40 selten
}


def random_lifetime_seconds(tier: int) -> int:
    """Zufällige Lebenszeit innerhalb der Tier-Range."""
    lo, hi = LIFETIME_S.get(tier, (3600, 7200))
    return random.randint(lo, hi)


def random_floor_count(tier: int) -> int:
    lo, hi = FLOOR_COUNT.get(tier, (1, 1))
    return random.randint(lo, hi)


def random_mob_count(tier: int) -> int:
    lo, hi = MOBS_PER_FLOOR.get(tier, (3, 5))
    return random.randint(lo, hi)


def pick_theme(tier: int, seed: Optional[int] = None) -> str:
    """Wählt ein Theme aus dem Tier-Pool. seed für Determinismus."""
    pool = TIER_THEMES.get(tier, ["cave"])
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(pool)


def tier_for_key_item(item_kind: str) -> Optional[int]:
    """Welcher Tier-Dungeon wird durch ein Key-Item geöffnet?"""
    for tier, key in TIER_KEY_ITEM.items():
        if key == item_kind:
            return tier
    return None
