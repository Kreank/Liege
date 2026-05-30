# Liege — Welt-Design

Stand: 2026-05-30

Ziel: Welt, in der unterschiedliche Spielstile koexistieren — Baumeister, Jäger, Quest-Reisende, Schmiede, Sammler — und in der eine KI auf Aktivität reagiert.

## Recherche-Zusammenfassung

Wie etablierte Spiele Welten generieren (aus eigenem Erfahrungswissen, kein Web-Lookup):

**RimWorld** — Welt in Regionen, jede Region mit eigenen Biome-Eigenschaften (Niederschlag, Temperatur, Fruchtbarkeit). Eine Settlement-Karte ist 250×250 Tiles. Ressourcen verteilt über Pockets (z.B. Steinkohle-Adern). Map-Generator garantiert Mindestplatz für Builder.

**Dwarf Fortress** — Höhe + Niederschlag + Temperatur + Drainage + Vulkanik als parallele Maps. Biome aus Kombination. Höhle-Layer separat. Ressourcen in Adern (mineral veins) die durch Stein laufen.

**Minecraft** — Perlin Noise multi-octave für Höhe. Separate Biome-Maps. Erze in Cluster-Spawns mit Höhen-Bereichen (Diamant tief, Kohle überall). Strukturen (Dörfer, Tempel) prozedural mit Cluster-Center-Selection.

**Don't Starve** — Biome-Patches mit klaren Grenzen. Set-Pieces (vor-designte kleine Layouts) gestreut. Ressourcen aktiv-respawnt aber gedeckelt pro Biome.

## Erkenntnisse für Liege

1. **Multi-Layer-Noise** statt einfache Höhen-Klassifikation — gibt natürlichere Biome.
2. **Kohärente Biome** — große zusammenhängende Flächen (Wald-Patches, Wüsten-Areale) statt Tile-für-Tile-Schwankung.
3. **Density-Maps** pro Ressource-Typ — Bäume dichter im Wald-Zentrum, dünner am Rand.
4. **Settlement-Spaces** — garantiert leere Flächen pro Region (50–100 Tiles am Stück) damit Baumeister Platz haben.
5. **Resource-Cluster** — Erze in Adern, nicht random scatter.
6. **Wasserstellen** — Seen + spätere Flüsse, nicht nur Ozean.
7. **State-aware Welt-Manager** — KI weiß was passiert ist und reagiert.

## Architektur-Plan

### Welt-Generierung (chunked, deterministic)

Bestätigter Stand (`world.py`, `time_system.py`, `weather_worker.py`):
- **10 Biome**: WATER, SAND, GRASS, FOREST, MOUNTAIN, DESERT, JUNGLE, LAVA, SNOW, SWAMP.
- **32×32-Chunks** (`CHUNK_SIZE = 32`), prozedural + deterministisch aus Seed, in DB gecacht.
- **Multi-Layer-Noise** (height/moisture/temperature) für Biome-Klassifikation.
- **Tag/Nacht**: 4 Phasen (morning, day, evening, night), 1 Spieltag = **48 Echtminuten** (0,5 Spielminuten/Sekunde).
- **Wetter**: clear / rain / snow / fog / swamp_mist mit Intensitäts-Stufen.

Drei Noise-Layer pro Position (x, y):
- **height** — bestimmt Wasser/Land/Berge
- **moisture** — Niederschlag (trocken bis nass)
- **temperature** — kalt bis heiß

Biome-Klassifikation aus diesen drei:

| Höhe | Feuchte | Temp | Biome |
|------|---------|------|-------|
| <0.15 | * | * | Wasser (Ozean) |
| <0.18 (Senken) | hoch | warm | See (innerhalb von Land) |
| 0.18–0.25 | * | * | Strand/Sand |
| 0.25–0.7 | <0.3 | <0.3 | Tundra/Schnee |
| 0.25–0.7 | <0.3 | >0.7 | Wüste |
| 0.25–0.7 | 0.3–0.7 | mid | Grasland |
| 0.25–0.7 | >0.7 | warm | Sumpf (niedrig) / Dschungel (hoch) |
| 0.5–0.7 | mid–hoch | mid | Wald (dichter als Grasland) |
| 0.7–0.88 | * | * | Berg |
| >0.88 | * | heiß | Lava |
| >0.88 | * | kalt | Schneeberg |

### Resource-Distribution

**Density-Map pro Ressource-Typ**: zusätzliche Noise-Layer. Beispiel `tree_density(x, y)` — gibt 0–1. Wenn Tile = Wald UND tree_density > 0.5: hohe Wahrscheinlichkeit für Baum.

**Cluster-Effekt**: viele resources sind nicht uniform sondern in patches. Bäume bilden Cluster (Wald-Inseln), Erze Adern (entlang noise-Gradienten).

**Free-Space-Garantie**: pro Chunk maximal 20% Deko-Dichte. Bei höherer Würfelchance wird random-skipped damit Platz bleibt.

### Wasserstellen

Aktuell nur ozeane (low-height-edges). Erweiterung:
- **Seen**: Niedrige Plateaus im Land werden zu Wasser wenn von Wasser umgeben oder durch sekundäre noise als "water-pocket" markiert
- **Flüsse**: später (separate Feature, braucht Pfad-Finding)

### Settlement-Spaces

