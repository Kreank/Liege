"""Need/Greed-Loot-Roll-System für Spielergruppen.

Wenn die Gruppe `loot_rule='need_greed'` hat, lösen rollwürdige Drops
(equipment, magic, Items mit affixes/unique_name) einen 20-Sekunden-Roll
unter den Group-Members im 15-Tile-Radius aus.

Voting:
    need  — Brauchst das Item (Roll 1-100, hat Priorität vor greed)
    greed — Willst es z.B. zum Verkaufen (Roll 1-100, niedrigere Priorität)
    pass  — Aussetzen / kein Interesse

Resolution:
    1. Höchster need-Roll gewinnt (wenn min. 1 need-Vote da ist)
    2. Sonst höchster greed-Roll (wenn min. 1 greed-Vote)
    3. Sonst Item bleibt auf dem Boden, FFA-Pickup für alle frei

Trading/Trade nach dem Roll ist wie immer erlaubt — das Modul kümmert
sich nur um die Erst-Vergabe.
"""
import asyncio
import logging
import random
import time

log = logging.getLogger("liege.loot_rolls")

ROLL_DURATION_SECONDS = 20
ROLL_RADIUS_TILES = 15  # gleich wie XP-Radius für Konsistenz

_active_rolls: dict[int, dict] = {}    # roll_id → state
_item_to_roll: dict[int, int] = {}     # item_id → roll_id (während Lock)
_next_roll_id = 1


def is_rollable(item: dict) -> bool:
    """Filter: nur 'gute' Drops lösen Rolls aus. Resources/Food/Consumables
    bleiben FFA — sonst wäre für jede Beere ein Roll-Popup nötig."""
    if not item:
        return False
    cat = item.get("category", "")
    if cat in ("equipment", "magic"):
        return True
    if item.get("affixes"):
        return True
    if item.get("unique_name"):
        return True
    return False


def is_locked(item_id: int) -> bool:
    """True wenn das Item gerade in einem Roll ist und nicht aufgehoben
    werden darf (außer vom späteren Gewinner)."""
    return item_id in _item_to_roll


def allowed_picker(item_id: int) -> str | None:
    """Falls Lock besteht: Name des Gewinners (oder None falls Roll noch läuft).
    Falls kein Lock: None (= jeder darf, FFA)."""
    rid = _item_to_roll.get(item_id)
    if rid is None:
        return None
    return _active_rolls.get(rid, {}).get("winner")


async def start_roll(item: dict, group_id: int, eligible: set[str],
                     broadcast_cb, finalize_cb) -> int:
    """Startet einen Roll auf `item`.

    - broadcast_cb(message: dict, eligible: set[str]) async
    - finalize_cb(state: dict) async — wird bei Resolve aufgerufen, soll
      Item-Transfer / Lock-Release machen. State enthält 'winner', 'win_vote',
      'win_roll', 'item' etc.
    Return: roll_id (int)."""
    global _next_roll_id
    rid = _next_roll_id
    _next_roll_id += 1
    state = {
        "roll_id": rid,
        "item": item,
        "group_id": group_id,
        "eligible": eligible,
        "votes": {},          # player_name → "need"|"greed"|"pass"
        "rolls": {},          # player_name → int (1-100)
        "started_at": time.time(),
        "winner": None,
        "win_vote": None,
        "win_roll": None,
        "broadcast_cb": broadcast_cb,
        "finalize_cb": finalize_cb,
        "task": None,
    }
    _active_rolls[rid] = state
    _item_to_roll[item["id"]] = rid
    await broadcast_cb({
        "type": "loot_roll_started",
        "roll_id": rid,
        "item": item,
        "expires_in_s": ROLL_DURATION_SECONDS,
    }, eligible)
    state["task"] = asyncio.create_task(_timeout_resolve(rid))
    log.info("Roll %d gestartet: item=%s group=%d eligible=%d",
             rid, item.get("kind"), group_id, len(eligible))
    return rid


async def vote(roll_id: int, player_name: str, vote_kind: str) -> dict:
    state = _active_rolls.get(roll_id)
    if not state:
        return {"ok": False, "reason": "roll_not_found"}
    if player_name not in state["eligible"]:
        return {"ok": False, "reason": "not_eligible"}
    if player_name in state["votes"]:
        return {"ok": False, "reason": "already_voted"}
    if vote_kind not in ("need", "greed", "pass"):
        return {"ok": False, "reason": "invalid_vote"}
    state["votes"][player_name] = vote_kind
    if vote_kind in ("need", "greed"):
        state["rolls"][player_name] = random.randint(1, 100)
    await state["broadcast_cb"]({
        "type": "loot_roll_voted",
        "roll_id": roll_id,
        "player": player_name,
        "vote": vote_kind,
    }, state["eligible"])
    if len(state["votes"]) >= len(state["eligible"]):
        await _resolve(roll_id, early=True)
    return {"ok": True}


async def _timeout_resolve(roll_id: int) -> None:
    try:
        await asyncio.sleep(ROLL_DURATION_SECONDS)
        if roll_id in _active_rolls:
            await _resolve(roll_id, early=False)
    except asyncio.CancelledError:
        pass


async def _resolve(roll_id: int, early: bool) -> None:
    state = _active_rolls.pop(roll_id, None)
    if not state:
        return
    if early and state["task"]:
        try: state["task"].cancel()
        except Exception: pass
    item_id = state["item"]["id"]
    rolls = state["rolls"]
    votes = state["votes"]
    needers = sorted(
        ((p, r) for p, r in rolls.items() if votes.get(p) == "need"),
        key=lambda x: -x[1],
    )
    greeders = sorted(
        ((p, r) for p, r in rolls.items() if votes.get(p) == "greed"),
        key=lambda x: -x[1],
    )
    if needers:
        state["winner"], state["win_roll"] = needers[0]
        state["win_vote"] = "need"
    elif greeders:
        state["winner"], state["win_roll"] = greeders[0]
        state["win_vote"] = "greed"
    # Lock release
    _item_to_roll.pop(item_id, None)
    try:
        await state["finalize_cb"](state)
    except Exception:
        log.exception("Loot-Roll finalize_cb failed")
    try:
        await state["broadcast_cb"]({
            "type": "loot_roll_resolved",
            "roll_id": roll_id,
            "item_id": item_id,
            "winner": state["winner"],
            "vote": state["win_vote"],
            "roll": state["win_roll"],
            "all_rolls": [
                {"player": p, "vote": votes.get(p), "roll": rolls.get(p)}
                for p in state["eligible"]
            ],
        }, state["eligible"])
    except Exception:
        log.exception("Loot-Roll broadcast resolved failed")
    log.info("Roll %d resolved: winner=%s vote=%s roll=%s",
             roll_id, state["winner"], state["win_vote"], state["win_roll"])
