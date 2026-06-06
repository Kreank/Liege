"""Quests-Handler (Phase B13): list_quests, query_npc_quests,
accept_quest_template, quest_turn_in, accept_quest_from_npc,
claim_quest_reward.

Behält 1:1 das Verhalten aus den Legacy-Blocks in main.py.

HINWEIS: list_quests ruft quests.all_reputation und crasht latent
(REFACTOR_NOTES §1). Verhalten bleibt unverändert. Der Smoke testet
list_quests nicht mehr.
"""
from __future__ import annotations

import json
import logging

import combat
import currency
import db
import npc_worker
import quest_generator
import quests
import research
import skills

from .context import WsContext
from .dispatcher import register


async def handle_list_quests(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    qs = await quests.list_for_player(player_id)
    rep = await quests.all_reputation(player_id)
    await websocket.send_json({"type": "quests_update", "quests": qs,
                                "reputation": rep})


async def handle_query_npc_quests(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    npcs = ctx.npcs
    # Welle 23: Frontend fragt was dieser NPC anbietet / wo abgeben
    npc_id = int(data.get("npc_id", 0))
    npc = npcs.get(npc_id)
    if npc is None or npc["kind"] in combat.CREATURE_KINDS:
        await websocket.send_json({"type": "npc_quest_status",
                                    "npc_id": npc_id,
                                    "offers": [], "turnins": []})
        return
    combat_lvl = await skills.get_skill_level(player_id, "combat")
    offers = await quests.offers_for_npc(npc, player_id, combat_lvl)
    turnins = await quests.turnin_targets_for_npc(npc, player_id)
    # Schlanke Versionen für UI (offers = template-shape)
    offers_ui = [{
        "template_id": t["id"],
        "title": t["title_template"].format(**t["objective"]),
        "description": t["desc_template"].format(**t["objective"]),
        "quest_type": t["type"],
        "objective": t["objective"],
        "reward": t["reward"],
        "tier": t.get("tier", 1),
    } for t in offers]
    await websocket.send_json({
        "type": "npc_quest_status",
        "npc_id": npc_id,
        "offers":  offers_ui,
        "turnins": turnins,
    })


async def handle_accept_quest_template(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    npcs = ctx.npcs
    # Welle 23: template-basierte Annahme (statt LLM-Generator)
    template_id = str(data.get("template_id", ""))
    npc_id = int(data.get("npc_id", 0))
    npc = npcs.get(npc_id)
    if npc is None or not template_id:
        return
    # 3-Aktive-Quests-Limit beibehalten
    active_qs = await quests.list_for_player(player_id, ("active",))
    if len(active_qs) >= 3:
        await websocket.send_json({
            "type": "toast", "text": "Du hast bereits 3 aktive Quests!",
        })
        return
    new_q = await quests.accept_template(player_id, template_id, npc_id)
    if new_q is None:
        await websocket.send_json({
            "type": "toast",
            "text": "Quest konnte nicht angenommen werden.",
        })
        return
    await websocket.send_json({"type": "quest_new", "quest": new_q})
    await websocket.send_json({
        "type": "toast", "text": f"📜 {new_q['title']}",
    })
    # Welle 53: Escort-Quest → folgenden Schützling (merchant) am Spieler spawnen.
    # Er wird ausschließlich vom quest_worker geführt (ESCORT_NPCS-Skip im Wander-
    # Loop); seine id + Annahme-Anker landen in der Quest-progress.
    if new_q["quest_type"] == "escort":
        try:
            player = manager.get_players().get(player_id, {})
            ex, ey = player.get("x", 60), player.get("y", 40)
            escort = await npc_worker.spawn_one(world, npcs, manager,
                                                kind="merchant", at=(ex, ey))
            if escort is not None:
                npc_worker.ESCORT_NPCS.add(escort["id"])
                prog = dict(new_q.get("progress") or {})
                prog["escort_npc_id"] = escort["id"]
                prog["anchor_x"], prog["anchor_y"] = ex, ey
                await db.pool().execute(
                    "UPDATE quests SET progress = $2 WHERE id = $1",
                    new_q["id"], json.dumps(prog))
        except Exception:
            logging.exception("Escort-NPC-Spawn fehlgeschlagen")
    # Welle 23: Quest-Spawn-Garantie — bei kill-Quests sicherstellen
    # dass mindestens N target-creatures in erreichbarer Distanz sind.
    if new_q["quest_type"] == "kill":
        obj = new_q["objective"] or {}
        target_kind = obj.get("creature_kind")
        need_count = int(obj.get("count", 1))
        if target_kind:
            try:
                player = manager.get_players().get(player_id, {})
                px = player.get("x", 60)
                py = player.get("y", 40)
                # Wie viele matching creatures in Player-Radius 35?
                existing = sum(
                    1 for n in npcs.all()
                    if n["kind"] == target_kind
                    and abs(n["x"] - px) <= 35
                    and abs(n["y"] - py) <= 35
                )
                deficit = need_count - existing
                if deficit > 0:
                    # On-demand spawn — Cluster außerhalb Safe-Zone
                    logging.info("Quest-Spawn: %d × %s für Quest %d",
                                  deficit, target_kind, new_q["id"])
                    await npc_worker.spawn_cluster(
                        world, npcs, manager,
                        kind=target_kind,
                        count=deficit,
                        jitter=4,
                    )
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"💢 {deficit} {target_kind}-Spuren in der Nähe entdeckt …",
                    })
            except Exception:
                logging.exception("Quest-Spawn-Garantie fehlgeschlagen")
    sxp = await skills.gain_xp(player_id, "social", 6)
    if sxp:
        await websocket.send_json({"type": "skill_xp", **sxp})


async def handle_quest_turn_in(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    items = ctx.items
    # Welle 23: Quest beim NPC abgeben (Faction-Reward + Item-Reward)
    quest_id = int(data.get("quest_id", 0))
    npc_id = int(data.get("npc_id", 0))  # noqa: F841 — Legacy-Param, ungenutzt
    result = await quests.turn_in(quest_id, player_id)
    if result is None:
        await websocket.send_json({
            "type": "toast",
            "text": "Diese Quest ist nicht abschließbar.",
        })
        return
    reward = result.get("reward_granted") or {}
    # Items
    for item_kind, count in (reward.get("items") or {}).items():
        for _ in range(int(count)):
            created = await items.create_for_player(item_kind, player_id)
            if created is not None:
                await websocket.send_json({"type": "inventory_add",
                                            "item": created})
    # Welle 23: Research-Pool statt Skill-XP für wertvolle Quests.
    # Skill-XP gibt's bei Mob-Kills / Crafting direkt, nicht via Quest.
    if "research" in reward:
        n_research = int(reward["research"])
        new_pool = await research.award_points(
            player_id, n_research, reason="quest_turn_in",
        )
        await websocket.send_json({
            "type": "toast",
            "text": f"🔬 +{n_research} Forschungspunkte (Pool: {new_pool})",
        })
    # Legacy: alte Quests in DB könnten noch "xp" haben → still apply
    if "xp" in reward:
        xp_res = await skills.gain_xp(player_id, "combat", int(reward["xp"]))
        if xp_res:
            await websocket.send_json({"type": "skill_xp", **xp_res})
    # Welle 33: Gold-Reward in den Geldbeutel. Das "gold"-Feld wird als
    # SILBER interpretiert (×100 Kupfer) — Warenwert-Annahme, im
    # späteren Balancing-Pass ggf. anpassen.
    gold = int(reward.get("gold", 0))
    if gold > 0:
        # Welle 53: Quest-Gold ×10 statt ×100 (war absurd hoch ggü. den balancierten
        # Münz-Drops — gold:200 wären 20.000 Kupfer gewesen).
        await currency.add(player_id, gold * 10)
    # Münz-items im Reward sind via create_for_player schon ins Guthaben
    # geflossen → Geldbeutel jetzt an den Client pushen.
    await currency.push_wallet(manager, player_id)
    # Faction-Reputation-Toast
    for fac, delta in (reward.get("faction") or {}).items():
        new_rep = await quests.get_reputation(player_id, fac)
        sign = "+" if delta >= 0 else ""
        await websocket.send_json({
            "type": "toast",
            "text": f"🤝 {fac}: {sign}{delta} (Ruf: {new_rep})",
        })
    await websocket.send_json({"type": "quest_closed",
                                "quest_id": quest_id})
    await websocket.send_json({
        "type": "toast", "text": "✅ Quest abgegeben!",
    })


async def handle_accept_quest_from_npc(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    npcs = ctx.npcs
    npc_id = int(data.get("npc_id", 0))
    npc = npcs.get(npc_id)
    if npc is None or npc["kind"] in combat.CREATURE_KINDS:
        return
    # NPC-Kind darf überhaupt Quests vergeben?
    if not quest_generator.can_give_quest(npc["kind"]):
        await websocket.send_json({
            "type": "toast",
            "text": f"{npc['name']} hat keinen Auftrag für dich.",
        })
        return
    # Hat dieser NPC bereits eine offene Quest mit dem Spieler?
    existing = await db.pool().fetchrow(
        "SELECT id FROM quests WHERE player_name = $1 "
        "AND giver_npc_id = $2 AND status IN ('active','completed') LIMIT 1",
        player_id, npc_id,
    )
    if existing:
        await websocket.send_json({
            "type": "toast",
            "text": f"{npc['name']} hat dir bereits einen Auftrag gegeben.",
        })
        return
    # Spieler kann max. 3 aktive Quests gleichzeitig haben
    active_qs = await quests.list_for_player(player_id, ("active",))
    if len(active_qs) >= 3:
        await websocket.send_json({
            "type": "toast", "text": "Du hast bereits 3 aktive Quests!"
        })
        return
    # Welle 20: KI-generierte Quest mit Welt-Verifikation
    try:
        new_q = await quest_generator.generate_quest_for_npc(
            player_id, npc, npcs,
        )
    except Exception:
        logging.exception("Quest-Generator versagte")
        new_q = None
    # Fallback auf Template wenn LLM/Generator nicht klappt
    if new_q is None:
        new_q = await quests.create_from_template(player_id, npc_id, None)
    await websocket.send_json({"type": "quest_new", "quest": new_q})
    await websocket.send_json({
        "type": "toast", "text": f"📜 {new_q['title']}"
    })
    # Social-XP für Quest-Annahme
    sxp = await skills.gain_xp(player_id, "social", 6)
    if sxp:
        await websocket.send_json({"type": "skill_xp", **sxp})


async def handle_claim_quest_reward(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    items = ctx.items
    quest_id = int(data.get("quest_id", 0))
    qs = await quests.list_for_player(player_id, ("completed",))
    target_q = next((q for q in qs if q["id"] == quest_id), None)
    if target_q is None:
        return
    # Welle 53 — Anti-Doppel-Claim (TOCTOU): Reward NUR gewähren, wenn wir die
    # Quest atomar von 'completed' → 'closed' überführen können. Zwei parallele
    # claim-Frames → nur einer gewinnt das UPDATE, der andere bekommt nichts.
    claimed = await db.pool().fetchval(
        "UPDATE quests SET status = 'closed' "
        "WHERE id = $1 AND player_name = $2 AND status = 'completed' RETURNING id",
        quest_id, player_id,
    )
    if claimed is None:
        return   # bereits eingelöst
    # Reward-Struktur: { items: {kind:count}, gold:N, xp:N, research:N,
    # faction: {fac:delta} }. _row_to_dict hat schon defensiv geparsed.
    reward = target_q.get("reward") or {}
    # Items entfalten
    for item_kind, count in (reward.get("items") or {}).items():
        for _ in range(int(count)):
            created = await items.create_for_player(item_kind, player_id)
            if created is not None:
                await websocket.send_json({"type": "inventory_add", "item": created})
    # Welle 33: Gold-Reward in den Geldbeutel ("gold"-Feld = Silber).
    # Münz-items oben sind via create_for_player schon ins Guthaben geflossen.
    gold = int(reward.get("gold", 0) or 0)
    if gold > 0:
        # Welle 53: Quest-Gold ×10 statt ×100 (war absurd hoch ggü. den balancierten
        # Münz-Drops — gold:200 wären 20.000 Kupfer gewesen).
        await currency.add(player_id, gold * 10)
    await currency.push_wallet(manager, player_id)
    # XP → Combat-Skill (pragmatisch)
    xp = int(reward.get("xp", 0) or 0)
    if xp > 0:
        xp_result = await skills.gain_xp(player_id, "combat", xp)
        if xp_result:
            await websocket.send_json({"type": "skill_xp", **xp_result})
    # Research-Pool
    rp = int(reward.get("research", 0) or 0)
    if rp > 0:
        try:
            await research.award_points(player_id, rp, reason="quest")
        except Exception:
            logging.exception("quest research-reward failed")
    # Faction-Reputation
    for fac, delta in (reward.get("faction") or {}).items():
        try:
            await quests.add_reputation(player_id, fac, int(delta))
        except Exception:
            logging.exception("quest faction-reward failed")
    # (Status wurde oben bereits atomar auf 'closed' gesetzt.)
    await websocket.send_json({"type": "quest_closed", "quest_id": quest_id})
    await websocket.send_json({"type": "toast", "text": "✅ Quest abgegeben!"})


register("list_quests", handle_list_quests)
register("query_npc_quests", handle_query_npc_quests)
register("accept_quest_template", handle_accept_quest_template)
register("quest_turn_in", handle_quest_turn_in)
register("accept_quest_from_npc", handle_accept_quest_from_npc)
register("claim_quest_reward", handle_claim_quest_reward)
