# Liege — Feature-Backlog

Stand: 2026-05-25 (nach Sub-Wellen 1-13)

## ✅ Sub-Wellen 1-13 (2026-05-25 Session 3)

### Welle 1: Tools-System ✅
- 4 neue Tool-Items (pickaxe/shovel/hammer/hoe) — Slot "tool"
- Equipping verleiht Skill-Bonus: 2× structure-damage bei richtigem Skill + 40% Extra-Drop
- Hammer: +50% Construction-XP beim Bauen
- Rezepte am Amboss zum Schmieden

### Welle 2: Food-System ✅
- 8 echte Foods: apple, berries, wheat, bread, raw_meat, cooked_meat, fish, mushroom_food
- FOOD_RESTORE-Werte differenziert (raw=18, cooked=45, bread=40)
- Drops: apple aus tree_oak, berries aus bush, mushroom_food aus mushrooms, fish aus fishing_net
- Crafting: Brot aus Weizen (furnace), cooked_meat aus raw_meat/fish (furnace)
- Frontend: "Essen"-Button für Food-Items

### Welle 3: 6 neue Mobs ✅
- rat (15 HP, 3 dmg), bat (20 HP, 4 dmg), zombie (60 HP, 10 dmg)
- bandit (45 HP, 14 dmg, droppt sword/bow + gold)
- boar (70 HP, 11 dmg, raw_meat-Loot), bear (120 HP, 20 dmg, raw_meat + leather)
- Alle in CREATURE_KINDS → aggressiv, Loot-Tabellen + Move-Chances konfiguriert

### Welle 4: Frontend Body-Parts + NPC-Mood ✅
- 3 Body-Part-Bars (Torso/Arme/Beine) unter Stamina-Bar
- WS-Handler body_part_damaged → live-update
- Mental-State-Icon (😢/😨/💢) über NPC-Sprites
- WS-Handler npc_mood

### Welle 5: Bills-Queue UI ✅
- Im Crafting-Modal eigene Sektion "📋 Aufträge"
- +1/+5 Bill-Buttons pro Rezept
- Auto-refresh bei bills_update/bill_progress/bill_done/bill_blocked
- Backend-Hook list_bills beim Modal-Open

### Welle 6: Research-Tree-Panel ✅
- Hotkey R öffnet Forschungs-Panel
- 8 Knoten in 4 Pfaden mit Progress-Bars
- +1/+5 Buttons zum Investieren
- Prereqs sperren abhängige Knoten

### Welle 7: Tag/Nacht-Zyklus ✅
- time_system.py: 1 real-sec = 2 in-game min, voller Tag = 12 min real
- 4 Phasen: morning/day/evening/night (mit Übergangs-Logs)
- WS-Broadcast time_update (alle 5s)
- Frontend: Tint-Overlay + Uhr (☀️ 08:00)
- NPCs: Friendlies wandern 0.2× nachts, Creatures 1.3×

### Welle 8: Prozedurale Dörfer + Räuber-Lager ✅
- village_spawner.py: 18% Chance pro Settlement-qualifizierten Chunk
- Dorf = 3×3 Wood-Hütte mit Tür + Bett + Lagerfeuer + 1 friendly NPC
- Räuber-Lager: 4% Chance pro freiem Chunk
- Camp = Lagerfeuer + 2 camp_tents + cooking_pot + crate + 2 Banditen
- Auto-Spawn beim populate_chunk_if_needed

### Welle 9: Dungeon-Skelett ✅ (9b für Welt-Switching)
- dungeon_world.py: BSP-basierter Generator (24×24, 4 Räume + Korridore)
- DB-Schema: dungeons-Tabelle + players.world_id/overworld_x/y
- Frontend-Assets: dungeon_door/floor/wall/stairs + 5 dungeon_props preloaded
- Backend-Skelett ready — Welt-Switching-Implementation als Welle 9b
- **Welle 9b (offen)**: enter_dungeon/exit_dungeon Roundtrip, Frontend-View-Switch

### Welle 10: Quest-System ✅
- quests.py: 7 Quest-Templates (fetch/kill mit DE-Texten)
- DB-Tabelle quests mit progress + reward JSONB
- WS: accept_quest_from_npc, list_quests, claim_quest_reward
- Auto-Hooks: on_item_collected (pickup + harvest), on_creature_killed
- Frontend: Q-Hotkey → Quest-Panel mit Progress + Claim-Button
- "📜 Auftrag annehmen"-Button im NPC-Dialog

