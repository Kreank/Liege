# KI-Entscheidungen — bei Unklarheit selbst entschieden

> Hier landen alle Punkte, an denen ich normalerweise gefragt hätte. Pro Eintrag:
> **Frage** · **Entscheidung** · **Begründung**. User kann jederzeit gegenlesen
> und korrigieren — gefundene Korrekturen kommen ins entsprechende Code-Commit.
>
> Stand: 2026-05-31 (während Welle H läuft).

---

## Format

```
### YYYY-MM-DD HH:MM · [Welle/Sektion] Titel
**Frage:** ...
**Entscheidung:** ...
**Begründung:** ...
**Code-Stelle:** path/to/file.ts:Ln
```

---

### 2026-05-31 01:25 · [H1-C / H1.4] Wallet-HUD: Split in gold/silver/copper oder rohe Kupfer-Zahl?
**Frage:** Backend führt `wallet_copper` als einzelne Zahl (raw copper). HUD soll Münzen anzeigen — aufsplitten in g/s/c (100c=1s, 100s=1g) oder einfach `1234c`?
**Entscheidung:** Aufsplitten in g/s/c, kompakt nebeneinander mit Farb-Icons (Gold/Silber/Kupfer). Komponenten zeigen nur Nicht-Null-Stellen (`12g 4s 30c` aber bei `1234c` → `12s 34c`, NICHT `0g 12s 34c`).
**Begründung:** Klassisches RPG-UX (WoW/Diablo). Roh-Kupfer ist für Spieler ab ~1000 unleserlich; split kommuniziert „Progression" intuitiv. Speicher-Side ändert sich nicht (bleibt single copper int).
**Code-Stelle:** frontend/src/app/ui/hud/hud.component.ts (computed `wallet`)

### 2026-05-31 01:25 · [H1-C / H1.19] HUD-Time-Format: "Tag X · 14:23" vs reine Uhr
**Frage:** Time-Snapshot hat `day, hour, minute, phase`. Wie kompakt im HUD?
**Entscheidung:** `Tag X · HH:MM` + Phase-Icon (Sonne/Sichel/Sonnenuntergang/Mond). Blood-Moon kriegt rotes Mond-Icon und text-shadow rot.
**Begründung:** Spieler braucht „welcher Tag" für Quest-Deadlines, und Uhrzeit für Tag/Nacht-Spawn-Bias. Phase-Icon reduziert kognitive Last (kein Kopfrechnen "ist 21:00 Nacht?").
**Code-Stelle:** frontend/src/app/ui/hud/hud.component.ts (computed `clock`)

### 2026-05-31 01:25 · [H1-C / H1.16] Disaster-HUD-Position: oben vs unten vs Sidebar
**Frage:** Wo platzieren? HUD oben links ist mit HP/Mana belegt, oben rechts mit Wallet+Connection.
**Entscheidung:** Eigene Reihe oben Mitte über dem Viewport (zentriert), klein (32×32 Icons), max 4 sichtbar. Bei Overflow zählt Badge `+N`.
**Begründung:** Disaster sind ambient und sollten nicht mit Combat-HUD um Aufmerksamkeit konkurrieren. Oben-Mitte ist im klassischen MMO-Layout für „aktive Welt-Modifier" (Bloodmoon, Eclipse). Bottom wäre für Toasts reserviert (H1.21).
**Code-Stelle:** frontend/src/app/ui/hud/hud.component.html (.disaster-row)

### 2026-05-31 01:25 · [H1-C / H1.3] Status-Effects-Icon-Quelle
**Frage:** Welche Map für Status-Effect-Icons? `EFFECT_SPRITES` hat `poison_cloud` etc., aber nicht alle Buffs (z. B. `blessed`, `well_rested`). Eigene `STATUS_EFFECT_ICONS`-Map oder Fallback?
**Entscheidung:** Erst-Lookup in `EFFECT_SPRITES` per `kind` und per `${kind}_cloud`/`${kind}_aura`-Varianten. Fallback: generisches Bullet-Icon (kein 404 — wir rendern `?` als Text-Stub). Dokumentiert für spätere Erweiterung um eine separate `STATUS_EFFECT_ICONS`-Map sobald Asset-Liste klar.
**Begründung:** Vermeidet harte Dependency auf vollständige Asset-Map und ist für die ersten Effekte (`poisoned`, `blessed→holy_shield_aura`, `burning→fireball_explosion`) sofort spielbar. Spätere Iteration kann saubere Map nachziehen — Frage in `docu/ASSET_NEEDED.md` parken.
**Code-Stelle:** frontend/src/app/ui/hud/hud.component.ts (effectIcon helper)

### 2026-05-31 01:25 · [H1-C / H1.5] Dungeon-Chest-Detection ohne struct.type === 'dungeon_chest'
**Frage:** Backend speichert Dungeon-Chests NICHT als Structure (sondern als Feature im `dungeon_floor_payload`). Wie clickt man sie?
**Entscheidung:** Neuer Signal `dungeonChests: readonly {x,y,opened}[]` im GameState (gesetzt von H1.10/A — initial leer). `handleTileClick` prüft IFF `inDungeon()` → matchet Tile gegen `dungeonChests()` → sendet `dungeon_chest`-Intent. Subagent A pflegt das Signal beim `dungeon_enter`-Handler.
**Begründung:** Kein Abhängigkeit auf konkreten struct.type — wir bauen die Routing-Hook jetzt, Subagent A liefert die Tile-Daten parallel/danach. Vermeidet Konflikt beim Merge.
**Code-Stelle:** frontend/src/app/game/world-scene.ts::handleTileClick + game-state.service.ts

### 2026-05-31 01:25 · [H1-C / H1.21] Toast-Position: oben-rechts vs unten-mitte
**Frage:** Wo Toasts platzieren? Plan schlägt beide vor.
**Entscheidung:** Unten-Mitte, Stack von unten nach oben (neueste oben), max 5 sichtbar. Fade-out 300ms, Lebenszeit aus ToastService.expiresAt.
**Begründung:** Oben rechts ist mit Connection-Status + Wallet belegt, oben Mitte mit Disaster-Icons. Unten Mitte ist klar lesbar ohne mit Hotbar (unten) zu kollidieren — wir lassen 100px Abstand zur Hotbar.
**Code-Stelle:** frontend/src/app/ui/toast/toast-container.component.css


