import db

# Welle 51 — Settlement-Schilder. Slug = Manifest-Slug aus
# assets/props/settlement/signs/professional/manifest.json
SIGN_SLUGS = [
    "schmiede", "gasthaus", "wohnhaus", "baeckerei", "marktstand",
    "lagerhaus", "apotheke_heiler", "stall", "wache", "kaserne",
    "rathaus", "bergwerk", "saegewerk", "holzfaeller", "bauernhof",
    "muehle", "fischerhuette", "taverne_brauerei", "schneiderei",
    "gerberei", "jaegerhuette", "alchemie", "magierturm", "kapelle",
    "friedhof", "bibliothek", "schule", "goldschmied", "waffenladen",
    "ruestungsschmied", "hafen", "brunnen", "ritualplatz", "portalraum",
    "verzauberer", "drachenstall",
]

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
    # — Farming-Drop 2026-05-26 — wilde Crops/Sträucher/Obstbäume —
    "strawberry_bush": {"blocking": False},
    "blueberry_bush":  {"blocking": False},
    "blackberry_bush": {"blocking": False},
    "raspberry_bush":  {"blocking": False},
    "apple_tree":      {"blocking": True},
    "pear_tree":       {"blocking": True},
    "plum_tree":       {"blocking": True},
    "cherry_tree":     {"blocking": True},
    "carrot_plant":    {"blocking": False},
    "potato_plant":    {"blocking": False},
    "cucumber_plant":  {"blocking": False},
    "tomato_plant":    {"blocking": False},
    "onion_plant":     {"blocking": False},
    "cabbage_plant":   {"blocking": False},
    "pumpkin_plant":   {"blocking": False},
    "corn_plant":      {"blocking": False},
    "wheat_seedling":  {"blocking": False},
    "wheat_grown":     {"blocking": False},
    # Welle 23 — Gilden-Strukturen (in Capital + größeren Towns)
    "mage_guild":     {"blocking": True},
    "fighters_guild": {"blocking": True},
    "healers_guild":  {"blocking": True},
    "thieves_guild":  {"blocking": True},
    "temple":         {"blocking": True},
    # Welle 23 — Quest-Board (Capital + Spieler-Siedlungen)
    "quest_board":    {"blocking": True},
    # — Asset-Drop 2026-05-27b: Farm-Gebäude (groß) —
    "barn_large":          {"blocking": True},
    "barn_small":          {"blocking": True},
    "cow_shed":            {"blocking": True},
    "pigsty":              {"blocking": True},
    "henhouse":            {"blocking": True},
    "goat_pen":            {"blocking": True},
    "sheepfold":           {"blocking": True},
    "stable":              {"blocking": True},
    "dovecote":            {"blocking": True},
    "dairy_house":         {"blocking": True},
    "granary":             {"blocking": True},
    "hayloft":             {"blocking": True},
    "smokehouse":          {"blocking": True},
    "cart_shed":           {"blocking": True},
    "duck_pond":           {"blocking": False},
    "goose_pasture_marker":{"blocking": False},
    # Farm-Props
    "feed_trough":         {"blocking": True},
    "water_trough":        {"blocking": True},
    "hay_bale":            {"blocking": True},
    "hay_stack":           {"blocking": True},
    "straw_bale":          {"blocking": True},
    "cheese_press":        {"blocking": True},
    "butter_churn":        {"blocking": True},
    "milking_stool":       {"blocking": False},
    "nesting_box_egg":     {"blocking": False},
    "cheese_rack":         {"blocking": True},
    "wooden_fence_segment":{"blocking": True},
    "fence_gate_farm":     {"blocking": True},
}

# Welle 51 — alle Sign-Varianten als platzierbare Strukturen registrieren.
for _slug in SIGN_SLUGS:
    STRUCTURE_TYPES[f"sign_{_slug}"] = {"blocking": False}
del _slug

VALID_MATERIALS = {"stone", "wood", "straw"}
DEFAULT_MATERIAL = "stone"

