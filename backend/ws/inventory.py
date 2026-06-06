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
import random

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

log = logging.getLogger("liege.ws.inventory")


# ─────────────────────────────────────────────────────────────────────────────
# Welle 35 — Monster-Drop-Item Use-Effekte (146 Slugs).
# Die meisten Items haben Effekte via combat.USE_EFFECTS (Tränke), needs.FOOD_
# RESTORE (Hunger) oder werden gar nicht "ge-used". Lore-/Quest-/Trophy-Items
# sollen einen Flavor-Toast geben OHNE verbraucht zu werden — diese werden
# unten am Anfang von handle_use_item per Early-Return abgefangen.
# Materials/Ammo zeigen einen Hinweis-Toast und werden ebenfalls nicht
# verbraucht (Stack-Schutz vor versehentlichem Doppelklick).
# Foods aus monster_drop_items haben optionale Seiten-Effekte (z.B.
# Faules Fleisch → 30% poisoned).
# ─────────────────────────────────────────────────────────────────────────────

# Lore-Items: Toast-Text, KEIN Verbrauch.
_LORE_TOASTS: dict[str, str] = {
    "lore_fragment":       "📜 Du studierst das Fragment — eine alte Schrift offenbart sich kurz.",
    "unique_lore_item":    "✨ Ein einzigartiges Lore-Stück. Sicherer Aufbewahrungsort.",
    "white_pilgrim_token": "🪨 Der Stein des Pilgers fühlt sich warm an.",
    "dark_grimoire":       "📕 Düstere Magie. Lesen wäre gefährlich...",
    "ancient_treasure":    "💰 Antiker Schatz. Im Inventar lassen oder verkaufen.",
    "star_mote_shard":     "⭐ Ein Splitter eines Sterns. Ungewöhnlich warm.",
    "forehead_eye":        "👁 Du fühlst, dass jemand zurückschaut...",
    "old_god_shard":       "🌀 Etwas Uraltes pulsiert in deiner Hand.",
}

# Quest-Items: Toast-Text, KEIN Verbrauch (gehören NPCs).
_QUEST_TOASTS: dict[str, str] = {
    "living_toad":          "🐸 Quest-Item: Bring die Kröte zum richtigen NPC.",
    "drowner_lock_of_hair": "💧 Quest-Item: Bring die Locke zum Auftraggeber.",
    "messenger_capsule":    "✉️ Quest-Item: Liefere die Kapsel an den Empfänger.",
    "well_idol":            "⛲ Quest-Item: Bring das Idol zum Brunnen-Hüter.",
    "plague_phial":         "☠ Quest-Item: Vorsichtig zum Alchemisten bringen.",
    "stolen_pouch":         "👛 Quest-Item: Gib den Beutel dem Bestohlenen zurück.",
    "crude_map_fragment":   "🗺 Karten-Fragment. Markiert vielleicht einen Schatz — schau am Wegrand nach.",
}

# Trophy-Items (Bounty): Flavor-Toast, KEIN Verbrauch (bringt sie zum Auftraggeber).
_TROPHY_TOASTS: dict[str, str] = {
    "goblin_ear":      "🏆 Beweis deines Sieges über einen Goblin.",
    "orgrim_skull":    "🏆 Beweis deines Sieges über Orgrim.",
    "captain_banner":  "🏆 Erbeutetes Banner — Beweis deines Sieges über den Hauptmann.",
    "boss_trophy":     "🏆 Boss-Trophäe — Beweis deines Sieges über einen mächtigen Gegner.",
    "warchief_crown":  "👑 Krone des Kriegshäuptlings — schwer und blutig.",
    "witchking_crown": "👑 Krone des Hexenkönigs — sie flüstert kalt.",
    "undying_crown":   "👑 Krone der Untoten — sie ist niemals erkaltet.",
    "pharaoh_mask":    "🎭 Pharaonen-Maske — uralter Glanz der Wüste.",
    # Boss-Hearts / Eggs — wertvolle Crafting/Trade-Trophäen.
    "dragon_heart":    "🔥 Drachenherz — pulsierende Crafting-Reagenz, sehr wertvoll.",
    "emerald_egg":     "🥚 Smaragd-Ei — selten und schimmernd. Verkaufen oder ausbrüten?",
    "magma_heart":     "🌋 Magma-Herz — glühende Energie für Hoch-Tier-Crafting.",
    "avalanche_core":  "❄️ Lawinen-Kern — eisige Kraft, gefährlich zu lagern.",
    "ossuary_core":    "💀 Ossuar-Kern — verdichtete Knochenmasse, Nekromantie-Reagenz.",
}

# Material-Items: einheitlicher Toast, KEIN Verbrauch.
_MATERIAL_HINT = "🛠 Material — verwende es im Crafting."

