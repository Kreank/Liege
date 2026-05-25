"""Storyteller-Director (RimWorld-Pattern).

Deterministischer Event-Director, der entscheidet WAS und WANN passiert.
LLM macht danach nur den narrativen Text.

3 Modi (über STORYTELLER_MODE env oder set_mode()):
    chill     — selten, sanft (lange Pausen, geringere Mob-Spawns)
    balanced  — Standard, ausgewogen
    chaos     — häufig, hart (Raids, Boss-Spawns, Wetter)

Event-Kategorien:
    weather       — Atmosphäre, ungefährlich
    creature      — Mob-Spawn nahe Spieler
    faction       — politische Bewegung
    discovery     — Lore/Item-Spawn
    raid          — gefährliche Welle (über raid_director)
"""
import logging
import os
import random
import time

log = logging.getLogger("liege.storyteller")


MODES = ("chill", "balanced", "chaos")
DEFAULT_MODE = os.environ.get("STORYTELLER_MODE", "balanced")

# Modus-Profile
MODE_CONFIG = {
    "chill": {
        "event_interval_mult": 1.6,     # Events seltener
        "danger_weight":       0.4,     # Weniger Gefahr
        "creative_weight":     1.3,     # Mehr Atmosphäre/Discovery
        "raid_chance_mult":    0.3,
    },
    "balanced": {
        "event_interval_mult": 1.0,
        "danger_weight":       1.0,
        "creative_weight":     1.0,
        "raid_chance_mult":    1.0,
    },
    "chaos": {
        "event_interval_mult": 0.65,    # Events öfter
        "danger_weight":       1.7,
        "creative_weight":     0.7,
        "raid_chance_mult":    2.0,
    },
}

# Event-Templates: Director wählt aus diesem Pool
EVENT_TEMPLATES = [
    # (kind, weight, tag, min_wealth, requires_creature, danger)
    {"kind": "weather",   "tag": "rain",     "weight": 25, "danger": 0.0},
    {"kind": "weather",   "tag": "storm",    "weight": 18, "danger": 0.1},
    {"kind": "weather",   "tag": "fog",      "weight": 15, "danger": 0.1},
    {"kind": "weather",   "tag": "snow",     "weight": 10, "danger": 0.0},
    {"kind": "discovery", "tag": "lore",     "weight": 20, "danger": 0.0},
    {"kind": "discovery", "tag": "ruin",     "weight": 12, "danger": 0.2},
    {"kind": "creature",  "tag": "wandering","weight": 18, "danger": 0.6},
    {"kind": "creature",  "tag": "horde",    "weight": 8,  "danger": 0.9, "min_wealth": 5},
    {"kind": "faction",   "tag": "trade",    "weight": 14, "danger": 0.0},
    {"kind": "faction",   "tag": "conflict", "weight": 10, "danger": 0.5},
    {"kind": "natural",   "tag": "blessing", "weight": 8,  "danger": 0.0},
    {"kind": "natural",   "tag": "curse",    "weight": 8,  "danger": 0.5},
]


_state = {
    "mode": DEFAULT_MODE if DEFAULT_MODE in MODES else "balanced",
    "last_event_at": 0.0,
    "events_count":  0,
    "danger_streak": 0,   # wieviele danger-events in Folge
}


def set_mode(mode: str) -> None:
    if mode in MODES:
        _state["mode"] = mode
        log.info("Storyteller-Modus gewechselt zu: %s", mode)


def get_mode() -> str:
    return _state["mode"]


def time_since_last_event() -> float:
    if _state["last_event_at"] == 0:
        return 999999.0
    return time.monotonic() - _state["last_event_at"]


def should_fire_event(base_interval: float, world_state: dict) -> bool:
    """Entscheidet ob jetzt ein Event passieren sollte."""
    cfg = MODE_CONFIG[_state["mode"]]
    effective_interval = base_interval * cfg["event_interval_mult"]
    return time_since_last_event() >= effective_interval


def select_event(world_state: dict) -> dict | None:
    """Wählt deterministisch (gewichtet) das nächste Event basierend auf Welt-Zustand + Modus.

    world_state: {
        "active_players": N,
        "wealth_score":   N,    # z.B. Anzahl player-built structures
        "creature_count": N,
        "structure_count":N,
    }
    Returns Event-Template oder None wenn nichts passt.
    """
    cfg = MODE_CONFIG[_state["mode"]]
    candidates = []
    wealth = world_state.get("wealth_score", 0)
    creature_count = world_state.get("creature_count", 0)

    for tmpl in EVENT_TEMPLATES:
        # Wealth-Gate
        if tmpl.get("min_wealth", 0) > wealth:
            continue
        # Wenn keine Creatures in der Welt: kein "horde"-Event
        if tmpl["kind"] == "creature" and tmpl["tag"] == "horde" and creature_count < 2:
            continue
        # Mode-spezifisches Re-weighting
        weight = tmpl["weight"]
        danger = tmpl.get("danger", 0.0)
        # Anti-Streak: nach 2 danger-Events höhere Chance auf nicht-danger
        if _state["danger_streak"] >= 2 and danger > 0.3:
            weight *= 0.3
        if danger > 0.3:
            weight *= cfg["danger_weight"]
        else:
            weight *= cfg["creative_weight"]
        if tmpl["kind"] == "creature" and tmpl["tag"] == "horde":
            weight *= cfg["raid_chance_mult"]
        candidates.append((tmpl, max(0.01, weight)))

    if not candidates:
        return None
    templates = [c[0] for c in candidates]
    weights = [c[1] for c in candidates]
    chosen = random.choices(templates, weights=weights, k=1)[0]

    # Streak-Tracking
    if chosen.get("danger", 0) > 0.3:
        _state["danger_streak"] += 1
    else:
        _state["danger_streak"] = 0

    return chosen


def mark_event_fired() -> None:
    _state["last_event_at"] = time.monotonic()
    _state["events_count"] += 1


def status_summary() -> dict:
    return {
        "mode":           _state["mode"],
        "events_fired":   _state["events_count"],
        "danger_streak":  _state["danger_streak"],
        "last_event_age_s": time_since_last_event(),
    }