# ─── Welle 25: Struktur-HP-System ─────────────────────────────────────────
# Pro Strukturtyp die Combat-Max-HP. Strukturen die NICHT in dieser Tabelle
# stehen, sind "harvest-only" (Trees, Pflanzen, Felsen) und können nicht
# als Combat-Ziel angegriffen werden — ihre durability bleibt für Harvest.
STRUCTURE_MAX_HP = {
    # Wände & Tore — Festungs-Material
    "wall":              50,
    "floor":             30,
    "door_wood":         40,
    "door_iron":         80,
    "door_stone":        70,
    "door_reinforced":   100,
    "door_wood_open":    40,
    "door_iron_open":    80,
    "door_stone_open":   70,
    "garden_gate_ew_closed": 25, "garden_gate_ew_open": 25,
    "garden_gate_ns_closed": 25, "garden_gate_ns_open": 25,
    "fence":             18,
    "wooden_fence_segment": 18,
    "fence_gate_farm":   20,
    # Möbel / Produktions-Stationen
    "chest":             40,
    "workbench":         35,
    "furnace":           50,
    "anvil":             60,
    "bed":               20,
    "well":              80,
    "campfire":          15,
    # Welt-Deko / Container
    "barrel":            18,
    "crate":             18,
    "sack":              10,
    "marker":            12,
    "spike_trap":        15,
    "poison_trap":       15,
    "stairs_down":       40,
    "stairs_wood_up":    25, "stairs_wood_down":  25,
    "stairs_stone_up":   40, "stairs_stone_down": 40,
    "camp_tent":         15,
    "cooking_pot":       15,
    # Ruinen — schon halb-kaputt
    "ruin_pillar":       25,
    "rubble":            10,
    "statue_broken":     35,
    "gravestone":        40,
    # Dock/Boat
    "dock_corner":       20, "dock_straight": 20,
    "wooden_bridge":     30,
    "boat_small":        40, "shipwreck": 25,
    "anchor":            20, "fishing_net": 8,
    "driftwood":         10, "broken_cart": 20,
    # Farm-Gebäude — solide
    "barn_large":        90, "barn_small":   60,
    "cow_shed":          55, "pigsty":       50,
    "henhouse":          35, "goat_pen":     45,
    "sheepfold":         50, "stable":       70,
    "dovecote":          40, "dairy_house":  55,
    "granary":           80, "hayloft":      60,
    "smokehouse":        50, "cart_shed":    55,
    # Farm-Props (kleiner)
    "feed_trough":       15, "water_trough": 18,
    "hay_bale":          12, "hay_stack":     12,
    "straw_bale":        10, "cheese_press":  20,
    "butter_churn":      18, "milking_stool":  8,
    "nesting_box_egg":   10, "cheese_rack":   15,
    # Gilden / Tempel / Quest-Board — eher unzerstörbar (sehr hoch)
    "mage_guild":        500, "fighters_guild": 500,
    "healers_guild":     500, "thieves_guild":  500,
    "temple":            500, "quest_board":     80,
}

# Material-Multiplier auf max_hp — Stein zäh, Holz mittel, Stroh weich.
MATERIAL_HP_MULT = {"stone": 1.5, "wood": 1.0, "straw": 0.6}

# Material-Damage-Resistance gegen verschiedene Damage-Quellen (Spielerwaffen).
# Stein hart gegen Edge (Schwert/Axt), anfällig gegen Blunt (Mace/Hammer).
# Holz: andersrum. Stroh: alles geht.
MATERIAL_RESIST = {
    # material → {edge_dr, blunt_dr, magic_dr}, jeweils 0..1 (Damage-Reduktion)
    "stone": {"edge": 0.55, "blunt": 0.10, "magic": 0.30},
    "wood":  {"edge": 0.15, "blunt": 0.30, "magic": 0.20},
    "straw": {"edge": 0.00, "blunt": 0.00, "magic": 0.00},
}


def structure_max_hp(type_: str, material: str = DEFAULT_MATERIAL) -> int:
    """Berechnet max-HP für einen Strukturtyp + Material. None wenn die
    Struktur nicht im Combat-HP-System ist (Trees/Pflanzen → bleibt harvest)."""
    base = STRUCTURE_MAX_HP.get(type_)
    if base is None:
        return 0
    mult = MATERIAL_HP_MULT.get(material, 1.0)
    return max(1, int(round(base * mult)))


