"""Spell-Definitionen — zwei Schulen (Heiler, Magier) mit je 5 Spells.

Jeder Spell hat Cast-Time, Mana-Cost, Cooldown und einen skill_req auf den
'magic'-Skill. Effekte werden über vorhandene Mechaniken (status_effects,
combat.damage, heal) angewendet.

Die Sprite-Icons referenzieren Frames aus den FX-Anims unter
assets/animations/professional/combat_magic/ — jeder Spell setzt seinen
icon_path direkt auf einen passenden Frame.
"""

# target_kind:
#   self    — wirkt auf den Caster (Heal, Mana Shield)
#   single  — wirkt auf ein gewähltes Ziel (NPC oder Spieler)
#   aoe     — wirkt auf alle in radius um Ziel-Tile
#   group   — wirkt auf alle Spieler in radius um Caster
#   ground  — wirkt auf eine angeklickte Tile (Meteor)
#
# effect.kind:
#   heal           — heilt HP (amount)
#   damage         — direkter Schaden (amount, damage_type)
#   status         — wendet Status-Effekt an (effect, magnitude, duration)
#   resurrect      — heilt + setzt down-Status zurück
#
# Ein Spell darf mehrere Effekte haben (effects-Liste).

SPELLS = {
    # ─── Heiler-Schule ─────────────────────────────────────────────────────────
    "lesser_heal": {
        "name":         "Schwache Heilung",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/heal_pulse/heal_pulse_01.png",
        "fx_anim":      "heal_glow",
        "target_kind":  "self",
        "cast_time_ms": 1000,
        "mana_cost":    8,
        "cooldown_ms":  1500,
        "skill_req":    1,
        "threat":       8,
        "effects": [
            {"kind": "heal", "amount": 18},
        ],
        "description":  "Kleine Sofortheilung. Geringer Mana-Verbrauch.",
    },
    "heal": {
        "name":         "Heilung",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/heal_pulse/heal_pulse_08.png",
        "fx_anim":      "heal_glow",
        "target_kind":  "self",
        "cast_time_ms": 2000,
        "mana_cost":    18,
        "cooldown_ms":  3000,
        "skill_req":    4,
        "threat":       18,
        "effects": [
            {"kind": "heal", "amount": 45},
        ],
        "description":  "Mittelstarke Heilung. Längerer Cast.",
    },
    "group_heal": {
        "name":         "Gruppenheilung",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/heal_pulse/heal_pulse_10.png",
        "fx_anim":      "magic_circle",
        "target_kind":  "group",
        "radius":       6,
        "cast_time_ms": 3000,
        "mana_cost":    35,
        "cooldown_ms":  12000,
        "skill_req":    8,
        "threat":       40,
        "effects": [
            {"kind": "heal", "amount": 30},
        ],
        "description":  "Heilt dich und alle Spieler im Umkreis von 6 Feldern.",
    },
    "mana_shield": {
        "name":         "Mana-Schild",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/magic_circle/magic_circle_06.png",
        "fx_anim":      "magic_circle",
        "target_kind":  "self",
        "cast_time_ms": 1500,
        "mana_cost":    20,
        "cooldown_ms":  20000,
        "skill_req":    5,
        "threat":       5,
        "effects": [
            # Magnitude 50 == 50% Damage-Reduktion (siehe status_effects.damage_reduction_for)
            {"kind": "status", "effect": "shielded", "magnitude": 50, "duration": 20},
        ],
        "description":  "Reduziert eingehenden Schaden um 50 % für 20 s.",
    },
    "resurrection": {
        "name":         "Wiederbelebung",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/holy_shield_aura/holy_shield_aura_04.png",
        "fx_anim":      "heal_glow",
        "target_kind":  "downed",      # zielt auf einen nahen, gefallenen Spieler
        "range":        4,
        "cast_time_ms": 4000,
        "mana_cost":    60,
        "cooldown_ms":  60000,
        "skill_req":    12,
        "threat":       0,
        "effects": [
            {"kind": "revive"},        # Sonderfall: hebt Down-Status auf
            {"kind": "status", "effect": "blessed", "magnitude": 5, "duration": 30},
        ],
        "description":  "Belebt einen gefallenen Mitspieler in der Nähe wieder (max 4 Felder).",
    },

    # ─── Magier-Schule ─────────────────────────────────────────────────────────
    "magic_missile": {
        "name":         "Magisches Geschoss",
        "school":       "mage",
        "icon_path":    "/assets/animations/professional/combat_magic/magic_circle/magic_circle_04.png",
        "fx_anim":      "hit_spark",
        "target_kind":  "single",
        "range":        7,
        "cast_time_ms": 0,            # Instant
        "mana_cost":    6,
        "cooldown_ms":  1200,
        "skill_req":    1,
        "effects": [
            {"kind": "damage", "amount": 14, "damage_type": "magic"},
        ],
        "description":  "Instant-Geschoss. Geringer Schaden, kein Cast.",
    },
    "fireball": {
        "name":         "Feuerball",
        "school":       "mage",
        "icon_path":    "/assets/animations/professional/combat_magic/fireball_explosion/fireball_explosion_06.png",
        "fx_anim":      "fireball_explosion",
        "target_kind":  "aoe",
        "range":        8,
        "radius":       2,
        "cast_time_ms": 1500,
        "mana_cost":    18,
        "cooldown_ms":  4000,
        "skill_req":    4,
        "effects": [
            {"kind": "damage", "amount": 30, "damage_type": "fire"},
            {"kind": "status", "effect": "burning", "magnitude": 4, "duration": 9},
        ],
        "description":  "AoE-Schaden + brennende Wunden (DoT).",
    },
    "frostbolt": {
        "name":         "Frostpfeil",
        "school":       "mage",
        "icon_path":    "/assets/animations/spells/ice_shard_projectile.png",
        "fx_anim":      "ice_shard",
        "target_kind":  "single",
        "range":        7,
        "cast_time_ms": 1200,
        "mana_cost":    12,
        "cooldown_ms":  2500,
        "skill_req":    3,
        "effects": [
            {"kind": "damage", "amount": 22, "damage_type": "ice"},
            {"kind": "status", "effect": "slowed", "magnitude": 50, "duration": 4},
        ],
        "description":  "Eisschaden + verlangsamt das Ziel um 50 % für 4 s.",
    },
    "lightning_bolt": {
        "name":         "Blitzschlag",
        "school":       "mage",
        "icon_path":    "/assets/animations/spells/lightning_bolt_projectile.png",
        "fx_anim":      "lightning_strike",
        "target_kind":  "single",
        "range":        9,
        "cast_time_ms": 1800,
        "mana_cost":    22,
        "cooldown_ms":  5000,
        "skill_req":    6,
        "effects": [
            {"kind": "damage", "amount": 42, "damage_type": "lightning"},
        ],
        "description":  "Hoher Einzelschaden auf große Distanz.",
    },
    "meteor": {
        "name":         "Meteor",
        "school":       "mage",
        "icon_path":    "/assets/animations/professional/combat_magic/fireball_explosion/fireball_explosion_12.png",
        "fx_anim":      "fireball_explosion",
        "target_kind":  "ground",
        "range":        10,
        "radius":       4,
        "cast_time_ms": 4500,
        "mana_cost":    60,
        "cooldown_ms":  45000,
        "skill_req":    14,
        "effects": [
            {"kind": "damage", "amount": 90, "damage_type": "fire"},
            {"kind": "status", "effect": "burning", "magnitude": 8, "duration": 12},
        ],
        "description":  "Ultimativer Flächenschaden. Lange Cast-Zeit, lange Abklingzeit.",
    },
}


