"""Multi-Step-Quest-Engine (Welle 28, DAG-Pattern).

Quests können mehrere Stages haben. Stages werden im JSONB-Feld der
quests-Tabelle gespeichert. Jede Stage hat:
    key: string
    objective_type: fetch | kill | talk | visit
    objective_data: {...}
    progress: {...}
    state: locked | unlocked | in_progress | completed
    requires: [stage_keys, ...]    — DAG-Predecessors

Quest-Templates definieren Stages deklarativ; Engine handhabt State-Machine.
"""
import json
import logging

import db

log = logging.getLogger("liege.quest_stages")


# Multi-Stage-Quest-Templates (Beispiele, ergänzbar)
MULTI_STAGE_TEMPLATES = [
    {
        "id": "lost_amulet",
        "title": "Das verlorene Amulett",
        "description_template": "{npc_name} hat sein Amulett verloren — finde es wieder.",
        "stages": [
            {"key": "talk_to_witness",
             "type": "talk",
             "data": {"any_kind": "villager"},
             "description": "Sprich mit einem Dorfbewohner über das Amulett.",
             "requires": []},
            {"key": "find_clue",
             "type": "collect",
             "data": {"item_kind": "bone", "count": 3},
             "description": "Suche nach Spuren (3 Knochen aus der Region).",
             "requires": ["talk_to_witness"]},
            {"key": "defeat_thief",
             "type": "kill",
             "data": {"creature_kind": "bandit", "count": 1},
             "description": "Stell den Dieb und erlege ihn.",
             "requires": ["find_clue"]},
        ],
        "reward": {"gold_ore": 15, "amulet": 1, "xp": 100},
        "tag": "investigation",
        "min_player_level": 2,
    },
    {
        "id": "wolves_threat",
        "title": "Die Wölfe-Plage",
        "description_template": "{npc_name} bittet dich um Hilfe gegen Wölfe.",
        "stages": [
            {"key": "hunt_wolves",
             "type": "kill",
             "data": {"creature_kind": "wolf", "count": 5},
             "description": "Erlege 5 Wölfe.",
             "requires": []},
            {"key": "deliver_leather",
             "type": "collect",
             "data": {"item_kind": "leather", "count": 5},
             "description": "Bringe 5 Stücke Leder zurück.",
             "requires": ["hunt_wolves"]},
        ],
        "reward": {"gold_ore": 12, "boots": 1, "xp": 80},
        "tag": "danger",
        "min_player_level": 1,
    },
    {
        "id": "blacksmith_forge",
        "title": "Schmiede-Auftrag",
        "description_template": "{npc_name} braucht Material für eine besondere Waffe.",
        "stages": [
            {"key": "gather_iron",
             "type": "collect",
             "data": {"item_kind": "iron_ore", "count": 4},
             "description": "Sammle 4 Eisenerze.",
             "requires": []},
            {"key": "gather_wood",
             "type": "collect",
             "data": {"item_kind": "wood", "count": 5},
             "description": "Sammle 5 Stück Holz.",
             "requires": []},
            {"key": "deliver_steel",
             "type": "collect",
             "data": {"item_kind": "steel_ingot", "count": 2},
             "description": "Stelle 2 Stahlbarren her und bringe sie.",
             "requires": ["gather_iron", "gather_wood"]},
        ],
        "reward": {"gold_ore": 20, "sword": 1, "xp": 120},
        "tag": "smithing",
        "min_player_level": 2,
    },
    {
        "id": "arcane_research",
        "title": "Arkane Forschung",
        "description_template": "{npc_name} braucht seltene Kristalle für ein Ritual.",
        "stages": [
            {"key": "find_crystals",
             "type": "collect",
             "data": {"item_kind": "crystal", "count": 3},
             "description": "Bringe 3 Kristalle.",
             "requires": []},
            {"key": "defeat_undead",
             "type": "kill",
             "data": {"creature_kind": "skeleton", "count": 2},
             "description": "Vertreibe 2 Skelette.",
             "requires": []},
            {"key": "return",
             "type": "talk",
             "data": {"any_kind": "mage"},
             "description": "Kehre zum Magier zurück.",
             "requires": ["find_crystals", "defeat_undead"]},
        ],
        "reward": {"crystal": 1, "scroll": 2, "mana_potion": 2, "xp": 150},
        "tag": "arcane",
        "min_player_level": 4,
    },
]


def _all_predecessors_done(stages: list[dict], target_key: str) -> bool:
    """Sind alle requires des Targets erfüllt?"""
    target = next((s for s in stages if s["key"] == target_key), None)
    if not target:
        return False
    for req in target.get("requires", []):
        req_stage = next((s for s in stages if s["key"] == req), None)
        if not req_stage or req_stage.get("state") != "completed":
            return False
    return True


def initialize_stages(template_stages: list[dict]) -> list[dict]:
    """Erstellt initiale Stage-States (alle locked außer Start-Stages)."""
    stages = []
    for s in template_stages:
        st = dict(s)
        st["progress"] = {}
        st["state"] = "unlocked" if not s.get("requires") else "locked"
        stages.append(st)
    return stages


def unlock_eligible(stages: list[dict]) -> int:
    """Prüft alle locked Stages ob sie unlockable sind. Returns # changes."""
    changes = 0
    for s in stages:
        if s.get("state") == "locked" and _all_predecessors_done(stages, s["key"]):
            s["state"] = "unlocked"
            changes += 1
    return changes


