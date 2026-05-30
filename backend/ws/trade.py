"""Trade-Handler (Phase B7): open_trade, buy_item, sell_item.

Behält 1:1 das Verhalten aus dem Legacy-Block in main.py:
- open_trade: Merchant-Check, Distanz (chebyshev <= 2), Offerings.
- buy_item: Discount via Social/Talents, Currency.spend (Refund bei Fehler),
  Inventar-Refresh, Wallet-Push + trade_coins.
- sell_item: Sell-Bonus via Talents, Currency.add, Inventar-Refresh.
"""
from __future__ import annotations

import combat
import currency
import db
import skills
import talents
import trade as trade_mod

from .context import WsContext
from .dispatcher import register


async def handle_open_trade(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    npcs = ctx.npcs

    npc_id = int(data.get("npc_id", 0))
    npc = npcs.get(npc_id)
    if npc is None or npc["kind"] != "merchant":
        return
    player = manager.get_players().get(player_id)
    if player is None or combat.chebyshev(player["x"], player["y"], npc["x"], npc["y"]) > 2:
        return
    offerings_kinds = trade_mod.generate_offerings(8)
    from items import ITEM_KINDS
    offerings = [
        {
            "kind":   k,
            "name":   ITEM_KINDS[k]["name"],
            "price":  trade_mod.buy_price(k),
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


async def handle_buy_item(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    items = ctx.items

    kind = data.get("kind", "")
    from items import ITEM_KINDS
    if kind not in ITEM_KINDS:
        return
    price = trade_mod.buy_price(kind)
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
        return
    # Social-XP für Trade
    sxp = await skills.gain_xp(player_id, "social", 3)
    if sxp:
        await websocket.send_json({"type": "skill_xp", **sxp})
    created = await items.create_for_player(kind, player_id)
    if created is None:
        await currency.add(player_id, price)  # Refund bei Fehlschlag
        return
    inv = await items.get_inventory(player_id)
    await websocket.send_json({"type": "inventory_full_refresh", "inventory": inv})
    await currency.push_wallet(manager, player_id)
    await websocket.send_json({
        "type": "trade_coins", "coins": await currency.balance(player_id),
    })


async def handle_sell_item(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    items = ctx.items

    item_id = int(data.get("item_id", 0))
    row = await db.pool().fetchrow(
        "SELECT kind FROM items WHERE id = $1 AND owner = $2",
        item_id, player_id,
    )
    if row is None:
        return
    kind = row["kind"]
    price = trade_mod.sell_price(kind)
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
    await currency.push_wallet(manager, player_id)
    await websocket.send_json({
        "type": "trade_coins", "coins": await currency.balance(player_id),
    })


register("open_trade", handle_open_trade)
register("buy_item", handle_buy_item)
register("sell_item", handle_sell_item)
