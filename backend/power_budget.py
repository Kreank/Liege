"""Combat-Power-Budget (Recherche-Empfehlung).

Formalisiert erwarteten Spieler-DPS pro Level → kalibriert Mob-HP/Damage.

Player-Level wird als max(skills) ermittelt — pragmatisch, da wir kein
Gesamt-Level haben (RimWorld-style).

Curve (Last-Epoch-inspired):
    expected_dps(level) = BASE_DPS * 1.15^level    (15% pro Level)
    boss_dps(level)     = BASE_DPS * 1.12^level    (etwas darunter)
    mob_hp_scale(level) = 1.0 + level * 0.10       (Mob-HP wächst mit Player-Level)

Mob-Damage skaliert sanfter — damit ein Wolf nicht zum Insta-Kill wird.
"""
import math
import logging

log = logging.getLogger("liege.power_budget")

# Konstanten
BASE_PLAYER_DPS = 10.0    # erwartet bei Level 0 (Faust + base)
GROWTH_RATE     = 1.15    # 15% pro Level
BOSS_GROWTH     = 1.12    # Bosse hinken etwas hinterher
SOFT_CAP_LEVEL  = 20      # Skill-Cap

# Mob-Skalierung
MOB_HP_FLOOR_MULT  = 1.0
MOB_HP_CAP_MULT    = 3.0    # Max 3× HP wenn Player Lvl 20
MOB_DMG_GROWTH     = 1.06   # 6% pro Level — sanfter als HP


def expected_player_dps(level: int) -> float:
    """Erwarteter Spieler-DPS bei diesem Level."""
    lvl = max(0, min(SOFT_CAP_LEVEL, level))
    return BASE_PLAYER_DPS * (GROWTH_RATE ** lvl)


def expected_boss_dps(level: int) -> float:
    lvl = max(0, min(SOFT_CAP_LEVEL, level))
    return BASE_PLAYER_DPS * (BOSS_GROWTH ** lvl)


def mob_hp_multiplier(player_level: int) -> float:
    """Skaliert Base-HP von Mobs basierend auf Player-Level."""
    lvl = max(0, player_level)
    mult = 1.0 + lvl * 0.10
    return min(MOB_HP_CAP_MULT, max(MOB_HP_FLOOR_MULT, mult))


def mob_damage_multiplier(player_level: int) -> float:
    """Skaliert Mob-Damage sanft mit Player-Level."""
    lvl = max(0, min(SOFT_CAP_LEVEL, player_level))
    return MOB_DMG_GROWTH ** lvl


def player_level_estimate(skills_dict: dict) -> int:
    """Schätzt 'Player-Level' aus Skills-Dict.

    Kombiniert höchsten Combat-Wert (zählt am meisten) mit zweithöchster Skill.
    Beispiel: combat=10, mining=8 → ~9.
    """
    if not skills_dict:
        return 0
    combat_lvl = skills_dict.get("combat", {}).get("level", 0)
    magic_lvl = skills_dict.get("magic", {}).get("level", 0)
    others = sorted(
        (s.get("level", 0) for k, s in skills_dict.items()
         if k not in ("combat", "magic")),
        reverse=True,
    )
    second = others[0] if others else 0
    # Combat/Magic ist primär; restliche bringen 50% mit
    primary = max(combat_lvl, magic_lvl)
    return int(round(primary + second * 0.5))


def kalibrate_mob_hp(base_hp: int, player_level: int) -> int:
    """Skaliert einen Mob-Base-HP gegen Player-Level."""
    return int(round(base_hp * mob_hp_multiplier(player_level)))


def kalibrate_mob_damage(base_dmg: int, player_level: int) -> int:
    return int(round(base_dmg * mob_damage_multiplier(player_level)))
