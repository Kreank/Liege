# Assets — Status, Stil & offene Lücken

**Stand: 2026-05-30.** Single Source of Truth für Asset-Status. Ersetzt die alten
Einzeldocs (ASSETS_NEEDED, ASSET_NEEDED, ASSET_EXPANSION_LIST, ASSET_SPEC,
MISSING_ASSETS_2026-05-27, ASSETS_NEEDED_buildsystem_2026-05-29).

---

## 1. Stil-Vorgabe (für ALLE neuen Assets)

- **Stil:** handgemalt/painterly, dunkel-gritty Dark-Fantasy, gedämpfte erdige
  Palette, weiches gebackenes Licht. Referenzen:
  - Items/Equipment: `equipment/weapons/professional/inspired_2026_05_27/`
  - Gebäude: `assets/structures/farm/barn_large.png`
  - Schilder: `assets/props/settlement/signs/professional/` (Ausleger + Holzbrett + goldenes Relief-Emblem)
  - Monster (Top-Down): `assets/monsters/world_sprites/generated_longlist/`
- **Hintergrund:** vollständig transparent (PNG, Alpha).
- **Ein** Objekt zentriert, kein Text/Wasserzeichen/Rahmen, kein Sprite-Sheet.
- **Lieferung:** pro Slug mehrere Größen (`icons_64/128/256`, ggf. `masters_512`),
  `snake_case`-Dateinamen = Game-Slug, dazu `manifest.json` im Format von
  `equipment/weapons/professional/inspired_2026_05_27/manifest.json`.
- **No-Gos:** kein heller/Pergament-Hintergrund, keine Concept-Art-Tafeln, keine
  Multi-Asset-Sheets, keine Wasserzeichen/Branding, keine Strichskizzen,
  keine knallbunten/Cartoon-Farben, keine geometrisch-abstrakten Embleme.

---

## 2. Vollständig abgedeckt (kein Bedarf)

Ground-Truth-Audit (Datei-Existenz pro Backend-Definition):

- **Items / Ressourcen:** 172/172 Item-Sprites vorhanden — alle Roh-/Zwischen-
  produkte für Produktionsketten (Erze, Barren, Leder, Stoff, Mehl, Käse,
  Tränke, Food, Saatgut, Münzen-Icons).
- **Produktions-Stationen & Strukturen:** Werkbank, Schmelze, Amboss, Kochstelle,
  Lagerfeuer, alle Farm-Stationen + Farm-Gebäude (Scheune, Stall, Hühnerstall …).
- **Monster:** 133-Longlist als transparente Top-Down-Sprites
  (`world_sprites/generated_longlist/`, 96/128/mirrored/512) + ältere Sets.
- **Tiles, Tools, Equipment, Magie, Effekte, Tiere, NPCs/Characters.**
- **Welle 34b geliefert + verdrahtet:** 5 Gilden + Tempel
  (`assets/structures/guilds/`), `quest_board`, `fire_tile`, 36 Gewerbe-Schilder
  (`props/settlement/signs/professional/`), 5 dedizierte Lore-/Key-Item-Icons
  (`additional_assets_2026_05_29_v2/lore_items/`), Tech-Print-Icons.

---

## 3. Offene Lücken (echter Bedarf)

### 3.1 Vier Gewerbe-Schilder neu generieren — Emblem off-pattern
Rahmen (Ausleger + Holzbrett) ist gut, nur das zentrale Emblem ist zu
abstrakt/geometrisch und liest sich nicht. Aktuell im Bau-Menü **auskommentiert**
(`frontend/app.js`: `SIGN_VARIANTS` + Paletten-Arrays `sign_magic`/`sign_resource`)
— nach Re-Lieferung wieder einkommentieren.

| Slug | Emblem (golden-Relief, painterly) |
|---|---|
| `magierturm` | spitzer Turm + arkaner Stern |
| `alchemie` | klarer blubbernder Kolben + Sigille |
| `jaegerhuette` | klarer Bogen + Geweih |
| `verzauberer` | leuchtende Rune/Edelstein auf Stab |

### 3.2 Optional / niedrig
- `fire_tile`: statisches Sprite liegt vor; im Spiel läuft aktuell die animierte
  `fire_flame_lick`-Variante. Nur tauschen, falls statisch gewünscht.

---

## 4. Verfügbar aber (noch) ungenutzt — Opportunities

Material liegt im Repo, ist aber nicht ins Gameplay verdrahtet — Kandidaten für
künftige Features:

- **Monster-Portraits** (große, dunkle Gemälde, `generated_longlist/cells/`) —
  werden im **Bestiarium** genutzt; ein Encounter-/Info-Modal im Kampf wäre denkbar.
- Weather-Overlays / Biome-Ambient-Layer (atmosphärische Tiefe).
- Combat-Magic-Professional-Varianten als Ersatz der einfachen Effekt-Frames.
- Equipment-Rarity-Varianten (Skin-Pools je Slot/Rarity) — teils schon verdrahtet.

---

## 5. Audit-Methode (reproduzierbar)

„Fehlt ein Asset?" wird per **Datei-Existenz-Check** beantwortet, nicht subjektiv:
für jeden Backend-Strukturtyp (`structures.STRUCTURE_TYPES`) und jedes Item
(`items.ITEM_KINDS`) prüfen, ob die referenzierte `.png` unter `assets/` existiert.
Strukturen rendern im Frontend über `NPC_SPRITE`/`STRUCTURE`-Registry +
`_spriteKeyForStruct`; fehlt die Textur, greift ein Fallback (= sichtbarer Bedarf).
