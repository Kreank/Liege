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

---

## 12. F2 — STRUCTURE-Map enthielt im Legacy 26 Duplikat-Keys

**Ort:** `frontend/legacy/app.js` `STRUCTURE` (Z. 605-820).

**Symptom:** Welle 24 (notBuildable Stubs `barn_large`, `barn_small`, `cow_shed`, …)
und Asset-Drop 2026-05-27b (baubare Farm-Gebäude mit `farm_*`-Sprites) deklarieren
in derselben Object-Literal-`const STRUCTURE` denselben Key. JS schluckt das
ohne Warnung — die spätere Property gewinnt. Strict-TS (`noImplicitAny` egal,
aber `error TS1117: An object literal cannot have multiple properties with
the same name`) hätte das in einem Object-Literal abgelehnt.

**Migration:** Statt Object-Literal wird `STRUCTURE` über eine
`buildStructureMap()`-Funktion mit `Record<string, StructureDef>` zusammengebaut.
Late-Add wins (1:1 wie das JS-Verhalten); die früheren Welle-24-Stubs werden
durch die `farm_*`-Varianten überschrieben. Endresultat ist bytegleich zur
Legacy-Map.

**Liste der überschriebenen Keys (Welle 24 → 2026-05-27b):** `barn_large`,
`barn_small`, `stable`, `cow_shed`, `sheepfold`, `goat_pen`, `pigsty`,
`henhouse`, `duck_pond`, `goose_pasture_marker`, `dovecote`, `cart_shed`,
`dairy_house`, `smokehouse`, `hayloft`, `granary`, `water_trough`,
`feed_trough`, `hay_bale`, `hay_stack`, `straw_bale`, `fence_gate_farm`,
`wooden_fence_segment`, `milking_stool`, `cheese_press`, `nesting_box_egg`.

**Auswirkung auf Refactor:** keine — Datenstruktur identisch. Wer das alte
Welle-24-Sprite zurück will, muss explizit auf das `struct_<name>`-Asset
zugreifen (das Asset existiert weiter).

---

## 13. F2 — Animations-Listen werden generiert statt 1:1 abgeschrieben

**Ort:** `frontend/src/app/core/data/animations.ts`.

**Symptom:** `WORLD_DETAIL_P2_ANIMAL_ANIMS` (48 Einträge) und
`WORLD_DETAIL_P2_TRANSPORT_ANIMS` (16 Einträge) sind im Legacy als komplette
Object-Arrays mit URL-Strings je 4 Richtungen je Animal/Vehicle ausgeschrieben.
Alle Felder folgen demselben Schema (`/assets/animations/animals/<animal>/
<direction>/walk_sheet.png` etc.); nur `frame_width/height` variieren pro
Animal.

**Migration:** Spec-Tupel `[animal, fw, fh]` + Generator `_buildAnimalAnims()`
× 4 Richtungen produziert die identische Liste byteweise (selbe Reihenfolge:
south/east/north/west pro Animal). Output ist `readonly AnimalAnim[]`,
`as const`-frozen. Reduziert ~60 Zeilen URL-Boilerplate auf ein 12-Zeilen-Spec.

**Auswirkung:** keine — Output identisch. Future-Friendly weil ein neues
Animal hinzufügen jetzt nur ein Tupel ist statt 4 Zeilen × 5 Felder.

---

## 14. F2 — Helper-Funktionen aus dem Daten-Bereich NICHT migriert

**Ort:** `frontend/legacy/app.js` Z. 580-2382 (mit Daten verflochten).

**Status:** Diese Helper sind weder in F2 noch in F3 ein Migrations-Ziel —
sie kommen in F4ff. mit der jeweiligen Component oder dem Service mit, der sie
braucht:

- `_allTypesInCat(cat)` (Z. 580) — Build-Menü-Iteration, F5+ Inventar/Hotbar.
- `footprintFor(type)` (Z. 934) — Bridge/Renderer, F4.
- `relativeTime(iso)` (Z. 964) — Chat/Events-Panel, F14.
- `itemWeight(item)` (Z. 1107) — Inventar-Panel, F7.
- `isWaterContainer/containerCapacity` (Z. 1158-1159) — Inventar/Use-Item, F7.
- `splitCoins/formatCoinsHtml/formatCoinsText` (Z. 1168-1188) — HUD/Trade, F5+F-trade.
- `_qualityMult/buildItemStatsHtml/findEquippedInSlot` (Z. 1190-1282) — Tooltips, F7.
- `_equipDir/itemAssetPath/itemGroundScale/itemSpriteKey` (Z. 1878-1987) — Renderer-Bridge, F4.
- `effectiveQuality` (Z. 2000) — Inventar-Tooltips, F7.
- `proWeaponPath/proArmorPath/_proArmorAssetRarity/_ancientBladeForItem` (Z. 2330-2382) — Renderer, F4.

