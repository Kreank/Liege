# Liege — Manuelle Test-Anleitung

Stand: 2026-05-25 (Phase 4b — Items, Combat, erweiterte Welt)

## Setup

```bash
# Einmalig: Ollama-Modelle pullen (auf Host, NICHT im Container)
ollama pull qwen3.5:0.8b
ollama pull qwen3.5:9b
ollama pull nomic-embed-text

# Stack starten
docker compose up -d
```

Browser öffnen: **http://localhost:8000**

Beim allerersten Besuch fragt ein Prompt nach deinem Namen — wird in `localStorage` gespeichert (Key: `liege_player_name`). Um Name zu ändern: DevTools → Application → Local Storage → Eintrag löschen → Refresh.

---

## Phase 1 — Welt + Multiplayer-Grundlagen

| Was | Erwartung |
|-----|-----------|
| Welt rendert | 120×80 prozedurale Inselkarte mit Wasser/Strand/Gras/Wald/Berg |
| Schachbrett-Shading | Tiles haben dezenten Hell/Dunkel-Wechsel |
| Wald-Bäume, Berg-Gipfel | Sichtbar als Overlay-Sprites |
| Minimap | Unten rechts, 150×100, zeigt komplette Welt |
| HUD oben links | Koordinaten + Tile-Name (Grasland/Wald/...) live aktualisiert |
| HUD oben rechts | `Verbunden` + Spielerzahl |
| Bewegung | WASD oder Pfeiltasten, 1 Tile pro 150ms |
| Wasser/Berge blockieren | Bewegung dorthin verweigert |
| Zwei Browser-Fenster | Beide sehen sich gegenseitig; Bewegungen werden live übertragen |
| Spieler-Toast | "🧙 X betritt die Welt" beim Join |

---

## Phase 2 — Persistenz + Build-Mode

### Welt-Persistenz

| Aktion | Erwartung |
|--------|-----------|
| `docker compose restart backend` | Beim nächsten Refresh: **gleiche** Welt (gleiche tiles), keine Neugenerierung |
| `docker compose down && docker compose up -d` | Welt bleibt (im Postgres-Volume `liege-postgres-data`) |
| DB-Check: `docker exec liege-postgres psql -U liege -d liege -c "SELECT seed, created_at FROM worlds;"` | Eine Zeile, `created_at` ändert sich nie nach erstem Boot |

### Player-Persistenz

| Aktion | Erwartung |
|--------|-----------|
| Name eingeben, bewegen | Position wird live in DB gespeichert |
| Tab schließen, neu öffnen | Spawn an letzter Position (nicht Welt-Mitte) |
| Anderer Name | Frischer Spawn auf Grasland nahe Welt-Mitte |
| DB-Check: `docker exec liege-postgres psql -U liege -d liege -c "SELECT name, x, y, last_seen FROM players;"` | Eine Zeile pro Spieler, `last_seen` aktualisiert sich bei Bewegung |

### Build-Mode

| Taste | Aktion |
|-------|--------|
| `B` | Build-Mode ein/aus (Build-Bar erscheint unten Mitte) |
| `1` | Mauer wählen (blockiert Bewegung) |
| `2` | Boden wählen (dekorativ) |
| `3` | Lagerfeuer wählen (dekorativ) |
| `4` | Marker wählen (dekorativ) |
| `M` | Material wechseln: Stein → Holz → Stroh → Stein |
| **Linksklick** auf Tile | Struktur platzieren (im Build-Mode, mit aktuellem Material) |
| **Rechtsklick** auf Tile | Struktur abreißen (im Build-Mode) |
| Maus-Hover | Gelber Rahmen am Ziel-Tile (im Build-Mode) |

