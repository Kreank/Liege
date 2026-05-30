# Frontend-Implementierungs-Plan — Welle H+

> Stand: 2026-05-31. Single-Source-of-Truth für alle Frontend-Lücken bis das
> Spiel wieder vollständig wie vor dem großen Refactor (Welle F1-F-final + G1-G4)
> funktioniert.
>
> Methodik: Das Backend wurde verhaltenserhaltend portiert und ist überall ✓.
> Frontend-Status pro Feature:
> - ✅ **Full** — Backend ✓, GameState handelt, Komponente rendert sichtbar.
> - 🟡 **Partial** — wesentliche Teile da, aber konkrete Lücken benannt.
> - ⚠ **Stub** — GameState/Komponente existiert, aber UI-Reaktion fehlt.
> - ✗ **Missing** — WS-Event versickert in GameState oder wird gar nicht behandelt.
>
> Quelle: `docu/WS_PROTOCOL.md` (904 Z., 69 Client→Server-Types, ~95
> Server→Client-Types), `frontend/src/app/core/services/game-state.service.ts`
> (1169 Z., zentraler Dispatch), `frontend/src/app/ui/**` (30 Komponenten),
> `frontend/src/app/game/world-scene.ts` (969 Z., Phaser-Renderer + FX-Wiring).

## Inhaltsverzeichnis

