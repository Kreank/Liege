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


class StructureManager:
    def __init__(self):
        self._by_coord: dict[tuple[int, int], dict] = {}

    async def load(self) -> None:
        rows = await db.pool().fetch(
            "SELECT id, x, y, type, owner, material, durability FROM structures"
        )
        self._by_coord = {
            (r["x"], r["y"]): {
                "id":         r["id"],
                "x":          r["x"],
                "y":          r["y"],
                "type":       r["type"],
                "owner":      r["owner"],
                "material":   r["material"],
                "durability": r["durability"],
            }
            for r in rows
        }

    def all(self) -> list[dict]:
        return list(self._by_coord.values())

    def at(self, x: int, y: int) -> dict | None:
        return self._by_coord.get((x, y))

    def blocks(self, x: int, y: int) -> bool:
        s = self._by_coord.get((x, y))
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
        if (x, y) in self._by_coord:
            return None
        row = await db.pool().fetchrow(
            "INSERT INTO structures (x, y, type, owner, material, durability) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            x, y, type_, owner, material, durability,
        )
        struct = {
            "id":         row["id"],
            "x":          x,
            "y":          y,
            "type":       type_,
            "owner":      owner,
            "material":   material,
            "durability": durability,
        }
        self._by_coord[(x, y)] = struct
        return struct

    async def damage_structure(self, x: int, y: int, amount: int = 1) -> dict | None:
        """Reduziert durability. Wenn ≤ 0 → entfernt Struktur. Returnt aktuellen Stand oder None."""
        s = self._by_coord.get((x, y))
        if s is None:
            return None
        new_dur = s["durability"] - amount
        if new_dur <= 0:
            await db.pool().execute("DELETE FROM structures WHERE id = $1", s["id"])
            self._by_coord.pop((x, y), None)
            return None
        await db.pool().execute(
            "UPDATE structures SET durability = $1 WHERE id = $2", new_dur, s["id"]
        )
        s["durability"] = new_dur
        return s

    async def remove(self, x: int, y: int) -> dict | None:
        struct = self._by_coord.pop((x, y), None)
        if struct is None:
            return None
        await db.pool().execute(
            "DELETE FROM structures WHERE id = $1", struct["id"]
        )
        return struct
