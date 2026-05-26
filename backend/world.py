"""Chunked, prozedural generierte Welt mit Multi-Layer-Noise.

Vier parallele Noise-Maps:
- height       (Land/Wasser/Berge)
- moisture     (trocken bis nass)
- temperature  (kalt bis heiß)
- fertility    (Ressourcen-Dichte modifier)

Plus boolesche Maps:
- is_lake          (innland-See)
- is_settlement_area (Reserveflächen für Bauen)
"""

import logging
import math

import db

log = logging.getLogger("liege.world")

# Tile-Typen
WATER, SAND, GRASS, FOREST, MOUNTAIN = 0, 1, 2, 3, 4
DESERT, JUNGLE, LAVA, SNOW, SWAMP = 5, 6, 7, 8, 9
WALKABLE = {SAND, GRASS, FOREST, DESERT, JUNGLE, SNOW, SWAMP}
NON_WALKABLE = {WATER, MOUNTAIN, LAVA}

CHUNK_SIZE = 32
DEFAULT_SEED = 42


# — Noise-Primitives ——————————————————————————————————————————————————————————

def _hash01(x: int, y: int, seed: int) -> float:
    """Deterministischer Hash zu [0,1)."""
    h = (x * 374761393 + y * 668265263 + seed * 1013904223) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0x7FFFFFFF) / 0x7FFFFFFF


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _value_noise(x: float, y: float, seed: int) -> float:
    xi = math.floor(x)
    yi = math.floor(y)
    xf = x - xi
    yf = y - yi
    a = _hash01(xi,     yi,     seed)
    b = _hash01(xi + 1, yi,     seed)
    c = _hash01(xi,     yi + 1, seed)
    d = _hash01(xi + 1, yi + 1, seed)
    sx = _smooth(xf)
    sy = _smooth(yf)
    return _lerp(_lerp(a, b, sx), _lerp(c, d, sx), sy)


def _fbm(x: float, y: float, seed: int, octaves: int = 4,
         persistence: float = 0.5, lacunarity: float = 2.0) -> float:
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_amp = 0.0
    for _ in range(octaves):
        total += _value_noise(x * frequency, y * frequency, seed) * amplitude
        max_amp += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return total / max_amp if max_amp > 0 else 0.0


# — World ————————————————————————————————————————————————————————————————————