def is_complete(stages: list[dict]) -> bool:
    """Quest ist fertig wenn alle nicht-optionalen Stages completed sind."""
    return all(s.get("state") == "completed" for s in stages
               if not s.get("optional", False))


async def create_multi_stage_quest(player_name: str, giver_npc_id: int,
                                    template: dict) -> dict:
    """Legt eine Multi-Stage-Quest an."""
    stages = initialize_stages(template["stages"])
    npc_row = await db.pool().fetchrow(
        "SELECT name FROM npcs WHERE id = $1", giver_npc_id
    )
    npc_name = npc_row["name"] if npc_row else "Auftraggeber"
    description = template.get("description_template", "").format(npc_name=npc_name)

    objective = {"template_id": template["id"], "stages": stages,
                 "current_stage": stages[0]["key"] if stages else None}
    progress = {"stages_done": 0}
    row = await db.pool().fetchrow(
        "INSERT INTO quests (player_name, giver_npc_id, quest_type, title, "
        "description, objective, progress, reward) "
        "VALUES ($1, $2, 'multi_stage', $3, $4, $5, $6, $7) "
        "RETURNING id, player_name, giver_npc_id, target_npc_id, quest_type, "
        "title, description, objective, progress, reward, status, created_at",
        player_name, giver_npc_id, template["title"], description,
        json.dumps(objective), json.dumps(progress),
        json.dumps(template["reward"]),
    )
    return _row_to_dict(row)


def _row_to_dict(row):
    obj = row["objective"]
    if isinstance(obj, str):
        obj = json.loads(obj)
    prog = row["progress"]
    if isinstance(prog, str):
        prog = json.loads(prog)
    rew = row["reward"]
    if isinstance(rew, str):
        rew = json.loads(rew)
    return {
        "id":             row["id"],
        "player_name":    row["player_name"],
        "giver_npc_id":   row["giver_npc_id"],
        "target_npc_id":  row["target_npc_id"],
        "quest_type":     row["quest_type"],
        "title":          row["title"],
        "description":    row["description"],
        "objective":      obj,
        "progress":       prog,
        "reward":         rew,
        "status":         row["status"],
        "created_at":     row["created_at"].isoformat(),
    }


# — Hooks für Event-Bus ——————————————————————————————————————————————

async def on_player_event(player_name: str, event_type: str,
                          payload: dict) -> list[dict]:
    """Wird vom Game-Code aufgerufen bei Spieler-Aktionen.
    event_type: 'collect' | 'kill' | 'talk' | 'visit'
    payload: { ... event-spezifische Daten ... }

    Returns Liste der aktualisierten Multi-Stage-Quests.
    """
    rows = await db.pool().fetch(
        "SELECT id, player_name, giver_npc_id, target_npc_id, quest_type, "
        "title, description, objective, progress, reward, status, created_at "
        "FROM quests WHERE player_name = $1 AND quest_type = 'multi_stage' "
        "AND status = 'active'",
        player_name,
    )
    updated = []
    for r in rows:
        q = _row_to_dict(r)
        stages = q["objective"].get("stages", [])
        changed = False
        for s in stages:
            if s.get("state") not in ("unlocked", "in_progress"):
                continue
            if s.get("type") != event_type:
                continue
            data = s.get("data", {})
            # Match prüfen
            if event_type == "collect":
                if data.get("item_kind") != payload.get("item_kind"):
                    continue
                need = data.get("count", 1)
                have = s["progress"].get("collected", 0) + payload.get("count", 1)
                s["progress"]["collected"] = min(have, need)
                s["state"] = "in_progress"
                if s["progress"]["collected"] >= need:
                    s["state"] = "completed"
                changed = True
            elif event_type == "kill":
                if data.get("creature_kind") != payload.get("creature_kind"):
                    continue
                need = data.get("count", 1)
                have = s["progress"].get("killed", 0) + payload.get("count", 1)
                s["progress"]["killed"] = min(have, need)
                s["state"] = "in_progress"
                if s["progress"]["killed"] >= need:
                    s["state"] = "completed"
                changed = True
            elif event_type == "talk":
                if data.get("any_kind") and data["any_kind"] != payload.get("kind"):
                    continue
                s["state"] = "completed"
                changed = True
            elif event_type == "visit":
                if data.get("location_id") != payload.get("location_id"):
                    continue
                s["state"] = "completed"
                changed = True
        if changed:
            # Nachfolger entsperren + Quest-Status prüfen
            unlock_eligible(stages)
            stages_done = sum(1 for s in stages if s["state"] == "completed")
            q["progress"]["stages_done"] = stages_done
            new_status = "completed" if is_complete(stages) else "active"
            q["status"] = new_status
            # Aktuelle Stage updaten
            for s in stages:
                if s["state"] in ("unlocked", "in_progress"):
                    q["objective"]["current_stage"] = s["key"]
                    break
            await db.pool().execute(
                "UPDATE quests SET objective = $2, progress = $3, status = $4 "
                "WHERE id = $1",
                q["id"], json.dumps(q["objective"]),
                json.dumps(q["progress"]), new_status,
            )
            updated.append(q)
    return updated
