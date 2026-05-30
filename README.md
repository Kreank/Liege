# Liege

Persistente 2D-Multiplayer-Fantasy-Welt im Zelda/Terraria/RimWorld-Stil mit
KI-getriebenen NPCs, Welt-Events, KI-Quest-Generierung, Survival/Crafting,
Multi-Floor-Dungeons und Geldbeutel-Wirtschaft.

**Stand: 2026-05-30 (Welle 34b).** Live unter https://liege.tech-artist.de

## Stack

- **Backend**: Python 3.12 + FastAPI + WebSockets + asyncpg
- **DB**: PostgreSQL 16
- **Frontend**: HTML + Phaser 3.60 (Canvas/WebGL), WS-Endpoint `/ws`
- **LLM**: Ollama lokal (`qwen3.5:0.8b` Fast-Brain auf GPU, `qwen3.5:9b`
  Slow-Brain auf CPU)
- **Deployment**: Docker Compose (Services `backend` + `postgres`), Caddy + TLS

## Quick-Start

```bash
git clone https://github.com/Kreank/Liege.git
cd Liege

# Ollama-Modelle ziehen (auf Host) — siehe docu/ollama_pull_list.md
ollama pull qwen3.5:0.8b
ollama pull qwen3.5:9b

# Stack starten
docker compose up -d --build

# Im Browser
open http://localhost:8000
```

Nach Code-Änderungen am Backend: `docker compose build backend && docker compose up -d backend`.
Bei Frontend-Änderungen zusätzlich den Service-Worker (`frontend/sw.js`, `CACHE_NAME`) bumpen.

## Features

### Core Gameplay
- Chunked Welt mit Multi-Layer-Noise (32×32-Chunks, lazy-generated)
- 10 Biome (Water, Sand, Grass, Forest, Mountain, Desert, Jungle, Lava, Snow, Swamp)
- Pixel-basierte Bewegung mit per-Achsen-Collision
- Tag/Nacht-Zyklus (1 Spieltag = 48 Echtminuten) + 5-Phasen-Wetter (clear/rain/snow/fog/swamp_mist)
- Hotbar + Slot-Inventar mit Stacking

### Survival & Bedürfnisse
- Hunger + Durst (Tick alle 30s, Schaden bei 0)
- **Stamina/Schlaf/Sprint** (`needs.py`): Sprint per Shift (8 Stamina/s),
  Bauen kostet Ausdauer bei niedriger Versorgung, Bett-Schlaf regeneriert
  Stamina + HP

### Skill-/Talent-/Forschung
- **11 Skills** (Bergbau/Holzfällen/Sammeln/Bauen/Handwerk/Kampf/Magie/Kochen/
  Heilkunde/Landwirtschaft/Sozial), Level 0–20, non-linear XP
- **46 Talente** in Tier-Bäumen — 1 Talent-Punkt pro Skill-Levelup
- **12 abgeleitete Attribute** (Stärke/Ausdauer/Energie/Intelligenz/…) aus
  Skills + Equipment + Talenten
- **70 Research-Nodes** in 5 Tech-Ages × 8 Branches (Punkte aus Skill-Levelups)

### Crafting & Wirtschaft
- **4 Crafting-Stationen** (hand/workbench/furnace/anvil) + Bills/Queue,
  Produktionsketten (Erz → Barren → Equipment etc.)
- **172 Item-Kinds**, 5 Quality-Stufen (roh → legendär) + Affix-System
- **Geldbeutel-Währung** (`currency.py`): Kupfer/Silber/Gold (100 K = 1 S,
  100 S = 1 G), intern `wallet_copper`. Geld aus Mobs/Boden/Quests/Truhen/Händler
  fließt direkt in den Beutel — Münzen sind keine Inventar-Items mehr.
- Händler mit Social-Skill-Rabatt + Talent-Boni (`trade.py`)

### Combat & Monster
- 17 Waffen mit echten Stats, 5 Rüstungs-Slots + Schmuck, Body-Parts,
  Status-Effekte (burning/poisoned/blessed/…)
- **~150 Monster** (handkodiert + **133-Monster-Longlist** daten-getrieben aus
  Manifest, `monster_longlist.py`): Tier 1–5, Spawn nach Biome, tier-skalierter Loot
