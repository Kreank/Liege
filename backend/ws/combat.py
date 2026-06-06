"""Combat-Handler (Phase B16): attack_npc, cast_spell.

Behält 1:1 das Verhalten aus den Legacy-Blocks in main.py — die heikelsten
zwei Branches, weil sie Loot/XP/Faction/Quest-Hooks orchestrieren.
Nutzt durchgehend services.* + Domain-Module statt der alten
main.py-Wrapper.
"""
from __future__ import annotations

import logging

import body_parts
import combat as combat_mod
import db
import factions
import loot
import needs
import quest_stages
import quests
import skills
import spell_caster
import spells
import status_effects
import talents

from services.player_equipment import get_equipped_weapon_kind
from services.player_state import heal_player as heal_player_svc

from .context import WsContext
from .dispatcher import register


async def handle_attack_npc(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    npcs = ctx.npcs
    items = ctx.items
    npc_id = int(data.get("npc_id", 0))
    npc = npcs.get(npc_id)
    if npc is None:
        return
    player = manager.get_players().get(player_id)
    if player is None:
        return
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
    attack_range = max(combat_mod.ATTACK_RANGE, _is.weapon_range(weapon))
    if combat_mod.chebyshev(player["x"], player["y"], npc["x"], npc["y"]) > attack_range:
        return
    # Ausdauer-Kosten pro Schlag — ALLE Waffen (2H teurer als 1H/Bogen).
    # Zu wenig Ausdauer → halbierter Schaden statt Block, damit der
    # Spieler nie komplett wehrlos ist.
    _heavy_dmg_penalty = 1.0
    _atk_cost = needs.attack_stamina_cost(weapon)
    if not await needs.use_stamina(player_id, _atk_cost):
        _heavy_dmg_penalty = 0.5
        await websocket.send_json({
            "type": "toast",
            "text": "🥵 Erschöpft — der Hieb hat keinen Schwung",
        })
    else:
        # Ausdauer-Balken sofort aktualisieren (Sekunden-Loop wäre träge)
        _atk_needs = await needs.get_needs(player_id)
        if _atk_needs:
            await websocket.send_json({
                "type":        "player_needs",
                "hunger":      _atk_needs["hunger"],
                "max_hunger":  _atk_needs["max_hunger"],
                "stamina":     _atk_needs["stamina"],
                "max_stamina": _atk_needs["max_stamina"],
                "thirst":      _atk_needs["thirst"],
                "max_thirst":  _atk_needs["max_thirst"],
            })
    # Talent-Effekte für Combat anwenden
    talent_effects = await talents.aggregate_effects(player_id)
    # Crit-Chance-Boost durch Talent + Welle 52: Attribut-Krit-Rate (krit_rate-
    # Total als Bruchteil, gecached). Der Roll vergleicht später rng_roll <
    # crit_chance — beide Boni senken den Roll, erhöhen also die Crit-Wahrsch.
    crit_roll = (_r.random()
                 - talent_effects.get("combat_crit_chance", 0)
                 - combat_mod.player_crit_chance(player_id))
    dmg, is_crit = combat_mod.calc_player_damage(
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
        oh_dmg, oh_crit = combat_mod.calc_player_damage(
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
    # Welle 51: Attribut-Schaden — Stärke skaliert den Angriff (gecachter Mult,
    # enthält Equipment-Affixe via damage_pct→stärke). Schließt die Lücke
    # „Stats kumulieren nicht mit dem Grundangriff".
    dmg = int(round(dmg * combat_mod.player_damage_mult(player_id)))
    # Crit-Damage-Boost
    if is_crit:
        # Welle 52: Attribut-Krit-Schaden (krit_schaden-Total als additiver
        # %-Bonus, z.B. 50 → ×1.5) ON TOP des Waffen-crit_mult, der bereits in
        # calc_player_damage angewendet wurde. Mult ist 1.0 wenn kein Sheet
        # gebaut (neutraler Default).
        dmg = int(round(dmg * combat_mod.player_crit_damage_mult(player_id)))
        if talent_effects.get("combat_crit_damage", 0) > 0:
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
            await heal_player_svc(manager, player_id, heal_amount)
    # Arm-Verletzung reduziert ausgeteilten Schaden
    bp = await body_parts.get_body_parts(player_id)
    if bp:
        dmg = int(dmg * body_parts.arm_damage_multiplier(bp["arms"]))
        if dmg < 1:
            dmg = 1
    # Stamina-Penalty: 2H-Waffe ohne genug Ausdauer → halber Hieb
    if _heavy_dmg_penalty < 1.0:
        dmg = max(1, int(dmg * _heavy_dmg_penalty))
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
    dmg = combat_mod.apply_creature_resists(
        npc["kind"], dmg,
        dmg_type=combat_mod.weapon_damage_type(weapon),
        armor_pen=_armor_pen,
    )
    result = await npcs.damage(npc_id, dmg)
    if result is None:
        drop_x, drop_y = await loot.find_drop_xy(world, structures, npc["x"], npc["y"])
        await loot.drop_loot_for_npc(manager, items, player_id, npc, drop_x, drop_y)
        import npc_worker as _nw
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
                is_hostile_kind = npc["kind"] in combat_mod.CREATURE_KINDS
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
    # Welle 31: XP-Split bei Gruppe — alle Members im 15-Tile-Radius
    _xp_amount = max(2, dmg // 2)
    _xp_shares = await combat_mod.gain_combat_xp_with_share(
        manager, player_id, _xp_amount, npc["x"], npc["y"]
    )
    for _pid, _xr in _xp_shares:
        if _pid == player_id:
            await websocket.send_json({"type": "skill_xp", **_xr})
        else:
            _ws_m = manager.connections.get(_pid)
            if _ws_m is not None:
                try:
                    await _ws_m.send_json({"type": "skill_xp", **_xr})
                except Exception:
                    pass


async def handle_cast_spell(ctx: WsContext, data: dict) -> None:
    websocket = ctx.websocket
    player_id = ctx.player_id
    manager = ctx.manager
    world = ctx.world
    structures = ctx.structures
    npcs = ctx.npcs
    items = ctx.items
    # Welle 25: Neuer Pfad — spell_id statt item_id (Hotbar/Spellbook-Cast).
    spell_id = data.get("spell_id")
    if spell_id:
        spell = spells.get(spell_id)
        if not spell:
            return
        # Spell gelernt?
        learned = await db.pool().fetchval(
            "SELECT 1 FROM learned_spells WHERE player_name = $1 AND spell_kind = $2",
            player_id, spell_id,
        )
        if not learned:
            await websocket.send_json({
                "type": "toast", "text": "Du beherrschst diesen Zauber nicht.",
            })
            return
        # Mana + Skill-Level + Position holen
        pstate = await db.pool().fetchrow(
            "SELECT mana, max_mana FROM players WHERE name = $1", player_id,
        )
        if pstate is None:
            return
        magic_lvl = await skills.get_skill_level(player_id, "magic")
        pinfo = manager.get_players().get(player_id, {})
        px, py = pinfo.get("x", 0), pinfo.get("y", 0)
        target = {
            "x":      data.get("target_x"),
            "y":      data.get("target_y"),
            "npc_id": data.get("target_npc_id"),
        }
        result = await spell_caster.start_cast(
            player_id, spell_id, target,
            current_mana=int(pstate["mana"]),
            current_x=px, current_y=py,
            magic_level=magic_lvl,
        )
        if not result.get("ok"):
            reason = result.get("reason")
            msg_text = {
                "no_mana":         f"Nicht genug Mana ({result.get('needed', 0)}).",
                "cooldown":        f"Noch nicht bereit ({result.get('remaining', 0):.1f}s).",
                "already_casting": "Du wirkst bereits einen Zauber.",
                "skill":           f"Magie-Level {result.get('needed', 0)} benötigt.",
                "out_of_range":    f"Zu weit weg (max {result.get('max', 0)} Felder).",
                "unknown_spell":   "Unbekannter Zauber.",
            }.get(reason, f"Cast fehlgeschlagen: {reason}")
            await websocket.send_json({"type": "toast", "text": msg_text})
            return
        # Mana abziehen
        new_mana = pstate["mana"] - int(spell.get("mana_cost", 0))
        await db.pool().execute(
            "UPDATE players SET mana = $1 WHERE name = $2",
            new_mana, player_id,
        )
        await websocket.send_json({
            "type": "player_mana", "mana": new_mana,
            "max_mana": pstate["max_mana"],
        })
        # Cast-Started an Client → UI zeigt Cast-Bar
        await websocket.send_json({
            "type":         "cast_started",
            "spell_id":     spell_id,
            "cast_time_ms": result["cast_time_ms"],
        })
        return  # Skip legacy item-path

    # ─── Legacy item-based cast (spell_book/scroll/rune_stone) ───
    item_id = int(data.get("item_id", 0))
    row = await db.pool().fetchrow(
        "SELECT kind FROM items WHERE id = $1 AND owner = $2",
        item_id, player_id,
    )
    if row is None:
        return
    spell = combat_mod.SPELLS.get(row["kind"])
    if spell is None:
        return
    pstate = await db.pool().fetchrow(
        "SELECT mana, max_mana FROM players WHERE name = $1", player_id
    )
    if pstate is None or pstate["mana"] < spell["mana"]:
        await websocket.send_json({
            "type": "toast",
            "text": f"Nicht genug Mana ({spell['mana']} benötigt, {pstate['mana'] if pstate else 0} vorhanden)",
        })
        return
    player_pos = manager.get_players().get(player_id)
    if player_pos is None:
        return

    # Effekt: Heal self
    if spell.get("heal_self", 0) > 0:
        await heal_player_svc(manager, player_id, spell["heal_self"])

    # Effekt: Damage
    if spell.get("damage", 0) > 0:
        candidates = [n for n in npcs.all() if n["kind"] in combat_mod.CREATURE_KINDS]
        if candidates:
            target = min(
                candidates,
                key=lambda n: combat_mod.chebyshev(player_pos["x"], player_pos["y"], n["x"], n["y"]),
            )
            dist = combat_mod.chebyshev(player_pos["x"], player_pos["y"], target["x"], target["y"])
            if dist <= spell["range"]:
                aoe = spell.get("aoe_radius", 0)
                if aoe > 0:
                    targets = [
                        n for n in candidates
                        if combat_mod.manhattan(target["x"], target["y"], n["x"], n["y"]) <= aoe
                    ]
                else:
                    targets = [target]
                # Welle 28: Spell → Pro-Animation-Kind. Map nutzt die
                # neuen 256×256 / 512×512 Spritesheet-Animations
                # aus assets/animations/professional/combat_magic/.
                spell_fx = {
                    "spell_book":         "fireball_explosion",
                    "scroll":             "hit_spark",
                    "rune_stone":         "heal_pulse",
                    # Welle 29d — neue Spell-Visuals
                    "ice_scroll":         "ice_spell",
                    "wind_slash_scroll":  "wind_slash_spell",
                    "holy_shield_scroll": "holy_shield_aura",
                }.get(row["kind"], "fireball_explosion")
                await manager.broadcast({
                    "type": "visual_effect", "kind": spell_fx,
                    "x": target["x"], "y": target["y"],
                })
                # Welle 15: Spell-Damage-Typ je nach Spell-Item
                _spell_dmg_type = {
                    "spell_book":         "fire",
                    "scroll":             "lightning",
                    "rune_stone":         "magic",
                    "ice_scroll":         "ice",
                    "wind_slash_scroll":  "magic",
                    "holy_shield_scroll": "magic",
                }.get(row["kind"], "magic")
                for t in targets:
                    _final = combat_mod.apply_creature_resists(
                        t["kind"], spell["damage"], dmg_type=_spell_dmg_type
                    )
                    result = await npcs.damage(t["id"], _final)
                    if result is None:
                        drop_x, drop_y = await loot.find_drop_xy(world, structures, t["x"], t["y"])
                        await loot.drop_loot_for_npc(manager, items, player_id, t, drop_x, drop_y)
                        await manager.broadcast({
                            "type": "npc_died", "npc_id": t["id"],
                            "killed_by": player_id, "name": t["name"],
                        })
                        # Quest-Hook auch bei Direct-Spell-Kills
                        try:
                            updated_q = await quests.on_creature_killed(
                                player_id, t["kind"], 1)
                            for q in updated_q:
                                await websocket.send_json(
                                    {"type": "quest_progress", "quest": q})
                            stage_q = await quest_stages.on_player_event(
                                player_id, "kill",
                                {"creature_kind": t["kind"], "count": 1},
                            )
                            for q in stage_q:
                                await websocket.send_json(
                                    {"type": "quest_progress", "quest": q})
                        except Exception:
                            logging.exception("quest hook (direct-spell-kill) failed")
                        # Combat-XP-Share auch bei Direct-Spell-Kills
                        try:
                            _shares = await combat_mod.gain_combat_xp_with_share(
                                manager, player_id, max(2, _final // 2), t["x"], t["y"]
                            )
                            for _pid, _xr in _shares:
                                ws_t = manager.connections.get(_pid)
                                if ws_t is not None:
                                    try: await ws_t.send_json({"type": "skill_xp", **_xr})
                                    except Exception: pass
                        except Exception:
                            logging.exception("xp share (direct-spell-kill) failed")
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


register("attack_npc", handle_attack_npc)
register("cast_spell", handle_cast_spell)
