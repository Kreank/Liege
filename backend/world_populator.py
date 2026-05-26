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


# Pflanzen/Gras-Filler die als Ambient auch außerhalb von Sites Sinn ergeben.
# Trees/Rocks/Ruinen kommen NUR über Encounter-Templates — die sollen nicht
# einzeln im Nirgendwo stehen.
AMBIENT_PROPS_BY_BIOME = {
    GRASS:  [("tall_grass", 0.025), ("flowers", 0.010), ("bush", 0.008)],
    FOREST: [("tall_grass", 0.030), ("bush", 0.012), ("flowers", 0.008)],
    DESERT: [("dry_bush", 0.010), ("desert_skull", 0.002)],
    JUNGLE: [("tall_grass", 0.030), ("jungle_flower", 0.015),
             ("jungle_vines", 0.012)],
    SWAMP:  [("reeds", 0.025), ("lily_pads", 0.012), ("tall_grass", 0.015)],
    SNOW:   [("frozen_bush", 0.010)],
    SAND:   [],  # plus WATERSIDE für küsten-Sand
}


def _pick_ambient(world, x: int, y: int, tile_id: int) -> str | None:
    """Sparsamer Ambient-Roll: nur Gras/Blumen/Sträucher als einzelne Tiles.
    Bäume, Felsen und größere Strukturen werden ausschließlich über
    Encounter-Templates platziert."""
    fertility = world.fertility(x, y)
    for prop_type, base in AMBIENT_PROPS_BY_BIOME.get(tile_id, []):
        if random.random() < base * (0.6 + fertility * 0.6):
            return prop_type
    # Wasser-Adjacent Sand bekommt seltene Coast-Props auch außerhalb von Sites
    if tile_id == SAND and _is_water_adjacent(world, x, y):
        for prop_type, chance, density_kind in WATERSIDE_SCATTER:
            density = world.resource_density(x, y, density_kind)
            if random.random() < chance * _density_mod(density) * 0.4:
                return prop_type
    return None


def _pick_for_water(world, x: int, y: int) -> str | None:
    """Picks aus WATER_SCATTER (Schiffswrack, Boot, Seerosen)."""
    for prop_type, chance, density_kind in WATER_SCATTER:
        density = world.resource_density(x, y, density_kind)
        if random.random() < chance * _density_mod(density):
            return prop_type
    return None