### Welle 11: Magic-Status-Effekte ✅
- status_effects.py: 6 Effekte (burning/poisoned/bleeding/blessed/shielded/slowed)
- Worker tickt DOT/HOT (3s) und broadcastet status_effects pro Spieler
- rune_stone-Spell verleiht "blessed" (4 HoT × 20s)
- Frontend: Status-Chip-Row mit Icons + Restzeit

### Welle 12: Asset-Recheck + Integration ✅
- 13 Biome-Props in BIOME_SPAWNS integriert (Desert: cactus/desert_skull/dry_bush, Jungle: palm/flower/vines, Snow: frozen_bush/ice_crystal/snow_rock, Swamp: bubbles/log, Lava: lava_rock)
- Alle in harvest.py DURABILITY + YIELD_PER_HIT eingetragen
- Frontend: alle Biome-Props + Dungeon-Assets preloaded

### Welle 13: Skill-Erweiterung ✅
- 4 neue Skills (RimWorld-inspired): cooking, medical, farming, social
- Frontend Skills-Panel um 4 Zeilen erweitert
- Hooks: cooking-XP bei bread/cooked_meat-Crafting, medical-XP bei Heiltrank-Use, social-XP bei Quest-Annahme
- Skill-Effekte: cooking_quality_bonus, medical_heal_bonus, farming_growth_bonus, social_trade_discount (für später)

## ✅ Sub-Wellen 14-20 (Session 4 — 2026-05-25)

### Welle 14: Pixel-Movement ✅
- Continuous Velocity-based movement (240 px/sec)
- Per-Achse Collision (slide-along-wall)
- Tile-Sync nur bei Tile-Wechsel
- Other-Players + NPCs: 220ms Lerp-Tween

### Welle 15: Siedlungen mit Variation ✅
- 3 Siedlungs-Typen: Stadt / Dorf / Lager
- 6 Haus-Größen-Varianten (gewichtet)
- 5 Haus-Typen: house / shop / smithy / workshop / tavern
- Mehrere NPCs pro Siedlung mit haustyp-passenden Kinds
- Stadt: zentraler Brunnen + Marktstand-Truhe
- Räuber-Lager: Lagerfeuer + 2-3 Zelte + 2-4 Banditen

### Welle 16: 8 neue Waffen ✅
- wand, greatsword, spear, crossbow, throwing_knife, mace, scythe, dagger
- Items + Frontend-Preload + Stats

### Welle 17: Weapon/Armor Stats-System ✅
- item_stats.py: WEAPON_STATS (damage, speed, crit, range, two_handed)
- ARMOR_STATS (defense, weight, block_chance), JEWELRY_STATS
- combat.calc_player_damage() mit Quality + Skill + Crit
- Damage-Reduction: total_defense / (total_defense + 100) — diminishing
- Crit-Broadcast für Frontend
- Weapon-Range im Attack-Pfad (spear=2, crossbow=6 tiles)

### Welle 18: Talent-Baum ✅
- talents.py: ~55 Talente in 11 Skill-Pfaden
- Tier 1/2/3 mit Skill-Level-Anforderungen + Prereqs
- 1 Talent-Punkt pro Skill-Levelup
- Talent-Effekte aggregiert + in Combat/Mining/Woodcutting/Medical/Crafting integriert
- Frontend Talent-Panel mit T-Hotkey, Tabs pro Skill

### Welle 19: KI-Item-Generator mit Affix-System ✅
- affixes.py: Prefix/Suffix-Pools (Tier 1/2/3, gewichtet, item-tag-gefiltert)
- Quality-basiertes Affix-Budget (fine: 0-1+0-1, masterwork: 1-2+1-2, legendary: 2-3+1-2)
- item_namer.py: LLM generiert Name + Flavor (NUR Narrative, KEINE Stats)
- llm.py: JSON-Schema-Constrained-Output für strukturierte Generation
- Crafting-Flow integriert: fine+ Items bekommen Affixes, legendary auch LLM-Naming
- Frontend zeigt unique_name, Affixes-Tag, Flavor-Text

