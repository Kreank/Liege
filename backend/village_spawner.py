"""Prozedurale Siedlungen — Stadt, Dorf, Lager.

Drei Größenstufen mit variierender Hauszahl + Hausgröße + NPC-Anzahl:

    Lager (camp):   1-2 kleine Strukturen + 2-4 Banditen, kein "Gebäude"
                    feindlich, außerhalb Settlement-Areas

    Dorf (village): 3-5 Häuser (verschiedene Größen + Typen), 3-6 Bewohner,
                    Bauernhof-Atmosphäre

    Stadt (town):   6-10 Häuser, 8-15 Bewohner, mit zentralem Brunnen,
                    Marktstand, Schmiede, Werkstatt

Haus-Typen mit Inneneinrichtung:
    house     — Wohnhaus mit Bett + (manchmal) Lagerfeuer
    shop      — Verkaufsladen mit Truhe (merchant-NPC drinnen)
    smithy    — Schmiede mit Amboss + Schmelze
    workshop  — Werkstatt mit Werkbank
    tavern    — Schenke mit mehreren Betten + Lagerfeuer
"""
import logging
import random

from world import CHUNK_SIZE

log = logging.getLogger("liege.village_spawner")

# Siedlungs-Chancen pro Chunk
SETTLEMENT_BASE_CHANCE  = 0.25       # qualifizierter Chunk → eine Siedlung?
BANDIT_CAMP_CHANCE      = 0.04       # nicht-Settlement-Chunk → Lager?

# Settlement-Area-Threshold: bestimmt Stadt vs Dorf
SETTLEMENT_TILES_MIN_VILLAGE = 20
SETTLEMENT_TILES_MIN_TOWN    = 60

# Hauszahl pro Siedlung
HOUSE_COUNT_VILLAGE = (3, 5)
HOUSE_COUNT_TOWN    = (6, 10)

# NPCs pro Siedlung (pro Haus + Extra)
NPC_PER_HOUSE_VILLAGE = (0.8, 1.4)   # multipliziert mit Hauszahl
NPC_PER_HOUSE_TOWN    = (1.2, 1.8)

# Haus-Größen — (innen_w, innen_h, Wahrscheinlichkeit-Weight)
HOUSE_SIZE_VARIANTS = [
    (2, 2, 30),   # Mini-Hütte 4×4 mit Wänden
    (3, 2, 30),   # Kleines Haus
    (3, 3, 20),   # Mittel
    (4, 3, 12),   # Groß
    (5, 4, 5),    # Sehr groß (selten)
    (4, 4, 3),    # Quadratisch groß
]

# Haus-Typen mit gewichteten Spawn-Chancen pro Siedlungs-Stufe
HOUSE_TYPES_VILLAGE = [
    ("house",     60),  # einfaches Wohnhaus
    ("smithy",    15),  # Schmiede
    ("workshop",  15),  # Werkstatt
    ("shop",      10),  # Laden
]
HOUSE_TYPES_TOWN = [
    ("house",     40),
    ("smithy",    15),
    ("workshop",  15),
    ("shop",      20),
    ("tavern",    10),
]

# NPC-Pool pro Haustyp — Asset-Drop 2026-05-27 ergänzt um Handwerks-/Dorf-Rollen.
# Mehrfache Listings für gleiche Rollen sind Absicht — random.choice gewichtet
# häufige Bewohner stärker.
NPC_KIND_BY_HOUSE = {
    "house":     ["villager", "farmer", "wanderer", "hermit", "peasant",
                  "woodcutter", "hunter", "fisher", "priest"],
    "shop":      ["merchant", "baker", "tailor"],
    "smithy":    ["blacksmith", "carpenter"],
    "workshop":  ["scholar", "mage", "scribe", "carpenter", "tailor"],
    "tavern":    ["bard", "merchant", "villager", "innkeeper"],
}