# ─── Encounter-Templates ──────────────────────────────────────────────────────
# "Sites" sind kohärente Sets von Strukturen die zusammen Sinn ergeben:
# Bäume in Gruppen, Zelt mit Lagerfeuer, Ruinen-Komplex, etc.
#   placements: liste von (dx, dy, prop_type)
#   biomes:     erlaubte Tile-IDs für den Ankerpunkt
#   weight:     Auswahl-Gewicht beim Roll
#   spread:     Radius für Filler-Props um den Anker
#   fillers:    Liste (prop_type, chance) für zufällige extra-Props im spread
ENCOUNTER_TEMPLATES = {
    # Wäldchen: dichter Baumcluster mit Unterwuchs
    "forest_grove": {
        "biomes": {GRASS, FOREST, JUNGLE},
        "weight": 6,
        "spread": 4,
        "placements": [
            (0, 0, "tree_oak"),
            (1, 0, "tree_oak"),
            (-1, 0, "tree_pine"),
            (0, 1, "tree_pine"),
            (2, 1, "tree_oak"),
            (-1, 2, "tree_dead"),
            (1, -2, "tree_oak"),
        ],
        "fillers": [("bush", 0.25), ("mushrooms", 0.15), ("tall_grass", 0.20),
                    ("flowers", 0.10), ("rock_mossy", 0.05)],
    },
    # Pilz-Hain
    "mushroom_patch": {
        "biomes": {FOREST, SWAMP, JUNGLE},
        "weight": 3,
        "spread": 3,
        "placements": [
            (0, 0, "mushrooms"),
            (1, 0, "mushrooms"),
            (0, 1, "mushrooms"),
            (-1, 1, "mushrooms"),
        ],
        "fillers": [("mushrooms", 0.25), ("bush", 0.10), ("tall_grass", 0.15)],
    },
    # Steinhaufen — basis für Erz-Abbau
    "rock_outcrop": {
        "biomes": {GRASS, DESERT, SNOW, FOREST},
        "weight": 4,
        "spread": 3,
        "placements": [
            (0, 0, "rock_large"),
            (1, 0, "rock_small"),
            (-1, 0, "rock_small"),
            (0, 1, "rock_small"),
        ],
        "fillers": [("rock_small", 0.20), ("rubble", 0.10)],
    },
    # Verlassenes Camp — Zelt + Lagerfeuer + Versorgung
    "abandoned_camp": {
        "biomes": {GRASS, FOREST, DESERT, SNOW},
        "weight": 1,
        "spread": 3,
        "placements": [
            (0, 0, "camp_tent"),
            (1, 0, "campfire"),       # Lagerfeuer direkt neben Zelt
            (-1, 0, "cooking_pot"),
            (2, 1, "barrel"),
            (-1, -1, "crate"),
        ],
        "fillers": [("sack", 0.15), ("driftwood", 0.10)],
    },
    # Ruinen-Komplex
    "ancient_ruin": {
        "biomes": {GRASS, DESERT, SNOW},
        "weight": 2,
        "spread": 4,
        "placements": [
            (0, 0, "statue_broken"),
            (2, 0, "ruin_pillar"),
            (-2, 0, "ruin_pillar"),
            (0, 2, "ruin_pillar"),
            (1, 1, "rubble"),
            (-1, 1, "rubble"),
            (0, -2, "gravestone"),
        ],
        "fillers": [("rubble", 0.25), ("bones_scatter", 0.10)],
    },
    # Friedhof
    "graveyard": {
        "biomes": {SWAMP, DESERT, GRASS},
        "weight": 1,
        "spread": 3,
        "placements": [
            (0, 0, "gravestone"),
            (1, 0, "gravestone"),
            (-1, 0, "gravestone"),
            (0, 1, "gravestone"),
            (1, 1, "rubble"),
        ],
        "fillers": [("gravestone", 0.20), ("bones_scatter", 0.20),
                    ("ruin_pillar", 0.08)],
    },
    # Wüsten-Knochenfund
    "bone_field": {
        "biomes": {DESERT},
        "weight": 2,
        "spread": 3,
        "placements": [
            (0, 0, "bones_scatter"),
            (1, 0, "desert_skull"),
            (-1, 0, "bones_scatter"),
            (0, 1, "dry_bush"),
        ],
        "fillers": [("bones_scatter", 0.25), ("dry_bush", 0.20)],
    },
    # Sumpf-Cluster
    "swamp_thicket": {
        "biomes": {SWAMP},
        "weight": 3,
        "spread": 3,
        "placements": [
            (0, 0, "swamp_log"),
            (1, 0, "reeds"),
            (-1, 0, "reeds"),
            (0, 1, "mushrooms"),
            (1, 1, "swamp_bubbles"),
        ],
        "fillers": [("reeds", 0.30), ("lily_pads", 0.15)],
    },
    # Kakteen-Hain in Wüste
    "cactus_grove": {
        "biomes": {DESERT},
        "weight": 3,
        "spread": 3,
        "placements": [
            (0, 0, "cactus"),
            (1, 0, "cactus"),
            (-1, 0, "dry_bush"),
            (0, 1, "cactus"),
        ],
        "fillers": [("cactus", 0.15), ("dry_bush", 0.20)],
    },
    # — Farming-Drop 2026-05-26 — wilde Vegetations-Cluster —
    # Beeren-Hain
    "berry_patch": {
        "biomes": {GRASS, FOREST},
        "weight": 3,
        "spread": 3,
        "placements": [
            (0, 0, "strawberry_bush"),
            (1, 0, "blueberry_bush"),
            (-1, 0, "raspberry_bush"),
            (0, 1, "blackberry_bush"),
            (1, 1, "strawberry_bush"),
        ],
        "fillers": [("strawberry_bush", 0.15), ("blueberry_bush", 0.10),
                    ("raspberry_bush", 0.10), ("plant_fiber", 0)],
    },
    # Obst-Hain (Orchard)
    "orchard": {
        "biomes": {GRASS, FOREST},
        "weight": 2,
        "spread": 4,
        "placements": [
            (0, 0, "apple_tree"),
            (3, 0, "apple_tree"),
            (-2, 0, "pear_tree"),
            (1, 2, "cherry_tree"),
            (-1, -2, "plum_tree"),
            (2, -2, "apple_tree"),
        ],
        "fillers": [("apple_tree", 0.10), ("flowers", 0.10), ("tall_grass", 0.15)],
    },
    # Weizenfeld
    "wheat_field": {
        "biomes": {GRASS},
        "weight": 2,
        "spread": 3,
        "placements": [
            (0, 0, "wheat_grown"),
            (1, 0, "wheat_grown"),
            (-1, 0, "wheat_grown"),
            (0, 1, "wheat_grown"),
            (1, 1, "wheat_seedling"),
            (-1, 1, "wheat_grown"),
            (0, -1, "wheat_seedling"),
        ],
        "fillers": [("wheat_grown", 0.35), ("wheat_seedling", 0.15)],
    },
    # Verwildertes Feld (gemüse-cluster)
    "wild_vegetable_patch": {
        "biomes": {GRASS, JUNGLE},
        "weight": 2,
        "spread": 3,
        "placements": [
            (0, 0, "carrot_plant"),
            (1, 0, "onion_plant"),
            (-1, 0, "potato_plant"),
            (0, 1, "cabbage_plant"),
            (1, 1, "tomato_plant"),
            (-1, 1, "cucumber_plant"),
        ],
        "fillers": [("carrot_plant", 0.12), ("potato_plant", 0.12),
                    ("onion_plant", 0.10)],
    },
    # Kürbis/Mais Feld
    "pumpkin_patch": {
        "biomes": {GRASS, FOREST},
        "weight": 1,
        "spread": 3,
        "placements": [
            (0, 0, "pumpkin_plant"),
            (1, 0, "pumpkin_plant"),
            (0, 1, "corn_plant"),
            (-1, 1, "corn_plant"),
            (1, 1, "pumpkin_plant"),
        ],
        "fillers": [("pumpkin_plant", 0.15), ("corn_plant", 0.15)],
    },
}


