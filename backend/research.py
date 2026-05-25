"""Research-Tree MVP — Tech-Progression.

Spieler investiert Zeit (Klick = 1 Punkt) in Forschungs-Knoten.
Wenn ein Knoten komplett ist, ist er 'unlocked' — Effekt: andere Knoten freischalten
oder Rezepte aktivieren (Game-Code muss `is_research_done` prüfen)."""

import logging

import db

log = logging.getLogger("liege.research")


RESEARCH_NODES = {
    "smithing_basics": {
        "name":     "Schmiede-Grundlagen",
        "points":   5,
        "prereq":   None,
        "unlocks":  ["iron_sword", "iron_helm"],  # crafting recipes (string-IDs)
        "icon":     "⚒️",
    },
    "smithing_advanced": {
        "name":     "Fortgeschrittene Schmiedekunst",
        "points":   15,
        "prereq":   "smithing_basics",
        "unlocks":  ["mithril_sword", "steel_chestplate"],  # placeholder recipes
        "icon":     "🗡️",
    },
    "alchemy_basics": {
        "name":     "Alchemie-Grundlagen",
        "points":   5,
        "prereq":   None,
        "unlocks":  ["smelt_health", "smelt_mana"],
        "icon":     "⚗️",
    },
    "alchemy_advanced": {
        "name":     "Höhere Alchemie",
        "points":   12,
        "prereq":   "alchemy_basics",
        "unlocks":  ["strength_potion", "speed_potion"],
        "icon":     "🧪",
    },
    "magic_basics": {
        "name":     "Magische Grundlagen",
        "points":   8,
        "prereq":   None,
        "unlocks":  ["scroll_fire", "rune_shield"],
        "icon":     "✨",
    },
    "magic_advanced": {
        "name":     "Höhere Magie",
        "points":   20,
        "prereq":   "magic_basics",
        "unlocks":  ["spell_lightning", "rune_teleport"],
        "icon":     "🔮",
    },
    "agriculture": {
        "name":     "Landwirtschaft",
        "points":   6,
        "prereq":   None,
        "unlocks":  ["wheat_seed", "advanced_farm_plot"],
        "icon":     "🌾",
    },
    "architecture": {
        "name":     "Architektur",
        "points":   8,
        "prereq":   None,
        "unlocks":  ["stone_wall_reinforced", "tower"],
        "icon":     "🏛️",
    },
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS research_progress (
    player_name TEXT NOT NULL,
    node_id     TEXT NOT NULL,
    points      INTEGER NOT NULL DEFAULT 0,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (player_name, node_id)
);
"""


async def get_player_research(player_name: str) -> dict:
    """Returns {node_id: {"points": N, "done": bool}} für alle nodes."""
    rows = await db.pool().fetch(
        "SELECT node_id, points, done FROM research_progress WHERE player_name = $1",
        player_name,
    )
    progress = {r["node_id"]: {"points": r["points"], "done": r["done"]} for r in rows}
    out = {}
    for node_id, cfg in RESEARCH_NODES.items():
        p = progress.get(node_id, {"points": 0, "done": False})
        # Available wenn prereq done oder kein prereq
        prereq = cfg["prereq"]
        available = (
            prereq is None
            or progress.get(prereq, {}).get("done", False)
        )
        out[node_id] = {
            "name":      cfg["name"],
            "icon":      cfg["icon"],
            "points":    p["points"],
            "points_max": cfg["points"],
            "done":      p["done"],
            "available": available,
            "prereq":    prereq,
            "unlocks":   cfg["unlocks"],
        }
    return out


async def invest(player_name: str, node_id: str, points: int = 1) -> dict | None:
    """Spieler investiert points in einen Knoten. Returns updated state oder None."""
    cfg = RESEARCH_NODES.get(node_id)
    if cfg is None:
        return None
    # Check prereq
    if cfg["prereq"]:
        prereq_done = await db.pool().fetchrow(
            "SELECT done FROM research_progress "
            "WHERE player_name = $1 AND node_id = $2",
            player_name, cfg["prereq"],
        )
        if not (prereq_done and prereq_done["done"]):
            return None
    # Upsert
    row = await db.pool().fetchrow(
        "INSERT INTO research_progress (player_name, node_id, points, done) "
        "VALUES ($1, $2, $3, FALSE) "
        "ON CONFLICT (player_name, node_id) DO UPDATE "
        "SET points = LEAST(research_progress.points + $3, $4), "
        "    done = (research_progress.points + $3 >= $4) "
        "RETURNING points, done",
        player_name, node_id, points, cfg["points"],
    )
    return {
        "node_id":    node_id,
        "points":     row["points"],
        "points_max": cfg["points"],
        "done":       row["done"],
        "unlocks":    cfg["unlocks"] if row["done"] else [],
    }


async def is_unlocked(player_name: str, unlock_key: str) -> bool:
    """Prüft ob ein Spieler einen unlock-key (z.B. Recipe-ID) freigeschaltet hat."""
    rows = await db.pool().fetch(
        "SELECT node_id FROM research_progress "
        "WHERE player_name = $1 AND done = TRUE",
        player_name,
    )
    for r in rows:
        node = RESEARCH_NODES.get(r["node_id"])
        if node and unlock_key in node["unlocks"]:
            return True
    return False
