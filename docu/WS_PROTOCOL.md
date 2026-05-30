# WebSocket-Protokoll von Liege (eingefroren)

> Stand: 2026-05-30, Commit 115dd16.
> Refactoring-Vertrag (Phase 0.1 aus `refectoring-plan.md`).
> Änderungen nur mit explizitem Versionssprung — Backend (`backend/main.py`-Handler) und Frontend (`app.js`-Konsument) müssen synchron bleiben.

---

## Konventionen

- **Endpoint:** `GET /ws` (WebSocket-Upgrade).
- **Auth:** Cookie/Token-basiert via `auth.get_user_from_ws(websocket)` — kein Login-Frame. Bei fehlender Auth schließt der Server mit Code `1008`.
- **Wire-Format:** JSON-Objekt pro Frame, Diskriminator-Feld `type` (String). Beispiel: `{"type": "move", "x": 12, "y": 7}`.
- **Required vs. Optional:** Felder, die im Code mit `data["x"]` gelesen werden, sind **required** (KeyError bei Fehlen → `WebSocketDisconnect`). Felder mit `data.get("x", default)` sind **optional**.
- **Player-Identität:** Der Server kennt den Sender über `player_id` aus dem Auth-Cookie; Clients **senden keinen** `player_id`-Header in Frames.
- **Stille Validierung:** Viele Branches `continue`-en lautlos bei ungültigem Input (z. B. fehlende Felder, Out-of-Range, fehlende Berechtigung) — der Client sieht keine Antwort, das ist by-design.
- **Toasts:** Sehr viele Server→Client-Fehler kommen als `{"type": "toast", "text": "..."}`. Spezifische Error-Types existieren nur dort, wo der Client gezielt reagieren muss (z. B. `group_error`, `loot_vote_error`, `raid_error`).
- **Broadcast-Reichweiten:** Der `ConnectionManager.broadcast(...)` sendet aktuell an **alle** verbundenen Spieler (kein View-Distance-Filter im WS-Layer). `_broadcast_to_group(group_id, ...)` adressiert nur Party-/Raid-Mitglieder.

---

## Verbindungs-Lifecycle

### 1. Connect → `init` (Server → Client)

Nach erfolgreichem Auth + `manager.connect(...)` sendet der Server **einen** `init`-Frame als kompletten initialen Snapshot:

- `player_id`, `needs_character_creation` (bool), `preset` (string|null)
- `chunks` (umliegende Tiles), `chunk_size: 32`, `world_seed`
- `players` (online-Map), `structures`, `dungeons` (Minimap-Marker), `events`, `npcs`, `items_ground`
- `inventory`, `wallet_copper`
- `spawn` ({x,y}), `hp`/`max_hp`, `mana`/`max_mana`, `hunger`/`max_hunger`, `stamina`/`max_stamina`, `thirst`/`max_thirst`
- `skills`, `body_parts`, `research`, `time`, `quests`, `factions`, `attributes`, `active_disasters`, `stats`, `power_tier`
- `spell_catalog`, `learned_spells`, `talents` ({learned, points, tree})
- `group` (Party-Snapshot oder null), `group_invites`

Direkt danach:
- `group_member_online` (Broadcast an Group, falls bereits in Gruppe) — kennzeichnet Reconnect.
- `player_joined` (Broadcast an alle anderen, exclude self).

### 2. Disconnect (`WebSocketDisconnect`)

Server-seitige Aufräum-Arbeit (kein Client-Frame nötig):
- `spell_caster.cleanup_player`, `needs.clear_player_state`, Down-Timer canceln.
- Group-Hook: Leader-Offline-Reaper-Timer setzen (`mark_leader_offline`) und `group_member_offline` an die Gruppe broadcasten.
- `manager.disconnect`, `last_seen = NOW()` in DB.
- `player_left` an alle anderen broadcasten.

### Übergreifende Server → Client-Types (Cross-Domain)

Diese kommen aus dem Hauptloop **und** aus Background-Workern (event_worker, npc_worker, raid_director, spell_caster, status_effects, time_loop, world_populator), unabhängig vom konkreten Client-Frame:

- `toast` — generische 1-Zeilen-Notification.
- `error` — selten benutzt, meist domain-spezifisch.
- `chat` — Welt-Chat-Echo.
- `player_joined`, `player_left`, `player_moved`, `player_healed`, `player_damaged`, `player_mana`, `player_needs`, `player_downed`, `player_downed_visible`, `player_revived_visible`, `player_respawned`, `body_part_damaged`.
- `npc_spawned`, `npc_damaged`, `npc_died`, `npc_moved` (aus npc_worker).
- `item_spawned`, `item_picked_up`.
- `structure_placed`, `structure_removed`, `structure_replaced`, `structure_damaged`, `structure_repaired`, `structure_upgraded`.
- `visual_effect`, `earthquake_shake`.
- `event`, `world_event`, `disaster_started`, `disaster_ended`.
- `chunks` — Folge-Chunks nach Chunk-Wechsel.
- `status_effects` — komplette Liste der aktiven Effekte am Spieler.
- `cast_started`, `cast_finished`, `cast_interrupted`.
- `time_tick` (aus time_system).

---

## Domäne: movement

### `move`
**Client → Server.**
**Felder:** `x: int` (required), `y: int` (required).
**Antworten:**
- `trap_triggered` — falls Dungeon-Falle ausgelöst (an Spieler).
- `inventory_add` / `inventory_update` — Auto-Pickup beim Drüberlaufen.
- `item_picked_up` — Broadcast bei Auto-Pickup.
- `dungeon_exit`, `dungeon_floor_change`, `toast` — bei Treppen-Tile (STAIRS_UP/STAIRS_DOWN).
- `chunks` — bei Chunk-Wechsel.
- `player_moved` — Broadcast an alle anderen.
- `visual_effect` (`poison_cloud`/`hit_spark`) — bei Trap-Strukturen.
- `quest_progress` — bei Item-Pickup, das einen Quest-Trigger feuert.
- `inventory_remove` + `player_downed` (via damage_player) — falls Trap-Schaden den Spieler killt.