def _pick_template_for_biome(tile_id: int) -> str | None:
    """Gewichteter Pick eines Templates das in diesem Biome erlaubt ist."""
    candidates = [(tid, t["weight"]) for tid, t in ENCOUNTER_TEMPLATES.items()
                  if tile_id in t["biomes"]]
    if not candidates:
        return None
    total = sum(w for _, w in candidates)
    r = random.uniform(0, total)
    acc = 0.0
    for tid, w in candidates:
        acc += w
        if r <= acc:
            return tid
    return candidates[-1][0]


async def _place_template(template_id: str, world, structure_manager,
                          anchor_x: int, anchor_y: int) -> list[dict]:
    """Platziert ein Template am Anker. Nicht-walkable / belegte tiles werden
    übersprungen statt das ganze Template fehlschlagen zu lassen."""
    tmpl = ENCOUNTER_TEMPLATES[template_id]
    placed: list[dict] = []
    # Fixe placements
    for dx, dy, prop in tmpl["placements"]:
        x, y = anchor_x + dx, anchor_y + dy
        if not _can_place_at(world, structure_manager, x, y):
            continue
        dur = harvest_module.initial_durability(prop)
        s = await structure_manager.place(x, y, prop, "system",
                                          material="stone", durability=dur)
        if s is not None:
            placed.append(s)
    # Filler im spread-Radius
    spread = tmpl.get("spread", 3)
    fillers = tmpl.get("fillers", [])
    if fillers and spread > 0:
        for dy in range(-spread, spread + 1):
            for dx in range(-spread, spread + 1):
                # Skip die fixen placements
                if any(dx == fdx and dy == fdy
                       for fdx, fdy, _ in tmpl["placements"]):
                    continue
                x, y = anchor_x + dx, anchor_y + dy
                if not _can_place_at(world, structure_manager, x, y):
                    continue
                for prop, chance in fillers:
                    if random.random() < chance:
                        dur = harvest_module.initial_durability(prop)
                        s = await structure_manager.place(x, y, prop, "system",
                                                          material="stone",
                                                          durability=dur)
                        if s is not None:
                            placed.append(s)
                        break  # höchstens 1 filler pro tile
    return placed


