"""Prozeduraler Dungeon-Generator (BSP + Loops + Features).

Überarbeitung 2026-05-29: deutlich größere Etagen, mehr Räume, zusätzliche
Schleifen-Verbindungen (nicht nur ein Baum → kein langweiliger Schlauch),
sowie deterministisch generierte FEATURES (Kisten, versteckte Fallen, Decor).
Alles aus dem Floor-Seed reproduzierbar — der Server kann Features jederzeit
neu berechnen ohne Extra-DB-Spalten.

Tile-IDs (Dungeon-spezifisch, separat von Overworld):
    0 = wall (solid)
    1 = floor (Raum)
    2 = corridor (Gang, begehbar)
    3 = stairs_up   (zur vorherigen Floor / Overworld-Exit auf Floor 0)
    4 = stairs_down (zur nächsten Floor, nur auf nicht-letzter Floor)

Features (separat von den Tiles, als Listen im Layout-Dict):
    chests : [{"x","y"}]            — Schatzkisten (Loot beim Öffnen)
    traps  : [{"x","y","kind"}]     — versteckte Fallen (Trigger beim Betreten)
    decor  : [{"x","y","kind"}]     — kosmetische Theme-Props
"""
import logging
import random

log = logging.getLogger("liege.dungeon_world")

WALL, FLOOR, CORRIDOR, STAIRS_UP, STAIRS_DOWN = 0, 1, 2, 3, 4

DEFAULT_SIZE = 48
MIN_ROOM_SIZE = 5
MAX_ROOM_SIZE = 13
# Mindestpartitionsgröße, ab der weiter gesplittet wird (steuert Raumanzahl).
LEAF_TARGET = 18


class _Room:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)


def _carve_room(tiles, room):
    for y in range(room.y, room.y + room.h):
        for x in range(room.x, room.x + room.w):
            tiles[y][x] = FLOOR


def _carve_corridor(tiles, a, b, rng):
    """L- oder Z-Korridor zwischen zwei Punkten, 2 Tiles breit für großzügige
    Gänge in den großen Maps."""
    ax, ay = a
    bx, by = b
    horizontal_first = rng.random() < 0.5
    h_max = len(tiles)
    w_max = len(tiles[0])

    def hcarve(y, x0, x1):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for yy in (y, y + 1):
                if 0 <= yy < h_max and 0 <= x < w_max and tiles[yy][x] == WALL:
                    tiles[yy][x] = CORRIDOR

    def vcarve(x, y0, y1):
        for y in range(min(y0, y1), max(y0, y1) + 1):
            for xx in (x, x + 1):
                if 0 <= xx < w_max and 0 <= y < h_max and tiles[y][xx] == WALL:
                    tiles[y][xx] = CORRIDOR

    if horizontal_first:
        hcarve(ay, ax, bx)
        vcarve(bx, ay, by)
    else:
        vcarve(ax, ay, by)
        hcarve(by, ax, bx)


def _split_bsp(rng, x, y, w, h, rooms):
    """Rekursiver BSP-Split bis Partitionen ~LEAF_TARGET sind, dann ein Raum
    pro Leaf."""
    can_split_w = w > LEAF_TARGET * 1.4
    can_split_h = h > LEAF_TARGET * 1.4
    if not can_split_w and not can_split_h:
        rw = rng.randint(MIN_ROOM_SIZE, max(MIN_ROOM_SIZE, min(MAX_ROOM_SIZE, w - 2)))
        rh = rng.randint(MIN_ROOM_SIZE, max(MIN_ROOM_SIZE, min(MAX_ROOM_SIZE, h - 2)))
        rx = x + rng.randint(1, max(1, w - rw - 1))
        ry = y + rng.randint(1, max(1, h - rh - 1))
        rooms.append(_Room(rx, ry, rw, rh))
        return
    if can_split_w and can_split_h:
        split_h = rng.random() < 0.5
    else:
        split_h = can_split_h
    if split_h:
        s = rng.randint(int(h * 0.35), int(h * 0.65))
        _split_bsp(rng, x, y, w, s, rooms)
        _split_bsp(rng, x, y + s, w, h - s, rooms)
    else:
        s = rng.randint(int(w * 0.35), int(w * 0.65))
        _split_bsp(rng, x, y, s, h, rooms)
        _split_bsp(rng, x + s, y, w - s, h, rooms)


def _walkable_in_room(tiles, room):
    """Begehbare (FLOOR) Innen-Tiles eines Raums (1-Tile-Rand nach innen)."""
    spots = []
    for yy in range(room.y + 1, room.y + room.h - 1):
        for xx in range(room.x + 1, room.x + room.w - 1):
            if tiles[yy][xx] == FLOOR:
                spots.append((xx, yy))
    return spots


