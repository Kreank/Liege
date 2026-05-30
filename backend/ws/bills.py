"""Bills-Handler (Phase B4): add_bill, remove_bill, list_bills.

Behält 1:1 das Verhalten aus dem Legacy-Block in main.py:
- add_bill: Research-Gate via recipes.find_recipe → research.is_node_done.
- remove_bill: bill_id + player_id.
- list_bills: optional station_type-Filter.
Alle drei senden `bills_update` zurück.
"""
from __future__ import annotations

import bill_queue
import recipes
import research

from .context import WsContext
from .dispatcher import register


async def handle_add_bill(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    station_type = data.get("station_type", "")
    recipe_id = data.get("recipe_id", "")
    count = max(1, min(99, int(data.get("count", 1))))
    # Welle 22: Research-Gate auch hier
    _recipe = recipes.find_recipe(station_type, recipe_id)
    _req = _recipe.get("requires") if _recipe else None
    if _req and not await research.is_node_done(player_id, _req):
        node_name = research.RESEARCH_NODES.get(_req, {}).get("name", _req)
        await websocket.send_json({
            "type": "toast",
            "text": f"🔒 Erst forschen: {node_name}",
        })
        return
    await bill_queue.add_bill(player_id, station_type, recipe_id, count)
    bills_now = await bill_queue.list_bills(player_id)
    await websocket.send_json({"type": "bills_update", "bills": bills_now})


async def handle_remove_bill(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    bill_id = int(data.get("bill_id", 0))
    await bill_queue.remove_bill(bill_id, player_id)
    bills_now = await bill_queue.list_bills(player_id)
    await websocket.send_json({"type": "bills_update", "bills": bills_now})


async def handle_list_bills(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    bills_now = await bill_queue.list_bills(player_id, data.get("station_type"))
    await websocket.send_json({"type": "bills_update", "bills": bills_now})


register("add_bill", handle_add_bill)
register("remove_bill", handle_remove_bill)
register("list_bills", handle_list_bills)
