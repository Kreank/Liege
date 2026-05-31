"""Player-Lifecycle (Welle 34c, extrahiert aus main.py).

Enthält:
- load_or_create_player: Spawn-Load + DB-Insert für neuen Spieler
- heal_player / damage_player: Stat-Mutation mit Broadcasts
- is_downed / _enter_downed_state / _downed_timer / _do_respawn:
  Downed-Mechanik (30s liegen, Respawn am Bett/Spawn-Punkt)
- restore_mana / _refund_mana: Mana-Helper

Module-Globals werden als Parameter durchgereicht, sodass das Modul keine
zirkulären Importe von main.py braucht.
"""

import asyncio
import logging
import time

import db
import body_parts
import combat
import spell_caster

from .player_comms import send_to_player


DEFAULT_SPAWN_CENTER = (60, 40)  # nahe Mitte der Legacy-Welt
DOWNED_DURATION_S = 30.0

# Modul-globaler Downed-State, geteilt zwischen den Helfern hier (und vom
# spell-cast-Code drüben im spells-Modul über apply_spell_effects abgefragt).
# player_name → {downed_at: epoch, x, y, task: asyncio.Task}
downed_state: dict[str, dict] = {}

# Modul-globale World/Structures-Refs für _downed_timer (das automatische
# Respawnen nach 30s ohne Wiederbelebung). Werden via init() vom Startup
# in main.py gesetzt. Vermeidet dass jeder Helper ein 7-Parameter-Aufruf wird.
_world = None
_structures = None


def init(world, structures) -> None:
    """Bindet World+StructureManager an dieses Modul. Vom main.py-Startup
    aufgerufen, sobald world geladen ist (lifespan-Funktion)."""
    global _world, _structures
    _world = world
    _structures = structures


async def load_or_create_player(world, structures, name: str) -> dict:
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
            new_pos = await world.find_spawn(*DEFAULT_SPAWN_CENTER, structures=structures)
            spawn["x"], spawn["y"] = new_pos["x"], new_pos["y"]
            await db.pool().execute(
                "UPDATE players SET x = $1, y = $2 WHERE name = $3",
                spawn["x"], spawn["y"], name,
            )
        return spawn

    pos = await world.find_spawn(*DEFAULT_SPAWN_CENTER, structures=structures)
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


async def heal_player(manager, name: str, amount: int) -> None:
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


def is_downed(player_name: str) -> bool:
    return player_name in downed_state


async def _enter_downed_state(manager, name: str) -> None:
    if is_downed(name):
        return
    row = await db.pool().fetchrow(
        "SELECT x, y FROM players WHERE name = $1", name,
    )
    if row is None:
        return
    px, py = row["x"], row["y"]
    await db.pool().execute("UPDATE players SET hp = 0 WHERE name = $1", name)
    # Aktiven Cast cleanen
    spell_caster.cleanup_player(name)
    # 30s-Timer
    task = asyncio.create_task(_downed_timer(manager, name))
    downed_state[name] = {
        "downed_at":  time.time(),
        "x":          px, "y": py,
        "task":       task,
    }
    await send_to_player(manager, name, {
        "type":       "player_downed",
        "duration_s": DOWNED_DURATION_S,
        "x":          px, "y": py,
    })
    await manager.broadcast({
        "type": "player_downed_visible", "player_id": name,
        "x":    px, "y": py,
    }, exclude=name)


async def _downed_timer(manager, name: str) -> None:
    try:
        await asyncio.sleep(DOWNED_DURATION_S)
        if is_downed(name):
            await do_respawn(manager, _world, _structures, name, in_place=False)
    except asyncio.CancelledError:
        pass
    except Exception:
        logging.exception("downed_timer failed for %s", name)


async def do_respawn(manager, world, structures, name: str, in_place: bool = False) -> None:
    """Respawn am Spawn-Punkt (oder in-place bei Resurrection). Räumt
    Down-State, setzt full HP."""
    state = downed_state.pop(name, None)
    if state and state.get("task"):
        try:
            state["task"].cancel()
        except Exception:
            pass
    row = await db.pool().fetchrow(
        "SELECT max_hp, spawn_x, spawn_y FROM players WHERE name = $1", name,
    )
    if row is None:
        return
    if in_place and state:
        x, y = state["x"], state["y"]
    elif row["spawn_x"] is not None and row["spawn_y"] is not None:
        # Welle 25: Heim-Spawn (Bett/Lagerfeuer). Falls die Position inzwischen
        # blockiert ist, suche ein freies Nachbar-Tile.
        hx, hy = int(row["spawn_x"]), int(row["spawn_y"])
        if (await world.is_walkable(hx, hy)) and not structures.blocks(hx, hy):
            x, y = hx, hy
        else:
            spawn = await world.find_spawn(hx, hy, structures=structures)
            x, y = spawn["x"], spawn["y"]
    else:
        spawn = await world.find_spawn(*DEFAULT_SPAWN_CENTER, structures=structures)
        x, y = spawn["x"], spawn["y"]
    await db.pool().execute(
        "UPDATE players SET hp = max_hp, x = $1, y = $2 WHERE name = $3",
        x, y, name,
    )
    manager.update_player(name, x, y)
    await send_to_player(manager, name, {
        "type":   "player_respawned",
        "x":      x, "y": y,
        "hp":     row["max_hp"], "max_hp": row["max_hp"],
        "in_place": in_place,
    })
    await manager.broadcast({
        "type": "player_moved", "player_id": name, "x": x, "y": y,
    }, exclude=name)
    await manager.broadcast({
        "type": "player_revived_visible", "player_id": name,
    }, exclude=name)


async def restore_mana(manager, name: str, amount: int) -> None:
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


async def refund_mana(manager, player_id: str, amount: int) -> None:
    await restore_mana(manager, player_id, amount)


async def damage_player(manager, name: str, dmg: int, source_npc_id: int | None = None,
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
    # Welle 25: Downed-Spieler nehmen keinen Schaden mehr.
    if is_downed(name):
        return
    # Welle 25: Damage unterbricht aktiven Cast (Standard-RPG-Verhalten).
    if spell_caster.is_casting(name):
        spell_caster.interrupt(name, "damage_taken")
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
        # Welle 25: Spieler geht in DOWNED-State (30s) statt sofort respawn.
        # Ressurrection-Spell oder force_respawn beenden den Zustand früher.
        await _enter_downed_state(manager, name)
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
