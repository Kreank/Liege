"""Affix-System für magische/unique Items (Diablo/PoE-inspiriert).

Items haben Prefix- und Suffix-Affixes mit gewichteten Spawn-Chancen und
Tiers. Quality bestimmt wie viele Affixes ein Item bekommt:

    rough/normal   → 0 Prefix + 0 Suffix
    fine           → 0-1 Prefix + 0-1 Suffix
    masterwork     → 1-2 Prefix + 1-2 Suffix
    legendary      → 2-3 Prefix + 1-2 Suffix + Unique-Name (LLM)

LLM darf **niemals** Stats setzen. Sie liefert ausschließlich `name` und
`flavor`-Text. Stats sind 100% server-deterministisch.
"""
import json
import logging
import random

import db

log = logging.getLogger("liege.affixes")


SCHEMA = """
-- Items werden um JSONB-Spalte für Affixes erweitert
ALTER TABLE items ADD COLUMN IF NOT EXISTS affixes JSONB NULL;
ALTER TABLE items ADD COLUMN IF NOT EXISTS unique_name TEXT NULL;
ALTER TABLE items ADD COLUMN IF NOT EXISTS flavor TEXT NULL;
"""


# Affix-Pool. Jeder Affix:
#   id, kind ("prefix" oder "suffix"), tier (1-3), weight (Spawn-Wahrscheinlichkeit)
#   stats: dict mit (min, max) Werten — wird bei Roll konkretisiert
#   tags: für welche Item-Tags er gilt (e.g. ["weapon", "melee"])
#   name_part: was in den Item-Namen einfließt
AFFIXES_PREFIX = {
    # — TIER 1 (häufig, schwach) ————————————————————————————————————
    "sharp":   {"tier": 1, "weight": 60, "tags": ["weapon"],
                "stats": {"damage_pct": (5, 12)}, "name_part": "Scharfe"},
    "swift":   {"tier": 1, "weight": 50, "tags": ["weapon"],
                "stats": {"speed_pct": (5, 10)}, "name_part": "Schnelle"},
    "sturdy":  {"tier": 1, "weight": 60, "tags": ["armor"],
                "stats": {"defense_flat": (2, 5)}, "name_part": "Robuste"},
    "warm":    {"tier": 1, "weight": 40, "tags": ["armor"],
                "stats": {"resist_cold": (5, 10)}, "name_part": "Warme"},
    "lucky":   {"tier": 1, "weight": 30, "tags": ["weapon", "armor", "jewelry"],
                "stats": {"crit_chance_pct": (2, 5)}, "name_part": "Glückliche"},

    # — TIER 2 (selten, mittel) —————————————————————————————————————
    "vicious":  {"tier": 2, "weight": 25, "tags": ["weapon"],
                 "stats": {"damage_pct": (12, 25)}, "name_part": "Bösartige"},
    "blazing":  {"tier": 2, "weight": 18, "tags": ["weapon", "magic"],
                 "stats": {"fire_damage": (5, 12), "burn_chance_pct": (10, 25)},
                 "name_part": "Flammende"},
    "frost":    {"tier": 2, "weight": 18, "tags": ["weapon", "magic"],
                 "stats": {"ice_damage": (5, 10), "slow_chance_pct": (10, 20)},
                 "name_part": "Eisige"},
    "spectral": {"tier": 2, "weight": 15, "tags": ["weapon", "magic"],
                 "stats": {"necrotic_damage": (6, 12), "lifesteal_pct": (3, 8)},
                 "name_part": "Geisterhafte"},
    "fortified":{"tier": 2, "weight": 22, "tags": ["armor"],
                 "stats": {"defense_flat": (6, 12), "hp_flat": (10, 20)},
                 "name_part": "Befestigte"},
    "swift_runner":{"tier": 2, "weight": 18, "tags": ["armor"],
                    "stats": {"speed_pct": (10, 18)}, "name_part": "Eilende"},
    "channeler":{"tier": 2, "weight": 20, "tags": ["magic", "jewelry"],
                 "stats": {"mana_flat": (15, 30), "mana_regen_pct": (5, 15)},
                 "name_part": "Kanalisierende"},

    # — TIER 3 (sehr selten, stark) —————————————————————————————————
    "godslayer":{"tier": 3, "weight": 4, "tags": ["weapon"],
                 "stats": {"damage_pct": (25, 50), "armor_pen_pct": (15, 30)},
                 "name_part": "Götterschlächter-"},
    "soulbound":{"tier": 3, "weight": 3, "tags": ["weapon", "armor"],
                 "stats": {"hp_flat": (25, 50), "lifesteal_pct": (8, 15)},
                 "name_part": "Seelenverbundene"},
    "thunder":  {"tier": 3, "weight": 5, "tags": ["weapon", "magic"],
                 "stats": {"lightning_damage": (15, 30), "crit_chance_pct": (8, 15)},
                 "name_part": "Donnernde"},
    "ancient":  {"tier": 3, "weight": 4, "tags": ["weapon", "armor"],
                 "stats": {"all_stats_pct": (10, 20)}, "name_part": "Uralte"},
}

