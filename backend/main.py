"""Liege backend entry-point.

Schlanke Hülle nach B-final: App-Setup + lifespan + HTTP-Routes +
Statik-Mounts + dünner /ws-Endpoint. Alle WS-Message-Branches leben
jetzt in `backend/ws/<domain>.py` und registrieren sich beim Import
im Dispatcher.

`load_or_create_player`, der init-Payload-Builder und die
disconnect-Cleanup nutzen weiterhin die Service-Funktionen direkt;
ein paar dünne Bind-Wrapper (`damage_player`, `heal_player`,
`_apply_spell_effects` …) bleiben, weil Hintergrund-Worker und
spell_caster-Callbacks sie als fertig-konfigurierten Callable
brauchen.
"""
import asyncio
import logging
import os
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
import bill_queue
import body_parts
import currency
import disaster_state
import dungeons
import event_worker
import factions
import farm_worker
import groups
import item_worker
import needs
import npc_mood
import npc_worker
import power_budget
import quests
import raid_director
import recipes
import research
import quest_worker
import respawn_worker
import skills
import spell_caster
import spells
import status_effects
import talents
import time_system
import weather_worker
import world_populator
from ws_manager import ConnectionManager
from world import World
from structures import StructureManager
from events import EventManager
from npcs import NPCManager
from items import ItemManager

from services import player_state as _player_state
from services.player_state import (
    load_or_create_player as _load_or_create_player_svc,
    heal_player as _heal_player_svc,
    damage_player as _damage_player_svc,
    do_respawn as _do_respawn_svc,
    refund_mana as _refund_mana_svc,
    downed_state as _downed_state,
)
from services.player_comms import send_to_player as _send_to_player_svc

from ws.context import WsContext
from ws.dispatcher import dispatch as ws_dispatch
import ws.movement     # noqa: F401 — registriert move/sprint
import ws.bills        # noqa: F401 — registriert add_bill/remove_bill/list_bills
import ws.research     # noqa: F401 — registriert invest_research
import ws.dialog       # noqa: F401 — registriert talk_to_npc
import ws.trade        # noqa: F401 — registriert open_trade/buy_item/sell_item
import ws.loot         # noqa: F401 — registriert loot_vote/set_loot_rule
import ws.raid         # noqa: F401 — registriert raid_trigger_manual/dev_*/force_respawn
import ws.crafting     # noqa: F401 — registriert open_hand_crafting/craft
import ws.character    # noqa: F401 — registriert wake/allocate_attr/learn_*/list_*/character_*
import ws.inventory    # noqa: F401 — registriert split/merge/equip/unequip/use_item/pick/drop/chest_*
import ws.quests       # noqa: F401 — registriert list_quests/query_npc_quests/accept_quest_*/quest_turn_in/claim_quest_reward
import ws.social       # noqa: F401 — registriert chat + group_*
import ws.structures   # noqa: F401 — registriert dungeon_chest/place/toggle_door/remove/attack/repair/upgrade/use_structure/fill/water/drink_*
import ws.combat       # noqa: F401 — registriert attack_npc + cast_spell

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s: %(message)s")

manager = ConnectionManager()
structures = StructureManager()
events = EventManager()
npcs = NPCManager()
items = ItemManager()
# Welle 23: globaler Ref damit village_spawner/world_populator Chests befüllen
# können, ohne den item_manager als Parameter durchreichen zu müssen.
import items as _items_module
_items_module.set_global_item_manager(items)
world: World | None = None


# ─── Bind-Wrapper für Hintergrund-Worker + spell_caster-Callbacks ─────
# Die Worker (needs.run, status_effects.run, npc_worker.wander_loop …) und
# der spell_caster brauchen Callables mit fixen Signatures (player_id,
# amount). Hier binden wir die Service-Funktionen einmalig an die
# Modul-Globals. Aufrufer in ws/<domain>.py rufen die services-Funktionen
# direkt — diese Wrapper sind ausschließlich für die Hintergrund-Tasks.