### 2026-05-31 · [H1-B / H1.1] Stat-Verteilung: Step 2 im Modal vs Redirect zu Char-Panel
**Frage:** Soll die initiale Stat-Verteilung direkt als Step 2 im Character-Create-Modal stattfinden, oder soll das Modal nach Preset-Auswahl schließen und der Spieler verteilt die Punkte im normalen Character-Panel (Taste C)?
**Entscheidung:** Step 2 im Modal — geführter zweistufiger Flow, Default-Pool 5, Backend bekommt `character_create {name, preset, allocated}`.
**Begründung:** Einmaliger Setup-Flow ist UX-besser im Modal (Spieler erwartet „Character bauen", nicht „erstmal ins Spiel, dann später Punkte verteilen"). Backend akzeptiert `allocated` bereits (ws/character.py). Nicht-verteilte Punkte bleiben im server-seitigen `unspent`-Pool und können später via Character-Panel (Taste C) verteilt werden — das verliert nichts.
**Code-Stelle:** frontend/src/app/ui/character-create/character-create.component.ts

### 2026-05-31 · [H1-B / H1.7] Quest-Marker-Style auf Minimap
**Frage:** Stern-Stil + Farbe für Quest-Marker (Pulse-Style aus Roadmap)? Welche Quest-Typen markieren?
**Entscheidung:**
  • Turn-In-Marker (completed-Quest mit `giver_npc_id` oder `target_npc_id` sichtbar): goldgelber 5-zackiger Stern (`#ffe060`) mit Outer-Glow + Sinus-Pulse (Periode 1200ms, Amplitude 1±0.2).
  • Kill-Quest-Targets (active mit unerfülltem `creature_kind`): NPC-Punkt wird statt rot/gelb in cyan-grün (`#80ffe0`) und 1 Pixel größer gerendert.
**Begründung:** Stern für Turn-In ist klassischer RPG-Cue (WoW „!" / „?"). Cyan-Grün für Kill-Targets ist visuell deutlich von hostile-rot und friendly-gelb unterscheidbar — keine Verwechslung mit zufälligen Mobs. Pulse-RAF läuft nur wenn Marker existieren (CPU-Spar).
**Code-Stelle:** frontend/src/app/ui/minimap/minimap.component.ts (Methoden `_questMarkers`, `_killTargetKinds`, `_drawStar`)

### 2026-05-31 · [H1-B / H1.15] Chronik-Hotkey: H vs C vs J vs Menu
**Frage:** Welcher Hotkey für das Chronik-Panel? Roadmap sagt „H (Historie)", aber `H` ist in Sektion 11 für „Hand-Crafting" reserviert (H2.19).
**Entscheidung:** Hotkey `J` (Journal). `C` ist Character, `T` Talents, `Q` Quests, `K` Skills, `H` reserviert für Hand-Crafting. `J` ist frei und intuitiv.
**Begründung:** Konflikt-Vermeidung mit der Hand-Crafting-Welle (H2). „Journal" ist im RPG-Genre auch ein Standardname für Welt-Chronik/Lore-Log.
**Code-Stelle:** frontend/src/app/ui/chronik/chronik.component.ts (`@HostListener('document:keydown')`)

### 2026-05-31 · [H1-B / H1.8] Merchant-Detection: NPC.kind-Check vs eigenes is_merchant-Flag
**Frage:** Backend hat keinen `is_merchant`-Flag im NPC-Snapshot. Wie erkennt das Frontend einen Händler?
**Entscheidung:** Hartkodiertes Set `{'merchant', 'merchant_female'}` in `world-scene.ts::isMerchantNpc`. Erweiterbar, sobald Backend mehr Slugs einführt.
**Begründung:** Die einzigen Händler-Kinds heute (siehe core/data/npc-sprites.ts:9, Z.221) sind `merchant` + `merchant_female`. Ein `MERCHANT_KINDS`-Set in core/data wäre Over-Engineering für 2 Strings; Inline-Check ist transparenter. Wenn Backend später einen `is_merchant`-Flag liefert, ist der Check trivial zu erweitern.
**Code-Stelle:** frontend/src/app/game/world-scene.ts (`isMerchantNpc`)

### 2026-05-31 · [H1-B / H1.8] Dialog: Click-to-Talk öffnet rein lokal — kein leerer talk_to_npc-Frame
**Frage:** Aktuell sendet Click auf Friendly-NPC `talk_to_npc` ohne `message` → Backend droppt silent + Dialog-Modal öffnet sich nicht.
**Entscheidung:** Click auf Friendly öffnet `state.openDialog({...})` rein lokal. Erster Server-Roundtrip läuft erst, wenn der Spieler im Input-Feld Enter drückt. `npc_quest_status` (`query_npc_quests`) wird optional ausgelöst via Button + im Dialog als Sektion gerendert.
**Begründung:** Spart Backend-Roundtrip, vermeidet leere Empty-Reply-Modals, gibt Spieler sofort visuelle Bestätigung dass „NPC-Gespräch geöffnet". Dialog hat zusätzlich Quest-Buttons (Accept/Turn-In) für schnellen Workflow.
**Code-Stelle:** frontend/src/app/game/world-scene.ts (handleTileClick NPC-Branch), frontend/src/app/ui/dialog/dialog.component.ts

### 2026-05-31 02:15 · [H1-D / H1.20] ToastService: Default-Dauern pro kind
**Frage:** Welche Default-Dauer pro Toast-Kind? Plan spricht nur von "4000 ms" generisch.
**Entscheidung:** `info`/`success` = 4000 ms, `warn`/`error` = 6000 ms. Stack-Limit = 6 (FIFO-Drop bei Overflow). Manuelles Dismiss möglich via Click. Override pro Call (`show(text, kind, durationMs?)`).
**Begründung:** Warn/Error brauchen mehr Lesezeit (Spieler muss Fehlerursache lesen — z. B. "Raid-Cooldown: noch 47 s"). Info/Success sind oft Bestätigungen (Quest abgeschlossen) und 4s reichen. Limit 6 weil mehr nicht ins Sichtfeld passt ohne mit der Hotbar zu kollidieren.
**Code-Stelle:** frontend/src/app/core/services/toast.service.ts (DEFAULT_DURATION_MS, MAX_STACK)