| Test | Erwartung |
|------|-----------|
| Mauer platzieren, davor laufen, durchgehen versuchen | Mauer blockiert Bewegung (sowohl Frontend-Prediction als auch Backend-Validation) |
| Zwei Browser, einer baut | Andere sehen die Struktur **live** ohne Refresh |
| Struktur auf Wasser/Berg setzen versuchen | Backend ignoriert (Tile nicht walkable) |
| Struktur auf existierende Struktur setzen | Wird ignoriert (Unique-Constraint `(x, y)`) |
| Refresh nach Bau | Strukturen bleiben sichtbar |
| Backend-Restart | Strukturen bleiben (in `structures`-Table) |
| DB-Check: `docker exec liege-postgres psql -U liege -d liege -c "SELECT id, x, y, type, owner FROM structures;"` | Alle gebauten Strukturen mit Owner = Spielername |

---

## Phase 3 — KI-DM (Welt-Events)

**Voraussetzung:** Ollama läuft auf dem Host und bindet auf `0.0.0.0:11434` (siehe Setup oben). Modelle gepullt: `qwen3.5:0.8b`, `qwen3.5:9b`, `nomic-embed-text`.

### Was du sehen solltest

| Wo | Was |
|----|-----|
| **Links oben** (unter HUD) | Chronik-Panel mit allen vergangenen Welt-Events. Klick auf Header `📜 Chronik` → ein/ausklappen |
| **Mitte oben** | Story-Toast wenn ein neues Event kommt (~10s sichtbar mit Titel + Body) |
| Backend-Logs | `Event-Worker startet, Intervall 180s` beim Start; alle 180s `Event geschickt: ...` |

### Was zu testen ist

| Aktion | Erwartung |
|--------|-----------|
| Erstes Connect | Chronik enthält alle bisher generierten Events (älteste oben, neueste unten) |
| Nach ~3 Minuten (Default-Intervall) | Neuer Event-Toast erscheint mittig oben, neue Zeile in Chronik unten |
| Zwei Browser, beide warten | Beide bekommen denselben neuen Event zeitgleich |
| Backend-Restart | Chronik bleibt — Events in DB persistiert |
| Backend ohne Ollama (testweise `sudo systemctl stop ollama`) | Worker loggt `Event-Worker iteration fehlgeschlagen`, läuft weiter, aber keine neuen Events bis Ollama zurück ist |

### Schneller Test (Wartezeit reduzieren)

Default-Intervall ist 180s. Für einen schnellen Test temporär runter:

```bash
# in docker-compose.yml unter backend.environment hinzufügen:
#   - EVENT_INTERVAL_SECONDS=30
# dann:
docker compose up -d --force-recreate backend
```

### DB-Checks

```bash
# Alle Events anschauen
docker exec liege-postgres psql -U liege -d liege \
  -c "SELECT id, kind, title, created_at FROM events ORDER BY id;"

# Latenz-Messung am Backend
docker compose logs backend | grep "Event geschickt"
```

### Performance-Erwartung

| Modell | Latenz pro Event |
|--------|------------------|
| `qwen3.5:9b` auf CPU (Server: Ryzen 9 3900X) | ~13s (Dev-PC) bis ~20–30s (Server, geringere Performance möglich) |
| `qwen3.5:0.8b` auf GPU (für später NPC-Dialoge) | <1s (mit `think=false`) |

⚠️ Wichtig: `"think": false` ist im LLM-Client default. Qwen 3.5 mit Thinking-Modus wäre praktisch unbrauchbar (53s+ pro Call auf der 0.8b, Timeout auf der 9b). Wenn jemand mal komplexes Reasoning braucht → explizit `think=True` setzen.

---

## Phase 3.2 — Lebendige Welt (NPCs + Player-Action-Events)

### Player-Action-Events (Welle A)

Bestimmte Strukturen lösen ein KI-Welt-Event aus, beschrieben durch den Slow Brain mit Kontext (Spielername, Position, Terrain).

