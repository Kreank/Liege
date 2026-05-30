# Refactoring-Plan: Liege

> **Anleitung für den Coding-Agent.** Dies ist kein Skill — es ist ein Arbeitsdokument.
> Lies es vollständig, bevor du irgendetwas anfasst. Arbeite es **phasenweise** ab.
> Nach jeder Phase: verifizieren → committen → Haken in der Checkliste setzen → kurzer Bericht → **stop**.

---

## 0. Was hier passiert (in einem Satz)

Wir zerlegen zwei Monolithen — den Backend-WebSocket-Handler (`main.py`, 4141 Zeilen)
und das Frontend (`app.js`, 492 KB) — in eine saubere Struktur, **ohne das Verhalten zu ändern**.
Frontend-Ziel: **Angular 21 (PWA) als Hülle, Phaser 3.60 als Renderer.**
Backend-Ziel: **dünner `/ws`-Endpoint + Dispatcher + Domain-Handler.**
Bindeglied: das **WebSocket-Protokoll bleibt eingefroren** — dadurch lassen sich beide Seiten unabhängig umbauen.

---

## 1. Grundprinzipien (nicht verhandelbar)

1. **Verhaltenserhaltend.** Reine Extraktion/Migration. Keine Logikänderung, keine neuen Features, keine „Verbesserungen nebenbei". Wenn dir etwas falsch vorkommt: **notieren**, nicht fixen. Fixes kommen in einem separaten Durchgang *nach* dem Refactoring.
2. **Inkrementell.** Eine Domäne (Backend) bzw. ein Panel (Frontend) pro Phase. Nie mehrere gleichzeitig.
3. **Immer lauffähig.** Nach **jeder** Phase muss das Spiel booten, einloggbar und spielbar sein. Kein Commit lässt das Spiel kaputt zurück.
4. **WS-Protokoll niemals ändern.** Message-Namen, Felder und Semantik bleiben identisch. Das ist der Vertrag zwischen Frontend und Backend.
5. **Verifizieren vor Commit.** Erst grün (siehe §6), dann committen, dann Haken setzen.
6. **Bei Rot: zurückrollen.** Wenn eine Phase nicht grün wird → `git restore` / Branch zurücksetzen, Blocker melden. Niemals auf einen roten Stand draufstapeln.
7. **Keine Dependency-Upgrades.** Phaser bleibt 3.60, FastAPI bleibt 0.111, PostgreSQL bleibt 16. Versions-Upgrades sind ein eigenes Projekt.

---

## 2. Ist-Zustand (Ground Truth — damit du nicht neu suchen musst)

### 2.1 Backend

- **`backend/main.py` — 4141 Zeilen.** Aufbau:
  - Z. 1–75: Imports. **Wichtig:** 70 Domain-Module existieren bereits und werden hier importiert (`combat`, `quests`, `factions`, `npc_worker`, `structures`, `items`, …).
  - Z. 80–1085: **~30 lose Helper-Funktionen** auf Modulebene. Cluster:
    - Gruppen: `_group_snapshot`, `_broadcast_to_group`, `_push_group_state`, `_push_group_state_to_all_members`
    - Loot: `_drop_loot_for_npc`, `_maybe_start_loot_roll`, `_find_drop_xy`
    - Combat-XP: `_gain_combat_xp_with_share`
    - Player-Lifecycle: `load_or_create_player`, `heal_player`, `damage_player`, `_enter_downed_state`, `_downed_timer`, `_do_respawn`, `is_downed`, `restore_mana`, `_refund_mana`
    - Attribute: `_compute_attributes`, `_build_stat_sheet`, `_send_attrs_update`
    - Spells: `_sync_learned_spells`, `_list_learned_spells`, `_apply_spell_effects`, `_apply_heal_aggro`
    - Equipment: `get_equipped_weapon_kind`, `get_equipped_tool_kind`, `has_tool_for_skill`
    - Sonstiges: `_send_to_player`, `_populate_chunks_bg`
  - Z. 337–443: `lifespan` (Startup/Shutdown).
  - Z. 440–480: Statik-Mounts (`/static` → `../frontend`, `/assets` → `../assets`) + HTTP-Routes (`/`, `/login`, `/admin`, `/manifest.webmanifest`, `/sw.js`).
  - **Z. 1086–4141: der WebSocket-God-Handler.** Eine einzige `async def websocket_endpoint(...)` mit einem `if/elif`-Block über **88 Message-Types**. Einzelne Branches 20–220 Zeilen. **Das ist das Hauptziel.**