**Side Effects:** DB-Update `players.x/y/last_seen`, ggf. `dungeon_instance.change_floor` / `exit_dungeon`, ggf. Aufdecken+Markieren von Fallen, Quest-Hooks (`quests.on_item_collected`, `quest_stages.on_player_event(collect)`), Lazy-Spawn neuer Chunks via `_populate_chunks_bg`.
**Blockiert wenn:** `is_downed(player_id)` (Down-State frisst alle Moves).
**Seiteneffekte beim Senden:** Bricht aktiven Cast ab (`spell_caster.interrupt(..., "movement")`) und beendet Bett-Schlaf (`needs.set_resting(False)`).

### `sprint`
**Client → Server.**
**Felder:** `on: bool` (optional, default false).
**Antworten:** keine direkte Response. Stamina-Drain läuft passiv → `player_needs` kommt aus dem Needs-Loop.
**Side Effects:** `needs.set_sprint(player_id, on)`.

---

## Domäne: social/groups

### `group_create_party`
**Client → Server.**
**Felder:** —.
**Antworten:** `group_state` (mit Group-Snapshot, an Caller via `_push_group_state`), oder `group_error` (`{reason: str}`).
**Side Effects:** `groups.create_party(player_id)` legt Party in DB an.

### `group_invite`
**Client → Server.**
**Felder:** `target: str` (required, name des Eingeladenen).
**Antworten:**
- `group_state` (an Caller, falls implizit Party erstellt).
- `group_invite_sent` (`{target, expires_at}`) — an Caller.
- `group_invite_received` (`{invite_id, group_id, from, kind, expires_at}`) — an Target, falls online.
- `group_error` (`{reason}`) bei Fehlschlag.

**Side Effects:** `groups.invite(...)` schreibt einen DB-Invite mit Expiry.

### `group_accept`
**Client → Server.**
**Felder:** `invite_id: int` (required, sonst silent-skip).
**Antworten:** `group_state` an alle Member (via `_push_group_state_to_all_members`); `group_error` bei Fehlschlag.
**Side Effects:** Invite aus DB konsumiert, Spieler als Member eingetragen.

### `group_decline`
**Client → Server.**
**Felder:** `invite_id: int` (required, sonst silent-skip).
**Antworten:** keine.
**Side Effects:** Invite in DB als declined markiert.

### `group_leave`
**Client → Server.**
**Felder:** —.
**Antworten:**
- `group_state` (an Caller; leerer Snapshot).
- `group_member_left` (`{player_name, new_leader?}`) — Broadcast an Restgruppe.
- `group_state` an Restgruppen-Member (falls nicht disbanded).
- `group_error` bei Fehlschlag.

**Side Effects:** DB-Mitgliedschaft entfernt; ggf. Leader-Transfer; ggf. Group-Auflösung wenn letzter Member.

### `group_kick`
**Client → Server.**
**Felder:** `target: str` (required, sonst silent-skip).
**Antworten:**
- `group_state` an den Gekickten (leer).
- `group_kicked` (`{by}`) an den Gekickten.
- `group_state` an alle Restmember.
- `group_error` bei Fehlschlag (z. B. `no_permission`).

**Side Effects:** Mitgliedschaft des Targets entfernt.

### `group_promote`
**Client → Server.**
**Felder:** `target: str` (required, sonst silent-skip).
**Antworten:** `group_state` an alle Member; `group_error` bei Fehlschlag.
**Side Effects:** Role-Update in DB (Officer-Status).

### `group_transfer_leader`
**Client → Server.**
**Felder:** `target: str` (required, sonst silent-skip).
**Antworten:** `group_state` an alle Member; `group_error` bei Fehlschlag.
**Side Effects:** `leader`-Feld der Gruppe in DB neu gesetzt.

### `group_disband`
**Client → Server.**
**Felder:** —.
**Antworten (an alle Ex-Member):**
- `group_disbanded` (`{group_id, by}`).
- `group_state` (`{group: null}`).
- `group_error` (`{reason: "no_permission"}`) wenn Caller nicht berechtigt.

**Side Effects:** Group-Row + Members-Rows aus DB gelöscht.

### `group_refresh`
**Client → Server.**
**Felder:** —.
**Antworten:** `group_state` an Caller.
**Side Effects:** keine — reiner Resync.

### `group_chat`
**Client → Server.**
**Felder:** `text: str` (required, max 500 Zeichen, leer → silent-skip).
**Antworten:** `group_chat` (`{from, text, kind}`) Broadcast an alle Member; `group_error` (`not_in_group`) wenn solo.
**Side Effects:** keine DB-Persistenz, In-Memory-Fan-Out.

### `group_convert_to_raid`
**Client → Server.**
**Felder:** `kind: str` (optional, default `"raid_small"`).
**Antworten:**
- `group_converted` (`{from_kind, to_kind}`) Broadcast an Member.
- `group_state` an alle Member.
- `group_error` bei Fehlschlag.

**Side Effects:** `groups.convert_to_raid(...)` ändert `kind` in DB von `party` → `raid_*` und erlaubt mehr Members.

---

## Domäne: chat

### `chat`
**Client → Server.**
**Felder:** `text: str` (required, max 500 Zeichen, leer → skip).
**Antworten:** `chat` (`{from, text}`) Broadcast an alle Spieler (Welt-Chat).
**Side Effects:** keine Persistenz.

---

## Domäne: loot

### `loot_vote`
**Client → Server.**
**Felder:** `roll_id: int` (required), `vote: str` (required, lowercased — z. B. `"need"`, `"greed"`, `"pass"`).
**Antworten:**
- `loot_roll_voted` (`{roll_id, voter, vote, votes_cast}`) Broadcast an Roll-Teilnehmer.
- `loot_roll_resolved` (`{roll_id, winner, item, ...}`) wenn alle gevotet haben.
- `loot_vote_error` (`{reason}`) bei ungültiger Stimme.
- Bei Gewinner: `item_picked_up` Broadcast, `inventory_add` / `inventory_update` an Gewinner.