def generate(seed, size=DEFAULT_SIZE, theme=None, with_stairs_down=False):
    """Generiert ein Floor-Layout inkl. Features. Deterministisch aus seed."""
    import dungeon_themes
    if theme is None or theme not in dungeon_themes.THEMES:
        theme = dungeon_themes.pick_theme_for_seed(seed)
    rng = random.Random(seed)
    tiles = [[WALL for _ in range(size)] for _ in range(size)]

    rooms = []
    _split_bsp(rng, 0, 0, size, size, rooms)
    for r in rooms:
        r.x = max(1, min(size - 2 - r.w, r.x))
        r.y = max(1, min(size - 2 - r.h, r.y))
        _carve_room(tiles, r)
    if not rooms:
        r = _Room(size // 4, size // 4, size // 2, size // 2)
        _carve_room(tiles, r)
        rooms = [r]

    centers = [r.center for r in rooms]
    # Spanning-Pfad (garantiert zusammenhängend)
    for i in range(1, len(centers)):
        _carve_corridor(tiles, centers[i - 1], centers[i], rng)
    # Extra-Schleifen (~25%): Loops statt reiner Baum.
    extra = max(1, len(centers) // 4)
    for _ in range(extra):
        a, b = rng.randrange(len(centers)), rng.randrange(len(centers))
        if a != b:
            _carve_corridor(tiles, centers[a], centers[b], rng)

    # Spawn = größter Raum; Stairs-Up dort.
    spawn_room = max(rooms, key=lambda r: r.w * r.h)
    spawn = spawn_room.center
    tiles[spawn[1]][spawn[0]] = STAIRS_UP

    stairs_down = None
    boss_room = spawn_room
    if len(rooms) > 1:
        boss_room = max(rooms,
                        key=lambda r: abs(r.center[0] - spawn[0]) + abs(r.center[1] - spawn[1]))
        if with_stairs_down:
            bd = boss_room.center
            tiles[bd[1]][bd[0]] = STAIRS_DOWN
            stairs_down = bd

    # ── Features deterministisch platzieren ────────────────────────────────
    theme_data = dungeon_themes.THEMES.get(theme, {})
    decor_pool = theme_data.get("room_decor", ["wall_torch"])
    trap_kinds = theme_data.get("trap_kinds", ["spike_trap"])

    occupied = {spawn}
    if stairs_down:
        occupied.add(stairs_down)

    chests, traps, decor = [], [], []

    # Kisten: ~1/3 der Räume (außer Spawn) + garantiert im Boss-Raum.
    n_chests = max(1, len(rooms) // 3)
    if boss_room is not spawn_room:
        spots = [s for s in _walkable_in_room(tiles, boss_room) if s not in occupied]
        if spots:
            sx, sy = rng.choice(spots)
            chests.append({"x": sx, "y": sy})
            occupied.add((sx, sy))
    other_rooms = [r for r in rooms if r is not spawn_room and r is not boss_room]
    rng.shuffle(other_rooms)
    for r in other_rooms:
        if len(chests) >= n_chests:
            break
        spots = [s for s in _walkable_in_room(tiles, r) if s not in occupied]
        if not spots:
            continue
        sx, sy = rng.choice(spots)
        chests.append({"x": sx, "y": sy})
        occupied.add((sx, sy))

    # Decor: 1-3 Theme-Props pro Raum (kosmetisch).
    for r in rooms:
        spots = [s for s in _walkable_in_room(tiles, r) if s not in occupied]
        rng.shuffle(spots)
        for sx, sy in spots[:rng.randint(1, 3)]:
            decor.append({"x": sx, "y": sy, "kind": rng.choice(decor_pool)})
            occupied.add((sx, sy))

    # Versteckte Fallen: ~1.8% der begehbaren Fläche, nicht nahe Spawn.
    walk_all = []
    for y in range(size):
        for x in range(size):
            if tiles[y][x] in (FLOOR, CORRIDOR) and (x, y) not in occupied:
                if abs(x - spawn[0]) + abs(y - spawn[1]) <= 2:
                    continue
                walk_all.append((x, y))
    rng.shuffle(walk_all)
    n_traps = int(len(walk_all) * 0.018)
    for sx, sy in walk_all[:n_traps]:
        traps.append({"x": sx, "y": sy, "kind": rng.choice(trap_kinds)})

    log.info("Floor seed=%d theme=%s size=%d: %d rooms, %d chests, %d traps, %d decor",
             seed, theme, size, len(rooms), len(chests), len(traps), len(decor))
    return {
        "size":         size,
        "theme":        theme,
        "tiles":        tiles,
        "rooms":        [{"x": r.x, "y": r.y, "w": r.w, "h": r.h} for r in rooms],
        "spawn":        spawn,
        "stairs_up":    spawn,
        "stairs_down":  stairs_down,
        "chests":       chests,
        "traps":        traps,
        "decor":        decor,
    }


def is_walkable_tile(tile_id):
    return tile_id in (FLOOR, CORRIDOR, STAIRS_UP, STAIRS_DOWN)
