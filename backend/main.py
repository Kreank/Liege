import asyncio
import logging
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
import quest_stages
import dungeon_instance
import attributes
import trade
import world_populator
from ws_manager import ConnectionManager
from world import World
from structures import StructureManager
from events import EventManager
from npcs import NPCManager
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
world: World | None = None


async def _find_drop_xy(x: int, y: int) -> tuple[int, int]:
    """Return a coordinate suitable for ground-loot near (x, y).

    If (x, y) is walkable and not blocked by a structure, returns it as-is.
    Otherwise searches outward in a spiral up to radius 3 for the first
    walkable, non-blocked tile. Falls back to (x, y) if nothing is found.
    """
    if world is not None and await world.is_walkable(x, y) and not structures.blocks(x, y):
        return x, y
    for radius in range(1, 4):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if abs(dx) != radius and abs(dy) != radius:
                    continue
                nx, ny = x + dx, y + dy
                if world is not None and await world.is_walkable(nx, ny) and not structures.blocks(nx, ny):
                    return nx, ny
    return x, y


@asynccontextmanager
async def lifespan(app: FastAPI):
    global world
    await db.init_db()
    await llm.init_llm()
    world = await World.load_or_create(seed=42)
    await structures.load()
    await npcs.load()
    # Welle 27: Faction-System seeden + bestehende NPCs zuweisen
    await factions.seed_defaults()
    updated_npc_factions = await factions.assign_faction_to_existing_npcs()
    if updated_npc_factions:
        logging.info("Faction-IDs gesetzt für %d NPCs", updated_npc_factions)
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
    # Welle 24: Disaster-Tick (refresht Cache, broadcastet ended-Events)
    disaster_task = asyncio.create_task(disaster_state.run(manager))

    yield

    tasks = (event_task, wander_task, item_task, spawn_task, respawn_task,
             farm_task, world_respawn_task, needs_task, bill_task, mood_task,
             raid_task, time_task, status_task)
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


DEFAULT_SPAWN_CENTER = (60, 40)  # nahe Mitte der Legacy-Welt
CHUNK_SEND_RADIUS = 3  # 7x7 Chunks (224×224 Tiles) um Spieler


async def _populate_chunks_bg(chunks) -> None:
    """Background-Population eines Chunks-Sets — broadcastet structure_placed pro Item."""
    try:
        for c in chunks:
            await world_populator.populate_chunk_if_needed(
                world, structures, manager, c["cx"], c["cy"],
                npc_manager=npcs,
            )
    except Exception:
        logging.getLogger("liege.populate_bg").exception("Background-Populate fehlgeschlagen")


async def _list_learned_spells(player_name: str) -> list[str]:
    rows = await db.pool().fetch(
        "SELECT spell_kind FROM learned_spells WHERE player_name = $1",
        player_name,
    )
    return [r["spell_kind"] for r in rows]


async def _compute_attributes(player_name: str) -> dict:
    """Sammelt Skills + Equipment + Talents und berechnet Attribute."""
    sk = await skills.get_skills(player_name)
    inv = await items.get_inventory(player_name)
    equipped = [it for it in inv if it.get("equipped_slot")]
    te = await talents.aggregate_effects(player_name)
    bp = await body_parts.get_body_parts(player_name)
    attrs = attributes.calculate_attributes(sk, equipped, te, bp)
    return {"values": attrs, "labels": attributes.ATTR_LABELS}


async def _build_stat_sheet(player_name: str) -> dict:
    """Vollständiges Stat-Sheet (Welle 15): Attribute + Allokation + Resistances."""
    import player_stats as _ps
    inv = await items.get_inventory(player_name)
    equipped = [it for it in inv if it.get("equipped_slot")]
    te = await talents.aggregate_effects(player_name)
    bp = await body_parts.get_body_parts(player_name)
    sheet = await _ps.get_stat_sheet(player_name, equipped, te, bp)
    sheet["labels"] = attributes.ATTR_LABELS
    return sheet


