"""Stat-Architektur für Waffen, Rüstung und Schmuck.

Jede Waffen-/Rüstungs-Kind hat einen Basis-Stat-Block. Die effektiven Stats
beim Equipping ergeben sich aus:

    final_stat = rolled_base_stat * (1 + skill_bonus)

Welle 23: Per-Instance-Variance — jedes Equipment-Item rollt beim Erzeugen
seine eigenen Basis-Stats (damage als min/max range, andere Stats als
einzelner Wert). Höhere Quality vergrößert die Variance-Breite, sodass
legendäre Items deutlich von ihrer Basis abweichen können.

Combat-Damage-Formel:
    swing_damage   = random(rolled.damage_min, rolled.damage_max) + combat_bonus
    attack_cooldown = base_cooldown / (1 + combat_lvl * 0.01)
    crit_chance     = rolled.crit + combat_level * 0.005

Armor-Damage-Reduktion:
    dr_pct  = total_defense / (total_defense + 100)
    final_dmg = incoming_dmg * (1 - dr_pct)
"""

import random
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


# ─── Welle 23 — Per-Instance Stat-Roll ────────────────────────────────────
# Wie weit darf ein einzelnes Item vom Quality-multiplizierten Mittelwert
# abweichen? Höhere Quality = breitere Range (Bedeutung der Knappheit).
# Plus per-Swing-Variance auf damage damit kein Treffer gleich ist.
_INSTANCE_VARIANCE_PCT = {
    "rough":      0.08,   # ±8% Mittelpunkt
    "normal":     0.12,
    "fine":       0.18,
    "masterwork": 0.25,
    "legendary":  0.35,
}
_SWING_RANGE_PCT = {
    "rough":      0.12,   # damage_min/max ±12% des Mittelpunkts
    "normal":     0.15,
    "fine":       0.18,
    "masterwork": 0.22,
    "legendary":  0.30,
}


def _vary(base: float, pct: float, rng: random.Random | None = None) -> float:
    """Multipliziert base mit (1 ± pct) gleichverteilt."""
    r = rng or random
    return base * (1.0 + r.uniform(-pct, pct))


def roll_base_stats(item_kind: str, quality_kind: str = "normal",
                    rng: random.Random | None = None) -> dict | None:
    """Würfelt pro Item-Instanz die Basis-Stats inkl. damage-Range.
    Returns None für Nicht-Equipment-Items (resources/consumables/food).

    Schema je Slot:
      Waffe:   {damage_min, damage_max, speed, crit, crit_mult, range, armor_pen?}
      Rüstung: {defense, [weight], [crit_chance_bonus|block_chance|speed_bonus]}
      Schmuck: jewelry-stats (hp_bonus / mana_bonus / regen_bonus / magic_bonus)
    """
    r = rng or random
    q_mult = quality.QUALITY_MULT.get(quality_kind, 1.0)
    inst_pct = _INSTANCE_VARIANCE_PCT.get(quality_kind, 0.12)
    swing_pct = _SWING_RANGE_PCT.get(quality_kind, 0.15)

    # — Waffe —
    w = WEAPON_STATS.get(item_kind)
    if w is not None:
        center = w["damage"] * q_mult
        center = _vary(center, inst_pct, r)
        rolled = {
            "damage_min": max(1, int(round(center * (1.0 - swing_pct)))),
            "damage_max": max(1, int(round(center * (1.0 + swing_pct)))),
            "speed":      round(_vary(w["speed"],     inst_pct * 0.5, r), 3),
            "crit":       round(max(0.0, _vary(w["crit"], inst_pct, r)), 4),
            "crit_mult":  round(_vary(w["crit_mult"], inst_pct * 0.5, r), 3),
            "range":      w["range"],     # Range nie variieren (Gameplay-Logik)
        }
        if "armor_pen" in w:
            rolled["armor_pen"] = round(max(0.0, _vary(w["armor_pen"], inst_pct, r)), 3)
        if w.get("two_handed"):
            rolled["two_handed"] = True
        if w.get("cleave"):
            rolled["cleave"] = True
        return rolled

    # — Rüstung —
    a = ARMOR_STATS.get(item_kind)
    if a is not None:
        rolled = {
            "defense": max(1, int(round(_vary(a["defense"] * q_mult, inst_pct, r)))),
        }
        if "weight" in a:
            rolled["weight"] = a["weight"]
        if "crit_chance_bonus" in a:
            rolled["crit_chance_bonus"] = round(_vary(a["crit_chance_bonus"], inst_pct, r), 4)
        if "block_chance" in a:
            rolled["block_chance"] = round(_vary(a["block_chance"], inst_pct, r), 4)
        if "speed_bonus" in a:
            rolled["speed_bonus"] = round(_vary(a["speed_bonus"], inst_pct, r), 4)
        return rolled

    # — Schmuck —
    j = JEWELRY_STATS.get(item_kind)
    if j is not None:
        rolled = {}
        for k, v in j.items():
            scaled = v * q_mult if isinstance(v, (int, float)) else v
            rolled[k] = (int(round(_vary(scaled, inst_pct, r)))
                         if isinstance(v, int)
                         else round(_vary(scaled, inst_pct, r), 4))
        return rolled

    return None


def roll_swing_damage(rolled: dict | None,
                      fallback_kind: str | None = None,
                      rng: random.Random | None = None) -> int:
    """Pro-Swing-Damage: rolled in (damage_min, damage_max), sonst Legacy-Base."""
    r = rng or random
    if rolled and "damage_min" in rolled and "damage_max" in rolled:
        lo, hi = rolled["damage_min"], rolled["damage_max"]
        return r.randint(lo, hi) if hi > lo else lo
    # Fallback für Items ohne rolled_stats (Pre-Welle-23-Inventar)
    return weapon_base_damage(fallback_kind)
