"""Raid/Dev-Handler (Phase B9): raid_trigger_manual, dev_world_repopulate,
dev_trigger_event, force_respawn.

Behält 1:1 das Verhalten aus dem Legacy-Block in main.py:
- raid_trigger_manual: Group-Check, Leader-Check, raid_director.trigger_manual_raid,
  Broadcast `raid_started` an Gruppe.
- dev_world_repopulate: Admin-only, world_populator.reset_chunks_without_player_structures.
- dev_trigger_event: Admin-only, event_worker._apply_event_effect.
- force_respawn: bei Downed-State → services.player_state.do_respawn.
"""
from __future__ import annotations

import logging

import event_worker
import groups
import needs
import raid_director
import world_populator
from services.player_state import (
    do_respawn as do_respawn_svc,
    is_downed,
)

from .context import WsContext
from .dispatcher import register


async def handle_raid_trigger_manual(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    npcs = ctx.npcs
    events = ctx.events

    tier = int(data.get("tier", 1))
    g = await groups.get_group_for(player_id)
    if not g:
        await websocket.send_json({"type": "group_error",
                                    "reason": "not_in_group"})
        return
    # Nur Leader darf manuelle Raids triggern
    if g["leader"] != player_id:
        await websocket.send_json({"type": "group_error",
                                    "reason": "leader_only"})
        return
    res = await raid_director.trigger_manual_raid(
        player_id, tier, world, npcs, manager, events,
    )
    if not res.get("ok"):
        await websocket.send_json({"type": "raid_error",
                                    "reason": res["reason"],
                                    "remaining_s": res.get("remaining_s", 0)})
        return
    await groups.broadcast_to_group(manager, g["id"], {
        "type": "raid_started",
        "tier": res["tier"],
        "label": res["label"],
        "spawned": res["spawned"],
        "by": player_id,
    })


async def handle_dev_world_repopulate(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    user = ctx.user or {}
    world = ctx.world
    # Admin-only: setzt populated=false für leere Chunks, löscht
    # System-Strukturen darin. Beim nächsten Betreten neu gespawnt.
    if user.get("role") != "admin":
        await websocket.send_json({"type": "toast",
                                    "text": "⛔ Admin only"})
        return
    count = await world_populator.reset_chunks_without_player_structures(world)
    await websocket.send_json({"type": "toast",
                                "text": f"♻️ {count} Chunks zurückgesetzt"})


async def handle_dev_trigger_event(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    user = ctx.user or {}
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    npcs = ctx.npcs
    # Admin-only: feuert sofort einen Event-Effekt (zum Testen von
    # Disastern etc.). data.effect = z.B. "thunderstorm", "toxic_fog".
    if user.get("role") != "admin":
        await websocket.send_json({"type": "toast", "text": "⛔ Admin only"})
        return
    eff = (data.get("effect") or "").strip()
    if not eff:
        await websocket.send_json({"type": "toast", "text": "effect fehlt"})
        return
    try:
        await event_worker._apply_event_effect(
            {"effect": eff}, {}, world, npcs, structures, manager)
        await websocket.send_json({"type": "toast",
                                    "text": f"🧪 Event ausgelöst: {eff}"})
    except Exception as _e:
        logging.exception("dev_trigger_event fehlgeschlagen")
        await websocket.send_json({"type": "toast",
                                    "text": f"Fehler: {_e}"})


async def handle_force_respawn(ctx: WsContext, data: dict) -> None:
    # Welle 25: force_respawn — Sofort-Respawn aus dem Down-State
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    if is_downed(player_id):
        await do_respawn_svc(manager, world, structures, player_id, in_place=False)


register("raid_trigger_manual", handle_raid_trigger_manual)
register("dev_world_repopulate", handle_dev_world_repopulate)
register("dev_trigger_event", handle_dev_trigger_event)
register("force_respawn", handle_force_respawn)
