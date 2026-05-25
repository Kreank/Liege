"""Quest-System — KI-generierte und template-basierte Aufträge.

Spieler bekommen Quests von NPCs. Templates abstrahieren das Belohnungssystem;
Slow-Brain kann später passende Quest-Narrative erzeugen.

Quest-Typen:
    fetch   — bring N×<item_kind> zurück
    kill    — töte N×<creature_kind>
    deliver — bring Item zu anderem NPC

Status: open → active → completed (collected reward) → closed.
"""
import json
import logging
import random

import db

log = logging.getLogger("liege.quests")


SCHEMA = """
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
"""


# Templates — Default-Bibliothek
QUEST_TEMPLATES = [
    {
        "type": "fetch", "item_kind": "wood", "count": 10,
        "title_de": "Holz für die Schmiede",
        "description_de": "Bringe mir 10 Stück Holz, ich brauche es für meine Werkstatt.",
        "reward": {"gold_ore": 5, "xp": 30},
    },
    {
        "type": "fetch", "item_kind": "iron_ore", "count": 5,
        "title_de": "Eisen aus den Bergen",
        "description_de": "Bringe mir 5 Eisenerze. Die Mine ist gefährlich, sei vorsichtig.",
        "reward": {"gold_ore": 10, "xp": 50},
    },
    {
        "type": "fetch", "item_kind": "herb", "count": 8,
        "title_de": "Heilkräuter",
        "description_de": "Ich brauche 8 Heilkräuter für meinen Heiltrank.",
        "reward": {"health_potion": 2, "xp": 25},
    },
    {
        "type": "fetch", "item_kind": "bone", "count": 6,
        "title_de": "Reste der Toten",
        "description_de": "Suche mir 6 Knochen — für rituelle Zwecke, sei nicht zu neugierig.",
        "reward": {"gold_ore": 6, "xp": 35},
    },
    {
        "type": "kill", "creature_kind": "wolf", "count": 3,
        "title_de": "Wölfe vertreiben",
        "description_de": "Die Wölfe machen unser Vieh nervös. Erlege 3 Wölfe.",
        "reward": {"leather": 3, "gold_ore": 8, "xp": 60},
    },
    {
        "type": "kill", "creature_kind": "goblin", "count": 4,
        "title_de": "Goblins unter Kontrolle",
        "description_de": "Erlege 4 Goblins, sie werden zu zahlreich.",
        "reward": {"gold_ore": 12, "xp": 70},
    },
    {
        "type": "kill", "creature_kind": "bandit", "count": 2,
        "title_de": "Räuber im Wald",
        "description_de": "Vertreibe 2 Banditen aus unseren Wäldern.",
        "reward": {"gold_ore": 20, "sword": 1, "xp": 80},
    },
]


# — DB-Layer ——————————————————————————————————————————————————————————————————

def _row_to_dict(row) -> dict:
    return {
        "id":             row["id"],
        "player_name":    row["player_name"],
        "giver_npc_id":   row["giver_npc_id"],
        "target_npc_id":  row["target_npc_id"],
        "quest_type":     row["quest_type"],
        "title":          row["title"],
        "description":    row["description"],
        "objective":      row["objective"],
        "progress":       row["progress"],
        "reward":         row["reward"],
        "status":         row["status"],
        "created_at":     row["created_at"].isoformat(),
    }


async def list_for_player(player_name: str,
                           status_filter: tuple[str, ...] = ("active", "completed")) -> list[dict]:
    rows = await db.pool().fetch(
        "SELECT id, player_name, giver_npc_id, target_npc_id, quest_type, "
        "title, description, objective, progress, reward, status, created_at "
        "FROM quests WHERE player_name = $1 AND status = ANY($2::text[]) "
        "ORDER BY id",
        player_name, list(status_filter),
    )
    return [_row_to_dict(r) for r in rows]


async def create_from_template(player_name: str, giver_npc_id: int | None,
                                template: dict | None = None) -> dict:
    """Erzeugt eine neue Quest aus Template. Wenn None: random."""
    tmpl = template if template is not None else random.choice(QUEST_TEMPLATES)
    if tmpl["type"] == "fetch":
        objective = {"item_kind": tmpl["item_kind"], "count": tmpl["count"]}
        progress = {"collected": 0}
    elif tmpl["type"] == "kill":
        objective = {"creature_kind": tmpl["creature_kind"], "count": tmpl["count"]}
        progress = {"killed": 0}
    else:
        objective = {}
        progress = {}
    row = await db.pool().fetchrow(
        "INSERT INTO quests (player_name, giver_npc_id, quest_type, title, "
        "description, objective, progress, reward) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
        "RETURNING id, player_name, giver_npc_id, target_npc_id, quest_type, "
        "title, description, objective, progress, reward, status, created_at",
        player_name, giver_npc_id, tmpl["type"], tmpl["title_de"],
        tmpl["description_de"], json.dumps(objective), json.dumps(progress),
        json.dumps(tmpl["reward"]),
    )
    return _row_to_dict(row)


async def mark_completed(quest_id: int) -> None:
    await db.pool().execute(
        "UPDATE quests SET status = 'completed' WHERE id = $1", quest_id,
    )


async def mark_closed(quest_id: int) -> None:
    await db.pool().execute(
        "UPDATE quests SET status = 'closed' WHERE id = $1", quest_id,
    )


# — Progress-Hooks (vom Game-Code aufgerufen) ——————————————————————————————————

async def on_item_collected(player_name: str, item_kind: str, count: int = 1) -> list[dict]:
    """Spieler hat item_kind erhalten — alle aktiven fetch-Quests prüfen.
    Returns Liste der Quests die durch diesen Hit weitergekommen sind."""
    quests = await list_for_player(player_name, status_filter=("active",))
    updated: list[dict] = []
    for q in quests:
        if q["quest_type"] != "fetch":
            continue
        if q["objective"].get("item_kind") != item_kind:
            continue
        collected = q["progress"].get("collected", 0) + count
        target = q["objective"].get("count", 1)
        if collected >= target:
            collected = target
        new_progress = {"collected": collected}
        new_status = "completed" if collected >= target else "active"
        await db.pool().execute(
            "UPDATE quests SET progress = $2, status = $3 WHERE id = $1",
            q["id"], json.dumps(new_progress), new_status,
        )
        q["progress"] = new_progress
        q["status"] = new_status
        updated.append(q)
    return updated


async def on_creature_killed(player_name: str, creature_kind: str, count: int = 1) -> list[dict]:
    quests = await list_for_player(player_name, status_filter=("active",))
    updated: list[dict] = []
    for q in quests:
        if q["quest_type"] != "kill":
            continue
        if q["objective"].get("creature_kind") != creature_kind:
            continue
        killed = q["progress"].get("killed", 0) + count
        target = q["objective"].get("count", 1)
        if killed >= target:
            killed = target
        new_progress = {"killed": killed}
        new_status = "completed" if killed >= target else "active"
        await db.pool().execute(
            "UPDATE quests SET progress = $2, status = $3 WHERE id = $1",
            q["id"], json.dumps(new_progress), new_status,
        )
        q["progress"] = new_progress
        q["status"] = new_status
        updated.append(q)
    return updated
