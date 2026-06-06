# Liege — Briefing

**Stand: 2026-06-06 · „Welt-Kohärenz"-Überarbeitung (Welle 53) live + World-Reset
auf neuen Seed.** Live: https://liege.tech-artist.de (Caddy + TLS).
Repo: `/srv/storage/projects/liege` (GitHub `Kreank/Liege`, Branch `main`, HEAD `98258f4`).

> **2026-06-06 (Welle 53):** Großer Pass gegen fehlende Welt-Struktur/Kohärenz
> (User-Befund: Händler-Schwemme, NPCs verstreut statt in Dörfern, Dörfer wie
> Wald, Stege am Strand, Blitz im Wasser, leere Gebiete, immer dieselben Quests,
> Hotbar-Zuweisung kaputt, Interaktions-Regression). 6 parallele Audit-Agents →
> deutlich mehr gefunden als die ursprünglichen Symptome. Alles deployt.
>
> ⚠️ **Alles seit dem Angular-Refactor (Welle 52 + 53) ist NOCH NICHT committet.**
> `git status` zeigt die geänderten Dateien. Erst nach Test committen.

---

## 🟢 Was in Welle 53 gefixt wurde (alles live)

**Interaktions-Regression (war: Angreifen/Tür/Objekt tot):** Wurzel war ein
Frontend-Crash — Backend sendet Fraktionen mit Key `id`/`name`, Frontend erwartete
`faction_id` → `_displayName(undefined).split()` warf im `rows`-computed → Angular-
Change-Detection brach → UI fror beim Empfangen ein. Fix: `_normalizeFactions`
(id→faction_id, nutzt Backend-`name`), Komponente crash-fest, **plus** WS-Dispatch
front (`game-state.service.ts` `_dispatch` try/catch) und back (`ws/dispatcher.py`
per-Handler try/except, `main.py` Cleanup in `finally`) gehärtet.

**Hotbar:** z-index 50→155 (`hotbar.component.css`) — Inventar-Overlay (150) fing
den Drop ab.

**Block 1 — Bevölkerung (`npc_worker.py`, `event_worker.py`):** Friendly-Soft-Cap
(`MAX_FRIENDLY_COUNT=120`), Heim-Leine (`FRIENDLY_LEASH_RADIUS=14`, NPCs kehren ins
Dorf zurück), Recycle für Karren/Disaster-Mobs/Drifter, Event-Händler-Cap
(`MAX_WANDERING_MERCHANTS=6`), Vieh pro Dorf gesenkt.

**Block 2 — Siedlungen (`village_spawner.py`):** `_clear_settlement_ground` rodet
die ganze Dorf-Bounding-Box von System-Natur-Props (Spielerbauten bleiben) →
Dorf = Lichtung statt Wald.

**Block 3 — Welt-Logik (`world_populator.py`, `weather_worker.py`, `main.py`,
`npc_worker.py`):** Stege auf Ufer-WASSER-Tiles (nicht mehr Sand), Brücken
(`wooden_bridge`) über 1-Tile-Wasserrinnen, Blitz nur auf Land (`world` an
`weather_loop` durchgereicht, Tile-Check), **Pro-Spieler-Mindestbestand**
(`LOCAL_CREATURE_MIN=6` im Radius 32) gegen tote Gegenden.

**Block 4 — Quests (`ws/structures.py`, `quests.py`, `quest_templates.py`):**
Rotation statt Dauer-Sperre (abgeschlossene Templates nach 8h wieder anbietbar),
`UNSUPPORTED_QUEST_TYPES={defend,escort}` aus Angebots-Pools gefiltert
(nicht-abschließbar → blieben sonst als `active` hängen).

**Block B — Exploits (`ws/trade.py`, `ws/crafting.py`, `ws/inventory.py`,
`ws/quests.py`, `quests.py`):** Geld-Arbitrage zu (sell < eigener buy via
`_effective_buy_price`), Verkauf/Crafting/Truhen-Coin atomar (kein Dupe),
Quest-Reward-Doppelvergabe via atomarem `UPDATE…WHERE status='completed' RETURNING`,
`trade_coins`-Vertrag (`coins`→`copper`).

**Block C — Performance/Robustheit (`npc_worker.py`, `structures.py`, `db.py`,
`ws/movement.py`):** N+1 im Wander-Tick weg (Spieler 1×/Tick via
`_ready_players_by_world`), Pool 10→24 (`DB_POOL_MAX`), Floor-Spread-Crash gefixt
(`structures.place` mit `ON CONFLICT (x,y,layer) DO NOTHING`), Move-Reject-Snap-Back.