### Welle 20: KI-Quest-Generator mit Verifikator ✅
- quest_generator.py: 10 Quest-Templates mit Welt-Conditions
- Template-Auswahl: Player-Level + NPC-Kind-Preferenz + Welt-Verifikation
- Kill-Quests werden nur generiert wenn Creature-Kind in der Welt existiert
- LLM-Narrative-Layer: NUR Title + Description (deutsch, NPC-Persona)
- Fallback auf statische Templates bei LLM-Fehler

## ✅ Sub-Wellen 21-27 (Session 5 — Recherche-Empfehlungen)

### Welle 21: 8 neue NPC-Kinds ✅
- mage/farmer/villager/guard/merchant/healer/quest_giver/blacksmith
- Eigene Sprites + HP-Werte + Move-Chances
- village_spawner: Haus-Typ → spezifische NPC-Kinds
- Stadt: 2 Wachen + Quest-Giver + Heiler am Brunnen

### Welle 22: Storyteller-Director ✅
- storyteller.py mit 3 Modi (chill/balanced/chaos)
- Deterministische Event-Auswahl basierend auf Welt-State
- Anti-Streak-Logik (nicht 2× danger in Folge)
- LLM macht nur noch Narrative für vorgegebenen kind+tag

### Welle 23: Welt-Historie pro Region ✅
- region_history.py mit 8×8-Chunk-Regionen
- Slow-Brain generiert region_name + theme + 3-5 historische Events
- Lazy-Trigger beim NPC-Dialog (async, blockt nicht)
- Region-Lore als Plot-Essentials im Dialog-System-Prompt

### Welle 24: Semantic-Cache (LLM-Output-Cache) ✅
- llm_cache.py mit nomic-embed-text Embeddings + Python-cosine
- Threshold pro Kind: factual=0.95, lore=0.92, intent=0.88, creative=NIE
- TTL pro Kind, Hash-Lookup zuerst (Fast-Path)
- Integriert in item_namer + quest_generator
- DB-Tabelle llm_cache mit JSONB-Embedding

### Welle 25: NPC Long-Term-Memory ✅
- npc_memory.py mit Episode-Storage + Importance-Scoring
- Top-K Retrieval mit Score = α·sim + β·recency + γ·importance
- Recency-Decay = exp(-Δt / 1 Tag)
- Importance via Fast-Brain (1-10), <2 nicht persistiert
- Memories als Plot-Essentials im Dialog-Prompt

### Welle 26: NPC-Quest-Eligibility ✅
- QUEST_GIVING_KINDS: quest_giver/merchant/blacksmith/mage/scholar/guard/soldier/healer
- Andere NPCs (wanderer/villager/farmer/hermit/bard) geben KEINE Quests
- Dialog-Context für aktive Quest: NPC erinnert an offene Pflicht
- Dialog-Context für completed Quest: NPC bedankt sich
- NPC ohne Quest erklärt im Charakter warum er keine hat
- Frontend: Quest-Button nur bei eligible Kinds

### Welle 27: Faction-System ✅
- 8 Default-Factions: villagers/goblins/bandits/kings_guard/merchants_guild/arcane_circle/undead_cult/wild_beasts
- 12 Initial-Relations zwischen Factions
- Player-Reputation -100..+100 mit 5 Tiers (hostile/unfriendly/neutral/friendly/allied)
- Propagation: 30% der Aktion schwingt auf verbündete (+) und feindliche (−) Factions
- NPC-Kill → Reputation-Hit + Tier-Wechsel-Toast
- Frontend Faction-Panel (F-Hotkey) mit Bars + Tier-Labels

## ✅ Sub-Wellen 28-31 + 9b (Session 6 — Final-Cleanup)

### Welle 28: Multi-Step-Quest-DAG ✅
- quest_stages.py mit 4 Multi-Stage-Templates (lost_amulet, wolves_threat, blacksmith_forge, arcane_research)
- DAG-Stages (locked/unlocked/in_progress/completed) mit requires-Liste
- 30% Chance auf Multi-Stage statt Single-Stage beim Quest-Annehmen
- Frontend rendert Stages mit Status-Icons (✓⏳▷🔒)
- Player-Hooks: collect/kill/talk events triggern stage-progression

### Welle 29: Dungeon-Themes ✅
- 5 Themes: crypt/mine/temple/ruin/cave mit eigenen Mob-/Loot-/Decor-Pools
- Deterministische Theme-Wahl aus Stair-Position
- Encounter-Loot themen-spezifisch (Krypta → bone/scroll, Mine → ore/crystal, …)