| Aktion | Erwartung |
|--------|-----------|
| Platziere `campfire` oder `marker` im Build-Mode | Nach 10–30 Sek erscheint ein Story-Toast + Chronik-Eintrag, der dich namentlich erwähnt |
| Erneut innerhalb 60 Sek | Kein neuer Event-Toast (Cooldown pro Spieler) |
| Wand oder Boden platzieren | Kein Event (nur `campfire` und `marker` triggern) |
| Backend-Log | `Player-Event geschickt (<name>): <title>` |

### NPCs (Welle B)

Beim allerersten Server-Boot werden 4 NPCs gespawnt (2 friendly + 2 Creatures). Identität (Name, Backstory, Mood) wird einmalig vom Slow Brain generiert (~13s pro NPC), persistiert in DB.

| Was | Erwartung |
|-----|-----------|
| Init-Connect | NPCs erscheinen an ihrer Position mit Sprite + Name als Label |
| Friendly Kinds (wanderer, merchant, etc.) | Gleicher Player-Sprite, aber farblich getintet je nach Rolle |
| Creature Kinds (goblin, wolf, skeleton, spider, slime) | Eigene Monster-Sprites aus `/assets/monsters/` |
| Wander-Loop | Alle 8–15 Sek (random) bewegt sich ein NPC ein Tile in walkbare Richtung, smooth animiert |
| DB-Check | `SELECT name, kind, x, y FROM npcs;` zeigt alle NPCs |
| Talk-Historie | `SELECT npc_id, player_name, role, text FROM talks ORDER BY id;` zeigt geführte Gespräche |

### NPC-Dialog (Welle C)

| Aktion | Erwartung |
|--------|-----------|
| Klick auf NPC (Build-Mode AUS) | Dialog-Modal öffnet sich mit Name, Rolle, Backstory |
| Text eingeben + Enter (oder Senden-Button) | Eigene Bubble rechts (gelb), NPC tippt "…" links (grau) |
| <1 Sek später | NPC-Antwort erscheint links (cyan), in-character zur Rolle/Backstory |
| Mehrere Nachrichten hintereinander | Gespräch hat Kontext (NPC erinnert sich an vorherige Antworten) |
| Esc oder Schließen-Button | Modal schließt, Bewegung wieder möglich |
| Während Dialog offen | WASD/Build-Hotkeys deaktiviert, kein Player-Movement |

---

## Phase 4a — Sprite-Renderer (RimWorld-Look)

Klötzchen-Grafik ist weg. Statt `Phaser.Graphics` werden alle Objekte als Sprites aus `/mnt/dev/Privat/Liege/assets/` gerendert.

**Voraussetzung:** Assets liegen unter `/mnt/dev/Privat/Liege/assets/` (11 PNGs, siehe `docu/ASSET_SPEC.md`). Backend serviert sie unter `/assets/...`.

### Was du sehen solltest

| Was | Erwartung |
|-----|-----------|
| Welt | Detaillierte Tile-Texturen (Gras, Wald, Wasser, Strand, Berg) — keine Farbflächen mehr |
| Tile-Größe | 64×64 Pixel (doppelt so groß wie vorher), Kamera-Zoom 1.0 |
| Strukturen | Mauer, Boden, Lagerfeuer, Marker als detaillierte Sprites — keine Kreise/Rechtecke mehr |
| Spieler (du) | Kapuzenfigur mit Schatten drunter, in Originalfarbe |
| Andere Spieler | Gleiche Kapuzenfigur, leicht bläulich getönt zur Unterscheidung, mit Namens-Label drüber |
| Kamera-Bounds | Beim Rand der Welt bleibt die Kamera stehen — kein schwarzer Bereich außerhalb der Karte |
| Build-Hover | Gelber Rahmen im Build-Mode ist sichtbar (über den Sprites) |

### Was zu testen ist

