"""Dialog-Handler (Phase B6): talk_to_npc.

Behält 1:1 das Verhalten aus dem Legacy-Block in main.py:
- Hostility/Livestock/Cart-Guards.
- Talk-History laden, Quest-Kontext aus DB, Region-Lore lazy, NPC-Memory.
- dialog.reply, npc_memory.write_memory, quest_stages.on_player_event.
"""
from __future__ import annotations

import asyncio
import logging

import combat
import db
import dialog
import npc_memory
import npc_worker
import quest_generator
import quest_stages
import region_history

from .context import WsContext
from .dispatcher import register


async def handle_talk_to_npc(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    npcs = ctx.npcs
    events = ctx.events
    world = ctx.world

    npc_id = int(data.get("npc_id", 0))
    message = str(data.get("message", "")).strip()[:500]
    npc = npcs.get(npc_id)
    if npc is None or not message:
        return
    # Hostile Kreaturen (Bandit/Wolf/Goblin/…) reden nicht — die greifen an.
    if npc["kind"] in combat.CREATURE_KINDS:
        await websocket.send_json({
            "type": "toast",
            "text": f"⚔️ {npc.get('name', 'Diese Kreatur')} ist feindlich — angreifen, nicht reden!",
        })
        return
    # Welle 25: Nutztiere + Karawanen-Wagen reden nicht.
    # Spätere Interaktions-Mechanik (Streichen/Melken/Scheren/
    # Schlachten/Wolle/Eier) kommt als eigenes System.
    if npc["kind"] in npc_worker.LIVESTOCK_KINDS:
        await websocket.send_json({
            "type": "toast",
            "text": f"🐾 {npc.get('name', 'Das Tier')} ist ein Nutztier — keine Konversation.",
        })
        return
    if npc["kind"] in npc_worker.CART_KINDS:
        await websocket.send_json({
            "type": "toast",
            "text": "🛒 Ein Wagen redet nicht — sprich den Händler daneben an.",
        })
        return
    await npcs.add_talk(npc_id, player_id, "user", message)
    history = await npcs.recent_talks(npc_id, player_id, limit=10)
    # History enthält die soeben gespeicherte Spieler-Nachricht;
    # die ist im Prompt-Builder bereits angehängt, also davor abschneiden.
    history_for_prompt = history[:-1] if history else []
    try:
        recent_events = await events.recent(5)
        # Welle 26: Quest-Kontext aufbereiten
        active_quest = None
        try:
            qrow = await db.pool().fetchrow(
                "SELECT id, quest_type, title, objective, progress, status "
                "FROM quests WHERE player_name = $1 AND giver_npc_id = $2 "
                "AND status IN ('active','completed') ORDER BY id DESC LIMIT 1",
                player_id, npc_id,
            )
            if qrow:
                import json as _json
                obj = qrow["objective"]
                prog = qrow["progress"]
                active_quest = {
                    "id": qrow["id"],
                    "quest_type": qrow["quest_type"],
                    "title": qrow["title"],
                    "objective": _json.loads(obj) if isinstance(obj, str) else obj,
                    "progress":  _json.loads(prog) if isinstance(prog, str) else prog,
                    "status":    qrow["status"],
                }
        except Exception:
            logging.exception("Quest-Context-Load fehlgeschlagen")
        can_give = quest_generator.can_give_quest(npc["kind"]) and active_quest is None
        # Welle 23: Region-Historie als Lore-Kontext (lazy gen)
        region_lore = None
        try:
            from world import CHUNK_SIZE
            cx = npc["x"] // CHUNK_SIZE
            cy = npc["y"] // CHUNK_SIZE
            rx, ry = region_history.region_for_chunk(cx, cy)
            # Erst aus DB lesen, sonst im Hintergrund generieren
            hist = await region_history.get_region_history(world.seed, rx, ry)
            if hist is None:
                asyncio.create_task(
                    region_history.ensure_region_history(world.seed, rx, ry)
                )
            else:
                region_lore = region_history.format_for_prompt(hist)
        except Exception:
            logging.exception("Region-Historie-Load fehlgeschlagen")
        # Welle 25: NPC Long-Term-Memory laden
        memories_text = None
        try:
            top_mem = await npc_memory.retrieve_top_k(
                npc_id, player_id, query=message, k=npc_memory.TOP_K,
            )
            memories_text = npc_memory.format_memories_for_prompt(top_mem)
        except Exception:
            logging.exception("NPC-Memory-Retrieval fehlgeschlagen")
        text = await dialog.reply(
            npc, player_id, message, history_for_prompt,
            recent_events=recent_events,
            active_quest=active_quest,
            can_give_quest=can_give,
            region_lore=region_lore,
            memories=memories_text,
        )
    except Exception:
        text = "…"  # fallback
    await npcs.add_talk(npc_id, player_id, "npc", text)
    # Welle 25: Turn als Memory speichern (Importance via Fast-Brain)
    turn_text = f"{player_id}: {message}\n{npc['name']}: {text}"
    asyncio.create_task(
        npc_memory.write_memory(npc_id, player_id, turn_text)
    )
    # Welle 28: Multi-Stage talk-hook
    try:
        stage_q = await quest_stages.on_player_event(
            player_id, "talk", {"kind": npc["kind"], "npc_id": npc_id},
        )
        for q in stage_q:
            await websocket.send_json({"type": "quest_progress", "quest": q})
    except Exception:
        pass
    await websocket.send_json({
        "type": "npc_reply",
        "npc_id": npc_id,
        "text": text,
    })


register("talk_to_npc", handle_talk_to_npc)