VILLAGER_NAMES = [
    "Alric", "Bertha", "Cuno", "Delia", "Edrick", "Frida", "Gorm", "Hilde",
    "Ivar", "Jana", "Korbin", "Liesel", "Mirek", "Nara", "Otto", "Pavla",
    "Quintus", "Rosa", "Stefan", "Tilda", "Ulrich", "Vesna", "Wendel", "Xara",
    "Yorik", "Zenta", "Aldric", "Brunhilde", "Conrad", "Dorothea",
]
VILLAGER_BACKSTORIES = {
    "house":    [
        "Lebt seit Jahren in diesem Weiler und kümmert sich um den Hof.",
        "Hier geboren, hier bleibend. Kennt jeden Pfad in der Umgebung.",
        "Ein einfacher Bewohner, freundlich aber zurückhaltend.",
        "Hat die Hütte vom Großvater geerbt und hütet sie sorgsam.",
        "Bestellt das Feld vor dem Haus und kennt jede Pflanze beim Namen.",
    ],
    "guard":    [
        "Wacht über die Siedlung — Tag und Nacht, immer aufmerksam.",
        "Hat schon manchen Banditen-Überfall abgewehrt.",
        "Trägt die Rüstung mit Stolz und Verantwortung.",
    ],
    "healer":   [
        "Versorgt die Wunden der Bewohner mit Kräutern und ruhiger Hand.",
        "Hat das Wissen alter Heilkunst von einer wandernden Frau gelernt.",
        "Nie ohne ihren Tränke-Beutel — und ein freundliches Wort.",
    ],
    "quest_giver":[
        "Hat Aufträge für die, die mutig genug sind, sie anzunehmen.",
        "Sucht zuverlässige Helfer für Aufgaben, die niemand sonst will.",
        "Spricht leise, aber die Augen verraten viel Erfahrung.",
    ],
    "mage":     [
        "Studiert die alten Schriften und brütet über Runen-Rätseln.",
        "Hat einen Kreis aus Kristallen in seinem Zimmer — frag nicht warum.",
        "Spricht selten, doch wenn, dann mit Bedacht.",
    ],
    "shop":     [
        "Verkauft, was Reisende brauchen — und etwas mehr für die richtige Münze.",
        "Hat eine ganze Karawane Waren angeschleppt und macht sein Geschäft hier.",
        "Klüger im Handel als die meisten — und gewitzter als gewünscht.",
    ],
    "smithy":   [
        "Hämmert tagein, tagaus am Eisen. Das Donnern hört nie auf.",
        "Schmiedet Waffen und Werkzeug, seit er denken kann.",
        "Ein wortkarger Schmied mit kräftigen Armen.",
    ],
    "workshop": [
        "Tüftler und Erfinder — seine Werkstatt ist voller Pläne.",
        "Bastelt an Dingen, die sonst niemand versteht.",
        "Hat Augen, die zu viel gesehen haben — und doch noch suchen.",
    ],
    "tavern":   [
        "Erzählt jedem Gast die Geschichte vom Drachen im Tal.",
        "Schenkt Met und Bier aus, hört zu, lacht laut.",
        "Singt jede Nacht ein altes Lied, das niemand kennt.",
    ],
}

BANDIT_NAMES = [
    "Schwarzklinge", "Narbenkopf", "Galgen-Jorg", "Rasselbein", "Aas-Mira",
    "Klauenfuß", "Dunkelmaul", "Eisenfaust", "Stachelhaar", "Wolfszahn",
]
BANDIT_BACKSTORY = [
    "Ein Räuber, der am Lager hockt und auf Reisende wartet.",
    "Mitglied einer kleinen Banditengruppe — gefährlich und schnell.",
    "Verkommen und brutal. Lebt vom Überfall auf Wanderer.",
    "Vertrieben aus jedem Dorf, das er kannte. Schlägt jetzt zurück.",
]


# — Helpers ————————————————————————————————————————————————————————————————

def _weighted_pick(weighted_list):
    """[(kind, weight), ...] → kind"""
    kinds = [k for k, _ in weighted_list]
    weights = [w for _, w in weighted_list]
    return random.choices(kinds, weights=weights, k=1)[0]