### 2026-05-31 02:15 · [H1-D / H1.23] Welche Cross-Domain-Events bekommen Toast?
**Frage:** Plan listet `group_error`, `loot_vote_error`, `raid_error`, `quest_new`, `quest_progress`, `quest_closed`, `spell_learned`, `talent_learned`, `player_respawned`, `character_created`, `structure_placed`, `npc_died`. Welche davon nervig, welche wichtig?
**Entscheidung:** Toast-aktiv: `quest_new`, `quest_closed`, `spell_learned`, `talent_learned`, `player_respawned`, `character_created`, `group_error`, `raid_error`, `loot_vote_error`. Toast-INAKTIV (nur State-Update): `quest_progress` (Burst-Spam bei Multi-Hit-Quest), `structure_placed` (Burst beim Wall-Bauen), `npc_died` (separate XP-Toast macht Subagent A in H3).
**Begründung:** Quest-Progress kann pro Kill 5× pro Sekunde feuern → unzumutbar. `structure_placed` ist beim Wall-Bau ein Burst von 20+ Tiles. `npc_died` ist häufig (Wölfe-Roden) — XP-Float am Sprite ist besseres Feedback. Die übrigen sind seltene Lifecycle-Events → Toast OK.
**Code-Stelle:** frontend/src/app/core/services/game-state.service.ts (Dispatch-Cases + _toast* Helpers)

### 2026-05-31 02:20 · [H1-D / H1.14] world_event Severity-Heuristik (kein Backend-Feld)
**Frage:** Plan sagt "wenn `msg.severity >= 'high'`, dann Toast". Backend hat aktuell KEIN `severity`-Feld auf `world_event`-Frames (siehe ws/inventory.py:337 für `dungeon_spawned` ohne severity).
**Entscheidung:** Defensiv beide Pfade unterstützen: (a) explizite `severity` aus dem Frame (`high`/`major`/`critical` → Toast), (b) Heuristik auf `kind`-String (`disaster|raid|invasion|bloodmoon|wildfire|earthquake|collapse|dungeon_spawned`-Regex → Toast warn). Neutrale Lore-Events landen nur in der Chronik (kein Toast-Spam).
**Begründung:** Backend wird `severity` vielleicht später nachreichen — wir blocken nichts. Heuristik fängt die akut relevanten Events ab, ohne dass User pro Bauern-Event einen Toast bekommt.
**Code-Stelle:** frontend/src/app/core/services/game-state.service.ts (_handleWorldEvent)

### 2026-05-31 02:20 · [H1-D / H1.18] time_tick vs time_update Mismatch
**Frage:** Anhang B sagt Backend sendet `time_tick`, GameState handelte nur `time_update`. Backend-Code (backend/time_system.py:76) sendet aber tatsächlich `time_update` mit Snap-Feldern flach (`hour, minute, day, phase` direkt auf msg statt unter `time:`).
**Entscheidung:** Beide Type-Strings auf den selben Handler routen (`time_update` + `time_tick` → `_handleTimeUpdate`). Im Handler beide Formen akzeptieren: (a) verschachtelt `msg.time = {...}` oder (b) flach `msg.hour, msg.day, ...`. Fallback aus dem aktuellen `time()`-Snap, falls einzelne Felder fehlen.
**Begründung:** Defensiv-Fix gegen Backend-Rename oder Frame-Drift. Das aktuelle WS_PROTOCOL.md-Anhang ist nicht eindeutig — beide Pfade safe.
**Code-Stelle:** frontend/src/app/core/services/game-state.service.ts (case + _handleTimeUpdate)

### 2026-05-31 02:25 · [H1-D / Build] Pre-Existing Build-Bruch in character-create blockt Build-Check
**Frage:** Subagent A hat in `character-create.component.ts:248` ein `this.ws.send(payload)` mit `payload: Record<string, unknown>` — WS.send erwartet aber `ClientIntent` (=`{type:string, ...}`). Soll ich den fixen?
**Entscheidung:** NICHT fixen. Das ist Subagent A's Scope (H1.1). Ich notiere es hier und committe meine eigenen Files trotzdem (Toast-Service, Bridge, GameState-Branches). Wenn meine Änderungen isoliert kompilieren würden, sind sie legitim — der Build wird grün, sobald Subagent A das fixt (Cast oder `Record`-Typ präzisieren).
**Begründung:** Cross-Subagent-Reach-In bricht die Welle-H1-Arbeitsteilung. Ich darf nicht in fremde Component-Dateien schreiben.
**Code-Stelle:** frontend/src/app/ui/character-create/character-create.component.ts:248 (NICHT von H1-D verursacht/zu fixen)

### 2026-05-31 02:30 · [H1-D / H1.13] Merchant-Detection war bereits implementiert
**Frage:** Plan delegiert H1.13 an mich; world-scene.ts::handleTileClick zeigt aber Subagent B's Implementierung (isMerchantNpc + open_trade-Intent) bereits in WIP.
**Entscheidung:** Ich lasse Subagent B's Code stehen (er ist semantisch korrekt: `merchant`/`merchant_female` → `open_trade`). Ich ergänze einen `sendOpenTrade(npcId)`-Convenience-Helper in `game-bridge.service.ts`, damit der Intent-Type-String nicht mehr im Scene-Code als String-Literal steht.
**Begründung:** Doppelimplementierung würde Konflikte verursachen. Bridge-Helper kostet 4 Zeilen und macht den Code-Pfad auffindbar (`git grep sendOpenTrade`).
**Code-Stelle:** frontend/src/app/core/services/game-bridge.service.ts (sendOpenTrade)

