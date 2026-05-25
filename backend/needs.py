import asyncio
import logging
import os
from typing import Awaitable, Callable

import db

log = logging.getLogger("liege.needs")

# — DB-Schema-Ergänzungen ———————————————————————————————————————————————————————
# In db.py beim Init ausführen (idempotent via IF NOT EXISTS).
SCHEMA_ALTERS: tuple[str, ...] = (
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS hunger INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS max_hunger INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS stamina INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS max_stamina INTEGER NOT NULL DEFAULT 100",
)

# — Tuning-Konstanten —————————————————————————————————————————————————————————
HUNGER_TICK_SECONDS: int = int(os.environ.get("HUNGER_TICK_SECONDS", "30"))
HUNGER_STARVE_HP_DAMAGE: int = 2
STAMINA_REGEN_PER_TICK: int = 5
SLEEP_STAMINA_RESTORE: int = 100

# Welche Items füllen Hunger auf (0 oder Abwesenheit => kein Food)
FOOD_RESTORE: dict[str, int] = {
    "herb": 8,
    "health_potion": 30,
    "mana_potion": 20,
    # Echte Foods
    "apple":         15,
    "berries":       12,
    "wheat":         8,
    "bread":         40,    # verarbeitet, sehr sättigend
    "raw_meat":      18,    # rohes Fleisch
    "cooked_meat":   45,    # gegart noch sättigender
    "fish":          25,
    "mushroom_food": 20,
    "food_ration":   35,    # Proviant — gut sättigend, lange haltbar
    "wood": 0,
    "stone": 0,
    "iron_ore": 0,
    "bone": 0,
}


# — Helper für use_item-Integration ——————————————————————————————————————————

def is_food(kind: str) -> bool:
    """True wenn das Item-Kind Hunger auffüllt (Wert > 0)."""
    return FOOD_RESTORE.get(kind, 0) > 0


def food_value(kind: str) -> int:
    """Wieviel Hunger füllt dieses Item auf? 0 wenn unbekannt/kein Food."""
    return FOOD_RESTORE.get(kind, 0)


# — DB-Queries ————————————————————————————————————————————————————————————————

def _row_to_needs(row) -> dict:
    return {
        "hunger":      row["hunger"],
        "max_hunger":  row["max_hunger"],
        "stamina":     row["stamina"],
        "max_stamina": row["max_stamina"],
    }


async def get_needs(player_name: str) -> dict | None:
    row = await db.pool().fetchrow(
        "SELECT hunger, max_hunger, stamina, max_stamina "
        "FROM players WHERE name = $1",
        player_name,
    )
    return _row_to_needs(row) if row else None


async def restore_hunger(player_name: str, amount: int) -> dict | None:
    """Füllt Hunger auf bis max. Returns neuen State, oder None wenn Spieler
    nicht existiert oder Hunger bereits voll war."""
    if amount <= 0:
        return None
    row = await db.pool().fetchrow(
        "UPDATE players "
        "SET hunger = LEAST(max_hunger, hunger + $2) "
        "WHERE name = $1 AND hunger < max_hunger "
        "RETURNING hunger, max_hunger, stamina, max_stamina",
        player_name, amount,
    )
    return _row_to_needs(row) if row else None


async def restore_stamina(player_name: str, amount: int) -> dict | None:
    """Füllt Stamina auf bis max. Returns neuen State, oder None wenn Spieler
    nicht existiert oder Stamina bereits voll war."""
    if amount <= 0:
        return None
    row = await db.pool().fetchrow(
        "UPDATE players "
        "SET stamina = LEAST(max_stamina, stamina + $2) "
        "WHERE name = $1 AND stamina < max_stamina "
        "RETURNING hunger, max_hunger, stamina, max_stamina",
        player_name, amount,
    )
    return _row_to_needs(row) if row else None


async def use_stamina(player_name: str, amount: int) -> bool:
    """Versucht Stamina abzuziehen. Returns True bei Erfolg, False wenn nicht
    genug verfügbar oder Spieler nicht existiert."""
    if amount <= 0:
        return True
    row = await db.pool().fetchrow(
        "UPDATE players SET stamina = stamina - $2 "
        "WHERE name = $1 AND stamina >= $2 "
        "RETURNING stamina",
        player_name, amount,
    )
    return row is not None


# — Worker ————————————————————————————————————————————————————————————————————

DamagePlayerCb = Callable[[str, int], Awaitable[None]]


async def _send_needs(connection_manager, player_name: str, needs: dict) -> None:
    """Schickt den aktuellen Needs-State nur an den jeweiligen Spieler."""
    ws = connection_manager.connections.get(player_name)
    if ws is None:
        return
    try:
        await ws.send_json({
            "type":        "player_needs",
            "hunger":      needs["hunger"],
            "max_hunger":  needs["max_hunger"],
            "stamina":     needs["stamina"],
            "max_stamina": needs["max_stamina"],
        })
    except Exception:
        log.debug("send_needs an %s fehlgeschlagen", player_name, exc_info=True)


async def run(connection_manager, damage_player_cb: DamagePlayerCb) -> None:
    """Hintergrund-Loop: tickt Hunger runter und regeneriert Stamina für alle
    aktiv verbundenen Spieler."""
    log.info("Needs-Worker startet (tick=%ds)", HUNGER_TICK_SECONDS)
    while True:
        try:
            await asyncio.sleep(HUNGER_TICK_SECONDS)

            # Snapshot der aktuell verbundenen Spielernamen
            player_names = list(connection_manager.get_players().keys())
            if not player_names:
                continue

            for name in player_names:
                # 1) Hunger -1 (clamp >= 0) und Stamina-Regen (clamp <= max)
                row = await db.pool().fetchrow(
                    "UPDATE players "
                    "SET hunger  = GREATEST(0, hunger - 1), "
                    "    stamina = LEAST(max_stamina, stamina + $2) "
                    "WHERE name = $1 "
                    "RETURNING hunger, max_hunger, stamina, max_stamina",
                    name, STAMINA_REGEN_PER_TICK,
                )
                if row is None:
                    continue

                needs = _row_to_needs(row)

                # 2) Starvation-Damage bei Hunger == 0
                if needs["hunger"] == 0:
                    try:
                        await damage_player_cb(name, HUNGER_STARVE_HP_DAMAGE)
                    except Exception:
                        log.exception("Starve-Damage fehlgeschlagen für %s", name)

                # 3) WS-Update an diesen Spieler
                await _send_needs(connection_manager, name, needs)

        except asyncio.CancelledError:
            log.info("Needs-Worker gestoppt")
            raise
        except Exception:
            log.exception("Needs-Worker-Iteration fehlgeschlagen")