# Food-Side-Effekte (zusätzlich zur Hunger-Restoration via FOOD_RESTORE).
# Aktiviert sich AFTER consume und Standard-Hunger-Branch.
# Schema: { "poison_chance": float, "poison_magnitude": int, "poison_duration": int }
_FOOD_SIDE_EFFECTS: dict[str, dict] = {
    # Faules Fleisch: 30% Chance auf Vergiftung (mag 3, 30s)
    "rotten_flesh": {"poison_chance": 0.30, "poison_magnitude": 3, "poison_duration": 30},
    # strider_meat: speed-Buff geplant, aber kein 'swift'-Effekt vorhanden →
    # siehe docu/REFACTOR_NOTES.md ("Welle 35 strider_meat speed-buff").
}

# Hunger-Werte für Monster-Drop-Foods (nicht in needs.FOOD_RESTORE definiert,
# da die ursprüngliche FOOD_RESTORE-Map konservativ klein gehalten wurde).
_MONSTER_FOOD_HUNGER: dict[str, int] = {
    "rotten_flesh":  20,
    "dark_meat":     30,
    "pork_loin":     40,
    "strider_meat":  35,
    "tentacle_meat": 25,
    "herb_bundle":    5,   # primär Heilkraut, sekundär minimale Sättigung
}

# herb_bundle: zusätzlich +5 HP (Heilkraut-Charakter)
_MONSTER_FOOD_HEAL: dict[str, int] = {
    "herb_bundle": 5,
}

# Witch-Brew Roll-Tabelle: (cum_threshold, effect_kind, label).
_WITCH_BREW_TABLE: list[tuple[float, str, str]] = [
    (0.25, "health",   "💚 Heilung (+30 HP)"),
    (0.50, "mana",     "💙 Mana (+20)"),
    (0.70, "poison",   "☠ Selbst-Vergiftung (DoT 30s)"),
    (0.85, "speed",    "💨 Geschwindigkeit (60s)"),
    (1.01, "strength", "💪 Stärke (60s)"),
]