def is_combat_structure(type_: str) -> bool:
    """True wenn diese Struktur angegriffen/repariert werden kann.
    False = harvest-only (Trees, Pflanzen, Felsen)."""
    return type_ in STRUCTURE_MAX_HP


def player_damage_class(weapon_kind: str | None) -> str:
    """Damage-Klasse einer Waffe vs Strukturen: edge/blunt/magic.

    Edge = Schwert/Axt/Speer/Dolch/Sense — gut gegen Holz, schwach gegen Stein.
    Blunt = Mace/Hammer — gut gegen Stein.
    Magic = Staff/Wand — neutral.
    """
    if weapon_kind is None:
        return "blunt"   # Faust = blunt
    EDGE = {"sword","axe","greatsword","spear","throwing_knife","scythe","dagger"}
    BLUNT = {"mace","hammer"}
    MAGIC = {"staff","wand","bow","crossbow"}
    if weapon_kind in EDGE:  return "edge"
    if weapon_kind in BLUNT: return "blunt"
    if weapon_kind in MAGIC: return "magic"
    return "blunt"


def apply_material_resist(material: str, raw_dmg: int, dmg_class: str) -> int:
    """Wendet Material-DR auf Roh-Schaden gegen Struktur an. Min 1."""
    if raw_dmg <= 0:
        return 0
    resists = MATERIAL_RESIST.get(material, MATERIAL_RESIST["wood"])
    dr = resists.get(dmg_class, 0.2)
    return max(1, int(round(raw_dmg * (1 - dr))))


# ─── Welle 25: Material-Upgrade-Hierarchie ─────────────────────────────────
# Aufsteigende Reihenfolge — Spieler können hochgraden, kein Downgrade.
MATERIAL_TIER_ORDER = ["straw", "wood", "stone"]

# Material-Kosten fürs Upgrade: 2× das neue (höhere) Material pro Klick.
UPGRADE_MATERIAL_COST = 2


def material_tier(material: str) -> int:
    """Tier 0=straw, 1=wood, 2=stone. -1 wenn unbekannt."""
    try:
        return MATERIAL_TIER_ORDER.index(material)
    except ValueError:
        return -1


def next_material(material: str) -> str | None:
    """Liefert das nächst-höhere Material oder None wenn schon top-tier."""
    t = material_tier(material)
    if t < 0 or t + 1 >= len(MATERIAL_TIER_ORDER):
        return None
    return MATERIAL_TIER_ORDER[t + 1]