def _can_place_at(world, structure_manager, x: int, y: int) -> bool:
    tile = world.tile_at_sync(x, y)
    if tile in (WATER, MOUNTAIN, LAVA):
        return False
    if world.is_settlement_area(x, y):
        return False
    if structure_manager.at(x, y) is not None:
        return False
    return True


async def populate_chunk_if_needed(world, structure_manager, connection_manager,
                                    cx: int, cy: int, npc_manager=None) -> int:
    """Populiert einen Chunk wenn populated=False. Setzt Flag in DB.

    Zwei-Pass-System:
      Pass A: Encounter-Sites (Bäume in Gruppen, Camps mit Lagerfeuer, …)
      Pass B: Spärliche Ambient-Props auf den restlichen Tiles
    Wasser-Tiles bekommen separates Scattering (Wracks, Boote, Seerosen).
    """
    row = await db.pool().fetchrow(
        "SELECT populated FROM world_chunks WHERE world_seed = $1 "
        "AND chunk_x = $2 AND chunk_y = $3",
        world.seed, cx, cy,
    )
    if row is None or row["populated"]:
        return 0
    chunk = await world.get_chunk(cx, cy)
    placed_list = []

    # ── Pass A: 0-3 Encounter-Sites pro Chunk ──────────────────────────────
    # Pro Chunk wird gewürfelt wie viele Sites; jeder Site bekommt einen
    # Anker auf einem random walkable Tile, dann passendes Template gewählt.
    site_count = random.choices([0, 1, 2, 3], weights=[10, 50, 30, 10], k=1)[0]
    site_anchors_taken: list[tuple[int, int]] = []
    for _ in range(site_count):
        # Anker-Tile suchen (max 30 Versuche)
        anchor = None
        for _try in range(30):
            lx = random.randint(2, CHUNK_SIZE - 3)
            ly = random.randint(2, CHUNK_SIZE - 3)
            wx = cx * CHUNK_SIZE + lx
            wy = cy * CHUNK_SIZE + ly
            tile = chunk[ly][lx]
            if tile in (WATER, MOUNTAIN, LAVA):
                continue
            if world.is_settlement_area(wx, wy):
                continue
            # Mindestabstand zu bereits platzierten Sites
            if any(abs(wx - ax) < 6 and abs(wy - ay) < 6
                   for ax, ay in site_anchors_taken):
                continue
            anchor = (wx, wy, tile)
            break
        if anchor is None:
            continue
        ax, ay, atile = anchor
        template_id = _pick_template_for_biome(atile)
        if template_id is None:
            continue
        site_anchors_taken.append((ax, ay))
        placed = await _place_template(template_id, world, structure_manager, ax, ay)
        placed_list.extend(placed)
        log.info("Site '%s' @(%d,%d): %d structures",
                 template_id, ax, ay, len(placed))

    # ── Pass B: Ambient + Water/Coast — sehr sparsam ───────────────────────
    for ly in range(CHUNK_SIZE):
        for lx in range(CHUNK_SIZE):
            wx = cx * CHUNK_SIZE + lx
            wy = cy * CHUNK_SIZE + ly
            tile = chunk[ly][lx]
            if tile in (MOUNTAIN, LAVA):
                continue
            if world.is_settlement_area(wx, wy):
                continue
            if structure_manager.at(wx, wy) is not None:
                continue
            # Wasser bleibt im alten Scatter (Wracks, Boote, Seerosen)
            if tile == WATER:
                chosen = _pick_for_water(world, wx, wy)
                if chosen is None:
                    continue
                dur = harvest_module.initial_durability(chosen)
                ps = await structure_manager.place(
                    wx, wy, chosen, "system", material="wood", durability=dur,
                )
                if ps is not None:
                    placed_list.append(ps)
                continue
            # Land: nur noch ambient mit ~30% der Original-Chance, sodass
            # die Welt zwischen Sites nicht zu kahl wirkt aber Sites dominieren.
            chosen = _pick_ambient(world, wx, wy, tile)
            if chosen is None:
                continue
            dur = harvest_module.initial_durability(chosen)
            ps = await structure_manager.place(
                wx, wy, chosen, "system", material="stone", durability=dur,
            )
            if ps is not None:
                placed_list.append(ps)
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