AFFIXES_SUFFIX = {
    # — TIER 1 ——————————————————————————————————————————————————————————
    "of_health":  {"tier": 1, "weight": 60, "tags": ["any"],
                   "stats": {"hp_flat": (5, 15)}, "name_part": "der Gesundheit"},
    "of_mana":    {"tier": 1, "weight": 50, "tags": ["any"],
                   "stats": {"mana_flat": (8, 15)}, "name_part": "des Mana"},
    "of_speed":   {"tier": 1, "weight": 45, "tags": ["armor", "weapon"],
                   "stats": {"speed_pct": (5, 10)}, "name_part": "der Eile"},
    "of_strength":{"tier": 1, "weight": 40, "tags": ["weapon", "armor"],
                   "stats": {"damage_pct": (4, 10)}, "name_part": "der Stärke"},

    # — TIER 2 ——————————————————————————————————————————————————————————
    "of_the_bear":  {"tier": 2, "weight": 22, "tags": ["weapon", "armor"],
                     "stats": {"hp_flat": (20, 35), "damage_pct": (5, 12)},
                     "name_part": "des Bären"},
    "of_the_wolf":  {"tier": 2, "weight": 22, "tags": ["weapon"],
                     "stats": {"speed_pct": (10, 18), "crit_chance_pct": (3, 8)},
                     "name_part": "des Wolfs"},
    "of_the_owl":   {"tier": 2, "weight": 20, "tags": ["magic", "jewelry"],
                     "stats": {"mana_flat": (25, 45), "spell_damage_pct": (8, 18)},
                     "name_part": "der Eule"},
    "of_protection":{"tier": 2, "weight": 25, "tags": ["armor"],
                     "stats": {"defense_flat": (8, 15), "resist_all_pct": (5, 12)},
                     "name_part": "des Schutzes"},
    "of_vampire":   {"tier": 2, "weight": 15, "tags": ["weapon"],
                     "stats": {"lifesteal_pct": (6, 12)}, "name_part": "des Vampirs"},

    # — TIER 3 ——————————————————————————————————————————————————————————
    "of_titans":    {"tier": 3, "weight": 4, "tags": ["weapon", "armor"],
                     "stats": {"hp_flat": (50, 100), "damage_pct": (15, 25)},
                     "name_part": "der Titanen"},
    "of_dragons":   {"tier": 3, "weight": 4, "tags": ["weapon", "magic"],
                     "stats": {"fire_damage": (20, 40), "armor_pen_pct": (10, 20)},
                     "name_part": "der Drachen"},
    "of_eternity":  {"tier": 3, "weight": 3, "tags": ["jewelry"],
                     "stats": {"all_stats_pct": (15, 30)}, "name_part": "der Ewigkeit"},
}


# Quality → (min_prefix, max_prefix, min_suffix, max_suffix, can_unique)
AFFIX_BUDGET = {
    "rough":      (0, 0, 0, 0, False),
    "normal":     (0, 0, 0, 0, False),
    "fine":       (0, 1, 0, 1, False),
    "masterwork": (1, 2, 1, 2, False),
    "legendary":  (2, 3, 1, 2, True),
}

# Tier-Limits pro Quality — höhere Quality = Tier-3 möglich
TIER_LIMIT_BY_QUALITY = {
    "fine":       1,
    "masterwork": 2,
    "legendary":  3,
}


# — Helpers ————————————————————————————————————————————————————————————

def _item_tags(item_kind: str) -> set[str]:
    """Welche Tags hat ein Item-Kind für Affix-Matching?"""
    # Pragmatisch: aus item_stats + items ableiten
    try:
        import item_stats
        if item_kind in item_stats.WEAPON_STATS:
            cfg = item_stats.WEAPON_STATS[item_kind]
            tags = {"weapon", "any", cfg["class"]}
            if cfg["class"] in ("physical", "finesse"):
                tags.add("melee")
            if cfg["class"] == "ranged":
                tags.add("ranged")
            if cfg["class"] == "magic":
                tags.add("magic")
            return tags
        if item_kind in item_stats.ARMOR_STATS:
            return {"armor", "any"}
        if item_kind in item_stats.JEWELRY_STATS:
            return {"jewelry", "any"}
    except ImportError:
        pass
    return {"any"}


