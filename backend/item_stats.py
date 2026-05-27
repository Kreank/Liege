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
    # ─── Welle 19 (2026-05-26i): Stat-Rebalance — klare Klassen-Identitäten ────
    # Faustformel: 1H DPS ≈ X, 2H DPS ≈ 1.3-1.5×X. Range-Waffen ~0.9×X als
    # Reichweite-Steuer. Magic ~0.7×X kompensiert durch Mana/Range.
    #
    # ── 1H Melee ────────────────────────────────────────────────────────────
    "dagger": {
        # Assassin — schnell, sehr hohe Crit, niedrige Basis. DPS 6×1.8=10.8.
        # Mit Crit-Avg (22% × 2.5× extra-mult): ~13 effektive DPS.
        "damage": 6, "speed": 1.8, "crit": 0.22, "crit_mult": 2.5,
        "range": 1, "class": "finesse", "two_handed": False,
    },
    "sword": {
        # Allrounder — balanced. DPS 11×1.0=11.0. Reliable, kein Spezialeffekt.
        "damage": 11, "speed": 1.0, "crit": 0.06, "crit_mult": 1.5,
        "range": 1, "class": "physical", "two_handed": False,
    },
    "axe": {
        # Brawler — hoch DMG, langsam, leichte armor_pen.
        # DPS 15×0.85=12.75 (+armor_pen-Bonus).
        "damage": 15, "speed": 0.85, "crit": 0.05, "crit_mult": 1.7,
        "range": 1, "class": "physical", "two_handed": False,
        "armor_pen": 0.10,
    },
    "mace": {
        # Anti-Armor — niedrige DMG, sehr langsam, MASSIVE armor_pen.
        # Gegen gerüstete Gegner deutlich effektiver als Sword/Axe.
        "damage": 13, "speed": 0.80, "crit": 0.03, "crit_mult": 1.6,
        "range": 1, "class": "physical", "two_handed": False,
        "armor_pen": 0.35,
    },

    # ── 1H Magic/Finesse Ranged ─────────────────────────────────────────────
    "throwing_knife": {
        # Skirmisher — sehr schnell, gute Crit, mittlere Range.
        "damage": 6, "speed": 1.6, "crit": 0.15, "crit_mult": 2.0,
        "range": 3, "class": "finesse", "two_handed": False,
    },
    "wand": {
        # Caster-1H — schnell, hoher Crit, mana-bonus. DPS 7×1.3=9.1.
        "damage": 7, "speed": 1.3, "crit": 0.10, "crit_mult": 1.5,
        "range": 4, "class": "magic", "two_handed": False,
        "mana_bonus": 15,
    },

    # ── 2H Melee ────────────────────────────────────────────────────────────
    "greatsword": {
        # Power-2H — sehr hoher single-target DMG, sehr langsam.
        # DPS 26×0.65=16.9 (~50% mehr als 1H Sword — 2H-Premium).
        "damage": 26, "speed": 0.65, "crit": 0.07, "crit_mult": 1.9,
        "range": 1, "class": "physical", "two_handed": True,
    },
    "spear": {
        # Reach-Waffe — Range 2 ist der Selling-Point.
        "damage": 13, "speed": 1.0, "crit": 0.08, "crit_mult": 1.6,
        "range": 2, "class": "physical", "two_handed": True,
    },
    "scythe": {
        # AOE-Cleaver — hoher DMG + cleave (Mehrfach-Hit-Potenzial).
        "damage": 18, "speed": 0.70, "crit": 0.08, "crit_mult": 1.9,
        "range": 1, "class": "physical", "two_handed": True,
        "cleave": True,
    },

    # ── 2H Ranged ───────────────────────────────────────────────────────────
    "bow": {
        # Standard-Bogen — gute DPS, Range 5. DPS 10×1.0=10.
        "damage": 10, "speed": 1.0, "crit": 0.10, "crit_mult": 1.6,
        "range": 5, "class": "ranged", "two_handed": True,
    },
    "crossbow": {
        # Sniper — niedrige DPS aber MASSIVER single-shot + armor_pen.
        # DPS 22×0.50=11. Single-Hit deutlich tödlicher als Bow.
        "damage": 22, "speed": 0.50, "crit": 0.15, "crit_mult": 1.9,
        "range": 6, "class": "ranged", "two_handed": True,
        "armor_pen": 0.30,
    },

    # ── 2H Magic ────────────────────────────────────────────────────────────
    "staff": {
        # Caster-2H — Range 4, mana-bonus, etwas mehr DMG als Wand.
        "damage": 9, "speed": 1.0, "crit": 0.08, "crit_mult": 1.5,
        "range": 4, "class": "magic", "two_handed": True,
        "mana_bonus": 12,
    },
}

# Rüstung: Defense pro Slot (Welle 19 — höhere Werte für meaningful protection).
# Vollausrüstung Common (8+22+4+15+6 = 55) → 35% DR
# Vollausrüstung Legendary (×1.5 = 82) → 45% DR
ARMOR_STATS = {
    "helmet":     {"defense": 8,  "weight": 3},
    "chestplate": {"defense": 22, "weight": 8},     # größter Brocken
    "gloves":     {"defense": 4,  "weight": 1, "crit_chance_bonus": 0.01},
    "shield":     {"defense": 15, "weight": 5, "block_chance": 0.15},
    "boots":      {"defense": 6,  "weight": 2, "speed_bonus": 0.05},
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
