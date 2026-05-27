"""Research-Tree MVP — Tech-Progression.

Spieler investiert Zeit (Klick = 1 Punkt) in Forschungs-Knoten.
Wenn ein Knoten komplett ist, ist er 'unlocked' — Effekt: andere Knoten freischalten
oder Rezepte aktivieren (Game-Code muss `is_research_done` prüfen)."""

import logging

import db

log = logging.getLogger("liege.research")


RESEARCH_NODES = {
    # ── Schmiede-Linie (3 Stufen) ──────────────────────────────────────────
    "smithing_basics": {
        "name":     "Schmiede-Grundlagen",
        "desc":     "Eisen schmelzen + einfache Eisenwaffen/-rüstung",
        "points":   5, "prereq": None,
        "unlocks":  ["smelt_iron", "iron_sword", "iron_axe", "iron_helm",
                     "iron_chest", "iron_shield", "iron_boots"],
        "icon":     "⚒️",
    },
    "smithing_advanced": {
        "name":     "Fortgeschrittene Schmiedekunst",
        "desc":     "Stahl + Silber",
        "points":   15, "prereq": "smithing_basics",
        "unlocks":  ["smelt_steel", "smelt_silver",
                     "steel_sword", "steel_chest",
                     "silver_sword", "silver_helm",
                     "make_pickaxe", "make_hammer", "make_shovel", "make_hoe"],
        "icon":     "🗡️",
    },
    "mastersmithing": {
        "name":     "Meister-Schmiedekunst",
        "desc":     "Gold und Mithril — Endgame-Equipment",
        "points":   30, "prereq": "smithing_advanced",
        "unlocks":  ["smelt_gold", "smelt_mithril",
                     "gold_helm", "gold_chest",
                     "mithril_sword", "mithril_chest"],
        "icon":     "👑",
    },
    # ── Alchemie-Linie ─────────────────────────────────────────────────────
    "alchemy_basics": {
        "name":     "Alchemie-Grundlagen",
        "desc":     "Heil- und Manatränke brauen",
        "points":   5, "prereq": None,
        "unlocks":  ["brew_health", "brew_mana"],
        "icon":     "⚗️",
    },
    "alchemy_advanced": {
        "name":     "Höhere Alchemie",
        "desc":     "Spezielle Tränke (Stärke, Schnelligkeit)",
        "points":   12, "prereq": "alchemy_basics",
        "unlocks":  [],   # Platzhalter — neue Trank-Rezepte hier dazu
        "icon":     "🧪",
    },
    "alchemy_mastery": {
        "name":     "Alchemie-Meisterschaft",
        "desc":     "Mythische Tränke und Elixiere",
        "points":   25, "prereq": "alchemy_advanced",
        "unlocks":  [],
        "icon":     "🌟",
    },
    # ── Magie-Linie ────────────────────────────────────────────────────────
    "magic_basics": {
        "name":     "Magische Grundlagen",
        "desc":     "Einfache Schriftrollen und Runen",
        "points":   8, "prereq": None,
        "unlocks":  [],   # spell_book/scroll/rune Crafting kommt später
        "icon":     "✨",
    },
    "magic_advanced": {
        "name":     "Höhere Magie",
        "desc":     "Stärkere Zauber",
        "points":   20, "prereq": "magic_basics",
        "unlocks":  [],
        "icon":     "🔮",
    },
    "magic_mastery": {
        "name":     "Arkane Meisterschaft",
        "desc":     "Welt-bewegende Magie",
        "points":   40, "prereq": "magic_advanced",
        "unlocks":  [],
        "icon":     "🌌",
    },
    # ── Landwirtschaft ─────────────────────────────────────────────────────
    "agriculture": {
        "name":     "Landwirtschaft",
        "desc":     "Brot backen, gekochte Mahlzeiten",
        "points":   6, "prereq": None,
        "unlocks":  ["bake_bread", "cook_meat", "cook_fish"],
        "icon":     "🌾",
    },
    "advanced_agriculture": {
        "name":     "Fortgeschrittene Landwirtschaft",
        "desc":     "Bessere Erträge, neue Pflanzen",
        "points":   15, "prereq": "agriculture",
        "unlocks":  [],
        "icon":     "🌻",
    },
    # ── Architektur ────────────────────────────────────────────────────────
    "architecture": {
        "name":     "Architektur",
        "desc":     "Spezielle Bauten",
        "points":   8, "prereq": None,
        "unlocks":  [],
        "icon":     "🏛️",
    },
    "advanced_architecture": {
        "name":     "Festungs-Architektur",
        "desc":     "Verstärkte Mauern, Türme",
        "points":   20, "prereq": "architecture",
        "unlocks":  [],
        "icon":     "🏰",
    },
}