def get(spell_id: str) -> dict | None:
    return SPELLS.get(spell_id)


def all_ids() -> list[str]:
    return list(SPELLS.keys())


def all_for_school(school: str) -> list[str]:
    return [sid for sid, s in SPELLS.items() if s["school"] == school]


# ─── Spell-Books — Items zum Spell-Lernen ────────────────────────────────────
# spell_book_<id> Items werden in ITEM_KINDS (items.py) ergänzt; beim use wird
# der zugehörige Spell gelernt.

def book_to_spell_id(book_kind: str) -> str | None:
    """spell_book_fireball → 'fireball'."""
    if not book_kind.startswith("spell_book_"):
        return None
    return book_kind[len("spell_book_"):]


async def try_unlock_by_level(player_name: str, magic_level: int) -> list[str]:
    """Schaltet alle Spells frei, deren skill_req der Spieler erreicht hat.
    Returns Liste der NEU gelernten spell_ids."""
    import db
    eligible = [
        sid for sid, s in SPELLS.items()
        if magic_level >= int(s.get("skill_req", 0))
    ]
    if not eligible:
        return []
    existing_rows = await db.pool().fetch(
        "SELECT spell_kind FROM learned_spells WHERE player_name = $1",
        player_name,
    )
    existing = {r["spell_kind"] for r in existing_rows}
    new_ones = [sid for sid in eligible if sid not in existing]
    for sid in new_ones:
        await db.pool().execute(
            "INSERT INTO learned_spells (player_name, spell_kind) "
            "VALUES ($1, $2) ON CONFLICT DO NOTHING",
            player_name, sid,
        )
    return new_ones


