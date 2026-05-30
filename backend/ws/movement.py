"""Movement-Handler (Phase B3): move, sprint.

Behält 1:1 das Verhalten aus dem Legacy-Block in main.py:
- Overworld-Move: walkability, chunk-shift, db-update, broadcast,
  auto-pickup, quest-hooks, trap-check.
- Dungeon-Move: floor-bounds, trap-trigger, auto-pickup, stairs.
- Sprint: Frontend-Flag an needs.set_sprint.
"""
from __future__ import annotations

import asyncio
import logging

import combat
import db
import dungeon_instance
import needs
import npcs as npcs_mod
import quest_stages
import quests
import spell_caster
import status_effects
import world_populator
from dungeons import dungeon_floor_payload
from services.player_state import damage_player as damage_player_svc, is_downed
from world import World

from .context import WsContext
from .dispatcher import register


CHUNK_SEND_RADIUS = 3  # 7x7 Chunks (224×224 Tiles) um Spieler

DUNGEON_TRAP_DMG = {
    "spike_trap": 14, "dart_trap": 12, "fire_trap": 22,
    "frost_trap": 16, "poison_trap": 10, "rockfall_trap": 24,
}
DUNGEON_TRAP_LABEL = {
    "spike_trap":    "🗡️ Stachelfalle! Spitzen schießen aus dem Boden.",
    "dart_trap":     "🎯 Pfeilfalle! Bolzen aus der Wand.",
    "fire_trap":     "🔥 Feuerfalle! Eine Stichflamme schlägt hoch.",
    "frost_trap":    "❄️ Frostfalle! Eisige Dornen.",
    "poison_trap":   "☠️ Giftfalle! Eine grüne Wolke zischt hervor.",
    "rockfall_trap": "🪨 Steinschlag! Die Decke bricht herab.",
}


async def handle_move(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    items = ctx.items
    npcs = ctx.npcs

    # Welle 25: Down-State blockt Bewegung
    if is_downed(player_id):
        return
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
            return
        dungeon_id, floor_idx = parsed
        floor = await dungeon_instance.get_floor(dungeon_id, floor_idx)
        if floor is None:
            return
        size = floor["size"]
        tiles = floor["tiles"]
        if not (0 <= x < size and 0 <= y < size
                and dungeon_instance.is_walkable_tile(tiles[y][x])):
            return
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
            _tdmg = DUNGEON_TRAP_DMG.get(_trap, 12)
            await damage_player_svc(manager, player_id, _tdmg)
            if _trap == "poison_trap":
                try: await status_effects.apply("player", player_id,
                        "poisoned", magnitude=4, duration_seconds=20)
                except Exception: pass
            await websocket.send_json({
                "type": "trap_triggered", "x": x, "y": y,
                "kind": _trap, "dmg": _tdmg,
                "text": DUNGEON_TRAP_LABEL.get(_trap, "💥 Falle ausgelöst!"),
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
                        "npcs": npcs_mod.overworld_npcs_near(npcs, ow[0], ow[1]),
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
                    _extra = await dungeon_floor_payload(npcs, dungeon_id, floor_idx - 1)
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
                    _extra = await dungeon_floor_payload(npcs, dungeon_id, floor_idx + 1)
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
        return
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
            asyncio.create_task(world_populator.populate_chunks_bg(
                world, structures, manager, npcs, new_chunks))
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
                await damage_player_svc(manager, player_id, trap_dmg)


async def handle_sprint(ctx: WsContext, data: dict) -> None:
    # Frontend meldet Sprint-Zustand (SHIFT gehalten + in Bewegung).
    # run_stamina verbraucht dann Ausdauer/s und stoppt bei 0.
    needs.set_sprint(ctx.player_id, bool(data.get("on")))


register("move", handle_move)
register("sprint", handle_sprint)
