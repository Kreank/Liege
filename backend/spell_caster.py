"""Spell-Cast-Engine — Cast-Timer, Cooldowns, Interrupts.

Hält den ephemeren Cast-State (welcher Spieler castet was wann) und
Cooldown-Map in-memory. Da Casts immer im Sekundenbereich liegen, ist
Persistierung nicht nötig — bei Server-Restart wird alles "abgebrochen"
und kann ohne Schaden neu gewürfelt werden.

Effekte werden über Callback-Hooks an main.py delegiert. Damit bleibt
dieses Modul testbar und entkoppelt.
"""
import asyncio
import logging
import time
from typing import Awaitable, Callable

import spells

log = logging.getLogger("liege.spell_caster")


# player_name → {
#     spell_id, target (dict with x/y/npc_id), start_at, finish_at,
#     task (asyncio.Task), interrupted (bool), mana_paid (int)
# }
_active_casts: dict[str, dict] = {}

# (player_name, spell_id) → ready_at (epoch seconds)
_cooldowns: dict[tuple[str, str], float] = {}


# Effect-Callbacks werden von main.py beim Startup gesetzt.
# heal_cb(player_id: str, amount: int)
# damage_npc_cb(npc_id: int, amount: int, dmg_type: str, by_player: str) → npc_died?
# damage_player_cb(player_id: str, dmg: int)
# status_npc_cb(npc_id: int, effect: str, magnitude: int, duration: int)
# status_player_cb(player_id: str, effect: str, magnitude: int, duration: int)
# broadcast_cb(payload: dict)
# send_to_player_cb(player_id: str, payload: dict)
# refund_mana_cb(player_id: str, amount: int)
# aggro_cb(player_id: str, x: int, y: int, threat: int)

_callbacks: dict[str, Callable] = {}


def set_callbacks(**cbs) -> None:
    _callbacks.update(cbs)


def _cb(name: str) -> Callable:
    fn = _callbacks.get(name)
    if fn is None:
        raise RuntimeError(f"spell_caster callback '{name}' not set")
    return fn


def is_casting(player_id: str) -> bool:
    return player_id in _active_casts


def cooldown_remaining(player_id: str, spell_id: str) -> float:
    ready_at = _cooldowns.get((player_id, spell_id), 0.0)
    return max(0.0, ready_at - time.monotonic())


def active_cast(player_id: str) -> dict | None:
    """Snapshot für externe Reader (z.B. UI-Sync)."""
    c = _active_casts.get(player_id)
    if not c:
        return None
    return {
        "spell_id":  c["spell_id"],
        "start_at":  c["start_at"],
        "finish_at": c["finish_at"],
    }


async def start_cast(player_id: str, spell_id: str, target: dict,
                      current_mana: int, current_x: int, current_y: int,
                      magic_level: int) -> dict:
    """Versucht einen Cast zu starten. Returns Result-Dict:
        {"ok": True, "cast_time_ms": int, "spell_id": ...}
        {"ok": False, "reason": "no_mana"|"cooldown"|"already_casting"|"skill"|"range"|"unknown_spell"|"out_of_range"}
    """
    if is_casting(player_id):
        return {"ok": False, "reason": "already_casting"}

    spell = spells.get(spell_id)
    if spell is None:
        return {"ok": False, "reason": "unknown_spell"}

    if magic_level < spell.get("skill_req", 0):
        return {"ok": False, "reason": "skill",
                "needed": spell["skill_req"]}

    cd_rem = cooldown_remaining(player_id, spell_id)
    if cd_rem > 0.05:
        return {"ok": False, "reason": "cooldown", "remaining": cd_rem}

    mana_cost = int(spell.get("mana_cost", 0))
    if current_mana < mana_cost:
        return {"ok": False, "reason": "no_mana", "needed": mana_cost}

    # Range-Check (für single/aoe/ground; group/self ignoriert)
    rng = spell.get("range")
    if rng is not None and target.get("x") is not None and target.get("y") is not None:
        dist = abs(target["x"] - current_x) + abs(target["y"] - current_y)
        if dist > rng:
            return {"ok": False, "reason": "out_of_range", "max": rng}

    cast_time_ms = int(spell.get("cast_time_ms", 0))
    now = time.monotonic()
    cast_info = {
        "spell_id":   spell_id,
        "target":     target,
        "start_at":   now,
        "finish_at":  now + cast_time_ms / 1000.0,
        "interrupted": False,
        "mana_paid":  mana_cost,
        "task":       None,
    }
    _active_casts[player_id] = cast_info

    # Threat aus Heal-Cast → Aggro-Pull (sofort beim Cast-Start)
    threat = int(spell.get("threat", 0))
    if threat > 0:
        try:
            cb = _callbacks.get("aggro_cb")
            if cb:
                await cb(player_id, current_x, current_y, threat)
        except Exception:
            log.exception("aggro_cb failed")

    # Cast-Task starten
    task = asyncio.create_task(
        _cast_loop(player_id, spell_id, cast_time_ms)
    )
    cast_info["task"] = task

    return {"ok": True, "cast_time_ms": cast_time_ms, "spell_id": spell_id}