### Welle 30: Combat-Power-Budget ✅
- power_budget.py: DPS-Curve = BASE_DPS * 1.15^level
- Mob-HP-Skalierung mit Player-Level (cap 3×)
- Mob-Damage skaliert sanfter (1.06^level)
- player_level_estimate = primary(combat/magic) + 0.5 * 2nd-Skill

### Welle 31: Polish-Items ✅
- Cooking-Skill-Bonus aktiviert (+4% Hunger-Restore pro Level)
- Master-Chef-Talent: +10 HP bei cooked Food
- Social-Skill-Discount im Trade-Handler aktiviert
- Haggler-Talent + Merchant-Friend-Talent integriert
- Farming-XP-Hook im farm_worker (15 XP pro Pflanze gewachsen)
- NPC-Home-Position: Friendlies kehren nachts zu home_x/home_y
- Move-toward-Helper für gerichtetes NPC-Movement

### Welle 9b: Begehbare Dungeons (Welt-Switch) ✅
- dungeon_instance.py mit get_or_create + enter/exit
- Player-DB-State: world_id, overworld_x/y für Rückkehr
- Stairs-Down: dungeon_enter (statt Encounter), Stairs-Up im Dungeon: dungeon_exit
- Server validiert Moves gegen Dungeon-Tiles wenn in Dungeon
- Frontend renderet Dungeon-Tiles, blendet Overworld aus
- isWalkable berücksichtigt Dungeon-Modus
- Same-seed-stair gibt gleichen Dungeon (persistent)

## ❄️ Noch offen (Asset-abhängig oder spätere Polish-Phase)
- Tile-Übergänge (Auto-Tiling Terrain) — pures Polish
- Music + Sound-Effekte (Audio-Assets nötig)
- Walk-Animation Frames (Sprite-Sheets nötig)
- Tag/Nacht beeinflusst Resource-Spawn (Pilze nachts) — späteres Tuning
- Dungeon-Mobs spawnen IM Dungeon beim Betreten (aktuell sind Dungeons leer — Mobs werden via Encounter-Loot abgebildet, später full-spawn)
- Quest-Hint-System für stuck-Quests (Heartbeat-Validator aus Recherche)
- Faction-Daily-Drift-Job

## 🔧 Behobene Bugs
- Farm-Worker DataError (str → timedelta) — pre-existing, in Welle 13 mitgefixt

Status: ✅ done, 🔄 in_progress, ⏳ planned, ❄️ later

## ✅ Implementiert

- Welt + Persistenz (Welt, Player, NPCs, Strukturen, Events, Items)
- Multiplayer + Smooth-Movement
- KI-Welt-Events (periodisch + Spieler-Aktionen)
- NPCs mit KI-Identität + Wandern + Aggression + Dialog (Slow Brain)
- Combat (Player-Attack, NPC-Aggression, HP, Respawn, Damage-Bonus durch Waffen)
- Item-System (Spawn, Pickup, Inventar, Equip 7 Slots, Drop, Use mit Heal)
- Build-System mit 3 Materialien (Stein/Holz/Stroh) + Auto-Tiling Wände
- Strukturen: Mauer, Boden, Lagerfeuer, Marker, Truhe, Werkbank, Schmelze, Amboss, Bett, Brunnen, Acker, Spike/Poison-Trap
- Crafting (Werkbank/Schmelze/Amboss) mit Rezepten
- Truhen-Storage (Item-Transfer)
- Heal-Strukturen (Bett, Brunnen)
- Traps mit Damage-on-Step
- Visual Effects (Hit-Spark, Heal-Glow, Poison-Cloud)
- Wand-Bitmask-Auto-Tiling mit 10 Varianten pro Material
- Welt-Generator erweitert um 5 Biome (Wüste, Dschungel, Lava, Schnee, Sumpf)
- Mob-Respawn (alle 3 Min, Creatures auf ≥4 auffüllen)

## 🐛 Offene Bugs / kleine Lücken

- Welt-DB hat noch alte Tile-IDs (0-4) — neue Biome erst nach `docker compose down -v`
- TestGobbo bei (62,41) — Test-Rest in DB
- struct_floor Fallback bei Material-Floor (eigentlich kein Bug, dokumentiert)

## ✅ Welle 12 — RimWorld-Mechaniken Tier 1+2+3 (2026-05-25)