async def is_node_done(player_name: str, node_id: str) -> bool:
    """Welle 22: prüft ob ein bestimmter Forschungs-Knoten abgeschlossen ist."""
    row = await db.pool().fetchrow(
        "SELECT done FROM research_progress "
        "WHERE player_name = $1 AND node_id = $2",
        player_name, node_id,
    )
    return bool(row and row["done"])


SCHEMA = """
CREATE TABLE IF NOT EXISTS research_progress (
    player_name TEXT NOT NULL,
    node_id     TEXT NOT NULL,
    points      INTEGER NOT NULL DEFAULT 0,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (player_name, node_id)
);
"""


async def get_pool(player_name: str) -> int:
    row = await db.pool().fetchrow(
        "SELECT research_pool FROM players WHERE name = $1", player_name,
    )
    return int(row["research_pool"]) if row else 0


async def award_points(player_name: str, n: int, reason: str = "") -> int:
    """Welle 22: addiert n Forschungspunkte in den Pool des Spielers.
    Returns neuer Pool-Stand. Reason ist nur fürs Logging."""
    if n <= 0:
        return await get_pool(player_name)
    row = await db.pool().fetchrow(
        "UPDATE players SET research_pool = research_pool + $1 "
        "WHERE name = $2 RETURNING research_pool",
        n, player_name,
    )
    if row is None:
        return 0
    log.debug("research_pool %s += %d (%s) → %d", player_name, n, reason, row["research_pool"])
    return int(row["research_pool"])


async def get_player_research(player_name: str) -> dict:
    """Returns {nodes: {node_id: {...}}, pool: N}. Pool wird mit
    zurückgegeben damit Frontend ihn anzeigen kann."""
    rows = await db.pool().fetch(
        "SELECT node_id, points, done FROM research_progress WHERE player_name = $1",
        player_name,
    )
    progress = {r["node_id"]: {"points": r["points"], "done": r["done"]} for r in rows}
    nodes = {}
    for node_id, cfg in RESEARCH_NODES.items():
        p = progress.get(node_id, {"points": 0, "done": False})
        prereq = cfg["prereq"]
        available = (
            prereq is None
            or progress.get(prereq, {}).get("done", False)
        )
        nodes[node_id] = {
            "name":      cfg["name"],
            "icon":      cfg["icon"],
            "points":    p["points"],
            "points_max": cfg["points"],
            "done":      p["done"],
            "available": available,
            "prereq":    prereq,
            "unlocks":   cfg["unlocks"],
        }
    return {"nodes": nodes, "pool": await get_pool(player_name)}


async def invest(player_name: str, node_id: str, points: int = 1) -> dict | None:
    """Spieler investiert points in einen Knoten — verbraucht Pool-Punkte.
    Returns updated state oder None. Wenn nicht genug Pool: 'error': 'not_enough_points'."""
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
    # Welle 22: Pool-Check + Decrement (atomar)
    pool_row = await db.pool().fetchrow(
        "UPDATE players SET research_pool = research_pool - $1 "
        "WHERE name = $2 AND research_pool >= $1 "
        "RETURNING research_pool",
        points, player_name,
    )
    if pool_row is None:
        return {"error": "not_enough_points", "pool": await get_pool(player_name)}
    new_pool = int(pool_row["research_pool"])
    # Investiere in Node
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
        "pool":       new_pool,
    }


# ─── Time-Tick Worker (Welle 22) ────────────────────────────────────────────
async def time_tick_loop(connection_manager) -> None:
    """Alle TICK Sekunden bekommt jeder online-Spieler +TICK_POINTS Pool-Punkte.
    Belohnt aktive Online-Zeit auch bei idle."""
    import asyncio
    import os
    tick_seconds = int(os.environ.get("RESEARCH_TICK_SECONDS", "300"))    # 5 min
    tick_points  = int(os.environ.get("RESEARCH_TICK_POINTS", "1"))
    log.info("Research-Tick-Loop startet (alle %ds +%d Pool)",
             tick_seconds, tick_points)
    while True:
        try:
            await asyncio.sleep(tick_seconds)
            for name in list(connection_manager.get_players().keys()):
                new_pool = await award_points(name, tick_points, "time_tick")
                ws = connection_manager.connections.get(name)
                if ws is not None:
                    try:
                        await ws.send_json({
                            "type": "research_pool_update",
                            "pool": new_pool,
                            "gained": tick_points,
                            "reason": "🕐 Zeit",
                        })
                    except Exception:
                        pass
        except asyncio.CancelledError:
            log.info("Research-Tick-Loop gestoppt")
            raise
        except Exception:
            log.exception("Research-Tick-Loop Iteration fehlgeschlagen")


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
