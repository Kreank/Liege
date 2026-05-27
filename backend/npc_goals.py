"""NPC-Goal-System (Welle 20, Session 2) — NPCs mit Tagesplänen.

NPCs bekommen ein `current_goal` das ihre Bewegung steuert:

    Goal          Bedeutung                                    Triggert wann
    ─────────────────────────────────────────────────────────────────────────
    sleep         NPC geht zum home und schläft                Nachts (21:00-06:00)
    work          NPC arbeitet an einer passenden Struktur     Tagsüber (09:00-17:00)
    socialize     NPC sucht einen anderen NPC zum Plaudern     Abends (17:00-21:00)
    eat           NPC sucht Feuer/Brunnen                      Morgens (06:00-09:00) + selten
    wander        Default: zufällig laufen                     Wenn nichts passt

Jeder NPC-Kind hat eine "Arbeitsstruktur":
    blacksmith → anvil
    farmer     → farm_plot
    miner      → workbench (Steine zerkleinern)
    healer     → bed (Patienten)
    merchant   → home (Markt)
    villager   → well oder farm_plot
    bard       → wandern (kein fester Arbeitsplatz)
    soldier    → patrouilliert (kein Goal-Target, wandert)

Goals werden in-memory am NpcManager-State gehalten — kein DB-Schema-Change.
Bei Server-Restart werden Goals neu berechnet.
"""
import logging
import random

import combat
import time_system

log = logging.getLogger("liege.npc_goals")

# NPC-Kind → bevorzugte Arbeits-Struktur (struct_type)
WORK_STRUCTURE_BY_KIND = {
    "blacksmith":   "anvil",
    "farmer":       "farm_plot",
    "villager":     "well",
    "miner":        "workbench",
    "healer":       "bed",
    "merchant":     None,    # bleibt bei home
    "bard":         None,    # wandert
    "scholar":      "workbench",
    "watchman":     None,    # patrouilliert
    "guard":        None,
    "mage":         "workbench",
    "hermit":       None,
    "quest_giver":  None,
    "village_elder":"well",
    "cat":          None,    # streunt
    "dog":          None,
    "child":        None,    # spielt, wandert
    "wanderer":     None,
    "soldier":      None,
}

# Goal-Wechsel-Cooldown: nach Erreichen wird X Sekunden gewartet bevor neues Goal
GOAL_COOLDOWN_SECONDS = 30

# Wenn NPC nicht in N Ticks dem Goal näher kommt, neues Goal pflanzen (stuck)
MAX_STUCK_TICKS = 8


def _is_friendly_kind(kind: str) -> bool:
    return kind not in combat.CREATURE_KINDS


def _goal_for_phase(npc: dict, phase: str, struct_manager) -> tuple[str, int, int] | None:
    """Bestimmt Goal + Target-Tile für einen NPC basierend auf Tageszeit + Kind.

    Returns (goal_name, x, y) oder None wenn kein passendes Goal — dann wird
    der NPC seinen Random-Wander fortsetzen.
    """
    if not _is_friendly_kind(npc["kind"]):
        return None   # Creatures haben kein Daily-Plan-System

    home_x = npc.get("home_x")
    home_y = npc.get("home_y")

    # Nachts: alle friendly NPCs gehen heim zum Schlafen
    if phase == "night" and home_x is not None and home_y is not None:
        return ("sleep", home_x, home_y)

    # Tagsüber: zur Arbeitsstruktur
    if phase == "day":
        target_type = WORK_STRUCTURE_BY_KIND.get(npc["kind"])
        if target_type is not None:
            target = _find_nearest_structure(struct_manager, npc, target_type, max_dist=25)
            if target is not None:
                return ("work", target["x"], target["y"])

    # Morgens: eat (Feuer/Brunnen) wenn vorhanden
    if phase == "morning":
        for st_type in ("campfire", "cooking_pot", "well"):
            target = _find_nearest_structure(struct_manager, npc, st_type, max_dist=20)
            if target is not None:
                return ("eat", target["x"], target["y"])

    # Abends: socialize — Ziel ist ein anderer NPC in der Nähe (resolved in
    # wander_loop via npc_manager). Wir geben nur die Goal-Markierung zurück
    # ohne x/y — wander_loop pickt selbst einen Nachbarn.
    if phase == "evening":
        # Marker — wander_loop ersetzt die x/y
        return ("socialize", npc["x"], npc["y"])

    return None