| Aktion | Erwartung |
|--------|-----------|
| Hard-Refresh (Strg+Shift+R) | Assets werden geladen, Welt rendert mit Sprites |
| Browser-Console | Keine 404-Fehler für `/assets/...`-URLs |
| Schon gebaute Strukturen (aus Phase 2 Test) | Werden mit den neuen Sprites angezeigt |
| Bewegung WASD | Spieler **gleitet smooth** zwischen Tiles (150ms-Tween), Schatten + Label bewegen sich als Einheit mit |
| Zweites Browser-Fenster | Beide Spieler sehen sich als unterschiedlich getönte Figuren mit Labels |
| Build-Mode (`B` + 1–4 + Linksklick) | Strukturen erscheinen als Sprites, sofort sichtbar |
| **Material `M`-Hotkey im Build-Mode** | Build-Bar zeigt Material-Wechsel Stein/Holz/Stroh; neu platzierte Wände/Böden in gewähltem Material |
| **Wand-Auto-Tiling** | Wände greifen ineinander: einzelne Wand = Endstück, Reihe = Straight, Ecke = Corner. Bitmask wählt aus 10 Varianten pro Material |
| Welt-Event-Toast | Erscheint weiter oben mittig, Chronik links bleibt funktional |
| Minimap | Eigener weißer Punkt mit Rand, hellblaue Punkte für andere Spieler, gelb für friendly NPCs, rot für Creatures |
| Random tile-IDs in DB | Mit `docker exec liege-postgres psql -U liege -d liege -c "SELECT seed FROM worlds;"` → unverändert (Renderer-Umbau berührt DB nicht) |

### Wenn was nicht passt

| Symptom | Was checken |
|---------|-------------|
| Welt komplett schwarz, keine Tiles | `docker compose logs backend` — Mount-Fehler? Browser-Console — `/assets/tiles/...` 404? |
| Tiles geladen, aber falsche Größe | TILE_SIZE in `frontend/index.html` muss 64 sein, Kamera-Zoom 1.0 |
| Player ist riesig | `setDisplaySize(TILE_SIZE * 0.95, ...)` in `spawnSprite()` — sollte ~60px ergeben |
| Strukturen unsichtbar | Sprite-Key in `STRUCTURE`-Konfig falsch? Asset im DOM? |
| Bewegung lag-y | Eigentlich identisch zu Phase 1, kein Grund langsamer zu sein — Browser-Performance? |

---

## Phase 4b — Items, Inventar, Combat

### Welt-Generator erweitert (5 neue Biome)

Neben den ursprünglichen Tiles (Wasser/Sand/Gras/Wald/Berg) gibt es jetzt:

| Tile | Begehbar | Wo |
|------|----------|-----|
| Wüste | ✓ | heiße Niederungen |
| Dschungel | ✓ | heiße mittlere Höhen |
| Schnee | ✓ | kalte Zonen (Pol-Latitude oder kalter Klima-Noise) |
| Sumpf | ✓ | warme, niedrige feuchte Bereiche |
| Lava | ✗ blockiert | Bergspitzen mit hohem Klima |

Die bestehende Welt aus DB hat **noch alte Tile-IDs (0–4)**. Um die neuen Biome zu sehen:

```bash
# DB-Reset (verliert alle Strukturen + Player-Positionen + NPCs)
docker compose down -v
docker compose up -d
```

### Item-System

| Was | Wie |
|-----|-----|
| Items spawnen | Alle ~60s ein zufälliges Item irgendwo auf walkbarem Tile (Resources häufig, Equipment selten) |
| Aufheben | Lauf auf das Tile → automatisch aufgehoben → Toast "🎒 X aufgehoben" |
| Inventar öffnen | `I`-Taste, oder Esc/Klick auf Schließen-Button |
| **Equipment-Slots** | Waffe, Helm, Brustpanzer, Schild, Ring — Klick auf Slot = Item ablegen |
| Items im Beutel | "Anlegen" für Equipment, "Benutzen" für Consumables, "Ablegen" droppt aufs aktuelle Tile |
| Während Inventar offen | Kein WASD, kein Build-Mode |

### Combat