def _eligible_affixes(pool: dict, item_tags: set[str], tier_max: int) -> list[tuple[str, dict]]:
    out = []
    for aid, a in pool.items():
        if a["tier"] > tier_max:
            continue
        a_tags = set(a["tags"])
        if a_tags & item_tags or "any" in a_tags:
            out.append((aid, a))
    return out


def _roll_one_affix(pool: dict, item_tags: set[str], tier_max: int,
                    excluded: set[str]) -> tuple[str, dict] | None:
    candidates = [(aid, a) for aid, a in _eligible_affixes(pool, item_tags, tier_max)
                  if aid not in excluded]
    if not candidates:
        return None
    weights = [a["weight"] for _, a in candidates]
    aid, a = random.choices(candidates, weights=weights, k=1)[0]
    # Stat-Werte konkretisieren
    rolled_stats = {}
    for stat_key, (mn, mx) in a["stats"].items():
        rolled_stats[stat_key] = random.randint(mn, mx)
    return aid, {
        "id":         aid,
        "kind":       "prefix" if pool is AFFIXES_PREFIX else "suffix",
        "tier":       a["tier"],
        "name_part":  a["name_part"],
        "stats":      rolled_stats,
    }


def roll_affixes(item_kind: str, quality_kind: str) -> list[dict]:
    """Würfelt das komplette Affix-Set für ein Item basierend auf Quality.
    Returns Liste von Affix-Dicts (mit konkreten Stats)."""
    budget = AFFIX_BUDGET.get(quality_kind)
    if budget is None or budget == (0, 0, 0, 0, False):
        return []
    tags = _item_tags(item_kind)
    tier_max = TIER_LIMIT_BY_QUALITY.get(quality_kind, 1)
    n_prefix = random.randint(budget[0], budget[1])
    n_suffix = random.randint(budget[2], budget[3])

    rolled: list[dict] = []
    used_ids: set[str] = set()
    for _ in range(n_prefix):
        r = _roll_one_affix(AFFIXES_PREFIX, tags, tier_max, used_ids)
        if r is None: break
        used_ids.add(r[0])
        rolled.append(r[1])
    for _ in range(n_suffix):
        r = _roll_one_affix(AFFIXES_SUFFIX, tags, tier_max, used_ids)
        if r is None: break
        used_ids.add(r[0])
        rolled.append(r[1])
    return rolled


def build_item_name(item_base_name: str, affixes: list[dict]) -> str:
    """Baut den Item-Namen aus Base + Prefix + Suffix."""
    prefixes = [a for a in affixes if a["kind"] == "prefix"]
    suffixes = [a for a in affixes if a["kind"] == "suffix"]
    name = item_base_name
    if prefixes:
        # Nimm höchsten Tier (wertvollstes Wort zuerst)
        prefixes.sort(key=lambda a: -a["tier"])
        name = prefixes[0]["name_part"] + " " + name
    if suffixes:
        suffixes.sort(key=lambda a: -a["tier"])
        name = name + " " + suffixes[0]["name_part"]
    return name


def aggregate_stats(affixes: list[dict]) -> dict[str, float]:
    """Summiert die Stat-Effekte aller Affixes."""
    out: dict[str, float] = {}
    for a in affixes:
        for k, v in a.get("stats", {}).items():
            out[k] = out.get(k, 0) + v
    return out


# — Persistenz ————————————————————————————————————————————————————————

async def save_affixes_to_item(item_id: int, affixes: list[dict],
                                 unique_name: str | None = None,
                                 flavor: str | None = None) -> None:
    await db.pool().execute(
        "UPDATE items SET affixes = $2, unique_name = $3, flavor = $4 "
        "WHERE id = $1",
        item_id, json.dumps(affixes) if affixes else None,
        unique_name, flavor,
    )


async def load_affixes_for_item(item_id: int) -> tuple[list[dict], str | None, str | None]:
    row = await db.pool().fetchrow(
        "SELECT affixes, unique_name, flavor FROM items WHERE id = $1",
        item_id,
    )
    if row is None:
        return [], None, None
    aff = row["affixes"] or []
    if isinstance(aff, str):
        aff = json.loads(aff)
    return aff, row["unique_name"], row["flavor"]
