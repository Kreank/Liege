"""Crafting-Handler (Phase B10): open_hand_crafting, craft.

Behält 1:1 das Verhalten aus dem Legacy-Block in main.py:
- open_hand_crafting: sendet `crafting_open` mit station="hand".
- craft: Research-Gate, Material-Check, Verbrauch, Quality-Roll,
  Talent-Boni (crafting_quality_bonus, crafting_min_quality,
  crafting_legendary_chance), Affix-Roll bei fine+, LLM-Naming bei
  legendary, Inventar-Refresh, Crafting/Cooking-XP.
"""
from __future__ import annotations

import logging

import affixes
import item_namer
import quality
import recipes
import research
import skills
import talents
from items import ITEM_KINDS

from .context import WsContext
from .dispatcher import register


async def handle_open_hand_crafting(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    # Inventar-getriebenes Hand-Crafting: keine Werkbank nötig.
    await websocket.send_json({
        "type":    "crafting_open",
        "station": "hand",
        "recipes": recipes.get_recipes("hand"),
    })


async def handle_craft(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items

    station = str(data.get("station", ""))
    recipe_id = str(data.get("recipe_id", ""))
    recipe = recipes.find_recipe(station, recipe_id)
    if recipe is None:
        return
    # Welle 22: Research-Gate
    req = recipe.get("requires")
    if req and not await research.is_node_done(player_id, req):
        node_name = research.RESEARCH_NODES.get(req, {}).get("name", req)
        await websocket.send_json({
            "type": "toast",
            "text": f"🔒 Erst forschen: {node_name}",
        })
        return
    counts = await items.count_owned_by_kind(player_id)
    if not all(counts.get(k, 0) >= n for k, n in recipe["inputs"]):
        await websocket.send_json({
            "type": "toast", "text": "Nicht genug Material",
        })
        return
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
                base_name = ITEM_KINDS.get(recipe["output"], {}).get("name", recipe["output"])
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


register("open_hand_crafting", handle_open_hand_crafting)
register("craft", handle_craft)
