"""Inventory-Handler (Phase B12): split_stack, merge_stacks, equip_item,
unequip_item, use_item, pick_item, drop_item, chest_transfer_to,
chest_transfer_from.

Behält 1:1 das Verhalten aus den Legacy-Blocks in main.py:
- split_stack / merge_stacks: stack-management → inventory_update/_add/_full_refresh.
- equip_item / unequip_item: items.equip/unequip + attrs_update.
- use_item: groß — food/heal/spell-scroll/lore-item Sub-Logik inkl. talent
  bonuses, hunger/thirst/needs, research-items, dungeon-key spawn.
- pick_item / drop_item: ground-pickup mit Range-Check + Loot-Roll-Lock.
- chest_transfer_to/from: Inventar ↔ Chest-Owner-Switch, mit Coin-Special-Case.
"""
from __future__ import annotations

import logging

import body_parts
import combat
import currency
import db
import dungeon_instance
import dungeon_tiers
import loot_rolls
import needs
import research
import skills
import status_effects
import talents

from services.player_state import heal_player as heal_player_svc, restore_mana as restore_mana_svc
from services.player_equipment import has_tool_for_skill  # noqa: F401 — kein direkter Use, future-proofing

from .context import WsContext
from .dispatcher import register


async def handle_split_stack(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
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


async def handle_merge_stacks(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
    kind = str(data.get("kind", ""))
    quality_str = str(data.get("quality", "normal"))
    if not kind:
        return
    result = await items.merge_stacks(player_id, kind, quality_str)
    if result is not None:
        # Full-refresh damit Frontend die gelöschten Rows + neue Quantities sieht
        new_inv = await items.get_inventory(player_id)
        await websocket.send_json({
            "type": "inventory_full_refresh",
            "inventory": new_inv,
        })


async def handle_equip_item(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
    item_id = int(data.get("item_id", 0))
    to_slot = data.get("to_slot")  # Welle 23 — Dual-Wield optional
    item = await items.equip(item_id, player_id, to_slot=to_slot)
    if item is not None:
        await websocket.send_json({"type": "inventory_update", "item": item})
        import attributes
        await attributes.send_attrs_update(items, websocket, player_id)
    else:
        await websocket.send_json({"type": "toast",
            "text": "Off-Hand: 2H-Waffe kann nicht dual-equipped werden."})


async def handle_unequip_item(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
    item_id = int(data.get("item_id", 0))
    item = await items.unequip(item_id, player_id)
    if item is not None:
        await websocket.send_json({"type": "inventory_update", "item": item})
        import attributes
        await attributes.send_attrs_update(items, websocket, player_id)


async def handle_use_item(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    items = ctx.items
    item_id = int(data.get("item_id", 0))
    # Item vor dem Löschen lesen für Effekt-Lookup
    cur = await db.pool().fetchrow(
        "SELECT kind FROM items WHERE id = $1 AND owner = $2", item_id, player_id
    )
    kind = cur["kind"] if cur else None
    consumed = await items.consume(item_id, player_id)
    if consumed is None:
        return
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
            await heal_player_svc(manager, player_id, int(effect["hp"] * heal_mult))
        if "mana" in effect:
            await restore_mana_svc(manager, player_id, effect["mana"])
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
            await heal_player_svc(manager, player_id, int(talent_eff_c["cooking_heal_bonus"]))
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


async def handle_pick_item(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    items = ctx.items
    # Expliziter Pickup: Spieler klickt auf Item am Boden in Reichweite (≤1 Tile).
    item_id = int(data.get("item_id", 0))
    player = manager.get_players().get(player_id)
    if player is None:
        return
    ground = await db.pool().fetchrow(
        "SELECT x, y FROM items WHERE id = $1 AND owner IS NULL",
        item_id,
    )
    if ground is None:
        return  # schon weg
    if combat.chebyshev(player["x"], player["y"], int(ground["x"]), int(ground["y"])) > 1:
        return  # zu weit weg (Sanity-Check — Frontend prüft auch)
    # Loot-Roll-Lock: Item ist gerade in einem Need/Greed-Roll →
    # nur der ausgelobte Gewinner darf aufheben.
    if loot_rolls.is_locked(item_id):
        winner = loot_rolls.allowed_picker(item_id)
        if winner is None:
            await websocket.send_json({"type": "toast",
                                        "text": "⏳ Loot-Roll läuft noch"})
            return
        if winner != player_id:
            await websocket.send_json({"type": "toast",
                                        "text": f"🔒 Für {winner} reserviert"})
            return
    picked = await items.pickup(item_id, player_id)
    if picked is None:
        return
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


async def handle_drop_item(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    items = ctx.items
    item_id = int(data.get("item_id", 0))
    player = manager.get_players().get(player_id)
    if player is None:
        return
    dropped = await items.drop(item_id, player_id, player["x"], player["y"])
    if dropped is None:
        return
    await websocket.send_json({
        "type": "inventory_remove",
        "item_id": dropped["id"],
    })
    await manager.broadcast({
        "type": "item_spawned",
        "item": dropped,
    })


async def handle_chest_transfer_to(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
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


async def handle_chest_transfer_from(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    items = ctx.items
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
        await currency.push_wallet(manager, player_id, gained=_gain)
        return
    transferred = await items.transfer_from_chest(item_id, chest_id, player_id)
    if transferred:
        await websocket.send_json({
            "type": "chest_remove", "chest_id": chest_id, "item_id": item_id,
        })
        await websocket.send_json({
            "type": "inventory_add", "item": transferred,
        })


register("split_stack", handle_split_stack)
register("merge_stacks", handle_merge_stacks)
register("equip_item", handle_equip_item)
register("unequip_item", handle_unequip_item)
register("use_item", handle_use_item)
register("pick_item", handle_pick_item)
register("drop_item", handle_drop_item)
register("chest_transfer_to", handle_chest_transfer_to)
register("chest_transfer_from", handle_chest_transfer_from)
