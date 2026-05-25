"""Dungeon-Instanzen-Manager — Welle 9b.

Persistierte Dungeon-Instanzen pro Stair-Position. Beim ersten Betreten
wird ein Dungeon generiert + Mobs gespawnt; bei späteren Besuchen wird
die gleiche Instanz wiedergeöffnet.

Player-State im DB-Feld players.world_id (Werte: 'overworld' oder 'dungeon:<id>')
und players.overworld_x/y für Rückkehr.
"""
import json
import logging
import random

import db
import dungeon_world
import dungeon_themes

log = logging.getLogger("liege.dungeon_instance")


async def get_or_create_dungeon(stair_x: int, stair_y: int) -> dict:
    """Lädt vorhandenen Dungeon an dieser Stair-Position oder generiert einen neuen."""
    # Stair-Position als Seed-Source
    seed = (stair_x * 73856093) ^ (stair_y * 19349663)
    seed = seed & 0x7FFFFFFF  # 31-bit
    row = await db.pool().fetchrow(
        "SELECT id, seed, name, size, tiles, spawn_x, spawn_y FROM dungeons "
        "WHERE seed = $1",
        seed,
    )
    if row:
        tiles = row["tiles"]
        if isinstance(tiles, str):
            tiles = json.loads(tiles)
        return {
            "id": row["id"], "seed": row["seed"], "name": row["name"],
            "size": row["size"], "tiles": tiles,
            "spawn_x": row["spawn_x"], "spawn_y": row["spawn_y"],
            "theme": (row["name"] or "").split(":")[-1] if ":" in (row["name"] or "") else None,
        }

    # Generieren
    theme = dungeon_themes.pick_theme_for_seed(seed)
    layout = dungeon_world.generate(seed, theme=theme)
    name = f"{dungeon_themes.THEMES[theme]['label']}:{theme}"
    row = await db.pool().fetchrow(
        "INSERT INTO dungeons (seed, name, size, tiles, spawn_x, spawn_y) "
        "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
        seed, name, layout["size"], json.dumps(layout["tiles"]),
        layout["spawn"][0], layout["spawn"][1],
    )
    log.info("Dungeon erzeugt: seed=%d theme=%s id=%d", seed, theme, row["id"])
    return {
        "id": row["id"], "seed": seed, "name": name,
        "size": layout["size"], "tiles": layout["tiles"],
        "spawn_x": layout["spawn"][0], "spawn_y": layout["spawn"][1],
        "theme": theme,
    }


async def enter_dungeon(player_name: str, stair_x: int, stair_y: int,
                         overworld_x: int, overworld_y: int) -> dict:
    """Setzt Player auf dungeon. Returns Dungeon-Daten + spawn-Position."""
    dungeon = await get_or_create_dungeon(stair_x, stair_y)
    world_id = f"dungeon:{dungeon['id']}"
    await db.pool().execute(
        "UPDATE players SET world_id = $1, x = $2, y = $3, "
        "overworld_x = $4, overworld_y = $5 WHERE name = $6",
        world_id, dungeon["spawn_x"], dungeon["spawn_y"],
        overworld_x, overworld_y, player_name,
    )
    return dungeon


async def exit_dungeon(player_name: str) -> tuple[int, int] | None:
    """Setzt Player zurück auf Overworld an alter Position. Returns (x,y) oder None."""
    row = await db.pool().fetchrow(
        "SELECT overworld_x, overworld_y FROM players WHERE name = $1",
        player_name,
    )
    if not row or row["overworld_x"] is None:
        return None
    x = row["overworld_x"]
    y = row["overworld_y"]
    await db.pool().execute(
        "UPDATE players SET world_id = 'overworld', x = $1, y = $2, "
        "overworld_x = NULL, overworld_y = NULL WHERE name = $3",
        x, y, player_name,
    )
    return (x, y)


async def get_player_world(player_name: str) -> str:
    row = await db.pool().fetchrow(
        "SELECT world_id FROM players WHERE name = $1", player_name,
    )
    return row["world_id"] if row and row["world_id"] else "overworld"


def is_walkable_tile(tile_id: int) -> bool:
    return dungeon_world.is_walkable_tile(tile_id)


def tile_at(dungeon_tiles: list, x: int, y: int) -> int:
    size = len(dungeon_tiles)
    if not (0 <= x < size and 0 <= y < size):
        return dungeon_world.WALL
    return dungeon_tiles[y][x]
