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
ALTER TABLE quests ADD COLUMN IF NOT EXISTS template_id TEXT NULL;
ALTER TABLE quests ADD COLUMN IF NOT EXISTS tier        INTEGER NULL;
CREATE INDEX IF NOT EXISTS quests_player_status_idx ON quests (player_name, status);

-- Welle 23-F: Faction-Reputation pro Player
CREATE TABLE IF NOT EXISTS player_faction_reputation (
    player_name TEXT NOT NULL,
    faction     TEXT NOT NULL,
    reputation  INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_name, faction)
);
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

def _maybe_parse(value):
    # Legacy-Daten in der DB sind teilweise doppelt JSON-encoded (json.dumps +
    # jsonb-codec encoder=json.dumps). Decoder liefert dann den JSON-String
    # statt eines dict. Hier defensiv nachparsen.
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _row_to_dict(row) -> dict:
    return {
        "id":             row["id"],
        "player_name":    row["player_name"],
        "giver_npc_id":   row["giver_npc_id"],
        "target_npc_id":  row["target_npc_id"],
        "quest_type":     row["quest_type"],
        "title":          row["title"],
        "description":    row["description"],
        "objective":      _maybe_parse(row["objective"]),
        "progress":       _maybe_parse(row["progress"]),
        "reward":         _maybe_parse(row["reward"]),
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


# ─── Welle 23 — Template-Library + Radiant + Faction-Reputation ──────────

async def offers_for_npc(npc: dict, player_name: str,
                          player_level: int = 0) -> list[dict]:
    """Welche Quests kann dieser NPC dem Spieler ANBIETEN?
    Filtert nach giver_kinds, player_level, und schließt Quests aus,
    die der Spieler bereits angenommen hat oder als completed/closed hat
    (gleicher template_id).
    """
    import quest_templates as qt
    candidates = qt.templates_for_npc_kind(npc["kind"], player_level)
    if not candidates:
        return []
    # Quests die Player schon hat
    rows = await db.pool().fetch(
        "SELECT template_id FROM quests "
        "WHERE player_name = $1 AND status IN ('active','completed','closed') "
        "  AND template_id IS NOT NULL",
        player_name,
    )
    taken = {r["template_id"] for r in rows}
    # Faction-Filter
    rep_cache: dict[str, int] = {}
    out = []
    for t in candidates:
        if t["id"] in taken:
            continue
        # Faction-Requirement?
        ok = True
        for fac, min_rep in (t.get("faction_req") or {}).items():
            if fac not in rep_cache:
                rep_cache[fac] = await get_reputation(player_name, fac)
            if rep_cache[fac] < min_rep:
                ok = False
                break
        if ok:
            out.append(t)
    return out


async def turnin_targets_for_npc(npc: dict, player_name: str) -> list[dict]:
    """Welche aktiven/completed Quests kann der Spieler bei diesem NPC abgeben?
    completed-Quests werden bei giver_npc_id ODER target_npc_id (bei deliver/
    talk) abgegeben.
    """
    rows = await db.pool().fetch(
        "SELECT id, player_name, giver_npc_id, target_npc_id, quest_type, "
        "title, description, objective, progress, reward, status, created_at, "
        "template_id, tier "
        "FROM quests WHERE player_name = $1 AND status = 'completed' "
        "ORDER BY id",
        player_name,
    )
    out = []
    for r in rows:
        q = _row_to_dict(r)
        q["template_id"] = r["template_id"]
        # Determine receiver
        if q["quest_type"] in ("deliver", "talk"):
            # receiver = target_npc_id (gleicher kind wie objective.to_kind)
            obj = q["objective"] or {}
            target_kind = obj.get("to_kind")
            if target_kind and npc["kind"] == target_kind:
                out.append(q)
        else:
            # Standard: giver-NPC
            if q["giver_npc_id"] == npc["id"]:
                out.append(q)
    return out


async def accept_template(player_name: str, template_id: str,
                            giver_npc_id: int | None) -> dict | None:
    """Spieler nimmt eine Template-Quest an. Returns die neue Quest oder None
    wenn template nicht existiert / schon angenommen."""
    import quest_templates as qt
    tmpl = qt.template_by_id(template_id)
    if tmpl is None:
        return None
    # Doppelt-Annahme-Schutz
    existing = await db.pool().fetchval(
        "SELECT id FROM quests WHERE player_name = $1 AND template_id = $2 "
        "AND status IN ('active','completed')",
        player_name, template_id,
    )
    if existing:
        return None
    objective = dict(tmpl["objective"])
    progress = _initial_progress(tmpl["type"])
    title = tmpl["title_template"].format(**objective)
    desc  = tmpl["desc_template"].format(**objective)
    row = await db.pool().fetchrow(
        "INSERT INTO quests (player_name, giver_npc_id, quest_type, title, "
        "description, objective, progress, reward, template_id, tier) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
        "RETURNING id, player_name, giver_npc_id, target_npc_id, quest_type, "
        "title, description, objective, progress, reward, status, created_at",
        player_name, giver_npc_id, tmpl["type"], title, desc,
        json.dumps(objective), json.dumps(progress), json.dumps(tmpl["reward"]),
        template_id, tmpl.get("tier", 1),
    )
    return _row_to_dict(row)


def _initial_progress(quest_type: str) -> dict:
    return {
        "kill":    {"killed": 0},
        "fetch":   {"collected": 0},
        "deliver": {"delivered": False},
        "talk":    {"talked": False},
        "visit":   {"visited": False},
        "defend":  {"elapsed_s": 0},
        "escort":  {"distance": 0},
        "bounty":  {"killed": 0},
    }.get(quest_type, {})


async def turn_in(quest_id: int, player_name: str) -> dict | None:
    """Quest abgeben — closed + Reward gewähren. Returns die Quest mit
    `reward_granted` für UI-Feedback, oder None wenn Quest nicht completed."""
    row = await db.pool().fetchrow(
        "SELECT id, player_name, giver_npc_id, target_npc_id, quest_type, "
        "title, description, objective, progress, reward, status, created_at, "
        "template_id, tier "
        "FROM quests WHERE id = $1 AND player_name = $2",
        quest_id, player_name,
    )
    if not row or row["status"] != "completed":
        return None
    await mark_closed(quest_id)
    # reward kann (legacy) doppelt JSON-encoded sein → defensiv parsen,
    # sonst ist es ein str und reward.get(...) crasht (Reward ginge verloren).
    reward = _maybe_parse(row["reward"])
    # Faction-Reputation anwenden
    for fac, delta in (reward.get("faction") or {}).items():
        await add_reputation(player_name, fac, int(delta))
    out = _row_to_dict(row)
    out["status"] = "closed"
    out["reward_granted"] = reward
    out["template_id"] = row["template_id"]
    return out


# ─── Faction-Reputation ────────────────────────────────────────────────────

async def get_reputation(player_name: str, faction: str) -> int:
    val = await db.pool().fetchval(
        "SELECT goodwill FROM player_faction_reputation "
        "WHERE player_name = $1 AND faction_id = $2",
        player_name, faction,
    )
    return int(val or 0)


async def add_reputation(player_name: str, faction: str, delta: int) -> int:
    """Inkrementiert goodwill, returnt neuen Wert."""
    row = await db.pool().fetchrow(
        "INSERT INTO player_faction_reputation (player_name, faction_id, goodwill) "
        "VALUES ($1, $2, $3) "
        "ON CONFLICT (player_name, faction_id) DO UPDATE SET "
        "  goodwill = player_faction_reputation.goodwill + $3, "
        "  updated_at = NOW() "
        "RETURNING goodwill",
        player_name, faction, int(delta),
    )
    new_val = int(row["goodwill"])
    log.info("Reputation %s/%s %+d → %d", player_name, faction, delta, new_val)
    return new_val


async def all_reputation(player_name: str) -> dict[str, int]:
    rows = await db.pool().fetch(
        "SELECT faction_id, goodwill FROM player_faction_reputation "
        "WHERE player_name = $1 ORDER BY goodwill DESC",
        player_name,
    )
    return {r["faction_id"]: int(r["goodwill"]) for r in rows}


# ─── Weitere Hooks (Welle 23 — defend, escort, visit, talk, deliver) ──────

async def on_npc_talked_to(player_name: str, npc_kind: str,
                             npc_id: int) -> list[dict]:
    """Hook für talk-/deliver-Quests."""
    quests = await list_for_player(player_name, status_filter=("active",))
    updated: list[dict] = []
    for q in quests:
        obj = q["objective"] or {}
        target_kind = obj.get("to_kind")
        if q["quest_type"] == "talk" and target_kind == npc_kind:
            await db.pool().execute(
                "UPDATE quests SET progress = $2, status = 'completed', target_npc_id = $3 "
                "WHERE id = $1",
                q["id"], json.dumps({"talked": True}), npc_id,
            )
            q["progress"] = {"talked": True}
            q["status"] = "completed"
            q["target_npc_id"] = npc_id
            updated.append(q)
    return updated


async def on_location_visited(player_name: str, struct_type: str,
                                x: int, y: int) -> list[dict]:
    """Hook für visit-Quests."""
    quests = await list_for_player(player_name, status_filter=("active",))
    updated: list[dict] = []
    for q in quests:
        if q["quest_type"] != "visit":
            continue
        obj = q["objective"] or {}
        if obj.get("location_struct") != struct_type:
            continue
        await db.pool().execute(
            "UPDATE quests SET progress = $2, status = 'completed' WHERE id = $1",
            q["id"], json.dumps({"visited": True, "x": x, "y": y}),
        )
        q["progress"] = {"visited": True, "x": x, "y": y}
        q["status"] = "completed"
        updated.append(q)
    return updated