async def _send_attrs_update(websocket, player_name: str) -> None:
    """Schickt einen frischen Stat-Sheet-Snapshot. Bei jedem Equip/Allocation."""
    try:
        sheet = await _build_stat_sheet(player_name)
        await websocket.send_json({"type": "attrs_update", "stats": sheet})
    except Exception:
        logging.exception("attrs_update fehlgeschlagen")


async def load_or_create_player(name: str) -> dict:
    row = await db.pool().fetchrow(
        "SELECT x, y, hp, max_hp, mana, max_mana, hunger, max_hunger, "
        "stamina, max_stamina, thirst, max_thirst FROM players WHERE name = $1", name
    )
    if row is not None:
        await db.pool().execute(
            "UPDATE players SET last_seen = NOW() WHERE name = $1", name
        )
        spawn = {
            "x": row["x"], "y": row["y"],
            "hp": row["hp"], "max_hp": row["max_hp"],
            "mana": row["mana"], "max_mana": row["max_mana"],
            "hunger": row["hunger"], "max_hunger": row["max_hunger"],
            "stamina": row["stamina"], "max_stamina": row["max_stamina"],
            "thirst": row["thirst"], "max_thirst": row["max_thirst"],
        }
        walkable = await world.is_walkable(spawn["x"], spawn["y"])
        if not walkable or structures.blocks(spawn["x"], spawn["y"]):
            new_pos = await world.find_spawn(*DEFAULT_SPAWN_CENTER)
            spawn["x"], spawn["y"] = new_pos["x"], new_pos["y"]
            await db.pool().execute(
                "UPDATE players SET x = $1, y = $2 WHERE name = $3",
                spawn["x"], spawn["y"], name,
            )
        return spawn

    pos = await world.find_spawn(*DEFAULT_SPAWN_CENTER)
    await db.pool().execute(
        "INSERT INTO players (name, x, y) VALUES ($1, $2, $3)",
        name, pos["x"], pos["y"],
    )
    return {
        "x": pos["x"], "y": pos["y"],
        "hp": combat.PLAYER_MAX_HP, "max_hp": combat.PLAYER_MAX_HP,
        "mana": combat.PLAYER_MAX_MANA, "max_mana": combat.PLAYER_MAX_MANA,
        "hunger": 100, "max_hunger": 100,
        "stamina": 100, "max_stamina": 100,
    }


async def get_equipped_weapon_kind(player_name: str) -> str | None:
    row = await db.pool().fetchrow(
        "SELECT kind FROM items WHERE owner = $1 AND equipped_slot = 'weapon'",
        player_name,
    )
    return row["kind"] if row else None


async def get_equipped_tool_kind(player_name: str) -> str | None:
    row = await db.pool().fetchrow(
        "SELECT kind FROM items WHERE owner = $1 AND equipped_slot = 'tool'",
        player_name,
    )
    return row["kind"] if row else None


# Welche Tools/Waffen welchem Harvest-Skill genügen
# Werden gegen items.equipped_slot IN ('tool', 'weapon') geprüft.
TOOL_FOR_SKILL = {
    "mining":       {"pickaxe"},
    "woodcutting":  {"axe"},
    "gathering":    {"sickle", "scythe", "hoe", "shovel"},  # Sichel (tool), Sense (weapon), oder Hacke/Schaufel
    "construction": {"hammer"},
}

# Welche Strukturen welches Tool brauchen.
# Mapping prop_type → skill_name. Default ist "gathering" (Sichel/Hacke).
PROP_SKILL = {
    # Holz → Axt
    "tree_oak": "woodcutting", "tree_pine": "woodcutting", "tree_dead": "woodcutting",
    "tree_stump": "woodcutting", "fallen_log": "woodcutting", "palm_tree": "woodcutting",
    "swamp_log": "woodcutting",
    "broken_cart": "woodcutting", "barrel": "woodcutting", "crate": "woodcutting",
    "fence": "woodcutting", "dock_straight": "woodcutting", "dock_corner": "woodcutting",
    "wooden_bridge": "woodcutting", "shipwreck": "woodcutting", "boat_small": "woodcutting",
    "driftwood": "woodcutting", "camp_tent": "woodcutting",
    # Stein → Spitzhacke
    "rock_small": "mining", "rock_large": "mining", "rock_mossy": "mining",
    "ruin_pillar": "mining", "rubble": "mining", "statue_broken": "mining",
    "gravestone": "mining", "lava_rock": "mining", "snow_rock": "mining",
    "ice_crystal": "mining", "anchor": "mining", "cooking_pot": "mining",
    # Pflanzen/Stoff → Sichel/Hacke/Schaufel
    "bush": "gathering", "tall_grass": "gathering", "flowers": "gathering",
    "mushrooms": "gathering", "reeds": "gathering", "lily_pads": "gathering",
    "sack": "gathering", "fishing_net": "gathering",
    "cactus": "gathering", "desert_skull": "gathering", "dry_bush": "gathering",
    "jungle_flower": "gathering", "jungle_vines": "gathering",
    "frozen_bush": "gathering", "swamp_bubbles": "gathering",
    "bones_scatter": "gathering",
}

