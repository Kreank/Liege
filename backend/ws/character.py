"""Character/Progression-Handler (Phase B11): allocate_attr, learn_talent,
learn_spell, list_attributes, character_check_name,
character_create, list_talents, wake.

Behält 1:1 das Verhalten aus den Legacy-Blocks in main.py:
- wake: Bett-Schlaf brechen (needs.set_resting False).
- allocate_attr: player_stats.allocate_point + attrs_update.
- learn_talent: talents.learn_talent → talent_learned + Tree-Refresh.
- learn_spell: Item-Verbrauch + INSERT learned_spells + skill_xp magic.
  (Gecastet wird ausschließlich über cast_spell → spell_caster, siehe ws/combat.py.)
- list_attributes: attributes.player_combat_sheet → attributes_update (flach: attributes+stats).
- character_check_name: display_name-Validierung + DB-Check.
- character_create: Preset+Allocation+display_name persistieren.
- list_talents: talents.tree_for_ui + talents_update.
"""
from __future__ import annotations

import logging

import attributes
import combat
import db
import needs
import skills
import spells
import talents

from .context import WsContext
from .dispatcher import register


async def handle_wake(ctx: WsContext, data: dict) -> None:
    # Spieler wacht aktiv aus dem Bett-Schlaf auf (ohne Bewegung).
    # Wie in movement.py: bei tatsächlichem Resting->False muss ein
    # 'rest_end' an den Client, sonst bleibt dessen `is_resting`-Flag
    # hängen (rest_start ohne Gegen-Frame).
    if needs.is_resting(ctx.player_id):
        needs.set_resting(ctx.player_id, False)
        await ctx.websocket.send_json({"type": "rest_end", "reason": "woke"})


async def handle_allocate_attr(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
    attr = (data.get("attr") or "").strip()
    n = int(data.get("n", 1) or 1)
    if attr and -50 <= n <= 50:
        import player_stats as _ps
        result = await _ps.allocate_point(player_id, attr, n)
        if result and "ok" in result:
            await attributes.send_attrs_update(items, websocket, player_id)
        elif result and "error" in result:
            await websocket.send_json({
                "type": "toast",
                "text": f"Allokation: {result['error']}",
            })


async def handle_learn_talent(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    talent_id = data.get("talent_id", "")
    found = talents.find_talent(talent_id)
    if found is None:
        await websocket.send_json({"type": "toast", "text": "Unbekanntes Talent"})
        return
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


async def handle_learn_spell(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
    # Spieler lernt aus einem Spell-Item (verbraucht 1 Stück)
    item_id = int(data.get("item_id", 0))
    row = await db.pool().fetchrow(
        "SELECT kind, category FROM items WHERE id = $1 AND owner = $2",
        item_id, player_id,
    )
    if not row or row["category"] != "magic":
        await websocket.send_json({"type": "toast", "text": "Das ist kein Zauber-Item"})
        return
    spell_kind = row["kind"]
    # Schon gelernt?
    exists = await db.pool().fetchrow(
        "SELECT 1 FROM learned_spells WHERE player_name = $1 AND spell_kind = $2",
        player_id, spell_kind,
    )
    if exists:
        await websocket.send_json({"type": "toast",
            "text": "Diesen Zauber kennst du bereits."})
        return
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
        "learned": await spells.list_learned_for_player(player_id),
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


async def handle_list_attributes(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    items = ctx.items
    # FE-konforme flache Form (attributes + stats), identisch zu init/attrs_update.
    cs = await attributes.player_combat_sheet(items, player_id)
    await websocket.send_json({
        "type": "attributes_update",
        "attributes": cs["attributes"],
        "stats": cs["stats"],
        "max_hp": cs["max_hp"],
        "max_mana": cs["max_mana"],
        "hp": cs["hp"],
        "mana": cs["mana"],
    })


async def handle_character_check_name(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    # Welle 23: Live-Check ob ein gewünschter display_name frei ist.
    want = str(data.get("display_name", "")).strip()[:24]
    if not want or len(want) < 3:
        await websocket.send_json({"type": "character_name_check",
            "name": want, "available": False, "reason": "zu kurz (min 3 Zeichen)"})
        return
    if not all(c.isalnum() or c in "-_ " for c in want):
        await websocket.send_json({"type": "character_name_check",
            "name": want, "available": False, "reason": "nur Buchstaben/Zahlen/-_ Leerzeichen"})
        return
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


async def handle_character_create(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
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
        return
    if not all(c.isalnum() or c in "-_ " for c in display_name):
        await websocket.send_json({"type": "toast",
            "text": "Spielername: nur Buchstaben/Zahlen/-_ Leerzeichen erlaubt."})
        return
    taken = await db.pool().fetchval(
        "SELECT 1 FROM players WHERE LOWER(display_name) = LOWER($1) "
        "AND name <> $2", display_name, player_id,
    )
    if taken:
        await websocket.send_json({"type": "toast",
            "text": f"Spielername '{display_name}' ist bereits vergeben."})
        return
    # Validate preset
    VALID_PRESETS = {"ember_mage", "iron_delver", "knife_runner",
                      "shieldbearer", "wanderer_cloak", "wild_ranger"}
    if preset not in VALID_PRESETS:
        await websocket.send_json({"type": "toast",
            "text": "Ungültige Charakter-Auswahl"})
        return
    # Validate allocated: gültige Attribute (aus dem Attribut-System abgeleitet,
    # bleibt automatisch synchron), sum <= 20, each <= MAX_PER_ATTR.
    VALID_ATTRS = set(attributes.ATTR_LABELS.keys())
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
        return
    # Already created? — block re-creation
    row = await db.pool().fetchrow(
        "SELECT character_created FROM players WHERE name = $1",
        player_id,
    )
    if row and row["character_created"]:
        await websocket.send_json({"type": "toast",
            "text": "Charakter ist bereits erstellt"})
        return
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


async def handle_list_talents(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    sk = await skills.get_skills(player_id)
    learned = await talents.list_learned(player_id)
    pts = await talents.get_talent_points(player_id)
    await websocket.send_json({
        "type":    "talents_update",
        "learned": learned,
        "points":  pts,
        "tree":    talents.tree_for_ui(sk, set(l["talent_id"] for l in learned), pts),
    })


register("wake", handle_wake)
register("allocate_attr", handle_allocate_attr)
register("learn_talent", handle_learn_talent)
register("learn_spell", handle_learn_spell)
register("list_attributes", handle_list_attributes)
register("character_check_name", handle_character_check_name)
register("character_create", handle_character_create)
register("list_talents", handle_list_talents)