### Tier 1: Spielbar machend
- **Skill-System** (skills.py): 7 Skills (Mining/Woodcutting/Gathering/Construction/Crafting/Combat/Magic), Level 0-20, XP-Hooks an Aktionen, Effekte (Yield-Bonus, Damage-Bonus)
- **Item-Quality** (quality.py): 5 Stufen (roh/normal/fein/meisterhaft/legendär), Skill-basiertes Quality-Roll beim Crafting, Stat-Multiplier
- **Hunger + Stamina** (needs.py): periodische Need-Bars, Food restored Hunger, bei 0 HP-Verlust, Stamina regen
- **Storyteller-Modi** (env STORYTELLER_MODE): balanced/chill/chaos beeinflusst Event-Härte + Spawn-Frequenz

### Tier 2: Tiefe
- **Body-Parts-Health** (body_parts.py): legs/arms/torso jeweils 0-100. Damage trifft random Body-Part. Verletzte Arme reduzieren ausgeteilten Schaden. Heiltrank ≥25 HP heilt auch Parts.
- **Crafting-Bills (Queue)** (bill_queue.py): bills-Tabelle, Worker arbeitet Queue per Tick ab, WS-Messages add_bill/remove_bill/bills_update/bill_progress
- **NPC-Mood + Mental Breaks** (npc_mood.py): mood_value 0-100, mental_state (normal/sad/fleeing/berserk), Mood-Worker decay, Hooks für Wander-Logic

### Tier 3: Major
- **Research-Tree** (research.py): 8 Knoten in 4 Pfaden (Schmiede/Alchemie/Magie/Landwirtschaft/Architektur). Punkte-Investition, Prerequisites
- **Raid-Mechanik** (raid_director.py): periodischer Check pro Spieler, basiert auf Wealth (Struktur-Count). Triggert Spawn von 2-6 Creatures nahe der Base. Cooldown 30min.

### Smoke-Test
- 11 Hintergrund-Worker laufen parallel
- Init liefert: HP, Mana, Hunger, Stamina, 7 Skills, 3 Body-Parts, 8 Research-Knoten

### Was im Frontend NOCH FEHLT
- Bill-Queue-UI im Crafting-Modal (aktuell nur single-click crafting)
- Research-Tree-UI (separates Panel)
- Body-Parts-Anzeige
- NPC-Mood-Indikator (optional, könnte als kleine Icon über NPC erscheinen)
- Verbleibt für nächste Session

## ✅ Welle 11 — Welt-Refactor (2026-05-25)

### Multi-Layer-Noise statt sin/cos
- Value-Noise mit deterministischem Hash, multi-octave FBM
- 4 parallele Maps: height, moisture, temperature, fertility
- 4 zusätzliche Maps für Resource-Density (tree/rock/ore/plant)
- 1 Settlement-Map (markiert Bauplätze die NICHT mit Deko zugewachsen werden)
- 1 Lake-Map (innland-Seen in feuchten Senken)

### Bessere Welt-Distribution
- 12% Wasser (vorher 2%)
- 86% walkable (gut für Bewegung + Hindernisse für Atmosphäre)
- Variation: Grass 43%, Sand 26%, Forest 6%, Jungle 6%, Swamp 4%, Mountain 3%, Desert 1%, Water 12%
- Strand-Gürtel rings um Wasser
- Bergketten zusammenhängend

### Resource-Density mit Cluster-Effekt
- Spawn-Chances 5× reduziert + mit Density-Map moduliert
- Bäume dichter im Wald-Zentrum (fertility hoch), dünner am Rand
- Settlement-Areas garantiert leer (Bauplätze)
- Ressourcen-Cluster statt random scatter

### Welt-Manager-KI
- Slow Brain bekommt **welt-state-summary** beim Event-Generieren
- State: aktive Spieler, wilde Kreaturen, Bewohner, Spieler-Bauten
- KI reagiert kontextuell ("viele Kreaturen → Wildnis-Unruhe", "viele Bauten → wachsende Zivilisation")

### Asset-Welle 11 (12 neue Assets integriert)
- **Boss-Mobs**: ogre (200 HP), necromancer (150 HP), dragon_whelp (180 HP) mit eigenen Loot-Tabellen + Damage-Werten
- **Settlement-Deko**: camp_tent, cooking_pot (Lager-Reste auf der Welt)
- **Ruins-Deko**: bones_scatter, gravestone (Atmosphäre)
- **Wasser-Deko**: dock_corner, boat_small, anchor, fishing_net, driftwood
- Alle harvestbar mit eigenen Durabilities + Loot-Tabellen