# ─── Welle 34c: WS-Side Spell-Helpers (extrahiert aus main.py) ───────────────

async def sync_learned_for_player(player_name: str) -> list[str]:
    """Welle 25: schaltet jeden Spell automatisch frei, dessen skill_req der
    Spieler erreicht hat. Returns Liste neu freigeschalteter spell-IDs."""
    import db
    import skills
    magic_lvl = await skills.get_skill_level(player_name, "magic")
    eligible = [
        sid for sid, s in SPELLS.items()
        if magic_lvl >= int(s.get("skill_req", 0))
    ]
    if not eligible:
        return []
    existing_rows = await db.pool().fetch(
        "SELECT spell_kind FROM learned_spells WHERE player_name = $1",
        player_name,
    )
    existing = {r["spell_kind"] for r in existing_rows}
    new_ones = [sid for sid in eligible if sid not in existing]
    for sid in new_ones:
        await db.pool().execute(
            "INSERT INTO learned_spells (player_name, spell_kind) "
            "VALUES ($1, $2) ON CONFLICT DO NOTHING",
            player_name, sid,
        )
    return new_ones


async def list_learned_for_player(player_name: str) -> list[str]:
    import db
    rows = await db.pool().fetch(
        "SELECT spell_kind FROM learned_spells WHERE player_name = $1",
        player_name,
    )
    return [r["spell_kind"] for r in rows]