# Tool-Hint-Text pro Skill für UI-Feedback
TOOL_HINT = {
    "mining":      "⛏️ Du brauchst eine Spitzhacke",
    "woodcutting": "🪓 Du brauchst eine Axt",
    "gathering":   "🌿 Du brauchst eine Sichel oder Hacke",
}

# Basic-Props die OHNE Tool harvestbar bleiben — wichtig damit neue Spieler
# überhaupt Wood/Stone für die ersten Tools bekommen.
NO_TOOL_PROPS = {"tree_stump", "fallen_log", "rubble", "driftwood"}


async def has_tool_for_skill(player_name: str, skill: str) -> bool:
    """Prüft ob ein passendes Tool/Waffe equipped ist für diesen Skill."""
    tools = TOOL_FOR_SKILL.get(skill, set())
    if not tools:
        return False
    row = await db.pool().fetchrow(
        "SELECT 1 FROM items WHERE owner = $1 "
        "AND equipped_slot IN ('tool', 'weapon') AND kind = ANY($2::text[]) LIMIT 1",
        player_name, list(tools),
    )
    return row is not None


async def heal_player(name: str, amount: int) -> None:
    """Heilt einen Spieler bis max_hp. Broadcastet player_healed.
    Bei voller Heilung werden auch Body-Parts wiederhergestellt."""
    row = await db.pool().fetchrow("SELECT hp, max_hp, x, y FROM players WHERE name = $1", name)
    if row is None:
        return
    new_hp = min(row["max_hp"], row["hp"] + amount)
    # Heiltrank o.ä. mit großem Heal heilt auch Body-Parts
    if amount >= 25:
        await body_parts.heal_all_parts(name)
    if new_hp == row["hp"]:
        return
    await db.pool().execute("UPDATE players SET hp = $1 WHERE name = $2", new_hp, name)
    ws = manager.connections.get(name)
    if ws is not None:
        await ws.send_json({
            "type":   "player_healed",
            "hp":     new_hp,
            "max_hp": row["max_hp"],
            "amount": new_hp - row["hp"],
        })
    await manager.broadcast({
        "type": "visual_effect",
        "kind": "heal_glow",
        "x":    row["x"],
        "y":    row["y"],
    })


async def restore_mana(name: str, amount: int) -> None:
    row = await db.pool().fetchrow("SELECT mana, max_mana FROM players WHERE name = $1", name)
    if row is None:
        return
    new_mana = min(row["max_mana"], row["mana"] + amount)
    if new_mana == row["mana"]:
        return
    await db.pool().execute("UPDATE players SET mana = $1 WHERE name = $2", new_mana, name)
    ws = manager.connections.get(name)
    if ws is not None:
        await ws.send_json({
            "type":     "player_mana",
            "mana":     new_mana,
            "max_mana": row["max_mana"],
        })


# Cooldown-Tracking für Heal-Strukturen: dict[(player_name, struct_id)] → timestamp
_heal_cooldowns: dict[tuple[str, int], float] = {}
# Cooldown-Tracking für Dungeon-Encounter (1 Eintrag pro Spieler)
_dungeon_cooldowns: dict[str, float] = {}


