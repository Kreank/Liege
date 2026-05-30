import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

import auth
from auth_routes import router as auth_router
from dev_chat import dev_chat_handler
import db
import llm
import combat
import dialog
import disaster_state
import dungeons
import event_worker
import farm_worker
import harvest
import item_worker
import loot
import loot_rolls
import needs
import body_parts
import bill_queue
import npc_mood
import npc_worker
import player_events
import quality
import recipes
import research
import respawn_worker
import skills
import raid_director
import time_system
import weather_worker
import quests
import status_effects
import talents
import affixes
import item_namer
import quest_generator
import region_history
import npc_memory
import factions
import groups
import quest_stages
import dungeon_instance
import dungeon_tiers
import attributes
import trade
import world_populator
import power_budget
import spells
import spell_caster
from ws_manager import ConnectionManager
from world import World
from structures import StructureManager
from events import EventManager
from npcs import NPCManager
import npcs as npcs_mod
from items import ItemManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")

manager = ConnectionManager()
structures = StructureManager()
events = EventManager()
npcs = NPCManager()
items = ItemManager()
# Welle 23: globaler Ref damit village_spawner/world_populator Chests befüllen
# können, ohne den item_manager als Parameter durchreichen zu müssen.
import items as _items_module
_items_module.set_global_item_manager(items)
import currency
from services import player_state as _player_state
from services import player_equipment as _player_equipment
from services.player_comms import send_to_player as _send_to_player_svc
from services.player_equipment import (
    get_equipped_weapon_kind, get_equipped_tool_kind, has_tool_for_skill,
    TOOL_FOR_SKILL, PROP_SKILL, TOOL_HINT, NO_TOOL_PROPS,
)
from services.player_state import (
    load_or_create_player as _load_or_create_player_svc,
    heal_player as _heal_player_svc,
    damage_player as _damage_player_svc,
    is_downed, do_respawn as _do_respawn_svc,
    restore_mana as _restore_mana_svc,
    refund_mana as _refund_mana_svc,
    DEFAULT_SPAWN_CENTER,
    downed_state as _downed_state,
)
world: World | None = None


# ─── Dünne Bind-Wrapper für Helper aus services/* + Geschwister-Modulen ────
# Damit die hunderten Aufrufstellen weiter nur den player_id übergeben können
# und nicht jedes Mal `manager`/`world`/… explizit mitschreiben müssen, binden
# wir hier die Modul-Globals ein einziges Mal. B2 löst das später via WsContext
# vollständig auf.

async def _push_wallet(player_id: str, gained: int | None = None) -> None:
    await currency.push_wallet(manager, player_id, gained=gained)


async def _group_snapshot(player_id: str) -> dict | None:
    return await groups.group_snapshot(manager, player_id)


async def _broadcast_to_group(group_id: int, message: dict,
                              exclude: str | None = None) -> None:
    await groups.broadcast_to_group(manager, group_id, message, exclude=exclude)


async def _push_group_state(player_id: str) -> None:
    await groups.push_group_state(manager, player_id)


async def _push_group_state_to_all_members(group_id: int) -> None:
    await groups.push_group_state_to_all_members(manager, group_id)


# Re-Export der Konstanten, falls anderswo importiert
GROUP_XP_SHARE_RADIUS = combat.GROUP_XP_SHARE_RADIUS
GROUP_XP_BONUS_FACTOR = combat.GROUP_XP_BONUS_FACTOR
LOOT_ROLL_RADIUS = loot.LOOT_ROLL_RADIUS


async def _drop_loot_for_npc(killer_id: str, npc: dict,
                              drop_x: int, drop_y: int) -> None:
    await loot.drop_loot_for_npc(manager, items, killer_id, npc, drop_x, drop_y)


async def _maybe_start_loot_roll(killer_id: str, dropped: dict) -> None:
    await loot.maybe_start_loot_roll(manager, items, killer_id, dropped)


async def _gain_combat_xp_with_share(killer_id: str, amount: int,
                                     npc_x: int, npc_y: int) -> list[tuple[str, dict]]:
    return await combat.gain_combat_xp_with_share(manager, killer_id, amount, npc_x, npc_y)


async def _find_drop_xy(x: int, y: int) -> tuple[int, int]:
    return await loot.find_drop_xy(world, structures, x, y)


async def _send_to_player(player_id: str, payload: dict) -> None:
    await _send_to_player_svc(manager, player_id, payload)


# Player-Lifecycle-Bind-Wrapper (gleiches Muster wie oben — main.py-Code ruft
# sie weiter mit kurzem Signatures auf; services-Funktionen bekommen Globals).

async def load_or_create_player(name: str) -> dict:
    return await _load_or_create_player_svc(world, structures, name)


async def heal_player(name: str, amount: int) -> None:
    await _heal_player_svc(manager, name, amount)


async def damage_player(name: str, dmg: int, source_npc_id: int | None = None,
                        dmg_type: str = "physical") -> None:
    await _damage_player_svc(manager, name, dmg, source_npc_id, dmg_type)


async def _do_respawn(name: str, in_place: bool = False) -> None:
    await _do_respawn_svc(manager, world, structures, name, in_place=in_place)


async def restore_mana(name: str, amount: int) -> None:
    await _restore_mana_svc(manager, name, amount)


async def _refund_mana(player_id: str, amount: int) -> None:
    await _refund_mana_svc(manager, player_id, amount)


async def _apply_heal_aggro(player_id: str, x: int, y: int, threat: int) -> None:
    await combat.apply_heal_aggro(npcs, player_id, x, y, threat)


