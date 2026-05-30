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
from ws.context import WsContext
from ws.dispatcher import dispatch as ws_dispatch
import ws.movement  # noqa: F401 — registriert move/sprint im Dispatcher
import ws.bills  # noqa: F401 — registriert add_bill/remove_bill/list_bills
import ws.research  # noqa: F401 — registriert invest_research
import ws.dialog  # noqa: F401 — registriert talk_to_npc
import ws.trade  # noqa: F401 — registriert open_trade/buy_item/sell_item
import ws.loot  # noqa: F401 — registriert loot_vote/set_loot_rule
import ws.raid  # noqa: F401 — registriert raid_trigger_manual/dev_*/force_respawn
import ws.crafting  # noqa: F401 — registriert open_hand_crafting/craft
import ws.character  # noqa: F401 — registriert wake/allocate_attr/learn_*/cast_learned/list_*/character_*
import ws.inventory  # noqa: F401 — registriert split/merge/equip/unequip/use_item/pick/drop/chest_*
import ws.quests  # noqa: F401 — registriert list_quests/query_npc_quests/accept_quest_*/quest_turn_in/claim_quest_reward
import ws.social  # noqa: F401 — registriert chat + group_*
import ws.structures  # noqa: F401 — registriert dungeon_chest/place/toggle_door/remove/attack/repair/upgrade/use_structure/fill/water/drink_*
import ws.combat  # noqa: F401 — registriert attack_npc + cast_spell

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

    ctx = WsContext(
        websocket=websocket,
        player_id=player_id,
        manager=manager,
        world=world,
        structures=structures,
        npcs=npcs,
        items=items,
        events=events,
        user=user,
    )

    try:
        while True:
            data = await websocket.receive_json()
            mtype = data.get("type")

            # Phase B2 (hybrid): erst neuen Dispatcher fragen, sonst Fallback
            # in die alte if/elif-Kette. Mit jeder weiteren B-Phase wandern
            # Branches in ws/<domain>.py und werden hier aus dem Monolithen
            # entfernt.
            if await ws_dispatch(ctx, data):
                continue

            pass  # all messages handled by ws_dispatch above

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
