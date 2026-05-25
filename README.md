# Liege

Persistent 2D-Multiplayer-Fantasy-Welt im Zelda/Terraria/RimWorld-Stil mit KI-getriebenen NPCs, Welt-Events, Quest-Generierung und Item-Naming.

## Stack

- **Backend**: Python 3.12 + FastAPI + WebSockets + asyncpg
- **DB**: PostgreSQL 16
- **Frontend**: HTML + Phaser 3.60 (Canvas/WebGL)
- **LLM**: Ollama lokal (`qwen3.5:0.8b` Fast-Brain auf GPU, `qwen3.5:9b` Slow-Brain auf CPU, `nomic-embed-text` für Semantic-Cache)

## Quick-Start

```bash
git clone https://github.com/Kreank/Liege.git
cd Liege

# Ollama-Modelle ziehen (auf Host)
ollama pull qwen3.5:0.8b
ollama pull qwen3.5:9b
ollama pull nomic-embed-text

# Stack starten
docker compose up -d --build

# Im Browser
open http://localhost:8000
```

## Features (Wellen 1-31 + 9b)

### Core Gameplay
- Chunked Welt mit Multi-Layer-Noise (32×32-Chunks, lazy-generated)
- 8 Biome (Grass, Forest, Mountain, Desert, Jungle, Snow, Swamp, Lava)
- Pixel-basierte Bewegung mit per-Achsen-Collision
- Hotbar (1-9) + Slot-Inventar mit Stacking (max 500/150/25 pro Kategorie)

### Skill-/Talent-System
- 11 Skills (Bergbau/Holzfällen/Sammeln/Bauen/Handwerk/Kampf/Magie/Kochen/Heilkunde/Landwirtschaft/Sozial)
- ~55 Talente in 3 Tiers — 1 Talent-Punkt pro Skill-Levelup
- 12 derived Attribute (Stärke/Ausdauer/Energie/Intelligenz/...) aus Skills + Equipment + Talenten

### Combat
- 12 Waffen mit echten Stats (Damage/Speed/Crit/Range/Two-Handed)
- 4 Rüstungs-Slots + Schmuck mit Affixes
- 5 Quality-Stufen (grob → legendär) + Affix-System (Prefix/Suffix-Pools)
- Body-Parts (Legs/Arms/Torso) + Status-Effekte (burning/poisoned/blessed/...)

### NPCs & Welt
- 13 friendly NPC-Kinds + 14 Creature-Kinds (alle mit eigenen Sprites)
- 3 Siedlungstypen (Stadt/Dorf/Lager) mit varianten Häusern (Wohnhaus/Schmiede/Werkstatt/Laden/Schenke)
- Faction-System mit 8 Factions + Beziehungs-Propagation
- Tag/Nacht-Zyklus (12 Min real = 1 Spieltag), NPCs kehren nachts zu Home-Position

### KI-Features
- **Storyteller-Director** (Cassandra/Phoebe/Randy-Modi) wählt Events deterministisch, LLM macht nur Narrative
- **NPC-Long-Term-Memory** mit Embeddings (RAG, Importance-Scoring, Recency-Decay)
- **Semantic-Cache** für LLM-Outputs (50-80% Calls eingespart)
- **Welt-Historie** pro Region (Slow-Brain generiert Geschichte + Themes)
- **KI-Quest-Generator** mit Welt-Verifikator (Multi-Step-DAG-Stages möglich)
- **KI-Item-Namer** für legendary Items (Constrained JSON-Output)

### Dungeons
- Begehbare Dungeons (BSP-Layout, 5 Themes: Krypta/Mine/Tempel/Burgruine/Höhle)
- Welt-Switch via Treppe (persistente Dungeon-Instanzen)

## Hotkeys

| Taste | Funktion |
|---|---|
| WASD / Pfeile | Bewegen |
| 1-9 | Hotbar-Slot aktivieren |
| I | Inventar |
| K | Skills |
| T | Talente |
| R | Forschung |
| Q | Quests |
| C | Charakter (Attribute) |
| F | Faktionen |
| B | Bau-Modus |
| M | Material wechseln (im Bau-Modus) |

## Architektur

```
liege/
├── backend/           # FastAPI + Workers
│   ├── main.py        # WebSocket-Handler, Init, Lifespan
│   ├── world.py       # Chunked World, Noise
│   ├── llm.py         # Ollama-Client + JSON-Schema-Output
│   ├── skills.py / talents.py / attributes.py
│   ├── factions.py / quests.py / quest_stages.py
│   ├── npc_memory.py / llm_cache.py / region_history.py
│   ├── storyteller.py / dungeon_world.py / dungeon_themes.py
│   └── ...
├── frontend/
│   └── index.html     # Phaser-Game + UI
├── assets/            # Sprites
└── docu/              # Design-Dokumente
```

## Lizenz

Privates Projekt — Quellcode öffentlich für Lerneffekt + Transparenz.