## ✅ Wellen 7-10 (2026-05-25, Session 2)

### Welle 7: Chunked Procedural World ✅
- world_chunks Tabelle, 32×32 Chunks, lazy generiert + persistiert
- Effektiv unendliche Welt — Spieler kann frei wandern
- Legacy 120×80 Welt migriert in 12 Chunks
- Frontend lädt nur Chunks im 7×7 um Spieler, neue Chunks gesendet bei Chunk-Crossing
- Camera-Bounds entfernt
- Async `world.is_walkable`, `world.tile_at`, `world.find_spawn` — synchroner Fallback `is_walkable_sync` für Tight Loops in Workern

### Welle 8: Welt-Respawn ✅
- respawn_worker spawnt periodisch (alle 5min) ~15 Strukturen in geladenen Chunks nach
- Bäume / Felsen / Gras können nachwachsen wo abgeerntet

### Welle 9: Event-getriggertes Mob-Spawn ✅
- Slow-Brain-Events können Creatures spawnen
- Heuristik: Wenn Event-Body Creature-Namen erwähnt → spawn passend
- Bei "creature"-kind → zufälliges Creature
- Sonst 25% Chance auf Zufalls-Spawn

### Welle 10: Händler-Mechanik ✅
- merchant-NPCs öffnen jetzt **Trade-Modal** statt Dialog
- Marktpreise pro Item (trade.py: ITEM_VALUES)
- Verkaufspreis = Marktwert / 2
- Coin-Workaround: `gold_ore` ist die Währung (ASSET_NEEDED: coin sprites)
- Random 8 Angebote pro Trade-Session aus MERCHANT_POOL

## ✅ Wellen 1-6 (2026-05-25)

### Welle 1: NPC-Loot-Drops ✅
- Goblin/Wolf/Skelett/Spinne/Slime droppen kind-spezifische Items (1-2 pro Kill)

### Welle 2: Acker-Growth ✅
- Klick auf Acker + Kraut im Inventar → planted
- Farm-Worker prüft alle 30s, nach 60s wächst Kraut-Item

### Welle 3: Mana + Magic-System ✅
- player.mana/max_mana (default 50)
- Manatrank +30 Mana
- 3 Spells: Feuerball-Buch (AOE), Schriftrolle (single, verbraucht), Heilrune (self-heal)
- Mana-Bar unter HP

### Welle 4: Combat-Polish ✅
- NPC-Tint Rot 250ms bei Treffer
- Screen-Rand Rot bei Spieler-Damage
- Knockback-Vibration

### Welle 5: Dungeons (Encounter-MVP) ✅
- stairs_down platzierbar
- Klick → 3-5 random Items + 70% Trap-Damage Chance
- 5min Cooldown pro Spieler
- Echte begehbare Dungeons → eigene Welle später

### Welle 6: NPCs kennen Welt-Events ✅
- dialog System-Prompt erweitert um letzte 3 Welt-Events
- NPC kann sie organisch erwähnen

## ❄️ Größere Features (eigene Wellen, später)

- XP/Level-System
- Quests (Slow Brain generiert)
- Fraktionen (Goblin-Lager, Wolfsrudel)
- NPC-Tagesabläufe (Händler reist, Einsiedler bleibt)
- Item-Tier-System (rare/legendary)
- Tag/Nacht-Zyklus + Wetter
- PvP / Trading / Gilden
- Tile-Übergänge (Auto-Tiling für Terrain)
- Walk-Animation mit echten Frames
- Wasser-Animation
- Music + Sound-Effekte
- Auth-System (richtiges Login)
- Boss-Mobs (ogre, necromancer, dragon_whelp aus ASSET_EXPANSION_LIST)
- Deko-Props (trees, bushes, ruins aus ASSET_EXPANSION_LIST)
- Magic-Erweiterung: Buffs/Debuffs/Status-Effects
- Server-Deployment-Script

## 🤖 KI-Tiefe (Phase 5-Vision)

- World-Brain reagiert auf aktuellen Welt-Zustand
- NPC-Stimmungen ändern sich über Zeit
- Lore wird kumulativ in DB aufgebaut
- NPCs leben gegeneinander (Wolf jagt Goblin)
- Dynamische Faktion-Konflikte vom Slow Brain