1. [Charaktererstellung & Progression](#1-charaktererstellung--progression)
2. [Bewegung & Welt](#2-bewegung--welt)
3. [Kampf](#3-kampf)
4. [Loot & Inventar](#4-loot--inventar)
5. [Quests](#5-quests)
6. [Dialog & NPC-Interaktion](#6-dialog--npc-interaktion)
7. [Gruppen & Raids](#7-gruppen--raids)
8. [Dungeons](#8-dungeons)
9. [Bauen & Strukturen](#9-bauen--strukturen)
10. [Forschung & Talente & Spells](#10-forschung--talente--spells)
11. [Crafting & Bill-Queue](#11-crafting--bill-queue)
12. [Trade & Wallet](#12-trade--wallet)
13. [Welt-Events & Storyteller](#13-welt-events--storyteller)
14. [Disaster, Weather & Earthquake](#14-disaster-weather--earthquake)
15. [Tag/Nacht & Time](#15-tagnacht--time)
16. [NPC-Lebenswelt (Goals/Mood/Chatter)](#16-npc-lebenswelt-goalsmoodchatter)
17. [Minimap-Features](#17-minimap-features)
18. [Toast/Notification-Infrastruktur](#18-toastnotification-infrastruktur)
19. [Audio & Sound](#19-audio--sound)
20. [Reihenfolge & Aufwand](#20-reihenfolge--aufwand)
21. [Anhang: Server→Client Event-Coverage-Matrix](#21-anhang-event-coverage-matrix)

---

## 0. Generelle Hot Spots vorab

Drei Querschnitts-Lücken, die in fast jeder Sektion wieder auftauchen — sie
sind die **Top-Priorität für Welle H1**, weil sie ~40 % der UI-Lücken in
einem Schlag schließen:

1. **Toast-Infrastruktur fehlt komplett.** Backend sendet >150 `toast`-Frames
   für jeden denkbaren Erfolg/Fehler (Stamina-Mangel, Tool-Hinweis, Quest-
   Limit, Faction-Toast, Trinken-Erfolg, Raid-Cooldown, …). GameState
   `case 'toast'` ist ein expliziter No-op (`game-state.service.ts:362`).
   Folge: Spieler bekommt für ~70 % der Aktionen keinerlei Feedback.
   → Siehe Sektion 18.
2. **`event` / `world_event` werden in Signal `events` geschoben, aber kein
   Panel rendert sie.** Backend feuert sie für Welt-Lore (Storyteller-LLM),
   Disaster-Ansagen, Raid-Wellen, Strukturen-Highlights, ... Die Chronik-
   Lane fehlt → Siehe Sektion 13.
3. **`skill_xp` versickert.** Floating-Text-Anker wäre Hotbar/HUD, gibt aber
   kein Floating-Number-FX. Auch keine Toast-Notification beim Level-Up.
   → Siehe Sektion 3 (Combat-Floats) und Sektion 10 (Skill-Level-Up).

---

## 1. Charaktererstellung & Progression

### Backend-Features (alle ✓)
- `character_check_name {display_name}` → `character_name_check {name, available, reason}`.
- `character_create {preset, allocated, display_name}` → `character_created {preset, display_name, allocated, unspent}`.
  - Backend akzeptiert bereits `allocated: dict` im `character_create`-Frame
    (siehe `ws/character.py`); kann die Initial-Stat-Verteilung also direkt
    persistieren.
- `allocate_attr {attr, n}` (range −50..+50) → `attrs_update {attributes, stats}` oder `toast` bei Fehler.
- `list_attributes` → `attributes_update {attributes}`.
- `list_talents` → `talents_update {learned, points, tree}`.
- `init` liefert: `attributes`, `stats`, `power_tier`, `skills`, `body_parts`,
  `talents`, `learned_spells`, `needs_character_creation`, `preset`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Modal-Pflicht bei `needs_character_creation=true` | ✅ Full | `ui/character-create/character-create.component.ts` | z-index 9999, kein Schließen-Button. |
| Name-Live-Check (Debounce, Status-Icon) | ✅ Full | dito | sendet `character_check_name`, hört auf `character_name_check`. |
| Preset-Auswahl (6 Walk-Cycle-Charaktere) | ✅ Full | dito | Wanderer / Glutmagier / Eisengräber / Klingenläufer / Schildträger / Wildhüter. |
| **Initial-Stat-Verteilung im Modal** | ✗ Missing | dito | Step 2 fehlt. Modal sendet `character_create` ohne `allocated` — Backend startet mit Default-Punkten ungenutzt im Pool. |
| Stat-Allocation-Panel (Taste `C`) | ✅ Full | `ui/character/character.component.ts` | 6 Attribute, +/−-Buttons, Unspent-Counter, Stat-Sheet (9 Stats). |
| Skills-Panel (Taste `K`) | ✅ Full | `ui/skills/skills.component.ts` | XP-Bars, Level, Icons für 11 Skills. |
| Talents-Panel (Taste `T`) | 🟡 Partial | `ui/talents/talents.component.ts` | Rendert nur, wenn `talents.tree` vom Server kommt. Default `tree: []` zeigt nichts. |
| **Skill-Level-Up-Toast** | ✗ Missing | – | `skill_xp` mit `level_up: true`-Hinweis wird nicht visuell aufgegriffen. |
| Spellbook (Taste `P`) | ✅ Full | `ui/spellbook/spellbook.component.ts` | Healer/Mage-Tabs, Status (gelernt/Skill-Locked), Detail-Box. |

### Aufgaben für H1
- [ ] **H1.1** `character-create.component`: Step-2-Pane „Attribute verteilen" hinzufügen.
  - Felder: 6 Attribute, +/−-Buttons, Counter „X von Y Punkten verteilt".
  - Default-Pool: 5 (im Backend in `services/player_state.py` definiert, vom `init`-Frame als `attributes.unspent` lesbar — fallback 5).
  - „Charakter erstellen"-Button sendet jetzt `{type:'character_create', display_name, preset, allocated: {strength, …}}`.
  - DoD: nach Modal-Close startet der Spieler mit verteilten Attributen sichtbar im Stat-Sheet.
  - Effort: mittel.
- [ ] **H1.2** Talents-Panel: Wenn `talents.tree` leer ist, statt leeren Panels einen Hinweis „Talente werden ab Skill-Level X freigeschaltet" zeigen + Skill-Requirements der nicht-erreichten Stufe.
  - Backend liefert `talents.tree` ab Welle 23+; aktuell ist die Liste meistens leer → Komponente wirkt kaputt.
  - DoD: Panel nie blank.
  - Effort: klein.

### Aufgaben für H3 (Polish)
- [ ] **H3.1** Skill-Level-Up: GameState hört auf `skill_xp` und prüft, ob `level` höher als zuvor → Toast `🎉 Holzfällen jetzt Stufe 12`.
  - Effort: klein (sobald Toast-Infrastruktur aus H1 steht).

---

## 2. Bewegung & Welt

### Backend-Features (alle ✓)
- `move {x, y}` → `player_moved`, `chunks` (bei Chunk-Wechsel), `trap_triggered`, Auto-Pickup, …
- `sprint {on}` → kein direkter Response, Needs-Loop steuert Stamina-Drain.
- Server→Client: `player_moved`, `chunks`, `player_joined`, `player_left`, `player_needs`, `player_damaged` (Falle), `player_downed` (Falle), `trap_triggered`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Klick → `move` | ✅ Full | `game/world-scene.ts::handleTileClick` | Dedup gegen Spam, kontextueller Switch (NPC/Item/Struktur/Move). |
| Sprint-Edge (`Shift`) | ✅ Full | `game/world-scene.ts::handleSprintChange` | Sendet nur on/off-Edges. |
| Auto-Pickup (Walk-over) | ✅ Full | GameState `inventory_add`/`item_picked_up` werden gehandelt. |
| Chunk-Streaming | ✅ Full | GameState `_handleChunks` (Z. 714) merged korrekt. |
| Player-Sprites + Walk-Animation | ✅ Full | `world-scene.ts::updatePlayerSprite` mit Direction-Tracker + Idle-Fallback. |
| Online-Spieler-Liste + Join/Leave | ✅ Full | GameState `_handlePlayerJoined`/`_Left`. |
| **Trap-Triggered (Falle ausgelöst)** | 🟡 Partial | `world-scene.ts:308` hat `visual_effect` + `npc_damaged`. Aber `trap_triggered` selbst geht in den `default`-Branch von `handleFxMessage` → kein dedizierter FX, keine Sound, kein Toast. |
| **Coords im HUD** | ✅ Full | `hud.component.ts::coords` zeigt `x:Y y:Z`. |

### Aufgaben für H2
- [ ] **H2.1** WorldScene: `trap_triggered`-Handler ergänzen.
  - Verhalten: roter Hit-Spark auf Spieler-Tile + Toast `⚠ Falle ausgelöst (X Schaden)`.
  - Effort: klein.

---

## 3. Kampf

### Backend-Features (alle ✓)
- `attack_npc {npc_id}` → `npc_damaged`, `npc_died`, `visual_effect` (Waffen-FX), `wallet_update` (Coin-Drop), `quest_progress`, `factions_update`, `loot_roll_started`, `skill_xp` (geteilt mit Group), `item_spawned`.
- `attack_structure {x, y}` → `structure_damaged`, `structure_removed`, `structure_placed` (Trümmer).
- `cast_spell {spell_id, target_x, target_y, target_npc_id}` neuer Pfad + `cast_spell {item_id}` Legacy-Pfad.
- `cast_learned {spell_kind}` Legacy-Direct-Cast.
- Server→Client: `npc_damaged`, `npc_died`, `npc_spawned`, `npc_moved`, `player_damaged`, `player_healed`, `player_mana`, `body_part_damaged`, `visual_effect`, `cast_started`, `cast_interrupted`, `cast_finished`, `status_effects`, `skill_xp`.

### Frontend-Status — Combat-Core

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Click-Attack (hostile NPC) | ✅ Full | `world-scene.ts:381`. |
| Damage-Floating-Numbers | ✅ Full | `world-scene.ts::fxNpcDamaged` + `fxPlayerDamaged`. |
| Hit-Spark | ✅ Full | `combat-fx.ts::spawnHitSpark`. |
| Death-Fade-Animation | ✅ Full | `world-scene.ts::fxNpcDied`. |
| Screen-Shake bei Heavy-Hit | ✅ Full | `combat-fx.ts::screenShake` (skaliert mit dmg). |
| Player-Healed-Floats (`+N`) | ✅ Full | `world-scene.ts::fxPlayerHealed`. |
| HP-/Mana-Bar im HUD | ✅ Full | `ui/hud/hud.component.ts`. |
| **Mob-HP-Bar über Sprite** | ✗ Missing | – | `npc_damaged` hat hp/max_hp, aber kein floating Mob-Bar wie in Legacy (war eine `Phaser.GameObjects.Graphics`-Bar über jedem Mob). |
| Body-Parts-Anzeige | 🟡 Partial | `character.component.ts` rendert sie nicht; `body_parts` wandert in `player`-Signal. Im Stat-Panel fehlt eine Body-Parts-Section. |

### Frontend-Status — Spell-System

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Cast-Bar | ✅ Full | `ui/cast-bar/cast-bar.component.ts` + FX-Sprites-Fallback. |
| Cast-Interrupt durch Bewegung (visuell) | ✅ Full | GameState clearts `activeCast` bei `cast_interrupted`. |
| Spellbook-UI | ✅ Full | `ui/spellbook/`. |
| **Spell-Target-Selection (Click-to-Cast)** | ✗ Missing | – | Hotbar/Spellbook hat keinen Ground-Target-Mode für AoE-Spells. `cast_spell` mit `target_x`/`target_y` wird nirgends gefeuert. Aktuell nur Self-Cast über `cast_learned`. |
| **`visual_effect` für Spell-Resolve (Multi-Frame)** | ✅ Full | `visual-effects.ts::spawnMultiFrameAnim` + `effect-animations.service.ts` (G4). |
| Status-Effects-Anzeige | 🟡 Partial | `statusEffects`-Signal wird gefüllt, aber kein Panel listet aktive Buffs/Debuffs auf. HUD-Reihe `#status-effects-row` aus Legacy fehlt. |
| Mana-Cost-Indicator | ✗ Missing | – | Hotbar zeigt nicht „Mana ausreichend?" für Spell-Slots. |
| Cooldown-Overlay auf Hotbar-Slot | 🟡 Partial | `hotbar.component.ts::cooldownsRemaining` ist ein leerer Hook (siehe Z. 119). Backend liefert `cast_finished {cooldown_ms}` — wird nicht in den Cooldown-Tracker geschoben. |

### Frontend-Status — Sub-Events

| Event | Behandelt? | Detail |
|---|---|---|
| `body_part_damaged` | ✅ Full | GameState patcht `player.body_parts`. Aber: kein Panel zeigt es. |
| `status_effects` (Bag) | ✅ Full | Signal gepflegt; **kein UI** liest es. |

### Aufgaben für H1
- [ ] **H1.3** Status-Effects-Reihe im HUD.
  - Position: zwischen Connection-Status und HP-Bar.
  - Pro `statusEffects()`-Eintrag ein kleines Icon (24×24) + Tooltip mit `kind`, `remaining_s`.
  - DoD: Blessed-Buff vom Holy-Spell ist 30s sichtbar.
  - Effort: mittel.

### Aufgaben für H2
- [ ] **H2.2** Mob-HP-Bar.
  - `world-scene.ts`: bei jedem `npc_damaged` oder bei NPC mit `hp < max_hp`
    eine schmale 24×3-Bar über dem Sprite einblenden (auto-fade nach 4 s).
  - DoD: nach Hit sieht man den HP-Verlust visuell, nicht nur als Float.
  - Effort: mittel.
- [ ] **H2.3** Spell-Target-Selection-Mode.
  - Hotbar/Spellbook: Klick auf Spell mit `requires_target=true` aktiviert
    Ziel-Mode (Cursor-Anpassung). Nächster Klick auf NPC → `cast_spell {spell_id, target_npc_id}`,
    Klick auf leeres Tile → `cast_spell {spell_id, target_x, target_y}`.
  - DoD: AoE-Spell auf Bodenpunkt funktioniert; Single-Target-Heal auf
    Mitspieler funktioniert.
  - Effort: groß.
- [ ] **H2.4** Cast-Cooldown-Overlay in Hotbar.
  - `cast_finished {spell_id, cooldown_ms}` → in `cooldownsRemaining`-Map
    schreiben, mit RAF runterzählen, in Hotbar als Dark-Overlay rendern.
  - DoD: Slot bleibt nach Cast für CD-Dauer halbtransparent + Sekunden-Label.
  - Effort: klein.

### Aufgaben für H3 (Polish)
- [ ] **H3.2** Body-Parts-Section im Character-Panel.
  - Liste der `body_parts` mit hp/max_hp-Bar + Damaged-Highlight.
  - Effort: klein.
- [ ] **H3.3** Mana-Cost-Indicator: Hotbar-Spells mit `mana_cost > current_mana` rot tinten.
  - Effort: klein.

---

## 4. Loot & Inventar

### Backend-Features (alle ✓)
- `pick_item`, `drop_item`, `equip_item`, `unequip_item`, `use_item`, `split_stack`, `merge_stacks`.
- `chest_transfer_to`, `chest_transfer_from`.
- `loot_vote {roll_id, vote}`, `set_loot_rule {rule}`.
- Server→Client: `inventory_add`, `inventory_update`, `inventory_remove`, `inventory_full_refresh`, `wallet_update`, `item_spawned`, `item_picked_up`, `chest_open`, `chest_add`, `chest_remove`, `loot_roll_started`, `loot_roll_resolved`, `loot_roll_voted`, `loot_rule_changed`, `loot_vote_error`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Inventar-Modal (Taste `I`) | ✅ Full | `ui/inventory/` (493 Z.). |
| Drag/Drop intern (Reorder) | ✅ Full | localStorage-Persistenz. |
| Equip/Unequip Drag-Drop | ✅ Full | dito. |
| Split-Stack (Shift+Klick + Modal) | ✅ Full | dito. |
| Drop-Confirm-Modal | ✅ Full | dito. |
| Stack-Counter + Quality-Border | ✅ Full | dito. |
| Hotbar 1-9 | ✅ Full | `ui/hotbar/` (440 Z., Drag-Drop, localStorage). |
| Item-Tooltip | ✅ Full | `ui/item-tooltip/` + `tooltip.service.ts`. |
| Chest-Modal | ✅ Full | `ui/chest/` + GameState `_handleChestOpen/Add/Remove`. |
| Wallet-HUD-Anzeige | ✗ Missing | – | `walletCopper`-Signal wird gepflegt, aber **kein dedizierter Wallet-Display**. Nur Inventar zeigt es im Footer. |
| Auto-Pickup-Toast (`+1 Eichenholz`) | ✗ Missing | – | Backend macht silent, Legacy hatte das als Floating-Text. |
| **Loot-Roll-Overlay (Need/Greed/Pass)** | ✅ Full | `ui/loot-roll/` mit Countdown. |
| `loot_roll_voted` (Vote-Count-Update) | ⚠ Stub | GameState `case 'loot_roll_voted': break` — kein Live-Counter im Overlay (wäre zB „2/4 gevotet"). |
| `loot_rule_changed` Anzeige | ⚠ Stub | GameState `case 'loot_rule_changed': break` — Party-Frame zeigt nicht „aktuelle Regel: FFA". |
| `loot_vote_error` | ✗ Missing | – | wird nicht behandelt; landet im `default` → `console.warn`. |
| `fill_container` / `water_plant` / `drink_container` / `drink_water_tile` Intents | ✗ Missing | – | Backend akzeptiert sie, aber **keine UI-Buttons** im Inventar (Right-Click-Menü auf Container fehlt). |
| `dungeon_chest` Intent | 🟡 Partial | `use_structure` auf Chest in Dungeon sendet `dungeon_chest` nicht — aktuell wird `use_structure` gefeuert, das fängt das Backend für Dungeon-Chests **nicht** ab. Folge: Dungeon-Boss-Truhe nicht öffenbar. |

### Aufgaben für H1
- [ ] **H1.4** Wallet-HUD-Display.
  - Kleine Münzen-Anzeige neben dem HP-/Mana-Bars-Panel.
  - DoD: Verkauf einer Beere → Wallet steigt sichtbar um 1 Kupfer.
  - Effort: klein.
- [ ] **H1.5** Dungeon-Chest-Öffnen.
  - `world-scene.ts::handleTileClick`: wenn Tile-Struktur `boss_chest`/`dungeon_chest` und Spieler im Dungeon → `bridge.sendIntent({type:'dungeon_chest', x, y})` statt `use_structure`.
  - DoD: Boss-Truhe spawnt Loot + Currency.
  - Effort: klein.

### Aufgaben für H2
- [ ] **H2.5** Auto-Pickup-Floating-Text.
  - Bei `inventory_add` während Move-Event → FloatingNumber am Spieler `+1 Eichenholz`.
  - Effort: klein.
- [ ] **H2.6** Container-Aktionen im Inventar.
  - Right-Click auf Wasser-Container öffnet Mini-Menü: „Auffüllen / Trinken / Pflanze gießen".
  - „Auffüllen" + „Gießen" gehen in Ground-Target-Mode (analog Spell-Target).
  - DoD: leeres Wasserfass → an See füllen → an Acker gießen funktioniert.
  - Effort: mittel.
- [ ] **H2.7** Loot-Roll Vote-Count + Loot-Rule-Status.
  - Overlay zeigt „2/4 gevotet" pro Aktualisierung.
  - PartyFrame zeigt „Loot: Need/Greed" als Subtext.
  - `loot_vote_error` → Toast `🎲 Vote ungültig: {reason}`.
  - Effort: klein.

---

## 5. Quests

### Backend-Features (alle ✓)
- `list_quests` → `quests_update`.
- `query_npc_quests {npc_id}` → `npc_quest_status {offers, turnins}`.
- `accept_quest_template {template_id, npc_id}` → `quest_new`, `npc_spawned` (bei Kill-Quest-Spawn-Garantie), `toast`, `skill_xp`.
- `accept_quest_from_npc {npc_id}` → `quest_new`, `skill_xp`, `toast`.
- `quest_turn_in {quest_id, npc_id}` → `quest_closed`, `inventory_add`, `wallet_update`, `skill_xp`, `toast`, `factions_update`.
- `claim_quest_reward {quest_id}` → analog.
- Server→Client: `quest_new`, `quest_progress`, `quest_closed`, `quests_update`, `npc_quest_status`, `quest_board_open`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Quest-Panel (Taste `Q`) | ✅ Full | `ui/quests/quests.component.ts` (109 Z.). |
| Liste aktiver/verfügbarer/abgeschlossener Quests | ✅ Full | dito, sortiert nach State. |
| Accept-Button | ✅ Full | sendet `accept_quest_template` oder `accept_quest_from_npc`. |
| Claim-Reward-Button | ✅ Full | sendet `claim_quest_reward`. |
| Turn-In-Button | ✅ Full | sendet `quest_turn_in`. |
| **Quest-Marker auf Minimap** | ✗ Missing | `ui/minimap/minimap.component.ts:13` sagt explizit: „Quest-Markierungen ... kein State-Ziel der Migration". |
| **Quest-Marker im Welt-Renderer (Pfeil/Outline)** | ✗ Missing | – | Legacy zeigte einen „!"-Marker über Quest-NPCs und einen Highlight-Ring über Quest-Ressourcen. |
| **Quest-Board-Modal** | ✗ Missing | – | `quest_board_open {board_id, offers}` wird vom Backend gesendet (wenn Spieler ein `quest_board` benutzt), aber GameState `case 'quest_board_open': /* UI-Trigger */ break` ist No-op. Komponente existiert nicht. |
| **NPC-Quest-Status-Anzeige** | 🟡 Partial | `ui/dialog/dialog.component.ts::askQuest` sendet `query_npc_quests` — aber `npc_quest_status` wird in GameState ignoriert (`case 'npc_quest_status': break`). Antwort versickert. |
| `quest_new`-Toast | ✗ Missing | – | Backend sendet zusätzlich `toast` mit Titel, aber Toast-Infrastruktur fehlt → Spieler sieht Quest-Erhalt nur, wenn Panel offen ist. |
| Quest-Progress-Indikator | 🟡 Partial | Panel zeigt es, aber **kein Floating-Notification** beim Mob-Kill „Quest 3/5 erledigt". |
| Quest-Reward-Modal (mit Item-Icons) | ✗ Missing | – | Reward kommt als `inventory_add` + Wallet — kein Reward-Screen mit Animation. |
| Folge-Quest-Trigger | 🟡 Partial | Backend sendet bei `quest_turn_in` evtl. einen neuen `quest_new`-Frame; UI zeigt ihn dann im Panel, aber kein „Folge-Quest verfügbar"-Cue. |

### Aufgaben für H1
- [ ] **H1.6** Quest-Board-Modal-Komponente neu bauen.
  - Datei: `ui/quest-board/quest-board.component.ts`.
  - State: in GameState `activeQuestBoard` signal hinzufügen, in `_handleQuestBoardOpen` setzen.
  - UI: Liste der `offers`, jede Zeile mit „Annehmen"-Button → `accept_quest_template`.
  - DoD: `use_structure` auf `quest_board` → Modal öffnet sich, Offer annehmbar.
  - Effort: mittel.
- [ ] **H1.7** Quest-Marker auf Minimap.
  - GameState neue Signals: `questMarkers: {x, y, kind: 'kill'|'collect'|'turnin'}[]`.
  - Befüllen aus `quests()`-Signal: pro aktiver Quest und `quest.target_npc_id`-Position bzw. `quest.target_x/y` (siehe Quest-Model `target_*`-Felder).
  - Minimap `_draw` rendert sie als gelbe Pulse-Punkte.
  - DoD: Quest „Töte 5 Wölfe" zeigt Wolf-Cluster auf Minimap als Marker.
  - Effort: mittel.

### Aufgaben für H2
- [ ] **H2.8** NPC-Quest-Status-Handler im Dialog.
  - GameState neuer Signal `activeNpcQuestStatus` + `case 'npc_quest_status'`.
  - Dialog-Komponente zeigt unter Verlauf einen „Aufträge"-Tab mit `offers`/`turnins`.
  - DoD: „Fragen" im Dialog listet 1-2 Quest-Angebote auf.
  - Effort: mittel.
- [ ] **H2.9** Quest-Progress-Toast.
  - Bei `quest_progress`-Frame: Toast `📋 Quest: 3/5 Wölfe erledigt`.
  - Effort: klein (hängt an Toast-Infrastruktur).
- [ ] **H2.10** Quest-New-Toast.
  - Bei `quest_new`-Frame: Toast `📜 Neue Quest: {title}` + Sound-Stub.
  - Effort: klein.

### Aufgaben für H3 (Polish)
- [ ] **H3.4** Quest-Reward-Modal.
  - Bei `quest_closed` (mit zugehörigem Inv-/Wallet-Delta): Modal „Belohnung erhalten" mit Item-Icons, schließt nach 4s oder Klick.
  - Effort: mittel.
- [ ] **H3.5** Quest-Marker im Welt-Renderer.
  - Phaser: über Quest-NPCs ein „!"-Sprite (Goldgelb, Bobbing-Tween).
  - Über Quest-Ressourcen (z. B. „Sammle 10 Schwarzbeeren"): Highlight-Ring um passende Strukturen.
  - Effort: groß.

---

## 6. Dialog & NPC-Interaktion

### Backend-Features (alle ✓)
- `talk_to_npc {npc_id, message}` → `npc_reply {text}` + ggf. `quest_progress`.
- Server→Client: `npc_reply`, `npc_speech` (Chatter aus npc_chatter), `npc_mood`, `npc_goal`, `npc_attacked`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Dialog-Modal | ✅ Full | `ui/dialog/dialog.component.ts`. |
| Eingabefeld + Verlauf | ✅ Full | dito, mit Typing-Indicator. |
| Frage-nach-Quest-Button | 🟡 Partial | sendet `query_npc_quests`, aber Antwort versickert (siehe Sektion 5). |
| Click-to-Talk auf friendly NPC | ✅ Full | `world-scene.ts:383` sendet `talk_to_npc` ohne `message` → Dialog öffnet sich. |
| Aber: leere `message` → Backend `skip` | ✗ Bug | `talk_to_npc` braucht `message: required` — leer wird im Backend silent verworfen. **Frontend sendet eine leere Message beim ersten Click → kein Reply, Dialog-Modal öffnet sich nicht.** Stattdessen sollte das Frontend nur das Modal öffnen (lokaler State, `openDialog`) und erst beim ersten Send einen Server-Roundtrip machen. |
| **`npc_speech` (Sprechblase)** | ✗ Missing | GameState `case 'npc_speech': break`. Backend sendet sie aus `npc_chatter` (Stadt-Chatter) — nirgendwo gerendert. |
| **`npc_mood`** | ✗ Missing | GameState `case 'npc_mood': break`. Sollte Mood-Icon über NPC-Sprite zeigen (😡 / 😴 / 🥰). |
| **`npc_goal`** | ✗ Missing | GameState `case 'npc_goal': break`. Sollte bei eigenem NPC einen Tooltip „pflügt Feld" zeigen — vor allem für Companion-System. |
| **`npc_attacked`** | ✗ Missing | GameState `case 'npc_attacked': break`. Sollte bei eigenem Pet/Companion Toast `Dein Hund wird angegriffen!` triggern. |

### Aufgaben für H1
- [ ] **H1.8** Click-to-Talk-Fix.
  - `world-scene.ts::handleTileClick`: bei friendly NPC nicht `sendTalkToNpc` direkt, sondern `state.openDialog({npc_id, npc_name, npc_kind, backstory:''})`.
  - DoD: Click auf NPC → Dialog-Modal öffnet sich ohne Reply-Frage, Eingabefeld leer.
  - Effort: klein.

### Aufgaben für H2
- [ ] **H2.11** NPC-Sprechblasen (Phaser-Renderer).
  - Bei `npc_speech {npc_id, text}` → über NPC-Sprite eine kleine Bubble mit Text (1.5 s sichtbar).
  - DoD: Stadtwachen-Chatter wird sichtbar.
  - Effort: mittel.

### Aufgaben für H3 (Polish)
- [ ] **H3.6** NPC-Mood-Icon (Phaser).
  - `npc_mood {npc_id, mood}` → kleines Mood-Sprite-Overlay (😡/😴/🥰) über NPC. Existing Asset-Pfad: `assets/effects/npc_mood_*.png` (TODO: checken).
  - Effort: klein.
- [ ] **H3.7** Companion-Toast: `npc_attacked` für eigene Companions/Pets.
  - Effort: klein.

---

## 7. Gruppen & Raids

### Backend-Features (alle ✓)
- `group_create_party`, `group_invite`, `group_accept`, `group_decline`, `group_leave`, `group_kick`, `group_promote`, `group_transfer_leader`, `group_disband`, `group_refresh`, `group_chat`, `group_convert_to_raid`.
- `raid_trigger_manual {tier}` → `raid_started`.
- `set_loot_rule {rule}` → `loot_rule_changed`.
- Server→Client: `group_state`, `group_invite_received`, `group_invite_sent`, `group_disbanded`, `group_kicked`, `group_member_left`, `group_member_online`, `group_member_offline`, `group_converted`, `group_chat`, `group_error`, `raid_started`, `raid_error`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Party-Frame | ✅ Full | `ui/party-frame/` (154 Z.) mit Sub-Party-Sections für Raids. |
| Invite-Overlay | ✅ Full | `ui/group-invite/`. |
| Raid-Selector | ✅ Full | `ui/raid-selector/`, T1-T5. |
| Group-Chat über Slash-Commands | ✅ Full | `ui/chat/chat.component.ts` `_handleSlash`. |
| Group-State-Updates | ✅ Full | GameState handelt `group_state`, `group_converted`, `group_member_online/offline`. |
| `group_chat`-Empfang | ✅ Full | GameState `_handleGroupChat` → Chat-Log mit kind=`group`. |
| **Mob-Skalierung Visual** | ✗ Missing | – | Backend skaliert Mobs für Gruppen automatisch (siehe `power_budget.py`, `region_difficulty.py`), aber Mob-Tooltip/Mob-HP-Bar zeigt keine „Skaliert: 4×"-Info. |
| **Gruppen-XP-Tooltip** | ✗ Missing | – | `skill_xp`-Frame hat ein `shared`-Flag bzw. mehrere Empfänger; UI zeigt nicht „+12 XP (geteilt mit 3 Spielern)". |
| Member-Position auf Minimap | 🟡 Partial | `minimap.component.ts` zeichnet `players`, aber differenziert nicht zwischen Group-Member (grün) und sonstigen Online-Spielern (blau). |
| `raid_started`-Anzeige | ⚠ Stub | GameState `case 'raid_started': /* Visual-Event */ break` — keine Toast, kein Welt-Event-Eintrag. |
| `group_kicked` | ✅ Full | GameState `case 'group_kicked': this.party.set(null)` — aber **kein Toast** an den Gekickten. |
| `group_error`-Reasons (`not_in_group`, `leader_only`, etc.) | ⚠ Stub | GameState skipt; Spieler bekommt keinen Hinweis warum sein Befehl gescheitert ist. |
| `raid_error`-Reasons (Cooldown, etc.) | ⚠ Stub | dito. |

### Aufgaben für H1
- [ ] **H1.9** Group-/Raid-Error-Toasts.
  - GameState: in `case 'group_error'` und `case 'raid_error'` Toast emittieren.
  - DoD: `/raidstart 1` während Cooldown → Toast `🚫 Raid-Cooldown: noch 47 s`.
  - Effort: klein.

### Aufgaben für H2
- [ ] **H2.12** Minimap-Differenzierung Group-Member.
  - Group-Member als grüner Punkt (`#88ff88`), andere Online-Spieler bleiben blau (`#a0c8ff`).
  - Effort: klein.
- [ ] **H2.13** `raid_started`-Welt-Event + Toast.
  - GameState: Toast `⚔ Raid T{tier} startet ({by})` + `events.set([...events, ev])` für die Chronik (siehe Sektion 13).
  - Effort: klein.

### Aufgaben für H3 (Polish)
- [ ] **H3.8** Mob-Tooltip mit Power-Budget-Skalierungs-Info.
  - Hover über Mob: Tooltip mit `name, hp/max_hp, power_tier, scaled_for: 4`.
  - Effort: mittel.
- [ ] **H3.9** Skill-XP-Tooltip mit Group-Share-Info.
  - Bei `skill_xp` mit `shared_with: [..]` → Tooltip am Floating-Number „+12 XP (geteilt mit 3)".
  - Effort: klein.

---

## 8. Dungeons

### Backend-Features (alle ✓)
- `use_structure {x, y}` auf `stairs_down` → `dungeon_enter`.
- `move {x, y}` auf Treppen-Tile → `dungeon_floor_change` / `dungeon_exit`.
- `dungeon_chest {x, y}` → `dungeon_chest_opened`, `inventory_add`, `wallet_update`.
- Worker: `dungeon_director` (spawnt Dungeon-Marker), `dungeon_instance` (Floor-Maps), `dungeon_themes`.
- Server→Client: `dungeon_enter`, `dungeon_exit`, `dungeon_floor_change`, `dungeon_chest_opened`, `dungeon_collapsed`, `dungeon_sense`, `trap_triggered`, `npc_spawned` (Floor-Mobs).

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Dungeon-Marker auf Minimap | 🟡 Partial | `minimap.component.ts:189` zeichnet `dungeons` als lila Punkte. Aber **kein Sense-Radius** (Legacy zeigte nur Dungeons in 70-Tile-Chebyshev). |
| Dungeon-Spawn-Sprite in der Welt | ✅ Full | über `structures()`-Signal (Stairs-Struktur). |
| **`dungeon_enter` Floor-Map-Anzeige** | ✗ Missing | GameState `case 'dungeon_enter': break`. Tile-Map des Floors wird **nicht** in die `chunks`-Signal-Form geladen. Folge: Spieler betritt Dungeon → Overworld-Chunks bleiben sichtbar, eigene Position wechselt aber. |
| `dungeon_floor_change` | ✗ Missing | GameState skipt. Spieler nimmt Treppe → kein Re-Render. |
| `dungeon_exit` | ✗ Missing | dito. |
| **`dungeon_chest_opened`** | ✗ Missing | GameState skipt. Backend setzt Chest auf `opened` — aber Frontend zeichnet sie weiter als ungenutzt. Sprite müsste auf „leer/offen"-Variante wechseln. |
| **`dungeon_collapsed`** | ✗ Missing | GameState skipt. Dungeon läuft ab → Spieler wird auf Overworld zurückgesetzt; UI zeigt keinen Hinweis. |
| **`dungeon_sense`** | ✗ Missing | GameState skipt. Wenn der Spieler ein „Spüre Dungeon"-Item nutzt, zeigt das Backend Dungeon-Positionen im Sense-Radius — wird ignoriert. Legacy hatte dafür einen kurzen Highlight-Pulse auf der Minimap. |
| `trap_triggered` | 🟡 Partial | GameState skipt (Sektion 2 Lücke). |

### Aufgaben für H1
- [ ] **H1.10** Dungeon-Floor-Rendering.
  - GameState: bei `dungeon_enter {tiles, size, spawn, floor_idx}` einen Spezial-Mode aktivieren:
    - `chunks`-Signal mit einem Single-Chunk aus `tiles` ersetzen.
    - `player.x/y` auf `spawn` setzen.
    - `dungeonMode`-Signal (neu) auf `{id, floor_idx, floor_count}` setzen.
  - WorldScene: keine Änderung nötig, weil sie `chunks` rendert.
  - HUD-Erweiterung: kleines Banner „Dungeon: Verfallene Krypta · Etage 1/4".
  - DoD: Treppe runter → Dungeon-Map sichtbar, Spieler auf Spawn.
  - Effort: groß.
- [ ] **H1.11** Dungeon-Floor-Change + Exit-Handler.
  - GameState: `dungeon_floor_change {tiles, spawn, floor_idx}` analog H1.10 reapply.
  - `dungeon_exit {tiles?, spawn}` → `dungeonMode` clearen, Overworld-Chunks aus dem nächsten `chunks`-Frame zeichnen.
  - DoD: Treppe rauf → nächste Etage sichtbar; Verlassen → wieder Overworld.
  - Effort: mittel.

### Aufgaben für H2
- [ ] **H2.14** Dungeon-Chest-Open-Sprite-Swap.
  - GameState: in `case 'dungeon_chest_opened' {x, y}` → die Struktur an (x,y) mit `type: 'chest_opened'` markieren (oder neue Variante via `structureLookup`).
  - DoD: geöffnete Chest visuell anders als ungeöffnete.
  - Effort: klein.
- [ ] **H2.15** Dungeon-Collapsed-Notification.
  - GameState: Toast `💥 Dungeon „{name}" eingestürzt — du wurdest hinausgeworfen`.
  - Effort: klein.

### Aufgaben für H3 (Polish)
- [ ] **H3.10** Sense-Radius-Visualisierung.
  - Bei `dungeon_sense {dungeons: [{x, y, radius}]}` → Minimap-Pulse-Animation an den Positionen für 5 s.
  - Effort: mittel.
- [ ] **H3.11** Dungeon-Marker-Sense-Filter auf Minimap.
  - `minimap.component.ts:185`: Chebyshev-Distance-Filter (default 70 Tiles) nachziehen.
  - Effort: klein.

---

## 9. Bauen & Strukturen

### Backend-Features (alle ✓)
- `place_structure`, `toggle_door`, `remove_structure`, `attack_structure`, `repair_structure`, `upgrade_structure`, `use_structure`.
- Server→Client: `structure_placed`, `structure_replaced`, `structure_removed`, `structure_damaged`, `structure_repaired`, `structure_upgraded`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Build-Bar (Taste `B`) | ✅ Full | `ui/build-bar/build-bar.component.ts` mit Kategorien/Subkategorien/Material/Rotation. |
| Place-Click | ✅ Full | `world-scene.ts:351` Build-Mode-Pfad. |
| **Place-Ghost (Preview-Sprite)** | ✗ Missing | – | Legacy zeigte ein halbtransparentes Preview-Sprite am Cursor; aktuell nur „Klick → platziert". |
| **Place-Validation-Highlight (rot/grün)** | ✗ Missing | – | Vor Place-Click kein Hinweis ob Tile frei ist. |
| **Rotation visuell** | 🟡 Partial | Build-Bar zeigt Winkel-Label, aber Preview rotiert nicht (gibt's nicht). |
| Wall-Auto-Tiling | ✅ Full | `world-scene.ts::updateStructureSprite` + `wall-tiler.ts`. |
| Door-Toggle | 🟡 Partial | Backend hat `toggle_door` — Frontend sendet aber `use_structure` → Backend mappt das auf `toggle_door`? **Nein**, `toggle_door` ist ein separates Intent (siehe WS_PROTOCOL.md Z. 280). Frontend müsste das gezielt senden. Aktuell: Door öffnet nicht. |
| Attack-Structure | ✅ Full | `world-scene.ts:402`, sendet bei harvestable. |
| Repair-Structure | ✗ Missing | – | Kein UI-Button und kein Hotkey. Backend bietet `repair_structure`, aber Frontend ruft es nie auf. |
| Upgrade-Structure | ✗ Missing | – | analog. |
| `structure_repaired` Frame | ✅ Full (Handler) | GameState handelt es als `structureDamaged`. Aber **kein Visual** (Heal-Pulse über Struktur fehlt). |
| `structure_upgraded` Frame | ✅ Full | GameState handelt es als `structureReplaced`. |
| Struct-Place-FX | ✅ Full | `visual_effect` (`wp_build_hammer`) wird von Backend gefeuert + WorldScene rendert es. |

### Aufgaben für H1
- [ ] **H1.12** Door-Toggle.
  - `world-scene.ts::handleTileClick`: für Struktur-Type-Prefix `door_*` (und `garden_gate_*`) statt `use_structure` → `bridge.sendIntent({type:'toggle_door', x, y})`.
  - DoD: Klick auf Holztür wechselt offen↔zu, Sprite wechselt via `structure_replaced`.
  - Effort: klein.

### Aufgaben für H2
- [ ] **H2.16** Place-Ghost-Preview.
  - WorldScene: bei `buildMode=true` ein halbtransparentes Sprite am Cursor-Tile rendern (folgt dem Mouse-Move). Sprite = `selectedStructure` (Texture-Key aus `assetLoader.textureKeyFor(...)`).
  - Tile-frei-Check: wenn `structures.find(...)` → Tint rot, sonst grün.
  - DoD: Bei aktivem Build-Mode sieht der Spieler an jeder Maus-Position eine Vorschau.
  - Effort: mittel.
- [ ] **H2.17** Repair/Upgrade-Buttons.
  - Right-Click auf eigene Struktur öffnet kleines Kontextmenü „Reparieren / Aufwerten / Entfernen".
  - DoD: Damaged Wall reparierbar; Stroh-Wand auf Holz aufwertbar.
  - Effort: mittel.

### Aufgaben für H3 (Polish)
- [ ] **H3.12** Repair-Heal-Pulse-Visual.
  - Bei `structure_repaired` → grüner Pulse-Ring an der Struktur.
  - Effort: klein.

---

## 10. Forschung & Talente & Spells

### Backend-Features (alle ✓)
- `invest_research {node_id, points}` → `research_update`.
- `learn_talent {talent_id}` → `talent_learned`, `toast`.
- `learn_spell {item_id}` → `spell_learned`, `skill_xp`, `inventory_full_refresh`.
- Server→Client: `research_update`, `research_pool_update`, `talent_learned`, `talents_update`, `spell_learned`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Research-Panel (Taste `R`) | ✅ Full | `ui/research/research.component.ts`. |
| +1/+5/+25-Invest-Buttons | ✅ Full | dito. |
| Pool-Banner | ✅ Full | dito. |
| Branch-Tabs | ✅ Full | dito. |
| `research_update`-Handler | ✅ Full | GameState `_handleResearchUpdate` mit Auto-Unlock von Folge-Nodes. |
| `research_pool_update` | ✅ Full | dito. |
| **Research-Complete-Toast** | ✗ Missing | – | `toast` „🔬 Forschung abgeschlossen ..." kommt vom Backend, versickert in Toast-Infrastruktur. |
| Talent-Panel (Taste `T`) | 🟡 Partial | s. Sektion 1 — Tree-Render fehlt bei leerem `tree`. |
| `talent_learned` | ✅ Full | GameState. |
| Spellbook (Taste `P`) | ✅ Full | s. Sektion 1. |
| `spell_learned` | ✅ Full | GameState merged in `spells.learned`. |
| **Spell-Item-Lern-UI** | 🟡 Partial | Backend braucht `learn_spell {item_id}`. Frontend: Inventory-Klick auf ein Spell-Item könnte den Lern-Intent senden, tut es aber nicht. Aktuell wird `use_item` gefeuert → Backend lehnt für Spell-Items ab. |

### Aufgaben für H2
- [ ] **H2.18** Spell-Item-Learning.
  - `inventory.component.ts::useOrEquip`: bei `category === 'spell_book'` → `bridge.sendIntent({type:'learn_spell', item_id})` statt `use_item`.
  - Voraussetzung: Item-Definition trägt `category: 'spell_book'` oder `kind`-Match auf `spell_scroll_*`.
  - DoD: Doppelklick auf „Feuerball-Scroll" → Spell wird gelernt, Item verschwindet, Spellbook zeigt neuen Spell.
  - Effort: klein.

### Aufgaben für H3 (Polish)
- [ ] **H3.13** Research-Complete-Animation.
  - Bei `research_update {done:true}`: Toast `🔬 {node_name} erforscht!` + kurzer Flash am Research-Icon im Top-Right.
  - Effort: klein.

---

## 11. Crafting & Bill-Queue

### Backend-Features (alle ✓)
- `open_hand_crafting` → `crafting_open`.
- `use_structure` auf Werkbank/Ofen/Amboss → `crafting_open`.
- `craft {station, recipe_id}` → `inventory_full_refresh`, `skill_xp`, `toast`.
- `add_bill`, `remove_bill`, `list_bills` → `bills_update`.
- Server→Client: `crafting_open`, `bills_update`, `bill_progress`, `bill_done`, `bill_blocked`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Crafting-Modal | ✅ Full | `ui/crafting/crafting.component.ts`. |
| Hand-Crafting öffnen | 🟡 Partial | Komponente sendet `open_hand_crafting` per Hotkey? **Checken** — aktuell hängt es nur am `crafting_open`-Frame. Spieler muss zu einer Station laufen. Hotkey für Hand-Crafting (im Legacy `H`) fehlt. |
| Recipe-Liste mit Ingredients | ✅ Full | dito. |
| Craft-Button | ✅ Full | sendet `craft`. |
| Bills-Panel | ✅ Full | `ui/bills/bills.component.ts`. |
| `bill_progress`/`bill_done`/`bill_blocked` | ✅ Full | GameState handelt sie. |
| `bill_blocked`-Reason-Toast | 🟡 Partial | Backend sendet `toast` mit Reason; versickert in Toast-Infrastruktur. |
| **Recipe-Discovery (Research-Lock)** | 🟡 Partial | Backend sendet `toast` „🔒 Erst forschen ...". Frontend zeigt das Rezept zwar greyed-out (?), aber kein Tooltip warum. |
| Quality-Roll-Erfolg-Toast | ✗ Missing | – | „⭐ Meisterwerk gefertigt!" versickert in Toast. |

### Aufgaben für H2
- [ ] **H2.19** Hand-Crafting-Hotkey.
  - Globaler Listener auf `H` → `ws.send({type:'open_hand_crafting'})`.
  - DoD: `H` öffnet ein Crafting-Modal mit allen Hand-Rezepten.
  - Effort: klein.
- [ ] **H2.20** Recipe-Lock-Tooltip.
  - Crafting-Modal: bei Rezepten mit `requires` → Tooltip „Forschung benötigt: {node_name}".
  - Effort: klein.

---

## 12. Trade & Wallet

### Backend-Features (alle ✓)
- `open_trade {npc_id}` → `trade_open {offerings, coins}`.
- `buy_item {kind}` → `inventory_full_refresh`, `wallet_update`, `trade_coins`.
- `sell_item {item_id}` → analog.
- Server→Client: `trade_open`, `trade_coins`, `wallet_update`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Trade-Modal | ✅ Full | `ui/trade/trade.component.ts`. |
| Offerings-Liste | ✅ Full | dito. |
| Buy-Button | ✅ Full | dito. |
| Sell-Button | 🟡 Partial | **Checken**: Trade-Component müsste auch Sell-Slots haben (Inventar-Item klicken → `sell_item`). Aktuell vermutlich nur Buy. |
| Coin-Display | ✅ Full | dito. |
| `wallet_update` Sync mit Trade | ✅ Full | GameState `_handleWalletUpdate` patcht auch `activeTrade.coins`. |
| Wallet-HUD | ✗ Missing | s. Sektion 4 H1.4. |
| Open-Trade-Trigger | 🟡 Partial | Klick auf Merchant-NPC → soll `open_trade` senden statt `talk_to_npc`. Aktuell: Friendly NPC = Dialog → Trade unerreichbar. |

### Aufgaben für H1
- [ ] **H1.13** Merchant-Detection.
  - `world-scene.ts::handleTileClick`: NPCs mit `kind: 'merchant'` (oder `is_merchant:true` aus NPC-Snapshot) → `bridge.sendIntent({type:'open_trade', npc_id})` statt `talk_to_npc`.
  - DoD: Klick auf Händler → Handels-Modal öffnet sich.
  - Effort: klein.

### Aufgaben für H2
- [ ] **H2.21** Sell-Tab im Trade-Modal.
  - Modal hat zwei Tabs: „Kaufen" (Offerings) + „Verkaufen" (Inventory-Items klickbar → `sell_item`).
  - DoD: Spieler kann Item an Händler verkaufen, Coin steigt.
  - Effort: mittel.

---

## 13. Welt-Events & Storyteller

### Backend-Features (alle ✓)
- Worker: `event_worker`, `storyteller`, `raid_director`.
- Server→Client: `event`, `world_event`.
  - `event {event: {id, ts, kind, text, x?, y?, severity?}}` — Stadt-Chronik.
  - `world_event` — größere Notifications (Disaster-Anfänge, Raid-Start, Dungeon-Spawn).

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| `event`-Handler | ✅ Full | GameState `_handleEvent` pusht in `events`-Signal (limitiert auf 50). |
| `world_event` | ✗ Missing | GameState hat **keinen** `case 'world_event'`. Landet im `default` → `console.warn`. |
| **Chronik-/Event-Log-Panel** | ✗ Missing | – | `events`-Signal wird nirgends gelesen. Im Legacy gab es ein „Welt-Chronik"-Panel, das die letzten 20 Events listete. Aktuell: kein Panel. |
| **`event` als Chat-System-Linie** | ✗ Missing | – | Legacy spiegelte wichtige Events in den Chat-Log; Frontend macht das nicht. |
| Storyteller-Output | ✗ Missing | – | Backend nutzt LLM für Welt-Erzählungen, die als `event` reinkommen — landet im Signal aber nirgends sichtbar. |
| `event_worker`-Disaster-Effekt-Trigger | ✗ Missing | – | Admin sendet `dev_trigger_event`, Backend feuert `disaster_started` + diverse Events. Spieler sieht Disaster-Tint (Sektion 14) — aber den Storyteller-Text nicht. |
| `raid_started` als Event | ⚠ Stub | s. Sektion 7 H2.13. |

### Aufgaben für H1
- [ ] **H1.14** `world_event`-Handler in GameState.
  - Neuer Case → in `events`-Signal pushen + zusätzlich als `chat`-Systemzeile spiegeln.
  - DoD: Disaster-Start → Spieler sieht im Chat „🔥 Eine schwelende Hitze überzieht das Land".
  - Effort: klein.
- [ ] **H1.15** Chronik-Panel (kleines Toggle-Panel).
  - Neue Komponente `ui/chronicle/` (Taste `J` für „Journal").
  - Liste der letzten 20 `events`-Einträge mit Timestamp + severity-Farbe.
  - DoD: `J` öffnet Panel mit den letzten Welt-Events.
  - Effort: mittel.

### Aufgaben für H2
- [ ] **H2.22** Welt-Event-Toast für hohe Severity.
  - Events mit `severity >= 'major'` → zusätzlich Toast.
  - Effort: klein.

---

## 14. Disaster, Weather & Earthquake

### Backend-Features (alle ✓)
- Worker: `disaster_state`, `weather_worker`.
- Server→Client: `disaster_started {kind, x?, y?}`, `disaster_ended {kind}`, `weather {kind, intensity}`, `earthquake_shake {intensity, duration_ms}`, `lightning_strike {x, y}`.
- Bekannte Kinds: `bloodmoon`, `dying_sun`, `thunderstorm`, `scorching_heat`, `ash_rain`, `wildfire`, `pestilence`, `locust_swarm`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| Disaster-Overlay (Tint, Particles, Bolt) | ✅ Full | `game/disaster-overlay.ts` (244 Z., G4). |
| `disaster_started`/`ended` Hookup | ✅ Full | `world-scene.ts::fxDisasterStarted` + `fxDisasterEnded`. |
| `earthquake_shake` | ✅ Full | `world-scene.ts::fxEarthquake`. |
| `lightning_strike` | ✅ Full | `world-scene.ts::fxLightningStrike` → Bolt-Sprite. |
| `weather`-Snapshot | 🟡 Partial | GameState `_handleWeather` füllt `weather`-Signal. Aber **kein Renderer** zeichnet Rain/Snow-Particles. Auch keine Anzeige im HUD. |
| **Disaster-Start-Toast** | ✗ Missing | – | `disaster_started` triggert nur Visual; kein Toast „🌑 Blutmond zieht auf — Mobs werden stärker". |
| **Disaster-Active-HUD-Anzeige** | 🟡 Partial | `active_disasters` kommt im `init`-Frame, aber das Signal wird gar nicht erst gehalten (kein Eintrag in GameState `_handleInit`). |

### Aufgaben für H1
- [ ] **H1.16** Active-Disasters-Signal + HUD-Icon-Reihe.
  - GameState: `activeDisasters`-Signal (Array of `{kind, started_at}`); aus `init.active_disasters` + bei `disaster_started`/`ended` patchen.
  - HUD: kleine Disaster-Icon-Reihe (z. B. unter Coords) mit Tooltip „Blutmond seit 2 min".
  - DoD: Blutmond aktiv → Icon sichtbar, Hover zeigt Beschreibung.
  - Effort: mittel.
- [ ] **H1.17** Disaster-Start/End-Toast.
  - Effort: klein.

### Aufgaben für H3 (Polish)
- [ ] **H3.14** Weather-Particles.
  - Bei `weather.kind === 'rain'`/`snow` Phaser-Particle-Emitter im Viewport.
  - Effort: mittel.

---

## 15. Tag/Nacht & Time

### Backend-Features (alle ✓)
- Worker: `time_system`.
- Server→Client: `time_tick`, evtl. `time_update`.

### Frontend-Status

| Feature | Status | Datei | Detail |
|---|---|---|---|
| `time_update`-Handler | ✅ Full | GameState `_handleTimeUpdate` füllt `time`-Signal. |
| `time_tick`-Handler | ✗ Missing | GameState hat **keinen** `case 'time_tick'`. Backend sendet das Frame, landet im `default`. (Backend nutzt `time_tick`, nicht `time_update` — Mismatch!) |
| **HUD-Time-Display** | ✗ Missing | – | `time`-Signal wird gefüllt, aber **kein Panel zeigt die Uhrzeit oder den Tag**. |
| **Tag/Nacht-Visual-Tint** | ✗ Missing | – | Legacy hatte ein dunkler-werdendes Overlay basierend auf `time.hour`. Aktuell: Dungeon-Tints arbeiten, aber Tag/Nacht-Cycle nicht. |
| Monster-Spawn-Bias (Tag/Nacht) | ✅ Backend, kein FE | Backend handlet das selbst (`npc_worker` + Time-Bias); UI hat keine Anzeige. |

### Aufgaben für H1
- [ ] **H1.18** `time_tick`-Handler.
  - GameState `case 'time_tick'` → analog `_handleTimeUpdate` (Frame ist `{time: TimeSnapshot}` oder direkt das Snapshot — Backend prüfen).
  - Effort: klein.
- [ ] **H1.19** HUD-Time-Display.
  - Kleines Time-Widget oben links: „Tag 12 · 18:30 · 🌅".
  - Effort: klein.

### Aufgaben für H2
- [ ] **H2.23** Tag/Nacht-Tint-Overlay.
  - DisasterOverlay erweitern: zusätzlicher `day_night_overlay`-Layer, der abhängig von `time.hour` einen blauen/violetten Tint zwischen 21:00-05:00 zieht.
  - Effort: mittel.

---

## 16. NPC-Lebenswelt (Goals/Mood/Chatter)

### Backend-Features (alle ✓)
- Worker: `npc_worker` (Goal-Picker), `npc_chatter` (LLM-Chatter), `npc_mood`.
- Server→Client: `npc_goal`, `npc_speech`, `npc_mood`, `npc_attacked`, `npc_reply`.

### Frontend-Status

| Event | Status | Detail |
|---|---|---|
| `npc_goal` | ✗ Missing | s. Sektion 6. |
| `npc_speech` | ✗ Missing | s. Sektion 6. |
| `npc_mood` | ✗ Missing | s. Sektion 6. |
| `npc_attacked` | ✗ Missing | s. Sektion 6. |
| `npc_reply` | ✅ Full | Dialog. |

Aufgaben siehe Sektion 6 (H2.11, H3.6, H3.7).

---

## 17. Minimap-Features

### Status-Übersicht

| Feature | Status | Detail |
|---|---|---|
| Tile-Layer | ✅ Full | |
| Strukturen-Punkte | ✅ Full | |
| NPC-Punkte (Friendly/Hostile) | ✅ Full | |
| Online-Spieler | ✅ Full | |
| Dungeon-Marker | 🟡 Partial | kein Sense-Radius-Filter. |
| **Quest-Marker** | ✗ Missing | s. Sektion 5 H1.7. |
| **Group-Member-Highlight** | ✗ Missing | s. Sektion 7 H2.12. |
| **Event-Pulse (Disaster, Raid, Bloodmoon)** | ✗ Missing | – | Legacy zeigte pulsierende rote Punkte für aktive Welt-Events. Komplett fehlend. |
| **Sense-Radius-Pulse** | ✗ Missing | s. Sektion 8 H3.10. |
| Eigener Spieler (Mitte) | ✅ Full | |

### Aufgaben (alle in Sektionen oben referenziert; hier nur Aggregat)
- H1.7 Quest-Marker
- H2.12 Group-Member-Differenzierung
- H3.10 Sense-Radius-Pulse
- H3.11 Dungeon-Sense-Filter
- **NEU H2.24** Event-Pulse für aktive Disaster:
  - Bei `activeDisasters().length > 0`: roter Pulse-Ring um Spieler-Position auf Minimap.
  - Effort: klein.

---

## 18. Toast/Notification-Infrastruktur

> **Kritisch — blockt mehrere andere Wellen.** Backend feuert >150 verschiedene
> `toast`-Frames. Ohne Toast-UI versickern ~70 % aller User-Feedback-Hinweise.

### Lückenanalyse
- GameState `case 'toast': break` (Z. 362) — expliziter No-op.
- `appendChat({kind:'system'})` wird als provisorischer Ersatz genutzt
  (Hotbar, World-Scene), ist aber kein passender Trigger weil viele Spieler
  den Chat nicht offen haben.

### Aufgaben für H1
- [ ] **H1.20** `ToastService`-Implementierung.
  - Neue Datei: `core/services/toast.service.ts`.
  - API: `push({text, kind: 'info'|'warn'|'error'|'success', icon?, durationMs?})`.
  - State: Signal `toasts: readonly Toast[]`, Auto-Remove via setTimeout.
  - Effort: klein.
- [ ] **H1.21** `ToastContainerComponent`.
  - Neue Datei: `ui/toast/toast.component.ts`.
  - Position: unten-mitte oder oben-rechts (Legacy: oben).
  - Stack max 4 Toasts, animation slide-in-from-top.
  - Effort: klein.
- [ ] **H1.22** GameState `case 'toast': this.toast.push({text: msg.text})`.
  - Effort: trivial.
- [ ] **H1.23** Toast-Triggers für Cross-Domain-Events.
  - GameState: bei diesen Frames zusätzlich Toast generieren (Backend sendet das eigene `toast` nicht in allen Fällen):
    - `group_error` (Sektion 7 H1.9 ist redundant — fließt hier ein).
    - `raid_error` (dito).
    - `loot_vote_error` (Sektion 4 H2.7).
    - `cast_interrupted {reason}` (Sektion 3 — Spieler weiß sonst nicht warum).
  - Effort: klein.

---

## 19. Audio & Sound

### Status
Komplett ✗ Missing. Backend feuert keine eigenen Sound-Events (Audio läuft
clientseitig, getriggert durch Visual-Events). `tools/audio_gen/` existiert
für Asset-Generierung, aber **keinerlei Audio-Hook im Frontend**.

### Aufgaben — alle H4 (Polish — niedrigste Priorität)
- [ ] **H4.1** `AudioService` mit Howler.js oder Web-Audio-API.
  - Effort: mittel.
- [ ] **H4.2** SFX-Trigger an Visual-Events binden (cast_started, npc_died, structure_placed, …).
  - Effort: mittel.
- [ ] **H4.3** Ambient-Music pro Tag/Nacht/Disaster.
  - Effort: groß.

> Weil das Backend keine Sound-Frames sendet, ist Audio rein eine
> Client-Side-Polish-Schicht. Spiel-Korrektheit hängt nicht davon ab.

---

## 20. Reihenfolge & Aufwand

### Welle H1 — Critical (Spielbarkeit blockt sich ohne diese)

| ID | Was | Sektion | Effort |
|---|---|---|---|
| H1.1 | Initial-Stat-Verteilung im Charakter-Modal | 1 | mittel |
| H1.2 | Talents-Panel: nie blank | 1 | klein |
| H1.3 | Status-Effects-Reihe im HUD | 3 | mittel |
| H1.4 | Wallet-HUD-Display | 4 | klein |
| H1.5 | Dungeon-Chest-Öffnen-Intent | 4 | klein |
| H1.6 | Quest-Board-Modal | 5 | mittel |
| H1.7 | Quest-Marker auf Minimap | 5 | mittel |
| H1.8 | Click-to-Talk-Fix (Dialog-Modal lokal öffnen) | 6 | klein |
| H1.9 | Group/Raid-Error-Toasts (fließt in H1.20) | 7 | – |
| H1.10 | Dungeon-Floor-Rendering | 8 | groß |
| H1.11 | Dungeon-Floor-Change + Exit | 8 | mittel |
| H1.12 | Door-Toggle-Intent | 9 | klein |
| H1.13 | Merchant-Detection (Trade öffnen) | 12 | klein |
| H1.14 | `world_event`-Handler | 13 | klein |
| H1.15 | Chronik-Panel | 13 | mittel |
| H1.16 | Active-Disasters-Signal + HUD-Icons | 14 | mittel |
| H1.17 | Disaster-Start/End-Toast | 14 | klein |
| H1.18 | `time_tick`-Handler | 15 | klein |
| H1.19 | HUD-Time-Display | 15 | klein |
| H1.20 | ToastService | 18 | klein |
| H1.21 | ToastContainerComponent | 18 | klein |
| H1.22 | Toast-Wiring in GameState | 18 | trivial |
| H1.23 | Toast-Triggers für Cross-Domain-Events | 18 | klein |

**Geschätzter Aufwand H1: ~3-4 Subagent-Wellen** (groß + 5 mittel + 12 klein).

### Welle H2 — Critical (komplettes Quest-/Welt-Erlebnis)

| ID | Was | Sektion | Effort |
|---|---|---|---|
| H2.1 | Trap-Triggered-FX + Toast | 2 | klein |
| H2.2 | Mob-HP-Bar über Sprite | 3 | mittel |
| H2.3 | Spell-Target-Selection-Mode | 3 | groß |
| H2.4 | Cast-Cooldown-Overlay in Hotbar | 3 | klein |
| H2.5 | Auto-Pickup-Floating-Text | 4 | klein |
| H2.6 | Container-Aktionen (fill/water/drink) | 4 | mittel |
| H2.7 | Loot-Roll Vote-Count + Loot-Rule-Status | 4 | klein |
| H2.8 | NPC-Quest-Status-Handler | 5 | mittel |
| H2.9 | Quest-Progress-Toast | 5 | klein |
| H2.10 | Quest-New-Toast | 5 | klein |
| H2.11 | NPC-Sprechblasen | 6 | mittel |
| H2.12 | Minimap-Group-Member-Differenzierung | 7 | klein |
| H2.13 | `raid_started`-Welt-Event + Toast | 7 | klein |
| H2.14 | Dungeon-Chest-Sprite-Swap | 8 | klein |
| H2.15 | Dungeon-Collapsed-Notification | 8 | klein |
| H2.16 | Place-Ghost-Preview | 9 | mittel |
| H2.17 | Repair/Upgrade-Buttons | 9 | mittel |
| H2.18 | Spell-Item-Learning | 10 | klein |
| H2.19 | Hand-Crafting-Hotkey | 11 | klein |
| H2.20 | Recipe-Lock-Tooltip | 11 | klein |
| H2.21 | Sell-Tab im Trade-Modal | 12 | mittel |
| H2.22 | Welt-Event-Toast für hohe Severity | 13 | klein |
| H2.23 | Tag/Nacht-Tint-Overlay | 15 | mittel |
| H2.24 | Event-Pulse auf Minimap bei Disaster | 17 | klein |

**Geschätzter Aufwand H2: ~3 Subagent-Wellen** (1 groß + 8 mittel + 15 klein).

### Welle H3 — Polish (Spielbarkeit OK ohne, aber spürt sich besser an)

| ID | Was | Sektion | Effort |
|---|---|---|---|
| H3.1 | Skill-Level-Up-Toast | 1 | klein |
| H3.2 | Body-Parts-Section im Character-Panel | 3 | klein |
| H3.3 | Mana-Cost-Indicator in Hotbar | 3 | klein |
| H3.4 | Quest-Reward-Modal | 5 | mittel |
| H3.5 | Quest-Marker im Welt-Renderer | 5 | groß |
| H3.6 | NPC-Mood-Icon | 6 | klein |
| H3.7 | Companion-Toast `npc_attacked` | 6 | klein |
| H3.8 | Mob-Tooltip mit Skalierungs-Info | 7 | mittel |
| H3.9 | Skill-XP-Tooltip mit Group-Share | 7 | klein |
| H3.10 | Sense-Radius-Visualisierung | 8 | mittel |
| H3.11 | Dungeon-Sense-Filter auf Minimap | 8 | klein |
| H3.12 | Repair-Heal-Pulse-Visual | 9 | klein |
| H3.13 | Research-Complete-Animation | 10 | klein |
| H3.14 | Weather-Particles | 14 | mittel |

**Geschätzter Aufwand H3: ~2 Subagent-Wellen** (1 groß + 4 mittel + 9 klein).

### Welle H4 — Audio (separate Welle, blockt nichts)
- H4.1-H4.3 Audio-System (ohne Backend-Sound-Events): ~2 Subagent-Wellen.

### Gesamt-Schätzung
**~8-10 Subagent-Wellen** bis das Spiel wieder vollständig wie pre-Refactor spielbar ist
(H1+H2+H3, ohne H4-Audio). Mit Audio: ~10-12.

---

## 21. Anhang: Event-Coverage-Matrix

Vollständige Tabelle über **alle 95 Server→Client-Frames** aus WS_PROTOCOL.md.

Spalten:
- **GS** = GameStateService-Handler vorhanden? ✓ / ✗ / – (irrelevant für State).
- **UI** = Sichtbare Reaktion in einer Komponente / FX?
- **Status** = Gesamt-Bewertung.
- **Sek** = Sektion in diesem Dokument.

| Event | GS | UI | Status | Sek |
|---|---|---|---|---|
| `init` | ✓ | ✓ alle Panels lesen Signals | ✅ | 0 |
| `chat` | ✓ | ✓ ChatComponent | ✅ | – |
| `toast` | ✗ no-op | ✗ | ✗ | 18 |
| `error` | ✗ default | ✗ | ✗ | 18 |
| `player_joined` | ✓ | ✓ Phaser-Pool | ✅ | 2 |
| `player_left` | ✓ | ✓ Phaser-Pool | ✅ | 2 |
| `player_moved` | ✓ | ✓ Phaser | ✅ | 2 |
| `player_damaged` | ✓ | ✓ HUD + Float | ✅ | 3 |
| `player_healed` | ✓ | ✓ HUD + Float | ✅ | 3 |
| `player_mana` | ✓ | ✓ HUD | ✅ | 3 |
| `player_needs` | ✓ | ✓ HUD | ✅ | 0 |
| `player_downed` | ✓ | ✓ DownedOverlay | ✅ | 3 |
| `player_downed_visible` | ✗ break | ✗ | ✗ | 3 |
| `player_revived_visible` | ✗ break | ✗ | ✗ | 3 |
| `player_respawned` | ✓ | ✓ DownedOverlay schließt | ✅ | 3 |
| `player_died` | ✗ break | ✗ kein Toast | ⚠ | 18 |
| `body_part_damaged` | ✓ | ✗ kein Panel | 🟡 | 3 |
| `sprint_state` | ✓ | ✗ kein HUD-Icon | 🟡 | 2 |
| `rest_start` | ✓ | ✗ kein HUD-Icon | 🟡 | 0 |
| `rest_end` | ✓ | ✗ kein HUD-Icon | 🟡 | 0 |
| `attributes_update` | ✓ | ✓ Character-Panel | ✅ | 1 |
| `attrs_update` | ✓ | ✓ Character-Panel | ✅ | 1 |
| `status_effects` | ✓ | ✗ kein HUD-Indicator | ⚠ | 3 |
| `inventory_add` | ✓ | ✓ Inventar | ✅ | 4 |
| `inventory_update` | ✓ | ✓ Inventar | ✅ | 4 |
| `inventory_remove` | ✓ | ✓ Inventar | ✅ | 4 |
| `inventory_full_refresh` | ✓ | ✓ Inventar | ✅ | 4 |
| `wallet_update` | ✓ | 🟡 nur Inventar-Footer, kein HUD | 🟡 | 4 |
| `trade_coins` | ✓ | ✓ Trade-Modal | ✅ | 12 |
| `npc_spawned` | ✓ | ✓ Phaser-Pool | ✅ | 0 |
| `npc_moved` | ✓ | ✓ Phaser | ✅ | 0 |
| `npc_damaged` | ✓ | ✓ Float + Spark | ✅ | 3 |
| `npc_died` | ✓ | ✓ Death-Fade | ✅ | 3 |
| `npc_reply` | ✓ | ✓ Dialog | ✅ | 6 |
| `npc_attacked` | ✗ break | ✗ | ✗ | 6 |
| `npc_goal` | ✗ break | ✗ | ✗ | 6 |
| `npc_speech` | ✗ break | ✗ keine Bubble | ✗ | 6 |
| `npc_mood` | ✗ break | ✗ kein Mood-Icon | ✗ | 6 |
| `npc_quest_status` | ✗ break | ✗ versickert | ✗ | 5 |
| `item_spawned` | ✓ | ✓ Phaser-Pool | ✅ | 4 |
| `item_picked_up` | ✓ | ✓ Phaser-Pool | ✅ | 4 |
| `structure_placed` | ✓ | ✓ Phaser-Pool + FX | ✅ | 9 |
| `structure_replaced` | ✓ | ✓ Phaser-Pool | ✅ | 9 |
| `structure_removed` | ✓ | ✓ Phaser-Pool + FX | ✅ | 9 |
| `structure_damaged` | ✓ | ✓ Spark + HP-Patch | ✅ | 9 |
| `structure_repaired` | ✓ | 🟡 nur HP-Patch, kein Heal-Pulse | 🟡 | 9 |
| `structure_upgraded` | ✓ | ✓ Sprite-Refresh | ✅ | 9 |
| `chunks` | ✓ | ✓ Phaser-Tile-Layer | ✅ | 2 |
| `event` | ✓ Signal | ✗ kein Panel | ⚠ | 13 |
| `world_event` | ✗ default | ✗ | ✗ | 13 |
| `weather` | ✓ Signal | ✗ kein Renderer/HUD | ⚠ | 14 |
| `time_update` | ✓ | ✗ kein HUD-Display | 🟡 | 15 |
| `time_tick` | ✗ default | ✗ | ✗ | 15 |
| `group_state` | ✓ | ✓ PartyFrame | ✅ | 7 |
| `group_invite_received` | ✓ | ✓ GroupInvite-Overlay | ✅ | 7 |
| `group_invite_sent` | ✗ break | ✗ kein Toast | ⚠ | 7 |
| `group_disbanded` | ✓ | 🟡 kein Toast | 🟡 | 7 |
| `group_kicked` | ✓ | 🟡 kein Toast | 🟡 | 7 |
| `group_member_left` | ✗ break | ✗ kein Toast | ⚠ | 7 |
| `group_member_online` | ✓ | ✓ PartyFrame-Status | ✅ | 7 |
| `group_member_offline` | ✓ | ✓ PartyFrame-Status | ✅ | 7 |
| `group_converted` | ✓ | ✓ PartyFrame | ✅ | 7 |
| `group_chat` | ✓ | ✓ Chat | ✅ | 7 |
| `group_error` | ✗ break | ✗ kein Toast | ✗ | 7 |
| `raid_started` | ✗ break | ✗ kein Toast, kein Event-Log | ✗ | 7 |
| `raid_error` | ✗ break | ✗ kein Toast | ✗ | 7 |
| `loot_roll_started` | ✓ | ✓ LootRoll-Overlay | ✅ | 4 |
| `loot_roll_voted` | ✗ break | ✗ kein Vote-Count im Overlay | ⚠ | 4 |
| `loot_roll_resolved` | ✓ | ✓ Overlay schließt | ✅ | 4 |
| `loot_rule_changed` | ✗ break | ✗ kein PartyFrame-Tag | ⚠ | 4 |
| `loot_vote_error` | ✗ default | ✗ | ✗ | 4 |
| `quests_update` | ✓ | ✓ Quests-Panel | ✅ | 5 |
| `quest_new` | ✓ | 🟡 Panel ja, Toast nein | 🟡 | 5 |
| `quest_progress` | ✓ | 🟡 Panel ja, Float/Toast nein | 🟡 | 5 |
| `quest_closed` | ✓ | 🟡 Panel ja, Reward-Modal nein | 🟡 | 5 |
| `factions_update` | ✓ | ✓ Factions-Panel | ✅ | 7 |
| `quest_board_open` | ✗ break | ✗ kein Modal | ✗ | 5 |
| `talents_update` | ✓ | 🟡 Panel zeigt nichts bei leerem tree | 🟡 | 10 |
| `talent_learned` | ✓ | ✓ Panel + Talents-Patch | ✅ | 10 |
| `spell_learned` | ✓ | ✓ Spellbook-Patch | ✅ | 10 |
| `cast_started` | ✓ | ✓ CastBar | ✅ | 3 |
| `cast_interrupted` | ✓ | ✓ CastBar schließt | 🟡 (kein Reason-Toast) | 3 |
| `cast_finished` | ✓ | ✓ CastBar schließt | 🟡 (kein Cooldown-Overlay) | 3 |
| `crafting_open` | ✓ | ✓ Crafting-Modal | ✅ | 11 |
| `trade_open` | ✓ | ✓ Trade-Modal | ✅ | 12 |
| `chest_open` | ✓ | ✓ Chest-Modal | ✅ | 4 |
| `chest_add` | ✓ | ✓ Chest-Modal | ✅ | 4 |
| `chest_remove` | ✓ | ✓ Chest-Modal | ✅ | 4 |
| `sign_inspect` | ✓ | ✓ SignInspect-Modal | ✅ | – |
| `bills_update` | ✓ | ✓ Bills-Panel | ✅ | 11 |
| `bill_progress` | ✓ | ✓ Bills-Panel | ✅ | 11 |
| `bill_done` | ✓ | ✓ Bills-Panel | ✅ | 11 |
| `bill_blocked` | ✓ | 🟡 Panel ja, Toast-Reason nein | 🟡 | 11 |
| `research_update` | ✓ | ✓ Research-Panel | ✅ | 10 |
| `research_pool_update` | ✓ | ✓ Research-Panel | ✅ | 10 |
| `skill_xp` | ✗ break | ✗ kein Float, kein LevelUp-Toast | ✗ | 3, 10 |
| `dungeon_enter` | ✗ break | ✗ kein Floor-Render | ✗ | 8 |
| `dungeon_exit` | ✗ break | ✗ | ✗ | 8 |
| `dungeon_floor_change` | ✗ break | ✗ | ✗ | 8 |
| `dungeon_collapsed` | ✗ break | ✗ kein Toast | ✗ | 8 |
| `dungeon_sense` | ✗ break | ✗ | ✗ | 8 |
| `dungeon_chest_opened` | ✗ break | ✗ kein Sprite-Swap | ✗ | 8 |
| `trap_triggered` | ✗ break | ✗ kein FX/Toast | ✗ | 2 |
| `disaster_started` | ✗ break | ✓ Disaster-Overlay | 🟡 (Visual ja, Toast nein) | 14 |
| `disaster_ended` | ✗ break | ✓ Disaster-Overlay | 🟡 (Visual ja, Toast nein) | 14 |
| `lightning_strike` | ✗ break | ✓ Phaser-Bolt | ✅ | 14 |
| `earthquake_shake` | ✗ break | ✓ Camera-Shake | ✅ | 14 |
| `visual_effect` | ✗ break | ✓ Phaser-FX | ✅ | 3, 9 |
| `character_created` | ✗ break | ✓ CharacterCreate schließt via re-init | ✅ | 1 |
| `character_name_check` | ✗ break | ✓ CharacterCreate | ✅ | 1 |
| `pong` | – | – | – reserviert | – |

**Summe Status:**
- ✅ Full: 47
- 🟡 Partial: 15
- ⚠ Stub: 9
- ✗ Missing: 24

Damit sind **24 Frames absolut unbehandelt** und weitere **24 nur teilweise**. Die
Welle H1+H2 deckt alle ✗ und ⚠ ab; H3 schließt die 🟡 zu ✅.

---

## Anhang B: Bekannte Mismatch-Spots (Type-Namen / Frame-Form)

Diese sind nicht „fehlen", sondern „falsch verdrahtet". Bei der Umsetzung mit zu prüfen:

1. **`time_tick` vs. `time_update`**: GameState handelt `time_update`, Backend sendet aber `time_tick` (siehe WS_PROTOCOL.md Anhang Z. 897). Wahrscheinlich versickert die Zeit-Tick komplett, bis ein `init` neu kommt. → H1.18.
2. **`weather`**: WS_PROTOCOL.md listet das im Anhang gar nicht explizit (nur `time_tick`). Backend `weather_worker` sendet aber ein `weather`-Frame mit `{kind, intensity}`. GameState handelt es korrekt — das ist ok, aber undokumentiert.
3. **`player_died` vs. `player_downed`**: Down-System ersetzte Death komplett (siehe `combat.py`). `player_died` kommt nur noch in absoluten Permadeath-Fällen (Solo-Player-Death). Frontend ignoriert es vermutlich zurecht, aber Toast wäre angebracht (H1.20 Toast-Infra).
4. **`pong`**: reserviert, kein Sender. Frontend braucht es nicht.
5. **`bill_progress` / `bill_done` / `bill_blocked`**: nicht im WS_PROTOCOL.md-Anhang aufgelistet, aber im Backend `bill_queue.py` definiert. GameState handelt sie. → WS_PROTOCOL.md-Anhang lückenhaft, sollte gepflegt werden.

---

## Anhang C: Architektur-Notiz

Das Refactor hat den Frontend-Stack auf Angular 18 + Phaser 3 in strikter
Trennung gebaut:
- **State** lebt im `GameStateService` (Signals). Phaser liest read-only per
  `bridge.state.<sig>()`. UI-Komponenten lesen via `inject(GameStateService)`.
- **Intents** gehen über `WebSocketService.send(...)` oder den
  `GameBridgeService` (für Phaser).
- **FX** (transient) werden direkt am WS-Stream konsumiert
  (`world-scene.ts::handleFxMessage`), parallel zum State-Patch.

Diese Architektur ist sauber. Die Lücken sind durchgängig: „GameState-Handler
fehlt" → einfach `case '...': this._handleX(msg); break;` ergänzen +
Signal-Update + Komponente liest. Keine Refactor-Kosten, nur Implementierung.
