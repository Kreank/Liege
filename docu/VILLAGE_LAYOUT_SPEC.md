# Liege Village Layout Spec

> **Status (2026-05-30):** Teilweise umgesetzt — bezieht sich auf
> `backend/village_spawner.py` (Welle 24).
>
> **Live im Code (Section 5, Schritte 1-5):**
> - `SETTLEMENT_STRUCT_TYPES`-Whitelist + `_cleanup_footprint` (Deko-Räumung
>   vor dem Bau, inkl. 1-Tile-Clearance) ✓
> - Reihenfolge in `_place_house`: Cleanup → Türposition → Wände → Tür als
>   echte `door_<kind>`-Struktur → Boden auf allen Innen-Tiles → Tür-Vor-Zone
>   (innen) als `occupied` reserviert → Möbel ✓
> - `_door_kind_for` (door_wood/iron/stone je Haustyp), `_floor_material` ✓
> - Tür bevorzugt Süd (Gewicht 55/15/15/15), Eck-Tiles nie Tür ✓
>
> **Noch offen (Backlog):**
> - `_validate_house` + Rollback (Section 3) — nicht implementiert.
> - Pfade zwischen Tür und Brunnen (Section 2.7, `_carve_path`) — fehlt;
>   town/capital bekommen nur Brunnen, keine Pfade.
> - Layout-Padding: Code nutzt noch `+2 +1` (1 Tile Gasse), Spec will `+2 +2`.
> - Boden-unter-Möbel: Code **entfernt** den Boden vor Möbel-Placement
>   (`_try_place`), die Spec bevorzugt Boden behalten + Möbel als Overlay.
> - Eigene äußere Tür-Vor-Tile-Clearance-Garantie (2.6) ist nicht als eigener
>   Schritt vorhanden, hängt am allgemeinen Cleanup. Status unklar, im Code prüfen.

Konkrete Design-Regeln für `backend/village_spawner.py`, abgeleitet aus
Recherche (Minecraft, RimWorld, prozedurale Room-Gen) und den bekannten
Bugs (offene Wände, Möbel vor Wand, keine Türen, Deko blockt Eingang,
fehlender Boden).

---

## 1. Recherche-Erkenntnisse (was andere richtig machen)

- **Minecraft Villages** (minecraft.wiki): Layout startet mit einem
  Anker (Brunnen/Glocke). Pfade verbinden alle Gebäude. Jedes
  Strukturmodul (Blueprint) ist intern komplett geschlossen mit
  garantierter Tür. Vorher existierender Untergrund wird durch Pfad-
  oder Plattform-Tiles ersetzt (kein "Building über Busch").
- **RimWorld** (Wiki, GamepadSquire): Räume gelten nur als
  "enclosed" wenn alle Außenwände lückenlos sind — der Spiel-Engine-Check
  bricht ab, sobald ein Tile fehlt. Türen ersetzen ein Wand-Tile, niemals
  ein Boden-Tile.
- **Unexplored / MagicalTimeBean Room-Gen**: Room als Rechteck +
  Boundary-Wall, Tür wird auf genau 1 Tile reduziert, Boden separat
  geflutet. Möbel kommen erst nach Wand+Boden+Tür validiert sind.
- **Grammar-Based Village (Cal Poly, Tarquiscani)**: Constraint
  "1-Tile Outer-Clearance" um jedes Gebäude — kein Deko-Tile darf
  Wand oder Tür berühren, sonst NPC-Pathing bricht.
- **Wave Function Collapse**: gut für Variation, aber overkill für
  uns — Rechteck-Stamping mit Validierung reicht.

Gemeinsamer roter Faden: **Wand → Tür → Boden → Möbel → Außenfreizone**,
strikt in dieser Reihenfolge, mit Validierung nach jedem Schritt.

---

## 2. Liege Design-Rules

### 2.1 Wand-Vollständigkeit
- Jedes Haus ist ein achsen-ausgerichtetes Rechteck der Außenmaße
  `width = inner_w + 2`, `height = inner_h + 2`.
- Alle 4 Außenwand-Linien sind **lückenlos** mit `wall`-Struct belegt,
  **außer** für genau die Tür-Positionen.