def interrupt(player_id: str, reason: str = "interrupted") -> dict | None:
    """Brecht Cast ab. Setzt `interrupted` damit der Cast-Loop sauber endet.
    Returns Cast-Info (für caller-side mana-refund), oder None wenn kein Cast aktiv."""
    cast = _active_casts.get(player_id)
    if cast is None:
        return None
    if cast.get("interrupted"):
        return cast
    cast["interrupted"] = True
    cast["interrupt_reason"] = reason
    return cast


async def _cast_loop(player_id: str, spell_id: str, cast_time_ms: int) -> None:
    """Wartet bis Cast-Time abgelaufen oder Interrupt gesetzt. Dann Effekte
    anwenden oder Mana refunden."""
    try:
        # Polling-Loop für Interrupt-Check (50ms-Auflösung)
        end_at = time.monotonic() + cast_time_ms / 1000.0
        while time.monotonic() < end_at:
            await asyncio.sleep(0.05)
            cast = _active_casts.get(player_id)
            if cast is None:
                return  # Spieler weg
            if cast["interrupted"]:
                # Refund 50% mana bei Interrupt
                refund = max(1, cast["mana_paid"] // 2)
                refund_cb = _callbacks.get("refund_mana_cb")
                if refund_cb:
                    try:
                        await refund_cb(player_id, refund)
                    except Exception:
                        log.exception("refund_mana_cb failed")
                # Broadcast Interrupt
                send_cb = _callbacks.get("send_to_player_cb")
                if send_cb:
                    await send_cb(player_id, {
                        "type":     "cast_interrupted",
                        "spell_id": spell_id,
                        "reason":   cast.get("interrupt_reason", "interrupted"),
                    })
                return

        # Cast erfolgreich → Effekte ausführen
        cast = _active_casts.pop(player_id, None)
        if cast is None:
            return
        await _apply_effects(player_id, spell_id, cast["target"])

        # Cooldown setzen
        spell = spells.get(spell_id) or {}
        cd_ms = int(spell.get("cooldown_ms", 0))
        if cd_ms > 0:
            _cooldowns[(player_id, spell_id)] = time.monotonic() + cd_ms / 1000.0

        # Cast-Finished an Client
        send_cb = _callbacks.get("send_to_player_cb")
        if send_cb:
            await send_cb(player_id, {
                "type":     "cast_finished",
                "spell_id": spell_id,
                "cooldown_ms": cd_ms,
            })
    finally:
        _active_casts.pop(player_id, None)


async def _apply_effects(player_id: str, spell_id: str, target: dict) -> None:
    """Verteilt Effekte (heal/damage/status) an die richtigen Callbacks."""
    spell = spells.get(spell_id)
    if not spell:
        return
    apply_cb = _callbacks.get("apply_effects_cb")
    if apply_cb is None:
        log.error("apply_effects_cb not registered")
        return
    try:
        await apply_cb(player_id, spell_id, spell, target)
    except Exception:
        log.exception("apply_effects_cb failed for spell %s", spell_id)


def cleanup_player(player_id: str) -> None:
    """Beim Disconnect: aktiven Cast + Cooldowns räumen."""
    cast = _active_casts.pop(player_id, None)
    if cast and cast.get("task"):
        try:
            cast["task"].cancel()
        except Exception:
            pass
    for key in list(_cooldowns.keys()):
        if key[0] == player_id:
            _cooldowns.pop(key, None)