Pro Chunk wird beim Generieren eine "Settlement-Suitability" Bit gesetzt — ein klares freies Area das groß genug für ein Dorf ist (z.B. 8×8 Tiles flach + walkable + ohne Deko).

Spieler können dort bauen ohne Bäume fällen zu müssen. Später spawnen NPC-Dörfer in solchen Gebieten.

### Welt-Manager-KI

Slow Brain bekommt beim Event-Generieren einen Welt-State-Schnipsel:

```
Welt-Zustand:
- Aktive Spieler: 2
- Creatures gesamt: 6 (Wölfe: 2, Goblins: 1, ...)
- Strukturen vom Spieler gebaut: 47
- Kürzliche Aktionen: 3 Goblin getötet, 1 Truhe gebaut
- Tageszeit: Tag (kommt später)
```

Damit kann das Modell kontextuell sinnvolle Events generieren ("Die Wölfe rächen ihre Gefallenen"). Plus: Events können konkrete Aktionen triggern (spawn merchant, spawn raid-party).

## Spielstil-Fokus

Die Welt soll mehrere Spielstile bedienen:

| Stil | Was die Welt liefert | Status |
|------|----------------------|--------|
| Baumeister | Settlement-Spaces, Crafting-Stationen, Material-Quellen | Crafting ✓, Settlement-Spaces als nächstes |
| Jäger | Creatures mit Drops, Aggro-Range, Wieder-Spawn | ✓ funktioniert |
| Sammler | Ressourcen verteilt, respawnable | ✓ Welt-Respawn |
| Schmied | Schmelze, Amboss, Erz-Quellen, Rezepte | Crafting ✓, Erz-Adern als nächstes |
| Schreiner | Werkbank, Holz-Quellen, Holz-Rezepte | ✓ |
| Händler-Reisender | Geldbeutel-Währung, Markt, Inventar-Diversität | ✓ Trade-System + Wallet |
| Abenteurer | Quests, Dungeons, Boss-Encounter | ✓ KI-Quests + Multi-Floor-Dungeons (5 Tiers) |
| Magier | Spells, Mana, Magic-Items | ✓ funktioniert |

Was als nächstes ausgebaut wird: **NPC-Dörfer als Hubs**, **Quest-Board (Spieler reichen Quests ein/nehmen an)**, **Tod-Strafe**.

## Wirtschaft & Geld

Geld läuft über einen **Geldbeutel** (Wallet), nicht mehr über Inventar-Items.

- Drei Münz-Stufen: **Kupfer, Silber, Gold**. `100 Kupfer = 1 Silber`, `100 Silber = 1 Gold` (= 10.000 Kupfer).
- Intern wird alles in Kupfer gerechnet und in `players.wallet_copper` gespeichert (`currency.py`).
- Münzen sind **keine Inventar-Items mehr** — `copper_coin`/`silver_coin`/`gold_coin` existieren nicht im Inventar. `gold_ore` ist wieder ein normales, verkaufbares Erz.
- Geld-Quellen: Monster-Loot, Funde am Boden, Quest-Rewards, Truhen, Verkauf beim Händler.

## Monster & Drops

- ~133 Monster über alle Tiers **1–5**, on-map platziert.
- Daten-getrieben aus einem Manifest (`monster_longlist.py`) — kein Code pro Monster.
- **Spawn nach Biome** (passende Kreaturen je Umgebung).
- **Loot tier-skaliert**: höhere Tiers droppen wertvolleres/höherwertiges Loot.
- **Bestiarium-UI** als Kompendium: gesehene Monster werden gesammelt und einsehbar.

## Dungeon-Struktur

Begehbare **Multi-Floor-Instanzen** mit **5 Tiers** (`dungeon_tiers.py`):

| Tier | Größe | Lifetime | Zugang |
|------|-------|----------|--------|
| 1 Small | klein | 2–4 h | offen |
| 2 Medium | mittel | 16–24 h | offen |
| 3 Large | groß | 24–48 h | Key-Item `dungeon_map` (Quest-Reward) |
| 4 Raid20 | Raid | 3–5 Tage | Key-Item `rift_lore` (Boss-Loot/Event) |
| 5 Raid40 | Großraid | 4–7 Tage | Key-Item `kings_seal` (selten) |

- **Auto-Spawn pro Floor**: Mobs werden je Etage automatisch gesetzt, Boss garantiert auf der letzten Floor.
- **Tier-skalierte Loot-Qualität** und Mob-Härte (Mob-Tier-Multiplikator steigt pro Tier).
- **Reaper** räumt abgelaufene Instanzen auf, sobald die Lifetime überschritten ist.
- **Key-Items** (`dungeon_map`/`rift_lore`/`kings_seal`) schalten die höheren Tiers (3–5) frei.

## NPC-Identitäten & KI-Quests

- NPCs erhalten **LLM-generierte Persönlichkeiten und Backstory** (via Ollama).
- Zwei Brains (`llm.py`): **FAST-Brain `qwen3.5:0.8b`** für Dialoge (schnell), **SLOW-Brain `qwen3.5:9b`** für Quests/Events (CPU, sensiblere Generation).
- **Quests**: Narrative/Texte werden per LLM erzeugt, die **Mechanik bleibt deterministisch** (klare Bedingungen, Rewards, Fortschritt).