| Was | Wie |
|-----|-----|
| HP-Balken oben links | Roter Balken mit "100/100"-Anzeige, blinkt bei Schaden |
| Creatures (Goblin, Wolf, Skelett, Spinne, Schleim) | Greifen an, wenn du näher als 6 Tiles bist; ziehen zu dir wenn 2–6, Attack wenn 1 |
| **Spieler-Angriff** | Klick auf Creature im Build-Mode-OFF → Angriff (nur wenn ≤1 Tile entfernt, sonst Toast "Zu weit weg") |
| Schaden | Base 4 HP + Waffen-Bonus (Schwert +8, Axt +12, Bogen +6, Stab +5) |
| Creature stirbt | Verschwindet, Toast "☠️ Name wurde besiegt", evtl. später Drop |
| Player stirbt (HP=0) | Respawn am Weltmittel-Spawn, volle HP, Story-Toast "💀 Du bist gefallen" |
| HP über NPCs | Kleiner roter Balken über Sprite erscheint sobald Creature verletzt ist |
| DB-Check | `SELECT name, hp, max_hp FROM players;` und `SELECT name, kind, hp FROM npcs;` |

### Polish-Updates

| Was | Stand |
|-----|-------|
| NPC-Wander | Jeder NPC würfelt **pro 2s-Tick** unabhängig ob er sich bewegt. Wölfe (35%), Goblins (30%) am aktivsten. Einsiedler (5%) am ruhigsten |
| Dialog-Modell | Slow Brain (qwen3.5:9b auf CPU) — **~13s Latenz**, aber deutlich bessere Roleplay-Qualität. Typing-Indikator pulsiert während Wartezeit |
| WASD im Dialog/Inventar | Phaser-Keyboard deaktiviert solange Modal offen — Tasten gehen ins Eingabefeld |

### Test-Subjekt im Spawn-Bereich

⚠️ Es gibt einen `TestGobbo` (HP 26/30) bei (62, 41) — direkt neben dem Spieler-Spawn. Wenn du connectest, wird er dich vermutlich sofort angreifen. Combat-Test! Löschen via SQL falls gewünscht:

```bash
docker exec liege-postgres psql -U liege -d liege -c "DELETE FROM npcs WHERE name = 'TestGobbo';"
```

---

## Phase 4c — Crafting, Heal, Traps, Visual Effects

### Build-Palette (13 Strukturen)

| Hotkey | Struktur | Effekt |
|--------|----------|--------|
| `1` | Mauer | Blockiert (Material-fähig) |
| `2` | Boden | Dekorativ (Material-fähig) |
| `3` | Lagerfeuer | Dekorativ, triggert KI-Event |
| `4` | Marker | Dekorativ, triggert KI-Event |
| `5` | Truhe | Storage — Klick öffnet Modal mit Item-Transfer |
| `6` | Werkbank | Crafting — Holzschwert, Steinaxt, Lederhelm, Bogen, Schild, Amulett |
| `7` | Schmelze | Crafting — Stahl, Heiltrank, Manatrank |
| `8` | Amboss | Crafting — Eisenpanzer, Eisenhelm, Eisenschwert |
| `9` | Bett | Heilung auf voll (Klick, 30s Cooldown) |
| `0` | Brunnen | +20 HP (Klick, 30s Cooldown) |
| — | Acker | Dekorativ (Growth-Mechanik kommt noch) |
| — | Stachelfalle | -10 HP wenn Spieler/NPC drauftritt |
| — | Giftfalle | -15 HP wenn Spieler/NPC drauftritt |

Klick auf Palette-Button im Build-Mode wählt die Struktur. Hotkeys 1–0 sind Shortcuts.

### Heilung

| Quelle | Effekt |
|--------|--------|
| Heiltrank (use) | +30 HP |
| Kraut (use) | +5 HP |
| Manatrank (use) | +10 HP (provisorisch, kein Mana-System) |
| Bett-Klick (nahe) | Volle Heilung (100 HP), 30s Cooldown |
| Brunnen-Klick (nahe) | +20 HP, 30s Cooldown |