- **Das Backend ist NICHT unmodularisiert.** Die Domänen-Logik liegt schon in den 70 Modulen. Das Problem ist ausschließlich, dass der WS-Handler die **Orchestrierung** (DB-Aufrufe, Broadcasts, Reihenfolge) inline macht.
- **Es gibt KEINE automatisierten Tests.** Das ist das größte Risiko → Phase 0 ist Pflicht.

### 2.2 Die 88 WS-Message-Types, nach Domäne gruppiert

Diese Gruppierung bestimmt die Ziel-Handler-Module. (Quelle: `if/elif`-Kette in `main.py`.)

- **movement:** `move`
- **social/groups:** `chat`, `group_create_party`, `group_invite`, `group_accept`, `group_decline`, `group_leave`, `group_kick`, `group_promote`, `group_transfer_leader`, `group_disband`, `group_refresh`, `group_chat`, `group_convert_to_raid`
- **loot:** `loot_vote`, `set_loot_rule`
- **raid/dev:** `raid_trigger_manual`, `dev_world_repopulate`, `force_respawn`
- **structures:** `place_structure`, `toggle_door`, `remove_structure`, `attack_structure`, `repair_structure`, `upgrade_structure`, `use_structure` (groß — enthält Sub-Branches für chest / quest_board / stairs_down / farm_plot / bed / well), `fill_container`, `water_plant`, `drink_container`, `drink_water_tile`
- **inventory:** `split_stack`, `merge_stacks`, `equip_item`, `unequip_item`, `use_item`, `pick_item`, `drop_item`, `chest_transfer_to`, `chest_transfer_from`
- **combat:** `attack_npc` (~217 Z.), `cast_spell` (~224 Z.)
- **crafting:** `open_hand_crafting`, `craft`
- **trade:** `open_trade`, `buy_item`, `sell_item`
- **character/progression:** `allocate_attr`, `learn_talent`, `learn_spell`, `cast_learned`, `list_attributes`, `character_check_name`, `character_create`, `list_talents`
- **quests:** `list_quests`, `query_npc_quests`, `accept_quest_template`, `quest_turn_in`, `accept_quest_from_npc`, `claim_quest_reward`
- **research:** `invest_research`
- **bills:** `add_bill`, `remove_bill`, `list_bills`
- **dialog:** `talk_to_npc`

### 2.3 Frontend

- **`frontend/index.html`** — UI-Gerüst mit ~40 Panels/Overlays, alle mit harten IDs (`party-frame`, `loot-roll-overlay`, `raid-selector-overlay`, `group-invite-overlay`, `hp-bar`, `mana-bar`, `hunger/thirst/stamina-bar`, `hotbar`, `downed-overlay`, `cast-bar`, `spellbook-overlay`, … + Inventar/Skills/Talente/Charakter/Quests/Faktionen).
- **`frontend/app.js` — 492 KB, eine Datei.** Aufbau:
  - Z. ~455–2296: **Datentabellen** (`TILE`, `STRUCTURE`, `ITEM`, `NPC_SPRITE`, `WEAPON_STATS`, `ARMOR_STATS`, `AFFIX_STAT_LABELS`, `EQUIP_SLOTS`, …). Großteils statische Daten, die das Backend spiegeln.
  - Z. 2296–~9445: **`class WorldScene extends Phaser.Scene`** — eine ~7000-Zeilen-God-Class: Rendering **+** alle UI-Panels **+** WebSocket-Handling **+** Input.
  - Z. ~9445: `new Phaser.Game(config)`.
- **`frontend/style.css` — 75 KB.**
- **Rendering-Stil:** 75× `innerHTML`, 146× `createElement`, 206× DOM-Queries. Imperative DOM-Manipulation über IDs.
- **PWA:** `sw.js` (handgeschrieben), `manifest.webmanifest`, Icons (`icon-192/512`, `apple-touch-icon`).
- **Laden:** Phaser via CDN (`phaser@3.60.0`), `<script src="/static/app.js" defer>`. **Kein Build-Step.**

---

## 3. Ziel-Architektur

### 3.1 Backend-Ziel