async def _apply_spell_effects(player_id: str, spell_id: str,
                                 spell: dict, target: dict) -> None:
    await spells.apply_spell_effects(
        manager, npcs, player_id, spell_id, spell, target,
        heal_player_fn=heal_player,
        do_respawn_fn=_do_respawn,
        is_downed_fn=is_downed,
        send_to_player_fn=_send_to_player,
        find_drop_xy_fn=_find_drop_xy,
        drop_loot_for_npc_fn=_drop_loot_for_npc,
        gain_combat_xp_with_share_fn=_gain_combat_xp_with_share,
        downed_state=_downed_state,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global world
    await db.init_db()
    await llm.init_llm()
    # World-Seed (env-überschreibbar). Reset 2026-05-30: neuer Seed → frische
    # Landkarte. Für künftige Resets einfach WORLD_SEED-Env ändern (oder hier).
    world = await World.load_or_create(
        seed=int(os.environ.get("WORLD_SEED", "20260530")))
    # services.player_state braucht world+structures für _downed_timer→do_respawn
    _player_state.init(world, structures)
    await structures.load()
    await npcs.load()
    # Welle 27: Faction-System seeden + bestehende NPCs zuweisen
    await factions.seed_defaults()
    updated_npc_factions = await factions.assign_faction_to_existing_npcs()
    if updated_npc_factions:
        logging.info("Faction-IDs gesetzt für %d NPCs", updated_npc_factions)
    # Welle 31: Spielergruppen (Party / Raid)
    await groups.init_schema()
    # Welle 23: Region-Difficulty-Tabelle (Stage-2-Hook für World-Brain)
    try:
        import region_difficulty
        await region_difficulty.init_schema()
    except Exception:
        logging.exception("region_difficulty init_schema failed (non-fatal)")
    # Welle 24: Disaster-State (Blutmond, Sterbende Sonne, Pest, ...)
    try:
        import disaster_state
        await disaster_state.init_schema()
    except Exception:
        logging.exception("disaster_state init_schema failed (non-fatal)")
    # Welle 26: Personality-Backfill für existierende NPCs ohne Archetyp.
    # Danach Reload damit die personality im In-Memory-Cache landet.
    try:
        import npc_chatter as _nc
        n_p = await _nc.assign_personality_to_existing_npcs()
        if n_p > 0:
            await npcs.load()
    except Exception:
        logging.exception("Personality-Backfill fehlgeschlagen (non-fatal)")
    # Populate läuft jetzt on-demand pro Chunk beim Connect/Chunk-Cross (siehe populate_chunk_if_needed)

    event_task = asyncio.create_task(
        event_worker.run(events, manager, world, npcs, structures)
    )
    wander_task = asyncio.create_task(
        npc_worker.wander_loop(world, npcs, manager,
                                damage_player_cb=damage_player,
                                structures_mgr=structures)
    )
    item_task = asyncio.create_task(item_worker.run(world, items, manager))
    spawn_task = asyncio.create_task(npc_worker.initial_spawn(world, npcs, manager, structures))
    respawn_task = asyncio.create_task(npc_worker.respawn_loop(world, npcs, manager, structures))
    farm_task = asyncio.create_task(farm_worker.run(items, manager))
    world_respawn_task = asyncio.create_task(respawn_worker.run(world, structures, manager))
    needs_task = asyncio.create_task(needs.run(manager, damage_player))
    stamina_task = asyncio.create_task(needs.run_stamina(manager, heal_player))
    bill_task = asyncio.create_task(bill_queue.run(manager, items, recipes))
    mood_task = asyncio.create_task(npc_mood.run(npcs, manager))
    raid_task = asyncio.create_task(raid_director.run(world, npcs, manager, events))
    time_task = asyncio.create_task(time_system.run(manager))
    weather_task = asyncio.create_task(weather_worker.weather_loop(manager))
    status_task = asyncio.create_task(
        status_effects.run(manager, damage_player, heal_player)
    )
    # Welle 22: Research-Tick-Worker (online-Player bekommen alle 5min +1 Pool)
    research_tick_task = asyncio.create_task(research.time_tick_loop(manager))
    # Welle 25: Spell-Caster Callbacks wiren (Effects-Apply, Mana-Refund, Aggro)
    spell_caster.set_callbacks(
        apply_effects_cb=_apply_spell_effects,
        refund_mana_cb=_refund_mana,
        aggro_cb=_apply_heal_aggro,
        send_to_player_cb=_send_to_player,
    )
    # Welle 24: Disaster-Tick (refresht Cache, broadcastet ended-Events)
    disaster_task = asyncio.create_task(disaster_state.run(manager))
    # Welle 29e: Wildfire-Spread-Loop (alle 30s prüft fire_tiles → spread/burn out)
    wildfire_task = asyncio.create_task(event_worker.wildfire_tick_loop(structures, manager))
    # Welle 31: Spielergruppen-Reaper (Auto-Disband idle parties + alte Raids)
    groups_reaper_task = asyncio.create_task(groups.reaper_loop(manager))
    # Welle 32: Dungeon-Reaper (expires_at) + Auto-Spawn
    import dungeon_director as _dd
    dungeon_reaper_task = asyncio.create_task(
        _dd.reaper_loop(manager, world, structures, npcs))
    dungeon_spawn_task = asyncio.create_task(
        _dd.spawn_loop(manager, world, structures))

    yield

    tasks = (event_task, wander_task, item_task, spawn_task, respawn_task,
             farm_task, world_respawn_task, needs_task, bill_task, mood_task,
             raid_task, time_task, status_task, groups_reaper_task,
             dungeon_reaper_task, dungeon_spawn_task)
    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass
    await llm.close_llm()
    await db.close_db()


app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.add_api_websocket_route("/ws/dev-chat", dev_chat_handler)

app.mount("/static", StaticFiles(directory="../frontend"), name="static")
app.mount("/assets", StaticFiles(directory="../assets"), name="assets")


@app.get("/")
async def root():
    return FileResponse("../frontend/index.html")


@app.get("/login")
async def login_page():
    return FileResponse("../frontend/login.html")


@app.get("/admin")
async def admin_page():
    return FileResponse("../frontend/admin.html")


@app.get("/manifest.webmanifest")
async def pwa_manifest():
    return FileResponse(
        "../frontend/manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/sw.js")
async def pwa_sw():
    # Muss von root serviert werden, damit der Scope `/` ist.
    return FileResponse(
        "../frontend/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


CHUNK_SEND_RADIUS = 3  # 7x7 Chunks (224×224 Tiles) um Spieler


async def _active_dungeon_markers() -> list[dict]:
    return await dungeons.active_dungeon_markers()


async def _dungeon_floor_payload(dungeon_id: int, floor_idx: int) -> dict:
    return await dungeons.dungeon_floor_payload(npcs, dungeon_id, floor_idx)


_DUNGEON_TRAP_DMG = {
    "spike_trap": 14, "dart_trap": 12, "fire_trap": 22,
    "frost_trap": 16, "poison_trap": 10, "rockfall_trap": 24,
}
_TRAP_LABEL = {
    "spike_trap":    "🗡️ Stachelfalle! Spitzen schießen aus dem Boden.",
    "dart_trap":     "🎯 Pfeilfalle! Bolzen aus der Wand.",
    "fire_trap":     "🔥 Feuerfalle! Eine Stichflamme schlägt hoch.",
    "frost_trap":    "❄️ Frostfalle! Eisige Dornen.",
    "poison_trap":   "☠️ Giftfalle! Eine grüne Wolke zischt hervor.",
    "rockfall_trap": "🪨 Steinschlag! Die Decke bricht herab.",
}


def _overworld_npcs_near(x: int, y: int, radius: int = 0) -> list:
    return npcs_mod.overworld_npcs_near(npcs, x, y, radius)


async def _populate_chunks_bg(chunks) -> None:
    await world_populator.populate_chunks_bg(world, structures, manager, npcs, chunks)


async def _sync_learned_spells(player_name: str) -> list[str]:
    return await spells.sync_learned_for_player(player_name)


async def _list_learned_spells(player_name: str) -> list[str]:
    return await spells.list_learned_for_player(player_name)


async def _compute_attributes(player_name: str) -> dict:
    return await attributes.compute_attributes(items, player_name)


async def _build_stat_sheet(player_name: str) -> dict:
    return await attributes.build_stat_sheet(items, player_name)


async def _send_attrs_update(websocket, player_name: str) -> None:
    await attributes.send_attrs_update(items, websocket, player_name)


# Cooldown-Tracking für Heal-Strukturen: dict[(player_name, struct_id)] → timestamp
_heal_cooldowns: dict[tuple[str, int], float] = {}
# Cooldown-Tracking für Dungeon-Encounter (1 Eintrag pro Spieler)
_dungeon_cooldowns: dict[str, float] = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user = await auth.get_user_from_ws(websocket)
    if not user:
        await websocket.accept()
        await websocket.close(code=1008)
        return
    player_id = user["name"]
    state = await load_or_create_player(player_id)
    spawn = {"x": state["x"], "y": state["y"]}
    await manager.connect(websocket, player_id, spawn["x"], spawn["y"])

    # Chunks um Spawn laden + senden (lazy gen für nicht-existierende)
    pcx, pcy, _, _ = World.world_to_chunk(spawn["x"], spawn["y"])
    chunks = await world.ensure_chunks_around(pcx, pcy, radius=CHUNK_SEND_RADIUS)
    # Populate als Background-Task, nicht-blockierend
    asyncio.create_task(_populate_chunks_bg(chunks))

    # Strukturen / Items / NPCs auf nahen Bereich filtern um Init-Payload klein zu halten
    view_radius = CHUNK_SEND_RADIUS * 32 + 32  # ~7 Chunks
    def near(x, y):
        return abs(x - spawn["x"]) <= view_radius and abs(y - spawn["y"]) <= view_radius
    nearby_structs = [s for s in structures.all() if near(s["x"], s["y"])]
    nearby_items = [it for it in await items.get_on_ground() if near(it["x"], it["y"])]
    nearby_npcs = [n for n in npcs.all() if near(n["x"], n["y"])]

    # Welle 23: Character-Creation-Flag aus DB lesen
    char_row = await db.pool().fetchrow(
        "SELECT preset, character_created FROM players WHERE name = $1",
        player_id,
    )
    needs_creation = not (char_row and char_row["character_created"])
    preset = char_row["preset"] if char_row else None

    await websocket.send_json({
        "type": "init",
        "player_id": player_id,
        "needs_character_creation": needs_creation,
        "preset": preset,
        "chunks": chunks,
        "chunk_size": 32,
        "world_seed": world.seed,
        "players": manager.get_players(),
        "structures": nearby_structs,
        "dungeons": await _active_dungeon_markers(),   # Minimap-Ortung (Spür-Radius)
        "events": await events.recent(20),
        "npcs": nearby_npcs,
        "items_ground": nearby_items,
        "inventory": await items.get_inventory(player_id),
        "wallet_copper": await currency.balance(player_id),
        "spawn": spawn,
        "hp": state["hp"],
        "max_hp": state["max_hp"],
        "mana": state["mana"],
        "max_mana": state["max_mana"],
        "hunger": state.get("hunger", 100),
        "max_hunger": state.get("max_hunger", 100),
        "stamina": state.get("stamina", 100),
        "max_stamina": state.get("max_stamina", 100),
        "thirst": state.get("thirst", 100),
        "max_thirst": state.get("max_thirst", 100),
        "skills": await skills.get_skills(player_id),
        "body_parts": await body_parts.get_body_parts(player_id) or {"legs": 100, "arms": 100, "torso": 100},
        "research": await research.get_player_research(player_id),
        "time":     time_system.snapshot(),
        "quests":   await quests.list_for_player(player_id),
        "factions":     await factions.list_all_reputations(player_id),
        "attributes":   await _compute_attributes(player_id),
        "active_disasters": await disaster_state.list_active(),
        "stats":        await _build_stat_sheet(player_id),
        "power_tier":   await power_budget.player_power_tier(player_id),
        # Welle 25: Spells anhand Magic-Skill freischalten, dann liefern
        "spell_catalog": spells.SPELLS,
        "learned_spells": (await _sync_learned_spells(player_id),
                            await _list_learned_spells(player_id))[1],
        "talents": {
            "learned":      await talents.list_learned(player_id),
            "points":       await talents.get_talent_points(player_id),
            "tree":         talents.tree_for_ui(
                                await skills.get_skills(player_id),
                                set(l["talent_id"] for l in await talents.list_learned(player_id)),
                                await talents.get_talent_points(player_id),
                            ),
        },
        "group":         await _group_snapshot(player_id),
        "group_invites": await groups.list_invites_for(player_id),
    })

    # Welle 31: falls Spieler Party-Leader ist und gerade reconnected, Reaper-Timer löschen
    _g = await groups.get_group_for(player_id)
    if _g and _g["kind"] == "party" and _g["leader"] == player_id:
        groups.mark_leader_online(_g["id"])
    # Alle Mitarbeiter-Anzeigen aktualisieren (Online-Status)
    if _g:
        await _broadcast_to_group(_g["id"], {
            "type": "group_member_online", "player_name": player_id,
        }, exclude=player_id)

    await manager.broadcast({
        "type": "player_joined",
        "player_id": player_id,
        "x": spawn["x"],
        "y": spawn["y"],
        "name": player_id[:12],
    }, exclude=player_id)

    try:
        while True:
            data = await websocket.receive_json()
            mtype = data.get("type")

            if mtype == "chat":
                text = (data.get("text") or "").strip()
                if text and len(text) <= 500:
                    await manager.broadcast({
                        "type": "chat",
                        "from": player_id,
                        "text": text,
                    })
                continue

            # — Welle 31: Spielergruppen (Party / Raid) ————————————————

            if mtype == "group_create_party":
                try:
                    await groups.create_party(player_id)
                    await _push_group_state(player_id)
                except ValueError as e:
                    await websocket.send_json({"type": "group_error",
                                                "reason": str(e)})
                continue

            if mtype == "group_invite":
                target = (data.get("target") or "").strip()
                if not target:
                    continue
                g = await groups.get_group_for(player_id)
                if not g:
                    # kein Solo-Invite — implizit Party erstellen
                    try:
                        g_new = await groups.create_party(player_id)
                        gid = g_new["id"]
                        await _push_group_state(player_id)
                    except ValueError:
                        await websocket.send_json({"type": "group_error",
                                                    "reason": "already_in_group"})
                        continue
                else:
                    gid = g["id"]
                res = await groups.invite(gid, player_id, target)
                if not res.get("ok"):
                    await websocket.send_json({"type": "group_error",
                                                "reason": res["reason"]})
                    continue
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
                continue

            if mtype == "group_accept":
                invite_id = int(data.get("invite_id") or 0)
                if not invite_id:
                    continue
                res = await groups.accept_invite(invite_id, player_id)
                if not res.get("ok"):
                    await websocket.send_json({"type": "group_error",
                                                "reason": res["reason"]})
                    continue
                await _push_group_state_to_all_members(res["group_id"])
                continue

            if mtype == "group_decline":
                invite_id = int(data.get("invite_id") or 0)
                if invite_id:
                    await groups.decline_invite(invite_id, player_id)
                continue

            if mtype == "group_leave":
                res = await groups.leave(player_id)
                if not res.get("ok"):
                    await websocket.send_json({"type": "group_error",
                                                "reason": res["reason"]})
                    continue
                # Spieler selbst: leer-state
                await _push_group_state(player_id)
                if not res["disbanded"]:
                    # Restmitglieder benachrichtigen
                    await _broadcast_to_group(res["group_id"], {
                        "type": "group_member_left",
                        "player_name": player_id,
                        "new_leader": res.get("new_leader"),
                    })
                    await _push_group_state_to_all_members(res["group_id"])
                continue

            if mtype == "group_kick":
                target = (data.get("target") or "").strip()
                g = await groups.get_group_for(player_id)
                if not g or not target:
                    continue
                res = await groups.kick(g["id"], player_id, target)
                if not res.get("ok"):
                    await websocket.send_json({"type": "group_error",
                                                "reason": res["reason"]})
                    continue
                # Gekickter Spieler: Snapshot wird leer
                await _push_group_state(target)
                tws = manager.connections.get(target)
                if tws is not None:
                    try:
                        await tws.send_json({"type": "group_kicked",
                                              "by": player_id})
                    except Exception:
                        pass
                await _push_group_state_to_all_members(g["id"])
                continue

            if mtype == "group_promote":
                target = (data.get("target") or "").strip()
                g = await groups.get_group_for(player_id)
                if not g or not target:
                    continue
                res = await groups.promote(g["id"], player_id, target)
                if not res.get("ok"):
                    await websocket.send_json({"type": "group_error",
                                                "reason": res["reason"]})
                    continue
                await _push_group_state_to_all_members(g["id"])
                continue

            if mtype == "group_transfer_leader":
                target = (data.get("target") or "").strip()
                g = await groups.get_group_for(player_id)
                if not g or not target:
                    continue
                res = await groups.transfer_leader(g["id"], player_id, target)
                if not res.get("ok"):
                    await websocket.send_json({"type": "group_error",
                                                "reason": res["reason"]})
                    continue
                await _push_group_state_to_all_members(g["id"])
                continue

            if mtype == "group_disband":
                g = await groups.get_group_for(player_id)
                if not g:
                    continue
                # Mitgliederliste VOR dem Disband holen, sonst kein Broadcast möglich
                member_names = await groups.get_member_names(g["id"])
                ok = await groups.disband(g["id"], player_id)
                if not ok:
                    await websocket.send_json({"type": "group_error",
                                                "reason": "no_permission"})
                    continue
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
                continue

            if mtype == "group_refresh":
                await _push_group_state(player_id)
                continue

            if mtype == "group_chat":
                text = (data.get("text") or "").strip()
                if not text or len(text) > 500:
                    continue
                g = await groups.get_group_for(player_id)
                if not g:
                    await websocket.send_json({"type": "group_error",
                                                "reason": "not_in_group"})
                    continue
                await _broadcast_to_group(g["id"], {
                    "type": "group_chat",
                    "from": player_id,
                    "text": text,
                    "kind": g["kind"],
                })
                continue

            if mtype == "group_convert_to_raid":
                new_kind = (data.get("kind") or "raid_small").strip()
                g = await groups.get_group_for(player_id)
                if not g:
                    await websocket.send_json({"type": "group_error",
                                                "reason": "not_in_group"})
                    continue
                res = await groups.convert_to_raid(g["id"], player_id, new_kind)
                if not res.get("ok"):
                    await websocket.send_json({"type": "group_error",
                                                "reason": res["reason"]})
                    continue
                await _broadcast_to_group(g["id"], {
                    "type": "group_converted",
                    "from_kind": res["from_kind"],
                    "to_kind": res["to_kind"],
                })
                await _push_group_state_to_all_members(g["id"])
                continue

            if mtype == "dev_world_repopulate":
                # Admin-only: setzt populated=false für leere Chunks, löscht
                # System-Strukturen darin. Beim nächsten Betreten neu gespawnt.
                if user.get("role") != "admin":
                    await websocket.send_json({"type": "toast",
                                                "text": "⛔ Admin only"})
                    continue
                import world_populator as _wp
                count = await _wp.reset_chunks_without_player_structures(world)
                await websocket.send_json({"type": "toast",
                                            "text": f"♻️ {count} Chunks zurückgesetzt"})
                continue

            if mtype == "dev_trigger_event":
                # Admin-only: feuert sofort einen Event-Effekt (zum Testen von
                # Disastern etc.). data.effect = z.B. "thunderstorm", "toxic_fog".
                if user.get("role") != "admin":
                    await websocket.send_json({"type": "toast", "text": "⛔ Admin only"})
                    continue
                eff = (data.get("effect") or "").strip()
                if not eff:
                    await websocket.send_json({"type": "toast", "text": "effect fehlt"})
                    continue
                try:
                    await event_worker._apply_event_effect(
                        {"effect": eff}, {}, world, npcs, structures, manager)
                    await websocket.send_json({"type": "toast",
                                                "text": f"🧪 Event ausgelöst: {eff}"})
                except Exception as _e:
                    logging.exception("dev_trigger_event fehlgeschlagen")
                    await websocket.send_json({"type": "toast",
                                                "text": f"Fehler: {_e}"})
                continue

            if mtype == "loot_vote":
                roll_id = int(data.get("roll_id", 0))
                vote_kind = (data.get("vote") or "").strip().lower()
                res = await loot_rolls.vote(roll_id, player_id, vote_kind)
                if not res.get("ok"):
                    await websocket.send_json({"type": "loot_vote_error",
                                                "reason": res["reason"]})
                continue

            if mtype == "set_loot_rule":
                rule = (data.get("rule") or "").strip().lower()
                g = await groups.get_group_for(player_id)
                if not g:
                    await websocket.send_json({"type": "group_error",
                                                "reason": "not_in_group"})
                    continue
                res = await groups.set_loot_rule(g["id"], player_id, rule)
                if not res.get("ok"):
                    await websocket.send_json({"type": "group_error",
                                                "reason": res["reason"]})
                    continue
                await _broadcast_to_group(g["id"], {
                    "type": "loot_rule_changed",
                    "rule": res["rule"],
                })
                continue

            if mtype == "raid_trigger_manual":
                tier = int(data.get("tier", 1))
                g = await groups.get_group_for(player_id)
                if not g:
                    await websocket.send_json({"type": "group_error",
                                                "reason": "not_in_group"})
                    continue
                # Nur Leader darf manuelle Raids triggern
                if g["leader"] != player_id:
                    await websocket.send_json({"type": "group_error",
                                                "reason": "leader_only"})
                    continue
                res = await raid_director.trigger_manual_raid(
                    player_id, tier, world, npcs, manager, events,
                )
                if not res.get("ok"):
                    await websocket.send_json({"type": "raid_error",
                                                "reason": res["reason"],
                                                "remaining_s": res.get("remaining_s", 0)})
                    continue
                await _broadcast_to_group(g["id"], {
                    "type": "raid_started",
                    "tier": res["tier"],
                    "label": res["label"],
                    "spawned": res["spawned"],
                    "by": player_id,
                })
                continue

            # Welle 25: force_respawn — Sofort-Respawn aus dem Down-State
            if mtype == "force_respawn":
                if is_downed(player_id):
                    await _do_respawn(player_id, in_place=False)
                continue

            if mtype == "move":
                # Welle 25: Down-State blockt Bewegung
                if is_downed(player_id):
                    continue
                # Bewegung weckt aus dem Bett-Schlaf (Safety, falls Client doch
                # einen move sendet während noch 'resting').
                if needs.is_resting(player_id):
                    needs.set_resting(player_id, False)
                # Welle 25: Bewegung bricht aktiven Cast ab.
                if spell_caster.is_casting(player_id):
                    spell_caster.interrupt(player_id, "movement")
                x, y = data["x"], data["y"]
                # Multi-Floor-Dungeon-Validierung
                cur_world = await dungeon_instance.get_player_world(player_id)
                if cur_world != "overworld":
                    parsed = dungeon_instance.parse_world_id(cur_world)
                    if parsed is None:
                        continue
                    dungeon_id, floor_idx = parsed
                    floor = await dungeon_instance.get_floor(dungeon_id, floor_idx)
                    if floor is None:
                        continue
                    size = floor["size"]
                    tiles = floor["tiles"]
                    if not (0 <= x < size and 0 <= y < size
                            and dungeon_instance.is_walkable_tile(tiles[y][x])):
                        continue
                    manager.update_player(player_id, x, y)
                    await db.pool().execute(
                        "UPDATE players SET x = $1, y = $2, last_seen = NOW() "
                        "WHERE name = $3",
                        x, y, player_id,
                    )
                    # Versteckte Falle? → auslösen (Schaden + aufdecken).
                    _trap = await dungeon_instance.trap_at(dungeon_id, floor_idx, x, y)
                    if _trap:
                        dungeon_instance.mark_trap_triggered(dungeon_id, floor_idx, x, y)
                        _tdmg = _DUNGEON_TRAP_DMG.get(_trap, 12)
                        await damage_player(player_id, _tdmg)
                        if _trap == "poison_trap":
                            try: await status_effects.apply("player", player_id,
                                    "poisoned", magnitude=4, duration_seconds=20)
                            except Exception: pass
                        await websocket.send_json({
                            "type": "trap_triggered", "x": x, "y": y,
                            "kind": _trap, "dmg": _tdmg,
                            "text": _TRAP_LABEL.get(_trap, "💥 Falle ausgelöst!"),
                        })
                    # Auto-Pickup im Dungeon (analog Overworld) — Loot beim
                    # Drüberlaufen einsammeln.
                    for _it in await items.get_at(x, y):
                        _pk = await items.pickup(_it["id"], player_id)
                        if _pk is None:
                            continue
                        await manager.broadcast({
                            "type": "item_picked_up", "item_id": _it["id"],
                            "x": x, "y": y, "by": player_id})
                        if _pk["id"] != _it["id"]:
                            await websocket.send_json({
                                "type": "inventory_update", "item_id": _pk["id"],
                                "quantity": int(_pk.get("quantity", 1))})
                        else:
                            await websocket.send_json({"type": "inventory_add", "item": _pk})
                    # Stairs-Trigger: nur wenn der Spieler GENAU auf das
                    # Treppen-Tile getreten ist (kein endless re-trigger).
                    import dungeon_world as _dw
                    tile = tiles[y][x]
                    if tile == _dw.STAIRS_UP:
                        if floor_idx == 0:
                            # Floor 0 → Exit zur Overworld
                            ow = await dungeon_instance.exit_dungeon(player_id)
                            if ow:
                                manager.update_player(player_id, ow[0], ow[1])
                                cx_, cy_, _, _ = World.world_to_chunk(ow[0], ow[1])
                                new_chunks = await world.ensure_chunks_around(
                                    cx_, cy_, radius=CHUNK_SEND_RADIUS,
                                )
                                await websocket.send_json({
                                    "type": "dungeon_exit",
                                    "spawn": {"x": ow[0], "y": ow[1]},
                                    "chunks": new_chunks,
                                    "npcs": _overworld_npcs_near(ow[0], ow[1]),
                                })
                                await websocket.send_json({
                                    "type": "toast",
                                    "text": "🌅 Du verlässt das Dungeon.",
                                })
                        else:
                            # Floor >0 → vorherige Floor
                            new_floor = await dungeon_instance.change_floor(
                                player_id, dungeon_id, floor_idx - 1,
                            )
                            if new_floor:
                                manager.update_player(
                                    player_id,
                                    new_floor["spawn"][0], new_floor["spawn"][1],
                                )
                                dungeon = await dungeon_instance.get_dungeon(dungeon_id)
                                _extra = await _dungeon_floor_payload(dungeon_id, floor_idx - 1)
                                await websocket.send_json({
                                    "type":       "dungeon_floor_change",
                                    "dungeon_id": dungeon_id,
                                    "floor_idx":  floor_idx - 1,
                                    "floor_count":dungeon["floor_count"],
                                    "size":       new_floor["size"],
                                    "tiles":      new_floor["tiles"],
                                    "spawn":      {"x": new_floor["spawn"][0],
                                                   "y": new_floor["spawn"][1]},
                                    **_extra,
                                })
                                await websocket.send_json({
                                    "type": "toast",
                                    "text": f"🪜 Floor {floor_idx}/{dungeon['floor_count']} (rauf)",
                                })
                    elif tile == _dw.STAIRS_DOWN:
                        dungeon = await dungeon_instance.get_dungeon(dungeon_id)
                        if dungeon and floor_idx + 1 < dungeon["floor_count"]:
                            new_floor = await dungeon_instance.change_floor(
                                player_id, dungeon_id, floor_idx + 1,
                            )
                            if new_floor:
                                manager.update_player(
                                    player_id,
                                    new_floor["spawn"][0], new_floor["spawn"][1],
                                )
                                try: await dungeon_instance.populate_floor_mobs(
                                    dungeon_id, floor_idx + 1, npcs, manager)
                                except Exception:
                                    logging.exception("floor population (down) failed")
                                _extra = await _dungeon_floor_payload(dungeon_id, floor_idx + 1)
                                await websocket.send_json({
                                    "type":       "dungeon_floor_change",
                                    "dungeon_id": dungeon_id,
                                    "floor_idx":  floor_idx + 1,
                                    "floor_count":dungeon["floor_count"],
                                    "size":       new_floor["size"],
                                    "tiles":      new_floor["tiles"],
                                    "spawn":      {"x": new_floor["spawn"][0],
                                                   "y": new_floor["spawn"][1]},
                                    **_extra,
                                })
                                await websocket.send_json({
                                    "type": "toast",
                                    "text": f"🪜 Floor {floor_idx+2}/{dungeon['floor_count']} (runter)",
                                })
                    continue
                walkable = await world.is_walkable(x, y)
                if walkable and not structures.blocks(x, y):
                    # Chunk-Wechsel? → neue Chunks senden
                    old_cx, old_cy, _, _ = World.world_to_chunk(
                        manager.get_players()[player_id]["x"],
                        manager.get_players()[player_id]["y"],
                    )
                    new_cx, new_cy, _, _ = World.world_to_chunk(x, y)
                    manager.update_player(player_id, x, y)
                    if (old_cx, old_cy) != (new_cx, new_cy):
                        new_chunks = await world.ensure_chunks_around(
                            new_cx, new_cy, radius=CHUNK_SEND_RADIUS
                        )
                        await websocket.send_json({"type": "chunks", "chunks": new_chunks})
                        asyncio.create_task(_populate_chunks_bg(new_chunks))
                    await db.pool().execute(
                        "UPDATE players SET x = $1, y = $2, last_seen = NOW() "
                        "WHERE name = $3",
                        x, y, player_id,
                    )
                    await manager.broadcast({
                        "type": "player_moved",
                        "player_id": player_id,
                        "x": x,
                        "y": y,
                    }, exclude=player_id)
                    # Auto-Pickup: alle Items am Ziel-Tile aufheben
                    items_here = await items.get_at(x, y)
                    for it in items_here:
                        picked = await items.pickup(it["id"], player_id)
                        if picked is None:
                            continue
                        # item_id muss die ORIGINAL ground-item-id sein, damit das
                        # Frontend das richtige Sprite zerstört. Bei Stack-Merge ist
                        # picked["id"] der existing Inventar-Stack — nicht das Sprite.
                        await manager.broadcast({
                            "type":    "item_picked_up",
                            "item_id": it["id"],
                            "x":       x,
                            "y":       y,
                            "by":      player_id,
                        })
                        # Stack-Merge → inventory_update; sonst neue Row → inventory_add
                        if picked["id"] != it["id"]:
                            await websocket.send_json({
                                "type": "inventory_update",
                                "item_id": picked["id"],
                                "quantity": int(picked.get("quantity", 1)),
                            })
                        else:
                            await websocket.send_json({
                                "type": "inventory_add",
                                "item": picked,
                            })
                        # Quest-Hook: Item-Collect (fetch-Quests + multi-stage)
                        try:
                            updated_q = await quests.on_item_collected(player_id, picked["kind"], 1)
                            for q in updated_q:
                                await websocket.send_json({"type": "quest_progress", "quest": q})
                            stage_q = await quest_stages.on_player_event(
                                player_id, "collect",
                                {"item_kind": picked["kind"], "count": 1},
                            )
                            for q in stage_q:
                                await websocket.send_json({"type": "quest_progress", "quest": q})
                        except Exception:
                            logging.exception("quest hook (item) failed")
                    # Trap-Check: wenn Trap am Ziel-Tile, Schaden anwenden
                    s = structures.at(x, y)
                    if s is not None:
                        trap_dmg = combat.TRAP_DAMAGE.get(s["type"])
                        if trap_dmg is not None:
                            await manager.broadcast({
                                "type": "visual_effect",
                                "kind": "poison_cloud" if s["type"] == "poison_trap" else "hit_spark",
                                "x": x, "y": y,
                            })
                            await damage_player(player_id, trap_dmg)

            elif mtype == "sprint":
                # Frontend meldet Sprint-Zustand (SHIFT gehalten + in Bewegung).
                # run_stamina verbraucht dann Ausdauer/s und stoppt bei 0.
                needs.set_sprint(player_id, bool(data.get("on")))

            elif mtype == "wake":
                # Spieler wacht aktiv aus dem Bett-Schlaf auf.
                needs.set_resting(player_id, False)

            elif mtype == "dungeon_chest":
                # Dungeon-Schatzkiste öffnen (Auto-Loot direkt ins Inventar).
                cw = await dungeon_instance.get_player_world(player_id)
                parsed = dungeon_instance.parse_world_id(cw)
                if parsed is None:
                    continue
                _did, _fidx = parsed
                ccx, ccy = int(data.get("x", 0)), int(data.get("y", 0))
                _pp = manager.get_players().get(player_id)
                if _pp is None:
                    continue
                if max(abs(ccx - _pp["x"]), abs(ccy - _pp["y"])) > 1:
                    await websocket.send_json({"type": "toast", "text": "🧰 Zu weit weg."})
                    continue
                if not await dungeon_instance.chest_at(_did, _fidx, ccx, ccy):
                    continue
                dungeon_instance.mark_chest_opened(_did, _fidx, ccx, ccy)
                import chest_loot as _cl
                _dg = await dungeon_instance.get_dungeon(_did)
                _is_last = bool(_dg and _fidx >= _dg["floor_count"] - 1)
                _rolls = _cl.roll_chest_loot("boss" if _is_last else "dungeon")
                _found = []
                for _r in _rolls:
                    _kind = _r["kind"]
                    _qty = max(1, int(_r.get("quantity", 1)))
                    _ql = _r.get("quality", "normal")
                    if currency.is_currency(_kind):
                        await currency.add_coin(player_id, _kind, _qty)
                        _found.append(f"{_qty}× {_kind}")
                        continue
                    for _ in range(min(_qty, 20)):
                        _it = await items.create_for_player(_kind, player_id, _ql)
                        if _it:
                            await websocket.send_json({"type": "inventory_add", "item": _it})
                    _found.append(f"{_qty}× {_kind}" if _qty > 1 else _kind)
                await websocket.send_json({"type": "wallet_update",
                                            "copper": await currency.balance(player_id)})
                await websocket.send_json({"type": "dungeon_chest_opened", "x": ccx, "y": ccy})
                await websocket.send_json({"type": "toast",
                                            "text": "🧰 Schatz gefunden: " + ", ".join(_found[:6])})

            elif mtype == "place_structure":
                x, y, type_ = data["x"], data["y"], data["structure_type"]
                material = data.get("material", "stone")
                rotation = int(data.get("rotation", 0) or 0)
                if not await world.is_walkable(x, y):
                    continue
                # Spezial: Türen ersetzen eine vorhandene Wand am Ziel-Tile.
                # Material wird von der Wand übernommen — sonst passt der Wand-Rahmen
                # hinter der Tür nicht zur restlichen Mauer.
                if type_.startswith("door_"):
                    obj_here = structures.object_at(x, y)
                    if obj_here is not None and obj_here["type"] == "wall":
                        material = obj_here.get("material") or material
                        await structures.remove(x, y, layer="object")
                        await manager.broadcast({
                            "type": "structure_removed",
                            "x": x, "y": y, "layer": "object",
                        })
                    elif obj_here is not None:
                        await websocket.send_json({
                            "type": "toast",
                            "text": "🚪 Türen passen nur in Wände",
                        })
                        continue
                    else:
                        await websocket.send_json({
                            "type": "toast",
                            "text": "🚪 Türen brauchen eine Wand zum Einsetzen",
                        })
                        continue
                # Ausdauer beim Bauen: bei guter Versorgung (Hunger UND Durst
                # >=50%) gratis → erschöpft nie. Unter 50% kostet es Ausdauer;
                # ohne genug blockiert der Bau (Spieler merkt die Mangellage).
                _bn = await needs.get_needs(player_id)
                if _bn:
                    _supply = min(_bn["hunger"] / max(1, _bn["max_hunger"]),
                                  _bn["thirst"] / max(1, _bn["max_thirst"]))
                    if _supply < needs.SUPPLY_LOW_PCT:
                        if not await needs.use_stamina(player_id, needs.BUILD_STAMINA_COST):
                            await websocket.send_json({
                                "type": "toast",
                                "text": "🥵 Zu erschöpft zum Bauen — iss und trink erst etwas.",
                            })
                            continue
                        _bn2 = await needs.get_needs(player_id)
                        if _bn2:
                            await websocket.send_json({
                                "type":        "player_needs",
                                "hunger":      _bn2["hunger"],
                                "max_hunger":  _bn2["max_hunger"],
                                "stamina":     _bn2["stamina"],
                                "max_stamina": _bn2["max_stamina"],
                                "thirst":      _bn2["thirst"],
                                "max_thirst":  _bn2["max_thirst"],
                            })
                placed = await structures.place(x, y, type_, player_id, material=material, rotation=rotation)
                if placed is not None:
                    await manager.broadcast({
                        "type": "structure_placed",
                        "structure": placed,
                    })
                    # Welle 50: Effekt am gebauten Tile.
                    # farm_plot → Hoe (Acker hacken), sonst Hammer. Floor: still.
                    if type_ == "farm_plot":
                        await manager.broadcast({
                            "type": "visual_effect", "kind": "wp_hoe_soil",
                            "x": x, "y": y,
                        })
                    elif type_ != "floor":
                        await manager.broadcast({
                            "type": "visual_effect", "kind": "wp_build_hammer",
                            "x": x, "y": y,
                        })
                    # Auto-Spread: löst den "Streifen am Object-Tile"-Effekt, der
                    # entsteht weil Object-Sprites die Tile-Fläche nicht voll
                    # füllen — ohne Boden darunter sieht man den Untergrund.
                    # Welle 25: gilt jetzt für ALLE Objects (Wände, Möbel, Container,
                    # Stationen). Trigger: ein direkter Nachbar hat Floor → Indoor-
                    # Platzierung → Floor auch darunter. Outdoor-Bauten (Lagerfeuer
                    # auf Wiese, Grabstein etc.) bleiben ohne Floor weil kein
                    # Floor-Nachbar.
                    if type_ == "floor":
                        # Boden gesetzt → unter angrenzende Objects auch Boden
                        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
                            nx, ny = x + dx, y + dy
                            obj_neighbor = structures.object_at(nx, ny)
                            if obj_neighbor is None:
                                continue
                            if structures.floor_at(nx, ny) is not None:
                                continue
                            auto = await structures.place(
                                nx, ny, "floor", player_id, material=material
                            )
                            if auto is not None:
                                await manager.broadcast({
                                    "type": "structure_placed",
                                    "structure": auto,
                                })
                    else:
                        # Beliebiges Object platziert (wall/chest/bed/workbench/
                        # furnace/anvil/well/...). Wenn Nachbar-Tile Floor hat,
                        # Floor auch hier drunter setzen. Material vom Nachbar-
                        # Floor übernommen für konsistenten Look.
                        if structures.floor_at(x, y) is None:
                            adj_floor_mat = None
                            for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
                                fl = structures.floor_at(x + dx, y + dy)
                                if fl is not None:
                                    adj_floor_mat = fl.get("material") or "stone"
                                    break
                            if adj_floor_mat is not None:
                                auto = await structures.place(
                                    x, y, "floor", player_id, material=adj_floor_mat
                                )
                                if auto is not None:
                                    await manager.broadcast({
                                        "type": "structure_placed",
                                        "structure": auto,
                                    })
                    # Hammer-Tool gibt +50% Construction-XP
                    has_hammer = await has_tool_for_skill(player_id, "construction")
                    xp_amount = 12 if has_hammer else 8
                    xp_result = await skills.gain_xp(player_id, "construction", xp_amount)
                    if xp_result:
                        await websocket.send_json({"type": "skill_xp", **xp_result})
                    # Bestimmte Strukturen lösen ein KI-Welt-Event aus, mit Cooldown
                    if player_events.can_trigger(player_id, type_):
                        player_events.mark_triggered(player_id)
                        tile_id = await world.tile_at(x, y)
                        asyncio.create_task(
                            player_events.trigger(
                                player_id, type_, x, y, tile_id,
                                events, manager,
                            )
                        )

            elif mtype == "toggle_door":
                x, y = int(data.get("x", 0)), int(data.get("y", 0))
                # Reichweite: 1 Tile (orthogonal benachbart oder gleiches Tile)
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                if combat.chebyshev(player["x"], player["y"], x, y) > 1:
                    continue
                struct = structures.object_at(x, y)
                if struct is None:
                    continue
                t = struct["type"]
                # Map closed ↔ open
                DOOR_TOGGLE = {
                    "door_wood":      "door_wood_open",
                    "door_wood_open": "door_wood",
                    "door_iron":      "door_iron_open",
                    "door_iron_open": "door_iron",
                    "door_stone":     "door_stone_open",
                    "door_stone_open":"door_stone",
                    "garden_gate_ew_closed": "garden_gate_ew_open",
                    "garden_gate_ew_open":   "garden_gate_ew_closed",
                    "garden_gate_ns_closed": "garden_gate_ns_open",
                    "garden_gate_ns_open":   "garden_gate_ns_closed",
                }
                new_type = DOOR_TOGGLE.get(t)
                if new_type is None:
                    continue
                await db.pool().execute(
                    "UPDATE structures SET type = $1 WHERE id = $2", new_type, struct["id"],
                )
                struct["type"] = new_type
                await manager.broadcast({
                    "type": "structure_replaced",
                    "x": x, "y": y, "structure": struct,
                })

            elif mtype == "remove_structure":
                x, y = data["x"], data["y"]
                # Client kann optional einen Layer angeben, sonst object zuerst
                layer_pref = data.get("layer")
                removed = await structures.remove(x, y, layer=layer_pref)
                if removed is not None:
                    await manager.broadcast({
                        "type": "structure_removed",
                        "x": x, "y": y,
                        "layer": removed["layer"],
                    })

            elif mtype == "split_stack":
                item_id = int(data.get("item_id", 0))
                amount = int(data.get("amount", 0))
                result = await items.split_stack(item_id, player_id, amount)
                if result is not None:
                    updated, new_item = result
                    await websocket.send_json({
                        "type": "inventory_update",
                        "item_id": updated["id"],
                        "quantity": int(updated.get("quantity", 1)),
                    })
                    await websocket.send_json({
                        "type": "inventory_add",
                        "item": new_item,
                    })

            elif mtype == "merge_stacks":
                kind = str(data.get("kind", ""))
                quality_str = str(data.get("quality", "normal"))
                if not kind:
                    continue
                result = await items.merge_stacks(player_id, kind, quality_str)
                if result is not None:
                    # Full-refresh damit Frontend die gelöschten Rows + neue Quantities sieht
                    new_inv = await items.get_inventory(player_id)
                    await websocket.send_json({
                        "type": "inventory_full_refresh",
                        "inventory": new_inv,
                    })

            elif mtype == "equip_item":
                item_id = int(data.get("item_id", 0))
                to_slot = data.get("to_slot")  # Welle 23 — Dual-Wield optional
                item = await items.equip(item_id, player_id, to_slot=to_slot)
                if item is not None:
                    await websocket.send_json({"type": "inventory_update", "item": item})
                    await _send_attrs_update(websocket, player_id)
                else:
                    await websocket.send_json({"type": "toast",
                        "text": "Off-Hand: 2H-Waffe kann nicht dual-equipped werden."})

            elif mtype == "unequip_item":
                item_id = int(data.get("item_id", 0))
                item = await items.unequip(item_id, player_id)
                if item is not None:
                    await websocket.send_json({"type": "inventory_update", "item": item})
                    await _send_attrs_update(websocket, player_id)

            elif mtype == "allocate_attr":
                attr = (data.get("attr") or "").strip()
                n = int(data.get("n", 1) or 1)
                if attr and -50 <= n <= 50:
                    import player_stats as _ps
                    result = await _ps.allocate_point(player_id, attr, n)
                    if result and "ok" in result:
                        await _send_attrs_update(websocket, player_id)
                    elif result and "error" in result:
                        await websocket.send_json({
                            "type": "toast",
                            "text": f"Allokation: {result['error']}",
                        })

            elif mtype == "use_item":
                item_id = int(data.get("item_id", 0))
                # Item vor dem Löschen lesen für Effekt-Lookup
                cur = await db.pool().fetchrow(
                    "SELECT kind FROM items WHERE id = $1 AND owner = $2", item_id, player_id
                )
                kind = cur["kind"] if cur else None
                consumed = await items.consume(item_id, player_id)
                if consumed is None:
                    continue
                if consumed.get("stack_remaining", 0) > 0:
                    # Stack hat noch Items übrig: nur quantity aktualisieren
                    await websocket.send_json({
                        "type": "inventory_update",
                        "item_id": consumed["id"],
                        "quantity": consumed["stack_remaining"],
                    })
                else:
                    await websocket.send_json({
                        "type": "inventory_remove",
                        "item_id": consumed["id"],
                        "consumed": True,
                    })
                effect = combat.USE_EFFECTS.get(kind or "")
                if effect:
                    # Medical-Talent-Bonus
                    talent_med = await talents.aggregate_effects(player_id)
                    heal_mult = 1 + talent_med.get("medical_heal_bonus", 0)
                    if "hp" in effect:
                        await heal_player(player_id, int(effect["hp"] * heal_mult))
                    if "mana" in effect:
                        await restore_mana(player_id, effect["mana"])
                    if "stamina" in effect:
                        new_state = await needs.restore_stamina(player_id, int(effect["stamina"]))
                        if new_state is not None:
                            await websocket.send_json({"type": "player_needs", **new_state})
                    # Rejuvenation: Body-Parts mitheilen
                    part_heal = int(talent_med.get("medical_part_heal", 0))
                    if part_heal > 0:
                        await body_parts.heal_all_parts(player_id)
                    # Blessed-Hands: 30% chance auf blessed-status
                    if (talent_med.get("medical_blessed_chance", 0) > 0
                            and __import__('random').random() < talent_med["medical_blessed_chance"]):
                        try:
                            await status_effects.apply("player", player_id, "blessed", 3, 15)
                            effs = await status_effects.list_for_target("player", player_id)
                            await websocket.send_json({"type": "status_effects", "effects": effs})
                        except Exception:
                            pass
                    # Medical-XP für Heiltrank-Anwendung
                    if effect.get("hp", 0) >= 10 or kind == "mana_potion":
                        med_xp = await skills.gain_xp(player_id, "medical", 8)
                        if med_xp:
                            await websocket.send_json({"type": "skill_xp", **med_xp})
                # Food: füllt Hunger — mit Cooking-Skill-Bonus + Master-Chef-Heal
                if kind and needs.is_food(kind):
                    cooking_lvl = await skills.get_skill_level(player_id, "cooking")
                    base_val = needs.food_value(kind)
                    eff_val = int(base_val * skills.cooking_quality_bonus(cooking_lvl))
                    new_state = await needs.restore_hunger(player_id, eff_val)
                    if new_state is not None:
                        await websocket.send_json({"type": "player_needs", **new_state})
                # Welle 17: viele Foods geben auch Durst-Restore (Gurke, Tomate, Trauben, ...)
                if kind:
                    t_val = needs.thirst_value(kind)
                    if t_val > 0:
                        t_state = await needs.restore_thirst(player_id, t_val)
                        if t_state is not None:
                            await websocket.send_json({"type": "player_needs", **t_state})
                # Welle 22: Forschungs-Items → Pool füllen
                if kind in ("research_scroll", "research_tome"):
                    gain = 5 if kind == "research_scroll" else 20
                    new_pool = await research.award_points(player_id, gain, f"item:{kind}")
                    await websocket.send_json({
                        "type": "research_pool_update", "pool": new_pool,
                        "gained": gain, "reason": f"📜 {kind}",
                    })
                    # Master-Chef-Talent: zusätzlich 10 HP bei gegarten Mahlzeiten
                    talent_eff_c = await talents.aggregate_effects(player_id)
                    if (kind in ("bread", "cooked_meat")
                            and talent_eff_c.get("cooking_heal_bonus", 0) > 0):
                        await heal_player(player_id, int(talent_eff_c["cooking_heal_bonus"]))
                # Welle 32: Dungeon-Key-Items — spawnt Tier-Dungeon an Player-Pos
                key_tier = dungeon_tiers.tier_for_key_item(kind or "")
                if key_tier is not None:
                    player_pos = manager.get_players().get(player_id)
                    if player_pos:
                        # Walkable-Spot in der Nähe finden
                        sx, sy = player_pos["x"], player_pos["y"]
                        spawn_xy = None
                        for dx, dy in [(0,0),(1,0),(-1,0),(0,1),(0,-1),(2,0),(0,2)]:
                            tx, ty = sx + dx, sy + dy
                            if await world.is_walkable(tx, ty) and structures.at(tx, ty) is None:
                                spawn_xy = (tx, ty); break
                        if spawn_xy:
                            meta = await dungeon_instance.spawn_dungeon(
                                spawn_xy[0], spawn_xy[1], key_tier,
                            )
                            s = await structures.place(
                                spawn_xy[0], spawn_xy[1], "stairs_down", "system",
                                material="stone", durability=999,
                            )
                            if s:
                                await manager.broadcast({
                                    "type": "structure_placed", "structure": s,
                                })
                            label = dungeon_tiers.TIER_LABEL.get(key_tier, "Verlies")
                            await manager.broadcast({
                                "type": "world_event",
                                "kind": "dungeon_spawned",
                                "text": f"🏚️ {player_id} öffnet ein {label}!",
                                "x": spawn_xy[0], "y": spawn_xy[1],
                            })
                            await websocket.send_json({
                                "type": "toast",
                                "text": f"🔮 {label} öffnet sich vor dir!",
                            })
                        else:
                            await websocket.send_json({
                                "type": "toast",
                                "text": "⛔ Kein freier Platz für das Verlies",
                            })

            elif mtype == "pick_item":
                # Expliziter Pickup: Spieler klickt auf Item am Boden in Reichweite (≤1 Tile).
                item_id = int(data.get("item_id", 0))
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                ground = await db.pool().fetchrow(
                    "SELECT x, y FROM items WHERE id = $1 AND owner IS NULL",
                    item_id,
                )
                if ground is None:
                    continue  # schon weg
                if combat.chebyshev(player["x"], player["y"], int(ground["x"]), int(ground["y"])) > 1:
                    continue  # zu weit weg (Sanity-Check — Frontend prüft auch)
                # Loot-Roll-Lock: Item ist gerade in einem Need/Greed-Roll →
                # nur der ausgelobte Gewinner darf aufheben.
                if loot_rolls.is_locked(item_id):
                    winner = loot_rolls.allowed_picker(item_id)
                    if winner is None:
                        await websocket.send_json({"type": "toast",
                                                    "text": "⏳ Loot-Roll läuft noch"})
                        continue
                    if winner != player_id:
                        await websocket.send_json({"type": "toast",
                                                    "text": f"🔒 Für {winner} reserviert"})
                        continue
                picked = await items.pickup(item_id, player_id)
                if picked is None:
                    continue
                await manager.broadcast({"type": "item_picked_up", "item_id": item_id})
                # Wenn in einen existierenden Stack gemergt: inventory_update mit neuer qty.
                # Sonst (neue Row im Inventar): inventory_add mit dem ganzen Item.
                if picked["id"] != item_id:
                    await websocket.send_json({
                        "type": "inventory_update",
                        "item_id": picked["id"],
                        "quantity": int(picked.get("quantity", 1)),
                    })
                else:
                    await websocket.send_json({
                        "type": "inventory_add",
                        "item": picked,
                    })

            elif mtype == "drop_item":
                item_id = int(data.get("item_id", 0))
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                dropped = await items.drop(item_id, player_id, player["x"], player["y"])
                if dropped is None:
                    continue
                await websocket.send_json({
                    "type": "inventory_remove",
                    "item_id": dropped["id"],
                })
                await manager.broadcast({
                    "type": "item_spawned",
                    "item": dropped,
                })

            elif mtype == "attack_npc":
                npc_id = int(data.get("npc_id", 0))
                npc = npcs.get(npc_id)
                if npc is None:
                    continue
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                weapon = await get_equipped_weapon_kind(player_id)
                weapon_quality = "normal"
                weapon_rolled_stats = None
                if weapon:
                    qrow = await db.pool().fetchrow(
                        "SELECT quality, rolled_stats FROM items WHERE owner = $1 "
                        "AND equipped_slot = 'weapon' LIMIT 1", player_id,
                    )
                    if qrow:
                        weapon_quality = qrow["quality"]
                        rs = qrow["rolled_stats"]
                        if rs:
                            import json as _json
                            weapon_rolled_stats = _json.loads(rs) if isinstance(rs, str) else rs
                combat_level = await skills.get_skill_level(player_id, "combat")
                # Range-Check: bei Ranged-Waffen größere Reichweite
                import item_stats as _is, random as _r
                attack_range = max(combat.ATTACK_RANGE, _is.weapon_range(weapon))
                if combat.chebyshev(player["x"], player["y"], npc["x"], npc["y"]) > attack_range:
                    continue
                # Ausdauer-Kosten pro Schlag — ALLE Waffen (2H teurer als 1H/Bogen).
                # Zu wenig Ausdauer → halbierter Schaden statt Block, damit der
                # Spieler nie komplett wehrlos ist.
                _heavy_dmg_penalty = 1.0
                _atk_cost = needs.attack_stamina_cost(weapon)
                if not await needs.use_stamina(player_id, _atk_cost):
                    _heavy_dmg_penalty = 0.5
                    await websocket.send_json({
                        "type": "toast",
                        "text": "🥵 Erschöpft — der Hieb hat keinen Schwung",
                    })
                else:
                    # Ausdauer-Balken sofort aktualisieren (Sekunden-Loop wäre träge)
                    _atk_needs = await needs.get_needs(player_id)
                    if _atk_needs:
                        await websocket.send_json({
                            "type":        "player_needs",
                            "hunger":      _atk_needs["hunger"],
                            "max_hunger":  _atk_needs["max_hunger"],
                            "stamina":     _atk_needs["stamina"],
                            "max_stamina": _atk_needs["max_stamina"],
                            "thirst":      _atk_needs["thirst"],
                            "max_thirst":  _atk_needs["max_thirst"],
                        })
                # Talent-Effekte für Combat anwenden
                talent_effects = await talents.aggregate_effects(player_id)
                # Crit-Chance-Boost durch Talent
                crit_roll = _r.random() - talent_effects.get("combat_crit_chance", 0)
                dmg, is_crit = combat.calc_player_damage(
                    weapon_kind=weapon,
                    weapon_quality=weapon_quality,
                    combat_level=combat_level,
                    rng_roll=crit_roll,
                    rolled_stats=weapon_rolled_stats,
                )
                # Welle 23 — Dual-Wield: zweite Waffe in offhand (shield-slot)?
                # Zusätzlicher Hieb mit 0.6× damage, eigener crit-roll.
                offhand_row = await db.pool().fetchrow(
                    "SELECT kind, quality, rolled_stats FROM items WHERE owner = $1 "
                    "AND equipped_slot = 'shield' LIMIT 1", player_id,
                )
                if offhand_row and offhand_row["kind"] in _is.WEAPON_STATS:
                    oh_rs = None
                    if offhand_row["rolled_stats"]:
                        import json as _json
                        oh_rs = (_json.loads(offhand_row["rolled_stats"])
                                 if isinstance(offhand_row["rolled_stats"], str)
                                 else offhand_row["rolled_stats"])
                    oh_dmg, oh_crit = combat.calc_player_damage(
                        weapon_kind=offhand_row["kind"],
                        weapon_quality=offhand_row["quality"],
                        combat_level=combat_level,
                        rng_roll=_r.random(),
                        rolled_stats=oh_rs,
                    )
                    # 60% damage des Hauptschlags durch Off-Hand
                    dmg += int(round(oh_dmg * 0.6))
                # Damage-Modifier durch Talente
                wclass = _is.weapon_class(weapon)
                if wclass == "ranged":
                    dmg = int(dmg * (1 + talent_effects.get("combat_ranged_damage", 0)))
                else:
                    dmg = int(dmg * (1 + talent_effects.get("combat_melee_damage", 0)))
                # Crit-Damage-Boost
                if is_crit and talent_effects.get("combat_crit_damage", 0) > 0:
                    dmg = int(dmg * (1 + talent_effects["combat_crit_damage"]))
                # Berserker: unter 30% HP
                prow = await db.pool().fetchrow(
                    "SELECT hp, max_hp FROM players WHERE name = $1", player_id,
                )
                if prow and talent_effects.get("combat_berserker", 0) > 0:
                    if prow["hp"] / max(1, prow["max_hp"]) < 0.3:
                        dmg = int(dmg * (1 + talent_effects["combat_berserker"]))
                # Lifesteal
                if talent_effects.get("combat_lifesteal", 0) > 0:
                    heal_amount = int(dmg * talent_effects["combat_lifesteal"])
                    if heal_amount > 0:
                        await heal_player(player_id, heal_amount)
                # Arm-Verletzung reduziert ausgeteilten Schaden
                bp = await body_parts.get_body_parts(player_id)
                if bp:
                    dmg = int(dmg * body_parts.arm_damage_multiplier(bp["arms"]))
                    if dmg < 1:
                        dmg = 1
                # Stamina-Penalty: 2H-Waffe ohne genug Ausdauer → halber Hieb
                if _heavy_dmg_penalty < 1.0:
                    dmg = max(1, int(dmg * _heavy_dmg_penalty))
                # Welle 40: Waffen-spezifischer Attack-Visual
                weapon_fx = {
                    "sword": "sword_slash", "greatsword": "sword_slash", "dagger": "sword_slash",
                    "axe": "axe_swing", "scythe": "axe_swing",
                    "mace": "mace_hit",
                    "bow": "arrow_hit", "crossbow": "arrow_hit", "throwing_knife": "arrow_hit",
                    "staff": "magic_circle", "wand": "magic_circle",
                }.get(weapon, "hit_spark")
                await manager.broadcast({
                    "type": "visual_effect", "kind": weapon_fx,
                    "x": npc["x"], "y": npc["y"],
                })
                # Welle 15: Monster-Resists/Defense anwenden
                # armor_pen aus Waffen-Stat (z.B. mace hat 0.25)
                _w_cfg = _is.WEAPON_STATS.get(weapon, {}) if weapon else {}
                _armor_pen = _w_cfg.get("armor_pen", 0.0)
                dmg = combat.apply_creature_resists(
                    npc["kind"], dmg,
                    dmg_type=combat.weapon_damage_type(weapon),
                    armor_pen=_armor_pen,
                )
                result = await npcs.damage(npc_id, dmg)
                if result is None:
                    drop_x, drop_y = await _find_drop_xy(npc["x"], npc["y"])
                    await _drop_loot_for_npc(player_id, npc, drop_x, drop_y)
                    import npc_worker as _nw
                    # Welle 23-F: Camp-Cooldown — wenn der letzte
                    # Bandit/Robber/Thief im chunk tot ist, mark als cleared.
                    if npc["kind"] in _nw.CAMP_ONLY_KINDS:
                        try:
                            from world import CHUNK_SIZE as _CS
                            ccx, ccy = npc["x"] // _CS, npc["y"] // _CS
                            still_alive = any(
                                (n["x"] // _CS == ccx and n["y"] // _CS == ccy
                                 and n["kind"] in _nw.CAMP_ONLY_KINDS
                                 and n["id"] != npc_id)
                                for n in npcs.all()
                            )
                            if not still_alive:
                                import region_difficulty as _rd
                                await _rd.mark_zone_cleared(ccx, ccy, "bandit_camp")
                        except Exception:
                            logging.exception("Camp-cleared-tracking failed")
                    await manager.broadcast({
                        "type":   "npc_died",
                        "npc_id": npc_id,
                        "killed_by": player_id,
                        "name":   npc["name"],
                    })
                    # Quest-Hook: Creature-Kill (single + multi-stage)
                    try:
                        updated_q = await quests.on_creature_killed(player_id, npc["kind"], 1)
                        for q in updated_q:
                            await websocket.send_json({"type": "quest_progress", "quest": q})
                        stage_q = await quest_stages.on_player_event(
                            player_id, "kill",
                            {"creature_kind": npc["kind"], "count": 1},
                        )
                        for q in stage_q:
                            await websocket.send_json({"type": "quest_progress", "quest": q})
                    except Exception:
                        logging.exception("quest hook (kill) failed")
                    # Welle 27: Faction-Reputation-Effekt
                    try:
                        fid = factions.faction_for_kind(npc["kind"])
                        if fid:
                            is_hostile_kind = npc["kind"] in combat.CREATURE_KINDS
                            # Hostile-Kill = +5 für Verbündete, Friendly-Kill = -25
                            delta = -25 if not is_hostile_kind else -10
                            result = await factions.apply_action(
                                player_id, fid, delta,
                                f"killed:{npc['kind']}:{npc_id}",
                            )
                            # Toast für Tier-Wechsel
                            for fname, old, new, tc in result["direct"]:
                                if tc:
                                    await websocket.send_json({
                                        "type": "toast",
                                        "text": f"⚔️ {fname}: {factions.reputation_tier(new)} ({new:+d})",
                                    })
                            # Reputation-Update an Client schicken
                            await websocket.send_json({
                                "type": "factions_update",
                                "factions": await factions.list_all_reputations(player_id),
                            })
                    except Exception:
                        logging.exception("faction hook (kill) failed")
                else:
                    await manager.broadcast({
                        "type":   "npc_damaged",
                        "npc_id": npc_id,
                        "hp":     result["hp"],
                        "max_hp": result["max_hp"],
                        "dmg":    dmg,
                        "crit":   is_crit,
                        "by":     player_id,
                    })
                # Welle 31: XP-Split bei Gruppe — alle Members im 15-Tile-Radius
                _xp_amount = max(2, dmg // 2)
                _xp_shares = await _gain_combat_xp_with_share(
                    player_id, _xp_amount, npc["x"], npc["y"]
                )
                for _pid, _xr in _xp_shares:
                    if _pid == player_id:
                        await websocket.send_json({"type": "skill_xp", **_xr})
                    else:
                        _ws_m = manager.connections.get(_pid)
                        if _ws_m is not None:
                            try:
                                await _ws_m.send_json({"type": "skill_xp", **_xr})
                            except Exception:
                                pass

            elif mtype == "cast_spell":
                # Welle 25: Neuer Pfad — spell_id statt item_id (Hotbar/Spellbook-Cast).
                spell_id = data.get("spell_id")
                if spell_id:
                    spell = spells.get(spell_id)
                    if not spell:
                        continue
                    # Spell gelernt?
                    learned = await db.pool().fetchval(
                        "SELECT 1 FROM learned_spells WHERE player_name = $1 AND spell_kind = $2",
                        player_id, spell_id,
                    )
                    if not learned:
                        await websocket.send_json({
                            "type": "toast", "text": "Du beherrschst diesen Zauber nicht.",
                        })
                        continue
                    # Mana + Skill-Level + Position holen
                    pstate = await db.pool().fetchrow(
                        "SELECT mana, max_mana FROM players WHERE name = $1", player_id,
                    )
                    if pstate is None:
                        continue
                    magic_lvl = await skills.get_skill_level(player_id, "magic")
                    pinfo = manager.get_players().get(player_id, {})
                    px, py = pinfo.get("x", 0), pinfo.get("y", 0)
                    target = {
                        "x":      data.get("target_x"),
                        "y":      data.get("target_y"),
                        "npc_id": data.get("target_npc_id"),
                    }
                    result = await spell_caster.start_cast(
                        player_id, spell_id, target,
                        current_mana=int(pstate["mana"]),
                        current_x=px, current_y=py,
                        magic_level=magic_lvl,
                    )
                    if not result.get("ok"):
                        reason = result.get("reason")
                        msg_text = {
                            "no_mana":         f"Nicht genug Mana ({result.get('needed', 0)}).",
                            "cooldown":        f"Noch nicht bereit ({result.get('remaining', 0):.1f}s).",
                            "already_casting": "Du wirkst bereits einen Zauber.",
                            "skill":           f"Magie-Level {result.get('needed', 0)} benötigt.",
                            "out_of_range":    f"Zu weit weg (max {result.get('max', 0)} Felder).",
                            "unknown_spell":   "Unbekannter Zauber.",
                        }.get(reason, f"Cast fehlgeschlagen: {reason}")
                        await websocket.send_json({"type": "toast", "text": msg_text})
                        continue
                    # Mana abziehen
                    new_mana = pstate["mana"] - int(spell.get("mana_cost", 0))
                    await db.pool().execute(
                        "UPDATE players SET mana = $1 WHERE name = $2",
                        new_mana, player_id,
                    )
                    await websocket.send_json({
                        "type": "player_mana", "mana": new_mana,
                        "max_mana": pstate["max_mana"],
                    })
                    # Cast-Started an Client → UI zeigt Cast-Bar
                    await websocket.send_json({
                        "type":         "cast_started",
                        "spell_id":     spell_id,
                        "cast_time_ms": result["cast_time_ms"],
                    })
                    continue  # Skip legacy item-path

                # ─── Legacy item-based cast (spell_book/scroll/rune_stone) ───
                item_id = int(data.get("item_id", 0))
                row = await db.pool().fetchrow(
                    "SELECT kind FROM items WHERE id = $1 AND owner = $2",
                    item_id, player_id,
                )
                if row is None:
                    continue
                spell = combat.SPELLS.get(row["kind"])
                if spell is None:
                    continue
                pstate = await db.pool().fetchrow(
                    "SELECT mana, max_mana FROM players WHERE name = $1", player_id
                )
                if pstate is None or pstate["mana"] < spell["mana"]:
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"Nicht genug Mana ({spell['mana']} benötigt, {pstate['mana'] if pstate else 0} vorhanden)",
                    })
                    continue
                player_pos = manager.get_players().get(player_id)
                if player_pos is None:
                    continue

                # Effekt: Heal self
                if spell.get("heal_self", 0) > 0:
                    await heal_player(player_id, spell["heal_self"])

                # Effekt: Damage
                if spell.get("damage", 0) > 0:
                    candidates = [n for n in npcs.all() if n["kind"] in combat.CREATURE_KINDS]
                    if candidates:
                        target = min(
                            candidates,
                            key=lambda n: combat.chebyshev(player_pos["x"], player_pos["y"], n["x"], n["y"]),
                        )
                        dist = combat.chebyshev(player_pos["x"], player_pos["y"], target["x"], target["y"])
                        if dist <= spell["range"]:
                            aoe = spell.get("aoe_radius", 0)
                            if aoe > 0:
                                targets = [
                                    n for n in candidates
                                    if combat.manhattan(target["x"], target["y"], n["x"], n["y"]) <= aoe
                                ]
                            else:
                                targets = [target]
                            # Welle 28: Spell → Pro-Animation-Kind. Map nutzt die
                            # neuen 256×256 / 512×512 Spritesheet-Animations
                            # aus assets/animations/professional/combat_magic/.
                            spell_fx = {
                                "spell_book":         "fireball_explosion",
                                "scroll":             "hit_spark",
                                "rune_stone":         "heal_pulse",
                                # Welle 29d — neue Spell-Visuals
                                "ice_scroll":         "ice_spell",
                                "wind_slash_scroll":  "wind_slash_spell",
                                "holy_shield_scroll": "holy_shield_aura",
                            }.get(row["kind"], "fireball_explosion")
                            await manager.broadcast({
                                "type": "visual_effect", "kind": spell_fx,
                                "x": target["x"], "y": target["y"],
                            })
                            # Welle 15: Spell-Damage-Typ je nach Spell-Item
                            _spell_dmg_type = {
                                "spell_book":         "fire",
                                "scroll":             "lightning",
                                "rune_stone":         "magic",
                                "ice_scroll":         "ice",
                                "wind_slash_scroll":  "magic",
                                "holy_shield_scroll": "magic",
                            }.get(row["kind"], "magic")
                            for t in targets:
                                _final = combat.apply_creature_resists(
                                    t["kind"], spell["damage"], dmg_type=_spell_dmg_type
                                )
                                result = await npcs.damage(t["id"], _final)
                                if result is None:
                                    drop_x, drop_y = await _find_drop_xy(t["x"], t["y"])
                                    await _drop_loot_for_npc(player_id, t, drop_x, drop_y)
                                    await manager.broadcast({
                                        "type": "npc_died", "npc_id": t["id"],
                                        "killed_by": player_id, "name": t["name"],
                                    })
                                    # Quest-Hook auch bei Direct-Spell-Kills
                                    try:
                                        updated_q = await quests.on_creature_killed(
                                            player_id, t["kind"], 1)
                                        for q in updated_q:
                                            await websocket.send_json(
                                                {"type": "quest_progress", "quest": q})
                                        stage_q = await quest_stages.on_player_event(
                                            player_id, "kill",
                                            {"creature_kind": t["kind"], "count": 1},
                                        )
                                        for q in stage_q:
                                            await websocket.send_json(
                                                {"type": "quest_progress", "quest": q})
                                    except Exception:
                                        logging.exception("quest hook (direct-spell-kill) failed")
                                    # Combat-XP-Share auch bei Direct-Spell-Kills
                                    try:
                                        _shares = await _gain_combat_xp_with_share(
                                            player_id, max(2, _final // 2), t["x"], t["y"]
                                        )
                                        for _pid, _xr in _shares:
                                            ws_t = manager.connections.get(_pid)
                                            if ws_t is not None:
                                                try: await ws_t.send_json({"type": "skill_xp", **_xr})
                                                except Exception: pass
                                    except Exception:
                                        logging.exception("xp share (direct-spell-kill) failed")
                                else:
                                    await manager.broadcast({
                                        "type": "npc_damaged", "npc_id": t["id"],
                                        "hp": result["hp"], "max_hp": result["max_hp"],
                                        "dmg": spell["damage"], "by": player_id,
                                    })
                        else:
                            await websocket.send_json({
                                "type": "toast", "text": "Kein Ziel in Reichweite",
                            })
                    else:
                        await websocket.send_json({
                            "type": "toast", "text": "Kein Ziel in Sicht",
                        })

                # Mana abziehen
                new_mana = pstate["mana"] - spell["mana"]
                await db.pool().execute(
                    "UPDATE players SET mana = $1 WHERE name = $2", new_mana, player_id
                )
                await websocket.send_json({
                    "type": "player_mana", "mana": new_mana, "max_mana": pstate["max_mana"],
                })

                # Spell-Item verbrauchen wenn nötig
                if spell.get("consume"):
                    await db.pool().execute("DELETE FROM items WHERE id = $1", item_id)
                    await websocket.send_json({"type": "inventory_remove", "item_id": item_id})
                # Selbst-Status-Effekt (Welle 11)
                self_eff = spell.get("self_effect")
                if self_eff:
                    try:
                        applied = await status_effects.apply(
                            "player", player_id,
                            self_eff["effect"], self_eff["magnitude"],
                            self_eff["duration"],
                        )
                        effs = await status_effects.list_for_target("player", player_id)
                        await websocket.send_json({"type": "status_effects", "effects": effs})
                    except Exception:
                        logging.exception("self_effect apply failed")
                # Magic-XP
                xp_result = await skills.gain_xp(player_id, "magic", 5 + spell["mana"] // 2)
                if xp_result:
                    await websocket.send_json({"type": "skill_xp", **xp_result})

            elif mtype == "attack_structure":
                # Welle 25: Spieler greift Struktur an (eigene Wand zerstören
                # in Build-Mode geht weiter via remove_structure Long-Press).
                # Hier: feindliche Strukturen (Bandit-Camp-Strukturen, fremde
                # Wände) angreifen mit der ausgerüsteten Waffe.
                x, y = int(data.get("x", -1)), int(data.get("y", -1))
                s = structures.object_at(x, y) or structures.floor_at(x, y)
                if s is None:
                    continue
                from structures import is_combat_structure as _is_cs
                if not _is_cs(s["type"]):
                    await websocket.send_json({
                        "type": "toast", "text": "Diese Struktur kann nicht angegriffen werden.",
                    })
                    continue
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                # Range-Check
                weapon = await get_equipped_weapon_kind(player_id)
                import item_stats as _is_struct
                attack_range = max(combat.ATTACK_RANGE, _is_struct.weapon_range(weapon))
                if combat.chebyshev(player["x"], player["y"], x, y) > attack_range:
                    await websocket.send_json({"type": "toast", "text": "Zu weit weg."})
                    continue
                # Damage-Calc
                weapon_quality = "normal"
                if weapon:
                    qrow = await db.pool().fetchrow(
                        "SELECT quality FROM items WHERE owner = $1 "
                        "AND equipped_slot = 'weapon' LIMIT 1", player_id)
                    if qrow:
                        weapon_quality = qrow["quality"]
                combat_level = await skills.get_skill_level(player_id, "combat")
                raw_dmg, is_crit = combat.calc_player_damage(
                    weapon_kind=weapon, weapon_quality=weapon_quality,
                    combat_level=combat_level, rng_roll=0.5,
                )
                # Material-Resistance anwenden (Stein vs Edge etc.)
                dmg_class = structures.player_damage_class(weapon)
                final_dmg = structures.apply_material_resist(s["material"], raw_dmg, dmg_class)
                result = await structures.damage_structure(x, y, amount=final_dmg)
                if result is None:
                    # Kollabiert
                    await manager.broadcast({
                        "type": "structure_removed", "x": x, "y": y,
                    })
                    # Splittert in rubble wenn vorher eine Wand/Tür war
                    if s["type"] in ("wall", "door_wood", "door_iron", "door_stone",
                                      "door_reinforced", "barn_large", "barn_small",
                                      "stable", "granary"):
                        rubble = await structures.place(
                            x, y, "rubble", "system",
                            material=s["material"], durability=2,
                        )
                        if rubble:
                            await manager.broadcast({
                                "type": "structure_placed", "structure": rubble,
                            })
                else:
                    await manager.broadcast({
                        "type": "structure_damaged",
                        "x": x, "y": y,
                        "durability":     result["durability"],
                        "max_durability": result["max_durability"],
                        "dmg":            final_dmg,
                        "by":             player_id,
                    })
                # Combat-XP fürs Angreifen — kleiner Bonus, hauptsächlich für
                # Strukturen-die-zurückschlagen-System (kommt später)
                try:
                    await skills.gain_xp(player_id, "combat", 2)
                except Exception:
                    pass

            elif mtype == "repair_structure":
                # Welle 25: Mit equipped hammer + 1 Material gleicher Sorte
                # die Struktur reparieren. +8 HP pro Klick, cap = max_durability.
                x, y = int(data.get("x", -1)), int(data.get("y", -1))
                s = structures.object_at(x, y) or structures.floor_at(x, y)
                if s is None:
                    continue
                from structures import is_combat_structure as _is_cs
                if not _is_cs(s["type"]):
                    continue
                if not structures.can_modify(player_id, s):
                    await websocket.send_json({
                        "type": "toast", "text": "🔒 Du bist nicht der Eigentümer.",
                    })
                    continue
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                if combat.chebyshev(player["x"], player["y"], x, y) > 1:
                    await websocket.send_json({"type": "toast", "text": "🤚 Zu weit weg."})
                    continue
                if s["durability"] >= s.get("max_durability", s["durability"]):
                    await websocket.send_json({"type": "toast", "text": "✨ Bereits voll repariert."})
                    continue
                # Hammer-Check
                tool = await db.pool().fetchrow(
                    "SELECT id FROM items WHERE owner = $1 AND equipped_slot = 'tool' "
                    "AND kind = 'hammer' LIMIT 1", player_id,
                )
                if not tool:
                    await websocket.send_json({"type": "toast", "text": "🔨 Hammer ausrüsten."})
                    continue
                # Material verfügbar? consume_one() handelt Stack-Logik selbst.
                needed_mat = s["material"]   # 'stone', 'wood', oder 'straw'
                consumed = await items.consume_one(player_id, needed_mat)
                if not consumed:
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"📦 Du brauchst 1× {needed_mat} zum Reparieren.",
                    })
                    continue
                result = await structures.repair_structure(x, y, amount=8)
                if result is not None:
                    await manager.broadcast({
                        "type": "structure_repaired",
                        "x": x, "y": y,
                        "durability":     result["durability"],
                        "max_durability": result["max_durability"],
                        "by":             player_id,
                    })
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"🔨 +8 HP — {result['durability']}/{result['max_durability']}",
                    })
                # Construction-XP
                try:
                    await skills.gain_xp(player_id, "construction", 3)
                except Exception:
                    pass

            elif mtype == "upgrade_structure":
                # Welle 25: Wand-Material aufwerten (straw→wood→stone).
                # Voraussetzungen: eigene Struktur (can_modify), Combat-fähig,
                # Hammer ausgerüstet, voll HP (kein Upgrade beschädigter Wände),
                # 2× neues Material im Inventar.
                x, y = int(data.get("x", -1)), int(data.get("y", -1))
                s = structures.object_at(x, y) or structures.floor_at(x, y)
                if s is None:
                    continue
                from structures import is_combat_structure as _is_cs
                if not _is_cs(s["type"]):
                    continue
                if not structures.can_modify(player_id, s):
                    await websocket.send_json({
                        "type": "toast", "text": "🔒 Du bist nicht der Eigentümer.",
                    })
                    continue
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                if combat.chebyshev(player["x"], player["y"], x, y) > 1:
                    await websocket.send_json({"type": "toast", "text": "🤚 Zu weit weg."})
                    continue
                new_mat = structures.next_material(s["material"])
                if new_mat is None:
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"⛰️ Bereits höchstes Material ({s['material']}).",
                    })
                    continue
                if s["durability"] < s.get("max_durability", s["durability"]):
                    await websocket.send_json({
                        "type": "toast",
                        "text": "🔨 Erst reparieren — beschädigte Wände können nicht aufgewertet werden.",
                    })
                    continue
                # Hammer-Check
                tool = await db.pool().fetchrow(
                    "SELECT id FROM items WHERE owner = $1 AND equipped_slot = 'tool' "
                    "AND kind = 'hammer' LIMIT 1", player_id,
                )
                if not tool:
                    await websocket.send_json({"type": "toast", "text": "🔨 Hammer ausrüsten."})
                    continue
                # Materialkosten: 2× das neue (höhere) Material.
                cost = structures.UPGRADE_MATERIAL_COST
                # Prüf-only: gibt es genug? consume_one() consumed jeweils 1.
                consumed_count = 0
                for _ in range(cost):
                    if await items.consume_one(player_id, new_mat):
                        consumed_count += 1
                    else:
                        break
                if consumed_count < cost:
                    # Rollback: zurückgeben was schon consumed wurde
                    for _ in range(consumed_count):
                        try:
                            await items.create_for_player(new_mat, player_id,
                                                           quality_kind="normal")
                        except Exception:
                            log.exception("Upgrade-Rollback fehlgeschlagen")
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"📦 Du brauchst {cost}× {new_mat} zum Aufwerten.",
                    })
                    continue
                result = await structures.upgrade_material(x, y)
                if result is not None:
                    await manager.broadcast({
                        "type": "structure_upgraded",
                        "x": x, "y": y,
                        "material":       result["material"],
                        "durability":     result["durability"],
                        "max_durability": result["max_durability"],
                        "by":             player_id,
                    })
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"⬆️ {s['type']} aufgewertet: {new_mat} ({result['max_durability']} HP)",
                    })
                # Construction-XP — höher als Repair, weil's eine Verbesserung ist
                try:
                    await skills.gain_xp(player_id, "construction", 5)
                except Exception:
                    pass

            elif mtype == "use_structure":
                # Klick auf Bed/Well/Anvil etc. — heilt oder anderes je nach Typ
                x, y = int(data.get("x", -1)), int(data.get("y", -1))
                s = structures.at(x, y)
                if s is None:
                    continue
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                # Nur wenn nahe genug
                if combat.chebyshev(player["x"], player["y"], x, y) > 1:
                    continue
                if s["type"] == "chest":
                    contents = await items.get_chest_contents(s["id"])
                    await websocket.send_json({
                        "type":     "chest_open",
                        "chest_id": s["id"],
                        "items":    contents,
                    })
                    continue
                # Welle 23: Quest-Board zeigt eine Auswahl Welt-Quests an.
                # Wird vom Frontend gerendert wie ein NPC-Quest-Dialog.
                if s["type"] == "quest_board":
                    import quest_templates as qt
                    combat_lvl = await skills.get_skill_level(player_id, "combat")
                    # Quests die Player schon hat
                    taken_rows = await db.pool().fetch(
                        "SELECT template_id FROM quests "
                        "WHERE player_name = $1 "
                        "AND status IN ('active','completed','closed') "
                        "AND template_id IS NOT NULL",
                        player_id,
                    )
                    taken = {r["template_id"] for r in taken_rows}
                    # Quest-Board zeigt die ersten 6 passenden Templates
                    pool = [
                        t for t in qt.QUEST_TEMPLATES
                        if t["min_level"] <= combat_lvl <= t["max_level"]
                        and t["id"] not in taken
                    ]
                    import random as _rb
                    pool = _rb.sample(pool, min(6, len(pool)))
                    offers_ui = [{
                        "template_id": t["id"],
                        "title": t["title_template"].format(**t["objective"]),
                        "description": t["desc_template"].format(**t["objective"]),
                        "quest_type": t["type"],
                        "objective": t["objective"],
                        "reward": t["reward"],
                        "tier": t.get("tier", 1),
                    } for t in pool]
                    await websocket.send_json({
                        "type":     "quest_board_open",
                        "board_id": s["id"],
                        "offers":   offers_ui,
                    })
                    continue
                if harvest.is_harvestable(s["type"]):
                    # Skill bestimmen — explizites Mapping mit Fallback gathering
                    skill_name = PROP_SKILL.get(s["type"], "gathering")
                    has_tool = await has_tool_for_skill(player_id, skill_name)
                    if not has_tool and s["type"] not in NO_TOOL_PROPS:
                        # Kein passendes Tool und kein freebie-Prop: Hinweis und abbrechen
                        await websocket.send_json({
                            "type": "toast",
                            "text": TOOL_HINT.get(skill_name, "Du brauchst das passende Werkzeug"),
                        })
                        continue
                    skill_level = await skills.get_skill_level(player_id, skill_name)
                    yield_bonus = skills.harvest_yield_bonus(skill_level)
                    talent_effects_h = await talents.aggregate_effects(player_id)
                    damage_amount = 2
                    # Talent: extra damage am structure
                    if skill_name == "mining":
                        damage_amount += int(talent_effects_h.get("mining_extra_damage", 0))
                    elif skill_name == "woodcutting":
                        damage_amount += int(talent_effects_h.get("woodcutting_extra_damage", 0))
                    # Biome + mountain-adjacency steuern welche Erze fallen können
                    target_tile = await world.tile_at(s["x"], s["y"])
                    mountain_adj = False
                    for ddx, ddy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                                     (-1, -1), (1, 1), (-1, 1), (1, -1)):
                        if await world.tile_at(s["x"] + ddx, s["y"] + ddy) == 4:  # MOUNTAIN
                            mountain_adj = True
                            break
                    drops = harvest.roll_hit_yield(
                        s["type"], biome=target_tile, mountain_adjacent=mountain_adj,
                    )
                    # Pro Skill-Level Chance auf zusätzlichen Drop
                    import random as _r
                    if drops and yield_bonus > 1.0 and _r.random() < (yield_bonus - 1.0):
                        drops.append(_r.choice(drops))
                    # Tool-Bonus: zusätzlicher Extra-Drop mit 40% Chance
                    if drops and has_tool and _r.random() < 0.4:
                        drops.append(_r.choice(drops))
                    # Talent-Bonus-Drops
                    if skill_name == "woodcutting" and drops:
                        if talent_effects_h.get("woodcutting_bonus_wood", 0) > 0:
                            drops.append("wood")
                        if (talent_effects_h.get("woodcutting_apple_chance", 0) > 0
                                and _r.random() < talent_effects_h["woodcutting_apple_chance"]):
                            drops.append("apple")
                    if skill_name == "mining" and drops:
                        if (talent_effects_h.get("mining_mythril_chance", 0) > 0
                                and _r.random() < talent_effects_h["mining_mythril_chance"]):
                            drops.append("mythril_ore")
                        if (talent_effects_h.get("mining_rare_chance", 0) > 0
                                and _r.random() < talent_effects_h["mining_rare_chance"]):
                            drops.append(_r.choice(["crystal", "gold_ore", "silver_ore"]))
                    if skill_name == "gathering" and drops:
                        if (talent_effects_h.get("gathering_crystal_chance", 0) > 0
                                and _r.random() < talent_effects_h["gathering_crystal_chance"]):
                            drops.append("crystal")
                    for drop_kind in drops:
                        created = await items.create_for_player(drop_kind, player_id)
                        if created is not None:
                            await websocket.send_json({"type": "inventory_add", "item": created})
                    # Quest-Hook: gesammelte Drops
                    if drops:
                        try:
                            from collections import Counter as _Cnt
                            for kind, cnt in _Cnt(drops).items():
                                updated_q = await quests.on_item_collected(player_id, kind, cnt)
                                for q in updated_q:
                                    await websocket.send_json({"type": "quest_progress", "quest": q})
                        except Exception:
                            logging.exception("quest hook (harvest) failed")
                    # XP gain
                    xp_result = await skills.gain_xp(player_id, skill_name, 4 * max(1, len(drops)))
                    if xp_result:
                        await websocket.send_json({"type": "skill_xp", **xp_result})
                    # Visueller Hit
                    await manager.broadcast({
                        "type": "visual_effect", "kind": "hit_spark",
                        "x": s["x"], "y": s["y"],
                    })
                    # Welle 50: skill-spezifischer World-Polish-Effect oben drauf
                    polish_kind = {
                        "woodcutting": "wp_chop_wood",
                        "mining":      "wp_mining_chip",
                        "gathering":   "wp_harvest_crop",
                    }.get(skill_name)
                    if polish_kind:
                        await manager.broadcast({
                            "type": "visual_effect", "kind": polish_kind,
                            "x": s["x"], "y": s["y"],
                        })
                    # Damage applied — structure bleibt oder geht weg
                    # Damage zielt auf den Layer, den at() liefert (Object > Floor)
                    damage_layer = s.get("layer", "object")
                    remaining = await structures.damage_structure(
                        s["x"], s["y"], amount=damage_amount, layer=damage_layer,
                    )
                    if remaining is None:
                        # Zerstört
                        await manager.broadcast({
                            "type": "structure_removed",
                            "x": s["x"], "y": s["y"],
                            "layer": damage_layer,
                        })
                    else:
                        # Noch da — Update broadcast für HP-Bar
                        await manager.broadcast({
                            "type": "structure_damaged",
                            "x": remaining["x"], "y": remaining["y"],
                            "durability": remaining["durability"],
                            "max_durability": harvest.initial_durability(remaining["type"]),
                        })
                    if drops:
                        from collections import Counter
                        cnts = Counter(drops)
                        desc = ", ".join(f"{n}× {k}" for k, n in cnts.items())
                        await websocket.send_json({
                            "type": "toast", "text": f"⛏️ +{desc}",
                        })
                    continue
                if s["type"] == "stairs_down":
                    # Welle 32: Multi-Floor-Dungeons. Dungeon-Eingang ist per
                    # entrance_x/y mit der stairs_down-Struktur verknüpft.
                    cur_world = await dungeon_instance.get_player_world(player_id)
                    if cur_world != "overworld":
                        await websocket.send_json({
                            "type": "toast",
                            "text": "Du bist bereits in einem Dungeon.",
                        })
                        continue
                    cur_player = manager.get_players().get(player_id)
                    if cur_player is None:
                        continue
                    # Existing Instance an dieser Eingangs-Position?
                    drow = await db.pool().fetchrow(
                        "SELECT id, tier, theme FROM dungeons "
                        "WHERE entrance_x = $1 AND entrance_y = $2 "
                        "  AND expires_at > NOW() ORDER BY id DESC LIMIT 1",
                        s["x"], s["y"],
                    )
                    if drow:
                        dungeon_id = drow["id"]
                    else:
                        # Player-platzierte oder alte stairs_down ohne Instanz
                        # → Ad-hoc Tier-1-Spawn (klein, 2-4h), Theme nach Biome.
                        import dungeon_themes as _dt
                        try: _biome = await world.tile_at(s["x"], s["y"])
                        except Exception: _biome = 2
                        meta = await dungeon_instance.spawn_dungeon(
                            s["x"], s["y"], dungeon_tiers.TIER_SMALL,
                            theme=_dt.theme_for_biome(_biome, s["x"] * 31 + s["y"]),
                        )
                        dungeon_id = meta["id"]
                    floor = await dungeon_instance.enter_dungeon(
                        player_id, dungeon_id,
                        cur_player["x"], cur_player["y"],
                        floor_idx=0,
                    )
                    if floor is None:
                        await websocket.send_json({
                            "type": "toast", "text": "⛔ Dungeon nicht erreichbar"})
                        continue
                    dungeon = await dungeon_instance.get_dungeon(dungeon_id)
                    manager.update_player(player_id,
                                          floor["spawn"][0], floor["spawn"][1])
                    # Mobs spawnen falls erste Floor-Begegnung
                    try: await dungeon_instance.populate_floor_mobs(
                        dungeon_id, 0, npcs, manager)
                    except Exception: logging.exception("floor population failed")
                    _extra = await _dungeon_floor_payload(dungeon["id"], 0)
                    await websocket.send_json({
                        "type": "dungeon_enter",
                        "dungeon_id": dungeon["id"],
                        "name":       dungeon["name"],
                        "tier":       dungeon["tier"],
                        "floor_count":dungeon["floor_count"],
                        "floor_idx":  0,
                        "size":       floor["size"],
                        "tiles":      floor["tiles"],
                        "spawn":      {"x": floor["spawn"][0], "y": floor["spawn"][1]},
                        "expires_at": dungeon["expires_at"],
                        **_extra,
                    })
                    label = dungeon_tiers.TIER_LABEL.get(dungeon["tier"], "Dungeon")
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"🏚️ {label} — Floor 1/{dungeon['floor_count']}",
                    })
                    continue
                if s["type"] == "farm_plot":
                    existing = await db.pool().fetchrow(
                        "SELECT plant_kind FROM plantings WHERE structure_id = $1", s["id"]
                    )
                    if existing:
                        await websocket.send_json({
                            "type": "toast", "text": "🌿 Hier wächst schon etwas",
                        })
                        continue
                    if not await items.consume_one(player_id, "herb"):
                        await websocket.send_json({
                            "type": "toast", "text": "Du brauchst ein Kraut zum Pflanzen",
                        })
                        continue
                    await db.pool().execute(
                        "INSERT INTO plantings (structure_id, plant_kind) VALUES ($1, $2)",
                        s["id"], "herb",
                    )
                    await websocket.send_json({
                        "type": "inventory_full_refresh",
                        "inventory": await items.get_inventory(player_id),
                    })
                    # Welle 50: Sow-Seeds Pop am Feld
                    await manager.broadcast({
                        "type": "visual_effect", "kind": "wp_sow_seeds",
                        "x": s["x"], "y": s["y"],
                    })
                    await websocket.send_json({
                        "type": "toast", "text": "🌱 Kraut gepflanzt",
                    })
                    continue
                if s["type"] in ("workbench", "furnace", "anvil"):
                    await websocket.send_json({
                        "type":     "crafting_open",
                        "station":  s["type"],
                        "recipes":  recipes.get_recipes(s["type"]),
                    })
                    continue
                # Welle 51 — Settlement-Schild anklicken → Inspect-Modal
                if s["type"].startswith("sign_"):
                    slug = s["type"][len("sign_"):]
                    await websocket.send_json({
                        "type": "sign_inspect",
                        "slug": slug,
                    })
                    continue
                # Welle 25: Bett / Lagerfeuer als Heim-Spawn setzen.
                # Spieler-Position bei nächstem Tod / Respawn → diese Struktur.
                if s["type"] in ("bed", "campfire"):
                    await db.pool().execute(
                        "UPDATE players SET spawn_x = $1, spawn_y = $2 WHERE name = $3",
                        s["x"], s["y"], player_id,
                    )
                    label = "🛏️ Bett" if s["type"] == "bed" else "🔥 Lagerfeuer"
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"{label} als Heim-Spawn gemerkt — du erscheinst hier wieder.",
                    })
                    # Bett: Schlafen starten → Ausdauer (und langsam HP) regenerieren
                    # bis 100%. Bewegung/Aktion weckt auf (siehe 'wake' + 'move').
                    if s["type"] == "bed":
                        needs.set_resting(player_id, True)
                        await websocket.send_json({"type": "rest_start"})
                        await websocket.send_json({
                            "type": "toast",
                            "text": "😴 Du legst dich schlafen — Bewegung weckt dich.",
                        })
                heal_amount = combat.STRUCTURE_HEAL.get(s["type"])
                if heal_amount is not None:
                    key = (player_id, s["id"])
                    now = time.time()
                    if now - _heal_cooldowns.get(key, 0.0) < combat.STRUCTURE_HEAL_COOLDOWN:
                        await websocket.send_json({
                            "type": "toast", "text": "Noch zu früh — warte einen Moment",
                        })
                        continue
                    _heal_cooldowns[key] = now
                    await heal_player(player_id, heal_amount)
                    # Welle 17: Brunnen tränkt auch — Durst auffüllen
                    if s["type"] == "well":
                        # Welle 24: Check ob dieser Brunnen vergiftet ist
                        is_tainted = False
                        try:
                            active_disasters = await disaster_state.list_active()
                            for d in active_disasters:
                                if d["kind"] == "tainted_well":
                                    meta = d.get("metadata") or {}
                                    if isinstance(meta, str):
                                        import json as _j
                                        meta = _j.loads(meta)
                                    if meta.get("x") == s["x"] and meta.get("y") == s["y"]:
                                        is_tainted = True
                                        break
                        except Exception:
                            pass
                        if is_tainted:
                            # Spieler kriegt Poison-Status für 30s
                            try:
                                await status_effects.apply(
                                    "player", player_id, "poisoned",
                                    magnitude=5, duration_seconds=30)
                            except Exception:
                                log.exception("Tainted-well poison apply failed")
                                await damage_player(player_id, 12)
                            await websocket.send_json({
                                "type": "toast",
                                "text": "☠️ Das Wasser ist vergiftet! Du bist verseucht!",
                            })
                            continue
                        amt = needs.thirst_value("well_drink") or 30
                        new_needs = await needs.restore_thirst(player_id, amt)
                        if new_needs:
                            await websocket.send_json({
                                "type":        "player_needs",
                                "hunger":      new_needs["hunger"],
                                "max_hunger":  new_needs["max_hunger"],
                                "stamina":     new_needs["stamina"],
                                "max_stamina": new_needs["max_stamina"],
                                "thirst":      new_needs["thirst"],
                                "max_thirst":  new_needs["max_thirst"],
                            })
                            await websocket.send_json({
                                "type": "toast", "text": f"💧 Brunnen-Trunk: +{amt} Durst",
                            })
                else:
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"{s['type']} — Mechanik kommt noch",
                    })

            elif mtype == "fill_container":
                # Füllt ein Container-Item (Eimer/Wasserschlauch/Gießkanne) am
                # angegebenen Tile-Click (entweder ein Brunnen oder Wasser-Tile).
                item_id = int(data.get("item_id", 0))
                x, y = int(data.get("x", 0)), int(data.get("y", 0))
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                if combat.chebyshev(player["x"], player["y"], x, y) > 1:
                    await websocket.send_json({"type": "toast", "text": "Zu weit weg."})
                    continue
                # Wasserquelle: Brunnen ODER WATER-Tile
                obj_here = structures.object_at(x, y)
                is_well = obj_here is not None and obj_here["type"] == "well"
                from world import WATER as _W
                tile_id = await world.tile_at(x, y)
                is_water_tile = (tile_id == _W)
                if not (is_well or is_water_tile):
                    await websocket.send_json({"type": "toast", "text": "Keine Wasserquelle."})
                    continue
                # Item muss Container sein und dem Spieler gehören
                cur_item = await db.pool().fetchrow(
                    "SELECT kind FROM items WHERE id = $1 AND owner = $2",
                    item_id, player_id,
                )
                if cur_item is None or not items.is_water_container(cur_item["kind"]):
                    await websocket.send_json({"type": "toast", "text": "Kein Behälter."})
                    continue
                cap = items.container_capacity(cur_item["kind"])
                filled = await items.set_charges(item_id, player_id, cap)
                if filled:
                    await websocket.send_json({"type": "inventory_update", "item": filled})
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"💧 {cur_item['kind']} aufgefüllt ({cap} Ladungen).",
                    })

            elif mtype == "water_plant":
                # Bewässert einen farm_plot in Reichweite (verbraucht 1 Container-Ladung)
                x, y = int(data.get("x", 0)), int(data.get("y", 0))
                container_id = int(data.get("item_id", 0))
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                if combat.chebyshev(player["x"], player["y"], x, y) > 1:
                    await websocket.send_json({"type": "toast", "text": "Zu weit weg."})
                    continue
                target = structures.at(x, y)
                if target is None or target["type"] != "farm_plot":
                    await websocket.send_json({"type": "toast", "text": "Hier ist kein Acker."})
                    continue
                # Container prüfen
                cur_item = await db.pool().fetchrow(
                    "SELECT kind, charges FROM items WHERE id = $1 AND owner = $2",
                    container_id, player_id,
                )
                if cur_item is None or not items.is_water_container(cur_item["kind"]):
                    await websocket.send_json({"type": "toast", "text": "Kein Wasserbehälter ausgewählt."})
                    continue
                if (cur_item["charges"] or 0) <= 0:
                    await websocket.send_json({"type": "toast", "text": "Behälter ist leer."})
                    continue
                # Bewässern: pflanze last_watered_at = NOW
                upd = await db.pool().fetchrow(
                    "UPDATE plantings SET last_watered_at = NOW() "
                    "WHERE structure_id = $1 "
                    "RETURNING structure_id, plant_kind",
                    target["id"],
                )
                if upd is None:
                    await websocket.send_json({"type": "toast", "text": "Acker ist leer (kein Samen)."})
                    continue
                # Charges -1
                updated = await items.add_charges(container_id, player_id, -1)
                if updated:
                    await websocket.send_json({"type": "inventory_update", "item": updated})
                # Welle 50: Wasser-Pop am Acker
                await manager.broadcast({
                    "type": "visual_effect", "kind": "wp_water_crop_tile",
                    "x": x, "y": y,
                })
                await websocket.send_json({
                    "type": "toast",
                    "text": f"🌱💧 Bewässert ({upd['plant_kind']})",
                })

            elif mtype == "drink_container":
                # Trinkt 1 Ladung aus einem vollen Container im Inventar.
                item_id = int(data.get("item_id", 0))
                cur_item = await db.pool().fetchrow(
                    "SELECT kind, charges FROM items WHERE id = $1 AND owner = $2",
                    item_id, player_id,
                )
                if cur_item is None or not items.is_water_container(cur_item["kind"]):
                    continue
                if (cur_item["charges"] or 0) <= 0:
                    await websocket.send_json({"type": "toast", "text": "Behälter ist leer."})
                    continue
                # Trinken: +25 Durst pro Ladung
                amt = needs.thirst_value("water_drink") or 25
                new_needs = await needs.restore_thirst(player_id, amt)
                if new_needs:
                    await websocket.send_json({"type": "player_needs", **new_needs})
                updated = await items.add_charges(item_id, player_id, -1)
                if updated:
                    await websocket.send_json({"type": "inventory_update", "item": updated})
                await websocket.send_json({
                    "type": "toast",
                    "text": f"💧 +{amt} Durst (Behälter: {updated['charges']}/{items.container_capacity(cur_item['kind'])})",
                })

            elif mtype == "drink_water_tile":
                # Trinkt aus angrenzendem Wasser-Tile (oder direkt drauf)
                x, y = int(data.get("x", 0)), int(data.get("y", 0))
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                if combat.chebyshev(player["x"], player["y"], x, y) > 1:
                    continue
                # WATER = tile id 0 (siehe world.py)
                tile_id = await world.tile_at(x, y)
                from world import WATER as _W
                if tile_id != _W:
                    await websocket.send_json({
                        "type": "toast", "text": "Hier ist kein Wasser.",
                    })
                    continue
                amt = needs.thirst_value("water_drink") or 25
                new_needs = await needs.restore_thirst(player_id, amt)
                if new_needs:
                    await websocket.send_json({
                        "type":        "player_needs",
                        "hunger":      new_needs["hunger"],
                        "max_hunger":  new_needs["max_hunger"],
                        "stamina":     new_needs["stamina"],
                        "max_stamina": new_needs["max_stamina"],
                        "thirst":      new_needs["thirst"],
                        "max_thirst":  new_needs["max_thirst"],
                    })
                    await websocket.send_json({
                        "type": "toast", "text": f"💧 Aus dem See getrunken: +{amt} Durst",
                    })

            elif mtype == "chest_transfer_to":
                chest_id = int(data.get("chest_id", 0))
                item_id = int(data.get("item_id", 0))
                transferred = await items.transfer_to_chest(item_id, player_id, chest_id)
                if transferred:
                    await websocket.send_json({
                        "type": "inventory_remove", "item_id": item_id,
                    })
                    await websocket.send_json({
                        "type": "chest_add", "chest_id": chest_id, "item": transferred,
                    })

            elif mtype == "chest_transfer_from":
                chest_id = int(data.get("chest_id", 0))
                item_id = int(data.get("item_id", 0))
                # Welle 33: Münzen aus der Truhe → Geldbeutel statt Inventar.
                _krow = await db.pool().fetchrow(
                    "SELECT kind, quantity FROM items WHERE id = $1 AND owner = $2",
                    item_id, f"chest:{chest_id}",
                )
                if _krow and currency.is_currency(_krow["kind"]):
                    _gain = currency.coin_to_copper(_krow["kind"], _krow["quantity"] or 1)
                    await db.pool().execute("DELETE FROM items WHERE id = $1", item_id)
                    await currency.add(player_id, _gain)
                    await websocket.send_json({
                        "type": "chest_remove", "chest_id": chest_id, "item_id": item_id,
                    })
                    await _push_wallet(player_id, gained=_gain)
                    continue
                transferred = await items.transfer_from_chest(item_id, chest_id, player_id)
                if transferred:
                    await websocket.send_json({
                        "type": "chest_remove", "chest_id": chest_id, "item_id": item_id,
                    })
                    await websocket.send_json({
                        "type": "inventory_add", "item": transferred,
                    })

            elif mtype == "open_hand_crafting":
                # Inventar-getriebenes Hand-Crafting: keine Werkbank nötig.
                await websocket.send_json({
                    "type":    "crafting_open",
                    "station": "hand",
                    "recipes": recipes.get_recipes("hand"),
                })

            elif mtype == "craft":
                station = str(data.get("station", ""))
                recipe_id = str(data.get("recipe_id", ""))
                recipe = recipes.find_recipe(station, recipe_id)
                if recipe is None:
                    continue
                # Welle 22: Research-Gate
                req = recipe.get("requires")
                if req and not await research.is_node_done(player_id, req):
                    node_name = research.RESEARCH_NODES.get(req, {}).get("name", req)
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"🔒 Erst forschen: {node_name}",
                    })
                    continue
                counts = await items.count_owned_by_kind(player_id)
                if not all(counts.get(k, 0) >= n for k, n in recipe["inputs"]):
                    await websocket.send_json({
                        "type": "toast", "text": "Nicht genug Material",
                    })
                    continue
                for k, n in recipe["inputs"]:
                    for _ in range(n):
                        await items.consume_one(player_id, k)
                # Quality-Roll basierend auf Crafting-Skill + Talente
                craft_level = await skills.get_skill_level(player_id, "crafting")
                talent_craft = await talents.aggregate_effects(player_id)
                # Bonus-Level für Quality-Roll
                effective_level = craft_level + int(talent_craft.get("crafting_quality_bonus", 0) * 8)
                q = quality.roll_quality(effective_level)
                # Perfektionist: nie schlechter als 'fein'
                if talent_craft.get("crafting_min_quality", 0) >= 1:
                    if q in ("rough", "normal"): q = "fine"
                # Großmeister: +5% chance auf legendär
                if (talent_craft.get("crafting_legendary_chance", 0) > 0
                        and q in ("masterwork", "fine")
                        and __import__('random').random() < talent_craft["crafting_legendary_chance"]):
                    q = "legendary"
                created = await items.create_for_player(
                    recipe["output"], player_id, quality_kind=q,
                    material=recipe.get("material"),
                )
                # Affix-Roll bei fine+ Items
                if created and q in ("fine", "masterwork", "legendary"):
                    rolled_affixes = affixes.roll_affixes(recipe["output"], q)
                    unique_name = None
                    flavor = None
                    # Legendary → LLM-Naming (im Hintergrund, blockt Crafting nicht)
                    if q == "legendary":
                        try:
                            base_name = items.ITEM_KINDS.get(recipe["output"], {}).get("name", recipe["output"])
                            naming = await item_namer.generate_name_and_flavor(
                                recipe["output"], base_name, q, rolled_affixes,
                                use_slow_brain=False,  # 0.8b ist schnell genug fürs Naming
                            )
                            if naming:
                                unique_name = naming["name"]
                                flavor = naming["flavor"]
                        except Exception:
                            logging.exception("LLM-Naming fehlgeschlagen")
                    if rolled_affixes or unique_name:
                        await affixes.save_affixes_to_item(
                            created["id"], rolled_affixes, unique_name, flavor,
                        )
                        # Reflect into created dict für die UI
                        created["affixes"] = rolled_affixes
                        if unique_name: created["unique_name"] = unique_name
                        if flavor: created["flavor"] = flavor
                new_inv = await items.get_inventory(player_id)
                await websocket.send_json({
                    "type": "inventory_full_refresh",
                    "inventory": new_inv if created else new_inv,
                })
                quality_label = quality.QUALITY_LABELS.get(q, "")
                quality_icon = quality.QUALITY_ICONS.get(q, "")
                qprefix = f"{quality_icon} {quality_label} " if quality_label else ""
                await websocket.send_json({
                    "type": "toast",
                    "text": f"✨ {qprefix}{recipe['name']} hergestellt",
                })
                # Crafting-XP (+ Cooking wenn Furnace mit Food-Output)
                xp_result = await skills.gain_xp(player_id, "crafting", 15)
                if xp_result:
                    await websocket.send_json({"type": "skill_xp", **xp_result})
                # Welle 30: Crafting gibt KEINE Forschungspunkte mehr — nur noch
                # Skill-Level-Up, Quests und 2h-Time-Tick füllen den Pool.
                # Cooking-XP wenn das Rezept Food produziert
                if recipe["output"] in ("bread", "cooked_meat"):
                    cook_xp = await skills.gain_xp(player_id, "cooking", 20)
                    if cook_xp:
                        await websocket.send_json({"type": "skill_xp", **cook_xp})

            elif mtype == "open_trade":
                npc_id = int(data.get("npc_id", 0))
                npc = npcs.get(npc_id)
                if npc is None or npc["kind"] != "merchant":
                    continue
                player = manager.get_players().get(player_id)
                if player is None or combat.chebyshev(player["x"], player["y"], npc["x"], npc["y"]) > 2:
                    continue
                offerings_kinds = trade.generate_offerings(8)
                from items import ITEM_KINDS
                offerings = [
                    {
                        "kind":   k,
                        "name":   ITEM_KINDS[k]["name"],
                        "price":  trade.buy_price(k),
                        "sprite_path": ITEM_KINDS[k]["sprite"],
                    }
                    for k in offerings_kinds if k in ITEM_KINDS
                ]
                await websocket.send_json({
                    "type":      "trade_open",
                    "npc_id":    npc_id,
                    "npc_name":  npc["name"],
                    "offerings": offerings,
                    "coins":     await currency.balance(player_id),  # Kupfer
                })

            elif mtype == "buy_item":
                kind = data.get("kind", "")
                from items import ITEM_KINDS
                if kind not in ITEM_KINDS:
                    continue
                price = trade.buy_price(kind)
                # Social-Skill + Haggler-Talent: Rabatt
                social_lvl = await skills.get_skill_level(player_id, "social")
                discount = skills.social_trade_discount(social_lvl)
                talent_eff_t = await talents.aggregate_effects(player_id)
                if talent_eff_t.get("social_buy_discount", 0) > 0:
                    discount *= (1 - talent_eff_t["social_buy_discount"])
                price = max(1, int(round(price * discount)))
                # Welle 33: aus dem Geldbeutel bezahlen (atomar)
                if not await currency.spend(player_id, price):
                    await websocket.send_json({"type": "toast", "text": "Nicht genug Geld"})
                    continue
                # Social-XP für Trade
                sxp = await skills.gain_xp(player_id, "social", 3)
                if sxp:
                    await websocket.send_json({"type": "skill_xp", **sxp})
                created = await items.create_for_player(kind, player_id)
                if created is None:
                    await currency.add(player_id, price)  # Refund bei Fehlschlag
                    continue
                inv = await items.get_inventory(player_id)
                await websocket.send_json({"type": "inventory_full_refresh", "inventory": inv})
                await _push_wallet(player_id)
                await websocket.send_json({
                    "type": "trade_coins", "coins": await currency.balance(player_id),
                })

            elif mtype == "sell_item":
                item_id = int(data.get("item_id", 0))
                row = await db.pool().fetchrow(
                    "SELECT kind FROM items WHERE id = $1 AND owner = $2",
                    item_id, player_id,
                )
                if row is None:
                    continue
                kind = row["kind"]
                price = trade.sell_price(kind)
                # Social-Skill + Merchant-Friend-Talent: Verkaufs-Bonus
                talent_eff_s = await talents.aggregate_effects(player_id)
                sell_mult = 1.0 + talent_eff_s.get("social_sell_bonus", 0)
                price = max(1, int(round(price * sell_mult)))
                # Social-XP
                sxp = await skills.gain_xp(player_id, "social", 4)
                if sxp:
                    await websocket.send_json({"type": "skill_xp", **sxp})
                await db.pool().execute("DELETE FROM items WHERE id = $1", item_id)
                # Welle 33: Erlös in den Geldbeutel
                await currency.add(player_id, price)
                inv = await items.get_inventory(player_id)
                await websocket.send_json({"type": "inventory_full_refresh", "inventory": inv})
                await _push_wallet(player_id)
                await websocket.send_json({
                    "type": "trade_coins", "coins": await currency.balance(player_id),
                })

            elif mtype == "learn_talent":
                talent_id = data.get("talent_id", "")
                found = talents.find_talent(talent_id)
                if found is None:
                    await websocket.send_json({"type": "toast", "text": "Unbekanntes Talent"})
                    continue
                skill_name, _ = found
                lvl = await skills.get_skill_level(player_id, skill_name)
                result = await talents.learn_talent(player_id, talent_id, lvl)
                if result["ok"]:
                    # Aktualisiertes Tree senden
                    sk = await skills.get_skills(player_id)
                    learned = await talents.list_learned(player_id)
                    pts = await talents.get_talent_points(player_id)
                    await websocket.send_json({
                        "type": "talent_learned",
                        "talent_id": talent_id,
                        "points":    pts,
                        "learned":   learned,
                        "tree":      talents.tree_for_ui(sk, set(l["talent_id"] for l in learned), pts),
                    })
                    await websocket.send_json({"type": "toast", "text": f"🌟 {found[1]['name']} gelernt!"})
                else:
                    reason_msgs = {
                        "skill_too_low":  f"Skill zu niedrig (brauche Level {result.get('needed')})",
                        "prereq_missing": f"Vorgänger-Talent fehlt: {result.get('prereq')}",
                        "already_learned":"Bereits gelernt",
                        "no_points":      "Keine Talent-Punkte verfügbar",
                    }
                    await websocket.send_json({
                        "type": "toast",
                        "text": reason_msgs.get(result["reason"], f"Fehler: {result['reason']}"),
                    })

            elif mtype == "learn_spell":
                # Spieler lernt aus einem Spell-Item (verbraucht 1 Stück)
                item_id = int(data.get("item_id", 0))
                row = await db.pool().fetchrow(
                    "SELECT kind, category FROM items WHERE id = $1 AND owner = $2",
                    item_id, player_id,
                )
                if not row or row["category"] != "magic":
                    await websocket.send_json({"type": "toast", "text": "Das ist kein Zauber-Item"})
                    continue
                spell_kind = row["kind"]
                # Schon gelernt?
                exists = await db.pool().fetchrow(
                    "SELECT 1 FROM learned_spells WHERE player_name = $1 AND spell_kind = $2",
                    player_id, spell_kind,
                )
                if exists:
                    await websocket.send_json({"type": "toast",
                        "text": "Diesen Zauber kennst du bereits."})
                    continue
                # Item verbrauchen + Spell speichern
                await items.consume_one(player_id, spell_kind)
                await db.pool().execute(
                    "INSERT INTO learned_spells (player_name, spell_kind) "
                    "VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    player_id, spell_kind,
                )
                spell_cfg = combat.SPELLS.get(spell_kind, {})
                await websocket.send_json({
                    "type": "spell_learned",
                    "spell_kind": spell_kind,
                    "learned": await _list_learned_spells(player_id),
                })
                await websocket.send_json({
                    "type": "toast",
                    "text": f"📖 Zauber gelernt: {spell_cfg.get('name', spell_kind)}",
                })
                # XP für Magie
                xp = await skills.gain_xp(player_id, "magic", 25)
                if xp:
                    await websocket.send_json({"type": "skill_xp", **xp})
                inv = await items.get_inventory(player_id)
                await websocket.send_json({"type": "inventory_full_refresh", "inventory": inv})

            elif mtype == "cast_learned":
                # Cast eines bereits gelernten Zaubers (ohne Item-Verbrauch)
                spell_kind = data.get("spell_kind", "")
                spell = combat.SPELLS.get(spell_kind)
                if not spell:
                    continue
                # Prüfen ob gelernt
                exists = await db.pool().fetchrow(
                    "SELECT 1 FROM learned_spells WHERE player_name = $1 AND spell_kind = $2",
                    player_id, spell_kind,
                )
                if not exists:
                    await websocket.send_json({"type": "toast",
                        "text": "Diesen Zauber hast du nicht gelernt."})
                    continue
                # Mana-Check
                pstate = await db.pool().fetchrow(
                    "SELECT mana, max_mana FROM players WHERE name = $1", player_id,
                )
                if not pstate or pstate["mana"] < spell["mana"]:
                    await websocket.send_json({"type": "toast", "text": "Zu wenig Mana"})
                    continue
                # Mana abziehen
                new_mana = pstate["mana"] - spell["mana"]
                await db.pool().execute(
                    "UPDATE players SET mana = $1 WHERE name = $2", new_mana, player_id,
                )
                await websocket.send_json({
                    "type": "player_mana", "mana": new_mana, "max_mana": pstate["max_mana"],
                })
                # Self-Effekt + Heal anwenden
                if spell.get("heal_self", 0) > 0:
                    await heal_player(player_id, spell["heal_self"])
                self_eff = spell.get("self_effect")
                if self_eff:
                    try:
                        await status_effects.apply("player", player_id,
                            self_eff["effect"], self_eff["magnitude"], self_eff["duration"])
                        effs = await status_effects.list_for_target("player", player_id)
                        await websocket.send_json({"type": "status_effects", "effects": effs})
                    except Exception:
                        pass
                await websocket.send_json({"type": "toast",
                    "text": f"✨ {spell.get('name', spell_kind)} gewirkt"})
                xp = await skills.gain_xp(player_id, "magic", 5 + spell["mana"] // 3)
                if xp:
                    await websocket.send_json({"type": "skill_xp", **xp})

            elif mtype == "list_attributes":
                attrs = await _compute_attributes(player_id)
                await websocket.send_json({"type": "attributes_update", **attrs})

            elif mtype == "character_check_name":
                # Welle 23: Live-Check ob ein gewünschter display_name frei ist.
                want = str(data.get("display_name", "")).strip()[:24]
                if not want or len(want) < 3:
                    await websocket.send_json({"type": "character_name_check",
                        "name": want, "available": False, "reason": "zu kurz (min 3 Zeichen)"})
                    continue
                if not all(c.isalnum() or c in "-_ " for c in want):
                    await websocket.send_json({"type": "character_name_check",
                        "name": want, "available": False, "reason": "nur Buchstaben/Zahlen/-_ Leerzeichen"})
                    continue
                taken = await db.pool().fetchval(
                    "SELECT 1 FROM players WHERE LOWER(display_name) = LOWER($1) "
                    "AND name <> $2", want, player_id,
                )
                await websocket.send_json({
                    "type": "character_name_check",
                    "name": want,
                    "available": not taken,
                    "reason": "schon vergeben" if taken else "frei",
                })

            elif mtype == "character_create":
                # Welle 23: Spieler wählt Preset + display_name + verteilt 20
                # Startpunkte. Wird nur akzeptiert wenn character_created
                # noch FALSE ist (kein erneutes Char-Creation für gleichen Account).
                preset = str(data.get("preset", "")).strip()[:32]
                allocated_in = data.get("allocated") or {}
                display_name = str(data.get("display_name", "")).strip()[:24]
                # display_name-Validation
                if not display_name or len(display_name) < 3:
                    await websocket.send_json({"type": "toast",
                        "text": "Spielername muss mindestens 3 Zeichen lang sein."})
                    continue
                if not all(c.isalnum() or c in "-_ " for c in display_name):
                    await websocket.send_json({"type": "toast",
                        "text": "Spielername: nur Buchstaben/Zahlen/-_ Leerzeichen erlaubt."})
                    continue
                taken = await db.pool().fetchval(
                    "SELECT 1 FROM players WHERE LOWER(display_name) = LOWER($1) "
                    "AND name <> $2", display_name, player_id,
                )
                if taken:
                    await websocket.send_json({"type": "toast",
                        "text": f"Spielername '{display_name}' ist bereits vergeben."})
                    continue
                # Validate preset
                VALID_PRESETS = {"ember_mage", "iron_delver", "knife_runner",
                                  "shieldbearer", "wanderer_cloak", "wild_ranger"}
                if preset not in VALID_PRESETS:
                    await websocket.send_json({"type": "toast",
                        "text": "Ungültige Charakter-Auswahl"})
                    continue
                # Validate allocated: 12 valid attrs, sum <= 20, each <= 5
                VALID_ATTRS = {"stärke", "ausdauer", "energie", "intelligenz",
                                "weisheit", "ausweichen", "geschick", "verteidigung",
                                "charisma", "krit_rate", "krit_schaden", "schleichen"}
                MAX_PER_ATTR = 10   # Welle 23: erhöht von 5 für mehr Specialization
                MAX_TOTAL = 20
                cleaned: dict[str, int] = {}
                total = 0
                for k, v in allocated_in.items():
                    if k not in VALID_ATTRS:
                        continue
                    iv = max(0, min(MAX_PER_ATTR, int(v)))
                    if iv > 0:
                        cleaned[k] = iv
                        total += iv
                if total > MAX_TOTAL:
                    await websocket.send_json({"type": "toast",
                        "text": f"Zu viele Punkte vergeben ({total}/{MAX_TOTAL})"})
                    continue
                # Already created? — block re-creation
                row = await db.pool().fetchrow(
                    "SELECT character_created FROM players WHERE name = $1",
                    player_id,
                )
                if row and row["character_created"]:
                    await websocket.send_json({"type": "toast",
                        "text": "Charakter ist bereits erstellt"})
                    continue
                # Persist preset + allocated_attrs + display_name + flag set
                import json as _json
                remaining_points = MAX_TOTAL - total
                await db.pool().execute(
                    "UPDATE players SET preset = $2, "
                    "  allocated_attrs = $3::jsonb, "
                    "  unspent_attr_points = $4, "
                    "  display_name = $5, "
                    "  character_created = TRUE "
                    "WHERE name = $1",
                    player_id, preset, _json.dumps(cleaned),
                    remaining_points, display_name,
                )
                logging.info("Character created: %s preset=%s name=%s alloc=%s",
                              player_id, preset, display_name, cleaned)
                await websocket.send_json({
                    "type": "character_created",
                    "preset": preset,
                    "display_name": display_name,
                    "allocated": cleaned,
                    "unspent": remaining_points,
                })

            elif mtype == "list_talents":
                sk = await skills.get_skills(player_id)
                learned = await talents.list_learned(player_id)
                pts = await talents.get_talent_points(player_id)
                await websocket.send_json({
                    "type":    "talents_update",
                    "learned": learned,
                    "points":  pts,
                    "tree":    talents.tree_for_ui(sk, set(l["talent_id"] for l in learned), pts),
                })

            elif mtype == "list_quests":
                qs = await quests.list_for_player(player_id)
                rep = await quests.all_reputation(player_id)
                await websocket.send_json({"type": "quests_update", "quests": qs,
                                            "reputation": rep})

            elif mtype == "query_npc_quests":
                # Welle 23: Frontend fragt was dieser NPC anbietet / wo abgeben
                npc_id = int(data.get("npc_id", 0))
                npc = npcs.get(npc_id)
                if npc is None or npc["kind"] in combat.CREATURE_KINDS:
                    await websocket.send_json({"type": "npc_quest_status",
                                                "npc_id": npc_id,
                                                "offers": [], "turnins": []})
                    continue
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

            elif mtype == "accept_quest_template":
                # Welle 23: template-basierte Annahme (statt LLM-Generator)
                template_id = str(data.get("template_id", ""))
                npc_id = int(data.get("npc_id", 0))
                npc = npcs.get(npc_id)
                if npc is None or not template_id:
                    continue
                # 3-Aktive-Quests-Limit beibehalten
                active_qs = await quests.list_for_player(player_id, ("active",))
                if len(active_qs) >= 3:
                    await websocket.send_json({
                        "type": "toast", "text": "Du hast bereits 3 aktive Quests!",
                    })
                    continue
                new_q = await quests.accept_template(player_id, template_id, npc_id)
                if new_q is None:
                    await websocket.send_json({
                        "type": "toast",
                        "text": "Quest konnte nicht angenommen werden.",
                    })
                    continue
                await websocket.send_json({"type": "quest_new", "quest": new_q})
                await websocket.send_json({
                    "type": "toast", "text": f"📜 {new_q['title']}",
                })
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

            elif mtype == "quest_turn_in":
                # Welle 23: Quest beim NPC abgeben (Faction-Reward + Item-Reward)
                quest_id = int(data.get("quest_id", 0))
                npc_id = int(data.get("npc_id", 0))
                result = await quests.turn_in(quest_id, player_id)
                if result is None:
                    await websocket.send_json({
                        "type": "toast",
                        "text": "Diese Quest ist nicht abschließbar.",
                    })
                    continue
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
                    await currency.add(player_id, gold * currency.COPPER_PER_SILVER)
                # Münz-items im Reward sind via create_for_player schon ins Guthaben
                # geflossen → Geldbeutel jetzt an den Client pushen.
                await _push_wallet(player_id)
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

            elif mtype == "accept_quest_from_npc":
                npc_id = int(data.get("npc_id", 0))
                npc = npcs.get(npc_id)
                if npc is None or npc["kind"] in combat.CREATURE_KINDS:
                    continue
                # NPC-Kind darf überhaupt Quests vergeben?
                if not quest_generator.can_give_quest(npc["kind"]):
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"{npc['name']} hat keinen Auftrag für dich.",
                    })
                    continue
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
                    continue
                # Spieler kann max. 3 aktive Quests gleichzeitig haben
                active_qs = await quests.list_for_player(player_id, ("active",))
                if len(active_qs) >= 3:
                    await websocket.send_json({
                        "type": "toast", "text": "Du hast bereits 3 aktive Quests!"
                    })
                    continue
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

            elif mtype == "claim_quest_reward":
                quest_id = int(data.get("quest_id", 0))
                qs = await quests.list_for_player(player_id, ("completed",))
                target_q = next((q for q in qs if q["id"] == quest_id), None)
                if target_q is None:
                    continue
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
                    await currency.add(player_id, gold * currency.COPPER_PER_SILVER)
                await _push_wallet(player_id)
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
                await quests.mark_closed(quest_id)
                await websocket.send_json({"type": "quest_closed", "quest_id": quest_id})
                await websocket.send_json({"type": "toast", "text": "✅ Quest abgegeben!"})

            elif mtype == "invest_research":
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

            elif mtype == "add_bill":
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
                    continue
                bill = await bill_queue.add_bill(player_id, station_type, recipe_id, count)
                bills_now = await bill_queue.list_bills(player_id)
                await websocket.send_json({"type": "bills_update", "bills": bills_now})

            elif mtype == "remove_bill":
                bill_id = int(data.get("bill_id", 0))
                await bill_queue.remove_bill(bill_id, player_id)
                bills_now = await bill_queue.list_bills(player_id)
                await websocket.send_json({"type": "bills_update", "bills": bills_now})

            elif mtype == "list_bills":
                bills_now = await bill_queue.list_bills(player_id, data.get("station_type"))
                await websocket.send_json({"type": "bills_update", "bills": bills_now})

            elif mtype == "talk_to_npc":
                npc_id = int(data.get("npc_id", 0))
                message = str(data.get("message", "")).strip()[:500]
                npc = npcs.get(npc_id)
                if npc is None or not message:
                    continue
                # Hostile Kreaturen (Bandit/Wolf/Goblin/…) reden nicht — die greifen an.
                if npc["kind"] in combat.CREATURE_KINDS:
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"⚔️ {npc.get('name', 'Diese Kreatur')} ist feindlich — angreifen, nicht reden!",
                    })
                    continue
                # Welle 25: Nutztiere + Karawanen-Wagen reden nicht.
                # Spätere Interaktions-Mechanik (Streichen/Melken/Scheren/
                # Schlachten/Wolle/Eier) kommt als eigenes System.
                if npc["kind"] in npc_worker.LIVESTOCK_KINDS:
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"🐾 {npc.get('name', 'Das Tier')} ist ein Nutztier — keine Konversation.",
                    })
                    continue
                if npc["kind"] in npc_worker.CART_KINDS:
                    await websocket.send_json({
                        "type": "toast",
                        "text": "🛒 Ein Wagen redet nicht — sprich den Händler daneben an.",
                    })
                    continue
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

    except WebSocketDisconnect:
        # Welle 25: aktiven Cast + Cooldowns räumen, Down-Timer canceln
        spell_caster.cleanup_player(player_id)
        needs.clear_player_state(player_id)   # Sprint/Ruhe/Akkumulator räumen
        ds = _downed_state.pop(player_id, None)
        if ds and ds.get("task"):
            try: ds["task"].cancel()
            except Exception: pass
        # Welle 31: Gruppen — Leader-Offline-Reaper-Timer setzen + Member benachrichtigen
        try:
            _g = await groups.get_group_for(player_id)
            if _g:
                if _g["kind"] == "party" and _g["leader"] == player_id:
                    groups.mark_leader_offline(_g["id"])
                await _broadcast_to_group(_g["id"], {
                    "type": "group_member_offline", "player_name": player_id,
                }, exclude=player_id)
        except Exception:
            logging.exception("group-disconnect-hook fehlgeschlagen")
        manager.disconnect(player_id)
        await db.pool().execute(
            "UPDATE players SET last_seen = NOW() WHERE name = $1", player_id
        )
        await manager.broadcast({
            "type": "player_left",
            "player_id": player_id,
        })


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
