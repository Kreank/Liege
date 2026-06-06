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
import skills

from .context import WsContext
from .dispatcher import register


# Welle 53 — Tier-Nutzinteraktion (melken / scheren / Eier / streicheln).
# Produkt-Items existieren bereits in items.ITEM_KINDS.
ANIMAL_PRODUCTS = {
    "cow": "milk_bucket", "calf": "milk_bucket", "ox": "milk_bucket", "bull": "milk_bucket",
    "goat": "milk_jug", "buck_goat": "milk_jug", "kid_goat": "milk_jug",
    "sheep": "wool_shearing", "ram": "wool_shearing", "lamb": "wool_shearing",
    "chicken_hen": "egg", "duck": "egg", "goose": "egg",
    "rooster": "feathers", "drake": "feathers", "gander": "feathers",
}
ANIMAL_VERB = {
    "milk_bucket": "melkst", "milk_jug": "melkst",
    "wool_shearing": "scherst", "egg": "sammelst ein Ei von",
    "feathers": "rupfst Federn von",
}
PET_FLAVOR = {
    "cat": "Die Katze schnurrt und reibt sich an deinem Bein. 🐈",
    "dog": "Der Hund wedelt freudig mit dem Schwanz. 🐕",
}
_TEND_COOLDOWN: dict[int, float] = {}   # npc_id → next_ready_epoch
TEND_COOLDOWN_S = 300                     # 5 min pro Tier


async def handle_tend_animal(ctx: WsContext, data: dict) -> None:
    """Streicheln/Melken/Scheren/Eier-Sammeln. Produzierende Nutztiere geben mit
    Cooldown ein Produkt ins Inventar; Haustiere + nicht-produzierende geben
    eine Flavor-Reaktion."""
    import time as _t
    websocket = ctx.websocket
    player_id = ctx.player_id
    npcs = ctx.npcs
    items = ctx.items
    manager = ctx.manager
    npc_id = int(data.get("npc_id", 0))
    npc = npcs.get(npc_id)
    if npc is None:
        return
    kind = npc["kind"]
    name = npc.get("name", "Das Tier")
    # Reichweite: Spieler muss am Tier stehen (chebyshev <= 2).
    player = manager.get_players().get(player_id)
    if player is None or combat.chebyshev(player["x"], player["y"], npc["x"], npc["y"]) > 2:
        await websocket.send_json({"type": "toast", "text": "Du bist zu weit weg."})
        return
    # Haustiere → Flavor.
    if kind in PET_FLAVOR:
        await websocket.send_json({"type": "toast", "text": PET_FLAVOR[kind]})
        return
    if kind not in npc_worker.LIVESTOCK_KINDS:
        return
    now = _t.time()
    ready = _TEND_COOLDOWN.get(npc_id, 0.0)
    if now < ready:
        mins = int((ready - now) / 60) + 1
        await websocket.send_json({"type": "toast",
            "text": f"🐾 {name} ist gerade versorgt — in ~{mins} min wieder."})
        return
    product = ANIMAL_PRODUCTS.get(kind)
    if not product:
        await websocket.send_json({"type": "toast", "text": f"🐾 Du tätschelst {name}."})
        return
    created = await items.create_for_player(product, player_id)
    _TEND_COOLDOWN[npc_id] = now + TEND_COOLDOWN_S
    if created is not None:
        from items import ITEM_KINDS as _IK
        pname = _IK.get(product, {}).get("name", product)
        verb = ANIMAL_VERB.get(product, "versorgst")
        await websocket.send_json({"type": "inventory_add", "item": created})
        await websocket.send_json({"type": "toast", "text": f"🪣 Du {verb} {name}: +1 {pname}"})
        try:
            xp = await skills.gain_xp(player_id, "gathering", 4)
            if xp:
                await websocket.send_json({"type": "skill_xp", **xp})
        except Exception:
            pass


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
register("tend_animal", handle_tend_animal)