`main.py` schrumpft auf: App-Setup, `lifespan`, Statik-Mounts, HTTP-Routes und einen **dünnen** `/ws`-Endpoint, der nur die Verbindung verwaltet und jede Message an den Dispatcher weiterreicht.

```
backend/
├── main.py                 # nur noch App-Setup, lifespan, Routes, dünner /ws-Loop
├── ws/
│   ├── __init__.py
│   ├── context.py          # WsContext-Dataclass: websocket, player_name, manager,
│   │                       #   world, structures, npcs, items, events, db + Service-Refs
│   ├── dispatcher.py        # HANDLERS: dict[str, Handler]  +  async def dispatch(ctx, data)
│   ├── movement.py
│   ├── social.py            # chat + group_*
│   ├── loot.py
│   ├── raid.py              # raid + dev + force_respawn
│   ├── structures.py
│   ├── inventory.py
│   ├── combat.py
│   ├── crafting.py
│   ├── trade.py
│   ├── character.py
│   ├── quests.py
│   ├── research.py
│   ├── bills.py
│   └── dialog.py
└── services/               # (optional) Heimat für die extrahierten losen Helper
    ├── player_state.py      # heal/damage/downed/respawn/mana/load_or_create
    ├── player_equipment.py  # get_equipped_*, has_tool_for_skill
    └── ...                   # oder: in die jeweils passenden Bestandsmodule schieben
```

- **Handler-Signatur (einheitlich):** `async def handle_<type>(ctx: WsContext, data: dict) -> None`
- **Dispatcher:** `HANDLERS = {"move": movement.handle_move, "craft": crafting.handle_craft, ...}`
- **`/ws`-Loop in `main.py`:**
  ```python
  while True:
      data = await websocket.receive_json()
      mtype = data.get("type")
      handler = HANDLERS.get(mtype)
      if handler:
          await ctx_dispatch(ctx, mtype, data)   # else: noch nicht migriert → siehe B2
  ```

### 3.2 Frontend-Ziel (Angular 21 + Phaser)

**Phaser bleibt der Renderer. Angular ist die Hülle.** Niemand baut die 2D-Welt in Angular-Komponenten nach.

```
frontend/                        # wird zum Angular-Workspace
└── src/
    ├── app/
    │   ├── core/
    │   │   ├── services/
    │   │   │   ├── websocket.service.ts    # besitzt die WS-Verbindung; send(intent); Message-Stream
    │   │   │   ├── game-state.service.ts    # Signals: player, inventory, party, quests,
    │   │   │   │                            #   hp/mana/needs, hotbar, …
    │   │   │   └── game-bridge.service.ts    # Phaser ↔ Angular: State runter, Intents hoch
    │   │   ├── models/                       # TS-Interfaces fürs Protokoll + Spieldaten
    │   │   └── data/                         # die Datentabellen (TILE, STRUCTURE, ITEM, …), typisiert
    │   ├── game/
    │   │   ├── world-scene.ts                # Phaser-Scene: NUR Rendering + Input→Intent
    │   │   └── phaser-game.component.ts       # mountet Phaser in ein <div>, Lifecycle
    │   ├── ui/                               # eine Komponente pro Panel/Overlay
    │   │   ├── hud/           (hp, mana, needs, coords, conn-status)
    │   │   ├── hotbar/
    │   │   ├── inventory/  skills/  talents/  character/
    │   │   ├── quests/  factions/
    │   │   ├── party-frame/  loot-roll/  raid-selector/  group-invite/
    │   │   ├── spellbook/  cast-bar/  chat/  downed-overlay/
    │   ├── app.component.ts
    │   └── app.routes.ts
    ├── index.html   main.ts   styles.css
    └── manifest.webmanifest  (von @angular/pwa verwaltet)
```

- **PWA:** `ng add @angular/pwa` ersetzt das handgeschriebene `sw.js`. Bestehendes Manifest + Icons übernehmen.
- **WorldScene** wird reduziert auf: Assets laden, Chunks/Tiles rendern, Sprites (Spieler/NPCs/Creatures/Strukturen) rendern, Kamera, Animationen, **Input → Intent über die Bridge**. **Kein `innerHTML`, kein `getElementById` mehr** — alles HUD/Panel-artige wandert nach Angular.
- **Phaser-Integration:**
  - `new Phaser.Game(...)` in `ngAfterViewInit`, `game.destroy(true)` in `ngOnDestroy`.
  - Phaser-Game in `ngZone.runOutsideAngular(...)` starten, damit die 60-FPS-Loop **nicht** die Change Detection triggert.