**Side Effects:** `loot_rolls.vote(...)` + ggf. `_finalize`-Hook pickt das Item direkt für den Winner.

### `set_loot_rule`
**Client → Server.**
**Felder:** `rule: str` (required, lowercased — z. B. `"free_for_all"`, `"need_greed"`).
**Antworten:**
- `loot_rule_changed` (`{rule}`) Broadcast an Group.
- `group_error` (`not_in_group` / Fehler-Reason) bei Fehlschlag.

**Side Effects:** `groups.set_loot_rule(...)` schreibt Regel in Group-Row.

---

## Domäne: raid/dev

### `raid_trigger_manual`
**Client → Server.**
**Felder:** `tier: int` (optional, default 1).
**Antworten:**
- `raid_started` (`{tier, label, spawned, by}`) Broadcast an Group.
- `raid_error` (`{reason, remaining_s?}`) bei Cooldown / Fehlschlag.
- `group_error` (`not_in_group` / `leader_only`) wenn Voraussetzungen fehlen.
- Folge-Frames aus `raid_director`: `npc_spawned` (mehrfach) + `event`.

**Side Effects:** `raid_director.trigger_manual_raid(...)` spawnt Mob-Welle in der Welt.

### `dev_world_repopulate`
**Client → Server.** Admin-only (`user.role == "admin"`).
**Felder:** —.
**Antworten:** `toast` (`"⛔ Admin only"` bei Nicht-Admin, sonst `"♻️ {count} Chunks zurückgesetzt"`).
**Side Effects:** `world_populator.reset_chunks_without_player_structures(...)` setzt `populated=false` und löscht System-Strukturen leerer Chunks.

### `dev_trigger_event`
**Client → Server.** Admin-only.
**Felder:** `effect: str` (required, leer → toast `"effect fehlt"`).
**Antworten:** `toast` (Erfolg/Fehler). Indirekt: Disaster-Frames aus `event_worker._apply_event_effect` (`disaster_started`, weitere abhängig vom Effekt).
**Side Effects:** Sofortiger Trigger eines Event-Effekts (Test-Helfer für Disasters wie `thunderstorm`, `toxic_fog`, ...).

### `force_respawn`
**Client → Server.**
**Felder:** —.
**Antworten:** Nur wenn `is_downed(player_id)`: `player_respawned` (`{x, y, hp, max_hp, in_place: false}`) an Caller + `player_moved` + `player_revived_visible` Broadcast.
**Side Effects:** Down-Timer cancelled, HP auf `max_hp`, Position auf Heim-Spawn (Bett/Lagerfeuer) bzw. Welt-Default.

---

## Domäne: structures

### `place_structure`
**Client → Server.**
**Felder:** `x: int`, `y: int`, `structure_type: str` (alle required), `material: str` (optional, default `"stone"`), `rotation: int` (optional, default 0).
**Antworten:**
- `toast` bei Tür-Spezialfällen (Tür braucht Wand), Stamina-Mangel, allgemeinem Block-Fehler.
- `structure_removed` (Broadcast) wenn eine Wand für eine Tür entfernt wird.
- `structure_placed` (Broadcast) für die neue Struktur + ggf. mehrere zusätzliche `structure_placed`-Broadcasts (Auto-Floor-Spread unter angrenzenden Objects).
- `visual_effect` (`wp_hoe_soil` für `farm_plot`, `wp_build_hammer` für andere Objects) Broadcast.
- `player_needs` an Caller bei Stamina-Verbrauch.
- `skill_xp` an Caller (construction).
- Eventuell `world_event` (delayed) via `player_events.trigger(...)`.

**Side Effects:** DB-Insert `structures`, ggf. DB-Delete einer Wand bei Türen-Replace, Stamina-Drain, XP-Vergabe, KI-Welt-Event-Trigger mit Cooldown.

### `toggle_door`
**Client → Server.**
**Felder:** `x: int` (optional, default 0), `y: int` (optional, default 0).
**Antworten:** `structure_replaced` (`{x, y, structure}`) Broadcast.
**Side Effects:** DB-Update `structures.type` (closed ↔ open Mapping für Wood/Iron/Stone-Türen und Garden-Gates). Range-Check: max 1 Tile.

### `remove_structure`
**Client → Server.**
**Felder:** `x: int`, `y: int` (required), `layer: str` (optional — `"object"`/`"floor"`).
**Antworten:** `structure_removed` (`{x, y, layer}`) Broadcast.
**Side Effects:** DB-Delete der Struktur.

### `attack_structure`
**Client → Server.**
**Felder:** `x: int` (optional, default -1), `y: int` (optional, default -1).
**Antworten:**
- `toast` bei Fehlern (kein Target, nicht combat-fähig, Reichweite).
- `structure_damaged` (`{x, y, durability, max_durability, dmg, by}`) Broadcast.
- `structure_removed` Broadcast bei Kollaps.
- `structure_placed` Broadcast für entstandene `rubble`.
- (Indirekt Combat-XP über `skills.gain_xp` — kein separater Frame.)

**Side Effects:** DB-Update der Durability, Material-Resistance-Berechnung, Trümmer-Erzeugung bei zerstörten Wänden/Toren/Stallungen.

### `repair_structure`
**Client → Server.**
**Felder:** `x: int`, `y: int` (optional, default -1).
**Antworten:**
- `toast` bei jedem Fehlschlag-Fall (kein Target, kein Eigentum, Reichweite, schon voll, kein Hammer, kein Material) **und** bei Erfolg (`+8 HP — {cur}/{max}`).
- `structure_repaired` (`{x, y, durability, max_durability, by}`) Broadcast bei Erfolg.

**Side Effects:** Verbraucht 1× Material via `items.consume_one`, DB-Update Durability +8 (cap = max), Construction-XP.

### `upgrade_structure`
**Client → Server.**
**Felder:** `x: int`, `y: int` (optional, default -1).
**Antworten:**
- `toast` bei Fehlschlägen (Eigentum, Reichweite, höchstes Material, beschädigt, kein Hammer, kein Material) und bei Erfolg.
- `structure_upgraded` (`{x, y, material, durability, max_durability, by}`) Broadcast bei Erfolg.

