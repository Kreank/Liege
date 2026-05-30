# Refactor-Notes — entdeckte Bugs, NICHT in dieser Refactor-Welle fixen

Plan §1.1: "Wenn dir etwas falsch vorkommt: notieren, nicht fixen.
Fixes kommen in einem separaten Durchgang *nach* dem Refactoring."

Stand: 2026-05-30, Commit 115dd16 (Branch `refactor/structure`).

---

## 1. `quests.py` — alte Spaltennamen in `player_faction_reputation`

**Ort:** `backend/quests.py`, Funktionen `get_reputation`, `add_reputation`, `all_reputation` (Z. 377–408).

**Symptom:** Beim Senden von `list_quests` über WS:
```
asyncpg.exceptions.UndefinedColumnError: column "faction" does not exist
HINT: Perhaps you meant to reference the column "player_faction_reputation.faction_id".
```
→ WebSocket schließt sofort (Bug crasht den Handler).

**Ursache:** Die Tabelle `player_faction_reputation` wurde umstrukturiert (jetzt
`faction_id` + `goodwill` statt `faction` + `reputation`, siehe
`backend/factions.py:181-186`). `factions.py` ist auf das neue Schema migriert;
`quests.py` benutzt aber noch die alten Spaltennamen.

**Auswirkung auf den Smoke-Harness:** `list_quests` ist deshalb aus der
Smoke-Sequenz entfernt (siehe `backend/tools/ws_smoke.py`). Außer dem WS-Branch
sollte nichts blockieren, weil die Tabelle für die Init-Payload über
`factions.list_all_reputations()` gelesen wird, nicht über `quests.all_reputation`.

**Wer den Fix übernimmt:** separater Bug-Fix-Push nach Abschluss von Phase B-final.

---

## 2. `docker-compose.yml` — kein `SESSION_SECRET` gesetzt

**Ort:** `docker-compose.yml`, `backend.environment`.

**Symptom:** `auth.py:_secret()` wirft `RuntimeError("SESSION_SECRET env var not set")`
bei erstem Auth-Call. Lokal über `docker-compose.override.yml` umgangen.

**Auswirkung:** Funktional kein Refactoring-Blocker, aber prod-relevant
(der Server hat das vermutlich über eine eigene `.env`/Override gesetzt).

---

## 3. Plan-Drift: Neue Message-Types seit Plan

**Ort:** `backend/main.py` `websocket_endpoint`.

**Symptom:** Plan §2.2 listet 88 Types, Code hat 69 — davon 4 neu seit Plan:

| Type | Zeile | Plan-Domäne |
|---|---|---|
| `sprint` | 1826 | movement |
| `wake` | 1831 | character/progression |
| `dungeon_chest` | 1835 | structures |
| `dev_trigger_event` | 1518 | raid/dev |

→ Aufgenommen in Phasen B3 / B11 / B15 / B9. Sind in `WS_PROTOCOL.md` dokumentiert.

**Auswirkung:** Tasks #6, #14, #18, #12 enthalten die neuen Types.

---

## 4. Helper-Drift

Plan zählte ~30 Helper-Funktionen in `main.py` Z. 80–1085; aktuell sind es 33
in Z. 82–1101 (siehe `refectoring-plan.md` und Phase B1).
Cluster sind unverändert; +3 Helper für Dungeon-Marker / Welt-Snapshots.

---

## 5. Smoke-Harness: `npc_goal` fehlte im Async-Filter (B1, fixed)

**Ort:** `backend/tools/ws_smoke.py:50` (`ASYNC_BROADCAST_TYPES`).

**Symptom:** Beim ersten ws_smoke-Lauf nach B1 zeigte `diff` Differenzen,
die ausschließlich aus `{"type": "npc_goal", "emoji": "🍞", "goal": "eat",
"npc_id": N}` bestanden — also Goal-Picks aus dem `npc_worker.wander_loop`
(zwischen den Smoke-Antworten reingelaufen, weil hungrige NPCs gerade
ihr Ziel wechselten).

**Ursache:** Das Golden wurde in Phase 0.2 ohne `npc_goal`-Filter erzeugt;
zur damaligen Sequenz hat der Worker zufällig keine Goal-Picks gebroadcastet.

**Fix in B1:** `"npc_goal"` zu `ASYNC_BROADCAST_TYPES` ergänzt (Kategorie
npc_worker, gleicher Charakter wie `npc_moved`/`npc_spawned`). Nach diesem
Fix sind 3 Läufe in Folge identisch zum Golden.

**Logik:** Keine Backend-Änderung — reine Filter-Erweiterung in der Test-
Tooling.

---

## 6. B1 — Helper-Extraktion: Wrapper-Pattern in main.py

**Ort:** `backend/main.py`, Z. ~80–200.

**Status nach B1:** Alle 33 in der Tabelle gelisteten Helper sind in
Geschwister- oder `services/`-Module verschoben. In `main.py` bleiben
nur dünne Bind-Wrapper, die die Module-Globals (`manager`, `world`,
`structures`, `npcs`, `items`) einmal injizieren — damit die hunderten
Call-Sites im monolithischen `if/elif`-Handler nicht angefasst werden
müssen. B2 löst diese Wrapper über `WsContext` final auf.

**Auffälligkeiten:**

- `services/player_state.py` hält `_world`/`_structures` als Modul-Globals
  (gesetzt via `init()` im Startup), damit `_downed_timer` → `do_respawn`
  ohne Closure-Hack die `world`-Ref erreicht. Das ist äquivalent zum alten
  Verhalten (timer → `_do_respawn(name, in_place=False)` → `world.find_spawn`).