async def heal_player(name: str, amount: int) -> None:
    await _heal_player_svc(manager, name, amount)


async def damage_player(name: str, dmg: int,
                        source_npc_id: int | None = None,
                        dmg_type: str = "physical") -> None:
    await _damage_player_svc(manager, name, dmg, source_npc_id, dmg_type)


async def _do_respawn(name: str, in_place: bool = False) -> None:
    await _do_respawn_svc(manager, world, structures, name, in_place=in_place)


async def _refund_mana(player_id: str, amount: int) -> None:
    await _refund_mana_svc(manager, player_id, amount)


async def _send_to_player(player_id: str, payload: dict) -> None:
    await _send_to_player_svc(manager, player_id, payload)


async def _apply_heal_aggro(player_id: str, x: int, y: int, threat: int) -> None:
    import combat
    await combat.apply_heal_aggro(npcs, player_id, x, y, threat)


async def _apply_spell_effects(player_id: str, spell_id: str,
                                spell: dict, target: dict) -> None:
    import loot
    import combat
    await spells.apply_spell_effects(
        manager, npcs, player_id, spell_id, spell, target,
        heal_player_fn=heal_player,
        do_respawn_fn=_do_respawn,
        is_downed_fn=_player_state.is_downed,
        send_to_player_fn=_send_to_player,
        find_drop_xy_fn=lambda x, y: loot.find_drop_xy(world, structures, x, y),
        drop_loot_for_npc_fn=lambda kid, npc, dx, dy:
            loot.drop_loot_for_npc(manager, items, kid, npc, dx, dy),
        gain_combat_xp_with_share_fn=lambda kid, amt, nx, ny:
            combat.gain_combat_xp_with_share(manager, kid, amt, nx, ny),
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
    # Populate läuft jetzt on-demand pro Chunk beim Connect/Chunk-Cross
    # (siehe populate_chunk_if_needed)

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
    weather_task = asyncio.create_task(weather_worker.weather_loop(manager, world))
    # Welle 53: Tick-Worker für defend/escort-Quests (Zeit/Position/Distanz).
    quest_tick_task = asyncio.create_task(
        quest_worker.run(manager, npcs, world, structures))
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
             dungeon_reaper_task, dungeon_spawn_task, quest_tick_task)
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

app.mount("/assets", StaticFiles(directory="../assets"), name="assets")


# Login + Admin bleiben Legacy-HTML (eigenständige Pages ohne Angular-
# Dependencies). Sie liegen in `frontend/public/`, werden von Angular
# unverändert ins Build-Dir kopiert und unterhalb von `dist/frontend/
# browser/` ausgeliefert. Die expliziten Routen unten haben Vorrang vor
# dem Catch-All-Mount (relevant, weil `/login` und `/admin` in Angular
# nicht als Routen existieren).
@app.get("/login")
async def login_page():
    return FileResponse("../frontend/dist/frontend/browser/login.html")


@app.get("/admin")
async def admin_page():
    return FileResponse("../frontend/dist/frontend/browser/admin.html")


# Manifest + Service-Worker (ngsw-worker.js, ngsw.json, safety-worker.js)
# werden seit F-PWA vom Angular-Build erzeugt und über den `/`-Static-Mount
# am Ende der Datei ausgeliefert. Keine dedizierten Routes nötig.


