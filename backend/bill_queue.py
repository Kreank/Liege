"""Bill-Queue-System für Crafting (RimWorld-inspiriert).

Ein "Bill" ist ein dauerhafter Auftrag wie "Mache 10× Schwert solange Material da ist".
Spieler queueen Bills pro Station, der Worker arbeitet sie nacheinander ab — EIN
Craft pro Tick (BILL_TICK_SECONDS). Das ursprüngliche per-Klick-Crafting bleibt
unangetastet; Bills laufen parallel im Hintergrund.

WS-Messages:
  - eingehend (Frontend → Backend, in main.py zu handlen):
      add_bill    {station_type, recipe_id, count}
      list_bills  {station_type?}     → antwortet mit bills_update
      remove_bill {bill_id}
  - ausgehend (Backend → Frontend):
      bills_update    {bills: [...]}                  (snapshot nach add/remove/list)
      bill_progress   {bill_id, completed, target, item}
      bill_done       {bill_id, recipe_id}
      bill_blocked    {bill_id, recipe_id, reason}    (z.B. fehlende Inputs — Hint)
"""
import asyncio
import logging
import os

import db

log = logging.getLogger("liege.bill_queue")

BILL_TICK_SECONDS = int(os.environ.get("BILL_TICK_SECONDS", "8"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
    id           BIGSERIAL PRIMARY KEY,
    player_name  TEXT NOT NULL,
    station_type TEXT NOT NULL,
    recipe_id    TEXT NOT NULL,
    target_count INTEGER NOT NULL,
    completed    INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS bills_player_idx ON bills (player_name, status);
"""


def _row_to_dict(row) -> dict:
    return {
        "id":           row["id"],
        "player_name":  row["player_name"],
        "station_type": row["station_type"],
        "recipe_id":    row["recipe_id"],
        "target_count": row["target_count"],
        "completed":    row["completed"],
        "status":       row["status"],
        "created_at":   row["created_at"].isoformat(),
    }


# — CRUD ————————————————————————————————————————————————————————————————————————

async def add_bill(player_name: str, station_type: str, recipe_id: str,
                   count: int) -> dict:
    """Legt neue Bill an. count wird auf >=1 geklemmt."""
    target = max(1, int(count))
    row = await db.pool().fetchrow(
        "INSERT INTO bills (player_name, station_type, recipe_id, target_count) "
        "VALUES ($1, $2, $3, $4) "
        "RETURNING id, player_name, station_type, recipe_id, target_count, "
        "completed, status, created_at",
        player_name, station_type, recipe_id, target,
    )
    return _row_to_dict(row)


async def list_bills(player_name: str, station_type: str | None = None) -> list[dict]:
    """Alle offenen Bills (status != 'done') eines Spielers, optional pro Station."""
    if station_type is None:
        rows = await db.pool().fetch(
            "SELECT id, player_name, station_type, recipe_id, target_count, "
            "completed, status, created_at "
            "FROM bills WHERE player_name = $1 AND status <> 'done' "
            "ORDER BY id",
            player_name,
        )
    else:
        rows = await db.pool().fetch(
            "SELECT id, player_name, station_type, recipe_id, target_count, "
            "completed, status, created_at "
            "FROM bills WHERE player_name = $1 AND station_type = $2 "
            "AND status <> 'done' ORDER BY id",
            player_name, station_type,
        )
    return [_row_to_dict(r) for r in rows]


async def remove_bill(bill_id: int, player_name: str) -> bool:
    """Löscht Bill, nur wenn dem Spieler gehört. Returns True bei Erfolg."""
    row = await db.pool().fetchrow(
        "DELETE FROM bills WHERE id = $1 AND player_name = $2 RETURNING id",
        bill_id, player_name,
    )
    return row is not None


async def get_next_pending(player_name: str) -> dict | None:
    """Nächste noch nicht fertige Bill (status in pending/active) für den Spieler."""
    row = await db.pool().fetchrow(
        "SELECT id, player_name, station_type, recipe_id, target_count, "
        "completed, status, created_at "
        "FROM bills WHERE player_name = $1 AND status IN ('pending', 'active') "
        "ORDER BY id LIMIT 1",
        player_name,
    )
    return _row_to_dict(row) if row else None


async def mark_progress(bill_id: int, completed_count: int) -> None:
    """Setzt completed und status='active'."""
    await db.pool().execute(
        "UPDATE bills SET completed = $2, status = 'active' WHERE id = $1",
        bill_id, completed_count,
    )


async def mark_done(bill_id: int) -> None:
    await db.pool().execute(
        "UPDATE bills SET status = 'done' WHERE id = $1", bill_id,
    )


# — Crafting-Hilfe ——————————————————————————————————————————————————————————————

def recipe_inputs_available(counts: dict[str, int], recipe: dict) -> bool:
    """Prüft, ob alle Input-Stacks im counts-Dict ausreichen.

    counts: Result von items_module.count_owned_by_kind(player_name).
    """
    for kind, need in recipe.get("inputs", []):
        if counts.get(kind, 0) < need:
            return False
    return True


async def _send(connection_manager, player_name: str, message: dict) -> None:
    ws = connection_manager.connections.get(player_name)
    if ws is None:
        return
    try:
        await ws.send_json(message)
    except Exception:
        log.debug("bill-WS-send an %s fehlgeschlagen", player_name, exc_info=True)


async def _process_player(player_name: str, connection_manager,
                          items_module, recipes_module) -> None:
    """Ein Tick für EINEN Spieler: max. 1 Craft."""
    bill = await get_next_pending(player_name)
    if bill is None:
        return

    recipe = recipes_module.find_recipe(bill["station_type"], bill["recipe_id"])
    if recipe is None:
        log.warning("Bill %d hat unbekanntes Rezept %s/%s — markiere failed",
                    bill["id"], bill["station_type"], bill["recipe_id"])
        await db.pool().execute(
            "UPDATE bills SET status = 'failed' WHERE id = $1", bill["id"]
        )
        await _send(connection_manager, player_name, {
            "type": "bill_blocked", "bill_id": bill["id"],
            "recipe_id": bill["recipe_id"], "reason": "unknown_recipe",
        })
        return

    counts = await items_module.count_owned_by_kind(player_name)
    if not recipe_inputs_available(counts, recipe):
        await _send(connection_manager, player_name, {
            "type": "bill_blocked", "bill_id": bill["id"],
            "recipe_id": bill["recipe_id"], "reason": "missing_inputs",
        })
        return

    # Inputs consumen
    for kind, need in recipe["inputs"]:
        for _ in range(need):
            ok = await items_module.consume_one(player_name, kind)
            if not ok:
                # Race: jemand hat zwischen Check und Consume Item entfernt.
                # Wir brechen ab und hoffen auf nächsten Tick.
                log.info("Bill %d: consume_one(%s) schlug fehl trotz vorheriger Prüfung",
                         bill["id"], kind)
                await _send(connection_manager, player_name, {
                    "type": "bill_blocked", "bill_id": bill["id"],
                    "recipe_id": bill["recipe_id"], "reason": "missing_inputs",
                })
                return

    created = await items_module.create_for_player(recipe["output"], player_name)
    if created is None:
        log.warning("Bill %d: create_for_player(%s) gab None",
                    bill["id"], recipe["output"])
        return

    new_completed = bill["completed"] + 1
    await mark_progress(bill["id"], new_completed)

    await _send(connection_manager, player_name, {
        "type":      "bill_progress",
        "bill_id":   bill["id"],
        "completed": new_completed,
        "target":    bill["target_count"],
        "item":      created,
    })

    if new_completed >= bill["target_count"]:
        await mark_done(bill["id"])
        await _send(connection_manager, player_name, {
            "type": "bill_done",
            "bill_id": bill["id"],
            "recipe_id": bill["recipe_id"],
        })
        log.info("Bill %d (%s ×%d) für %s abgeschlossen",
                 bill["id"], bill["recipe_id"], bill["target_count"], player_name)


async def run(connection_manager, items_module, recipes_module) -> None:
    """Bill-Worker — pro Tick max. 1 Craft pro Spieler."""
    log.info("Bill-Worker startet (tick=%ds)", BILL_TICK_SECONDS)
    while True:
        try:
            await asyncio.sleep(BILL_TICK_SECONDS)
            players = list(connection_manager.get_players().keys())
            for player_name in players:
                try:
                    await _process_player(
                        player_name, connection_manager,
                        items_module, recipes_module,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("Bill-Worker: Spieler %s schlug fehl", player_name)
        except asyncio.CancelledError:
            log.info("Bill-Worker gestoppt")
            raise
        except Exception:
            log.exception("Bill-Worker-Iteration fehlgeschlagen")