- Eck-Tiles sind IMMER `wall`, nie Tür.

### 2.2 Tür-Pflicht
- Mind. **1 Tür** pro Haus, max. **2** (z. B. tavern, capital-Häuser).
- Tür liegt auf einer Außenwand-Linie, nicht in Ecke (`door_dx ∈ [1, inner_w]`).
- Bevorzugte Seite: **Süd > Ost > West > Nord** (Süd zur Karte = sichtbar).
- Falls die Siedlung einen zentralen Brunnen hat: Tür sollte zur
  Brunnen-Richtung zeigen (best-effort, nicht hart).
- Tür-Tile zählt als Teil der Wand, NICHT als Boden-Tile.

### 2.3 Tür-Typ (Material-abhängig)
| Haus-Typ            | Tür-Struct    |
|---------------------|---------------|
| house, shop, workshop, tavern | `door_wood`  |
| smithy              | `door_iron`   |
| temple, mage_guild, healers_guild, fighters_guild, thieves_guild | `door_stone` |

(Falls Asset `door_iron`/`door_stone` noch fehlt → Fallback
`door_wood` mit material-Tag.)

### 2.4 Inneneinrichtung-Abstand
- Vor jeder Tür gibt es eine **Tür-Vor-Zone**: das Innen-Tile, das
  direkt an die Tür angrenzt (1 Tile nach innen in Tür-Richtung).
- Dieses Tile MUSS frei von Möbeln/Strukturen bleiben — nur `floor`
  ist erlaubt.
- Allgemein: kein Möbel-Struct darf direkt an einer Wand stehen ohne
  Begründung. Betten/Truhen DÜRFEN an Wand stehen (Standard), aber
  NICHT in der Tür-Vor-Zone.
- Werkbank/Amboss/Furnace stehen 1 Tile von der Wand entfernt wenn
  `inner_w >= 3` und `inner_h >= 3` — sonst Eck-Platzierung.

### 2.5 Boden
- Jedes **Innen-Tile** (`1 <= lx <= inner_w`, `1 <= ly <= inner_h`)
  bekommt ein `floor`-Struct.
- Material:
  - `material="wood"` → `wood-floor`
  - `material="stone"` → `stone-floor`
  - `material="straw"` → `wood-floor` (straw-Haus = Holzboden)
- Wenn Möbel auf dem Tile steht: Boden zuerst, Möbel überschreibt
  (oder Boden-Tile wird mit material-Variante platziert die das
  Möbel als "auf-Boden" markiert; aktueller Code entfernt Boden, das
  ist suboptimal → Boden behalten, Möbel als Overlay).

### 2.6 Außen-Frei-Zone (Clearance Belt)
- 1 Tile Rand um die Haus-Bounding-Box (also `(width+2) × (height+2)`)
  ist **deko-frei**.
- Vor dem Wand-Placement: Cleanup aller `decoration`-Strukturen
  (bush, flower, rock, tree, fallen_log, mushroom, …) in diesem
  Rand.
- Wand-Tiles selbst werden ebenfalls gecleaned bevor `wall` platziert
  wird (vorhandene Deko entfernen).
- **Tür-Vor-Tile außen** (1 Tile vor Tür, draußen): MUSS frei sein —
  zusätzliche Cleanup-Garantie, sonst NPC kann Haus nicht verlassen.

### 2.7 Pfade
- Bei `town`/`capital`: zentraler Brunnen als Anker.
- Nach allen Häuser-Spawns: für jedes Haus eine **L-förmige Pfad-
  Verbindung** vom Tür-Außen-Tile zum Brunnen ziehen.
- Pfad-Tile-Typ: `path` (neuer Struct-Type) mit `material="sand"`
  (village) oder `material="stone"` (town/capital).
- Pfad überschreibt Deko (cleanup beim Drüber-Setzen).
- Pfad-Breite: 1 Tile. Bei `capital`: 2 Tiles (Hauptachsen vom
  Brunnen in alle 4 Richtungen + L-Anschlüsse).

### 2.8 Vorhandene Deko-Räumung (Wiederholung wegen Wichtigkeit)
- `village_spawner` MUSS vor `_place_house` einen `_cleanup_footprint`-
  Schritt machen, der **alle nicht-Settlement-Strukturen** (Decoration,
  Vegetation, Stein) in `house-footprint + 1 Tile Clearance` entfernt.