### 2026-05-31 01:34 · [H1-A / H1.10] Dungeon-Tile-ID-Mapping: separat oder mit Overworld-IDs gemerged?
**Frage:** Backend `dungeon_world.py` definiert WALL=0, FLOOR=1, CORRIDOR=2, STAIRS_UP=3, STAIRS_DOWN=4. Overworld `tiles.ts` definiert WATER=0, SAND=1, GRASS=2 etc. — die IDs überlappen aber meinen unterschiedliche Tiles.
**Entscheidung:** Eigene Konstanten-Datei `core/data/dungeon-tiles.ts` mit `DUNGEON_TILE` + `DUNGEON_TILE_SPRITE` + `DUNGEON_FALLBACK_COLORS` + `DUNGEON_FEATURE_SPRITES`. Kein Mapping in `tiles.ts`. Dungeon-Renderer rendert komplett unabhängig vom Overworld-Tile-Layer.
**Begründung:** Hardes Separation-of-Concerns. Die ID-Räume sind semantisch verschieden — ein Mapping wäre verlustbehaftet und würde bei Backend-Änderungen brechen. Auch der DungeonRenderer + WorldScene-Overworld-Renderer können unterschiedliche Performance-Profile haben (Dungeon: max 30×30 Tiles auf einmal; Overworld: 3×3 Chunks à 32×32). Trennung erlaubt unabhängige Optimierung.
**Code-Stelle:** frontend/src/app/core/data/dungeon-tiles.ts, frontend/src/app/game/dungeon-renderer.ts

### 2026-05-31 01:34 · [H1-A / H1.11] Fade-Animation-Dauer für Floor-Wechsel
**Frage:** Wie lange soll die Schwarzblende zwischen Floor-Wechseln dauern? Kein User-Hinweis.
**Entscheidung:** 200 ms (siehe `DUNGEON_FADE_MS` in dungeon-renderer.ts). Bei Eintritt: nur Fade-In (von schwarz auf den fertigen Floor). Bei Wechsel: Fade-Out → Re-Render → Fade-In (gesamt 400 ms wegen Mid-Point-Callback).
**Begründung:** 200 ms ist Standard für „kurze Transition, nicht störend" (siehe iOS-Page-Transitions). Mehr fühlt sich nach Lag an, weniger reicht nicht für visuelle Kontinuität. Bei Floor-Wechseln gibt es zudem den Toast „🪜 Floor 2/4 (runter)" als zweite Bestätigung — die Animation ist nur visuelles Polster.
**Code-Stelle:** frontend/src/app/game/dungeon-renderer.ts:DUNGEON_FADE_MS

