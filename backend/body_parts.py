"""Body-Parts-Verletzungs-System nach RimWorld-Vorbild.

Spieler haben drei Körperteile (legs, arms, torso) mit jeweils 0-100 HP. Wenn
Schaden eingeht, wird er auf ein zufälliges (gewichtetes) Körperteil verteilt.
Verletzte Körperteile haben Folgewirkungen:

  - Arme:  reduzieren den ausgeteilten Schaden (Multiplikator)
  - Beine: reduzieren Bewegungsgeschwindigkeit (zukünftig)
  - Torso: reduziert die maximale HP

Heilung setzt alle Teile auf 100 zurück (z.B. nach Schlaf oder Heiltrank)."""

import logging
import random

import db

log = logging.getLogger("liege.body_parts")

# — DB-Schema-Ergänzungen ———————————————————————————————————————————————————————
# In db.py beim Init ausführen (idempotent via IF NOT EXISTS).
SCHEMA_ALTERS: tuple[str, ...] = (
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS legs_health  INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS arms_health  INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS torso_health INTEGER NOT NULL DEFAULT 100",
)

# — Tuning-Konstanten —————————————————————————————————————————————————————————
BODY_PARTS: list[str] = ["legs", "arms", "torso"]
PART_DAMAGE_WEIGHT: dict[str, int] = {"legs": 30, "arms": 35, "torso": 35}
MAX_PART_HP: int = 100

# Wie stark reduzieren beschädigte Arme den ausgeteilten Schaden? (bei arms=0)
ARM_MIN_DAMAGE_MULT: float = 0.3

# Maximale max_hp-Reduktion durch zerstörten Torso (bei torso=0)
TORSO_MAX_HP_REDUCTION: int = 50


# — DB-Zugriff ————————————————————————————————————————————————————————————————

def _row_to_parts(row) -> dict:
    return {
        "legs":  row["legs_health"],
        "arms":  row["arms_health"],
        "torso": row["torso_health"],
    }


async def get_body_parts(player_name: str) -> dict | None:
    """Returns {legs, arms, torso} oder None wenn Spieler nicht existiert."""
    row = await db.pool().fetchrow(
        "SELECT legs_health, arms_health, torso_health "
        "FROM players WHERE name = $1",
        player_name,
    )
    return _row_to_parts(row) if row else None


def _pick_random_part() -> str:
    """Pickt ein Körperteil gewichtet nach PART_DAMAGE_WEIGHT."""
    parts = BODY_PARTS
    weights = [PART_DAMAGE_WEIGHT[p] for p in parts]
    return random.choices(parts, weights=weights, k=1)[0]


async def damage_random_part(player_name: str, dmg: int) -> dict | None:
    """Verteilt Schaden auf ein zufälliges (gewichtetes) Körperteil und clamped
    auf >= 0. Returns {part, remaining, dmg} oder None wenn Spieler nicht
    existiert oder dmg <= 0."""
    if dmg <= 0:
        return None
    part = _pick_random_part()
    col = f"{part}_health"
    row = await db.pool().fetchrow(
        f"UPDATE players SET {col} = GREATEST(0, {col} - $2) "
        "WHERE name = $1 "
        f"RETURNING {col} AS remaining",
        player_name, dmg,
    )
    if row is None:
        return None
    return {
        "part":      part,
        "remaining": row["remaining"],
        "dmg":       dmg,
    }


async def heal_all_parts(player_name: str) -> dict | None:
    """Setzt alle drei Körperteile auf MAX_PART_HP zurück. Returns neuen Stand
    oder None wenn Spieler nicht existiert."""
    row = await db.pool().fetchrow(
        "UPDATE players "
        "SET legs_health = $2, arms_health = $2, torso_health = $2 "
        "WHERE name = $1 "
        "RETURNING legs_health, arms_health, torso_health",
        player_name, MAX_PART_HP,
    )
    return _row_to_parts(row) if row else None


# — Effekt-Helper (sync) ——————————————————————————————————————————————————————

def arm_damage_multiplier(arms_health: int) -> float:
    """Multiplier auf den ausgeteilten Schaden basierend auf Arm-HP.

    arms=100 -> 1.0, arms=0 -> ARM_MIN_DAMAGE_MULT (0.3), linear interpoliert.
    Werte oberhalb von 100 werden auf 1.0 gecappt."""
    if arms_health >= MAX_PART_HP:
        return 1.0
    if arms_health <= 0:
        return ARM_MIN_DAMAGE_MULT
    frac = arms_health / MAX_PART_HP
    return ARM_MIN_DAMAGE_MULT + (1.0 - ARM_MIN_DAMAGE_MULT) * frac


def leg_move_multiplier(legs_health: int) -> float:
    """Multiplier auf Bewegungsgeschwindigkeit (für später; aktuell immer 1.0)."""
    return 1.0


def torso_max_hp_reduction(torso_health: int) -> int:
    """Reduktion der maximalen HP basierend auf Torso-HP.

    torso=100 -> 0, torso=0 -> TORSO_MAX_HP_REDUCTION (50), linear interpoliert.
    Returns einen positiven Wert (= zu subtrahierender Betrag)."""
    if torso_health >= MAX_PART_HP:
        return 0
    if torso_health <= 0:
        return TORSO_MAX_HP_REDUCTION
    frac = torso_health / MAX_PART_HP
    return int(round(TORSO_MAX_HP_REDUCTION * (1.0 - frac)))