**Side Effects:** Verbraucht 2× nächst-höheres Material (mit Rollback bei Fehlschlag), DB-Update `material`, Construction-XP.

### `use_structure`
**Client → Server.** Polymorpher Branch auf `structures.at(x, y).type`.
**Felder:** `x: int`, `y: int` (optional, default -1). Range-Check: max 1 Tile.

#### Sub-Branch — `chest`
**Antworten:** `chest_open` (`{chest_id, items}`) an Caller.
**Side Effects:** keine.

#### Sub-Branch — `quest_board`
**Antworten:** `quest_board_open` (`{board_id, offers}`) an Caller.
**Side Effects:** keine; filtert Templates nach Combat-Level und schon angenommenen Quests.

#### Sub-Branch — harvestable (`tree_oak`, `rock_small`, `bush`, ...)
Bestimmt via `harvest.is_harvestable(s.type)`. Skill-Mapping über `PROP_SKILL` (woodcutting/mining/gathering).
**Antworten:**
- `toast` (Tool-Hinweis, Loot-Liste).
- `inventory_add` an Caller pro Drop.
- `quest_progress` an Caller bei Quest-Hook-Trigger.
- `skill_xp` an Caller.
- `visual_effect` (`hit_spark` + Polish-Kind `wp_chop_wood`/`wp_mining_chip`/`wp_harvest_crop`) Broadcast.
- `structure_damaged` Broadcast oder `structure_removed` Broadcast wenn die Ressource zerlegt ist.

**Side Effects:** DB-Damage an Struktur, ggf. DB-Delete, Inventar-Inserts.

#### Sub-Branch — `stairs_down`
**Antworten:**
- `toast` (z. B. "bereits in Dungeon").
- `dungeon_enter` (`{dungeon_id, name, tier, floor_count, floor_idx, size, tiles, spawn, expires_at, ...}`) an Caller.
- Indirekt: `npc_spawned` Broadcasts aus `populate_floor_mobs`.

**Side Effects:** ggf. Ad-hoc-Dungeon-Spawn via `dungeon_instance.spawn_dungeon`, `dungeon_instance.enter_dungeon` setzt Spieler-World auf `dungeon:<id>:<floor>`.

#### Sub-Branch — `farm_plot`
**Antworten:**
- `toast` (z. B. "wächst schon was", "Kraut zum Pflanzen", "🌱 Kraut gepflanzt").
- `inventory_full_refresh` (`{inventory}`) an Caller.
- `visual_effect` (`wp_sow_seeds`) Broadcast.

**Side Effects:** Verbraucht 1× `herb`, INSERT in `plantings`.

#### Sub-Branch — `workbench` / `furnace` / `anvil`
**Antworten:** `crafting_open` (`{station, recipes}`) an Caller.
**Side Effects:** keine.

#### Sub-Branch — `sign_*` (Welle 51 Settlement-Schilder)
**Antworten:** `sign_inspect` (`{slug}`) an Caller.
**Side Effects:** keine.

#### Sub-Branch — `bed` / `campfire`
**Antworten:**
- `toast` ("Heim-Spawn gemerkt", für Bett zusätzlich "Du legst dich schlafen").
- `rest_start` an Caller (nur Bett).

**Side Effects:** DB-Update `players.spawn_x/spawn_y`; bei Bett zusätzlich `needs.set_resting(True)`.

#### Sub-Branch — `well` / sonstige Heil-Struktur
Heal-Struktur falls Eintrag in `combat.STRUCTURE_HEAL`, plus Well-Spezialfall (Trinken + Tainted-Check).
**Antworten:**
- `toast` (Cooldown, Vergiftet, "💧 Brunnen-Trunk: +N Durst").
- `player_healed` an Caller (via `heal_player`).
- `player_needs` an Caller (bei Brunnen).
- `visual_effect` (`heal_glow`) Broadcast.
- `status_effects` an Caller bei Tainted-Well.

**Side Effects:** Heal-Cooldown-Tracking pro `(player, struct_id)`, ggf. Poison-Status, Durst-Restore.

#### Sub-Branch — Fallback (unbekannter Struktur-Typ)
**Antworten:** `toast` (`"{type} — Mechanik kommt noch"`).

### `fill_container`
**Client → Server.**
**Felder:** `item_id: int`, `x: int`, `y: int` (optional, default 0).
**Antworten:**
- `toast` (Reichweite, "Keine Wasserquelle", "Kein Behälter", Erfolg).
- `inventory_update` (`{item}`) an Caller.

**Side Effects:** DB-Update `items.charges = container_capacity(kind)`.

### `water_plant`
**Client → Server.**
**Felder:** `item_id: int` (Container), `x: int`, `y: int` (optional, default 0).
**Antworten:**
- `toast` (Reichweite, kein Acker, kein Behälter, leer, kein Samen, Erfolg).
- `inventory_update` an Caller.
- `visual_effect` (`wp_water_crop_tile`) Broadcast.

**Side Effects:** DB-Update `plantings.last_watered_at = NOW()`, Container-Charges −1.

### `drink_container`
**Client → Server.**
**Felder:** `item_id: int` (required).
**Antworten:**
- `toast` ("leer", Erfolg mit Charges-Anzeige).
- `player_needs` an Caller.
- `inventory_update` an Caller.

**Side Effects:** Charges −1, Durst-Restore.

### `drink_water_tile`
**Client → Server.**
**Felder:** `x: int`, `y: int` (optional, default 0).
**Antworten:**
- `toast` ("Hier ist kein Wasser" / "+N Durst").
- `player_needs` an Caller.

**Side Effects:** Durst-Restore (kein DB-Schreib am Tile).

### `dungeon_chest`
**Client → Server.**
**Felder:** `x: int`, `y: int` (optional, default 0).
**Antworten:**
- `toast` (Reichweite, Erfolg mit Loot-Liste).
- `inventory_add` an Caller pro nicht-Currency-Drop.
- `wallet_update` (`{copper}`) an Caller bei Münz-Drop.
- `dungeon_chest_opened` (`{x, y}`) an Caller.