- Was NICHT entfernt werden darf: `house`, `wall`, `floor`, `well`,
  `bed`, `chest` etc. (alle vorher gespawnten Settlement-Strukturen).
  → Whitelist via `SETTLEMENT_STRUCT_TYPES`-Set.

---

## 3. Validation-Checkliste (`try_spawn_settlement`)

Nach jedem Haus (in `_place_house` return), und nochmal am
Settlement-Ende:

- [ ] **Außenwand komplett**: alle Tiles auf den 4 Kanten haben
      `wall` ODER `door_*` Struct.
- [ ] **Tür-Anzahl**: `1 <= door_count <= 2`, korrekter Typ
      (`door_wood` / `door_iron` / `door_stone`).
- [ ] **Eck-Tiles sind Wall**: nicht Tür.
- [ ] **Innen-Tiles haben Boden**: jedes `(inner_x..inner_x+inner_w-1,
      inner_y..inner_y+inner_h-1)` Tile hat `floor`-Struct (oder
      Möbel-Struct das Boden impliziert).
- [ ] **Tür-Vor-Zone innen frei**: kein Möbel-Struct auf dem
      Innen-Tile direkt vor der Tür.
- [ ] **Tür-Vor-Zone außen frei**: kein Deko-Struct auf dem Tile
      direkt außerhalb der Tür.
- [ ] **Clearance Belt sauber**: kein Deko-Struct in den 1-Tile-Ring
      um die Hausbox.
- [ ] **Keine Doppel-Belegung**: kein Tile hat 2 Structures vom
      gleichen "Layer" (Wand+Wand, Möbel+Möbel).

Bei Fehlschlag: Haus rollback (`structure_manager.remove` alle in
`placed`), `log.warning`, neuer Versuch oder Skip.

---

## 4. Implementations-Hinweise (`backend/village_spawner.py`)

### 4.1 Neue Helper
```python
SETTLEMENT_STRUCT_TYPES = {"wall", "floor", "door_wood", "door_iron",
    "door_stone", "bed", "chest", "anvil", "furnace", "workbench",
    "well", "campfire", "path", "quest_board"}

async def _cleanup_footprint(structure_manager, x0, y0, w, h, padding=1):
    """Entfernt alle Nicht-Settlement-Strukturen im Bereich
    (x0-padding, y0-padding) bis (x0+w+padding, y0+h+padding)."""

def _door_kind_for(house_type: str) -> str:
    if house_type == "smithy": return "door_iron"
    if house_type in ("temple", "mage_guild", "healers_guild",
                      "fighters_guild", "thieves_guild"):
        return "door_stone"
    return "door_wood"

def _floor_material(material: str) -> str:
    return "stone" if material == "stone" else "wood"

def _door_inside_tile(door_x, door_y, door_side):
    """1 Tile vom Türtile nach innen — Tür-Vor-Zone."""
    if door_side == "south": return (door_x, door_y - 1)
    if door_side == "north": return (door_x, door_y + 1)
    if door_side == "east":  return (door_x - 1, door_y)
    return (door_x + 1, door_y)
```

### 4.2 Geänderte Funktionen

**`_place_house`** — Reihenfolge umstellen:
1. `_cleanup_footprint(...)` für gesamte Hausbox + 1 Tile Clearance.
2. Tür-Position + Tür-Side berechnen (wie bisher).
3. Wand-Loop: für jedes Edge-Tile außer Tür-Tile → `wall`.
4. Tür platzieren: `_door_kind_for(house_type)` statt floor.
5. Boden-Loop: jedes Innen-Tile → `floor` mit `_floor_material(...)`.
6. **Tür-Vor-Zone (innen)** in `occupied` eintragen BEVOR Möbel-
   Placement → `_try_place` skippt das Tile automatisch.
7. Möbel-Placement (`_try_place` bleibt, aber prüft jetzt `occupied`).
8. NPC-Spawn am Tür-Außen-Tile (bleibt).
9. **Validate** (siehe 3.) — bei Fail: rollback + skip.