CHUNK_SEND_RADIUS = 3  # 7x7 Chunks (224×224 Tiles) um Spieler


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user = await auth.get_user_from_ws(websocket)
    if not user:
        await websocket.accept()
        await websocket.close(code=1008)
        return
    player_id = user["name"]
    state = await _load_or_create_player_svc(world, structures, player_id)
    spawn = {"x": state["x"], "y": state["y"]}
    await manager.connect(websocket, player_id, spawn["x"], spawn["y"])

    # Chunks um Spawn laden + senden (lazy gen für nicht-existierende)
    pcx, pcy, _, _ = World.world_to_chunk(spawn["x"], spawn["y"])
    chunks = await world.ensure_chunks_around(pcx, pcy, radius=CHUNK_SEND_RADIUS)
    # Populate als Background-Task, nicht-blockierend
    asyncio.create_task(
        world_populator.populate_chunks_bg(world, structures, manager, npcs, chunks))

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

    # Welle 25: Spell-Catalog für UI; sync_learned aktualisiert die Liste
    # vorher (auto-unlock anhand Magic-Skill).
    await spells.sync_learned_for_player(player_id)
    learned_spells = await spells.list_learned_for_player(player_id)

    # Flache attributes + stats fürs Charakter-UI (PlayerAttributes/PlayerStats).
    _combat_sheet = await __import__("attributes").player_combat_sheet(items, player_id)

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
        "dungeons": await dungeons.active_dungeon_markers(),   # Minimap-Ortung
        "events": await events.recent(20),
        "npcs": nearby_npcs,
        "items_ground": nearby_items,
        "inventory": await items.get_inventory(player_id),
        "wallet_copper": await currency.balance(player_id),
        "spawn": spawn,
        "hp": _combat_sheet["hp"],
        "max_hp": _combat_sheet["max_hp"],
        "mana": _combat_sheet["mana"],
        "max_mana": _combat_sheet["max_mana"],
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
        "attributes":   _combat_sheet["attributes"],
        "active_disasters": await disaster_state.list_active(),
        "stats":        _combat_sheet["stats"],
        "power_tier":   await power_budget.player_power_tier(player_id),
        "spell_catalog": spells.SPELLS,
        "learned_spells": learned_spells,
        "talents": {
            "learned":      await talents.list_learned(player_id),
            "points":       await talents.get_talent_points(player_id),
            "tree":         talents.tree_for_ui(
                                await skills.get_skills(player_id),
                                set(l["talent_id"] for l in await talents.list_learned(player_id)),
                                await talents.get_talent_points(player_id),
                            ),
        },
        "group":         await groups.group_snapshot(manager, player_id),
        "group_invites": await groups.list_invites_for(player_id),
    })

    # Welle 31: falls Spieler Party-Leader ist und gerade reconnected,
    # Reaper-Timer löschen
    _g = await groups.get_group_for(player_id)
    if _g and _g["kind"] == "party" and _g["leader"] == player_id:
        groups.mark_leader_online(_g["id"])
    # Alle Mitarbeiter-Anzeigen aktualisieren (Online-Status)
    if _g:
        await groups.broadcast_to_group(manager, _g["id"], {
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
            # B-final: alle Branches sind in ws/<domain>.py extrahiert,
            # der Dispatcher ist die einzige Anlaufstelle. Unbekannte
            # Message-Types werden still ignoriert.
            await ws_dispatch(ctx, data)

    except WebSocketDisconnect:
        pass   # normaler Verbindungsabbruch — Cleanup läuft im finally
    except Exception:
        # Welle 53: unerwarteter Fehler in der Receive-Loop (z.B. defektes
        # JSON-Frame). Nicht still verschlucken, aber die Verbindung sauber
        # über das finally räumen statt den Cleanup zu überspringen.
        logging.exception("WS-Receive-Loop für %s abgebrochen", player_id)
    finally:
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
                await groups.broadcast_to_group(manager, _g["id"], {
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


# Angular-Build als Root mounten. MUSS am Ende stehen, damit alle
# explizit registrierten Routen (/ws, /auth/*, /login, /admin,
# /assets/*) Vorrang haben. Manifest + Service-Worker + Icons kommen
# aus dem Angular-Build und werden ebenfalls hierüber ausgeliefert.
# FastAPI prüft Routes in Registrierungsreihenfolge, Mounts greifen
# als Fallback. html=True liefert index.html für unbekannte Paths
# (SPA-Routing).
app.mount(
    "/",
    StaticFiles(
        directory="../frontend/dist/frontend/browser",
        html=True,
    ),
    name="ng_root",
)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
