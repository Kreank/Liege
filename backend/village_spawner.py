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
HOUSE_COUNT_VILLAGE = (5, 8)     # Welle 23: min 5 Häuser (vorher 3) für mehr Vielfalt
HOUSE_COUNT_TOWN    = (8, 14)
HOUSE_COUNT_CAPITAL = (22, 30)   # Welle 23: Königreich am Welt-Spawn

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
    ("house",     50),
    ("smithy",    18),
    ("workshop",  16),
    ("shop",      10),
    ("tavern",     6),
]
HOUSE_TYPES_TOWN = [
    ("house",     35),
    ("smithy",    13),
    ("workshop",  13),
    ("shop",      18),
    ("tavern",    13),
    ("mage_guild",     4),
    ("fighters_guild", 4),
]
# Welle 23: Capital-Haustypen — Königreich mit allen Distrikten
HOUSE_TYPES_CAPITAL = [
    ("house",          25),
    ("shop",           18),
    ("smithy",         12),
    ("workshop",       12),
    ("tavern",         10),
    ("mage_guild",      6),
    ("fighters_guild",  6),
    ("healers_guild",   5),
    ("thieves_guild",   3),
    ("temple",          3),
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
    # Welle 23: Gilden-Strukturen — Gilden-Master + ein Gilden-Mitglied
    "mage_guild":     ["mage", "scholar"],
    "fighters_guild": ["guard", "soldier"],
    "healers_guild":  ["healer", "priest"],
    "thieves_guild":  ["thief"],   # nur Diebe leben in der Diebesgilde
    "temple":         ["priest", "healer"],
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
    # Welle 23 — Gilden-Backstories
    "mage_guild": [
        "Gildenmeister der Magier — kennt Sprüche, die die Wirklichkeit beugen.",
        "Bewahrt die Schriften der alten Mysterien und unterrichtet Schüler.",
        "Trägt einen Stab aus dunklem Holz — und Augen wie kaltes Feuer.",
    ],
    "fighters_guild": [
        "Kommandant der Kriegerakademie — drillt die nächste Generation.",
        "Hat in 100 Schlachten gestanden, will jetzt nur noch lehren.",
        "Eine lebende Legende mit narbigen Händen und ruhigem Blick.",
    ],
    "healers_guild": [
        "Erzheilerin der Gilde — kennt jede Pflanze, jede Krankheit, jede Wunde.",
        "Lehrt junge Heiler, was kein Buch beschreiben kann.",
        "Ihre Hände tragen Spuren von tausend gerettetem Leben.",
    ],
    "thieves_guild": [
        "Meister der Schatten — hört man kaum, sieht man nie.",
        "Verwaltet die Verbindungen, von denen keiner offen spricht.",
        "Lächelt selten, aber wenn, dann mit einer Klinge in der Hand.",
    ],
    "temple": [
        "Hoher Priester des Tempels — vermittelt zwischen Welten.",
        "Spendet Trost, Heilung und ab und zu eine harte Wahrheit.",
        "Trägt das Symbol der Götter und ein ruhiges Gemüt.",
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


# Welle 24 — Settlement-Building-Spec (siehe docu/VILLAGE_LAYOUT_SPEC.md)
SETTLEMENT_STRUCT_TYPES = {
    "wall", "floor", "door_wood", "door_iron", "door_stone",
    "door_wood_open", "door_iron_open", "door_stone_open",
    "door_reinforced", "bed", "chest", "anvil", "furnace", "workbench",
    "well", "campfire", "path", "quest_board", "cooking_pot",
    "spike_trap", "poison_trap", "farm_plot",
}


def _door_kind_for(house_type: str, material: str = "wood") -> str:
    """Welche Tür-Art für welches Haus."""
    if house_type == "smithy":
        return "door_iron"
    if house_type in ("temple", "mage_guild", "healers_guild",
                       "fighters_guild", "thieves_guild"):
        return "door_stone"
    return "door_wood"


def _floor_material(material: str) -> str:
    return "stone" if material == "stone" else "wood"


async def _cleanup_footprint(structure_manager, x0: int, y0: int,
                              w: int, h: int, padding: int = 1) -> int:
    """Entfernt alle Nicht-Settlement-Strukturen im Bereich
    (x0-padding, y0-padding) bis (x0+w+padding, y0+h+padding).
    Returns Anzahl entfernter Structures."""
    removed = 0
    for dx in range(-padding, w + padding):
        for dy in range(-padding, h + padding):
            x, y = x0 + dx, y0 + dy
            existing = structure_manager.at(x, y)
            if existing is None:
                continue
            if existing["type"] in SETTLEMENT_STRUCT_TYPES:
                continue   # Settlement-Struct bleibt
            try:
                await structure_manager.remove(x, y)
                removed += 1
            except Exception:
                pass
    return removed


def _bounding_box(tiles: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [t[0] for t in tiles]
    ys = [t[1] for t in tiles]
    return (min(xs), min(ys), max(xs), max(ys))


async def _place_house(world, structure_manager, npc_manager, connection_manager,
                       origin_x: int, origin_y: int, inner_w: int, inner_h: int,
                       house_type: str, material: str) -> tuple[list[dict], list[dict]]:
    """Platziert ein Haus an (origin_x, origin_y) als linke obere Ecke der Wand.
    Returns (placed_structures, spawned_npcs).

    Welle 24 (siehe docu/VILLAGE_LAYOUT_SPEC.md):
    1. Cleanup-Footprint (Deko entfernen)
    2. Türposition entscheiden
    3. Wände komplett (außer Tür)
    4. Tür als door_<material>
    5. Boden auf allen Innen-Tiles
    6. Tür-Vor-Zone (innen) als occupied markieren bevor Möbel kommen
    7. Möbel via _try_place
    """
    placed: list[dict] = []
    spawned_npcs: list[dict] = []
    width = inner_w + 2   # mit Außenwänden
    height = inner_h + 2

    # Eck-Tiles dürfen NIE Tür sein — randint(1, inner_w/h) hält das ein.
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

    # 1) Cleanup vor Wand-Placement: Deko aus Hausbox + 1 Tile Clearance raus
    try:
        await _cleanup_footprint(structure_manager, origin_x, origin_y,
                                   width, height, padding=1)
    except Exception:
        log.exception("Cleanup-Footprint fehlgeschlagen für %s", house_type)

    door_kind = _door_kind_for(house_type, material)
    floor_mat = _floor_material(material)

    # 2-4) Wände + Tür + Boden
    for ly in range(height):
        for lx in range(width):
            x = origin_x + lx
            y = origin_y + ly
            is_edge = (lx == 0 or lx == width - 1 or ly == 0 or ly == height - 1)
            is_door = (x == door_x and y == door_y)
            if is_door:
                # Tür: door_<material>-Struct statt floor
                if await _can_place(structure_manager, world, x, y):
                    s = await structure_manager.place(x, y, door_kind, "system",
                                                       material=material, durability=15)
                    if s: placed.append(s)
                continue
            if is_edge:
                # Wand
                if not await _can_place(structure_manager, world, x, y):
                    continue
                s = await structure_manager.place(x, y, "wall", "system",
                                                   material=material, durability=25)
                if s: placed.append(s)
            else:
                # Innen-Tile → Boden
                if not await _can_place(structure_manager, world, x, y):
                    continue
                s = await structure_manager.place(x, y, "floor", "system",
                                                   material=floor_mat, durability=12)
                if s: placed.append(s)

    # Inneneinrichtung — pro Haus-Typ
    inner_x = origin_x + 1
    inner_y = origin_y + 1
    # Schon-belegt-Tracking innerhalb des Hauses
    occupied: set[tuple[int, int]] = set()
    # Welle 24: Tür-Vor-Zone (Innen-Tile direkt an der Tür) MUSS frei bleiben,
    # damit NPCs durch die Tür passen. Vor _try_place als occupied markieren.
    if door_side == "south":
        occupied.add((door_x, door_y - 1))
    elif door_side == "north":
        occupied.add((door_x, door_y + 1))
    elif door_side == "east":
        occupied.add((door_x - 1, door_y))
    else:  # west
        occupied.add((door_x + 1, door_y))

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
    # Welle 23 — Gilden-Strukturen: jedes Gilden-Haus hat seine charakteristische
    # Interior-Struktur in der Mitte + ggf. Bett für den Meister.
    elif house_type in ("mage_guild", "fighters_guild", "healers_guild",
                         "thieves_guild", "temple"):
        # Charakteristische Interior-Struktur
        interior_struct = {
            "mage_guild":     "workbench",   # Magier brauchen Werkbank/Studierzimmer
            "fighters_guild": "anvil",        # Kriegerakademie mit Amboss
            "healers_guild":  "bed",          # Krankenbett
            "thieves_guild":  "chest",        # Beute-Truhe
            "temple":         "well",         # Heiliger Brunnen
        }.get(house_type, "chest")
        cx_inner = max(0, min(inner_w - 1, inner_w // 2))
        cy_inner = max(0, min(inner_h - 1, inner_h // 2))
        s = await _try_place(cx_inner, cy_inner, interior_struct, 12)
        if s: placed.append(s)
        # Master-Bett am Rand
        if inner_h >= 2:
            s = await _try_place(0, 0, "bed", 10)
            if s: placed.append(s)
        # Zusätzliche Truhe (Loot drinnen — wird via populate_chest gefüllt)
        if inner_w >= 3:
            chest = await _try_place(inner_w - 1, 0, "chest", 10)
            if chest:
                placed.append(chest)
                try:
                    import items as _items_mod
                    mgr = getattr(_items_mod, "_global_item_manager", None)
                    if mgr is not None:
                        # Gilden-Truhen: dungeon-tier Loot (höherwertig)
                        await mgr.populate_chest(chest["id"], "dungeon")
                except Exception:
                    log.exception("Gilden-Chest populate fehlgeschlagen")

    # NPC spawnen — passend zum Haustyp
    npc_kinds = NPC_KIND_BY_HOUSE.get(house_type, ["wanderer"])
    backstories = VILLAGER_BACKSTORIES.get(house_type, VILLAGER_BACKSTORIES["house"])
    # Tavern + Gilden bekommen 2 NPCs (Master + Gast/Mitglied)
    if house_type == "tavern":
        npc_count = 2
    elif house_type in ("mage_guild", "fighters_guild", "healers_guild",
                         "thieves_guild", "temple"):
        npc_count = 2
    else:
        npc_count = 1
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
                   house_count: int,
                   settlement_kind: str = "village",
                   ) -> list[tuple[int, int, int, int, str]]:
    """Sucht nicht-überlappende Haus-Positionen in einer Bounding-Box.
    Returns Liste (origin_x, origin_y, inner_w, inner_h, house_type).

    settlement_kind: 'village' | 'town' | 'capital' — wählt den HOUSE_TYPES-Pool.
    """
    placed: list[tuple[int, int, int, int]] = []  # (x, y, w, h) Bounding-Boxes
    out: list[tuple[int, int, int, int, str]] = []
    max_attempts = house_count * 12

    if settlement_kind == "capital":
        house_types_pool = HOUSE_TYPES_CAPITAL
    elif settlement_kind == "town" or house_count >= 6:
        house_types_pool = HOUSE_TYPES_TOWN
    else:
        house_types_pool = HOUSE_TYPES_VILLAGE

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
    aus verfügbarer Settlement-Area. Returns # placed structures.

    Welle 23: Capital-Detection — der Welt-Spawn-Chunk wird IMMER zum
    Königreich (capital), garantiert mit großer Gebäudezahl + allen
    Distrikten (Gilden, Tempel, Quest-Board).
    """
    tiles = await _collect_settlement_tiles(world, cx, cy)
    if len(tiles) < SETTLEMENT_TILES_MIN_VILLAGE:
        return 0
    # Welt-Spawn-Chunk = Königreich. Lokales chunk-koord aus WORLD_SPAWN.
    from world import CHUNK_SIZE as _CS
    try:
        import region_difficulty as _rd
        spawn_cx, spawn_cy = _rd.WORLD_SPAWN_X // _CS, _rd.WORLD_SPAWN_Y // _CS
    except Exception:
        spawn_cx, spawn_cy = 60 // _CS, 40 // _CS
    is_capital = (cx == spawn_cx and cy == spawn_cy)
    # Capital ist garantiert, normale Settlements würfeln
    if not is_capital and random.random() >= SETTLEMENT_BASE_CHANCE:
        return 0

    # Bounding-Box der Settlement-Area
    min_x, min_y, max_x, max_y = _bounding_box(tiles)
    area_w = max_x - min_x + 1
    area_h = max_y - min_y + 1

    # Capital → Town → Village
    if is_capital:
        kind = "capital"
        house_count = random.randint(*HOUSE_COUNT_CAPITAL)
        npc_factor = random.uniform(*NPC_PER_HOUSE_TOWN) * 1.3   # mehr Bewohner
        log.info("CAPITAL spawn @chunk=(%d,%d): %d Gebäude geplant",
                 cx, cy, house_count)
    elif len(tiles) >= SETTLEMENT_TILES_MIN_TOWN and area_w >= 16 and area_h >= 16:
        kind = "town"
        house_count = random.randint(*HOUSE_COUNT_TOWN)
        npc_factor = random.uniform(*NPC_PER_HOUSE_TOWN)
    else:
        kind = "village"
        house_count = random.randint(*HOUSE_COUNT_VILLAGE)
        npc_factor = random.uniform(*NPC_PER_HOUSE_VILLAGE)

    # Materialien-Mix pro Siedlung (für visuelle Variation)
    # Capital nutzt mehr stone als Wood (königlich)
    if is_capital:
        material = random.choices(["stone", "wood"], weights=[70, 30], k=1)[0]
    else:
        material = random.choices(["wood", "stone", "straw"], weights=[55, 30, 15], k=1)[0]

    house_layouts = _layout_houses(min_x, min_y, area_w, area_h, house_count,
                                     settlement_kind=kind)
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
    if kind in ("town", "capital"):
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

    # Welle 23 — Capital-spezifische Garantien
    if kind == "capital":
        center_x = min_x + area_w // 2
        center_y = min_y + area_h // 2
        # Quest-Board am Hauptplatz
        for dx, dy in [(2, 0), (-2, 0), (0, 2), (0, -2)]:
            qb_x, qb_y = center_x + dx, center_y + dy
            if await _can_place(structure_manager, world, qb_x, qb_y):
                s = await structure_manager.place(qb_x, qb_y, "quest_board",
                                                    "system", material="wood",
                                                    durability=10)
                if s:
                    all_placed.append(s)
                    break
        # Zusätzliche Wachen (4 statt 2)
        for dx, dy in [(min_x + 4, min_y + 4), (max_x - 4, min_y + 4),
                        (min_x + 4, max_y - 4), (max_x - 4, max_y - 4)]:
            sx, sy = dx, dy
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
                    log.exception("Capital-Guard-Spawn fehlgeschlagen")
        # Garantierter Königreich-Händler-Mix: baker + tailor (zusätzlich zu
        # den evtl. random aus shops)
        for npc_kind in ("baker", "tailor", "scholar", "scribe"):
            for _try in range(6):
                sx = random.randint(min_x, max_x)
                sy = random.randint(min_y, max_y)
                if not world.is_walkable_sync(sx, sy):
                    continue
                if structure_manager.at(sx, sy) is not None:
                    continue
                try:
                    npc = await npc_manager.create(
                        name=random.choice(VILLAGER_NAMES),
                        kind=npc_kind, x=sx, y=sy,
                        backstory=random.choice(VILLAGER_BACKSTORIES.get(
                            "shop", VILLAGER_BACKSTORIES["house"])),
                        max_hp=50,
                    )
                    all_npcs.append(npc)
                    break
                except Exception:
                    pass
        log.info("Capital: %d Strukturen + %d NPCs platziert",
                 len(all_placed), len(all_npcs))

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

    # Asset-Drop 2026-05-27c: Nutztiere in Siedlungen.
    # Pro Settlement: 4-10 Tiere aus einem Mix-Pool. Capital bekommt mehr.
    livestock_pool = [
        # (kind, weight) — Geflügel häufiger als Großvieh
        ("chicken_hen", 6), ("rooster", 2), ("chick", 4),
        ("duck", 3), ("goose", 2),
        ("sheep", 4), ("lamb", 2), ("ram", 1),
        ("pig", 3), ("piglet", 2),
        ("cow", 3), ("calf", 1), ("bull", 1),
        ("goat", 3), ("kid_goat", 2),
        ("horse", 2), ("foal", 1), ("donkey", 1),
        ("dog", 2), ("cat", 2),
    ]
    livestock_kinds = [k for k, w in livestock_pool for _ in range(w)]
    livestock_count = random.randint(4, 10) if kind != "capital" else random.randint(8, 16)
    for _ in range(livestock_count):
        sx = random.randint(min_x, max_x)
        sy = random.randint(min_y, max_y)
        if not world.is_walkable_sync(sx, sy):
            continue
        if structure_manager.at(sx, sy) is not None:
            continue
        animal_kind = random.choice(livestock_kinds)
        try:
            npc = await npc_manager.create(
                name=animal_kind.replace("_", " ").capitalize(),
                kind=animal_kind, x=sx, y=sy,
                backstory="Ein Nutztier auf dem Bauernhof.",
                max_hp=30,
            )
            all_npcs.append(npc)
        except Exception:
            log.exception("Livestock-Spawn fehlgeschlagen (%d,%d)", sx, sy)

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
    # Welle 23-F: Camp-Cooldown — wenn dieser Chunk vor < 30 min gewiped
    # wurde, kein neues Camp dort.
    try:
        import region_difficulty
        if await region_difficulty.is_zone_cleared_recently(cx, cy, "bandit_camp"):
            log.info("Bandit-Camp-Skip @chunk=(%d,%d) — cooldown noch aktiv", cx, cy)
            return 0
    except Exception:
        log.exception("Camp-Cooldown-Check schlug fehl")
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

    # Welle 23: Bandit-Camp-Truhe mit bandit-loot
    chest_offsets = [(2, 0), (-2, 0), (0, 2), (0, -2)]
    random.shuffle(chest_offsets)
    for dx, dy in chest_offsets:
        x, y = cx_tile + dx, cy_tile + dy
        if await _can_place(structure_manager, world, x, y):
            chest = await structure_manager.place(x, y, "chest", "system",
                                                    material="wood", durability=3)
            if chest:
                placed.append(chest)
                try:
                    import items as _items_mod
                    # ItemManager-Instanz aus globalem Modul holen
                    if hasattr(_items_mod, "_global_item_manager"):
                        mgr = _items_mod._global_item_manager
                        await mgr.populate_chest(chest["id"], "bandit")
                except Exception:
                    log.exception("Bandit-Camp Chest populate fehlgeschlagen")
            break

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
