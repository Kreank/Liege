"""Structures-Handler (Phase B15): dungeon_chest, place_structure,
toggle_door, remove_structure, attack_structure, repair_structure,
upgrade_structure, use_structure (mit chest/quest_board/stairs_down/
farm_plot/bed/well-Sub-Branches), fill_container, water_plant,
drink_container, drink_water_tile.

Behält 1:1 das Verhalten aus den Legacy-Blocks in main.py.
"""
from __future__ import annotations

import asyncio
import logging
import time

import combat
import currency
import db
import disaster_state
import dungeon_instance
import dungeon_tiers
import harvest
import needs
import player_events
import quests
import recipes
import skills
import status_effects
import talents

from dungeons import dungeon_floor_payload
from services.player_equipment import (
    has_tool_for_skill, PROP_SKILL, TOOL_HINT, NO_TOOL_PROPS,
    get_equipped_weapon_kind,
)
from services.player_state import (
    heal_player as heal_player_svc,
    damage_player as damage_player_svc,
)

from .context import WsContext
from .dispatcher import register


# Cooldown-Tracking für Heal-Strukturen: dict[(player_name, struct_id)] → timestamp
# Modul-lokal, da nur use_structure es liest/schreibt.
_heal_cooldowns: dict[tuple[str, int], float] = {}


