"""Stat-Architektur für Waffen, Rüstung und Schmuck.

Jede Waffen-/Rüstungs-Kind hat einen Basis-Stat-Block. Die effektiven Stats
beim Equipping ergeben sich aus:

    final_stat = base_stat * QUALITY_MULT[quality] * (1 + skill_bonus)

Combat-Damage-Formel:
    swing_damage   = (base_damage + combat_lvl_bonus) * quality_mult * crit_mult
    attack_cooldown = base_cooldown / (1 + combat_lvl * 0.01)   # bis -20% bei lvl 20
    crit_chance     = base_crit + combat_lvl * 0.005           # +10% bei lvl 20

Armor-Damage-Reduktion:
    dr_pct  = total_defense / (total_defense + 100)            # diminishing returns
    final_dmg = incoming_dmg * (1 - dr_pct)
"""

import quality

# Damage-Klassen: passen zu unterschiedlichen Skill/Mana-Bonus
# Kategorien: physical, ranged, magic, finesse
WEAPON_STATS = {
    # — Standard-Waffen ——————————————————————————————————————————————————————
    "sword": {
        "damage": 10, "speed": 1.0, "crit": 0.05, "crit_mult": 1.5,
        "range": 1, "class": "physical", "two_handed": False,
    },
    "axe": {
        "damage": 14, "speed": 0.85, "crit": 0.04, "crit_mult": 1.7,
        "range": 1, "class": "physical", "two_handed": False,
    },
    "bow": {
        "damage": 8, "speed": 1.0, "crit": 0.08, "crit_mult": 1.5,
        "range": 5, "class": "ranged", "two_handed": True,
    },
    "staff": {
        "damage": 7, "speed": 1.0, "crit": 0.06, "crit_mult": 1.4,
        "range": 4, "class": "magic", "two_handed": True,
        "mana_bonus": 10,
    },
    # — Welle 16-Erweiterung ————————————————————————————————————————————————
    "wand": {
        "damage": 6, "speed": 1.3, "crit": 0.10, "crit_mult": 1.5,
        "range": 4, "class": "magic", "two_handed": False,
        "mana_bonus": 15,
    },
    "greatsword": {
        "damage": 22, "speed": 0.65, "crit": 0.06, "crit_mult": 1.8,
        "range": 1, "class": "physical", "two_handed": True,
    },
    "spear": {
        "damage": 12, "speed": 1.0, "crit": 0.07, "crit_mult": 1.5,
        "range": 2, "class": "physical", "two_handed": True,  # Reichweite!
    },
    "crossbow": {
        "damage": 16, "speed": 0.55, "crit": 0.12, "crit_mult": 1.8,
        "range": 6, "class": "ranged", "two_handed": True,
    },
    "throwing_knife": {
        "damage": 5, "speed": 1.6, "crit": 0.15, "crit_mult": 2.0,
        "range": 3, "class": "finesse", "two_handed": False,
    },
    "mace": {
        "damage": 13, "speed": 0.85, "crit": 0.03, "crit_mult": 1.6,
        "range": 1, "class": "physical", "two_handed": False,
        "armor_pen": 0.25,   # ignoriert 25% Defense
    },
    "scythe": {
        "damage": 16, "speed": 0.75, "crit": 0.08, "crit_mult": 1.8,
        "range": 1, "class": "physical", "two_handed": True,
        "cleave": True,    # AOE 1-Tile-Radius (später nutzbar)
    },
    "dagger": {
        "damage": 6, "speed": 1.8, "crit": 0.20, "crit_mult": 2.5,
        "range": 1, "class": "finesse", "two_handed": False,
    },
}

# Rüstung: Defense pro Item-Kind
ARMOR_STATS = {
    "helmet":     {"defense": 4,  "weight": 2},
    "chestplate": {"defense": 12, "weight": 5},
    "shield":     {"defense": 8,  "weight": 4, "block_chance": 0.15},
    "boots":      {"defense": 3,  "weight": 1, "speed_bonus": 0.05},
}

# Schmuck: prozentuale Effekte
JEWELRY_STATS = {
    "ring":   {"mana_bonus": 10, "magic_bonus": 0.05},
    "amulet": {"hp_bonus": 15,   "regen_bonus": 0.05},
}

# — Skill-Klassen pro Waffen-Class — bestimmt welcher Skill XP gibt
WEAPON_CLASS_SKILL = {
    "physical": "combat",
    "ranged":   "combat",
    "magic":    "magic",
    "finesse":  "combat",
}


# — Helper ————————————————————————————————————————————————————————————————

def weapon_base_damage(weapon_kind: str | None) -> int:
    """Base-Damage einer Waffe ohne Skill/Quality-Modifier."""
    if weapon_kind is None:
        return 4   # Faust
    cfg = WEAPON_STATS.get(weapon_kind)
    return cfg["damage"] if cfg else 4


def weapon_attack_speed(weapon_kind: str | None) -> float:
    """Attack-Speed-Multiplier (1.0 = normal, 2.0 = doppelt so schnell)."""
    if weapon_kind is None:
        return 1.0
    cfg = WEAPON_STATS.get(weapon_kind)
    return cfg["speed"] if cfg else 1.0


def weapon_range(weapon_kind: str | None) -> int:
    """Effektive Reichweite in Tiles (Manhattan)."""
    if weapon_kind is None:
        return 1
    cfg = WEAPON_STATS.get(weapon_kind)
    return cfg["range"] if cfg else 1


def weapon_class(weapon_kind: str | None) -> str:
    if weapon_kind is None:
        return "physical"
    cfg = WEAPON_STATS.get(weapon_kind)
    return cfg["class"] if cfg else "physical"


def is_two_handed(weapon_kind: str | None) -> bool:
    if weapon_kind is None:
        return False
    cfg = WEAPON_STATS.get(weapon_kind)
    return cfg.get("two_handed", False) if cfg else False


def weapon_stats_summary(weapon_kind: str, quality_kind: str = "normal") -> dict:
    """Kompletter Stat-Block für UI — schon mit Quality-Multiplier angewendet."""
    cfg = WEAPON_STATS.get(weapon_kind)
    if not cfg:
        return {}
    mult = quality.QUALITY_MULT.get(quality_kind, 1.0)
    return {
        "damage":     round(cfg["damage"] * mult, 1),
        "speed":      cfg["speed"],
        "crit":       cfg["crit"],
        "crit_mult":  cfg["crit_mult"],
        "range":      cfg["range"],
        "class":      cfg["class"],
        "two_handed": cfg.get("two_handed", False),
    }


def armor_defense(armor_kind: str | None, quality_kind: str = "normal") -> int:
    if armor_kind is None:
        return 0
    cfg = ARMOR_STATS.get(armor_kind)
    if not cfg:
        return 0
    mult = quality.QUALITY_MULT.get(quality_kind, 1.0)
    return int(round(cfg["defense"] * mult))


def armor_stats_summary(armor_kind: str, quality_kind: str = "normal") -> dict:
    cfg = ARMOR_STATS.get(armor_kind)
    if not cfg:
        return {}
    mult = quality.QUALITY_MULT.get(quality_kind, 1.0)
    out = dict(cfg)
    out["defense"] = int(round(cfg["defense"] * mult))
    return out


def damage_reduction(total_defense: int) -> float:
    """Standard-RPG-Formel: diminishing returns. 100 Def = 50% DR."""
    if total_defense <= 0:
        return 0.0
    return total_defense / (total_defense + 100.0)