### Visual Effects

- **Hit-Spark** beim Attack auf NPC
- **Poison-Cloud** beim Drauftreten auf Giftfalle
- **Heal-Glow** beim Heilen (Heiltrank, Bett, Brunnen)
- Alle fade-out animiert über 600ms

### Chest-Storage

Linksklick auf Truhe (nahe genug) → Modal mit zwei Spalten:
- Links: dein Beutel
- Rechts: Truheninhalt

Buttons `→ Truhe` / `↑ Beutel` transferieren Items. Persistent in DB (`items.owner = "chest:<id>"`).

### Crafting

Klick auf Werkbank/Schmelze/Amboss → Modal mit Rezept-Liste:
- Inputs werden mit aktueller Anzahl angezeigt (grün = genug, rot = fehlt)
- "Herstellen"-Button disabled wenn Material fehlt
- Bei Klick: Inputs werden gelöscht, Output ins Inventar

### DB-Checks

```sql
-- Strukturen
SELECT type, COUNT(*) FROM structures GROUP BY type;
-- Items in Truhen
SELECT owner, COUNT(*) FROM items WHERE owner LIKE 'chest:%' GROUP BY owner;
-- Cooldowns sind in-memory, nicht persistent
```

---

## Phase 4d — Loot, Farm, Magic, Combat-Polish, Dungeons, Event-Dialog

### NPC-Loot-Drops
- Töte einen Creature (Goblin/Wolf/Skelett/Spinne/Slime) → 1–2 Items droppen am NPC-Tile
- Loot-Tabelle pro Kind: Goblin → bone/cloth/wood, Skelett → bone/iron_ore, etc.

### Acker (Farm-Plot)
- Bau einen Acker (Build-Mode → Acker wählen aus Palette)
- Hab `Kraut` im Inventar → Klick auf Acker (nahe) → "🌱 Kraut gepflanzt"
- Nach 60s erscheint ein Kraut-Item auf dem Acker, aufnehmbar

### Mana + Magic
- HP-Balken oben links, **Mana-Balken** (blau) direkt darunter
- Manatrank im Inventar → "Benutzen" → +30 Mana
- Magic-Items (Feuerball-Buch, Schriftrolle, Heilrune): "✨ Casten" im Inventar
- Mana wird abgezogen; bei Damage-Spells: nahester Creature in Reichweite wird getroffen
- Feuerball: AOE +1 Tile Radius; Schriftrolle: single, verbraucht; Heilrune: self-heal

### Combat-Polish
- NPC blinkt rot beim Treffer
- Bildschirm-Rand rot beim Spieler-Damage
- Kleine Vibration beim Spieler bei Schaden

### Dungeon-Encounter
- Strukturen-Palette → 🏚️ Treppe nach unten platzieren
- Klick (nahe) auf stairs_down → Loot-Encounter: 3–5 random Items ins Inventar, 70% Chance auf 10–30 HP Trap-Damage
- 5min Cooldown pro Spieler (Toast zeigt verbleibende Zeit)
- Echte begehbare Dungeons folgen als eigene Welle

### NPCs reagieren auf Welt-Events
- Frag im Dialog z.B. "Was ist los?" → NPC erwähnt vielleicht ein aktuelles Welt-Event aus der Chronik
- Slow Brain bekommt die letzten 3 Events als Kontext im System-Prompt

---

## Phase 4f — Welt-Population + Harvesting

