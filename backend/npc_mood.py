import asyncio
import logging
import os

import db

log = logging.getLogger("liege.npc_mood")

# — DB-Schema-Ergänzungen ———————————————————————————————————————————————————————
# In db.py beim Init ausführen (idempotent via IF NOT EXISTS).
SCHEMA_ALTERS: tuple[str, ...] = (
    "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS mood_value INTEGER NOT NULL DEFAULT 50",
    "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS mental_state TEXT NOT NULL DEFAULT 'normal'",
    "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMPTZ NULL",
)

# — Tuning-Konstanten —————————————————————————————————————————————————————————
MOOD_DECAY_TICK_SECONDS: int = int(os.environ.get("MOOD_DECAY_TICK_SECONDS", "60"))
MOOD_RECOVER_PER_TICK: int = 1

# mood_value <= threshold => entsprechender mental_state
# Reihenfolge: niedrigste Schwelle gewinnt (berserk < fleeing < sad).
MOOD_THRESHOLDS: dict[str, int] = {
    "sad":     30,
    "fleeing": 15,
    "berserk": 5,
}

# Mood-Deltas pro Event-Typ (für andere Module zum Triggern)
MOOD_EVENT_DELTA: dict[str, int] = {
    "attacked":         -15,
    "killed_neighbor":  -25,
    "healed":           +10,
    "wandered_far":     -3,
}

# Welche Kinds gelten als "friendly" (für Berserk-Logik).
# Wird hier dupliziert um Zirkular-Import mit npc_worker zu vermeiden.
FRIENDLY_KINDS: frozenset[str] = frozenset(
    {"wanderer", "merchant", "hermit", "bard", "scholar", "soldier"}
)

MOOD_MIN: int = 0
MOOD_MAX: int = 100
MOOD_NEUTRAL: int = 50


# — Helpers ———————————————————————————————————————————————————————————————————

def compute_mental_state(mood_value: int) -> str:
    """Liefert den mental_state für einen gegebenen mood_value.

    Schwellenwerte sind kumulativ von unten nach oben: berserk (≤5) < fleeing
    (≤15) < sad (≤30) < normal (Rest).
    """
    if mood_value <= MOOD_THRESHOLDS["berserk"]:
        return "berserk"
    if mood_value <= MOOD_THRESHOLDS["fleeing"]:
        return "fleeing"
    if mood_value <= MOOD_THRESHOLDS["sad"]:
        return "sad"
    return "normal"


def _clamp_mood(value: int) -> int:
    return max(MOOD_MIN, min(MOOD_MAX, value))


def _row_to_mood(row) -> dict:
    return {
        "mood_value":   row["mood_value"],
        "mental_state": row["mental_state"],
    }


# — DB-Queries ————————————————————————————————————————————————————————————————

async def get_mood(npc_id: int) -> dict | None:
    """Liefert {mood_value, mental_state} oder None wenn NPC nicht existiert."""
    row = await db.pool().fetchrow(
        "SELECT mood_value, mental_state FROM npcs WHERE id = $1",
        npc_id,
    )
    return _row_to_mood(row) if row else None


async def adjust_mood(npc_id: int, delta: int, reason: str = "") -> dict | None:
    """Verändert mood_value um delta (clamped 0..100), aktualisiert mental_state
    nach den Schwellen und setzt last_event_at = NOW(). Liefert neuen State oder
    None wenn NPC nicht existiert.
    """
    if delta == 0:
        return await get_mood(npc_id)

    # 1) Aktuellen Wert holen
    current = await db.pool().fetchrow(
        "SELECT mood_value FROM npcs WHERE id = $1",
        npc_id,
    )
    if current is None:
        return None

    new_value = _clamp_mood(int(current["mood_value"]) + int(delta))
    new_state = compute_mental_state(new_value)

    row = await db.pool().fetchrow(
        "UPDATE npcs "
        "SET mood_value = $2, mental_state = $3, last_event_at = NOW() "
        "WHERE id = $1 "
        "RETURNING mood_value, mental_state",
        npc_id, new_value, new_state,
    )
    if row is None:
        return None

    if reason:
        log.debug(
            "adjust_mood npc=%s delta=%+d -> %d (%s) reason=%s",
            npc_id, delta, new_value, new_state, reason,
        )
    return _row_to_mood(row)


# — Mental-Break-Verhalten-Hooks ——————————————————————————————————————————————
# Diese werden vom npc_worker.wander_loop aufgerufen, um das Mental-Break-
# Verhalten in die normalen NPC-Ticks zu integrieren. Sie akzeptieren das
# NPC-Dict (wie es NPCManager.all()/get() liefert) und sind synchron.

