import json
import os
import asyncpg

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://liege:liege@localhost:5432/liege"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS worlds (
    seed         INTEGER PRIMARY KEY,
    width        INTEGER NOT NULL,
    height       INTEGER NOT NULL,
    tiles        JSONB   NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS world_chunks (
    world_seed   INTEGER NOT NULL,
    chunk_x      INTEGER NOT NULL,
    chunk_y      INTEGER NOT NULL,
    tiles        JSONB NOT NULL,
    populated    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (world_seed, chunk_x, chunk_y)
);
ALTER TABLE world_chunks ADD COLUMN IF NOT EXISTS populated BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS world_chunks_coords_idx
    ON world_chunks (world_seed, chunk_x, chunk_y);

CREATE TABLE IF NOT EXISTS players (
    name         TEXT PRIMARY KEY,
    x            INTEGER NOT NULL,
    y            INTEGER NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS structures (
    id           BIGSERIAL PRIMARY KEY,
    x            INTEGER NOT NULL,
    y            INTEGER NOT NULL,
    type         TEXT    NOT NULL,
    owner        TEXT    NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (x, y)
);

ALTER TABLE structures ADD COLUMN IF NOT EXISTS material   TEXT    NOT NULL DEFAULT 'stone';
ALTER TABLE structures ADD COLUMN IF NOT EXISTS durability INTEGER NOT NULL DEFAULT 1;

-- Combat-Felder
ALTER TABLE players ADD COLUMN IF NOT EXISTS hp       INTEGER NOT NULL DEFAULT 100;
ALTER TABLE players ADD COLUMN IF NOT EXISTS max_hp   INTEGER NOT NULL DEFAULT 100;
ALTER TABLE players ADD COLUMN IF NOT EXISTS mana     INTEGER NOT NULL DEFAULT 50;
ALTER TABLE players ADD COLUMN IF NOT EXISTS max_mana INTEGER NOT NULL DEFAULT 50;
ALTER TABLE npcs    ADD COLUMN IF NOT EXISTS hp       INTEGER NOT NULL DEFAULT 50;
ALTER TABLE npcs    ADD COLUMN IF NOT EXISTS max_hp   INTEGER NOT NULL DEFAULT 50;

-- RimWorld-inspirierte Felder
ALTER TABLE players ADD COLUMN IF NOT EXISTS hunger     INTEGER NOT NULL DEFAULT 100;
ALTER TABLE players ADD COLUMN IF NOT EXISTS max_hunger INTEGER NOT NULL DEFAULT 100;
ALTER TABLE players ADD COLUMN IF NOT EXISTS stamina    INTEGER NOT NULL DEFAULT 100;
ALTER TABLE players ADD COLUMN IF NOT EXISTS max_stamina INTEGER NOT NULL DEFAULT 100;
ALTER TABLE items ADD COLUMN IF NOT EXISTS quality TEXT NOT NULL DEFAULT 'normal';
-- Welle 36: Item-Stacking — quantity-Spalte
ALTER TABLE items ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS player_skills (
    player_name TEXT NOT NULL,
    skill       TEXT NOT NULL,
    xp          INTEGER NOT NULL DEFAULT 0,
    level       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_name, skill)
);

-- Body-Parts-Health (RimWorld-inspiriert)
ALTER TABLE players ADD COLUMN IF NOT EXISTS legs_health  INTEGER NOT NULL DEFAULT 100;
ALTER TABLE players ADD COLUMN IF NOT EXISTS arms_health  INTEGER NOT NULL DEFAULT 100;
ALTER TABLE players ADD COLUMN IF NOT EXISTS torso_health INTEGER NOT NULL DEFAULT 100;

-- Research-Progression
CREATE TABLE IF NOT EXISTS research_progress (
    player_name TEXT NOT NULL,
    node_id     TEXT NOT NULL,
    points      INTEGER NOT NULL DEFAULT 0,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (player_name, node_id)
);