**Block D — Cross-World (`npc_worker.py`, `services/player_state.py`, `needs.py`):**
world-scoped Aggro (Dungeon-Mobs greifen keine Overworld-Spieler mehr an),
Disaster (Giftnebel/Blitz/Dürre) verschonen Dungeon-Spieler, Downed+Bett-Heal-
Soft-Lock weg (`heal_player` no-op bei downed, `_enter_downed_state` beendet Resting).

---

## 🟢 Welle 53b (2026-06-06, nachgereicht — alles live)

- **Dungeon-Mob-Kollision gefixt:** `dungeon_instance` cached Floor-Tiles synchron
  (`cached_floor_tiles`), `npc_worker._can_walk(…, npc)` routet Dungeon-NPCs gegen
  die Dungeon-Floor-Geometrie statt Overworld. Mobs ohne geladenen Floor bleiben stehen.
- **Multi-Tile-Gebäude-Kollision Frontend gefixt:** `Structure`-Modell um
  `width/height` (Backend liefert sie), `isTileWalkable` iteriert den ganzen
  Footprint → kein Hineinlaufen in Ställe/Gilden/Tempel mehr.
- **Warenwert-Balancing:** Münz-DROPS geben jetzt randomisierte Kupfer-Beträge in
  Item-Markt-Größe (`currency.coin_drop_copper`: copper 3-12, silver 20-70, gold
  150-450) statt voller Nennwerte (gold_coin war 10.000). Quest-Gold ×10 statt ×100.
- **Defend/Escort echt implementiert:** neuer `quest_worker.py` (Tick 3s) — defend =
  Stellung `duration_s` im Radius halten (verlassen → Timer reset), escort = folgenden
  merchant-Schützling `distance_min` Tiles begleiten (Spawn bei Annahme, nur der
  quest_worker führt ihn via `ESCORT_NPCS`-Skip im Wander-Loop, fail wenn verloren).
  `UNSUPPORTED_QUEST_TYPES` wieder leer → beide werden angeboten.

## 🟢 Welle 53c (2026-06-06, Test-Feedback — live + gepusht, Commit 1ba2b19)

- Schwarzer Bildschirm beim Sterben: `do_respawn` (services/player_state.py)
  streamt jetzt Chunks um die Respawn-Position.
- Dauer-Blitz in der Welt: `disaster-overlay.ts` spielte repeat:-1-Anim →
  jetzt `repeat:0` + delayedCall-Cleanup.
- Tooltip blieb nach Inventar-Schließen: `tooltip.hide()` in i/Esc/close.
- Ringe/Amulette: `JEWELRY_STATS` in `attributes.calculate_attributes` verdrahtet
  + Jewelry-Zweig im item-tooltip.
- Zauberbücher: `handle_use_item` delegiert magic-Items an `handle_learn_spell`.
- Talent-UI nutzt jetzt Backend-`status` (skill_min-Gate), zeigt „Braucht Skill-Stufe X".
- Handels-Sortierung (Kategorie/Name/Preis), Crafting-Stats-Vorschau.
- Tier-Nutzinteraktion `tend_animal` (melken/scheren/Eier + 5min-Cooldown,
  Haustiere Flavor) — ws/dialog.py + world-scene isAnimalNpc.

## 🟢 Fähigkeiten-/Zaubersystem (Magier/Heiler) — Welle 53d/53e, live
Aufgebaut auf dem vorhandenen Gerüst (spell_caster, Schulen healer/mage,
learned_spells, Spellbook P-Taste, Cast-Bar, Target-Overlay):
- **Spell-Skalierung** (spells.apply_spell_effects): Schaden+Heilung ×(1+4%/Magie-
  Level) statt flat → Caster wachsen.
- **Stab-Kanalisierung** (ws/combat.py handle_cast_spell): Zaubern erfordert
  ausgerüsteten Stab/Wand (item_stats class 'magic'). Stäbe im Händler-Pool.
- **Weiches Klassensystem** (ws/character.py Startkit): Preset = Klasse + Startkit.
  ember_mage→Stab+magic_missile, wanderer_cloak→Stab+lesser_heal, wild_ranger→Bogen,
  knife_runner→Dolch, shieldbearer→Schwert+Schild, iron_delver→Schwert+Spitzhacke.
  Startwaffe direkt ausgerüstet. Wachstum weiter über Skills (kein Hard-Lock).
