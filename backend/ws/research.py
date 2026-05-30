"""Research-Handler (Phase B5): invest_research.

Behält 1:1 das Verhalten aus dem Legacy-Block in main.py:
- points werden auf [1,10] geclamped.
- Bei abgeschlossener Node zusätzlich Toast.
"""
from __future__ import annotations

import research

from .context import WsContext
from .dispatcher import register


async def handle_invest_research(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    node_id = data.get("node_id", "")
    points = max(1, min(10, int(data.get("points", 1))))
    result = await research.invest(player_id, node_id, points)
    if result is not None:
        await websocket.send_json({"type": "research_update", **result})
        if result["done"]:
            await websocket.send_json({
                "type": "toast",
                "text": f"🔬 Forschung abgeschlossen: {research.RESEARCH_NODES[node_id]['name']}",
            })


register("invest_research", handle_invest_research)