**Side Effects:** Markiert Chest als `opened` im Dungeon-State, würfelt `chest_loot.roll_chest_loot("boss"|"dungeon")`, schreibt Items / Currency in DB.

---

## Domäne: inventory

### `split_stack`
**Client → Server.**
**Felder:** `item_id: int` (optional, default 0), `amount: int` (optional, default 0).
**Antworten:** `inventory_update` (`{item_id, quantity}`) + `inventory_add` (`{item}`) an Caller.
**Side Effects:** DB-Update der alten Row + DB-Insert der neuen Stack-Row.

### `merge_stacks`
**Client → Server.**
**Felder:** `kind: str` (required), `quality: str` (optional, default `"normal"`).
**Antworten:** `inventory_full_refresh` (`{inventory}`) an Caller.
**Side Effects:** DB-Konsolidierung mehrerer Rows mit gleichem (kind, quality) zu einer.

### `equip_item`
**Client → Server.**
**Felder:** `item_id: int` (optional, default 0), `to_slot: str` (optional, Welle 23 Dual-Wield).
**Antworten:**
- `inventory_update` (`{item}`) an Caller.
- `attrs_update` (`{stats}`) an Caller via `_send_attrs_update`.
- `toast` bei Off-Hand-2H-Konflikt.

**Side Effects:** DB-Update `items.equipped_slot`.

### `unequip_item`
**Client → Server.**
**Felder:** `item_id: int` (optional, default 0).
**Antworten:** `inventory_update` (`{item}`) + `attrs_update` an Caller.
**Side Effects:** DB-Update `items.equipped_slot = NULL`.

### `use_item`
**Client → Server.**
**Felder:** `item_id: int` (optional, default 0).
**Antworten:**
- `inventory_update` (`{item_id, quantity}`) wenn Stack-Rest > 0, sonst `inventory_remove` (`{item_id, consumed: true}`) an Caller.
- `player_healed` (via `heal_player`) an Caller.
- `player_mana` (via `restore_mana`) an Caller.
- `player_needs` an Caller (Hunger/Stamina/Thirst-Restore).
- `status_effects` (Blessed bei Medical-Talent), `skill_xp` (medical / cooking).
- `research_pool_update` (`{pool, gained, reason}`) bei `research_scroll`/`research_tome`.
- Dungeon-Key-Items: `structure_placed` (Treppen), `world_event`, `toast` Broadcasts/Caller-Frames.

**Side Effects:** DB-Delete der Row bzw. Decrement der Quantity; ggf. Body-Parts-Heal, Heal-Aggro, Dungeon-Spawn.

### `pick_item`
**Client → Server.**
**Felder:** `item_id: int` (optional, default 0).
**Antworten:**
- `toast` (Loot-Roll-Lock, "Für X reserviert").
- `item_picked_up` (`{item_id}`) Broadcast.
- `inventory_update` (Stack-Merge) oder `inventory_add` (neue Row) an Caller.

**Side Effects:** Range-Check ≤1, Loot-Roll-Lock-Check, DB-Update der Item-Ownership.

### `drop_item`
**Client → Server.**
**Felder:** `item_id: int` (optional, default 0).
**Antworten:** `inventory_remove` (`{item_id}`) an Caller; `item_spawned` (`{item}`) Broadcast.
**Side Effects:** DB-Update `items.owner=NULL`, `x/y` auf Spielerposition.

### `chest_transfer_to`
**Client → Server.**
**Felder:** `chest_id: int`, `item_id: int` (optional, default 0).
**Antworten:** `inventory_remove` + `chest_add` (`{chest_id, item}`) an Caller.
**Side Effects:** DB-Update `items.owner = "chest:<id>"`.

### `chest_transfer_from`
**Client → Server.**
**Felder:** `chest_id: int`, `item_id: int` (optional, default 0).
**Antworten:**
- Sonderfall Currency: `chest_remove` (`{chest_id, item_id}`) + `wallet_update` an Caller (+ Gewinn-Toast).
- Normalfall: `chest_remove` + `inventory_add` (`{item}`) an Caller.

**Side Effects:** DB-Delete bzw. Update der Ownership; bei Münzen Currency-Gutschrift.

---

## Domäne: combat

### `attack_npc`
**Client → Server.**
**Felder:** `npc_id: int` (optional, default 0).
**Antworten:**
- `toast` ("erschöpft" Stamina-Penalty).
- `player_needs` an Caller bei Stamina-Drain.
- `visual_effect` (Waffen-FX) Broadcast.
- `npc_damaged` (`{npc_id, hp, max_hp, dmg, crit, by}`) Broadcast bei überlebendem NPC.
- `npc_died` (`{npc_id, killed_by, name}`) Broadcast bei Kill.
- `item_spawned` Broadcasts via `_drop_loot_for_npc` (Loot, Boss-Gear, Key-Items).
- `wallet_update` + Gewinn-Toast bei Münz-Drops.
- `quest_progress` an Caller (Kill-Quests + multi-stage).
- `loot_roll_started` Broadcast an Group falls Need/Greed-Regel und rollbares Item.
- `skill_xp` an Caller und (geteilt) an nahe Group-Member.
- `factions_update` + Reputation-Toast an Caller bei Friendly/Hostile-Kill.

**Side Effects:** DB-Damage am NPC, ggf. Loot-Spawn, Quest-Hooks (`quests.on_creature_killed`, `quest_stages.on_player_event(kill)`), Faction-Hook, Combat-XP-Share via `_gain_combat_xp_with_share`, Camp-Cleared-Tracking für Bandit-Kinder.

### `cast_spell`
**Client → Server.** Zwei Pfade: neuer Spell-System-Path (`spell_id`) und Legacy-Item-Path (`item_id`).
**Felder:**
- Neuer Pfad: `spell_id: str` (required), `target_x: int?`, `target_y: int?`, `target_npc_id: int?` (alle optional).
- Legacy: `item_id: int` (optional, default 0).