def _mental_state(npc: dict) -> str:
    """Defensiv: ältere NPC-Dicts haben evtl. noch keine mental_state-Spalte
    geladen. Default = 'normal'."""
    return npc.get("mental_state") or "normal"


def should_attack_player(npc: dict) -> bool:
    """True, wenn ein normalerweise friedlicher NPC im Berserk-Zustand ist und
    daher den Spieler angreifen sollte.

    Für creature/boss kinds wird hier False zurückgegeben — die haben ohnehin
    ihr eigenes Aggro-Verhalten in combat/npc_worker."""
    if _mental_state(npc) != "berserk":
        return False
    return npc.get("kind") in FRIENDLY_KINDS


def should_flee_player(npc: dict) -> bool:
    """True, wenn NPC fliehen sollte (vom Spieler weg bewegen)."""
    return _mental_state(npc) == "fleeing"


def should_skip_action(npc: dict) -> bool:
    """True, wenn NPC zu deprimiert ist um zu handeln (steht rum)."""
    return _mental_state(npc) == "sad"


# — Worker ————————————————————————————————————————————————————————————————————

async def _broadcast_mood(connection_manager, npc_id: int, mood: dict) -> None:
    """Broadcasted einen mood-Update an alle verbundenen Clients."""
    try:
        await connection_manager.broadcast({
            "type":         "npc_mood",
            "npc_id":       npc_id,
            "mood_value":   mood["mood_value"],
            "mental_state": mood["mental_state"],
        })
    except Exception:
        log.debug("broadcast npc_mood (id=%s) fehlgeschlagen", npc_id, exc_info=True)


async def run(npc_manager, connection_manager) -> None:
    """Hintergrund-Loop: normalisiert mood_value langsam Richtung 50 für alle
    NPCs. Bei jedem Übergang in einen anderen mental_state wird ein
    `npc_mood`-Event gebroadcastet.
    """
    log.info("NPC-Mood-Worker startet (tick=%ds)", MOOD_DECAY_TICK_SECONDS)
    while True:
        try:
            await asyncio.sleep(MOOD_DECAY_TICK_SECONDS)

            # Snapshot der NPC-IDs (NPCManager.all() könnte sich während des
            # Loops ändern, z.B. durch damage/Tod).
            npcs = list(npc_manager.all())
            if not npcs:
                continue

            for npc in npcs:
                npc_id = npc["id"]

                # Frischen Wert aus der DB lesen, damit parallele adjust_mood-
                # Calls (z.B. durch Combat) nicht überschrieben werden.
                row = await db.pool().fetchrow(
                    "SELECT mood_value, mental_state FROM npcs WHERE id = $1",
                    npc_id,
                )
                if row is None:
                    continue

                current_value = int(row["mood_value"])
                current_state = row["mental_state"] or "normal"

                if current_value == MOOD_NEUTRAL:
                    continue

                # Richtung 50 bewegen
                if current_value > MOOD_NEUTRAL:
                    new_value = max(MOOD_NEUTRAL, current_value - MOOD_RECOVER_PER_TICK)
                else:
                    new_value = min(MOOD_NEUTRAL, current_value + MOOD_RECOVER_PER_TICK)

                new_state = compute_mental_state(new_value)

                updated = await db.pool().fetchrow(
                    "UPDATE npcs SET mood_value = $2, mental_state = $3 "
                    "WHERE id = $1 "
                    "RETURNING mood_value, mental_state",
                    npc_id, new_value, new_state,
                )
                if updated is None:
                    continue

                # In-Memory-Cache vom NPCManager synchron halten (falls Felder
                # dort gespiegelt werden — defensive Zuweisung).
                cached = npc_manager.get(npc_id)
                if cached is not None:
                    cached["mood_value"] = new_value
                    cached["mental_state"] = new_state

                # Bei State-Change broadcasten
                if new_state != current_state:
                    log.info(
                        "NPC %s (%s) wechselt mental_state %s -> %s (mood=%d)",
                        npc_id, npc.get("kind"), current_state, new_state, new_value,
                    )
                    await _broadcast_mood(
                        connection_manager,
                        npc_id,
                        {"mood_value": new_value, "mental_state": new_state},
                    )

        except asyncio.CancelledError:
            log.info("NPC-Mood-Worker gestoppt")
            raise
        except Exception:
            log.exception("NPC-Mood-Worker-Iteration fehlgeschlagen")
