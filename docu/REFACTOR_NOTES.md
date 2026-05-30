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