- Schaden unterbricht Cast war bereits verdrahtet (player_state:293).

**Noch offen (Politur):** Hotbar-Casting (Spells aus Hotbar-Slots wirken +
Zuweisung Spellbook→Hotbar; aktuell castet man über das Spellbook/P). Doppel-
SPELLS-Struktur (spells.py-IDs vs combat.py-Item-Kinds) langfristig vereinheitlichen.
Spell-Skalierung auch an Intelligenz koppeln (aktuell nur Magie-Skill).

## 🟢 Respawn-Loop-Fix (Welle 53d): do_respawn füllt jetzt ALLE Vitalwerte
(hp/mana/hunger/thirst/stamina), nicht nur HP — sonst respawnte man in den
Verhungerungstod → 30s-Loop. + 3s Spawn-Unverwundbarkeit, Downed/Respawn-Logging.

## 🔴 OFFEN / bewusst aufgeschoben

1. **NPC-Move-Broadcast Proximity-Filter** + Move-Persistenz batchen (Perf —
   durch reduzierte Population aktuell unkritisch).
2. **Truhen-Münzen** geben weiterhin vollen Nennwert (gold_coin=10.000) — bewusst
   als seltener Schatz belassen; bei Bedarf analog zu Loot skalieren.
3. **Tod-Strafe** (weiterhin keine — Memory `project_liege_death_penalty`).
4. **Escort-Politur:** Schützling kann aktuell nicht von Mobs getötet werden (Mobs
   aggroen nur Spieler) → fail-on-death greift nur bei Despawn. Optionale Vertiefung.

---

## 🌍 World-Reset 2026-06-06 (neuer Seed)

- **Neuer Seed `WORLD_SEED=20260606`** in `docker-compose.yml` (backend env).
  Alte Welt war Seed `20260530`.
- Gewipt: `npcs`, `npc_memory_episode`, `npc_chatter_cache`, `structures` (548 NPC,
  38.686 Strukturen), `dungeons`/`dungeon_floors`, Ground-/Chest-Items,
  `region_difficulty`/`region_history`. `players SET world_id='overworld'`.
- **Erhalten:** Accounts, Charaktere, Inventar, Skills, Talente, Wallet, Fraktionen.
  Charakter-Position wird beim Login via `find_spawn` auf ein gültiges Tile gesetzt
  (`load_or_create_player` validiert Walkability) → niemand strandet im Wasser.
- **Spielerbauten gingen mit weg** (neuer Seed = neues Terrain, alte Coords sinnlos).
- **DB-Backup vor dem Reset:** `/srv/storage/projects/liege/backups/pre-newseed-20260606-115518.sql.gz`

**Rollback auf die alte Welt:** WORLD_SEED-Zeile in compose entfernen →
`gunzip -c backups/pre-newseed-*.sql.gz | docker compose exec -T postgres psql -U liege -d liege`
→ `docker compose up -d backend`. Code-Rollback: `git stash` (verwirft Welle 52+53)
+ rebuild.

---

## 🟢 Betrieb

```bash
cd /srv/storage/projects/liege
docker compose ps                 # backend + postgres
docker compose logs -f backend
```

- **Nach Code-Änderung:** `docker compose build backend && docker compose up -d backend`
  (Multi-Stage-Dockerfile baut Angular im Image). Bei Frontend-Änderung im Browser
  **Hard-Reload** (Strg+Shift+R) wegen PWA-`ngsw`-Cache.
- ⚠️ **DB-Schema-Falle:** `db.py` splittet SCHEMA an `;` — keine Semikolons in
  SQL-Kommentaren.
- **Compile-Checks vor Deploy:** `python3 -m py_compile <files>` + im frontend
  `node_modules/.bin/tsc --noEmit -p tsconfig.app.json`.

---

## 🛠 Workflow-Erinnerungen (Memory)

- `feedback_liege_rebuild` — nach Code-Änderung sofort build + up.
- `feedback_liege_design_philosophy` — lebensecht + fordernd, NICHT weichspülen
  (Welle 53 ist Kohärenz, kein Weichspülen).
- `feedback_server_step_by_step` — System-/DB-Eingriffe vorher abstimmen.
- Auto-Memory unter `~/.claude/projects/-home-server3070/memory/`.
