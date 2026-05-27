"""Ground-Item-Spawner: legt Ressourcen rund um aktive Spieler ab.

Welle 23 — Drop-Design-Refactor:
- Equipment + Magic-Items spawnen NIE mehr direkt im Gras. Die kommen nur
  noch aus Chests (chest_loot.py) oder Boss-Drops (loot.py).
- Pro Tile-Biome eigene Spawn-Tabelle: Wald → Holz/Pilze, Berg → Stein/Erze,
  Wiese → Kräuter, Wasser/Lava-Tiles werden übersprungen.
- Sehr seltene Consumables (Health/Mana-Potion ~1%) als Notfall-Drop sind
  weiterhin erlaubt, aber kein Equipment.
"""
import asyncio
import logging
import math as _math
import os
import random

log = logging.getLogger("liege.item_worker")

ITEM_SPAWN_INTERVAL_SECONDS = int(os.environ.get("ITEM_SPAWN_INTERVAL_SECONDS", "60"))
ITEM_SPAWN_MAX = int(os.environ.get("ITEM_SPAWN_MAX", "30"))

# Tile-ID-Mapping (passend zu world.py):
#   0 water, 1 sand, 2 grass, 3 forest, 4 mountain, 5 desert,
#   6 jungle, 7 lava, 8 snow, 9 swamp
TILE_WATER, TILE_SAND, TILE_GRASS, TILE_FOREST, TILE_MOUNTAIN = 0, 1, 2, 3, 4
TILE_DESERT, TILE_JUNGLE, TILE_LAVA, TILE_SNOW, TILE_SWAMP = 5, 6, 7, 8, 9

# Spawn-Tabellen pro Biome — Equipment & Magic explizit AUSGESCHLOSSEN.
# Schema: [(item_kind, weight), ...]
SPAWN_TABLE_BY_BIOME: dict[int, list[tuple[str, int]]] = {
    TILE_FOREST: [
        ("wood", 35), ("herb", 20), ("mushroom_food", 15), ("plant_fiber", 10),
        ("bone", 6), ("leather", 4), ("berries", 8), ("raw_meat", 2),
        ("health_potion", 1),  # sehr selten
    ],
    TILE_GRASS: [
        ("herb", 28), ("plant_fiber", 20), ("wood", 12), ("bone", 8),
        ("berries", 12), ("apple", 6), ("strawberry", 4), ("raw_meat", 3),
        ("health_potion", 1),
    ],
    TILE_MOUNTAIN: [
        ("stone", 35), ("iron_ore", 18), ("copper_ingot", 8), ("silver_ore", 10),
        ("gold_ore", 5), ("crystal", 4), ("mythril_ore", 1), ("bone", 5),
        ("herb", 3),
    ],
    TILE_DESERT: [
        ("stone", 28), ("bone", 18), ("gold_ore", 8), ("crystal", 6),
        ("herb", 6), ("silver_ore", 4), ("cloth", 4),
    ],
    TILE_JUNGLE: [
        ("wood", 28), ("herb", 22), ("plant_fiber", 15), ("mushroom_food", 10),
        ("leather", 6), ("berries", 8), ("bone", 4), ("cloth", 3),
        ("mana_potion", 1),
    ],
    TILE_SWAMP: [
        ("herb", 28), ("mushroom_food", 18), ("bone", 18), ("plant_fiber", 10),
        ("cloth", 8), ("crystal", 4), ("mana_potion", 2),
    ],
    TILE_SNOW: [
        ("bone", 22), ("leather", 18), ("herb", 12), ("wood", 8),
        ("crystal", 4), ("mythril_ore", 2), ("raw_meat", 6),
        ("health_potion", 1),
    ],
    TILE_SAND: [
        ("stone", 18), ("bone", 15), ("herb", 6), ("cloth", 4),
    ],
    TILE_LAVA: [
        # Lava: nur seltene, hochwertige Ressourcen (kein Holz/Pflanzen)
        ("crystal", 15), ("gold_ore", 8), ("mythril_ore", 4),
        ("fire_resist_potion", 1),
    ],
}

# Biomes wo wir KEIN Item spawnen wollen (Wasser etc.)
NO_SPAWN_BIOMES = {TILE_WATER}


def _pick_kind_for_biome(biome: int, rng: random.Random | None = None) -> str | None:
    """Wählt gewichtet ein Kind aus dem Biome-Pool. None wenn Biome unbekannt."""
    table = SPAWN_TABLE_BY_BIOME.get(biome)
    if not table:
        return None
    r = rng or random
    items, weights = zip(*table)
    return r.choices(items, weights=weights, k=1)[0]


async def _find_spawn_position(world, connection_manager) -> tuple[int, int, int] | None:
    """Sucht walkable Tile in Spielernähe. Returns (x, y, biome_id) oder None."""
    center_x, center_y = 60, 40
    players = connection_manager.get_players()
    if players:
        p = random.choice(list(players.values()))
        center_x, center_y = p["x"], p["y"]
    for _ in range(50):
        angle = random.random() * 6.283
        dist = random.randint(3, 20)
        x = center_x + int(_math.cos(angle) * dist)
        y = center_y + int(_math.sin(angle) * dist)
        if not await world.is_walkable(x, y):
            continue
        biome = await world.tile_at(x, y)
        if biome in NO_SPAWN_BIOMES:
            continue
        return x, y, biome
    return None


async def run(world, item_manager, connection_manager) -> None:
    """Periodisches Spawning von biome-passenden Items auf der Welt."""
    log.info("Item-Worker startet (intervall=%ss, biome-aware)",
             ITEM_SPAWN_INTERVAL_SECONDS)
    await asyncio.sleep(20)  # Anlaufzeit
    while True:
        try:
            await asyncio.sleep(ITEM_SPAWN_INTERVAL_SECONDS)
            current = await item_manager.get_on_ground()
            if len(current) >= ITEM_SPAWN_MAX:
                continue
            pos = await _find_spawn_position(world, connection_manager)
            if pos is None:
                continue
            x, y, biome = pos
            kind = _pick_kind_for_biome(biome)
            if kind is None:
                continue
            item = await item_manager.spawn_on_ground(kind, x, y)
            if item is not None:
                await connection_manager.broadcast({
                    "type": "item_spawned",
                    "item": item,
                })
                log.info("Item gespawnt: %s @ (%d, %d) biome=%d",
                         kind, x, y, biome)
        except asyncio.CancelledError:
            log.info("Item-Worker gestoppt")
            raise
        except Exception:
            log.exception("Item-Worker-Iteration fehlgeschlagen")