**Antworten (neuer Pfad):**
- `toast` (Cast nicht beherrscht, Fehlschlag-Reason wie `no_mana`/`cooldown`/...).
- `player_mana` an Caller.
- `cast_started` (`{spell_id, cast_time_ms}`) an Caller.
- Folge-Frames aus `spell_caster`: `cast_finished` / `cast_interrupted`, beim Auflösen `_apply_spell_effects` → `visual_effect`, `npc_damaged`/`npc_died`, `player_healed`, `status_effects`, `skill_xp`, `quest_progress`.

**Antworten (Legacy):**
- `toast` (Mana-Mangel, "Kein Ziel ...").
- `visual_effect` (Spell-spezifisch: `fireball_explosion`, `ice_spell`, `holy_shield_aura`, ...) Broadcast.
- `npc_damaged` / `npc_died` Broadcast pro Ziel.
- `quest_progress`, `skill_xp` Frames analog `attack_npc`.
- `player_healed` (Self-Heal-Spells).
- `player_mana` an Caller.
- `inventory_remove` an Caller wenn Spell-Item consumed.
- `status_effects` an Caller bei Self-Effect.

**Side Effects (beide Pfade):** Mana-Decrement, Magic-XP, Cast-State im `spell_caster`, ggf. NPC-Damage + Loot-Pipeline (analog `attack_npc`).

---

## Domäne: crafting

### `open_hand_crafting`
**Client → Server.**
**Felder:** —.
**Antworten:** `crafting_open` (`{station: "hand", recipes}`) an Caller.
**Side Effects:** keine.

### `craft`
**Client → Server.**
**Felder:** `station: str` (optional, default ""), `recipe_id: str` (optional, default "").
**Antworten:**
- `toast` (Research-Lock, "Nicht genug Material", Quality-Erfolg).
- `inventory_full_refresh` (`{inventory}`) an Caller.
- `skill_xp` an Caller (crafting, evtl. cooking).

**Side Effects:** Verbraucht Inputs via `items.consume_one`, würfelt Quality (`quality.roll_quality`) mit Talent-Boost, optional Affixes (`affixes.roll_affixes`) und LLM-Naming für Legendaries (`item_namer.generate_name_and_flavor`), DB-Insert des Outputs.

---

## Domäne: trade

### `open_trade`
**Client → Server.**
**Felder:** `npc_id: int` (optional, default 0).
**Antworten:** `trade_open` (`{npc_id, npc_name, offerings, coins}`) an Caller.
**Side Effects:** Range-Check ≤2 zum Merchant; `trade.generate_offerings(8)` ist deterministisch nicht-persistent.

### `buy_item`
**Client → Server.**
**Felder:** `kind: str` (optional, default "").
**Antworten:**
- `toast` ("Nicht genug Geld").
- `skill_xp` an Caller (social).
- `inventory_full_refresh` an Caller.
- `wallet_update` an Caller (via `_push_wallet`).
- `trade_coins` (`{coins}`) an Caller.

**Side Effects:** `currency.spend` (atomar), Refund bei Item-Erzeugungs-Fail, Social-Skill-XP, Talent-Discount.

### `sell_item`
**Client → Server.**
**Felder:** `item_id: int` (optional, default 0).
**Antworten:**
- `skill_xp` an Caller (social).
- `inventory_full_refresh` an Caller.
- `wallet_update` an Caller.
- `trade_coins` an Caller.

**Side Effects:** DB-Delete des Items, `currency.add`, Talent-Bonus auf Sell-Price.

---

## Domäne: character/progression

### `allocate_attr`
**Client → Server.**
**Felder:** `attr: str` (required, sonst skip), `n: int` (optional, default 1; range −50..50).
**Antworten:** `attrs_update` an Caller, oder `toast` bei Allokations-Fehler.
**Side Effects:** `player_stats.allocate_point(...)` aktualisiert Attribute in DB.

### `learn_talent`
**Client → Server.**
**Felder:** `talent_id: str` (optional, default "").
**Antworten:**
- `toast` ("Unbekanntes Talent", Fehler-Reason wie `skill_too_low`, Erfolg).
- `talent_learned` (`{talent_id, points, learned, tree}`) an Caller.

**Side Effects:** DB-Insert in `learned_talents`, Decrement Talent-Points.

### `learn_spell`
**Client → Server.**
**Felder:** `item_id: int` (optional, default 0).
**Antworten:**
- `toast` ("kein Zauber-Item", "bereits bekannt", Erfolg).
- `spell_learned` (`{spell_kind, learned}`) an Caller.
- `skill_xp` (magic) an Caller.
- `inventory_full_refresh` an Caller.

**Side Effects:** DB-Insert in `learned_spells`, Konsum des Spell-Items.

### `cast_learned`
**Client → Server.** Legacy-Cast-Pfad eines bereits gelernten Spells ohne Item, ohne `spell_caster`.
**Felder:** `spell_kind: str` (optional, default "").
**Antworten:**
- `toast` ("nicht gelernt", "Zu wenig Mana", "✨ X gewirkt").
- `player_mana` an Caller.
- `player_healed` (Self-Heal).
- `status_effects` an Caller bei Self-Effect.
- `skill_xp` (magic) an Caller.

**Side Effects:** Mana-Abzug, ggf. Self-Heal, ggf. Status-Effekt-Apply.

### `list_attributes`
**Client → Server.**
**Felder:** —.
**Antworten:** `attributes_update` (`{...attrs}`) an Caller.
**Side Effects:** keine.

### `character_check_name`
**Client → Server.**
**Felder:** `display_name: str` (optional, default "").
**Antworten:** `character_name_check` (`{name, available, reason}`) an Caller.
**Side Effects:** SELECT-Probe in `players` (case-insensitive).

### `character_create`
**Client → Server.**
**Felder:** `preset: str` (optional), `allocated: dict` (optional), `display_name: str` (optional).
**Antworten:**
- `toast` für jeden Validierungs-Fehler (min 3 Zeichen, Whitelist-Chars, Name vergeben, Preset ungültig, Punkte-Limit, schon erstellt).
- `character_created` (`{preset, display_name, allocated, unspent}`) bei Erfolg.

