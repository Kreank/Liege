"""Skill-System nach RimWorld-Vorbild.

Spieler haben mehrere Skills (Mining, Woodcutting, Crafting etc.) mit Level 0-20.
Aktionen geben XP, Level steigt non-linear. Höhere Level → mehr Output, höhere
Qualität, mehr Damage."""

import logging

import db

log = logging.getLogger("liege.skills")

SKILL_KINDS = [
    "mining",       # Felsen ernten
    "woodcutting",  # Bäume ernten
    "gathering",    # Pflanzen ernten
    "construction", # Bauen
    "crafting",     # Werkbank/Schmelze/Amboss
    "combat",       # Kreaturen-Schaden
    "magic",        # Spell-Cast
    # Welle 13 — RimWorld-inspirierte Erweiterung
    "cooking",      # Brot backen, Fleisch garen
    "medical",      # Heiltrank/Mana-Trank-Use, später: andere Spieler heilen
    "farming",      # Acker pflanzen + ernten (separat von gathering)
    "social",       # NPC-Dialog, Trade-Preise, Quest-Annahme
]
SKILL_LABELS = {
    "mining":       "Bergbau",
    "woodcutting":  "Holzfällen",
    "gathering":    "Sammeln",
    "construction": "Bauen",
    "crafting":     "Handwerk",
    "combat":       "Kampf",
    "magic":        "Magie",
    "cooking":      "Kochen",
    "medical":      "Heilkunde",
    "farming":      "Landwirtschaft",
    "social":       "Sozial",
}
SKILL_ICONS = {
    "mining": "⛏️", "woodcutting": "🪓", "gathering": "🌿",
    "construction": "🔨", "crafting": "⚒️", "combat": "⚔️", "magic": "✨",
    "cooking": "🍳", "medical": "❤️‍🩹", "farming": "🌾", "social": "💬",
}


# — Skill-spezifische Effekte —————————————————————————————————————————————

def cooking_quality_bonus(level: int) -> float:
    """Höhere Hunger-Restoration je Cooking-Level beim Food-Output."""
    return 1.0 + level * 0.04   # +80% bei Level 20


def medical_heal_bonus(level: int) -> float:
    """Heiltränke heilen mehr bei höherem Medical-Level."""
    return 1.0 + level * 0.05


def farming_growth_bonus(level: int) -> float:
    """Schnelleres Pflanzenwachstum / mehr Ernte."""
    return 1.0 + level * 0.05


def social_trade_discount(level: int) -> float:
    """Reduziert Kaufpreise bei Händlern. 1.0 = full, 0.7 = 30% Rabatt."""
    return max(0.5, 1.0 - level * 0.025)

MAX_LEVEL = 20


def xp_for_level(n: int) -> int:
    """XP needed to gain level n (going from level n-1 to n)."""
    return int(100 * (n ** 1.5))


def total_xp_for_level(level: int) -> int:
    """Cumulative XP needed to reach this level."""
    return sum(xp_for_level(n) for n in range(1, level + 1))


def level_for_xp(total_xp: int) -> int:
    n = 0
    cum = 0
    while n < MAX_LEVEL:
        needed = xp_for_level(n + 1)
        if cum + needed > total_xp:
            break
        cum += needed
        n += 1
    return n


def xp_to_next_level(total_xp: int) -> tuple[int, int]:
    """Returns (current_progress_in_level, xp_needed_for_next_level)."""
    level = level_for_xp(total_xp)
    if level >= MAX_LEVEL:
        return (0, 0)
    cum = total_xp_for_level(level)
    progress = total_xp - cum
    needed = xp_for_level(level + 1)
    return (progress, needed)


# — Skill-Effekte ————————————————————————————————————————————————————————

def harvest_yield_bonus(level: int) -> float:
    """1.0 = no bonus, höhere Werte = mehr Drops. Max 2.0 bei Level 20."""
    return 1.0 + level * 0.05


def combat_damage_bonus(level: int) -> int:
    """Zusätzlicher Schaden basierend auf Combat-Level."""
    return level // 4


def magic_damage_bonus(level: int) -> int:
    return level // 4


# — DB-Zugriff ————————————————————————————————————————————————————————————

async def get_skills(player_name: str) -> dict:
    rows = await db.pool().fetch(
        "SELECT skill, xp, level FROM player_skills WHERE player_name = $1",
        player_name,
    )
    out = {s: {"xp": 0, "level": 0} for s in SKILL_KINDS}
    for r in rows:
        if r["skill"] in out:
            out[r["skill"]] = {"xp": r["xp"], "level": r["level"]}
    return out


async def get_skill_level(player_name: str, skill: str) -> int:
    row = await db.pool().fetchrow(
        "SELECT level FROM player_skills WHERE player_name = $1 AND skill = $2",
        player_name, skill,
    )
    return row["level"] if row else 0


async def gain_xp(player_name: str, skill: str, amount: int) -> dict | None:
    """Add XP to a skill. Returns new state + whether leveled up.
    Returns None if skill invalid or amount <= 0."""
    if skill not in SKILL_KINDS or amount <= 0:
        return None
    row = await db.pool().fetchrow(
        "INSERT INTO player_skills (player_name, skill, xp, level) "
        "VALUES ($1, $2, $3, 0) "
        "ON CONFLICT (player_name, skill) DO UPDATE "
        "SET xp = player_skills.xp + EXCLUDED.xp "
        "RETURNING xp, level",
        player_name, skill, amount,
    )
    new_xp = row["xp"]
    old_level = row["level"]
    new_level = level_for_xp(new_xp)
    leveled_up = new_level > old_level
    points_gained = 0
    if leveled_up:
        await db.pool().execute(
            "UPDATE player_skills SET level = $1 "
            "WHERE player_name = $2 AND skill = $3",
            new_level, player_name, skill,
        )
        # Talent-Punkte: 1 pro Level-Up. Bei großen XP-Sprüngen mehrere
        # auf einmal möglich.
        points_gained = max(0, new_level - old_level)
        if points_gained > 0:
            try:
                import talents as _talents
                await _talents.grant_talent_point(player_name, points_gained)
            except Exception:
                log.exception("Talent-Punkt-Vergabe schlug fehl")
    return {
        "skill":          skill,
        "xp":             new_xp,
        "level":          new_level,
        "leveled_up":     leveled_up,
        "talent_points":  points_gained,
    }