async def handle_dungeon_chest(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    items = ctx.items
    # Dungeon-Schatzkiste öffnen (Auto-Loot direkt ins Inventar).
    cw = await dungeon_instance.get_player_world(player_id)
    parsed = dungeon_instance.parse_world_id(cw)
    if parsed is None:
        return
    _did, _fidx = parsed
    ccx, ccy = int(data.get("x", 0)), int(data.get("y", 0))
    _pp = manager.get_players().get(player_id)
    if _pp is None:
        return
    if max(abs(ccx - _pp["x"]), abs(ccy - _pp["y"])) > 1:
        await websocket.send_json({"type": "toast", "text": "🧰 Zu weit weg."})
        return
    if not await dungeon_instance.chest_at(_did, _fidx, ccx, ccy):
        return
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


async def handle_place_structure(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    events = ctx.events
    x, y, type_ = data["x"], data["y"], data["structure_type"]
    material = data.get("material", "stone")
    rotation = int(data.get("rotation", 0) or 0)
    if not await world.is_walkable(x, y):
        return
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
            return
        else:
            await websocket.send_json({
                "type": "toast",
                "text": "🚪 Türen brauchen eine Wand zum Einsetzen",
            })
            return
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
                return
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


async def handle_toggle_door(ctx: WsContext, data: dict) -> None:
    player_id = ctx.player_id
    manager = ctx.manager
    structures = ctx.structures
    x, y = int(data.get("x", 0)), int(data.get("y", 0))
    # Reichweite: 1 Tile (orthogonal benachbart oder gleiches Tile)
    player = manager.get_players().get(player_id)
    if player is None:
        return
    if combat.chebyshev(player["x"], player["y"], x, y) > 1:
        return
    struct = structures.object_at(x, y)
    if struct is None:
        return
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
        return
    await db.pool().execute(
        "UPDATE structures SET type = $1 WHERE id = $2", new_type, struct["id"],
    )
    struct["type"] = new_type
    await manager.broadcast({
        "type": "structure_replaced",
        "x": x, "y": y, "structure": struct,
    })


async def handle_remove_structure(ctx: WsContext, data: dict) -> None:
    manager = ctx.manager
    structures = ctx.structures
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


async def handle_attack_structure(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    structures = ctx.structures
    # Welle 25: Spieler greift Struktur an (eigene Wand zerstören
    # in Build-Mode geht weiter via remove_structure Long-Press).
    # Hier: feindliche Strukturen (Bandit-Camp-Strukturen, fremde
    # Wände) angreifen mit der ausgerüsteten Waffe.
    x, y = int(data.get("x", -1)), int(data.get("y", -1))
    s = structures.object_at(x, y) or structures.floor_at(x, y)
    if s is None:
        return
    from structures import is_combat_structure as _is_cs
    if not _is_cs(s["type"]):
        # Harvestables (Bäume/Pflanzen/Felsen — z. B. carrot_plant, wheat_grown,
        # tall_grass) sind KEINE Combat-Strukturen: sie werden GEERNTET, nicht
        # bekämpft. Das Frontend routet Harvest-Klicks (Sichel auf Getreide/
        # Karotten) als attack_structure hierher — wir delegieren an den
        # Ernte-Pfad in use_structure (Tool-Check, Yield, Durability, Quests).
        if harvest.is_harvestable(s["type"]):
            await handle_use_structure(ctx, data)
            return
        await websocket.send_json({
            "type": "toast", "text": "Diese Struktur kann nicht angegriffen werden.",
        })
        return
    player = manager.get_players().get(player_id)
    if player is None:
        return
    # Range-Check
    weapon = await get_equipped_weapon_kind(player_id)
    import item_stats as _is_struct
    attack_range = max(combat.ATTACK_RANGE, _is_struct.weapon_range(weapon))
    if combat.chebyshev(player["x"], player["y"], x, y) > attack_range:
        await websocket.send_json({"type": "toast", "text": "Zu weit weg."})
        return
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


async def handle_repair_structure(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    structures = ctx.structures
    items = ctx.items
    # Welle 25: Mit equipped hammer + 1 Material gleicher Sorte
    # die Struktur reparieren. +8 HP pro Klick, cap = max_durability.
    x, y = int(data.get("x", -1)), int(data.get("y", -1))
    s = structures.object_at(x, y) or structures.floor_at(x, y)
    if s is None:
        return
    from structures import is_combat_structure as _is_cs
    if not _is_cs(s["type"]):
        return
    if not structures.can_modify(player_id, s):
        await websocket.send_json({
            "type": "toast", "text": "🔒 Du bist nicht der Eigentümer.",
        })
        return
    player = manager.get_players().get(player_id)
    if player is None:
        return
    if combat.chebyshev(player["x"], player["y"], x, y) > 1:
        await websocket.send_json({"type": "toast", "text": "🤚 Zu weit weg."})
        return
    if s["durability"] >= s.get("max_durability", s["durability"]):
        await websocket.send_json({"type": "toast", "text": "✨ Bereits voll repariert."})
        return
    # Hammer-Check
    tool = await db.pool().fetchrow(
        "SELECT id FROM items WHERE owner = $1 AND equipped_slot = 'tool' "
        "AND kind = 'hammer' LIMIT 1", player_id,
    )
    if not tool:
        await websocket.send_json({"type": "toast", "text": "🔨 Hammer ausrüsten."})
        return
    # Material verfügbar? consume_one() handelt Stack-Logik selbst.
    needed_mat = s["material"]   # 'stone', 'wood', oder 'straw'
    consumed = await items.consume_one(player_id, needed_mat)
    if not consumed:
        await websocket.send_json({
            "type": "toast",
            "text": f"📦 Du brauchst 1× {needed_mat} zum Reparieren.",
        })
        return
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


async def handle_upgrade_structure(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    structures = ctx.structures
    items = ctx.items
    # Welle 25: Wand-Material aufwerten (straw→wood→stone).
    # Voraussetzungen: eigene Struktur (can_modify), Combat-fähig,
    # Hammer ausgerüstet, voll HP (kein Upgrade beschädigter Wände),
    # 2× neues Material im Inventar.
    x, y = int(data.get("x", -1)), int(data.get("y", -1))
    s = structures.object_at(x, y) or structures.floor_at(x, y)
    if s is None:
        return
    from structures import is_combat_structure as _is_cs
    if not _is_cs(s["type"]):
        return
    if not structures.can_modify(player_id, s):
        await websocket.send_json({
            "type": "toast", "text": "🔒 Du bist nicht der Eigentümer.",
        })
        return
    player = manager.get_players().get(player_id)
    if player is None:
        return
    if combat.chebyshev(player["x"], player["y"], x, y) > 1:
        await websocket.send_json({"type": "toast", "text": "🤚 Zu weit weg."})
        return
    new_mat = structures.next_material(s["material"])
    if new_mat is None:
        await websocket.send_json({
            "type": "toast",
            "text": f"⛰️ Bereits höchstes Material ({s['material']}).",
        })
        return
    if s["durability"] < s.get("max_durability", s["durability"]):
        await websocket.send_json({
            "type": "toast",
            "text": "🔨 Erst reparieren — beschädigte Wände können nicht aufgewertet werden.",
        })
        return
    # Hammer-Check
    tool = await db.pool().fetchrow(
        "SELECT id FROM items WHERE owner = $1 AND equipped_slot = 'tool' "
        "AND kind = 'hammer' LIMIT 1", player_id,
    )
    if not tool:
        await websocket.send_json({"type": "toast", "text": "🔨 Hammer ausrüsten."})
        return
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
                logging.exception("Upgrade-Rollback fehlgeschlagen")
        await websocket.send_json({
            "type": "toast",
            "text": f"📦 Du brauchst {cost}× {new_mat} zum Aufwerten.",
        })
        return
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


async def handle_use_structure(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    npcs = ctx.npcs
    items = ctx.items
    # Klick auf Bed/Well/Anvil etc. — heilt oder anderes je nach Typ
    x, y = int(data.get("x", -1)), int(data.get("y", -1))
    s = structures.at(x, y)
    if s is None:
        return
    player = manager.get_players().get(player_id)
    if player is None:
        return
    # Nur wenn nahe genug
    if combat.chebyshev(player["x"], player["y"], x, y) > 1:
        return
    if s["type"] == "chest":
        contents = await items.get_chest_contents(s["id"])
        await websocket.send_json({
            "type":     "chest_open",
            "chest_id": s["id"],
            "items":    contents,
        })
        return
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
        return
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
            return
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
        from collections import Counter as _Cnt
        drop_counts = _Cnt(drops)
        # Pro Item-Art EINE aggregierte inventory_add senden, mit `added` =
        # in DIESEM Schlag gewonnene Menge. `item.quantity` ist die Stack-
        # GESAMTmenge — die als Float „+102 Stein" anzuzeigen ist irreführend;
        # die Float nutzt daher `added` (z. B. „+2 Stein", passend zum Toast).
        for kind, cnt in drop_counts.items():
            created = None
            for _ in range(cnt):
                c = await items.create_for_player(kind, player_id)
                if c is not None:
                    created = c
            if created is not None:
                await websocket.send_json({
                    "type": "inventory_add", "item": created, "added": cnt,
                })
        # Quest-Hook: gesammelte Drops
        if drops:
            try:
                for kind, cnt in drop_counts.items():
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
        return
    if s["type"] == "stairs_down":
        # Welle 32: Multi-Floor-Dungeons. Dungeon-Eingang ist per
        # entrance_x/y mit der stairs_down-Struktur verknüpft.
        cur_world = await dungeon_instance.get_player_world(player_id)
        if cur_world != "overworld":
            await websocket.send_json({
                "type": "toast",
                "text": "Du bist bereits in einem Dungeon.",
            })
            return
        cur_player = manager.get_players().get(player_id)
        if cur_player is None:
            return
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
            return
        dungeon = await dungeon_instance.get_dungeon(dungeon_id)
        manager.update_player(player_id,
                              floor["spawn"][0], floor["spawn"][1])
        # Mobs spawnen falls erste Floor-Begegnung
        try: await dungeon_instance.populate_floor_mobs(
            dungeon_id, 0, npcs, manager)
        except Exception: logging.exception("floor population failed")
        _extra = await dungeon_floor_payload(npcs, dungeon["id"], 0)
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
        return
    if s["type"] == "farm_plot":
        existing = await db.pool().fetchrow(
            "SELECT plant_kind FROM plantings WHERE structure_id = $1", s["id"]
        )
        if existing:
            await websocket.send_json({
                "type": "toast", "text": "🌿 Hier wächst schon etwas",
            })
            return
        if not await items.consume_one(player_id, "herb"):
            await websocket.send_json({
                "type": "toast", "text": "Du brauchst ein Kraut zum Pflanzen",
            })
            return
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
        return
    if s["type"] in ("workbench", "furnace", "anvil"):
        await websocket.send_json({
            "type":     "crafting_open",
            "station":  s["type"],
            "recipes":  recipes.get_recipes(s["type"]),
        })
        return
    # Welle 51 — Settlement-Schild anklicken → Inspect-Modal
    if s["type"].startswith("sign_"):
        slug = s["type"][len("sign_"):]
        await websocket.send_json({
            "type": "sign_inspect",
            "slug": slug,
        })
        return
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
            return
        _heal_cooldowns[key] = now
        await heal_player_svc(manager, player_id, heal_amount)
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
                    logging.exception("Tainted-well poison apply failed")
                    await damage_player_svc(manager, player_id, 12)
                await websocket.send_json({
                    "type": "toast",
                    "text": "☠️ Das Wasser ist vergiftet! Du bist verseucht!",
                })
                return
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


async def handle_fill_container(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    items = ctx.items
    # Füllt ein Container-Item (Eimer/Wasserschlauch/Gießkanne) am
    # angegebenen Tile-Click (entweder ein Brunnen oder Wasser-Tile).
    item_id = int(data.get("item_id", 0))
    x, y = int(data.get("x", 0)), int(data.get("y", 0))
    player = manager.get_players().get(player_id)
    if player is None:
        return
    if combat.chebyshev(player["x"], player["y"], x, y) > 1:
        await websocket.send_json({"type": "toast", "text": "Zu weit weg."})
        return
    # Wasserquelle: Brunnen ODER WATER-Tile
    obj_here = structures.object_at(x, y)
    is_well = obj_here is not None and obj_here["type"] == "well"
    from world import WATER as _W
    tile_id = await world.tile_at(x, y)
    is_water_tile = (tile_id == _W)
    if not (is_well or is_water_tile):
        await websocket.send_json({"type": "toast", "text": "Keine Wasserquelle."})
        return
    # Item muss Container sein und dem Spieler gehören
    cur_item = await db.pool().fetchrow(
        "SELECT kind FROM items WHERE id = $1 AND owner = $2",
        item_id, player_id,
    )
    if cur_item is None or not items.is_water_container(cur_item["kind"]):
        await websocket.send_json({"type": "toast", "text": "Kein Behälter."})
        return
    cap = items.container_capacity(cur_item["kind"])
    filled = await items.set_charges(item_id, player_id, cap)
    if filled:
        await websocket.send_json({"type": "inventory_update", "item": filled})
        await websocket.send_json({
            "type": "toast",
            "text": f"💧 {cur_item['kind']} aufgefüllt ({cap} Ladungen).",
        })


async def handle_water_plant(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    structures = ctx.structures
    items = ctx.items
    # Bewässert einen farm_plot in Reichweite (verbraucht 1 Container-Ladung)
    x, y = int(data.get("x", 0)), int(data.get("y", 0))
    container_id = int(data.get("item_id", 0))
    player = manager.get_players().get(player_id)
    if player is None:
        return
    if combat.chebyshev(player["x"], player["y"], x, y) > 1:
        await websocket.send_json({"type": "toast", "text": "Zu weit weg."})
        return
    target = structures.at(x, y)
    if target is None or target["type"] != "farm_plot":
        await websocket.send_json({"type": "toast", "text": "Hier ist kein Acker."})
        return
    # Container prüfen
    cur_item = await db.pool().fetchrow(
        "SELECT kind, charges FROM items WHERE id = $1 AND owner = $2",
        container_id, player_id,
    )
    if cur_item is None or not items.is_water_container(cur_item["kind"]):
        await websocket.send_json({"type": "toast", "text": "Kein Wasserbehälter ausgewählt."})
        return
    if (cur_item["charges"] or 0) <= 0:
        await websocket.send_json({"type": "toast", "text": "Behälter ist leer."})
        return
    # Bewässern: pflanze last_watered_at = NOW
    upd = await db.pool().fetchrow(
        "UPDATE plantings SET last_watered_at = NOW() "
        "WHERE structure_id = $1 "
        "RETURNING structure_id, plant_kind",
        target["id"],
    )
    if upd is None:
        await websocket.send_json({"type": "toast", "text": "Acker ist leer (kein Samen)."})
        return
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


async def handle_drink_container(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
    # Trinkt 1 Ladung aus einem vollen Container im Inventar.
    item_id = int(data.get("item_id", 0))
    cur_item = await db.pool().fetchrow(
        "SELECT kind, charges FROM items WHERE id = $1 AND owner = $2",
        item_id, player_id,
    )
    if cur_item is None or not items.is_water_container(cur_item["kind"]):
        return
    if (cur_item["charges"] or 0) <= 0:
        await websocket.send_json({"type": "toast", "text": "Behälter ist leer."})
        return
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


async def handle_drink_water_tile(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    # Trinkt aus angrenzendem Wasser-Tile (oder direkt drauf)
    x, y = int(data.get("x", 0)), int(data.get("y", 0))
    player = manager.get_players().get(player_id)
    if player is None:
        return
    if combat.chebyshev(player["x"], player["y"], x, y) > 1:
        return
    # WATER = tile id 0 (siehe world.py)
    tile_id = await world.tile_at(x, y)
    from world import WATER as _W
    if tile_id != _W:
        await websocket.send_json({
            "type": "toast", "text": "Hier ist kein Wasser.",
        })
        return
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


register("dungeon_chest", handle_dungeon_chest)
register("place_structure", handle_place_structure)
register("toggle_door", handle_toggle_door)
register("remove_structure", handle_remove_structure)
register("attack_structure", handle_attack_structure)
register("repair_structure", handle_repair_structure)
register("upgrade_structure", handle_upgrade_structure)
register("use_structure", handle_use_structure)
register("fill_container", handle_fill_container)
register("water_plant", handle_water_plant)
register("drink_container", handle_drink_container)
register("drink_water_tile", handle_drink_water_tile)