**Side Effects:** DB-Update `players.preset/allocated_attrs/unspent_attr_points/display_name/character_created`. Akzeptiert nur einmal pro Account.

### `list_talents`
**Client → Server.**
**Felder:** —.
**Antworten:** `talents_update` (`{learned, points, tree}`) an Caller.
**Side Effects:** keine.

### `wake`
**Client → Server.**
**Felder:** —.
**Antworten:** keine direkte Response (Stamina/HP-Regen-Status kommt aus dem Needs-Loop).
**Side Effects:** `needs.set_resting(player_id, False)` — beendet das Bett-Ruhen.

---

## Domäne: quests

### `list_quests`
**Client → Server.**
**Felder:** —.
**Antworten:** `quests_update` (`{quests, reputation}`) an Caller.
**Side Effects:** keine.

### `query_npc_quests`
**Client → Server.**
**Felder:** `npc_id: int` (optional, default 0).
**Antworten:** `npc_quest_status` (`{npc_id, offers, turnins}`) an Caller (auch bei Creature: leere Listen).
**Side Effects:** keine.

### `accept_quest_template`
**Client → Server.**
**Felder:** `template_id: str` (optional, default ""), `npc_id: int` (optional, default 0).
**Antworten:**
- `toast` (Quest-Limit, Generic-Fehler, "📜 Title", Kill-Quest-Spawn-Hinweis).
- `quest_new` (`{quest}`) an Caller.
- `skill_xp` (social) an Caller.
- `npc_spawned` Broadcasts via `npc_worker.spawn_cluster` falls Kill-Quest mit fehlenden Mobs.

**Side Effects:** DB-Insert in `quests`, ggf. Quest-Spawn-Garantie für `kill`-Templates.

### `quest_turn_in`
**Client → Server.**
**Felder:** `quest_id: int`, `npc_id: int` (optional, default 0).
**Antworten:**
- `toast` ("nicht abschließbar", Faction-Toast, "✅ Quest abgegeben").
- `inventory_add` an Caller pro Item-Reward.
- `wallet_update` an Caller (via `_push_wallet`).
- `skill_xp` an Caller (Legacy-XP, falls Quest noch alte `xp`-Reward hat).
- `quest_closed` (`{quest_id}`) an Caller.

**Side Effects:** `quests.turn_in(...)` ändert Status, Research-Pool-Award, Currency-Gutschrift, Faction-Rep-Update.

### `accept_quest_from_npc`
**Client → Server.**
**Felder:** `npc_id: int` (optional, default 0).
**Antworten:**
- `toast` (Quest-Limit, "kein Auftrag", "📜 Title").
- `quest_new` an Caller.
- `skill_xp` (social) an Caller.

**Side Effects:** KI-generierte Quest via `quest_generator.generate_quest_for_npc`, Fallback auf Template via `quests.create_from_template`.

### `claim_quest_reward`
**Client → Server.**
**Felder:** `quest_id: int` (optional, default 0).
**Antworten:**
- `inventory_add` pro Item-Reward.
- `wallet_update` an Caller.
- `skill_xp` (combat) an Caller.
- `quest_closed` (`{quest_id}`) an Caller.
- `toast` ("✅ Quest abgegeben").

**Side Effects:** Currency-Gutschrift, Research-Pool-Award, Faction-Reputation, `quests.mark_closed`.

---

## Domäne: research

### `invest_research`
**Client → Server.**
**Felder:** `node_id: str` (optional, default ""), `points: int` (optional, default 1; range 1..10).
**Antworten:**
- `research_update` (`{...result}`) an Caller.
- `toast` ("🔬 Forschung abgeschlossen ...") bei Abschluss eines Nodes.

**Side Effects:** `research.invest(...)` schreibt Punkte in DB, ggf. setzt `done=true`.

---

## Domäne: bills

### `add_bill`
**Client → Server.**
**Felder:** `station_type: str`, `recipe_id: str` (optional, default ""), `count: int` (optional, default 1; range 1..99).
**Antworten:**
- `toast` ("🔒 Erst forschen ...") bei Research-Gate.
- `bills_update` (`{bills}`) an Caller.

**Side Effects:** `bill_queue.add_bill(...)` schreibt Bill in DB.

### `remove_bill`
**Client → Server.**
**Felder:** `bill_id: int` (optional, default 0).
**Antworten:** `bills_update` (`{bills}`) an Caller.
**Side Effects:** `bill_queue.remove_bill(...)` löscht Bill.

### `list_bills`
**Client → Server.**
**Felder:** `station_type: str` (optional, filtert die Liste).
**Antworten:** `bills_update` (`{bills}`) an Caller.
**Side Effects:** keine.

---

## Domäne: dialog

### `talk_to_npc`
**Client → Server.**
**Felder:** `npc_id: int` (optional, default 0), `message: str` (required, max 500 Zeichen, leer → skip).
**Antworten:**
- `toast` bei nicht-redenden Targets (Creatures, Livestock, Carts).
- `npc_reply` (`{npc_id, text}`) an Caller.
- `quest_progress` an Caller bei Multi-Stage-Talk-Trigger.

**Side Effects:** Speichert User- und NPC-Turn in `npc_talks` (DB), persistiert Memory async via `npc_memory.write_memory`, generiert Antwort via `dialog.reply(...)` mit Kontext (Recent-Events, Active-Quest, Region-Lore, NPC-Memory-Retrieval), ggf. Lazy-Gen der Region-Historie im Hintergrund.

---

## Anhang: Vollständige Liste der Server→Client-Types

Alphabetisch, mit 1-Zeilen-Sinn. Diese Liste ist der Tracker für die Frontend-Migration in Phase F3.