### Auto-Population
Beim ersten Server-Start nach diesem Update werden ~600+ natürliche Strukturen biome-spezifisch verteilt:
- **Gras**: Hohes Gras, Blumen, Büsche, kleine Felsen, vereinzelte Eichen
- **Wald**: Eichen, Nadelbäume, tote Bäume, Stümpfe, Stämme, Pilze, Moosfelsen
- **Berge**: Große/kleine Felsen, Moosfelsen
- **Dschungel**: dichte Bäume, Pilze, Blumen
- **Sumpf**: Schilf, Seerosen, tote Bäume
- **Schnee**: Nadelbäume, Felsen
- **Wüste**: tote Bäume, Felsen, vereinzelte Statue-Ruinen
- **Selten überall**: zerbrochene Karren, Fässer, Schiffswracks, Ruinen-Säulen

### Harvest-Mechanik (Multi-Hit mit Durability)

Jede natürliche Struktur braucht mehrere Schläge — robuste Sachen mehr:

| Strukturtyp | Schläge bis weg |
|-------------|-----------------|
| Eiche, Schiffswrack | 5–6 |
| Großer Felsen, Säule | 4–5 |
| Pine, Moosfelsen, Wracks | 3–4 |
| Toter Baum, Stamm, kl. Felsen, Statue | 2–3 |
| Stumpf, Gras, Blumen, Pilze, Sack, Zaun | 1 |

Pro Klick:
- 1–2 Resources ins Inventar (kind-spezifisch)
- Sprite wackelt kurz (Hit-Spark + Shake)
- Bei letztem Schlag verschwindet die Struktur
- Toast `⛏️ +N× X` zeigt was du bekommst

Loot-Tabellen pro Schlag:
- Bäume: 1–2× Holz
- Felsen klein/groß/moos: 1–2× Stein, Chance auf Eisenerz/Silber/Kristall
- Pflanzen: Kräuter / Stoff
- Wracks/Karren: meist Holz, Chance auf Gold/Eisen
- Ruinen: Stein

**Vorbereitet für Werkzeuge:** Später wird eine Axt/Spitzhacke die Schläge reduzieren und/oder Yield erhöhen. Die `damage_structure(amount)`-API ist schon parametrisierbar.

### Build-Palette gefiltert
Nur user-baubare Strukturen sind im Build-Modus wählbar (14 Stück: wall, floor, campfire, marker, chest, workbench, furnace, anvil, bed, well, farm_plot, spike_trap, poison_trap, stairs_down). Natürliche Deko (Bäume etc.) ist **nicht** baubar.

---

## Phase 4g — Stable Diffusion + Erweiterungen (noch offen)

Siehe `docu/BACKLOG.md` für vollständige Liste:
- Echte begehbare Dungeons (eigene Map)
- Tag/Nacht + Wetter
- Fraktionen + NPC-Tagesabläufe
- XP/Level + Quests
- Walk-Animation mit echten Frames
- SD-Pipeline für unique Items
- Auth-System
- Deko-Props (Bäume, Felsen, Ruinen)

---

## Wenn was nicht klappt

| Symptom | Was checken |
|---------|-------------|
| Browser zeigt nichts/weiße Seite | `docker compose logs backend` — Exceptions beim Startup? |
| "❌ Getrennt" oben rechts | Backend down oder Ollama-Verbindung verloren — Logs prüfen |
| Bewegung geht nicht | Backend lebt? Sind die Tasten richtig (WASD oder Pfeile)? |
| Build-Bar erscheint nicht bei `B` | DevTools-Console: gibt's JS-Errors? |
| Struktur verschwindet nach Refresh | Backend hat Struktur nicht in DB gespeichert — DB-Check (siehe oben) |
| Mauer blockiert nicht | Backend-Restart, evtl. Race-Condition; oder Frontend-Cache (Hard-Refresh: Strg+Shift+R) |
| "depends_on postgres unhealthy" | Postgres-Volume kaputt? `docker volume rm liege-postgres-data` + neu starten (Achtung: Welt + alle Daten weg) |

---

## DB-Schema (zum Nachschlagen)

```sql
worlds      (seed PK, width, height, tiles JSONB, created_at)
players     (name PK, x, y, created_at, last_seen)
structures  (id PK, x, y, type, owner, created_at, UNIQUE(x, y))
```