async def apply_spell_effects(manager, npcs, player_id: str, spell_id: str,
                                spell: dict, target: dict,
                                heal_player_fn, do_respawn_fn, is_downed_fn,
                                send_to_player_fn,
                                find_drop_xy_fn, drop_loot_for_npc_fn,
                                gain_combat_xp_with_share_fn,
                                downed_state: dict) -> None:
    """Wendet die effects-Liste eines Spells an. Target ist ein Dict mit
    optional x/y/npc_id. Mana ist bereits beim Cast-Start abgezogen."""
    import logging
    import combat
    import quests as _quests
    import quest_stages
    import skills
    import status_effects
    target_kind = spell.get("target_kind", "self")

    # Welle 53 — Spell-Skalierung: Schaden UND Heilung wachsen mit dem Magie-
    # Skill des Casters. Vorher waren beide FLAT (Fireball Lvl 1 == Lvl 50),
    # womit Caster (die ja nur ihre Fähigkeiten haben) nicht spielbar skalierten.
    # +4% pro Magie-Level → Lvl 25 ≈ ×2. Intelligenz speist weiterhin den Mana-
    # Pool (mehr Casts); reine Spell-Power hängt am Magie-Skill (Caster-Meisterschaft).
    _magic_lvl = await skills.get_skill_level(player_id, "magic")
    power_mult = 1.0 + _magic_lvl * 0.04

    # FX-Animation broadcasten — auf Ziel-Position (für AoE/single) oder
    # Caster-Position (für self/group).
    fx_kind = spell.get("fx_anim")
    pinfo = manager.get_players().get(player_id, {})
    fx_x = target.get("x", pinfo.get("x", 0))
    fx_y = target.get("y", pinfo.get("y", 0))
    if fx_kind:
        await manager.broadcast({
            "type": "visual_effect", "kind": fx_kind,
            "x": fx_x, "y": fx_y,
        })

    # Sammle Affected-Targets je nach target_kind
    affected_npcs: list[dict] = []
    affected_players: list[str] = []

    if target_kind == "self":
        affected_players = [player_id]
    elif target_kind == "single":
        npc_id = target.get("npc_id")
        if npc_id is not None:
            n = npcs.get(int(npc_id))
            if n is not None:
                affected_npcs = [n]
    elif target_kind == "aoe":
        radius = int(spell.get("radius", 2))
        tx, ty = int(target.get("x", 0)), int(target.get("y", 0))
        affected_npcs = [
            n for n in npcs.all()
            if n["kind"] in combat.CREATURE_KINDS
               and abs(n["x"] - tx) + abs(n["y"] - ty) <= radius
        ]
    elif target_kind == "ground":
        radius = int(spell.get("radius", 4))
        tx, ty = int(target.get("x", 0)), int(target.get("y", 0))
        affected_npcs = [
            n for n in npcs.all()
            if n["kind"] in combat.CREATURE_KINDS
               and abs(n["x"] - tx) + abs(n["y"] - ty) <= radius
        ]
    elif target_kind == "group":
        radius = int(spell.get("radius", 6))
        px, py = pinfo.get("x", 0), pinfo.get("y", 0)
        for pname, pdata in manager.get_players().items():
            if abs(pdata.get("x", 0) - px) + abs(pdata.get("y", 0) - py) <= radius:
                affected_players.append(pname)
    elif target_kind == "downed":
        # Welle 25: Resurrection — sucht nahe gefallene Mitspieler
        rng = int(spell.get("range", 4))
        px, py = pinfo.get("x", 0), pinfo.get("y", 0)
        for dname, dstate in downed_state.items():
            if dname == player_id:
                continue   # Caster selbst kann nicht casten (er ist down)
            if abs(dstate["x"] - px) + abs(dstate["y"] - py) <= rng:
                affected_players.append(dname)

    # Apply effects
    for eff in spell.get("effects", []):
        ekind = eff.get("kind")
        if ekind == "revive":
            # Welle 25: Resurrection auf affected_players (downed)
            for pname in affected_players:
                if is_downed_fn(pname):
                    await do_respawn_fn(pname, in_place=True)
        elif ekind == "heal":
            amount = int(round(int(eff.get("amount", 0)) * power_mult))
            for pname in affected_players:
                await heal_player_fn(pname, amount)
        elif ekind == "damage":
            amount = int(round(int(eff.get("amount", 0)) * power_mult))
            dmg_type = eff.get("damage_type", "magic")
            for n in affected_npcs:
                final = combat.apply_creature_resists(n["kind"], amount, dmg_type=dmg_type)
                result = await npcs.damage(n["id"], final)
                if result is None:
                    drop_x, drop_y = await find_drop_xy_fn(n["x"], n["y"])
                    await drop_loot_for_npc_fn(player_id, n, drop_x, drop_y)
                    await manager.broadcast({
                        "type": "npc_died", "npc_id": n["id"],
                        "killed_by": player_id, "name": n["name"],
                    })
                    # Quest-Hook auch bei Spell-Kills
                    try:
                        updated_q = await _quests.on_creature_killed(player_id, n["kind"], 1)
                        for q in updated_q:
                            await send_to_player_fn(player_id,
                                                  {"type": "quest_progress", "quest": q})
                        stage_q = await quest_stages.on_player_event(
                            player_id, "kill",
                            {"creature_kind": n["kind"], "count": 1},
                        )
                        for q in stage_q:
                            await send_to_player_fn(player_id,
                                                  {"type": "quest_progress", "quest": q})
                    except Exception:
                        logging.exception("quest hook (spell-kill) failed")
                    # Combat-XP-Share auch bei Spell-Kills (analog Melee-Kill)
                    try:
                        _shares = await gain_combat_xp_with_share_fn(
                            player_id, max(2, final // 2), n["x"], n["y"]
                        )
                        for _pid, _xr in _shares:
                            ws_t = manager.connections.get(_pid)
                            if ws_t is not None:
                                try: await ws_t.send_json({"type": "skill_xp", **_xr})
                                except Exception: pass
                    except Exception:
                        logging.exception("xp share (spell-kill) failed")
                else:
                    await manager.broadcast({
                        "type": "npc_damaged", "npc_id": n["id"],
                        "hp": result["hp"], "max_hp": result["max_hp"],
                        "dmg": final, "by": player_id,
                    })
        elif ekind == "status":
            sname = eff.get("effect")
            mag = int(eff.get("magnitude", 0))
            dur = int(eff.get("duration", 5))
            if sname is None:
                continue
            # Auf Player (self/group) → status_effects.apply("player", ...)
            for pname in affected_players:
                try:
                    await status_effects.apply("player", pname, sname, mag, dur)
                    effs = await status_effects.list_for_target("player", pname)
                    await send_to_player_fn(pname, {"type": "status_effects", "effects": effs})
                except Exception:
                    logging.exception("status apply player failed")
            # Auf NPCs (single/aoe/ground) → npc-status
            for n in affected_npcs:
                try:
                    await status_effects.apply("npc", str(n["id"]), sname, mag, dur)
                except Exception:
                    logging.exception("status apply npc failed")

    # Magic-XP basierend auf Mana-Cost
    mana_cost = int(spell.get("mana_cost", 0))
    if mana_cost > 0:
        xp_result = await skills.gain_xp(player_id, "magic", 5 + mana_cost // 2)
        if xp_result:
            await send_to_player_fn(player_id, {"type": "skill_xp", **xp_result})