- `attributes_update` — Snapshot der Roh-Attribute (response to `list_attributes`).
- `attrs_update` — Stat-Sheet (combined attrs + equipment) nach Equip-Wechsel oder Allokation.
- `bills_update` — Bill-Queue-Liste für Stations.
- `body_part_damaged` — Body-Part-Schaden (`legs`/`arms`/`torso`).
- `cast_finished` — Spell-Resolve-Signal aus `spell_caster`.
- `cast_interrupted` — Cast-Unterbrechung (Bewegung / Schaden).
- `cast_started` — Cast-Bar-Start mit `cast_time_ms`.
- `character_created` — Charaktererstellung erfolgreich gespeichert.
- `character_name_check` — Live-Verfügbarkeitscheck eines display_name.
- `chat` — Welt-Chat-Frame (`from`, `text`).
- `chest_add` — Item ist in eine Truhe gewandert.
- `chest_open` — Truhen-Inhalt-Snapshot.
- `chest_remove` — Item aus Truhe entfernt.
- `chunks` — Folge-Chunks bei Chunk-Wechsel.
- `crafting_open` — Crafting-UI öffnen (Station + Recipes).
- `disaster_started` — Disaster aktiv (Blutmond / Sterbende Sonne / Pest / ...).
- `disaster_ended` — Disaster vorbei.
- `dungeon_chest_opened` — Dungeon-Chest ist geleert (Sprite removen).
- `dungeon_enter` — Floor-0-Eintritt mit Tile-Map.
- `dungeon_exit` — Spieler verlässt Dungeon, Overworld-Kontext kommt mit.
- `dungeon_floor_change` — Wechsel innerhalb des Dungeons (Treppe rauf/runter).
- `earthquake_shake` — Erdbeben-FX-Trigger.
- `error` — generischer Error-Frame (selten).
- `event` — Welt-Event-Eintrag (von Workern / `raid_director`).
- `factions_update` — Reputations-Snapshot über alle Fraktionen.
- `group_chat` — Party-/Raid-Chat-Frame.
- `group_converted` — Party wurde zu Raid (kind-Wechsel).
- `group_disbanded` — Gruppe aufgelöst.
- `group_error` — Fehler bei Group-Operation (`reason`).
- `group_invite_received` — Eingehender Invite an den Target-Spieler.
- `group_invite_sent` — Bestätigung der Invite an den Inviter.
- `group_kicked` — Spieler wurde gekickt.
- `group_member_left` — Member hat Gruppe verlassen.
- `group_member_offline` — Member ist offline gegangen.
- `group_member_online` — Member ist online gekommen.
- `group_state` — Voller Group-Snapshot (members + roles).
- `init` — Initial-Welt-Snapshot beim Connect.
- `inventory_add` — neue Item-Row im Inventar.
- `inventory_full_refresh` — komplettes Inventar-Resync.
- `inventory_remove` — Item-Row weg.
- `inventory_update` — Stack-Quantity oder Item-Felder updaten.
- `item_picked_up` — Broadcast: Item ist nicht mehr am Boden.
- `item_spawned` — Item ist neu am Boden.
- `loot_roll_resolved` — Need/Greed-Roll fertig (Winner steht fest).
- `loot_roll_started` — Need/Greed-Roll startet (eligible-Liste + Item).
- `loot_roll_voted` — Zwischenstand eines Need/Greed-Rolls.
- `loot_rule_changed` — Loot-Regel der Gruppe geändert.
- `loot_vote_error` — Vote ungültig (`reason`).
- `npc_damaged` — NPC nimmt Schaden.
- `npc_died` — NPC tot.
- `npc_moved` — NPC bewegt sich (aus npc_worker).
- `npc_quest_status` — Offers + Turn-Ins, die ein NPC dem Spieler anbietet.
- `npc_reply` — NPC-Dialog-Antwort.
- `npc_spawned` — NPC erscheint in der Welt.
- `player_damaged` — Eigener HP-Update nach Damage.
- `player_downed` — Down-State-Start mit Timer.
- `player_downed_visible` — Down-Sichtbarkeit für Mitspieler.
- `player_healed` — Eigene Heilung.
- `player_joined` — Neuer Spieler eingeloggt.
- `player_left` — Spieler ausgeloggt.
- `player_mana` — Mana-Update.
- `player_moved` — Position-Broadcast.
- `player_needs` — Hunger/Stamina/Thirst-Snapshot.
- `player_respawned` — Eigener Respawn (Position + HP).
- `player_revived_visible` — Revive für Mitspieler-Sprites.
- `pong` — (reserviert, aktuell ungenutzt; siehe Konventionen).
- `quest_board_open` — Quest-Board-Auswahl öffnen.
- `quest_closed` — Quest geschlossen (Reward gezogen).
- `quest_new` — Neue Quest angenommen.
- `quest_progress` — Fortschrittsupdate (Single + Multi-Stage).
- `quests_update` — Voller Quest-List-Snapshot.
- `raid_error` — Manueller Raid abgelehnt (`reason`).
- `raid_started` — Manueller Raid getriggert.
- `research_pool_update` — Forschungspool gefüllt (z. B. via Item).
- `research_update` — Node-Stand nach Invest.
- `rest_start` — Bett-Schlaf gestartet.
- `sign_inspect` — Settlement-Schild geklickt (Modal-Trigger).
- `skill_xp` — Skill-XP-Gain (single oder shared).
- `spell_learned` — Neuer Spell im Buch.
- `status_effects` — Voller Status-Effekt-Snapshot.
- `structure_damaged` — Struktur nimmt Schaden.
- `structure_placed` — Neue Struktur in der Welt.
- `structure_removed` — Struktur weg.
- `structure_repaired` — Reparatur durchgeführt.
- `structure_replaced` — Struktur-Type-Wechsel (z. B. Tür auf/zu).
- `structure_upgraded` — Material upgrade (straw→wood→stone).
- `talent_learned` — Talent gelernt + neuer Tree.
- `talents_update` — Voller Talent-Snapshot.
- `time_tick` — Uhr-Tick aus `time_system`.
- `toast` — generische 1-Zeilen-Notification.
- `trade_coins` — Münz-Stand nach Trade-Aktion.
- `trade_open` — Handels-UI öffnen (Offerings + Münzen).
- `trap_triggered` — Dungeon-Falle ausgelöst.
- `visual_effect` — generischer FX-Spawn (kind, x, y).
- `wallet_update` — Geldbeutel-Stand (`copper`).
- `world_event` — Welt-Event-Notification (Dungeon-Spawn, ...).