Diese sind alle PURE-Funktionen über den portierten Daten — können in eine
`core/util/`-Subfolder, sobald die jeweilige Component sie zieht. F2 ist
deliberately data-only.

---

## 15. F2 — Bundle-Größe unverändert (Tree-Shaking)

**Symptom:** `ng build` vor und nach F2 produziert identische 213.66 kB main-
Bundle. Erwartet — nichts referenziert die `core/data`- oder `core/models`-
Files, also tree-shaken raus. Strict-TS-Check läuft trotzdem über `tsc --noEmit
-p tsconfig.app.json` (`src/**/*.ts` include), Exit 0.

**Auswirkung:** Erst wenn F4+ tatsächlich `import { TILE } from './core/data'`
schreibt, wandern die Daten ins Bundle. Dann wird ein realistischer Sprung
nach oben sichtbar werden.

---

## 16. F3 — ServerMessage als Bag-Type statt Diskriminator-Union

**Ort:** `frontend/src/app/core/models/ws-message.model.ts`.

**Symptom:** Erster Versuch typte `ServerMessage = InitMessage |
UnknownServerMessage`. Strict-TS akzeptiert das auf dem `isInitMessage`-True-
Pfad sauber, aber auf dem Else-Pfad bleibt `msg` ein
`InitMessage|UnknownServerMessage` — und Felder wie `msg['x']` werfen
`TS7053: Element implicitly has an 'any' type`, weil `InitMessage` keine
String-Index-Signatur hat. Negativ-Guard (`isGenericMessage`) bringt nichts
— die Union-Reduktion klappt strukturell nicht (InitMessage hat keine
Substruktur-Beziehung zu UnknownServerMessage).

**Entscheidung:** `ServerMessage` IST `UnknownServerMessage` (Bag-Type mit
String-Index-Signatur). `InitMessage` bleibt als voll-getypte Schnittmenge
verfügbar und wird per `isInitMessage`-Guard zu `ServerMessage & InitMessage`
verfeinert. So sind alle Handler-Bodies sauber `unknown`-getypt, kein
`any`, und der Init-Pfad behält volle Typsicherheit.

**Vorteile:**
- `_handlePlayerMoved(msg)` etc. sehen `msg['x']: unknown` → expliziter Cast
  `msg['x'] as number` zwingt die Migration, jeden Feld-Zugriff bewusst zu
  type-en.
- Kein `as any`-Lückenfüller. 0× `any` in `core/`.

**Trade-off:** Jeder Feld-Zugriff im Handler braucht einen `as TYPE` —
zusätzliche Tipparbeit, aber dokumentierter Vertrag. Sobald F5+ die UI-
Components die einzelnen Domänen anfasst, können sie pro Type ein eigenes
voll-getyptes Interface bauen und über einen weiteren `is...`-Guard
narrowen (gleiches Pattern wie `InitMessage`).

---

## 17. F3 — Kein DI für GameStateService, kein UI-Side-Effect-Routing

**Ort:** `frontend/src/app/core/services/game-state.service.ts`.

**Status:** Der Service nimmt eingehende WS-Messages und befüllt Signals.
UI-Side-Effects wie Sound (`playSfx('hit_flesh')`), Floating-Damage-Numbers,
Camera-Shake, Visual-Effects, Toasts und Modal-Trigger (`crafting_open`,
`chest_open`, `trade_open`, `sign_inspect`, `quest_board_open`) sind im
Legacy direkt in `handleMsg` verstreut. Wir machen das hier **nicht**.

**Warum nicht:** Diese Side-Effects gehören in F4 (Phaser → Visual-Effects,
Camera) bzw. F5+ (Component-spezifische Modals). Würden wir sie in
`GameStateService` reinpacken, wäre der Service nicht testbar und hätte
Output-Side-Effects auf die DOM/Audio-Layer — Anti-Pattern.

**Konsequenz:** Diese Messages werden im switch zwar erkannt, aber bewusst
no-op behandelt (siehe Kommentare "UI-Side-Effect, F4ff"). Bei der Migration
der jeweiligen UI-Component zieht diese sich die zugehörigen Messages über
einen separaten Subscribe auf `WebSocketService.messages$` (oder über einen
gezielten Signal-Effect am eigenen Panel-State).

---

## 18. F3 — Bundle-Größe immer noch unverändert

**Symptom:** Vor und nach F3 produziert `ng build` 213.66 kB main. Services
sind nirgends injected, Tree-Shaking entfernt sie komplett. Strict-TS-Check
über `tsc --noEmit -p tsconfig.app.json` läuft trotzdem über alle Files.

**Auswirkung:** Erst F4 (PhaserGameComponent injectet WebSocketService +
GameStateService und ruft `.connect()` im Constructor) lässt das Bundle real
wachsen — vermutlich um ~12-18 kB für RxJS Subject + die State-Service-
Branches, je nachdem wie aggressiv Angular die Switch-Cases reinpullt.
