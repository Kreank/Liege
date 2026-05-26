"""Welt mit natürlichen Strukturen befüllen.

Pro Chunk: prüft Settlement-Area-Maske (lässt Bauplätze leer), nutzt
Fertility + Resource-Density-Maps für realistischere Cluster."""

import logging
import random

import db
import harvest as harvest_module
from world import CHUNK_SIZE

log = logging.getLogger("liege.world_populator")

# Tile-IDs (synchron mit world.py)
WATER, SAND, GRASS, FOREST, MOUNTAIN = 0, 1, 2, 3, 4
DESERT, JUNGLE, LAVA, SNOW, SWAMP = 5, 6, 7, 8, 9

# Pro Biome: [(prop_type, base_chance, density_kind)]
# base_chance ist Basis-Würfelchance pro Tile. Wird mit density modifiziert.
# density_kind verweist auf welche resource-density-Map die Chance modifiziert.
BIOME_SPAWNS = {
    GRASS: [
        ("tall_grass",  0.06, "plant"),
        ("flowers",     0.025, "plant"),
        ("bush",        0.020, "plant"),
        ("rock_small",  0.008, "rock"),
        ("mushrooms",   0.006, "plant"),
        ("tree_oak",    0.012, "tree"),
    ],
    FOREST: [
        ("tree_oak",    0.10,  "tree"),
        ("tree_pine",   0.08,  "tree"),
        ("tree_dead",   0.015, "tree"),
        ("tree_stump",  0.012, "tree"),
        ("fallen_log",  0.010, "tree"),
        ("bush",        0.018, "plant"),
        ("mushrooms",   0.015, "plant"),
        ("rock_mossy",  0.008, "rock"),
    ],
    MOUNTAIN: [
        # MOUNTAIN ist non-walkable — nichts spawnt drauf
    ],
    SAND: [
        ("rock_small",  0.010, "rock"),
        ("rubble",      0.003, "ruin"),
    ],
    DESERT: [
        ("rock_small",  0.012, "rock"),
        ("tree_dead",   0.008, "tree"),
        ("statue_broken", 0.0015, "ruin"),
        ("bones_scatter", 0.005, "ruin"),
        ("gravestone",  0.002, "ruin"),
        # Welle 12 — Wüsten-Props
        ("cactus",       0.020, "plant"),
        ("desert_skull", 0.004, "ruin"),
        ("dry_bush",     0.015, "plant"),
    ],
    JUNGLE: [
        ("tree_oak",    0.07,  "tree"),
        ("tree_pine",   0.06,  "tree"),
        ("bush",        0.040, "plant"),
        ("flowers",     0.025, "plant"),
        ("mushrooms",   0.025, "plant"),
        ("tall_grass",  0.030, "plant"),
        # Welle 12 — Dschungel-Props
        ("palm_tree",     0.035, "tree"),
        ("jungle_flower", 0.030, "plant"),
        ("jungle_vines",  0.022, "plant"),
    ],
    SNOW: [
        ("tree_pine",   0.04,  "tree"),
        ("rock_small",  0.015, "rock"),
        ("tree_dead",   0.010, "tree"),
        ("gravestone",  0.002, "ruin"),
        # Welle 12 — Schnee-Props
        ("frozen_bush",  0.020, "plant"),
        ("ice_crystal",  0.008, "rock"),
        ("snow_rock",    0.018, "rock"),
    ],
    SWAMP: [
        ("reeds",       0.060, "plant"),
        ("lily_pads",   0.025, "plant"),
        ("tree_dead",   0.020, "tree"),
        ("mushrooms",   0.020, "plant"),
        ("tall_grass",  0.025, "plant"),
        ("bones_scatter", 0.004, "ruin"),
        # Welle 12 — Sumpf-Props
        ("swamp_bubbles", 0.015, "plant"),
        ("swamp_log",     0.018, "tree"),
    ],
}

# Wasser-Adjacent (nur in walkable tiles direkt am Wasser) — feature aktuell nicht implementiert,
# aber Boote/Stege könnten so platziert werden

# Sehr seltene Welt-Highlights (für alle walkable land-biome)
RARE_SCATTER = [
    ("ruin_pillar",   0.0003, "ruin"),
    ("broken_cart",   0.0005, "ruin"),
    ("camp_tent",     0.0007, "ruin"),  # verlassener Camp
    ("cooking_pot",   0.0005, "ruin"),  # Lager-Reste
    ("fence",         0.0008, "ruin"),  # Zaun-Fragment
    ("barrel",        0.0005, "ruin"),
    ("crate",         0.0005, "ruin"),
]

# Wasser-Adjacent: nur auf SAND-Tiles die an WATER grenzen
WATERSIDE_SCATTER = [
    ("dock_straight", 0.04,  "ruin"),
    ("driftwood",     0.06,  "tree"),
    ("anchor",        0.012, "ruin"),
    ("fishing_net",   0.020, "ruin"),
]

# Auf WATER-Tiles: nur Wasser-Strukturen
WATER_SCATTER = [
    ("shipwreck",     0.0015, "ruin"),
    ("boat_small",    0.0008, "ruin"),
    ("lily_pads",     0.008,  "plant"),
]


