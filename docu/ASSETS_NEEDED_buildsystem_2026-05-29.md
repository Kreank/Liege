# Asset-Bedarf: Bausystem / Strukturen / Produktionsketten

**Stand:** 2026-05-29 · **Methode:** Ground-Truth-Audit — für jeden im Backend
definierten Strukturtyp (`structures.STRUCTURE_TYPES`, 212 Typen) und jedes
Item (`items.ITEM_KINDS`, 172 Kinds) wurde geprüft, ob eine passende `.png`
unter `assets/` tatsächlich existiert. Aufgelistet ist nur, was **wirklich
fehlt** (kein Asset-File vorhanden → Render-Fallback im Spiel).

## Stil-Vorgabe (gilt für alles unten)
Wie in `ASSETS_NEEDED.md`: painterly, dunkel-gritty (Referenz:
`equipment/weapons/professional/inspired_2026_05_27/`). Top-Down-/leichte
Schräg-Aufsicht passend zu den vorhandenen Struktur-/Gebäude-Sprites
(`assets/buildings/`, `assets/props/`). Transparenter Hintergrund (PNG),
`snake_case` Slugs, pro Slug idealerweise mehrere Größen + `manifest.json`
im bestehenden Format.

---

## ✅ Was bereits VOLLSTÄNDIG abgedeckt ist (kein Bedarf)

- **Items / Ressourcen / Produktionsketten-Materialien:** 172/172 Item-Sprites
  vorhanden. Alle Roh- und Zwischenprodukte (Erze, Barren, Leder, Stoff, Kohle,
  Mehl, Käse, Tränke, Münzen …) haben Art.
  - Kleinigkeit (optional): 5 Lore/Key-Item-Paare teilen sich ein Sprite
    (`research_tome`↔`spell_book`, `research_scroll`↔`scroll`,
    `dungeon_map`↔`ancient_scroll`, `kings_seal`↔`gods_tablet`,
    `rift_lore`↔`runic_tablet`). Funktioniert, aber eigene Icons wären schöner.
- **Produktions-Stationen / Crafting:** Werkbank, Schmelze, Amboss, Kochstelle,
  Lagerfeuer, Käsepresse, Butterfass, Melkschemel, Käseregal, Brunnen, Acker,
  Farm-Gebäude (Scheune, Stall, Hühnerstall, Taubenschlag, Räucherei,
  Speicher …) — alle haben Sprites.
- **Tiles, Tools, Equipment, Magie, Tränke, Effekte, Tiere, Monster** (inkl.
  der 133er-Longlist) — abgedeckt.

---

## ❌ FEHLENDE STRUKTUR-ASSETS (43 Typen)

### 1. Gilden- & Zivilgebäude — HOHE PRIORITÄT (5)
Werden von `village_spawner` in Siedlungen/Hauptstadt platziert, haben aber
kein Gebäude-Sprite → aktuell Platzhalter. Mehrtilige Gebäude, Optik wie die
vorhandenen Farm-Gebäude (`assets/buildings/`), aber „städtisch/repräsentativ".

| Slug | Gebäude | Footprint (Tiles) |
|---|---|---|
| `mage_guild` | Magiergilde (Turm/Arkan) | 4×4 |
| `fighters_guild` | Kämpfergilde (wehrhaft, Banner) | 4×4 |
| `healers_guild` | Heilergilde (Kräuter/Licht) | 4×4 |
| `thieves_guild` | Diebesgilde (verrucht, versteckt) | 4×4 |
| `temple` | Tempel (sakral, groß) | 5×5 |

*Hinweis:* `temple` ist auch ein Dungeon-Theme — hier ist das **Overworld-
Gebäude** gemeint.

### 2. quest_board — HOHE PRIORITÄT (1)
| Slug | Was | Footprint |
|---|---|---|
| `quest_board` | Anschlagbrett mit Pergamenten/Steckbriefen (interaktiv, zentral fürs Quest-System) | 1×1 |

### 3. Hänge-/Laden-Schilder — MITTLERE PRIORITÄT (36)
Platzierbare Schilder pro Gewerbe (`sign_<slug>`, Welle 51). Es gibt bereits
englische Schild-Sprites + Wegweiser (`assets/props/settlement/signs/`) — diese
36 sollen im **gleichen Stil** dazukommen. Kleines hängendes Holz-/Metall-Schild
mit Symbol des Gewerbes, 1×1.

| Slug | Gewerbe | Slug | Gewerbe |
|---|---|---|---|
| `sign_schmiede` | Schmiede | `sign_gasthaus` | Gasthaus |
| `sign_wohnhaus` | Wohnhaus | `sign_baeckerei` | Bäckerei |
| `sign_marktstand` | Marktstand | `sign_lagerhaus` | Lagerhaus |
| `sign_apotheke_heiler` | Apotheke/Heiler | `sign_stall` | Stall |
| `sign_wache` | Wache | `sign_kaserne` | Kaserne |
| `sign_rathaus` | Rathaus | `sign_bergwerk` | Bergwerk |
| `sign_saegewerk` | Sägewerk | `sign_holzfaeller` | Holzfäller |
| `sign_bauernhof` | Bauernhof | `sign_muehle` | Mühle |
| `sign_fischerhuette` | Fischerhütte | `sign_taverne_brauerei` | Taverne/Brauerei |
| `sign_schneiderei` | Schneiderei | `sign_gerberei` | Gerberei |
| `sign_jaegerhuette` | Jägerhütte | `sign_alchemie` | Alchemie |
| `sign_magierturm` | Magierturm | `sign_kapelle` | Kapelle |
| `sign_friedhof` | Friedhof | `sign_bibliothek` | Bibliothek |
| `sign_schule` | Schule | `sign_goldschmied` | Goldschmied |
| `sign_waffenladen` | Waffenladen | `sign_ruestungsschmied` | Rüstungsschmied |
| `sign_hafen` | Hafen | `sign_brunnen` | Brunnen |
| `sign_ritualplatz` | Ritualplatz | `sign_portalraum` | Portalraum |
| `sign_verzauberer` | Verzauberer | `sign_drachenstall` | Drachenstall |

### 4. fire_tile — NIEDRIG / optional (1)
Waldbrand-Boden-Tile. Wird evtl. schon über einen Effekt gerendert; eigenes
Sprite (brennender Boden, animierbar) wäre nice-to-have.

---

## Priorisierungs-Vorschlag
1. **quest_board** (1) — zentrales Spielsystem, sofort sichtbar.
2. **Gilden + Tempel** (5) — prägen das Hauptstadt-/Siedlungsbild.
3. **36 Gewerbe-Schilder** — Polish, machen Siedlungen lesbar (Batch).
4. *(optional)* 5 Lore-Item-Icons + fire_tile.
