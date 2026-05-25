"""Item-Quality nach RimWorld: 5 Stufen, skill-abhängige Verteilung.

roh < normal < fein < meisterhaft < legendär.
Multiplier auf damage / defense / value für Equipment-Items.
Bei resources/consumables: meist 'normal', kein Effekt."""

import random


QUALITY_KINDS = ["rough", "normal", "fine", "masterwork", "legendary"]

QUALITY_LABELS = {
    "rough":      "Roh",
    "normal":     "",          # leeres Label für normal — Default-Item
    "fine":       "Fein",
    "masterwork": "Meisterhaft",
    "legendary":  "Legendär",
}

QUALITY_ICONS = {
    "rough":      "⚠️",
    "normal":     "",
    "fine":       "✨",
    "masterwork": "🌟",
    "legendary":  "👑",
}

# Multiplier auf base stats (damage/defense)
QUALITY_MULT = {
    "rough":      0.70,
    "normal":     1.00,
    "fine":       1.25,
    "masterwork": 1.60,
    "legendary":  2.20,
}

# Multiplier auf Marktpreis
QUALITY_VALUE_MULT = {
    "rough":      0.5,
    "normal":     1.0,
    "fine":       1.8,
    "masterwork": 3.5,
    "legendary":  7.0,
}


def roll_quality(skill_level: int) -> str:
    """Würfelt Qualität basierend auf Skill-Level (0-20).
    Höheres Level → höhere Chance auf bessere Qualität."""
    if skill_level >= 18:
        weights = [1, 4, 20, 40, 15]   # masterwork bevorzugt
    elif skill_level >= 14:
        weights = [2, 15, 35, 25, 5]
    elif skill_level >= 10:
        weights = [5, 35, 30, 10, 1]
    elif skill_level >= 6:
        weights = [10, 55, 20, 4, 0]
    elif skill_level >= 3:
        weights = [20, 65, 12, 1, 0]
    else:
        weights = [35, 60, 5, 0, 0]
    return random.choices(QUALITY_KINDS, weights=weights, k=1)[0]


def damage_multiplier(quality: str) -> float:
    return QUALITY_MULT.get(quality, 1.0)


def value_multiplier(quality: str) -> float:
    return QUALITY_VALUE_MULT.get(quality, 1.0)


def display_name(base_name: str, quality: str) -> str:
    """Item-Anzeigename mit Quality-Präfix."""
    if quality == "normal":
        return base_name
    icon = QUALITY_ICONS.get(quality, "")
    label = QUALITY_LABELS.get(quality, "")
    if icon and label:
        return f"{icon} {label} {base_name}"
    return base_name