def _pick_house_size():
    weighted = [(s, w) for s, _, w in [(s, s, w) for s, _, w in [(sw, 0, w) for sw, _, w in [(t, 0, w) for t, _, w in [(t[:2], 0, t[2]) for t in HOUSE_SIZE_VARIANTS]]]]]
    # Simpler: direkt aus HOUSE_SIZE_VARIANTS picken
    items = [((w, h), wt) for (w, h, wt) in HOUSE_SIZE_VARIANTS]
    return _weighted_pick(items)


async def _collect_settlement_tiles(world, cx: int, cy: int) -> list[tuple[int, int]]:
    """Sammelt alle walkable Settlement-Area-Tiles im Chunk."""
    chunk = await world.get_chunk(cx, cy)
    out: list[tuple[int, int]] = []
    for ly in range(CHUNK_SIZE):
        for lx in range(CHUNK_SIZE):
            wx = cx * CHUNK_SIZE + lx
            wy = cy * CHUNK_SIZE + ly
            tile = chunk[ly][lx]
            if tile in (0, 4, 7):  # WATER, MOUNTAIN, LAVA
                continue
            if world.is_settlement_area(wx, wy):
                out.append((wx, wy))
    return out


async def _can_place(structure_manager, world, x: int, y: int) -> bool:
    if structure_manager.at(x, y) is not None:
        return False
    if not world.is_walkable_sync(x, y):
        return False
    return True