- **Bestiarium** (📖): Monster-Kompendium mit Portrait/Tier/Biome/Mechanik
- **10 Spells** in 2 Schulen (Heiler/Magier), Mana-basiert, Magic-Level-Gates

### Dungeons
- Multi-Floor-Instanzen mit **5-Tier-System** (klein → Großraid),
  unterschiedliche Lifetime (Stunden bis Tage), **Reaper** räumt abgelaufene
  Instanzen, Auto-Spawn pro Floor, tier-skalierte Loot-Qualität
- Key-Items (`dungeon_map`/`rift_lore`/`kings_seal`) öffnen höhere Tiers

### Gruppen & Raids
- Party (5) / Raid20 / Raid40, Rollen (leader/assist/member), Sub-Partys
- Loot-Regeln **ffa** oder **need_greed** (Roll-System), XP-Share,
  manueller Raid-Trigger (`/raidstart`)

### NPCs & KI
- LLM-Identitäten (Backstory/Persönlichkeit) via Ollama; Fast-Brain für Dialoge,
  Slow-Brain für Quests/Events
- **Storyteller-Director** wählt Events deterministisch, LLM macht nur Narrative
- **KI-Quest-Generator** (Narrative per LLM, Mechanik server-deterministisch)
- Siedlungen (Lager/Dorf/Stadt/Kapital) mit 4 Gilden (Magier/Kämpfer/Heiler/Diebe)
  + Tempel, Faction-/Reputations-System

## Hotkeys

| Taste | Funktion |
|---|---|
| WASD / Pfeile | Bewegen |
| Shift | Sprinten (Ausdauer) |
| 1-9 / 0 | Hotbar-Slot bzw. Struktur im Bau-Modus |
| I | Inventar |
| K | Skills |
| T | Talente |
| R | Forschung (bzw. Rotation im Bau-Modus) |
| Q | Quests |
| C | Charakter (Attribute) |
| F | Faktionen |
| P | Zauberbuch |
| B | Bau-Modus |
| M | Material wechseln (im Bau-Modus) |
| ESC | Modal/Menü schließen |

Bestiarium + weitere Panels zusätzlich über die Aktionsleisten-Buttons (📖 etc.).

## Architektur

```
liege/
├── backend/                    # FastAPI + Worker
│   ├── main.py                 # WebSocket-Handler, Init, Lifespan
│   ├── world.py                # Chunked World, Noise
│   ├── llm.py                  # Ollama-Client (Fast/Slow-Brain)
│   ├── skills.py / talents.py / attributes.py / research.py
│   ├── needs.py                # Hunger/Durst/Stamina/Schlaf/Sprint
│   ├── items.py / recipes.py / trade.py / currency.py
│   ├── combat.py / monster_longlist.py / loot.py / spells.py
│   ├── dungeon_*.py            # Multi-Floor-Tier-Dungeons + Reaper
│   ├── groups.py / raid_director.py
│   ├── quests.py / quest_generator.py / storyteller.py / event_worker.py
│   ├── village_spawner.py / structures.py / world_populator.py
│   └── ...
├── frontend/
│   ├── index.html              # Phaser-Game + UI
│   ├── app.js                  # Game-Client (Rendering, WS, UI)
│   └── sw.js                   # Service-Worker (Cache-Versionierung)
├── assets/                     # Sprites
└── docu/                       # Design-Dokumente (siehe docu/ASSETS.md, WORLD_DESIGN.md …)
```

## Dokumentation

- `docu/ASSETS.md` — Asset-Status, Stil-Vorgaben, offene Lücken
- `docu/WORLD_DESIGN.md` — Welt-Generierung, Wirtschaft, Dungeons, NPC-Identität
- `docu/RIMWORLD_MAPPING.md` — welche RimWorld-Mechaniken übernommen sind
- `docu/BACKLOG.md` — Wellen-Historie + Architektur-Überblick
- `docu/VILLAGE_LAYOUT_SPEC.md` — Siedlungs-Spawn-Spezifikation
- `docu/TEST_GUIDE.md` — manuelle Smoke-Tests
- `docu/ollama_pull_list.md` — LLM-Modelle + Hardware-Routing

## Lizenz

Privates Projekt — Quellcode öffentlich für Lerneffekt + Transparenz.
