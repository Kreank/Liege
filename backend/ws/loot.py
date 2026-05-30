"""Loot-Handler (Phase B8): loot_vote, set_loot_rule.

Behält 1:1 das Verhalten aus dem Legacy-Block in main.py:
- loot_vote: loot_rolls.vote, bei Fehler `loot_vote_error`.
- set_loot_rule: groups.set_loot_rule, broadcasted `loot_rule_changed`.

Die `loot_roll_voted`/`loot_roll_resolved`-Broadcasts kommen aus
loot_rolls.vote()-Side-Effects, nicht hier.
"""
from __future__ import annotations

import groups
import loot_rolls

from .context import WsContext
from .dispatcher import register


async def handle_loot_vote(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    roll_id = int(data.get("roll_id", 0))
    vote_kind = (data.get("vote") or "").strip().lower()
    res = await loot_rolls.vote(roll_id, player_id, vote_kind)
    if not res.get("ok"):
        await websocket.send_json({"type": "loot_vote_error",
                                    "reason": res["reason"]})


async def handle_set_loot_rule(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    rule = (data.get("rule") or "").strip().lower()
    g = await groups.get_group_for(player_id)
    if not g:
        await websocket.send_json({"type": "group_error",
                                    "reason": "not_in_group"})
        return
    res = await groups.set_loot_rule(g["id"], player_id, rule)
    if not res.get("ok"):
        await websocket.send_json({"type": "group_error",
                                    "reason": res["reason"]})
        return
    await groups.broadcast_to_group(manager, g["id"], {
        "type": "loot_rule_changed",
        "rule": res["rule"],
    })


register("loot_vote", handle_loot_vote)
register("set_loot_rule", handle_set_loot_rule)
