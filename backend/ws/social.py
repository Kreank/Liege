"""Social/Groups-Handler (Phase B14): chat, group_create_party,
group_invite, group_accept, group_decline, group_leave, group_kick,
group_promote, group_transfer_leader, group_disband, group_refresh,
group_chat, group_convert_to_raid.

Behält 1:1 das Verhalten aus den Legacy-Blocks in main.py.
Nutzt durchgehend groups.*-Service-Funktionen statt der alten
main.py-Wrapper.
"""
from __future__ import annotations

import logging

import groups

from .context import WsContext
from .dispatcher import register


async def handle_chat(ctx: WsContext, data: dict) -> None:
    player_id = ctx.player_id
    manager = ctx.manager
    text = (data.get("text") or "").strip()
    if text and len(text) <= 500:
        await manager.broadcast({
            "type": "chat",
            "from": player_id,
            "text": text,
        })


async def handle_group_create_party(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    try:
        await groups.create_party(player_id)
        await groups.push_group_state(manager, player_id)
    except ValueError as e:
        await websocket.send_json({"type": "group_error",
                                    "reason": str(e)})


async def handle_group_invite(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    target = (data.get("target") or "").strip()
    if not target:
        return
    g = await groups.get_group_for(player_id)
    if not g:
        # kein Solo-Invite — implizit Party erstellen
        try:
            g_new = await groups.create_party(player_id)
            gid = g_new["id"]
            await groups.push_group_state(manager, player_id)
        except ValueError:
            await websocket.send_json({"type": "group_error",
                                        "reason": "already_in_group"})
            return
    else:
        gid = g["id"]
    res = await groups.invite(gid, player_id, target)
    if not res.get("ok"):
        await websocket.send_json({"type": "group_error",
                                    "reason": res["reason"]})
        return
    # Inviter bestätigen
    await websocket.send_json({
        "type": "group_invite_sent",
        "target": target,
        "expires_at": res["expires_at"].isoformat(),
    })
    # Target benachrichtigen (falls online)
    tws = manager.connections.get(target)
    if tws is not None:
        gg = await groups.get_group(gid)
        try:
            await tws.send_json({
                "type": "group_invite_received",
                "invite_id": res["invite_id"],
                "group_id": gid,
                "from": player_id,
                "kind": gg["kind"] if gg else "party",
                "expires_at": res["expires_at"].isoformat(),
            })
        except Exception:
            pass


async def handle_group_accept(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    invite_id = int(data.get("invite_id") or 0)
    if not invite_id:
        return
    res = await groups.accept_invite(invite_id, player_id)
    if not res.get("ok"):
        await websocket.send_json({"type": "group_error",
                                    "reason": res["reason"]})
        return
    await groups.push_group_state_to_all_members(manager, res["group_id"])


async def handle_group_decline(ctx: WsContext, data: dict) -> None:
    player_id = ctx.player_id
    invite_id = int(data.get("invite_id") or 0)
    if invite_id:
        await groups.decline_invite(invite_id, player_id)


async def handle_group_leave(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    res = await groups.leave(player_id)
    if not res.get("ok"):
        await websocket.send_json({"type": "group_error",
                                    "reason": res["reason"]})
        return
    # Spieler selbst: leer-state
    await groups.push_group_state(manager, player_id)
    if not res["disbanded"]:
        # Restmitglieder benachrichtigen
        await groups.broadcast_to_group(manager, res["group_id"], {
            "type": "group_member_left",
            "player_name": player_id,
            "new_leader": res.get("new_leader"),
        })
        await groups.push_group_state_to_all_members(manager, res["group_id"])


async def handle_group_kick(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    target = (data.get("target") or "").strip()
    g = await groups.get_group_for(player_id)
    if not g or not target:
        return
    res = await groups.kick(g["id"], player_id, target)
    if not res.get("ok"):
        await websocket.send_json({"type": "group_error",
                                    "reason": res["reason"]})
        return
    # Gekickter Spieler: Snapshot wird leer
    await groups.push_group_state(manager, target)
    tws = manager.connections.get(target)
    if tws is not None:
        try:
            await tws.send_json({"type": "group_kicked",
                                  "by": player_id})
        except Exception:
            pass
    await groups.push_group_state_to_all_members(manager, g["id"])


async def handle_group_promote(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    target = (data.get("target") or "").strip()
    g = await groups.get_group_for(player_id)
    if not g or not target:
        return
    res = await groups.promote(g["id"], player_id, target)
    if not res.get("ok"):
        await websocket.send_json({"type": "group_error",
                                    "reason": res["reason"]})
        return
    await groups.push_group_state_to_all_members(manager, g["id"])


async def handle_group_transfer_leader(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    target = (data.get("target") or "").strip()
    g = await groups.get_group_for(player_id)
    if not g or not target:
        return
    res = await groups.transfer_leader(g["id"], player_id, target)
    if not res.get("ok"):
        await websocket.send_json({"type": "group_error",
                                    "reason": res["reason"]})
        return
    await groups.push_group_state_to_all_members(manager, g["id"])


async def handle_group_disband(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    g = await groups.get_group_for(player_id)
    if not g:
        return
    # Mitgliederliste VOR dem Disband holen, sonst kein Broadcast möglich
    member_names = await groups.get_member_names(g["id"])
    ok = await groups.disband(g["id"], player_id)
    if not ok:
        await websocket.send_json({"type": "group_error",
                                    "reason": "no_permission"})
        return
    for pid in member_names:
        ws_m = manager.connections.get(pid)
        if ws_m is None:
            continue
        try:
            await ws_m.send_json({"type": "group_disbanded",
                                  "group_id": g["id"],
                                  "by": player_id})
            await ws_m.send_json({"type": "group_state",
                                  "group": None})
        except Exception:
            pass


async def handle_group_refresh(ctx: WsContext, data: dict) -> None:
    player_id = ctx.player_id
    manager = ctx.manager
    await groups.push_group_state(manager, player_id)


async def handle_group_chat(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    text = (data.get("text") or "").strip()
    if not text or len(text) > 500:
        return
    g = await groups.get_group_for(player_id)
    if not g:
        await websocket.send_json({"type": "group_error",
                                    "reason": "not_in_group"})
        return
    await groups.broadcast_to_group(manager, g["id"], {
        "type": "group_chat",
        "from": player_id,
        "text": text,
        "kind": g["kind"],
    })


async def handle_group_convert_to_raid(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    new_kind = (data.get("kind") or "raid_small").strip()
    g = await groups.get_group_for(player_id)
    if not g:
        await websocket.send_json({"type": "group_error",
                                    "reason": "not_in_group"})
        return
    res = await groups.convert_to_raid(g["id"], player_id, new_kind)
    if not res.get("ok"):
        await websocket.send_json({"type": "group_error",
                                    "reason": res["reason"]})
        return
    await groups.broadcast_to_group(manager, g["id"], {
        "type": "group_converted",
        "from_kind": res["from_kind"],
        "to_kind": res["to_kind"],
    })
    await groups.push_group_state_to_all_members(manager, g["id"])


register("chat", handle_chat)
register("group_create_party", handle_group_create_party)
register("group_invite", handle_group_invite)
register("group_accept", handle_group_accept)
register("group_decline", handle_group_decline)
register("group_leave", handle_group_leave)
register("group_kick", handle_group_kick)
register("group_promote", handle_group_promote)
register("group_transfer_leader", handle_group_transfer_leader)
register("group_disband", handle_group_disband)
register("group_refresh", handle_group_refresh)
register("group_chat", handle_group_chat)
register("group_convert_to_raid", handle_group_convert_to_raid)