**`_layout_houses`** — Padding anpassen: aktuell `+2 +1`, wir
brauchen `+2 +2` (1 Tile Clearance auf jeder Seite zwischen Häusern).
Bei `capital` evtl. `+3` für breitere Pfade.

**`try_spawn_settlement`** — nach allen `_place_house`-Calls:
- Bei `town`/`capital`: für jedes Haus `_carve_path(door_outside,
  well_pos, material="sand|stone")` aufrufen.
- Pfad-Carve: einfacher L-Path (erst horizontal, dann vertikal),
  jedes Tile bekommt `path`-Struct nach Deko-Cleanup.

### 4.3 Existierende Helper nutzbar
- `_can_place` — bleibt, wird VOR jedem Place verwendet.
- `_weighted_pick`, `_bounding_box` — unverändert.
- `structure_manager.remove(x, y)` — schon im Code, nutzen für
  Cleanup und Rollback.
- `world.is_walkable_sync` — für Tür-Außen-Tile-Check.

### 4.4 Code-Beispiel Validierung (skizziert)
```python
def _validate_house(structure_manager, ox, oy, w, h, door_xy):
    # Außenwand
    for lx in range(w):
        for ly in (0, h - 1):
            s = structure_manager.at(ox + lx, oy + ly)
            if (ox + lx, oy + ly) == door_xy:
                if not s or not s["type"].startswith("door_"): return False
            elif not s or s["type"] != "wall": return False
    for ly in range(h):
        for lx in (0, w - 1):
            ...gleich...
    # Innen-Boden
    for lx in range(1, w - 1):
        for ly in range(1, h - 1):
            s = structure_manager.at(ox + lx, oy + ly)
            if not s: return False  # Boden fehlt
    return True
```

---

## 5. Implementations-Reihenfolge (Was zuerst, was danach)

1. **`_cleanup_footprint` + Whitelist** — kleine Funktion, sofort
   testbar. Verhindert "Busch blockt Eingang"-Bug.
2. **Door-Struct statt floor** in `_place_house` — `_door_kind_for`-
   Helper + Tür-Tile bekommt jetzt echte `door_*`-Struktur (nicht
   `floor`). Sofort sichtbarer Fix.
3. **Boden-Loop sauber** — jedes Innen-Tile garantiert `floor`,
   Möbel überschreibt nicht den Boden (Boden bleibt, Möbel als
   zweite Struktur akzeptiert ODER Möbel hat eingebauten Boden im
   Sprite). Beseitigt "fehlender Boden"-Bug.
4. **Tür-Vor-Zone reservieren** — `occupied.add(_door_inside_tile(...))`
   am Anfang vor allen `_try_place`-Calls. Beseitigt "Möbel vor
   Tür"-Bug.
5. **Layout-Padding `+2`** in `_layout_houses` — sorgt für Clearance
   zwischen Häusern.
6. **`_validate_house` + Rollback** — Sicherheitsnetz nach jedem
   Haus.
7. **Pfade** zwischen Tür und Brunnen (town/capital) — letzter
   Polish-Schritt.

Mit Schritten 1-4 sind die User-gemeldeten Probleme alle gelöst;
5-7 sind Qualitäts-Upgrades.

---

## Quellen

- [Minecraft Wiki — Village/Structure/Blueprints](https://minecraft.wiki/w/Village/Structure/Blueprints)
- [RimWorld Wiki — Colony Building Guide](https://rimworldwiki.com/wiki/Colony_Building_Guide)
- [MagicalTimeBean — Procedural Room Generation Explained](https://www.magicaltimebean.com/2014/11/procedural-room-generation-explained/)
- [BorisTheBrave — Dungeon Generation in Unexplored](https://www.boristhebrave.com/2021/04/10/dungeon-generation-in-unexplored/)
- [Cal Poly — Grammar-Based Procedurally Generated Village Creation Tool](https://digitalcommons.calpoly.edu/cgi/viewcontent.cgi?article=1333&context=cpesp)
- [Tarquiscani — Evolving City Generation (GitHub)](https://github.com/Tarquiscani/evolving-city-generation)
- [GamepadSquire — RimWorld Base Building & Defensive Architecture](https://gamepadsquire.com/blog/rimworld/rimworld-base-building-colony-design-guide/)