- **Ausliefern:**
  - **Prod:** `ng build` → `dist/`. FastAPI serviert `dist/` (Statik-Mount-Ziel von `../frontend` auf das Build-Verzeichnis umstellen).
  - **Dev:** `ng serve` mit Proxy für `/ws` und `/assets` auf die FastAPI (`proxy.conf.json`).

---

## 4. Das eingefrorene Protokoll (der Trick)

Vor dem Umbau wird das WS-Protokoll dokumentiert und **eingefroren**. Solange Frontend und Backend exakt dieselben Message-Namen/Felder senden und empfangen, können beide Tracks **unabhängig und parallel** laufen. Keine Phase darf das Protokoll verändern.

---

## 5. Phasen

> Reihenfolge: **Phase 0 zuerst.** Danach dürfen Backend-Track (B) und Frontend-Track (F) parallel laufen — sie berühren sich nur über das eingefrorene Protokoll.

### Phase 0 — Sicherheitsnetz (ZWINGEND ZUERST)

- **0.1 Protokoll dokumentieren.** Erzeuge `docu/WS_PROTOCOL.md`: für alle 88 Message-Types den Namen, die eingehenden Felder und die ausgehenden Antwort-Messages. Das ist der Vertrag.
  *Fertig wenn:* jede der 88 Types in `WS_PROTOCOL.md` steht.
- **0.2 Smoke-Harness.** Schreibe `backend/tools/ws_smoke.py`: loggt einen Test-Spieler ein, öffnet `/ws`, schickt eine **feste** Sequenz repräsentativer Messages (mind. move, place_structure, craft, attack_npc, learn_talent, list_quests, group_create_party), protokolliert alle Antworten in eine Datei. Lauf einmal, speichere die Ausgabe als **Golden-Output** (`docu/ws_smoke_golden.txt`).
  *Fertig wenn:* Harness läuft gegen den aktuellen Stand und Golden-Output ist gespeichert.
- **0.3 Git.** Sauberer Arbeitsbaum, Branch `refactor/structure`. Ab jetzt: **ein Commit pro Phase**.
  *Fertig wenn:* Branch existiert, Tree clean.

### Backend-Track (B)

- **B1 — Lose Helper extrahieren.** Verschiebe die ~30 Helper aus `main.py` (Z. 80–1085) in passende Module (siehe Cluster in §2.1 → `services/player_state.py`, `services/player_equipment.py`, bzw. in die bestehenden `groups.py`/`loot.py`/`combat.py`/`attributes.py`/`spells.py`). `main.py` importiert sie. **Keine Logikänderung.**
  *Fertig wenn:* `ws_smoke` == Golden-Output (Diff leer), Spiel bootet.
- **B2 — Dispatcher-Gerüst (hybrid).** Lege `ws/context.py` (WsContext) und `ws/dispatcher.py` (leeres `HANDLERS`-Dict + `dispatch`) an. Verdrahte den `/ws`-Loop **hybrid**: erst Dispatcher fragen, bei Miss ins alte `if/elif` fallen. So lässt sich Type für Type migrieren, ohne dass dazwischen etwas bricht.
  *Fertig wenn:* `ws_smoke` == Golden (noch nichts migriert, alles fällt durch ins alte `if/elif`).
- **B3…Bn — Domänen migrieren (eine pro Phase).** Pro Domäne: die Branches in `ws/<domain>.py` als Handler herausziehen, im `HANDLERS`-Dict registrieren, aus dem alten `if/elif` **löschen**. **Den Closure-State sorgfältig in `ctx` überführen** (siehe §7). Empfohlene Reihenfolge (klein/risikoarm zuerst):
  `movement` → `bills` → `research` → `dialog` → `trade` → `loot` → `raid` → `crafting` → `character` → `inventory` → `quests` → `social` → `structures` → `combat`.
  *Fertig wenn (je Phase):* `ws_smoke` == Golden, betroffene Flows manuell im Browser geprüft, Commit.