async def damage_player(name: str, dmg: int, source_npc_id: int | None = None,
                        dmg_type: str = "physical") -> None:
    """Wendet Schaden auf einen Spieler an. Wenn HP ≤ 0 → Respawn.
    Berücksichtigt Armor-Defense + Shield-Status + Element-Resistance."""
    # Welle 23 — Godmode während Character-Creation: kein Schaden bevor
    # der Spieler den Character bestätigt hat.
    cc_row = await db.pool().fetchrow(
        "SELECT character_created FROM players WHERE name = $1", name,
    )
    if cc_row is None or not cc_row["character_created"]:
        return
    # Armor-Defense gilt nur für physical-Damage (Welle 15)
    import item_stats as _is
    if dmg_type == "physical":
        rows = await db.pool().fetch(
            "SELECT kind, quality FROM items WHERE owner = $1 "
            "AND equipped_slot IN ('helmet','chestplate','shield','boots')",
            name,
        )
        total_def = sum(_is.armor_defense(r["kind"], r["quality"]) for r in rows)
        dr_pct = _is.damage_reduction(total_def)
        dmg = max(1, int(round(dmg * (1.0 - dr_pct))))
    else:
        # Element/Magic: Player-Resistance anwenden (kombiniert DB-Basis
        # + Affix-Boni von equipped). Lookup nur DB-Basis hier (schnell);
        # Affix-Boni werden separat bei Equipping in der DB aufaddiert über
        # apply_equipment_to_resists()… für jetzt: nur Basis.
        try:
            import player_stats as _ps
            resist = await _ps.player_resistance(name, dmg_type)
            dmg = _ps.apply_resist_to_damage(dmg, resist)
        except Exception:
            pass
    # Status-Effekt 'shielded'
    try:
        import status_effects as _se
        shield_factor = await _se.damage_reduction_for("player", name)
        dmg = max(1, int(round(dmg * shield_factor)))
    except Exception:
        pass
    # Erst Body-Part-Damage (atmosphärisch + Effekte)
    part_result = await body_parts.damage_random_part(name, dmg)
    if part_result:
        ws_part = manager.connections.get(name)
        if ws_part is not None:
            await ws_part.send_json({"type": "body_part_damaged", **part_result})
    row = await db.pool().fetchrow(
        "SELECT hp, max_hp FROM players WHERE name = $1", name
    )
    if row is None:
        return
    new_hp = max(0, row["hp"] - dmg)
    if new_hp == 0:
        spawn = await world.find_spawn(*DEFAULT_SPAWN_CENTER)
        await db.pool().execute(
            "UPDATE players SET hp = max_hp, x = $1, y = $2 WHERE name = $3",
            spawn["x"], spawn["y"], name,
        )
        manager.update_player(name, spawn["x"], spawn["y"])
        ws = manager.connections.get(name)
        if ws is not None:
            await ws.send_json({
                "type":  "player_respawned",
                "x":     spawn["x"],
                "y":     spawn["y"],
                "hp":    row["max_hp"],
                "max_hp": row["max_hp"],
            })
        await manager.broadcast({"type": "player_died", "player_id": name}, exclude=name)
        await manager.broadcast({
            "type": "player_moved",
            "player_id": name,
            "x":   spawn["x"],
            "y":   spawn["y"],
        }, exclude=name)
        return
    await db.pool().execute(
        "UPDATE players SET hp = $1 WHERE name = $2", new_hp, name
    )
    ws = manager.connections.get(name)
    if ws is not None:
        await ws.send_json({
            "type":  "player_damaged",
            "hp":    new_hp,
            "max_hp": row["max_hp"],
            "by":    source_npc_id,
            "dmg":   dmg,
        })


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
        "events": await events.recent(20),
        "npcs": nearby_npcs,
        "items_ground": nearby_items,
        "inventory": await items.get_inventory(player_id),
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
        "learned_spells": await _list_learned_spells(player_id),
        "talents": {
            "learned":      await talents.list_learned(player_id),
            "points":       await talents.get_talent_points(player_id),
            "tree":         talents.tree_for_ui(
                                await skills.get_skills(player_id),
                                set(l["talent_id"] for l in await talents.list_learned(player_id)),
                                await talents.get_talent_points(player_id),
                            ),
        },
    })

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

            if mtype == "move":
                x, y = data["x"], data["y"]
                # Welle 9b: bei Dungeon-Aufenthalt anders validieren
                cur_world = await dungeon_instance.get_player_world(player_id)
                if cur_world != "overworld":
                    # Dungeon-Tile-Validierung
                    dungeon_id = int(cur_world.split(":")[1])
                    drow = await db.pool().fetchrow(
                        "SELECT tiles, size FROM dungeons WHERE id = $1", dungeon_id,
                    )
                    if drow:
                        import json as _json
                        tiles = drow["tiles"]
                        if isinstance(tiles, str):
                            tiles = _json.loads(tiles)
                        if (0 <= x < drow["size"] and 0 <= y < drow["size"]
                                and dungeon_instance.is_walkable_tile(tiles[y][x])):
                            manager.update_player(player_id, x, y)
                            await db.pool().execute(
                                "UPDATE players SET x = $1, y = $2, last_seen = NOW() "
                                "WHERE name = $3",
                                x, y, player_id,
                            )
                            # Stairs_up?
                            import dungeon_world as _dw
                            if tiles[y][x] == _dw.STAIRS_UP:
                                # Exit zurück zur Overworld
                                ow = await dungeon_instance.exit_dungeon(player_id)
                                if ow:
                                    manager.update_player(player_id, ow[0], ow[1])
                                    # Frische Overworld-Chunks senden
                                    cx_, cy_, _, _ = World.world_to_chunk(ow[0], ow[1])
                                    new_chunks = await world.ensure_chunks_around(
                                        cx_, cy_, radius=CHUNK_SEND_RADIUS,
                                    )
                                    await websocket.send_json({
                                        "type": "dungeon_exit",
                                        "spawn": {"x": ow[0], "y": ow[1]},
                                        "chunks": new_chunks,
                                    })
                                    await websocket.send_json({
                                        "type": "toast",
                                        "text": "🌅 Du verlässt das Dungeon.",
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
                    # Auto-Spread: löst den "Streifen am Wand-Tile"-Effekt, der
                    # entsteht weil Wand-Sprites nur ~27px in der Mitte des 64px-
                    # Tiles füllen — ohne Boden darunter sieht man den Untergrund.
                    if type_ == "floor":
                        # Boden gesetzt → unter angrenzende Wände auch Boden
                        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
                            nx, ny = x + dx, y + dy
                            obj_neighbor = structures.object_at(nx, ny)
                            if not obj_neighbor or obj_neighbor["type"] != "wall":
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
                    elif type_ == "wall":
                        # Wand neben existierendem Boden gesetzt → Boden auch
                        # unter diese Wand. Material vom angrenzenden Boden
                        # (sonst stimmt der Look nicht: stone-Floor mit wood-Wand-
                        # Lücke käme komisch).
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
                if abs(x - player["x"]) + abs(y - player["y"]) > 1:
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
                if abs(int(ground["x"]) - player["x"]) + abs(int(ground["y"]) - player["y"]) > 1:
                    continue  # zu weit weg (Sanity-Check — Frontend prüft auch)
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
                if combat.manhattan(player["x"], player["y"], npc["x"], npc["y"]) > attack_range:
                    continue
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
                    # Loot droppen — wenn NPC-Tile durch Struktur geblockt ist,
                    # weiche auf den ersten freien Nachbar aus.
                    drop_x, drop_y = await _find_drop_xy(npc["x"], npc["y"])
                    for drop_kind in loot.roll_loot(npc["kind"]):
                        dropped = await items.spawn_on_ground(drop_kind, drop_x, drop_y)
                        if dropped is not None:
                            await manager.broadcast({
                                "type": "item_spawned", "item": dropped,
                            })
                    # Welle 23: Boss-Garantie-Equipment-Drop (high quality)
                    import npc_worker as _nw
                    if npc["kind"] in _nw.BOSS_KINDS:
                        boss_eq = loot.roll_boss_equipment()
                        if boss_eq:
                            eq_kind, eq_q = boss_eq
                            dropped = await items.spawn_on_ground(
                                eq_kind, drop_x, drop_y, quality_kind=eq_q,
                            )
                            if dropped is not None:
                                await manager.broadcast({
                                    "type": "item_spawned", "item": dropped,
                                })
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
                xp_result = await skills.gain_xp(player_id, "combat", max(2, dmg // 2))
                if xp_result:
                    await websocket.send_json({"type": "skill_xp", **xp_result})

            elif mtype == "cast_spell":
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
                            key=lambda n: combat.manhattan(player_pos["x"], player_pos["y"], n["x"], n["y"]),
                        )
                        dist = combat.manhattan(player_pos["x"], player_pos["y"], target["x"], target["y"])
                        if dist <= spell["range"]:
                            aoe = spell.get("aoe_radius", 0)
                            if aoe > 0:
                                targets = [
                                    n for n in candidates
                                    if combat.manhattan(target["x"], target["y"], n["x"], n["y"]) <= aoe
                                ]
                            else:
                                targets = [target]
                            # Welle 40: Spell-spezifischer Visual-Effekt
                            spell_fx = {
                                "spell_book": "fireball_explosion",
                                "scroll":     "lightning_strike",
                                "rune_stone": "heal_glow",
                            }.get(row["kind"], "fireball_explosion")
                            await manager.broadcast({
                                "type": "visual_effect", "kind": spell_fx,
                                "x": target["x"], "y": target["y"],
                            })
                            # Welle 15: Spell-Damage-Typ je nach Spell-Item
                            _spell_dmg_type = {
                                "spell_book": "fire",
                                "scroll":     "lightning",
                                "rune_stone": "magic",
                            }.get(row["kind"], "magic")
                            for t in targets:
                                _final = combat.apply_creature_resists(
                                    t["kind"], spell["damage"], dmg_type=_spell_dmg_type
                                )
                                result = await npcs.damage(t["id"], _final)
                                if result is None:
                                    drop_x, drop_y = await _find_drop_xy(t["x"], t["y"])
                                    for drop_kind in loot.roll_loot(t["kind"]):
                                        dropped = await items.spawn_on_ground(drop_kind, drop_x, drop_y)
                                        if dropped:
                                            await manager.broadcast({
                                                "type": "item_spawned", "item": dropped,
                                            })
                                    # Welle 23: Boss-Garantie-Equipment auch via Spell-Kill
                                    import npc_worker as _nw2
                                    if t["kind"] in _nw2.BOSS_KINDS:
                                        boss_eq2 = loot.roll_boss_equipment()
                                        if boss_eq2:
                                            eq_kind2, eq_q2 = boss_eq2
                                            dropped = await items.spawn_on_ground(
                                                eq_kind2, drop_x, drop_y, quality_kind=eq_q2,
                                            )
                                            if dropped:
                                                await manager.broadcast({
                                                    "type": "item_spawned", "item": dropped,
                                                })
                                    await manager.broadcast({
                                        "type": "npc_died", "npc_id": t["id"],
                                        "killed_by": player_id, "name": t["name"],
                                    })
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
                if not structures.is_combat_structure(s["type"]):
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
                if combat.manhattan(player["x"], player["y"], x, y) > attack_range:
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
                if not structures.is_combat_structure(s["type"]):
                    continue
                if not structures.can_modify(player_id, s):
                    await websocket.send_json({
                        "type": "toast", "text": "🔒 Du bist nicht der Eigentümer.",
                    })
                    continue
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                if combat.manhattan(player["x"], player["y"], x, y) > 1:
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
                if not structures.is_combat_structure(s["type"]):
                    continue
                if not structures.can_modify(player_id, s):
                    await websocket.send_json({
                        "type": "toast", "text": "🔒 Du bist nicht der Eigentümer.",
                    })
                    continue
                player = manager.get_players().get(player_id)
                if player is None:
                    continue
                if combat.manhattan(player["x"], player["y"], x, y) > 1:
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
                if combat.manhattan(player["x"], player["y"], x, y) > 1:
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
                    # Welle 9b: echtes Betreten — Player wechselt Welt
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
                    dungeon = await dungeon_instance.enter_dungeon(
                        player_id, s["x"], s["y"],
                        cur_player["x"], cur_player["y"],
                    )
                    # Server-Position auch in-memory updaten
                    manager.update_player(player_id, dungeon["spawn_x"], dungeon["spawn_y"])
                    await websocket.send_json({
                        "type": "dungeon_enter",
                        "dungeon_id": dungeon["id"],
                        "name":       dungeon["name"],
                        "theme":      dungeon.get("theme"),
                        "size":       dungeon["size"],
                        "tiles":      dungeon["tiles"],
                        "spawn":      {"x": dungeon["spawn_x"], "y": dungeon["spawn_y"]},
                    })
                    await websocket.send_json({
                        "type": "toast",
                        "text": f"🏚️ Du betrittst: {dungeon['name'].split(':')[0]}",
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
                if abs(x - player["x"]) + abs(y - player["y"]) > 1:
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
                if abs(x - player["x"]) + abs(y - player["y"]) > 1:
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
                if abs(x - player["x"]) + abs(y - player["y"]) > 1:
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
                # Welle 22: Crafting an Station gibt +1 Forschungs-Pool
                _new_pool = await research.award_points(player_id, 1, f"craft:{station}")
                await websocket.send_json({
                    "type": "research_pool_update", "pool": _new_pool,
                    "gained": 1, "reason": f"🔨 {station}",
                })
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
                if player is None or combat.manhattan(player["x"], player["y"], npc["x"], npc["y"]) > 2:
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
                counts = await items.count_owned_by_kind(player_id)
                await websocket.send_json({
                    "type":      "trade_open",
                    "npc_id":    npc_id,
                    "npc_name":  npc["name"],
                    "offerings": offerings,
                    "coins":     counts.get("gold_ore", 0),
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
                counts = await items.count_owned_by_kind(player_id)
                if counts.get("gold_ore", 0) < price:
                    await websocket.send_json({"type": "toast", "text": "Nicht genug Münzen"})
                    continue
                # Social-XP für Trade
                sxp = await skills.gain_xp(player_id, "social", 3)
                if sxp:
                    await websocket.send_json({"type": "skill_xp", **sxp})
                for _ in range(price):
                    await items.consume_one(player_id, "gold_ore")
                created = await items.create_for_player(kind, player_id)
                if created is None:
                    continue
                inv = await items.get_inventory(player_id)
                await websocket.send_json({"type": "inventory_full_refresh", "inventory": inv})
                new_counts = await items.count_owned_by_kind(player_id)
                await websocket.send_json({
                    "type": "trade_coins", "coins": new_counts.get("gold_ore", 0),
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
                if kind == "gold_ore":
                    continue  # Currency selber nicht verkaufbar
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
                for _ in range(price):
                    await items.create_for_player("gold_ore", player_id)
                inv = await items.get_inventory(player_id)
                await websocket.send_json({"type": "inventory_full_refresh", "inventory": inv})
                new_counts = await items.count_owned_by_kind(player_id)
                await websocket.send_json({
                    "type": "trade_coins", "coins": new_counts.get("gold_ore", 0),
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
                log.info("Character created: %s preset=%s name=%s alloc=%s",
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
                # XP
                if "xp" in reward:
                    xp_res = await skills.gain_xp(player_id, "combat", int(reward["xp"]))
                    if xp_res:
                        await websocket.send_json({"type": "skill_xp", **xp_res})
                # Gold (als copper_coin-Stack)
                gold = int(reward.get("gold", 0))
                if gold > 0:
                    created = await items.create_for_player("copper_coin", player_id)
                    if created and gold > 1:
                        # quantity hochsetzen
                        await db.pool().execute(
                            "UPDATE items SET quantity = quantity + $2 WHERE id = $1",
                            created["id"], gold - 1,
                        )
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
                # Reward verteilen
                reward = target_q.get("reward") or {}
                for item_kind, count in reward.items():
                    if item_kind == "xp":
                        # XP wird an Combat-Skill verteilt (pragmatisch)
                        xp_result = await skills.gain_xp(player_id, "combat", int(count))
                        if xp_result:
                            await websocket.send_json({"type": "skill_xp", **xp_result})
                        continue
                    for _ in range(int(count)):
                        created = await items.create_for_player(item_kind, player_id)
                        if created is not None:
                            await websocket.send_json({"type": "inventory_add", "item": created})
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
