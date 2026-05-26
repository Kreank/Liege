import db

STRUCTURE_TYPES = {
    "wall":      {"blocking": True},
    "floor":     {"blocking": False},
    "campfire":  {"blocking": False},
    "marker":    {"blocking": False},
    # Interaktive Strukturen
    "chest":     {"blocking": True},
    "workbench": {"blocking": True},
    "furnace":   {"blocking": True},
    "anvil":     {"blocking": True},
    "bed":       {"blocking": False},
    "well":      {"blocking": True},
    "farm_plot": {"blocking": False},
    # Traps
    "spike_trap":  {"blocking": False},
    "poison_trap": {"blocking": False},
    # Dungeon-Eingang (MVP: Loot-Encounter beim Klick)
    "stairs_down": {"blocking": False},
    # Neue Welt-Deko (Settlement + Ruins + Wasser)
    "camp_tent":     {"blocking": False},
    "cooking_pot":   {"blocking": False},
    "bones_scatter": {"blocking": False},
    "gravestone":    {"blocking": True},
    "dock_corner":   {"blocking": False},
    "boat_small":    {"blocking": True},
    "anchor":        {"blocking": False},
    "fishing_net":   {"blocking": False},
    "driftwood":     {"blocking": False},
    # Deko: Natur
    "tree_oak":     {"blocking": True},
    "tree_pine":    {"blocking": True},
    "tree_dead":    {"blocking": True},
    "tree_stump":   {"blocking": True},
    "fallen_log":   {"blocking": True},
    "bush":         {"blocking": False},
    "tall_grass":   {"blocking": False},
    "flowers":      {"blocking": False},
    "mushrooms":    {"blocking": False},
    "rock_small":   {"blocking": True},
    "rock_large":   {"blocking": True},
    "rock_mossy":   {"blocking": True},
    # Deko: Wasser
    "lily_pads":      {"blocking": False},
    "reeds":          {"blocking": False},
    "dock_straight":  {"blocking": False},
    "wooden_bridge":  {"blocking": False},
    "shipwreck":      {"blocking": True},
    # Deko: Siedlung
    "broken_cart": {"blocking": True},
    "barrel":      {"blocking": True},
    "crate":       {"blocking": True},
    "sack":        {"blocking": False},
    "fence":       {"blocking": True},
    # Garden-Gates: zwei Richtungen (ew/ns), zwei Zustände (open/closed)
    "garden_gate_ew_closed": {"blocking": True},
    "garden_gate_ew_open":   {"blocking": False},
    "garden_gate_ns_closed": {"blocking": True},
    "garden_gate_ns_open":   {"blocking": False},
    # Türen — open/closed pro Material
    "door_wood":         {"blocking": True},
    "door_wood_open":    {"blocking": False},
    "door_iron":         {"blocking": True},
    "door_iron_open":    {"blocking": False},
    "door_stone":        {"blocking": True},
    "door_stone_open":   {"blocking": False},
    "door_reinforced":   {"blocking": True},
    # Treppen — auf/ab pro Material (laufbar wie Floor)
    "stairs_wood_up":    {"blocking": False},
    "stairs_wood_down":  {"blocking": False},
    "stairs_stone_up":   {"blocking": False},
    "stairs_stone_down": {"blocking": False},
    # Deko: Ruinen
    "ruin_pillar":    {"blocking": True},
    "rubble":         {"blocking": False},
    "statue_broken":  {"blocking": True},
}

VALID_MATERIALS = {"stone", "wood", "straw"}
DEFAULT_MATERIAL = "stone"

# Welche Strukturen ins floor-Layer gehören (Rest geht ins object-Layer).
# Floors blockieren nie und ein Object kann oben drauf platziert werden.
FLOOR_TYPES = {"floor"}


def _layer_for(type_: str) -> str:
    return "floor" if type_ in FLOOR_TYPES else "object"