# ─── Welle 25: Zentrale Permission-Logik ───────────────────────────────────
# Heute: nur Owner darf eigene Strukturen modifizieren (repair/upgrade/remove).
# Forward-compat: wenn das Allianzen/Gruppen-System kommt, wird HIER erweitert
# (NICHT in jedem WS-Handler einzeln). Erwartete Erweiterung sowas wie:
#   if struct["owner"] in alliance_members_of(player_id): return True
def can_modify(player_id: str, struct: dict) -> bool:
    """Darf dieser Spieler diese Struktur modifizieren (repair/upgrade)?

    Aktuell: True nur wenn player_id == struct['owner']. System-Strukturen
    (owner='system' oder None) sind für niemanden modifizierbar. Spielerbauten
    fremder Spieler sind erst nach Allianzen-System für Verbündete freigegeben.
    """
    if struct is None:
        return False
    owner = struct.get("owner")
    if not owner or owner == "system":
        return False
    return owner == player_id

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
            "SELECT id, x, y, type, owner, material, durability, max_durability, "
            "layer, rotation FROM structures"
        )
        self._floor_by_coord.clear()
        self._object_by_coord.clear()
        for r in rows:
            # Welle 25-Migration: max_durability war evtl. 1 (DEFAULT) — backfilll
            # auf den richtigen Combat-Max wenn die Struktur HP-fähig ist.
            mdur = int(r["max_durability"] or 0)
            cdur = int(r["durability"] or 0)
            wanted_max = structure_max_hp(r["type"], r["material"])
            if wanted_max > 0 and mdur < wanted_max:
                # Backfill: existing Strukturen kriegen ihren regulären Max,
                # current durability auf max gesetzt wenn niedriger (heile Bauten
                # sollen nach Migration heile sein).
                mdur = wanted_max
                cdur = max(cdur, mdur)
                try:
                    await db.pool().execute(
                        "UPDATE structures SET durability = $1, max_durability = $2 "
                        "WHERE id = $3", cdur, mdur, r["id"])
                except Exception:
                    pass
            struct = {
                "id":             r["id"],
                "x":              r["x"],
                "y":              r["y"],
                "type":           r["type"],
                "owner":          r["owner"],
                "material":       r["material"],
                "durability":     cdur,
                "max_durability": mdur,
                "layer":          r["layer"],
                "rotation":       r["rotation"] or 0,
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
                    material: str = DEFAULT_MATERIAL, durability: int = 1,
                    rotation: int = 0) -> dict | None:
        if type_ not in STRUCTURE_TYPES:
            return None
        if material not in VALID_MATERIALS:
            material = DEFAULT_MATERIAL
        # Rotation normalisieren: nur 0/90/180/270 erlaubt
        rotation = int(rotation) % 360
        if rotation not in (0, 90, 180, 270):
            rotation = 0
        layer = _layer_for(type_)
        layer_map = self._layer_map(layer)
        if (x, y) in layer_map:
            return None  # Slot in diesem Layer ist belegt
        # Welle 25: max_durability aus STRUCTURE_MAX_HP-Tabelle. Wenn die
        # Struktur Combat-fähig ist, override current durability auf max (frische
        # Bauten sind voll-HP). Sonst bleibt durability = caller-Wert (Harvest).
        max_dur = structure_max_hp(type_, material)
        if max_dur > 0:
            durability = max_dur
        else:
            max_dur = durability  # harvest-only: max = initial
        row = await db.pool().fetchrow(
            "INSERT INTO structures (x, y, type, owner, material, durability, "
            "max_durability, layer, rotation) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id",
            x, y, type_, owner, material, durability, max_dur, layer, rotation,
        )
        struct = {
            "id":             row["id"],
            "x":              x,
            "y":              y,
            "type":           type_,
            "owner":          owner,
            "material":       material,
            "durability":     durability,
            "max_durability": max_dur,
            "layer":          layer,
            "rotation":       rotation,
        }
        layer_map[(x, y)] = struct
        return struct

    async def upgrade_material(self, x: int, y: int,
                                 layer: str | None = None) -> dict | None:
        """Welle 25: Strukturen-Material auf nächste Tier-Stufe hochsetzen.
        max_durability wird neu berechnet, durability = max (frisch).
        Returns Struktur, oder None wenn nicht upgradebar."""
        if layer is None:
            s = self._object_by_coord.get((x, y)) or self._floor_by_coord.get((x, y))
        else:
            s = self._layer_map(layer).get((x, y))
        if s is None:
            return None
        new_mat = next_material(s["material"])
        if new_mat is None:
            return None  # bereits top-tier (stone)
        new_max = structure_max_hp(s["type"], new_mat)
        if new_max <= 0:
            return None  # nicht Combat-fähig — sollte nie passieren wenn caller is_combat_structure prüft
        await db.pool().execute(
            "UPDATE structures SET material = $1, durability = $2, max_durability = $2 "
            "WHERE id = $3",
            new_mat, new_max, s["id"],
        )
        s["material"] = new_mat
        s["durability"] = new_max
        s["max_durability"] = new_max
        return s

    async def repair_structure(self, x: int, y: int, amount: int = 8,
                                layer: str | None = None) -> dict | None:
        """Erhöht durability, gecapped bei max_durability. Returns Struktur."""
        if layer is None:
            s = self._object_by_coord.get((x, y)) or self._floor_by_coord.get((x, y))
        else:
            s = self._layer_map(layer).get((x, y))
        if s is None:
            return None
        max_d = int(s.get("max_durability") or s["durability"])
        new_dur = min(max_d, int(s["durability"]) + amount)
        if new_dur == s["durability"]:
            return s  # bereits voll
        await db.pool().execute(
            "UPDATE structures SET durability = $1 WHERE id = $2", new_dur, s["id"]
        )
        s["durability"] = new_dur
        return s

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