- `_apply_spell_effects` (spell-caster-Callback) wird zu
  `spells.apply_spell_effects(manager, npcs, …, callbacks…)`. Da der
  Effects-Code auf 6 weitere Helper (`heal_player`, `_do_respawn`,
  `is_downed`, `_find_drop_xy`, `_drop_loot_for_npc`,
  `_gain_combat_xp_with_share`) zugreift, werden diese als Funktions-
  Parameter durchgereicht statt als Module-Globals registriert — sonst
  wäre `spells.py` mit `main`-State-Lebenszyklus verheiratet.
- `_downed_state` (Modul-globales Dict in player_state.py) wird von
  `apply_spell_effects` für Resurrection-Target-Suche referenziert. Wird
  als expliziter Parameter übergeben statt importiert, damit spells.py
  nicht von services.player_state abhängt.

**Keine Logik-Änderungen entdeckt.** ws_smoke diff leer (3× hintereinander).

---

## 7. `weather_worker._rain_water_plantings` — `column "x" does not exist`

**Ort:** `backend/weather_worker.py:97`.

**Symptom:** Bei Regen-Tick wirft asyncpg `UndefinedColumnError: column "x"`.
Worker fängt es ab (loggt Traceback), Welt läuft weiter — kein Crash. Nur
visuelles Rauschen in den Logs.

**Auswirkung auf Refactor:** keine (Worker, kein WS-Handler), zwischen B3-Smoke-
Läufen sichtbar als Log-Spam wenn das Wetter zufällig auf Regen springt.

**Wer den Fix übernimmt:** separater Bug-Fix-Push nach B-final.

---

## 9. B10 — `items.ITEM_KINDS` ist ein latenter AttributeError

**Ort:** `backend/main.py` (vor B10) bzw. jetzt `backend/ws/crafting.py`,
Legendary-Naming-Block in `handle_craft`.

**Symptom:** Beim Legendary-Crafting wird `items.ITEM_KINDS.get(...)`
aufgerufen, wobei `items` die `ItemManager`-Instance ist (nicht das Modul).
`ItemManager` hat keine `ITEM_KINDS`-Attribute → `AttributeError`. Wird vom
umgebenden `try/except Exception: logging.exception(...)` abgefangen → kein
Crash, aber Legendary-Items bekommen **nie** einen LLM-Namen oder Flavor.

**Auswirkung:** Spielintern unsichtbar bis ein Spieler ein Legendary craftet
und sich wundert, warum es keinen Unique-Namen hat. Ground-Truth bei
trade-Block daneben ist `from items import ITEM_KINDS` — also dieselbe Story
nur korrekt gelöst.

**Fix:** sollte `from items import ITEM_KINDS` lokal importieren. Verschoben
in separaten Bug-Fix-Push nach B-final. B10 spiegelt das alte Verhalten 1:1
(Kommentar im Code).

---

## 8. Smoke-Filter: weather / lightning_strike (B3, fixed)

**Ort:** `backend/tools/ws_smoke.py` `ASYNC_BROADCAST_TYPES`.

**Symptom:** B3 Lauf 2 zeigte `weather` (intensity-Update) und
`lightning_strike` (Position) als Diff — beides aus `weather_worker`,
das alle ~15s Wetterzustände wechselt und bei Gewitter Blitze platziert.

**Fix:** beide in `ASYNC_BROADCAST_TYPES` aufgenommen. Keine Backend-
Änderung — wie schon bei `npc_goal` reines Test-Tooling.

---

## 10. F1 — Docker-Build erwartet vorher gebautes Angular-`dist/`

**Ort:** `backend/Dockerfile` (`COPY frontend/ ../frontend/`),
`backend/main.py` (`app.mount("/", StaticFiles(directory="../frontend/dist/
frontend/browser", html=True))`).

**Symptom:** Wenn jemand `docker compose build backend` ausführt, ohne vorher
`cd frontend && npm run build` zu laufen zu haben, ist `frontend/dist/` leer
oder fehlt → FastAPI-Startup wirft `RuntimeError: Directory
'../frontend/dist/frontend/browser' does not exist` und der Container bleibt
in Restart-Loop. F1 baut Angular im Host und schiebt das ganze `frontend/`-
Verzeichnis (inkl. `dist/`) per `COPY` in den Container.

**Auswirkung:** Solange wir nur lokal arbeiten und nach Codeänderung in
`frontend/src/` per Hand `npm run build && docker compose build backend`
laufen, ist alles gut. Sobald CI/CD oder ein "fresh clone"-Path dazukommt,
muss der Build-Step in den Container (Multi-Stage: `node:24-alpine` baut
`dist/`, `python:3.12-slim` kopiert nur das raus).

**Wer den Fix übernimmt:** Phase F-final oder F-PWA — sobald Angular die
Hauptseite tatsächlich liefert (jetzt noch leeres Standard-Template),
lohnt sich Multi-Stage. Bis dahin: README-Hinweis genügt.

---

## 11. F1 — Angular schluckt Phaser-CDN-Stand, keine Type-Defs verifiziert

**Ort:** `frontend/package.json` → `phaser@3.60.0`.

**Symptom:** Wir haben Phaser als `npm i phaser@3.60.0` reingezogen, um den
Stand des Legacy-CDN-Tags zu spiegeln. Phaser bringt eigene Type-Defs mit
(`phaser/types/phaser.d.ts`); ob die mit dem strict-mode-TS in Angular 21
sauber durchgehen, ist erst in Phase F4 (Phaser-Renderer integrieren)
sichtbar.

**Auswirkung:** F1-Build ist grün (Phaser wird nirgends importiert).
F4 könnte Type-Friction zeigen → ggf. `skipLibCheck: true` in `tsconfig.app.
json` setzen oder Phaser über `@ts-expect-error`-Wrapper isolieren.

**Wer den Fix übernimmt:** Phase F4 (Phaser als Renderer), nicht jetzt.
