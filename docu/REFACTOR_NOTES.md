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