def _no_consume_toast(kind: str) -> str | None:
    """Returns Toast-Text wenn das Item ohne Verbrauch ge-used wird, sonst None."""
    if kind in _LORE_TOASTS:
        return _LORE_TOASTS[kind]
    if kind in _QUEST_TOASTS:
        return _QUEST_TOASTS[kind]
    if kind in _TROPHY_TOASTS:
        return _TROPHY_TOASTS[kind]
    return None


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
        "SELECT kind, category FROM items WHERE id = $1 AND owner = $2", item_id, player_id
    )
    kind = cur["kind"] if cur else None
    category = cur["category"] if cur else None

    # Welle 53 — Magic-Items (Zauberbuch/Schriftrolle/Rune) → Zauber LERNEN.
    # Das Frontend routet spell_book wegen eines Catalog-Key-Mismatch auf
    # `use_item` statt `learn_spell`; consume() lehnt magic ab → vorher No-Op.
    # Wir delegieren hier an den (funktionierenden) Lern-Pfad.
    if category == "magic":
        from .character import handle_learn_spell
        await handle_learn_spell(ctx, data)
        return

    # Welle 35 — Lore / Quest / Trophy: Flavor-Toast, KEIN Verbrauch.
    no_consume_text = _no_consume_toast(kind or "")
    if no_consume_text is not None:
        await websocket.send_json({"type": "toast", "text": no_consume_text})
        return

    # Welle 35 — Material/Ammo: Hinweis-Toast, KEIN Verbrauch (Stack-Schutz).
    # Ammo wird automatisch beim Schießen verbraucht; Materials sind Crafting-Input.
    if category in ("material", "ammo"):
        await websocket.send_json({"type": "toast", "text": _MATERIAL_HINT})
        return

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

    # ─────────────────────────────────────────────────────────────────────────
    # Welle 35 — Monster-Drop-Food: zusätzliche Hunger-Restoration + Side-FX.
    # Die Slugs sind NICHT in needs.FOOD_RESTORE → eigene Map _MONSTER_FOOD_*.
    # Wird zusätzlich zum is_food()-Branch oben gefeuert (der für diese Slugs
    # nichts tut), garantiert also keine Doppel-Sättigung.
    # ─────────────────────────────────────────────────────────────────────────
    if kind in _MONSTER_FOOD_HUNGER:
        cooking_lvl = await skills.get_skill_level(player_id, "cooking")
        base_val = _MONSTER_FOOD_HUNGER[kind]
        eff_val = int(base_val * skills.cooking_quality_bonus(cooking_lvl))
        new_state = await needs.restore_hunger(player_id, eff_val)
        if new_state is not None:
            await websocket.send_json({"type": "player_needs", **new_state})
        # Optionaler Heil-Anteil (z.B. herb_bundle = Heilkraut)
        heal_amt = _MONSTER_FOOD_HEAL.get(kind, 0)
        if heal_amt > 0:
            await heal_player_svc(manager, player_id, heal_amt)
        # Optionaler Krankheits-Roll (z.B. faules Fleisch)
        side = _FOOD_SIDE_EFFECTS.get(kind)
        if side and random.random() < side.get("poison_chance", 0):
            try:
                await status_effects.apply(
                    "player", player_id, "poisoned",
                    side["poison_magnitude"], side["poison_duration"],
                )
                effs = await status_effects.list_for_target("player", player_id)
                await websocket.send_json({"type": "status_effects", "effects": effs})
                await websocket.send_json({
                    "type": "toast",
                    "text": "🤢 Du wirst krank — das Fleisch war verdorben!",
                })
            except Exception:
                log.debug("poison-side-effect für %s fehlgeschlagen", kind, exc_info=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Welle 35 — tech_print: gibt Research-Pool-Punkte (analog research_scroll).
    # Item ist category=lore, NICHT verbraucht durch consume() → hier müssen
    # wir es manuell löschen (Lore early-return haben wir oben übersprungen
    # weil tech_print bewusst NICHT in _LORE_TOASTS ist).
    # ─────────────────────────────────────────────────────────────────────────
    if kind == "tech_print":
        # Manuell verbrauchen — consume() filtert auf consumable/food.
        deleted = await db.pool().fetchrow(
            "DELETE FROM items WHERE id = $1 AND owner = $2 RETURNING id",
            item_id, player_id,
        )
        if deleted is not None:
            new_pool = await research.award_points(player_id, 10, "item:tech_print")
            await websocket.send_json({
                "type": "inventory_remove", "item_id": item_id, "consumed": True,
            })
            await websocket.send_json({
                "type": "research_pool_update", "pool": new_pool,
                "gained": 10, "reason": "🔧 Tech-Druck",
            })
            await websocket.send_json({
                "type": "toast",
                "text": "🔧 Tech-Druck studiert (+10 Forschung).",
            })

    # ─────────────────────────────────────────────────────────────────────────
    # Welle 35 — witch_brew: Random-Effekt-Roll (5 mögliche Ausgänge).
    # ─────────────────────────────────────────────────────────────────────────
    if kind == "witch_brew":
        roll = random.random()
        chosen = "strength"
        label = ""
        for threshold, eff_kind, eff_label in _WITCH_BREW_TABLE:
            if roll < threshold:
                chosen = eff_kind
                label = eff_label
                break
        try:
            if chosen == "health":
                await heal_player_svc(manager, player_id, 30)
            elif chosen == "mana":
                await restore_mana_svc(manager, player_id, 20)
            elif chosen == "poison":
                # DOT auf SICH SELBST
                await status_effects.apply("player", player_id, "poisoned", 4, 30)
                effs = await status_effects.list_for_target("player", player_id)
                await websocket.send_json({"type": "status_effects", "effects": effs})
            elif chosen == "speed":
                # speed-Buff via shielded-Fallback? Es gibt keinen 'swift'-Effekt.
                # Wir bedienen uns 'blessed' (HoT) als generischer Buff —
                # langfristig sollte ein dedizierter speed-Effekt rein.
                # Siehe docu/REFACTOR_NOTES.md ("Welle 35 witch_brew speed").
                await status_effects.apply("player", player_id, "blessed", 2, 60)
                effs = await status_effects.list_for_target("player", player_id)
                await websocket.send_json({"type": "status_effects", "effects": effs})
            elif chosen == "strength":
                # Analog: kein dedizierter strength-Effekt → blessed als Fallback.
                await status_effects.apply("player", player_id, "blessed", 3, 60)
                effs = await status_effects.list_for_target("player", player_id)
                await websocket.send_json({"type": "status_effects", "effects": effs})
        except Exception:
            log.debug("witch_brew Effekt-Anwendung fehlgeschlagen", exc_info=True)
        await websocket.send_json({
            "type": "toast",
            "text": f"🍶 Hexenbräu: {label}",
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
        "SELECT kind FROM items WHERE id = $1 AND owner = $2",
        item_id, f"chest:{chest_id}",
    )
    if _krow and currency.is_currency(_krow["kind"]):
        # Welle 53 — Anti-Dupe (TOCTOU): vorher SELECT→add→DELETE, wodurch zwei
        # parallele Transfers beide gutschreiben konnten. Jetzt atomar löschen
        # mit RETURNING — nur der Frame, der die Row WIRKLICH entfernt, schreibt gut.
        deleted = await db.pool().fetchrow(
            "DELETE FROM items WHERE id = $1 AND owner = $2 RETURNING kind, quantity",
            item_id, f"chest:{chest_id}",
        )
        if deleted is None:
            return   # bereits von einem parallelen Transfer geholt
        _gain = currency.coin_to_copper(deleted["kind"], deleted["quantity"] or 1)
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