- **B-final — Monolith entfernen.** Wenn das alte `if/elif` leer ist: Hybrid-Fallback entfernen, toten Code löschen. Ziel: `main.py` < ~400 Zeilen.
  *Fertig wenn:* `ws_smoke` == Golden, `main.py` enthält keinen `if mtype ==`-Block mehr.

### Frontend-Track (F)

- **F1 — Angular-Workspace.** Angular-21-Workspace in `frontend/` anlegen, Phaser als npm-Dependency, leere App per FastAPI ausliefern (Statik-Mount auf das Build-Verzeichnis, oder `ng serve` mit Proxy). 
  *Fertig wenn:* leere Angular-App lädt im Browser, `/assets` und `/ws` erreichbar.
- **F2 — Datentabellen portieren.** `app.js` Z. ~455–2296 → `core/data/*.ts` + `core/models/*.ts`, typisiert. **Nur Daten, kein Verhalten.**
  *Fertig wenn:* Tabellen kompilieren typsicher, keine Laufzeitnutzung nötig.
- **F3 — State- + WS-Service.** `WebSocketService` (besitzt Verbindung, `send()`, Message-Stream) und `GameStateService` (Signals). Das aktuelle `onmessage`-Handling aus `WorldScene` hierher spiegeln → Signals befüllen. **UI noch nicht verdrahtet.**
  *Fertig wenn:* Verbindung steht, eingehende Messages aktualisieren die Signals (per Logging/DevTools prüfbar).
- **F4 — Phaser als Renderer.** `PhaserGameComponent` + neue `WorldScene`, die **nur** die Rendering-Teile der alten Scene übernimmt, aus `GameState` liest und Intents über die Bridge schickt. **Größte Phase — bei Bedarf splitten:** F4a Tiles/Chunks, F4b Sprites (Spieler/NPC/Creature/Struktur), F4c Input→Intent + Kamera.
  *Fertig wenn:* Welt rendert, Bewegung funktioniert, andere Spieler/NPCs sichtbar. Phaser außerhalb der Angular-Zone gestartet.
- **F5…Fn — UI-Panels einzeln migrieren.** Pro Phase **ein** Panel → Angular-Komponente an Signals gebunden; den zugehörigen DOM-/`innerHTML`-Code aus der alten Scene **löschen**. Reihenfolge:
  HUD (hp/mana/needs/coords/conn) → Hotbar → Inventar → Skills/Talente/Charakter → Quests → Faktionen → Party-Frame → Loot-Roll/Raid/Group-Invite-Overlays → Spellbook/Cast-Bar → Chat → Downed-Overlay.
  *Fertig wenn (je Panel):* Panel funktioniert im Browser wie zuvor, alter DOM-Code entfernt, Commit.
- **F-PWA — PWA umstellen.** `ng add @angular/pwa`, handgeschriebenes `sw.js` raus, Manifest + Icons übernehmen, Caching-Strategie definieren (App-Shell + Assets).
  *Fertig wenn:* App installierbar, Service-Worker aktiv, Offline-Shell lädt.
- **F-final — Altlast entfernen.** `app.js` löschen, altes `index.html`-UI-Gerüst durch Angular-Komponenten ersetzt, `style.css` in Komponenten-Styles bzw. globale Styles migriert.
  *Fertig wenn:* `app.js` weg, Spiel vollständig über Angular läuft.

---

## 6. Verifikation pro Phase

- **Backend:** `python backend/tools/ws_smoke.py` → Diff gegen Golden-Output muss **leer** sein.
- **Frontend:** Manueller Browser-Smoke nach `docu/TEST_GUIDE.md` (es gibt keine FE-Tests). Playwright o. Ä. optional *nach* dem Refactoring — blockiert hier nichts.
- **Beide, immer:** Spiel bootet → einloggen → bewegen → der Kern-Flow der jeweiligen Phase einmal von Hand durchspielen.

---

## 7. Heikle Stellen (hier brechen Dinge)

