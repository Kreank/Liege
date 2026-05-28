"""Prozeduraler Dungeon-Generator (BSP-basiert).

Erzeugt Floor-Maps für mehrstufige Dungeons. Pro Floor ein BSP-Layout
mit Räumen, Korridoren, Start-Tile, `stairs_up` (Exit/vorherige Floor)
und optional `stairs_down` (nächste Floor).

Tile-IDs (Dungeon-spezifisch, separat von Overworld):
    0 = wall (solid)
    1 = floor
    2 = corridor (auch begehbar)
    3 = stairs_up   (zur vorherigen Floor / Overworld-Exit auf Floor 0)
    4 = stairs_down (zur nächsten Floor, nur auf nicht-letzter Floor)
"""
import logging
import random

log = logging.getLogger("liege.dungeon_world")

WALL, FLOOR, CORRIDOR, STAIRS_UP, STAIRS_DOWN = 0, 1, 2, 3, 4

DEFAULT_SIZE = 24
MIN_ROOM_SIZE = 4
MAX_ROOM_SIZE = 8
MAX_DEPTH = 4


class _Room:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)


def _carve_room(tiles: list[list[int]], room: _Room) -> None:
    for y in range(room.y, room.y + room.h):
        for x in range(room.x, room.x + room.w):
            tiles[y][x] = FLOOR


def _carve_corridor(tiles: list[list[int]], a: tuple[int, int],
                    b: tuple[int, int]) -> None:
    ax, ay = a
    bx, by = b
    # L-Form: zuerst horizontal, dann vertikal
    for x in range(min(ax, bx), max(ax, bx) + 1):
        if tiles[ay][x] == WALL:
            tiles[ay][x] = CORRIDOR
    for y in range(min(ay, by), max(ay, by) + 1):
        if tiles[y][bx] == WALL:
            tiles[y][bx] = CORRIDOR


def _split_bsp(rng: random.Random, x: int, y: int, w: int, h: int,
               depth: int) -> list[_Room]:
    """Rekursiver BSP-Split — gibt Liste von Räumen zurück."""
    if depth >= MAX_DEPTH or (w < MIN_ROOM_SIZE * 2 and h < MIN_ROOM_SIZE * 2):
        rw = rng.randint(MIN_ROOM_SIZE, min(MAX_ROOM_SIZE, max(MIN_ROOM_SIZE, w - 2)))
        rh = rng.randint(MIN_ROOM_SIZE, min(MAX_ROOM_SIZE, max(MIN_ROOM_SIZE, h - 2)))
        rx = x + rng.randint(1, max(1, w - rw - 1))
        ry = y + rng.randint(1, max(1, h - rh - 1))
        return [_Room(rx, ry, rw, rh)]
    split_horizontal = (h > w) if h != w else rng.random() < 0.5
    if split_horizontal and h >= MIN_ROOM_SIZE * 2 + 2:
        split = rng.randint(MIN_ROOM_SIZE + 1, h - MIN_ROOM_SIZE - 1)
        a = _split_bsp(rng, x, y, w, split, depth + 1)
        b = _split_bsp(rng, x, y + split, w, h - split, depth + 1)
        return a + b
    if not split_horizontal and w >= MIN_ROOM_SIZE * 2 + 2:
        split = rng.randint(MIN_ROOM_SIZE + 1, w - MIN_ROOM_SIZE - 1)
        a = _split_bsp(rng, x, y, split, h, depth + 1)
        b = _split_bsp(rng, x + split, y, w - split, h, depth + 1)
        return a + b
    # Kann nicht splitten — Endknoten
    rw = max(MIN_ROOM_SIZE, w - 2)
    rh = max(MIN_ROOM_SIZE, h - 2)
    return [_Room(x + 1, y + 1, rw, rh)]


def generate(seed: int, size: int = DEFAULT_SIZE, theme: str | None = None,
             with_stairs_down: bool = False) -> dict:
    """Generiert ein Floor-Layout.

    theme: optional 'crypt'/'mine'/'temple'/'ruin'/'cave' — wenn None,
    deterministisch aus seed gewählt.
    with_stairs_down: True → ein STAIRS_DOWN-Tile im am weitesten
    entfernten Raum platzieren. Auf der letzten Floor False (Boss statt
    Treppe).

    Returns: {
        "size": size, "theme": str,
        "tiles": list[list[int]],
        "rooms": list[(cx, cy)],
        "spawn": (x, y),               # STAIRS_UP-Position
        "stairs_up": (x, y),
        "stairs_down": (x, y) | None,
    }
    """
    import dungeon_themes
    if theme is None or theme not in dungeon_themes.THEMES:
        theme = dungeon_themes.pick_theme_for_seed(seed)
    rng = random.Random(seed)
    tiles = [[WALL for _ in range(size)] for _ in range(size)]
    rooms = _split_bsp(rng, 0, 0, size, size, 0)
    for r in rooms:
        # Clamp to map
        r.x = max(1, min(size - 2 - r.w, r.x))
        r.y = max(1, min(size - 2 - r.h, r.y))
        _carve_room(tiles, r)
    centers = [r.center for r in rooms]
    # Korridore verbinden alle Rooms zum jeweils nächsten
    for i in range(1, len(centers)):
        _carve_corridor(tiles, centers[i - 1], centers[i])
    # Spawn-Tile = erstes Room-Center, Stairs-Up dort
    spawn = centers[0] if centers else (size // 2, size // 2)
    tiles[spawn[1]][spawn[0]] = STAIRS_UP
    # Stairs-Down im am weitesten entfernten Raum-Center
    stairs_down = None
    if with_stairs_down and len(centers) > 1:
        farthest = max(centers[1:],
                       key=lambda c: abs(c[0] - spawn[0]) + abs(c[1] - spawn[1]))
        tiles[farthest[1]][farthest[0]] = STAIRS_DOWN
        stairs_down = farthest
    log.info("Floor seed=%d theme=%s: %d rooms, spawn=%s, stairs_down=%s",
             seed, theme, len(rooms), spawn, stairs_down)
    return {
        "size":         size,
        "theme":        theme,
        "tiles":        tiles,
        "rooms":        centers,
        "spawn":        spawn,
        "stairs_up":    spawn,
        "stairs_down":  stairs_down,
    }


def is_walkable_tile(tile_id: int) -> bool:
    return tile_id in (FLOOR, CORRIDOR, STAIRS_UP, STAIRS_DOWN)