def _find_nearest_structure(struct_manager, npc: dict, struct_type: str,
                             max_dist: int = 25) -> dict | None:
    """Findet die nächstgelegene Struktur des gegebenen Typs zum NPC. None
    wenn keine in Reichweite."""
    nx, ny = npc["x"], npc["y"]
    best = None
    best_dist = max_dist + 1
    for s in struct_manager.all():
        if s["type"] != struct_type:
            continue
        d = abs(s["x"] - nx) + abs(s["y"] - ny)
        if d < best_dist:
            best = s
            best_dist = d
    return best


def _find_socialize_partner(npc: dict, npc_manager) -> dict | None:
    """Suche einen anderen friendly NPC in Reichweite zum Plaudern."""
    nx, ny = npc["x"], npc["y"]
    best = None
    best_dist = 16
    for other in npc_manager.all():
        if other["id"] == npc["id"]:
            continue
        if not _is_friendly_kind(other["kind"]):
            continue
        d = abs(other["x"] - nx) + abs(other["y"] - ny)
        if d < best_dist:
            best = other
            best_dist = d
    return best


def pick_goal(npc: dict, struct_manager, npc_manager) -> tuple[str, int, int] | None:
    """High-level entry point: gibt (goal, target_x, target_y) oder None."""
    phase = time_system.clock.phase()
    g = _goal_for_phase(npc, phase, struct_manager)
    if g is None:
        return None
    goal, tx, ty = g
    # Spezialfall socialize: Partner-Lookup
    if goal == "socialize":
        partner = _find_socialize_partner(npc, npc_manager)
        if partner is None:
            return None
        return ("socialize", partner["x"], partner["y"])
    return (goal, tx, ty)


def goal_reached(npc: dict) -> bool:
    """True wenn NPC am Goal-Tile oder direkt daneben ist."""
    if npc.get("_goal_target_x") is None:
        return True
    dx = abs(npc["_goal_target_x"] - npc["x"])
    dy = abs(npc["_goal_target_y"] - npc["y"])
    return (dx + dy) <= 1


def assign_goal(npc: dict, goal: str, x: int, y: int) -> None:
    """Setzt das aktuelle Goal in-place auf dem NPC-Dict (in-memory state)."""
    npc["_goal"] = goal
    npc["_goal_target_x"] = x
    npc["_goal_target_y"] = y
    npc["_goal_stuck_count"] = 0
    npc["_goal_assigned_phase"] = time_system.clock.phase()


def clear_goal(npc: dict) -> None:
    npc["_goal"] = None
    npc["_goal_target_x"] = None
    npc["_goal_target_y"] = None
    npc["_goal_stuck_count"] = 0


def should_repick_goal(npc: dict) -> bool:
    """True wenn das aktuelle Goal nicht mehr gilt (Phase gewechselt, Reached,
    oder Stuck)."""
    if not npc.get("_goal"):
        return True
    # Phase gewechselt?
    if npc.get("_goal_assigned_phase") != time_system.clock.phase():
        return True
    if goal_reached(npc):
        return True
    if npc.get("_goal_stuck_count", 0) >= MAX_STUCK_TICKS:
        return True
    return False


def goal_emoji(goal: str | None) -> str:
    return {
        "sleep":     "💤",
        "work":      "⚒️",
        "eat":       "🍞",
        "socialize": "💬",
    }.get(goal or "", "")