def _bounding_box(tiles: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [t[0] for t in tiles]
    ys = [t[1] for t in tiles]
    return (min(xs), min(ys), max(xs), max(ys))


async def _place_house(world, structure_manager, npc_manager, connection_manager,
                       origin_x: int, origin_y: int, inner_w: int, inner_h: int,
                       house_type: str, material: str) -> tuple[list[dict], list[dict]]:
    """Platziert ein Haus an (origin_x, origin_y) als linke obere Ecke der Wand.
    Returns (placed_structures, spawned_npcs).
    """
    placed: list[dict] = []
    spawned_npcs: list[dict] = []
    width = inner_w + 2   # mit Außenwänden
    height = inner_h + 2

    # Tür zufällig wählen (an einer der 4 Seiten) — bevorzugt Süd
    door_side = random.choices(
        ["south", "north", "east", "west"], weights=[55, 15, 15, 15],
    )[0]
    if door_side == "south":
        door_dx = random.randint(1, inner_w)
        door_x, door_y = origin_x + door_dx, origin_y + height - 1
    elif door_side == "north":
        door_dx = random.randint(1, inner_w)
        door_x, door_y = origin_x + door_dx, origin_y
    elif door_side == "east":
        door_dy = random.randint(1, inner_h)
        door_x, door_y = origin_x + width - 1, origin_y + door_dy
    else:
        door_dy = random.randint(1, inner_h)
        door_x, door_y = origin_x, origin_y + door_dy

    # Wände + Boden
    for ly in range(height):
        for lx in range(width):
            x = origin_x + lx
            y = origin_y + ly
            is_edge = (lx == 0 or lx == width - 1 or ly == 0 or ly == height - 1)
            is_door = (x == door_x and y == door_y)
            if is_door:
                # Tür-Öffnung: lass Floor liegen (kein Wall)
                if await _can_place(structure_manager, world, x, y):
                    s = await structure_manager.place(x, y, "floor", "system",
                                                       material=material, durability=15)
                    if s: placed.append(s)
                continue
            kind = "wall" if is_edge else "floor"
            dur = 25 if kind == "wall" else 12
            if not await _can_place(structure_manager, world, x, y):
                continue
            s = await structure_manager.place(x, y, kind, "system",
                                               material=material, durability=dur)
            if s: placed.append(s)

    # Inneneinrichtung — pro Haus-Typ
    inner_x = origin_x + 1
    inner_y = origin_y + 1
    # Schon-belegt-Tracking innerhalb des Hauses
    occupied: set[tuple[int, int]] = set()

    async def _try_place(rx: int, ry: int, kind: str, dur: int = 8):
        x, y = inner_x + rx, inner_y + ry
        if (x, y) in occupied:
            return None
        if not (0 <= rx < inner_w and 0 <= ry < inner_h):
            return None
        # Floor existiert schon → nur eigenes Möbel drauf
        # structure_manager.at gibt jetzt floor zurück; wir überschreiben es?
        # Floor blockiert nicht. Aber `place` verhindert Doppel-Place auf gleicher Koord.
        # Pragmatic: floor entfernen + möbel platzieren ist zu aufwendig — Möbel direkt
        # platzieren würde fehlschlagen. Lösung: floor da lassen, Möbel als zweites
        # struct an gleicher Position geht nicht. → Möbel direkt setzen, floor weg.
        # Aber Welle 8 hat das so gemacht: place floor an den Stellen. Lass mich
        # einfach Floor vorher nicht platzieren wo Möbel hinkommen.
        occupied.add((x, y))
        # Bestehendes floor entfernen (vorher gesetzt)
        existing = structure_manager.at(x, y)
        if existing is not None:
            # Nur entfernen wenn floor
            if existing["type"] == "floor":
                await structure_manager.remove(x, y)
        s = await structure_manager.place(x, y, kind, "system",
                                           material=material, durability=dur)
        return s

    if house_type == "house":
        s = await _try_place(0, 0, "bed", 10)
        if s: placed.append(s)
        if random.random() < 0.5:
            s = await _try_place(inner_w - 1, inner_h - 1, "campfire", 8)
            if s: placed.append(s)
    elif house_type == "smithy":
        s = await _try_place(0, 0, "anvil", 30)
        if s: placed.append(s)
        s = await _try_place(0, 1, "furnace", 30)
        if s: placed.append(s)
        if inner_w >= 3:
            s = await _try_place(inner_w - 1, 0, "chest", 15)
            if s: placed.append(s)
    elif house_type == "workshop":
        s = await _try_place(0, 0, "workbench", 25)
        if s: placed.append(s)
        if inner_w >= 3:
            s = await _try_place(inner_w - 1, 0, "chest", 15)
            if s: placed.append(s)
        if random.random() < 0.4:
            s = await _try_place(0, inner_h - 1, "bed", 10)
            if s: placed.append(s)
    elif house_type == "shop":
        s = await _try_place(0, 0, "chest", 15)
        if s: placed.append(s)
        if inner_w >= 3:
            s = await _try_place(inner_w - 1, 0, "chest", 15)
            if s: placed.append(s)
        if random.random() < 0.5:
            s = await _try_place(inner_w // 2, inner_h - 1, "bed", 10)
            if s: placed.append(s)
    elif house_type == "tavern":
        # mehrere Betten + Lagerfeuer
        bed_positions = [(0, 0), (inner_w - 1, 0)]
        if inner_h > 2:
            bed_positions.append((0, inner_h - 1))
            bed_positions.append((inner_w - 1, inner_h - 1))
        for rx, ry in bed_positions[:random.randint(2, 4)]:
            s = await _try_place(rx, ry, "bed", 10)
            if s: placed.append(s)
        # Lagerfeuer in Mitte (falls Platz)
        if inner_w >= 3 and inner_h >= 3:
            s = await _try_place(inner_w // 2, inner_h // 2, "campfire", 8)
            if s: placed.append(s)

    # NPC spawnen — passend zum Haustyp
    npc_kinds = NPC_KIND_BY_HOUSE.get(house_type, ["wanderer"])
    backstories = VILLAGER_BACKSTORIES.get(house_type, VILLAGER_BACKSTORIES["house"])
    npc_count = 2 if house_type == "tavern" else 1
    for _ in range(npc_count):
        # Spawn nahe Tür (außerhalb)
        if door_side == "south":
            sx, sy = door_x, door_y + 1
        elif door_side == "north":
            sx, sy = door_x, door_y - 1
        elif door_side == "east":
            sx, sy = door_x + 1, door_y
        else:
            sx, sy = door_x - 1, door_y
        # Wenn nicht walkable, fallback ins Innere
        if not world.is_walkable_sync(sx, sy):
            sx, sy = inner_x + inner_w // 2, inner_y + inner_h // 2
        if not world.is_walkable_sync(sx, sy):
            continue
        kind = random.choice(npc_kinds)
        name = random.choice(VILLAGER_NAMES)
        backstory = random.choice(backstories)
        try:
            npc = await npc_manager.create(
                name=name, kind=kind, x=sx, y=sy,
                backstory=backstory, max_hp=50,
            )
            spawned_npcs.append(npc)
        except Exception:
            log.exception("Haus-NPC-Spawn fehlgeschlagen (%d,%d)", sx, sy)

    return placed, spawned_npcs


def _layout_houses(area_x: int, area_y: int, area_w: int, area_h: int,
                   house_count: int) -> list[tuple[int, int, int, int, str]]:
    """Sucht nicht-überlappende Haus-Positionen in einer Bounding-Box.
    Returns Liste (origin_x, origin_y, inner_w, inner_h, house_type).
    """
    placed: list[tuple[int, int, int, int]] = []  # (x, y, w, h) Bounding-Boxes
    out: list[tuple[int, int, int, int, str]] = []
    max_attempts = house_count * 12

    house_types_pool = HOUSE_TYPES_TOWN if house_count >= 6 else HOUSE_TYPES_VILLAGE

    for _ in range(max_attempts):
        if len(out) >= house_count:
            break
        inner_w, inner_h = _pick_house_size()
        # Mit Padding (1 Tile Gasse zwischen Häusern)
        w = inner_w + 2 + 1   # +Tür-Padding
        h = inner_h + 2 + 1
        if w > area_w or h > area_h:
            continue
        x = area_x + random.randint(0, area_w - w)
        y = area_y + random.randint(0, area_h - h)
        # Overlap-Check
        overlap = False
        for (px, py, pw, ph) in placed:
            if not (x + w <= px or px + pw <= x or y + h <= py or py + ph <= y):
                overlap = True
                break
        if overlap:
            continue
        house_type = _weighted_pick(house_types_pool)
        out.append((x, y, inner_w, inner_h, house_type))
        placed.append((x, y, w, h))
    return out


async def _broadcast_all(connection_manager, structures: list[dict],
                         npcs: list[dict]) -> None:
    if not connection_manager.get_players():
        return
    for s in structures:
        await connection_manager.broadcast({"type": "structure_placed", "structure": s})
    for npc in npcs:
        await connection_manager.broadcast({"type": "npc_spawned", "npc": npc})


# — Public API ————————————————————————————————————————————————————————————

async def try_spawn_settlement(world, structure_manager, npc_manager,
                                connection_manager, cx: int, cy: int) -> int:
    """Versucht eine Stadt oder ein Dorf zu platzieren — Größe ergibt sich
    aus verfügbarer Settlement-Area. Returns # placed structures."""
    tiles = await _collect_settlement_tiles(world, cx, cy)
    if len(tiles) < SETTLEMENT_TILES_MIN_VILLAGE:
        return 0
    if random.random() >= SETTLEMENT_BASE_CHANCE:
        return 0

    # Bounding-Box der Settlement-Area
    min_x, min_y, max_x, max_y = _bounding_box(tiles)
    area_w = max_x - min_x + 1
    area_h = max_y - min_y + 1

    # Stadt vs Dorf entscheiden
    if len(tiles) >= SETTLEMENT_TILES_MIN_TOWN and area_w >= 16 and area_h >= 16:
        kind = "town"
        house_count = random.randint(*HOUSE_COUNT_TOWN)
        npc_factor = random.uniform(*NPC_PER_HOUSE_TOWN)
    else:
        kind = "village"
        house_count = random.randint(*HOUSE_COUNT_VILLAGE)
        npc_factor = random.uniform(*NPC_PER_HOUSE_VILLAGE)

    # Materialien-Mix pro Siedlung (für visuelle Variation)
    material = random.choices(["wood", "stone", "straw"], weights=[55, 30, 15], k=1)[0]

    house_layouts = _layout_houses(min_x, min_y, area_w, area_h, house_count)
    if not house_layouts:
        return 0

    all_placed: list[dict] = []
    all_npcs: list[dict] = []

    for (hx, hy, hiw, hih, htype) in house_layouts:
        # Material pro Haus leicht variieren (60% Hauptmaterial, sonst zufällig)
        if random.random() < 0.6:
            mat = material
        else:
            mat = random.choice(["wood", "stone", "straw"])
        placed, npcs = await _place_house(
            world, structure_manager, npc_manager, connection_manager,
            hx, hy, hiw, hih, htype, mat,
        )
        all_placed.extend(placed)
        all_npcs.extend(npcs)

    # Zentrales Feature: Stadt bekommt Brunnen + Wachen + Quest-Giver
    if kind == "town":
        well_x = min_x + area_w // 2
        well_y = min_y + area_h // 2
        if await _can_place(structure_manager, world, well_x, well_y):
            s = await structure_manager.place(well_x, well_y, "well", "system",
                                                material="stone", durability=20)
            if s: all_placed.append(s)
        if await _can_place(structure_manager, world, well_x + 1, well_y):
            s = await structure_manager.place(well_x + 1, well_y, "chest", "system",
                                                material="wood", durability=15)
            if s: all_placed.append(s)
        # 2 Wachen an Stadtgrenzen + 1 Quest-Giver am Brunnen
        for guard_pos in [(min_x + 2, min_y + 2), (max_x - 2, max_y - 2)]:
            sx, sy = guard_pos
            if world.is_walkable_sync(sx, sy) and structure_manager.at(sx, sy) is None:
                try:
                    npc = await npc_manager.create(
                        name=random.choice(VILLAGER_NAMES),
                        kind="guard", x=sx, y=sy,
                        backstory=random.choice(VILLAGER_BACKSTORIES["guard"]),
                        max_hp=80,
                    )
                    all_npcs.append(npc)
                except Exception:
                    log.exception("Wache-Spawn fehlgeschlagen")
        # Quest-Giver
        qg_x, qg_y = well_x - 1, well_y
        if world.is_walkable_sync(qg_x, qg_y) and structure_manager.at(qg_x, qg_y) is None:
            try:
                npc = await npc_manager.create(
                    name=random.choice(VILLAGER_NAMES),
                    kind="quest_giver", x=qg_x, y=qg_y,
                    backstory=random.choice(VILLAGER_BACKSTORIES["quest_giver"]),
                    max_hp=50,
                )
                all_npcs.append(npc)
            except Exception:
                log.exception("Quest-Giver-Spawn fehlgeschlagen")
        # Heiler in der Stadt (nahe Brunnen)
        for dx, dy in [(0, 1), (1, 1), (-1, 1)]:
            sx, sy = well_x + dx, well_y + dy
            if world.is_walkable_sync(sx, sy) and structure_manager.at(sx, sy) is None:
                try:
                    npc = await npc_manager.create(
                        name=random.choice(VILLAGER_NAMES),
                        kind="healer", x=sx, y=sy,
                        backstory=random.choice(VILLAGER_BACKSTORIES["healer"]),
                        max_hp=45,
                    )
                    all_npcs.append(npc)
                    break
                except Exception:
                    pass

    # Extra wandernde NPCs (Marktbesucher / Kinder etc.)
    extra_npc_count = max(0, int(len(house_layouts) * npc_factor) - len(all_npcs))
    for _ in range(extra_npc_count):
        sx = random.randint(min_x, max_x)
        sy = random.randint(min_y, max_y)
        if not world.is_walkable_sync(sx, sy):
            continue
        if structure_manager.at(sx, sy) is not None:
            continue
        kind_pick = random.choice(["wanderer", "bard", "hermit", "scholar"])
        try:
            npc = await npc_manager.create(
                name=random.choice(VILLAGER_NAMES),
                kind=kind_pick, x=sx, y=sy,
                backstory=random.choice(VILLAGER_BACKSTORIES["house"]),
                max_hp=50,
            )
            all_npcs.append(npc)
        except Exception:
            log.exception("Extra-NPC-Spawn fehlgeschlagen (%d,%d)", sx, sy)

    await _broadcast_all(connection_manager, all_placed, all_npcs)
    log.info(
        "%s in Chunk (%d,%d) gespawnt: %d Häuser, %d Strukturen, %d NPCs",
        kind.upper(), cx, cy, len(house_layouts), len(all_placed), len(all_npcs),
    )
    return len(all_placed)


async def try_spawn_bandit_camp(world, structure_manager, npc_manager,
                                 connection_manager, cx: int, cy: int) -> int:
    """Räuber-Lager außerhalb von Siedlungsgebieten — KEIN echtes Gebäude,
    nur Camp-Reste + 2-4 Banditen."""
    if random.random() >= BANDIT_CAMP_CHANCE:
        return 0
    chunk = await world.get_chunk(cx, cy)
    candidates: list[tuple[int, int]] = []
    for ly in range(CHUNK_SIZE):
        for lx in range(CHUNK_SIZE):
            wx = cx * CHUNK_SIZE + lx
            wy = cy * CHUNK_SIZE + ly
            tile = chunk[ly][lx]
            if tile in (0, 4, 7):
                continue
            if world.is_settlement_area(wx, wy):
                continue
            candidates.append((wx, wy))
    if not candidates:
        return 0

    cx_tile, cy_tile = random.choice(candidates)
    placed: list[dict] = []

    # Lagerfeuer im Zentrum
    if await _can_place(structure_manager, world, cx_tile, cy_tile):
        s = await structure_manager.place(cx_tile, cy_tile, "campfire", "system",
                                            material="wood", durability=5)
        if s: placed.append(s)

    # 2-3 Zelte um's Feuer
    tent_positions = [(-2, 1), (2, 1), (-2, -1), (2, -1), (0, 2), (0, -2)]
    random.shuffle(tent_positions)
    for dx, dy in tent_positions[:random.randint(2, 3)]:
        x, y = cx_tile + dx, cy_tile + dy
        if await _can_place(structure_manager, world, x, y):
            s = await structure_manager.place(x, y, "camp_tent", "system",
                                                material="wood", durability=2)
            if s: placed.append(s)

    # Cooking-Pot + Crate
    for dx, dy, kind, dur in [
        (1, -1, "cooking_pot", 1),
        (-1, -1, "crate", 2),
        (1, 1, "barrel", 2),
    ]:
        x, y = cx_tile + dx, cy_tile + dy
        if await _can_place(structure_manager, world, x, y):
            s = await structure_manager.place(x, y, kind, "system",
                                                material="wood", durability=dur)
            if s: placed.append(s)

    # 2-4 Banditen verteilt
    bandit_count = random.randint(2, 4)
    spawn_offsets = [(-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3), (3, 3), (-3, 3), (3, -3)]
    random.shuffle(spawn_offsets)
    npcs_spawned: list[dict] = []
    for dx, dy in spawn_offsets[:bandit_count]:
        sx, sy = cx_tile + dx, cy_tile + dy
        if not world.is_walkable_sync(sx, sy):
            continue
        if structure_manager.at(sx, sy) is not None:
            continue
        try:
            npc = await npc_manager.create(
                name=random.choice(BANDIT_NAMES),
                kind="bandit", x=sx, y=sy,
                backstory=random.choice(BANDIT_BACKSTORY),
                max_hp=45,
            )
            npcs_spawned.append(npc)
        except Exception:
            log.exception("Banditen-Spawn fehlgeschlagen (%d,%d)", sx, sy)

    await _broadcast_all(connection_manager, placed, npcs_spawned)
    if placed:
        log.info("Räuber-Lager in Chunk (%d,%d): %d Strukturen, %d Banditen",
                 cx, cy, len(placed), len(npcs_spawned))
    return len(placed)


# Backwards-compat: alter Name "try_spawn_village" delegiert auf neuen Spawner
async def try_spawn_village(world, structure_manager, npc_manager,
                             connection_manager, cx: int, cy: int) -> int:
    return await try_spawn_settlement(
        world, structure_manager, npc_manager, connection_manager, cx, cy,
    )
