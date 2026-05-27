"""Player-Profile-Erkennung (Welle 20).

Aus den Skill-XP eines Spielers wird ein Profile abgeleitet, damit das
World-Brain seine Event-Auswahl auf die aktiven Spieler tunen kann.

Profile-Typen:
    warrior     — Combat-fokussiert
    crafter     — Crafting/Mining/Smithing
    mage        — Magic
    farmer      — Farming/Cooking
    ranger      — Gathering/Woodcutting/Exploration
    generalist  — gemischt (keiner über 35% dominant)

Erkennung: anteilig am Total-XP. Skill-Gruppen:
    combat    → warrior
    crafting, mining, construction → crafter
    magic, research → mage
    farming, cooking → farmer
    gathering, woodcutting, medical, social → ranger
"""
import logging

log = logging.getLogger("liege.player_profile")

# Skill → Profil-Gruppe
SKILL_GROUPS = {
    "combat":       "warrior",
    "crafting":     "crafter",
    "mining":       "crafter",
    "construction": "crafter",
    "magic":        "mage",
    "research":     "mage",
    "farming":      "farmer",
    "cooking":      "farmer",
    "gathering":    "ranger",
    "woodcutting":  "ranger",
    "medical":      "ranger",
    "social":       "ranger",
}

# Dominanz-Schwellen
DOMINANT_THRESHOLD = 0.35   # min anteil um als Profil zu zählen
GENERALIST_DEFAULT = "generalist"


def profile_from_skills(skills_dict: dict) -> str:
    """Berechnet das Profil aus skills_dict {skill_name: {level, xp}}.

    Returns einer aus warrior/crafter/mage/farmer/ranger/generalist.
    Wenn der Spieler kaum XP hat (< 50 total), wird 'generalist' zurückgegeben.
    """
    if not skills_dict:
        return GENERALIST_DEFAULT
    group_xp: dict[str, float] = {}
    total_xp = 0.0
    for skill_name, data in skills_dict.items():
        xp = float(data.get("xp", 0))
        if xp <= 0:
            continue
        total_xp += xp
        group = SKILL_GROUPS.get(skill_name)
        if group is None:
            continue
        group_xp[group] = group_xp.get(group, 0.0) + xp
    if total_xp < 50:
        return GENERALIST_DEFAULT
    if not group_xp:
        return GENERALIST_DEFAULT
    # Top-Gruppe
    top_group, top_xp = max(group_xp.items(), key=lambda kv: kv[1])
    if top_xp / total_xp >= DOMINANT_THRESHOLD:
        return top_group
    return GENERALIST_DEFAULT


async def active_audiences(connection_manager, skills_module) -> set[str]:
    """Returns die set der Profile aller gerade verbundenen Spieler.

    Wenn niemand connected: leere Menge (storyteller fällt dann auf reine
    weight-basierte Auswahl zurück, ohne Audience-Bonus)."""
    audiences: set[str] = set()
    for name in connection_manager.get_players().keys():
        try:
            sk = await skills_module.get_skills(name)
            audiences.add(profile_from_skills(sk))
        except Exception:
            log.debug("Profil-Lookup für %s fehlgeschlagen", name, exc_info=True)
            audiences.add(GENERALIST_DEFAULT)
    return audiences


def label(profile: str) -> str:
    return {
        "warrior":    "⚔️ Krieger",
        "crafter":    "⚒️ Handwerker",
        "mage":       "🔮 Magier",
        "farmer":     "🌾 Bauer",
        "ranger":     "🏹 Späher",
        "generalist": "🎭 Generalist",
    }.get(profile, profile)