class World:
    def __init__(self, seed: int = DEFAULT_SEED):
        self.seed = seed
        self._chunks: dict[tuple[int, int], list[list[int]]] = {}

    @classmethod
    async def load_or_create(cls, seed: int = DEFAULT_SEED) -> "World":
        w = cls(seed)
        rows = await db.pool().fetch(
            "SELECT chunk_x, chunk_y, tiles FROM world_chunks WHERE world_seed = $1",
            seed,
        )
        for r in rows:
            w._chunks[(r["chunk_x"], r["chunk_y"])] = r["tiles"]
        log.info("Welt %d: %d Chunks aus DB geladen", seed, len(w._chunks))
        return w

    # — Noise-Layer (großflächige Frequenzen für kohärente Biome) ——————————

    # Distance vom Äquator (y=0) bis zum Pol in tiles. Innerhalb dieser Distanz
    # geht das Klima von "tropisch" zu "polar". Größerer Wert = sanftere Übergänge.
    EQUATOR_TO_POLE = 600

    def height(self, x: int, y: int) -> float:
        return _fbm(x * 0.012, y * 0.012, self.seed * 1 + 100, octaves=5,
                    persistence=0.55)

    def moisture(self, x: int, y: int) -> float:
        # Pures Noise mit moderater Skala — damit Wüsten/Dschungel-Patches
        # sich gut von Klima-Zonen abheben (nicht gerade Linien).
        return _fbm(x * 0.018, y * 0.018, self.seed * 1 + 200, octaves=4)

    def temperature(self, x: int, y: int) -> float:
        """Klimazonen: heiß am Äquator (y=0), kalt an den Polen (|y|>=EQUATOR_TO_POLE).
        Plus fbm-Noise damit die Übergänge nicht als gerade Linien wirken."""
        lat_norm = min(1.0, abs(y) / self.EQUATOR_TO_POLE)  # 0=Äquator, 1+=Pol
        climate = 1.0 - lat_norm  # 1.0=heiß, 0.0=eiskalt
        # Noise-Overlay sorgt für unregelmäßige Übergangsgrenzen
        noise = _fbm(x * 0.010, y * 0.010, self.seed * 1 + 300, octaves=3)
        return max(0.0, min(1.0, 0.65 * climate + 0.35 * noise))

    def fertility(self, x: int, y: int) -> float:
        """Density-Map für Vegetation."""
        return _fbm(x * 0.04, y * 0.04, self.seed * 1 + 400, octaves=3)

    def resource_density(self, x: int, y: int, kind: str) -> float:
        offset = {"tree": 500, "rock": 600, "ore": 700,
                  "plant": 800, "ruin": 900}.get(kind, 1000)
        return _fbm(x * 0.05, y * 0.05, self.seed * 1 + offset, octaves=2)

    def is_lake(self, x: int, y: int) -> bool:
        """Innland-See in feuchten, niedrigen Senken."""
        h = self.height(x, y)
        if h < 0.32 or h > 0.50:
            return False
        m = self.moisture(x, y)
        if m < 0.65:
            return False
        lake_noise = _fbm(x * 0.035, y * 0.035, self.seed * 1 + 1500, octaves=2)
        return lake_noise > 0.72

    def is_settlement_area(self, x: int, y: int) -> bool:
        """Reserviere Bereiche als Bauplätze (keine natürliche Deko)."""
        return _fbm(x * 0.008, y * 0.008, self.seed * 1 + 2500, octaves=2) > 0.66

    def _classify_at(self, x: int, y: int) -> int:
        h = self.height(x, y)
        m = self.moisture(x, y)
        t = self.temperature(x, y)

        # Wasser-Senken (mehr Wasser für Atmosphäre)
        if h < 0.36:
            return WATER
        # Inland-Seen
        if self.is_lake(x, y):
            return WATER

        # Hohe Berge (mehr Variation oben)
        if h > 0.74:
            if t > 0.80 and h > 0.90:
                return LAVA
            if t < 0.25:
                return SNOW
            return MOUNTAIN

        # Strand-Gürtel direkt am Wasser
        if h < 0.42:
            if t < 0.22:
                return SNOW
            if t > 0.78 and m < 0.32:
                return DESERT
            return SAND

        # Hochland-Übergang
        if h > 0.66:
            if t < 0.22:
                return SNOW
            if m > 0.55:
                return FOREST
            return GRASS

        # Mittlere Höhen — biome aus moisture × temperature
        if t < 0.22:
            return SNOW
        if t > 0.78 and m < 0.32:
            return DESERT
        if m > 0.68 and t > 0.55:
            return JUNGLE
        if m > 0.65 and h < 0.50:
            return SWAMP
        if m < 0.38 and t > 0.55:
            return SAND
        if m > 0.50 and h > 0.55:
            return FOREST
        return GRASS

    def _generate_chunk(self, cx: int, cy: int) -> list[list[int]]:
        tiles = []
        for ly in range(CHUNK_SIZE):
            row = []
            for lx in range(CHUNK_SIZE):
                wx = cx * CHUNK_SIZE + lx
                wy = cy * CHUNK_SIZE + ly
                row.append(self._classify_at(wx, wy))
            tiles.append(row)
        return tiles

    # — Chunk-Zugriff ————————————————————————————————————————————————————

    async def get_chunk(self, cx: int, cy: int) -> list[list[int]]:
        if (cx, cy) in self._chunks:
            return self._chunks[(cx, cy)]
        row = await db.pool().fetchrow(
            "SELECT tiles FROM world_chunks WHERE world_seed = $1 "
            "AND chunk_x = $2 AND chunk_y = $3",
            self.seed, cx, cy,
        )
        if row is not None:
            tiles = row["tiles"]
        else:
            tiles = self._generate_chunk(cx, cy)
            await db.pool().execute(
                "INSERT INTO world_chunks (world_seed, chunk_x, chunk_y, tiles) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                self.seed, cx, cy, tiles,
            )
        self._chunks[(cx, cy)] = tiles
        return tiles

    async def ensure_chunks_around(self, cx: int, cy: int, radius: int = 3) -> list[dict]:
        out = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tcx, tcy = cx + dx, cy + dy
                tiles = await self.get_chunk(tcx, tcy)
                out.append({"cx": tcx, "cy": tcy, "tiles": tiles})
        return out

    @staticmethod
    def world_to_chunk(x: int, y: int) -> tuple[int, int, int, int]:
        cx, lx = divmod(x, CHUNK_SIZE)
        cy, ly = divmod(y, CHUNK_SIZE)
        return cx, cy, lx, ly

    async def tile_at(self, x: int, y: int) -> int:
        cx, cy, lx, ly = self.world_to_chunk(x, y)
        chunk = await self.get_chunk(cx, cy)
        return chunk[ly][lx]

    def tile_at_sync(self, x: int, y: int) -> int:
        cx, cy, lx, ly = self.world_to_chunk(x, y)
        chunk = self._chunks.get((cx, cy))
        if chunk is None:
            return WATER
        return chunk[ly][lx]

    async def is_walkable(self, x: int, y: int) -> bool:
        return await self.tile_at(x, y) in WALKABLE

    def is_walkable_sync(self, x: int, y: int) -> bool:
        return self.tile_at_sync(x, y) in WALKABLE

    async def find_spawn(self, center_x: int = 0, center_y: int = 0) -> dict:
        """Sicheren Grass-Spawn in einer Settlement-Area nahe (center_x, center_y)."""
        # Bevorzuge Settlement-Area + Grass
        for radius in range(0, 80):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    x = center_x + dx
                    y = center_y + dy
                    if await self.tile_at(x, y) == GRASS and self.is_settlement_area(x, y):
                        return {"x": x, "y": y}
        # Fallback nur Grass
        for radius in range(0, 80):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    x = center_x + dx
                    y = center_y + dy
                    if await self.tile_at(x, y) == GRASS:
                        return {"x": x, "y": y}
        # Fallback: irgendein walkable
        for radius in range(0, 80):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    x = center_x + dx
                    y = center_y + dy
                    if await self.is_walkable(x, y):
                        return {"x": x, "y": y}
        return {"x": center_x, "y": center_y}

    def chunks_in_cache(self) -> list[tuple[int, int]]:
        return list(self._chunks.keys())