- **Backend — der Closure-State.** Der WS-Handler ist eine einzige riesige Funktion. Viele Branches greifen auf Variablen zu, die weiter oben in dieser Funktion gesetzt wurden (Spielername, `websocket`, geladener Spieler-State) oder auf Modul-Globals (die Manager). Beim Herausziehen eines Branches in einen Handler **muss** dieser State explizit über `ctx` übergeben werden. **Die eigentliche Arbeit pro Branch ist nicht das Copy-Paste, sondern das Inventarisieren der genutzten Variablen** und ihre Überführung in `ctx`. Geht ein Branch nicht sauber raus, weil er zu sehr verwoben ist → notieren, vorerst im alten `if/elif` lassen, nächste Domäne nehmen.
- **Frontend — die Bridge ist die kritische Naht.** Definiere sie früh und klar: **State fließt runter** (Angular-Signals → Phaser liest), **Intents fließen hoch** (Phaser-Input → `WebSocketService.send()`). Phaser darf keinen DOM-State mehr besitzen. Phaser **außerhalb** der Angular-Zone starten (`ngZone.runOutsideAngular`), sonst feuert Change Detection 60×/s.
- **Frontend — Datentabellen-Dopplung.** Die Tabellen in `core/data/` spiegeln Backend-Daten. Für dieses Refactoring nur typisieren, nicht vereinheitlichen. (Später optional: vom Backend ausliefern. Jetzt **nicht** — Scope-Creep.)
- **KI-Asset-Pipeline (Kontext, kein Refactoring-Schritt).** Asset-Generierung ist Backend (Stable Diffusion, async). Phaser lädt generierte Assets exakt wie statische — der Renderer bleibt unberührt. Der Nutzen des Frameworks liegt in der späteren **Asset-Verwaltungs-UI** (Queue/Vorschau/Freigabe), nicht in der Generierung selbst. Beim Refactoring **nichts** dafür vorbauen.

---

## 8. Arbeitsweise pro Session

1. Diesen Plan + die Checkliste (§9) lesen.
2. Die **niedrigste offene** Phase wählen.
3. Den relevanten Ground-Truth-Abschnitt (§2) erneut lesen und den echten Code ansehen.
4. **Genau diese eine Phase** umsetzen — nichts darüber hinaus.
5. Verifizieren (§6).
6. **Grün** → committen, Haken setzen, 3-Zeilen-Phasenbericht (was bewegt, wie verifiziert, Auffälligkeiten).
7. **Rot** → zurückrollen, Blocker melden, nicht weitermachen.
8. **Stop.** Phasen nie ohne Verifikation verketten.

---

## 9. Phasen-Checkliste

```
Phase 0 — Sicherheitsnetz
[ ] 0.1  WS-Protokoll dokumentiert (docu/WS_PROTOCOL.md)
[ ] 0.2  Smoke-Harness + Golden-Output (backend/tools/ws_smoke.py)
[ ] 0.3  Git-Branch refactor/structure, Commit-pro-Phase-Regel etabliert

Backend-Track
[ ] B1   Lose Helper aus main.py extrahiert
[ ] B2   ws/context.py + ws/dispatcher.py (hybrid) verdrahtet
[ ] B3   Domäne: movement
[ ] B4   Domäne: bills
[ ] B5   Domäne: research
[ ] B6   Domäne: dialog
[ ] B7   Domäne: trade
[ ] B8   Domäne: loot
[ ] B9   Domäne: raid/dev
[ ] B10  Domäne: crafting
[ ] B11  Domäne: character/progression
[ ] B12  Domäne: inventory
[ ] B13  Domäne: quests
[ ] B14  Domäne: social/groups
[ ] B15  Domäne: structures
[ ] B16  Domäne: combat
[ ] B-final  Altes if/elif entfernt, main.py < ~400 Zeilen

Frontend-Track
[ ] F1   Angular-Workspace + Phaser-dep + Auslieferung
[ ] F2   Datentabellen → core/data + core/models (typisiert)
[ ] F3   WebSocketService + GameStateService (Signals)
[ ] F4   Phaser als Renderer (ggf. F4a Tiles / F4b Sprites / F4c Input)
[ ] F5   Panel: HUD
[ ] F6   Panel: Hotbar
[ ] F7   Panel: Inventar
[ ] F8   Panel: Skills/Talente/Charakter
[ ] F9   Panel: Quests
[ ] F10  Panel: Faktionen
[ ] F11  Panel: Party-Frame
[ ] F12  Overlays: Loot-Roll / Raid / Group-Invite
[ ] F13  Panel: Spellbook / Cast-Bar
[ ] F14  Panel: Chat
[ ] F15  Panel: Downed-Overlay
[ ] F-PWA  @angular/pwa, altes sw.js entfernt
[ ] F-final  app.js gelöscht, style.css migriert
```