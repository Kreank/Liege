"""Welle 53 — Quest-Tick-Worker für zeit-/positions-/distanz-basierte Quests:

  • defend  — Stellung N Sekunden im Radius um den Annahme-Ort halten.
  • escort  — einen folgenden NPC `distance_min` Tiles weit begleiten.

Die übrigen Quest-Typen sind event-getrieben (on_creature_killed,
on_item_collected, on_npc_talked_to, on_location_visited) und brauchen keinen
Tick. Der Worker läuft alle QUEST_TICK_SECONDS und meldet Fortschritt/Abschluss
über `quest_progress` (gleiches Frame wie die event-getriebenen Hooks).
"""
import asyncio
import json
import logging

import db
import npc_worker

log = logging.getLogger("liege.quest_worker")

QUEST_TICK_SECONDS = 3


def _parse(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return v or {}


async def _send(manager, player_name: str, payload: dict) -> None:
    ws = manager.connections.get(player_name)
    if ws is not None:
        try:
            await ws.send_json(payload)
        except Exception:
            pass


def _quest_payload(r, prog: dict, status: str) -> dict:
    return {
        "id":          r["id"],
        "quest_id":    r["id"],
        "player_name": r["player_name"],
        "quest_type":  r["quest_type"],
        "title":       r["title"],
        "objective":   _parse(r["objective"]),
        "progress":    prog,
        "reward":      _parse(r["reward"]),
        "status":      status,
    }


async def run(manager, npc_manager, world, structures_mgr=None) -> None:
    log.info("Quest-Tick-Worker startet (tick=%ds)", QUEST_TICK_SECONDS)
    await asyncio.sleep(15)
    while True:
        try:
            await asyncio.sleep(QUEST_TICK_SECONDS)
            players = manager.get_players()
            if not players:
                continue
            rows = await db.pool().fetch(
                "SELECT id, player_name, quest_type, objective, progress, title, reward "
                "FROM quests WHERE status = 'active' "
                "AND quest_type IN ('defend','escort') "
                "AND player_name = ANY($1::text[])",
                list(players.keys()),
            )
            for r in rows:
                pdata = players.get(r["player_name"])
                if pdata is None:
                    continue
                try:
                    if r["quest_type"] == "defend":
                        await _tick_defend(manager, r, pdata)
                    else:
                        await _tick_escort(manager, npc_manager, world,
                                           structures_mgr, r, pdata)
                except Exception:
                    log.exception("Quest-Tick für Quest %s fehlgeschlagen", r["id"])
        except asyncio.CancelledError:
            log.info("Quest-Tick-Worker gestoppt")
            raise
        except Exception:
            log.exception("Quest-Tick-Iteration fehlgeschlagen")


async def _tick_defend(manager, r, pdata) -> None:
    obj = _parse(r["objective"])
    prog = _parse(r["progress"])
    radius = int(obj.get("radius", 5))
    duration = int(obj.get("duration_s", 60))
    # Anker = Position bei der ersten Verarbeitung (Annahme-Ort).
    if prog.get("anchor_x") is None:
        prog["anchor_x"], prog["anchor_y"] = pdata["x"], pdata["y"]
        prog["elapsed_s"] = 0
    ax, ay = prog["anchor_x"], prog["anchor_y"]
    dist = max(abs(pdata["x"] - ax), abs(pdata["y"] - ay))
    if dist <= radius:
        prog["elapsed_s"] = int(prog.get("elapsed_s", 0)) + QUEST_TICK_SECONDS
    else:
        prog["elapsed_s"] = 0   # Stellung verlassen → Timer zurück auf 0
    done = prog["elapsed_s"] >= duration
    status = "completed" if done else "active"
    await db.pool().execute(
        "UPDATE quests SET progress = $2, status = $3 WHERE id = $1",
        r["id"], json.dumps(prog), status,
    )
    await _send(manager, r["player_name"],
                {"type": "quest_progress", "quest": _quest_payload(r, prog, status)})
    if done:
        await _send(manager, r["player_name"],
                    {"type": "toast",
                     "text": f"✅ Stellung gehalten — '{r['title']}' abgeschlossen!"})


async def _tick_escort(manager, npc_manager, world, structures_mgr, r, pdata) -> None:
    obj = _parse(r["objective"])
    prog = _parse(r["progress"])
    dist_min = int(obj.get("distance_min", 20))
    if prog.get("anchor_x") is None:
        prog["anchor_x"], prog["anchor_y"] = pdata["x"], pdata["y"]
    npc_id = prog.get("escort_npc_id")
    escort = npc_manager.get(npc_id) if npc_id else None

    # Schützling verloren (despawnt/getötet) → Quest gescheitert.
    if npc_id and escort is None:
        npc_worker.ESCORT_NPCS.discard(npc_id)
        await db.pool().execute("UPDATE quests SET status = 'failed' WHERE id = $1", r["id"])
        await _send(manager, r["player_name"], {"type": "quest_failed", "quest_id": r["id"]})
        await _send(manager, r["player_name"],
                    {"type": "toast",
                     "text": f"❌ Dein Schützling ist verloren — '{r['title']}' gescheitert."})
        return

    # Escort folgt dem Spieler (nur der Worker bewegt ihn; Wander-Loop skipt ihn).
    if escort is not None:
        d = max(abs(escort["x"] - pdata["x"]), abs(escort["y"] - pdata["y"]))
        if d > 1:
            try:
                await npc_worker._try_move_toward(
                    escort, pdata["x"], pdata["y"], world,
                    npc_manager, manager, structures_mgr)
            except Exception:
                log.debug("Escort-Follow-Move fehlgeschlagen", exc_info=True)

    # Fortschritt = größte erreichte Distanz vom Annahme-Ort.
    travelled = max(abs(pdata["x"] - prog["anchor_x"]), abs(pdata["y"] - prog["anchor_y"]))
    prog["distance"] = max(int(prog.get("distance", 0)), travelled)
    done = prog["distance"] >= dist_min and escort is not None
    status = "completed" if done else "active"
    await db.pool().execute(
        "UPDATE quests SET progress = $2, status = $3 WHERE id = $1",
        r["id"], json.dumps(prog), status,
    )
    await _send(manager, r["player_name"],
                {"type": "quest_progress", "quest": _quest_payload(r, prog, status)})
    if done and npc_id:
        # Schützling sicher angekommen → entlassen.
        npc_worker.ESCORT_NPCS.discard(npc_id)
        try:
            await npc_manager.despawn(npc_id)
            await manager.broadcast({"type": "npc_died", "npc_id": npc_id, "recycled": True})
        except Exception:
            pass
        await _send(manager, r["player_name"],
                    {"type": "toast",
                     "text": f"✅ Schützling sicher begleitet — '{r['title']}' abgeschlossen!"})