def _is_water_adjacent(world, x: int, y: int) -> bool:
    """True wenn mindestens 1 Nachbar-Tile WATER ist."""
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        if world.tile_at_sync(x + dx, y + dy) == WATER:
            return True
    return False

# Density-Modifier: chance *= (0.4 + density * 1.5)
# d=0.0 → 0.4x, d=0.5 → 1.15x, d=1.0 → 1.9x
def _density_mod(d: float) -> float:
    return 0.4 + d * 1.5


def _pick_for_tile(world, x: int, y: int, tile_id: int) -> str | None:
    """Wählt Deko basierend auf Biome + Density-Maps.
    Wasser-spezifische Strukturen werden separat in populate_chunk gehandhabt."""
    biome = BIOME_SPAWNS.get(tile_id, [])
    fertility = world.fertility(x, y)
    for prop_type, base, density_kind in biome:
        density = world.resource_density(x, y, density_kind)
        adjusted = base * _density_mod(density) * (0.7 + fertility * 0.6)
        if random.random() < adjusted:
            return prop_type
    # Wasser-Adjacent (nur auf SAND-Tiles direkt an Wasser)
    if tile_id == SAND and _is_water_adjacent(world, x, y):
        for prop_type, chance, density_kind in WATERSIDE_SCATTER:
            density = world.resource_density(x, y, density_kind)
            if random.random() < chance * _density_mod(density):
                return prop_type
    # Rare scatter über alle land-biome
    for prop_type, chance, density_kind in RARE_SCATTER:
        density = world.resource_density(x, y, density_kind)
        if random.random() < chance * _density_mod(density):
            return prop_type
    return None


def _pick_for_water(world, x: int, y: int) -> str | None:
    """Picks aus WATER_SCATTER (Schiffswrack, Boot, Seerosen)."""
    for prop_type, chance, density_kind in WATER_SCATTER:
        density = world.resource_density(x, y, density_kind)
        if random.random() < chance * _density_mod(density):
            return prop_type
    return None


async def populate_chunk_if_needed(world, structure_manager, connection_manager,
                                    cx: int, cy: int, npc_manager=None) -> int:
    """Populiert einen Chunk wenn populated=False. Setzt Flag in DB.

    Wenn npc_manager mitgegeben wird, kann das Befüllen auch Dörfer/Räuber-Lager
    auslösen (Welle 8)."""
    row = await db.pool().fetchrow(
        "SELECT populated FROM world_chunks WHERE world_seed = $1 "
        "AND chunk_x = $2 AND chunk_y = $3",
        world.seed, cx, cy,
    )
    if row is None or row["populated"]:
        return 0
    chunk = await world.get_chunk(cx, cy)
    placed_list = []
    for ly in range(CHUNK_SIZE):
        for lx in range(CHUNK_SIZE):
            wx = cx * CHUNK_SIZE + lx
            wy = cy * CHUNK_SIZE + ly
            tile = chunk[ly][lx]
            # MOUNTAIN und LAVA sind komplett strukturlos
            if tile in (MOUNTAIN, LAVA):
                continue
            # Settlement-Area: garantiert frei für Bauen
            if world.is_settlement_area(wx, wy):
                continue
            if structure_manager.at(wx, wy) is not None:
                continue
            # WATER bekommt eigene Scatter-Logik (Schiffswrack, Boot, Lily-Pads)
            if tile == WATER:
                chosen = _pick_for_water(world, wx, wy)
                if chosen is None:
                    continue
                dur = harvest_module.initial_durability(chosen)
                placed_struct = await structure_manager.place(
                    wx, wy, chosen, "system", material="wood", durability=dur,
                )
                if placed_struct is not None:
                    placed_list.append(placed_struct)
                continue
            chosen = _pick_for_tile(world, wx, wy, tile)
            if chosen is None:
                continue
            dur = harvest_module.initial_durability(chosen)
            placed_struct = await structure_manager.place(
                wx, wy, chosen, "system", material="stone", durability=dur
            )
            if placed_struct is not None:
                placed_list.append(placed_struct)
    # Broadcast nur wenn jemand connected ist (sonst zu viel Traffic für niemanden)
    if placed_list and connection_manager.get_players():
        for s in placed_list:
            await connection_manager.broadcast({
                "type": "structure_placed", "structure": s,
            })
    await db.pool().execute(
        "UPDATE world_chunks SET populated = TRUE WHERE world_seed = $1 "
        "AND chunk_x = $2 AND chunk_y = $3",
        world.seed, cx, cy,
    )
    if placed_list:
        log.info("Chunk (%d,%d) populiert: %d Strukturen", cx, cy, len(placed_list))

    # Welle 8: Dörfer und Räuber-Lager nach normaler Befüllung
    if npc_manager is not None:
        try:
            import village_spawner
            await village_spawner.try_spawn_village(
                world, structure_manager, npc_manager, connection_manager, cx, cy,
            )
            await village_spawner.try_spawn_bandit_camp(
                world, structure_manager, npc_manager, connection_manager, cx, cy,
            )
        except Exception:
            log.exception("village_spawner schlug fehl bei (%d,%d)", cx, cy)
    return len(placed_list)