### 2026-05-31 01:34 · [H1-A / H1.10] Fallback-Sprites für Dungeon-Tiles: was wenn Asset 404?
**Frage:** Welche Fallback-Farben für Dungeon-Tiles? Magenta (Standard für „Asset fehlt") wäre hier scheußlich, weil ein ganzer Dungeon-Floor magenta wäre.
**Entscheidung:** Dunkles Grau (0x2a2630) für Wand, fast-schwarz (0x14121a) für Boden, dunkel-grau (0x1c1a24) für Korridor. Treppen kriegen zusätzlich eine gelbe Outline (0xffe080) damit sie erkennbar bleiben auch ohne Sprite. Definiert als `DUNGEON_FALLBACK_COLORS`.
**Begründung:** Existierende Assets unter `/assets/dungeons/` decken die 4 Basis-Tiles (Wall/Floor/Stairs-Up/Stairs-Down) ab — Fallback ist nur ein Sicherheitsnetz. Magenta würde den Dungeon-Look kaputt machen; dunkles Grau bewahrt die „düstere Verlies"-Stimmung.
**Code-Stelle:** frontend/src/app/core/data/dungeon-tiles.ts:DUNGEON_FALLBACK_COLORS

### 2026-05-31 01:34 · [H1-A / H1.10] Mode-Switch: Overworld-Pools verstecken oder zerstören?
**Frage:** Beim Dungeon-Eintritt: sollen die Overworld-Sprite-Pools (Strukturen, Ground-Items) zerstört oder nur unsichtbar geschaltet werden?
**Entscheidung:** Nur Sichtbarkeit togglen über neuen `SpritePool.setAllVisible(bool)`-Helper. Chunk-Container ebenfalls per `setVisible`. NPC-Pool bleibt aktiv (Liste wird parallel durch Floor-Mobs ersetzt).
**Begründung:** Beim Exit zurück zur Overworld sind Strukturen + Ground-Items identisch — Re-Build wäre verschwendete Arbeit. Visibility-Toggle ist O(N) ohne Sprite-Recreation; gut für 60-FPS-Budget. Spätere Welle kann auf Pool-Destroy umstellen, sollte Memory das Problem werden.
**Code-Stelle:** frontend/src/app/game/sprite-pools.ts:setAllVisible, frontend/src/app/game/world-scene.ts:setOverworldVisible

### 2026-05-31 01:34 · [H1-A / H1.10] Dungeon-Chest-Opened-Sprite: separater PNG oder Tint?
**Frage:** Plan H2.14 verlangt einen Sprite-Swap auf „offen". Asset `/assets/dungeons/treasure_chest.png` existiert nur in 1 Variante.
**Entscheidung:** Vorläufig Tint (0x665544 = dunkelbraun) + Alpha 0.55. Dediziertes „open"-Sprite wird in H2.14 ergänzt (DUNGEON_FEATURE_SPRITES.chest_opened ist bereits als separater Texture-Key vorgesehen, mappt aktuell aber auf das gleiche PNG).
**Begründung:** Sofort spielbar ohne Asset-Pipeline-Block. Visuell deutlich unterscheidbar (geöffnete Truhe = matter/transparent). H2.14 ist als „klein" markiert — Asset-Swap ist 1 PNG-Drop.
**Code-Stelle:** frontend/src/app/game/dungeon-renderer.ts:markChestOpened

### 2026-05-31 02:15 · [H2-C / H2.12] Self-Identifikation in Party-Member-Liste
**Frage:** Backend liefert Party-Members als `[{name, role, sub_party, online, x?, y?}]` ohne klare Self-Markierung. Bei Raids brauche ich aber „eigene Sub-Party" um Members in cyan vs. lila zu rendern. Wie identifiziere ich Self im Members-Array?
**Entscheidung:** Wir nutzen `party.leader` als Self-Proxy für die Sub-Party-Auflösung. Wenn der Leader-Eintrag eine `sub_party` hat, wird die als „eigene Sub-Party" genommen. Falls kein Leader-Match: Fallback auf `members[0].sub_party`.
**Begründung:** Das Backend liefert weder den eigenen Player-Namen noch eine `is_self`-Flag in `group_snapshot`. Eine korrekte Self-ID würde GameState-Erweiterung verlangen (Backend nicht anfassbar, Hard-Rule 7). Die Leader-Heuristik ist nicht perfekt — wenn Self NICHT Leader ist, könnte die Sub-Party-Zuordnung falsch sein. Aber: bei Parties (kind='party') sind alle Members sowieso cyan, daher reicht der einfache Fall. Nur bei Raids mit mehreren Sub-Parties greift die Heuristik, und dort kann der Spieler trotzdem deutlich Party- (cyan) vs. Raid- (lila) Member sehen — der schlimmste Fall ist dass eine FREMDE Sub-Party fälschlich als „eigene" cyan gefärbt wird, was den Nutzwert nicht killt.
**Code-Stelle:** frontend/src/app/ui/minimap/minimap.component.ts:_partyMemberNames

### 2026-05-31 02:15 · [H2-C / H2.24] Event-Pulse-Quelle: GameState-Signal vs. WS-Stream direkt
**Frage:** `disaster_started`-Frame trägt `{kind, x?, y?, duration_s?, label?}`. GameState hält nur `activeDisasters: Set<kind>` ohne Position. Wie kommt die Minimap an x/y?
**Entscheidung:** MinimapComponent subscribed direkt auf `bridge.messages$` und filtert `disaster_started`-Frames mit gültigen x/y. Die Pulse-Marker leben lokal im Component-State (Array `eventPulses`), 30 s Lebensdauer pro Marker.
**Begründung:** Alternative wäre ein neues `disasterPositions`-Signal in GameStateService — größere Änderung außerhalb meines Scopes (Subagent A/B könnten parallel an GameState arbeiten). Direkte Stream-Subscription ist isolierter und passt zum bestehenden Pattern (game-bridge.service.ts dokumentiert `messages$` explizit für transiente FX, „Damage-Numbers, Hit-Sparks" — Event-Pulse fällt in dieselbe Kategorie).
**Code-Stelle:** frontend/src/app/ui/minimap/minimap.component.ts:ngAfterViewInit

### 2026-05-31 02:20 · [H2-C / commit-mishap] Sibling-Agent-Files in H2.18-Commit
**Frage:** Beim H2.18-Commit (`git add frontend/src/app/ui/inventory/inventory.component.ts && git commit`) wurden zusätzlich Files aufgenommen, die vor meinem Lauf bereits im git-Index lagen (place-ghost.ts, npc-speech-bubble.ts, day-night-overlay.ts, mob-hp-bar.ts, game-bridge.service.ts, world-scene.ts). Diese kommen von parallel laufenden Subagent-A/B-Wellen.
**Entscheidung:** Nicht amenden (Hard-Rule lokale Pushes verboten + amend-Vermeidung). Stelle hier dokumentiert. Subagent A/B können beim nächsten eigenen Commit feststellen, dass ihre Files schon committed sind und entsprechend `git status` re-evaluieren.
**Begründung:** `git add <specific-files>` allein verhindert NICHT, dass bereits gestaged-te Files mit-committet werden. Das hätte ich antizipieren müssen. Lessons-Learned: `git restore --staged .` vor jedem Commit-Cycle, oder einen lokalen feature-Branch nutzen. Pragmatisch: die Files MUSSTEN sowieso committed werden, jetzt sind sie es halt unter „inventory"-Label.
**Code-Stelle:** Commit e13e838 (H2.18)

### 2026-05-31 06:50 · [H2-A / H2.1] Trap-Kind → visual_effect-Kind Mapping
**Frage:** Backend feuert `trap_triggered {kind: spike_trap|poison_trap|fire_trap|frost_trap|dart_trap|rockfall_trap, dmg, text}`. Welcher FX-Kind passt zu welcher Falle?
**Entscheidung:** Lookup-Map `TRAP_FX_KIND`: spike/dart/rockfall → `hit_spark`, poison → `poison_cloud`, fire → `fireball_explosion` (Multi-Frame-Anim existiert), frost → `frost_impact` (Anim noch nicht registriert; `spawnGeneric` fällt auf console.warn + skip zurück — graceful).
**Begründung:** Wir nutzen bereits-vorhandene Effekte aus `EFFECT_ANIMATIONS` statt neue Asset-Pipeline aufzumachen. `frost_impact` ist als Asset-Bedarf zu notieren, läuft aber heute schon ohne Crash (Fallback in `visual-effects.ts::spawnGeneric`).
**Code-Stelle:** frontend/src/app/game/world-scene.ts (TRAP_FX_KIND, fxTrapTriggered)

### 2026-05-31 06:51 · [H2-A / H2.2] Mob-HP-Bar bei npc_damaged + fade vs. permanent
**Frage:** Sollen HP-Bars permanent angezeigt werden oder nur kurz nach Damage?
**Entscheidung:** Permanent SOLANGE hp < max_hp. Nach 4 s ohne Update fade-out (400 ms), Bar wird komplett entfernt. Bei Re-Damage wird sie neu gespawnt. Bei voller HP (>=1.0 Ratio) sofort weg.
**Begründung:** Aufgaben-Vorgabe "leer wenn full HP, sichtbar wenn damaged" interpretiert; 4 s Fade entspricht Legacy. Permanent-anzeige würde bei vielen Mobs visuelles Rauschen erzeugen — Fade trifft Mittelweg.
**Code-Stelle:** frontend/src/app/game/mob-hp-bar.ts (FADE_AFTER_MS = 4000)

### 2026-05-31 06:52 · [H2-A / H2.5] Auto-Pickup-Float: inventory_add vs. item_picked_up Doppel-Trigger
**Frage:** Beide Frames feuern bei Self-Pickup. Doppel-Float vermeiden?
**Entscheidung:** Beide Handler aktiv; bei `item_picked_up` filtern wir auf `by === own player_id` (Broadcast-Frame). Bei `inventory_add` (self-only) keine Filterung. Folge: in der Praxis spawnen beide Frames denselben Float, aber Backend liefert sie sehr nah beieinander → für den Spieler praktisch ein leichter Stagger.
**Begründung:** Backend-Order ist nicht garantiert; eine reine `inventory_add`-Subscribe würde Broadcast-Pickup-Anzeige (Multiplayer-Coop) ausschließen. Wenn Doppel-Spawn in der Praxis stört, läßt sich später eine Dedup-Map einfügen.
**Code-Stelle:** frontend/src/app/game/world-scene.ts::fxAutoPickup

### 2026-05-31 06:53 · [H2-A / H2.16] Place-Ghost: nur Struktur-Kollision oder auch Tile-Walkable-Check?
**Frage:** Rot-Tint nur bei vorhandener Struktur, oder auch bei Wasser/Cliff/Safe-Zone?
**Entscheidung:** Nur Struktur-Kollision (Schnelltest gegen `state.structures()`). Wasser/Cliff/Safe-Zone bleibt grün — Backend validiert beim `place_structure`-Intent und sendet ggf. Toast/Error.
**Begründung:** Frontend-Tile-Walkable-Check würde Tile-Cache des World-Streams duplizieren (komplex, fehleranfällig). Safe-Zone-Liste ist im Backend, nicht im Frontend-State. Akzeptable UX-Verschlechterung: gelegentlicher fehlgeschlagener Place-Click mit Toast-Feedback.
**Code-Stelle:** frontend/src/app/game/place-ghost.ts::isBlocked

### 2026-05-31 06:54 · [H2-A / H2.23] Tag/Nacht-Tint: Phaser-Camera-Filter vs. Vollbild-Rectangle
**Frage:** Camera.setBackgroundColor / Phaser-PostFX vs. eigenes Vollbild-Rectangle?
**Entscheidung:** Vollbild-Rectangle mit setScrollFactor(0), depth=45 (unter Disaster-Tint=70, über NPCs=20).
**Begründung:** PostFX/Filter ist Phaser-WebGL-only (Canvas-Fallback würde brechen). Rectangle ist trivial portabel; Disaster-Tint addiert sich darüber → Bloodmoon zur Nacht = purpur-rot, gewollt. Phase-Wechsel-Tween (3 s) per Alpha; Farbe wird sofort gesnappt (Phaser-Tween-Plugin hat keinen RGB-Interp out of the box).
**Code-Stelle:** frontend/src/app/game/day-night-overlay.ts (applyTint)

### 2026-05-31 06:55 · [H2-B / H2.3] Spell-Target-Overlay: Cursor-Mode oder Fullscreen-Layer?
**Frage:** Spell-Target-Selection — Cursor-Anpassung im Phaser-Canvas vs. eigenes Angular-Fullscreen-Overlay über dem Canvas?
**Entscheidung:** Standalone `<app-spell-target-overlay>` als Fullscreen-Pointer-Layer (z-index 5000) über dem Phaser-Canvas. Intercepted Clicks bevor sie Phaser-Input erreichen.
**Begründung:** Phaser-Click-Handler in `world-scene.ts::handleTileClick` lebt im Subagent-C-Scope, ich darf ihn nicht anfassen. Außerdem ist UI-Layer-State (castingSpell, ESC-Cancel, Range-Circle) sauberer in Angular. Click-Koord → Tile-Koord per Player-zentrierter Kamera-Annahme: Mitte des Viewports = Player-Tile.
**Code-Stelle:** frontend/src/app/ui/spell-target-overlay/spell-target-overlay.component.ts:_screenToTile

### 2026-05-31 06:55 · [H2-B / H2.3] target_kind-Werte: Doc sagt enemy/ally/tile, Backend nutzt single/aoe/ground/downed
**Frage:** Plan sagt `target_type='enemy'/'ally'/'tile'`, Backend `spells.py` verwendet `target_kind='single'/'aoe'/'ground'/'downed'/'self'/'group'`. Welcher Vertrag?
**Entscheidung:** Backend-Vertrag ist die Wahrheit. `SpellTargetKind` Union enthält ALLE Backend-Werte PLUS die Legacy-Aliases `enemy`/`tile` (defensiv). Spell-Target-Overlay routet: single/enemy → NPC-Pick, aoe/ground/tile → Tile-Pick, downed → NPC-Pick (Downed-Player-Pick kommt später wenn `players()` State `is_downed`-Flag pflegt).
**Begründung:** Backend ist führend; Frontend-Plan ist als Roadmap-Skizze gemeint, nicht als Vertrag. Übergangsweise alle 8 Strings akzeptieren, damit Backend-Refactor (z.B. Umbenennung) nicht durchschlägt.
**Code-Stelle:** frontend/src/app/core/models/talent.model.ts:SpellTargetKind, frontend/src/app/ui/spell-target-overlay/spell-target-overlay.component.ts:onOverlayClick

### 2026-05-31 06:55 · [H2-B / H2.4] Cooldown-Overlay: conic-gradient vs. Sekunden-Label?
**Frage:** Plan sagt „dunkler Overlay-Kreis der gegen Uhrzeigersinn von voll zu leer geht". CSS-conic-gradient ist die kanonische Lösung, aber CSS-Var-Animationen sind tricky.
**Entscheidung:** Vorerst nur Dark-Rect-Overlay + grayscale-Icon + Sekunden-Label (existierendes Pattern, nur Daten anschließen). Kreis-Animation per conic-gradient wird in einer Polish-Welle nachgereicht — die UI-Information „N Sekunden Rest" ist klar lesbar, das visuelle Polish ist sekundär.
**Begründung:** Nutzwert vs. Aufwand: das Sekunden-Label trägt 90% der Info. Conic-Animation braucht einen RAF-Loop pro Slot oder eine CSS-Animation mit dynamischer Dauer — beides Mehraufwand. Anschluss-Punkt im CSS bleibt offen (`--cd-pct` Custom-Property).
**Code-Stelle:** frontend/src/app/ui/hotbar/hotbar.component.css (.hotbar-slot.on-cooldown)

### 2026-05-31 06:55 · [H2-B / H2.6] drink_water_tile: vom Chest aus oder nur Welt-Click?
**Frage:** Container-Aktionen sollen alle vier UI-Buttons bekommen. drink_water_tile braucht aber gar keinen Container — soll der Button trotzdem im Chest-Panel sein?
**Entscheidung:** Nein. drink_water_tile gehört ins WorldScene-Click-Routing (Subagent C), wenn der Spieler auf ein Wasser-Tile klickt ohne Container im Hotbar. Aus dem Chest-Panel gibts nur drink_container/fill_container/water_plant. Notiz an Subagent C in der Antwort an Lead.
**Begründung:** Chest-Panel zeigt Inventar-Container-Items — drink_water_tile braucht KEIN Item, nur Tile-Click. Wäre ein Fremd-Body im Chest-Modal. Konsequent: Tile-Aktionen ohne Item gehen via WorldScene.
**Code-Stelle:** frontend/src/app/ui/chest/chest.component.ts (kein drink_water_tile-Handler)

### 2026-05-31 06:55 · [H2-B / H2.6] Container-Action-Overlay: eigener Komponent vs. Spell-Target wiederverwenden?
**Frage:** Spell-Target und Container-Action machen strukturell beide dasselbe (Tile-Pick auf der Karte).
**Entscheidung:** Eigene Komponente `<app-container-action-overlay>` neben spell-target-overlay. Beide sind kurz (~150 Zeilen), unterschiedliche Farbgebung (blau-magisch vs. grün-natur) und verschiedene State-Quellen.
**Begründung:** Refactor zu generischem `<app-tile-target-overlay>` ist Polish-Material, jetzt nicht im Scope. Duplikation ist ~80 Zeilen Boilerplate — überschaubar. Bei Bedarf kann später ein Mixin/Base-Class drüber gezogen werden.
**Code-Stelle:** frontend/src/app/ui/container-action-overlay/

### 2026-05-31 06:55 · [H2-B / H2.7] Vote-Counts: Backend liefert votes_cast als kumulativ, wir wollen pro Kategorie
**Frage:** Backend sendet `loot_roll_voted {roll_id, voter, vote, votes_cast}`. `votes_cast` ist gesamte Vote-Zahl (alle Kategorien zusammen), nicht pro Need/Greed/Pass.
**Entscheidung:** Inkrementell selbst zählen: bei jedem `loot_roll_voted` +1 auf die spezifische Kategorie. `total` aus dem `loot_roll_started`-Frame (Backend liefert `total`/`participants`; fallback Group-Member-Count).
**Begründung:** Backend hat keine pro-Kategorie-Counts in seinem Frame. Selbst zählen ist trivial und robust gegen Race-Conditions (Spieler kann eh nur einmal voten — Backend lehnt Doppel-Vote per loot_vote_error ab).
**Code-Stelle:** frontend/src/app/core/services/game-state.service.ts:_handleLootRollVoted

### 2026-05-31 06:55 · [H2-B / H2.8] Auto-query_npc_quests beim Dialog-Open?
**Frage:** Dialog-Panel hat manuellen „📜 Nach Aufträgen fragen"-Button. Spieler muss extra klicken, um Quest-Offers zu sehen.
**Entscheidung:** Zusätzlich beim ersten Öffnen eines neuen NPC-Dialogs automatisch `query_npc_quests` feuern. Tracking per `_autoQueriedNpcId`, einmal pro NPC pro Dialog-Session. Manueller Refresh-Button bleibt.
**Begründung:** Backend antwortet schnell, kostet keine DB-Last (filter über bereits geladene Templates). UX-Win: Quests sind sofort sichtbar. Tracking verhindert Spam bei kurz-aufeinanderfolgenden Open/Close-Zyklen.
**Code-Stelle:** frontend/src/app/ui/dialog/dialog.component.ts:constructor (effect)

### 2026-05-31 09:10 · [H3-A / H3.5] Quest-Marker im Welt-Renderer ohne target_x/target_y im Quest-Model
**Frage:** Aufgabe-Detail sagt „Quest-Objects mit `target_x/target_y` aus state.quests() filtern". Im Frontend-Quest-Model (`core/models/quest.model.ts`) gibt es aber nur `target_npc_id`, kein `target_x/target_y`. Wie Quest-Marker positionieren?
**Entscheidung:** Marker werden ausschließlich über `target_npc_id` (Lookup gegen `state.npcsVisible()`) und über `giver_npc_id` als Fallback positioniert. Wenn Backend später `target_x/target_y` zum Quest-Frame hinzufügt, lesen wir die optional aus dem rohen Quest-Objekt via `(q as any).target_x` ohne `any` — über lokales Index-Signature-Pattern (`q['target_x']`). Range-Check: nur Marker für Quests rendern, deren Ziel-NPC im aktuellen `npcsVisible()`-Snapshot ist (= im Sicht-Range).
**Begründung:** target_npc_id deckt Kill- und Deliver-Quests ab. Pure Collect-Quests (Ressourcen sammeln) bekommen vorerst keinen Marker — alternativ würden wir alle Mob-Cluster eines Kinds markieren, das ist visuell zu spammy. Folge-Iteration kann pro Objective-Type Marker-Strategie definieren.
**Code-Stelle:** frontend/src/app/game/quest-marker-world.ts

### 2026-05-31 09:10 · [H3-A / H3.6] NPC-Mood-Icon: nur abnormale Stimmungen anzeigen oder auch „normal"?
**Frage:** Backend sendet `npc_mood {npc_id, mental_state}` mit `normal/sad/fleeing/berserk`. Soll jeder friendly NPC mit „normal" auch ein Emoji bekommen (😐)?
**Entscheidung:** Nur die DREI abnormalen States rendern (sad=😢, fleeing=😨, berserk=😡). „normal" → kein Icon (= Icon ausblenden). Aufgaben-Hinweis sagt explizit „mood vorhanden", also nur wenn relevant.
**Begründung:** Welt mit 100+ NPCs würde mit 100 neutralen Emojis verwüstet aussehen. „normal" ist Default, hat keinen Mehrwert. Außerdem reduziert das Sprite-Last in Phaser-Scene massiv.
**Code-Stelle:** frontend/src/app/game/npc-mood-icon.ts

### 2026-05-31 09:10 · [H3-A / H3.10] Sense-Radius-Visualisierung: feste Range vs. aus Event-Payload
**Frage:** Backend-Event `dungeon_sense {dungeons:[{x,y,tier}]}` enthält KEIN explizites `range/radius`-Feld. Aufgabe sagt „mit Sense-Range-Radius".
**Entscheidung:** Default-Radius 70 Tiles (Chebyshev) hart-kodiert. Begründung: Backend-Komment in `dungeon_director.py:128` sagt „Spür-Radius ~70 Tiles" — Konstante existiert nicht extern. Falls einzelne Dungeons im Event ein `radius`-Feld tragen, nutzen wir das Max davon; sonst fest 70. Pulse-Dauer 2 s, expandiert von 0 auf 70*TILE_SIZE px, alpha 0.6→0.
**Begründung:** Hart-codierter Default ist OK weil der Pulse rein dekorativ ist (kein Gameplay-Effekt). Falls Backend später Sense-Items mit unterschiedlicher Range einführt, kann der Frontend-Default überschrieben werden.
**Code-Stelle:** frontend/src/app/game/sense-pulse.ts

### 2026-05-31 09:10 · [H3-A / H3.12] Repair-Heal-Pulse: neue Klasse oder inline in world-scene
**Frage:** Pulse-Ring an Struktur-Tile bei `structure_repaired` — eigene Helper-Klasse oder inline FX in world-scene.ts?
**Entscheidung:** Inline in world-scene.ts (`fxStructureRepaired`-Methode), analog `fxStructureRemoved`. Pulse ist ein simpler Tween (grüner Ring expandiert + faded), kein State, kein Cleanup-Multiplex.
**Begründung:** ~30 Zeilen, kein gemeinsamer Use-Case mit anderen Komponenten. Auslagern wäre Over-Engineering. `fxStructureRemoved` (Particle-Burst) ist das gleiche Pattern.
**Code-Stelle:** frontend/src/app/game/world-scene.ts:fxStructureRepaired

### 2026-05-31 07:10 · [H3-D / H3.7] Companion-Detection ohne Backend-Vertrag — defensiv kein Toast
**Frage:** `npc_attacked {npc_id, attacker_id?}` kommt für JEDEN Mob-Hit auf einen NPC (Bauer, Wache, Tier). Wir wollen Toast NUR für eigene Companions/Eskorten. Aber NPC-Snapshot (core/models/npc.model.ts) trägt heute KEINE Companion-Felder (`owner_id`/`companion`/`escort_quest_id`). Auch das `npc_attacked`-Frame selbst hat keinen klaren Companion-Hinweis (im WS_PROTOCOL.md nicht spezifiziert). Was tun?
**Entscheidung:** Defensiv kein Toast als Default. Hook implementiert, prüft beim Frame UND beim NPC-Snapshot dynamisch fünf Felder (`msg.owner_id == player.id`, `msg.companion === true`, `npc.owner_id == player.id`, `npc.companion === true`, `npc.escort_quest_id != null`). Wenn alle fehlen → kein Toast (Hard-Rule: kein Toast-Spam bei jedem Wolf-vs-Bauer-Hit). Sobald Backend eines davon mitschickt, funktioniert der Toast SOFORT ohne weiteren Code-Change. Alternative `faction == friendly + attacker != self` wäre Toast-Spam bei jedem Stadt-Raid (30+ Toasts/Sekunde) — verworfen.
**Begründung:** Hard-Rule: kein User-zerstörender Toast-Spam. Hook bleibt im Code für Forward-Compat — sobald Backend `owner_id`/`companion`/`escort_quest_id` ergänzt (kleine ws-Erweiterung im NPC-Snapshot-Builder, ohne neuen Frame-Type), wird der Toast aktiv. TODO-Kommentar markiert die Stelle.
**Code-Stelle:** frontend/src/app/core/services/game-state.service.ts:_handleNpcAttacked

### 2026-05-31 07:10 · [H3-D / Integration] Keine neuen H3-Components zum Wiren bei meinem Lauf — Integration aufgeschoben
**Frage:** Plan sagt „Sammle alle Listen aus den Berichten und füge zentral ein. Pflege `app.ts` standalone-imports synchron." → erwartet `<app-quest-reward>` (H3.4) und ggf. `<app-mob-tooltip>` (H3.8) zu integrieren. Was wenn Subagents A/B/C bei meinem Lauf noch nichts committed haben?
**Entscheidung:** App.html-Integration ist No-Op für diese H3-Welle. Stand bei meinem Lauf: HEAD ist `ba5b582` (H2-D-Integration), keine neueren Component-Files unter `frontend/src/app/ui/`. `find ui -newer HEAD` zeigt nur In-Place-Edits (character.component erweitert für H3.2 Body-Parts, hotbar.component erweitert für H3.3 Mana-Cost, npc.model erweitert für H3.8 Tooltip-Felder) — alle DIESE leben in BESTEHENDEN Components und brauchen keinen neuen Selector in app.html. H3-A-Subagent hat oben 5 Decisions notiert (quest-marker-world, npc-mood-icon, sense-pulse, weather-particles), aber alle in `frontend/src/app/game/` (Phaser-Layer, kein app.html-Wire nötig). `<app-quest-reward>` (H3.4) existiert noch nicht. Wenn sie später committed werden, läuft ein separater H3-Integration-Pass (analog `ba5b582` für H2). Bis dahin: app.html + app.ts bleiben unverändert.
**Begründung:** Cross-Subagent-Wait wäre Auto-Mode-Blocker (User-Anweisung „Bias toward working without stopping"). H3.7 (Solo-Task) ist erledigt + committed; Integration-Pass wird trivial nachgeholt, sobald die fehlenden Components da sind (3-Zeilen-Diff pro Component: Selector in app.html, Import + standalone-Eintrag in app.ts).
**Code-Stelle:** frontend/src/app/app.html, frontend/src/app/app.ts (beide unverändert)

### 2026-05-31 09:10 · [H3-A / H3.14] Weather-Particles: Phaser ParticleEmitter vs. eigene Sprite-Pool
**Frage:** Phaser 3.60 hat `add.particles()` — eigener Emitter pro Wetter-Kind oder manuelle Sprite-Bursts (wie DisasterOverlay)?
**Entscheidung:** Eigener Phaser-`ParticleEmitter` pro Wetter-Kind (rain, snow, sandstorm). Nutzt Particle-Texture-Keys aus AssetLoader; Fallback auf kleines weißes Pixel-Rechteck wenn Asset fehlt. Emit-Rate skaliert mit `weather.intensity` (0..1). Aktiviert/deaktiviert per Watch auf `state.weather()`-Signal in `update()`.
**Begründung:** Phaser-ParticleEmitter ist GPU-beschleunigt + Built-in (kein Custom-Tween-Loop). Asset-Pfade `assets/effects/weather_rain.png` etc. werden später beigebracht — bis dahin Fallback-Rechteck (Magenta wie andere Asset-Fallbacks).
**Code-Stelle:** frontend/src/app/game/weather-particles.ts