-- Crafting-Bills-Queue
CREATE TABLE IF NOT EXISTS bills (
    id           BIGSERIAL PRIMARY KEY,
    player_name  TEXT NOT NULL,
    station_type TEXT NOT NULL,
    recipe_id    TEXT NOT NULL,
    target_count INTEGER NOT NULL,
    completed    INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS bills_player_idx ON bills (player_name, status);

-- NPC-Mood
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS mood_value    INTEGER NOT NULL DEFAULT 50;
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS mental_state  TEXT NOT NULL DEFAULT 'normal';
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMPTZ NULL;

CREATE TABLE IF NOT EXISTS events (
    id           BIGSERIAL PRIMARY KEY,
    kind         TEXT    NOT NULL,
    title        TEXT    NOT NULL,
    body         TEXT    NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS events_created_at_idx ON events (created_at DESC);

CREATE TABLE IF NOT EXISTS npcs (
    id           BIGSERIAL PRIMARY KEY,
    name         TEXT    NOT NULL,
    kind         TEXT    NOT NULL,
    x            INTEGER NOT NULL,
    y            INTEGER NOT NULL,
    backstory    TEXT    NOT NULL,
    mood         TEXT    NOT NULL DEFAULT 'neutral',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_moved   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS talks (
    id           BIGSERIAL PRIMARY KEY,
    npc_id       BIGINT NOT NULL REFERENCES npcs(id) ON DELETE CASCADE,
    player_name  TEXT   NOT NULL,
    role         TEXT   NOT NULL,
    text         TEXT   NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS talks_npc_player_idx ON talks (npc_id, player_name, created_at);

CREATE TABLE IF NOT EXISTS items (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    x             INTEGER,
    y             INTEGER,
    owner         TEXT,
    equipped_slot TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT items_location_xor CHECK (
        (x IS NOT NULL AND y IS NOT NULL AND owner IS NULL)
        OR
        (owner IS NOT NULL AND x IS NULL AND y IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS items_ground_idx ON items (x, y) WHERE owner IS NULL;
CREATE INDEX IF NOT EXISTS items_owner_idx ON items (owner) WHERE owner IS NOT NULL;

CREATE TABLE IF NOT EXISTS plantings (
    structure_id BIGINT PRIMARY KEY REFERENCES structures(id) ON DELETE CASCADE,
    plant_kind   TEXT NOT NULL,
    planted_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Issue: gelernte Zauber
CREATE TABLE IF NOT EXISTS learned_spells (
    player_name  TEXT NOT NULL,
    spell_kind   TEXT NOT NULL,
    learned_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_name, spell_kind)
);

-- Welle 27: Faction-System
CREATE TABLE IF NOT EXISTS factions (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL,
    color         TEXT NOT NULL,
    natural_min   INTEGER NOT NULL DEFAULT -100,
    natural_max   INTEGER NOT NULL DEFAULT  100,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS faction_relations (
    faction_a_id   TEXT NOT NULL,
    faction_b_id   TEXT NOT NULL,
    goodwill       INTEGER NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (faction_a_id, faction_b_id),
    CHECK (faction_a_id < faction_b_id)
);
CREATE TABLE IF NOT EXISTS player_faction_reputation (
    player_name    TEXT NOT NULL,
    faction_id     TEXT NOT NULL,
    goodwill       INTEGER NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_name, faction_id)
);
CREATE TABLE IF NOT EXISTS reputation_events (
    id            BIGSERIAL PRIMARY KEY,
    player_name   TEXT NOT NULL,
    faction_id    TEXT NOT NULL,
    delta         INTEGER NOT NULL,
    reason        TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS reputation_events_player_idx
    ON reputation_events (player_name, created_at DESC);
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS faction_id TEXT NULL;
-- Welle 31: NPC-Tagesabläufe (home position)
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS home_x INTEGER NULL;
ALTER TABLE npcs ADD COLUMN IF NOT EXISTS home_y INTEGER NULL;

-- Welle 25: NPC Long-Term-Memory
CREATE TABLE IF NOT EXISTS npc_memory_episode (
    id           BIGSERIAL PRIMARY KEY,
    npc_id       BIGINT NOT NULL,
    player_name  TEXT NULL,
    content      TEXT NOT NULL,
    embedding    JSONB NOT NULL,
    importance   SMALLINT NOT NULL DEFAULT 5,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_access  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS npc_memory_lookup_idx
    ON npc_memory_episode (npc_id, player_name, created_at DESC);

-- Welle 24: Semantic-Cache
CREATE TABLE IF NOT EXISTS llm_cache (
    id            BIGSERIAL PRIMARY KEY,
    scope_key     TEXT NOT NULL,
    prompt_kind   TEXT NOT NULL,
    prompt_hash   TEXT NOT NULL,
    prompt_text   TEXT NOT NULL,
    embedding     JSONB NOT NULL,
    response      JSONB NOT NULL,
    model_name    TEXT NOT NULL,
    hit_count     INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS llm_cache_scope_idx
    ON llm_cache (scope_key, prompt_kind);
CREATE INDEX IF NOT EXISTS llm_cache_hash_idx
    ON llm_cache (prompt_hash);

-- Welle 23: Welt-Historie pro Region
CREATE TABLE IF NOT EXISTS region_history (
    world_seed   INTEGER NOT NULL,
    region_x     INTEGER NOT NULL,
    region_y     INTEGER NOT NULL,
    history      JSONB NOT NULL,
    region_name  TEXT NULL,
    theme        TEXT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (world_seed, region_x, region_y)
);

-- Welle 19: Affix-System für Items
ALTER TABLE items ADD COLUMN IF NOT EXISTS affixes JSONB NULL;
ALTER TABLE items ADD COLUMN IF NOT EXISTS unique_name TEXT NULL;
ALTER TABLE items ADD COLUMN IF NOT EXISTS flavor TEXT NULL;

-- Welle 18: Talent-Baum
CREATE TABLE IF NOT EXISTS player_talents (
    player_name  TEXT NOT NULL,
    talent_id    TEXT NOT NULL,
    rank         INTEGER NOT NULL DEFAULT 1,
    learned_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_name, talent_id)
);
ALTER TABLE players ADD COLUMN IF NOT EXISTS talent_points INTEGER NOT NULL DEFAULT 0;

-- Welle 11: Status-Effekte
CREATE TABLE IF NOT EXISTS status_effects (
    id            BIGSERIAL PRIMARY KEY,
    target_type   TEXT NOT NULL,
    target_id     TEXT NOT NULL,
    effect        TEXT NOT NULL,
    magnitude     INTEGER NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS status_effects_target_idx
    ON status_effects (target_type, target_id, expires_at);

-- Welle 10: Quests
CREATE TABLE IF NOT EXISTS quests (
    id            BIGSERIAL PRIMARY KEY,
    player_name   TEXT NOT NULL,
    giver_npc_id  BIGINT NULL,
    target_npc_id BIGINT NULL,
    quest_type    TEXT NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL,
    objective     JSONB NOT NULL,
    progress      JSONB NOT NULL DEFAULT '{}',
    reward        JSONB NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS quests_player_status_idx ON quests (player_name, status);

-- Welle 9: Echte Dungeons (eigene Welt pro Instanz)
CREATE TABLE IF NOT EXISTS dungeons (
    id           BIGSERIAL PRIMARY KEY,
    seed         INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    size         INTEGER NOT NULL,
    tiles        JSONB   NOT NULL,
    spawn_x      INTEGER NOT NULL,
    spawn_y      INTEGER NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE players ADD COLUMN IF NOT EXISTS world_id   TEXT NOT NULL DEFAULT 'overworld';
ALTER TABLE players ADD COLUMN IF NOT EXISTS overworld_x INTEGER NULL;
ALTER TABLE players ADD COLUMN IF NOT EXISTS overworld_y INTEGER NULL;
"""

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_db() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=1, max_size=10, init=_init_conn
    )
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)
    return _pool


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_db() first")
    return _pool