class StructureManager:
    def __init__(self):
        # Zwei Layer-Maps: floor (Boden) + object (Wände/Möbel/Deko).
        # Pro Tile kann genau ein Floor UND ein Object existieren.
        self._floor_by_coord: dict[tuple[int, int], dict] = {}
        self._object_by_coord: dict[tuple[int, int], dict] = {}

    def _layer_map(self, layer: str) -> dict:
        return self._floor_by_coord if layer == "floor" else self._object_by_coord

    async def load(self) -> None:
        rows = await db.pool().fetch(
            "SELECT id, x, y, type, owner, material, durability, layer FROM structures"
        )
        self._floor_by_coord.clear()
        self._object_by_coord.clear()
        for r in rows:
            struct = {
                "id":         r["id"],
                "x":          r["x"],
                "y":          r["y"],
                "type":       r["type"],
                "owner":      r["owner"],
                "material":   r["material"],
                "durability": r["durability"],
                "layer":      r["layer"],
            }
            self._layer_map(r["layer"])[(r["x"], r["y"])] = struct

    def all(self) -> list[dict]:
        """Alle Strukturen aus beiden Layern (Floor zuerst, dann Object)."""
        return list(self._floor_by_coord.values()) + list(self._object_by_coord.values())

    def at(self, x: int, y: int) -> dict | None:
        """Top-Layer-Lookup: Object wenn vorhanden, sonst Floor."""
        return self._object_by_coord.get((x, y)) or self._floor_by_coord.get((x, y))

    def object_at(self, x: int, y: int) -> dict | None:
        return self._object_by_coord.get((x, y))

    def floor_at(self, x: int, y: int) -> dict | None:
        return self._floor_by_coord.get((x, y))

    def blocks(self, x: int, y: int) -> bool:
        """Nur Object-Layer kann blocken (Floor blockiert nie)."""
        s = self._object_by_coord.get((x, y))
        if s is None:
            return False
        spec = STRUCTURE_TYPES.get(s["type"])
        return bool(spec and spec["blocking"])

    async def place(self, x: int, y: int, type_: str, owner: str,
                    material: str = DEFAULT_MATERIAL, durability: int = 1) -> dict | None:
        if type_ not in STRUCTURE_TYPES:
            return None
        if material not in VALID_MATERIALS:
            material = DEFAULT_MATERIAL
        layer = _layer_for(type_)
        layer_map = self._layer_map(layer)
        if (x, y) in layer_map:
            return None  # Slot in diesem Layer ist belegt
        row = await db.pool().fetchrow(
            "INSERT INTO structures (x, y, type, owner, material, durability, layer) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
            x, y, type_, owner, material, durability, layer,
        )
        struct = {
            "id":         row["id"],
            "x":          x,
            "y":          y,
            "type":       type_,
            "owner":      owner,
            "material":   material,
            "durability": durability,
            "layer":      layer,
        }
        layer_map[(x, y)] = struct
        return struct

    async def damage_structure(self, x: int, y: int, amount: int = 1,
                               layer: str | None = None) -> dict | None:
        """Reduziert durability. Default-Ziel: Object-Layer (sonst Floor)."""
        if layer is None:
            # Object hat Vorrang — wenn nichts da, dann Floor
            s = self._object_by_coord.get((x, y)) or self._floor_by_coord.get((x, y))
        else:
            s = self._layer_map(layer).get((x, y))
        if s is None:
            return None
        new_dur = s["durability"] - amount
        if new_dur <= 0:
            await db.pool().execute("DELETE FROM structures WHERE id = $1", s["id"])
            self._layer_map(s["layer"]).pop((x, y), None)
            return None
        await db.pool().execute(
            "UPDATE structures SET durability = $1 WHERE id = $2", new_dur, s["id"]
        )
        s["durability"] = new_dur
        return s

    async def remove(self, x: int, y: int, layer: str | None = None) -> dict | None:
        """Entfernt eine Struktur. Default: Object-Layer; wenn None und kein Object → Floor."""
        if layer is None:
            struct = self._object_by_coord.pop((x, y), None)
            if struct is None:
                struct = self._floor_by_coord.pop((x, y), None)
        else:
            struct = self._layer_map(layer).pop((x, y), None)
        if struct is None:
            return None
        await db.pool().execute(
            "DELETE FROM structures WHERE id = $1", struct["id"]
        )
        return struct
