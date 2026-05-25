"""KI-Quest-Generator mit Welt-Verifikation.

Pipeline (Recherche-Empfehlung):
    World-Query → Template-Selektion → Slot-Filling aus Welt →
    LLM-Decoration (Titel/Dialog/Lore) → Validator → Aktivierung

Wichtig: LLM macht NUR Narrative (Titel, Beschreibung). Mechanik (Item-Kind,
Count, Reward) ist server-deterministisch.
"""
import json
import logging
import random

import db
import combat
import items as items_module
import quests


# Welche NPC-Kinds dürfen überhaupt Quests vergeben?
# wanderer/villager/farmer/hermit/bard sind reine "Plauder-NPCs"
QUEST_GIVING_KINDS = frozenset({
    "quest_giver",   # primärer Quest-Geber
    "merchant",      # Sammel-Aufträge (Materialien)
    "blacksmith",    # Smithing-Materialien
    "mage",          # Arkane Aufgaben
    "scholar",       # Recherche / seltene Items
    "guard",         # Sicherheits-Aufgaben (Mob-Kills)
    "soldier",       # Kampf-Aufgaben
    "healer",        # Kräuter / Heilung-Materialien
})


def can_give_quest(npc_kind: str) -> bool:
    """Entscheidet ob ein NPC-Kind überhaupt Quests vergeben kann."""
    return npc_kind in QUEST_GIVING_KINDS

log = logging.getLogger("liege.quest_generator")


QUEST_NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning":   {"type": "string"},
        "title":       {"type": "string", "description": "Quest-Titel (3-7 Worte, atmosphärisch)."},
        "description": {"type": "string", "description": "Quest-Beschreibung aus Sicht des NPCs (1-3 Sätze)."},
    },
    "required": ["reasoning", "title", "description"],
}


_QUEST_SYSTEM = (
    "Du erfindest Quest-Texte für ein dunkles Fantasy-RPG. "
    "Du schreibst Titel und Auftragsbeschreibung im Stil des Quest-Gebers. "
    "WICHTIG: Du erwähnst KEINE Zahlen, Stat-Werte oder konkrete Belohnungen. "
    "Antworte AUSSCHLIESSLICH als gültiges JSON."
)


# Quest-Slots mit verifizierbaren Welt-Conditions
GENERATABLE_TEMPLATES = [
    {
        "type": "fetch", "item_kind": "wood", "count_range": (5, 15),
        "tag": "construction", "reward_pool": ["gold_ore"],
        "reward_count_range": (3, 8),
        "min_player_level": 0,
    },
    {
        "type": "fetch", "item_kind": "iron_ore", "count_range": (3, 8),
        "tag": "smithing", "reward_pool": ["gold_ore", "steel_ingot"],
        "reward_count_range": (3, 6),
        "min_player_level": 2,
    },
    {
        "type": "fetch", "item_kind": "herb", "count_range": (5, 12),
        "tag": "alchemy", "reward_pool": ["health_potion"],
        "reward_count_range": (1, 3),
        "min_player_level": 0,
    },
    {
        "type": "fetch", "item_kind": "leather", "count_range": (3, 6),
        "tag": "tailor", "reward_pool": ["gold_ore"],
        "reward_count_range": (4, 8),
        "min_player_level": 2,
    },
    {
        "type": "fetch", "item_kind": "crystal", "count_range": (2, 4),
        "tag": "arcane", "reward_pool": ["mana_potion", "scroll"],
        "reward_count_range": (1, 2),
        "min_player_level": 4,
    },
    {
        "type": "kill", "creature_kind": "wolf", "count_range": (2, 5),
        "tag": "danger", "reward_pool": ["gold_ore", "leather"],
        "reward_count_range": (4, 8),
        "min_player_level": 1,
    },
    {
        "type": "kill", "creature_kind": "goblin", "count_range": (3, 6),
        "tag": "danger", "reward_pool": ["gold_ore", "sword"],
        "reward_count_range": (5, 10),
        "min_player_level": 1,
    },
    {
        "type": "kill", "creature_kind": "bandit", "count_range": (2, 4),
        "tag": "law", "reward_pool": ["gold_ore", "sword", "bow"],
        "reward_count_range": (8, 15),
        "min_player_level": 3,
    },
    {
        "type": "kill", "creature_kind": "skeleton", "count_range": (3, 5),
        "tag": "necro", "reward_pool": ["gold_ore", "bone", "silver_ore"],
        "reward_count_range": (5, 10),
        "min_player_level": 3,
    },
    {
        "type": "kill", "creature_kind": "spider", "count_range": (3, 6),
        "tag": "danger", "reward_pool": ["cloth", "herb"],
        "reward_count_range": (3, 6),
        "min_player_level": 1,
    },
]


def _player_level_estimate(skills_dict: dict) -> int:
    """Rough player-level aus Skills (Höchster Skill-Level)."""
    if not skills_dict:
        return 0
    return max((s.get("level", 0) for s in skills_dict.values()), default=0)


async def _verify_creature_exists(creature_kind: str, npcs_module) -> bool:
    """Existiert die Creature aktuell in der Welt? (sonst nicht 'killbar')."""
    all_npcs = npcs_module.all()
    return any(n["kind"] == creature_kind for n in all_npcs)


async def _select_template(player_skills: dict, npcs_module,
                            npc_kind: str | None) -> dict | None:
    """Wählt Template basierend auf Player-Level + Welt-Verfügbarkeit + NPC-Theme."""
    player_lvl = _player_level_estimate(player_skills)
    # Filter: Level-Anforderung
    candidates = [t for t in GENERATABLE_TEMPLATES if t["min_player_level"] <= player_lvl]
    # Bevorzuge Templates die zum NPC-Kind passen (Schmied → smithing etc.)
    npc_to_tag = {
        "merchant":    ["construction", "alchemy", "smithing", "tailor"],
        "scholar":     ["alchemy", "arcane"],
        "bard":        ["danger", "law"],
        "soldier":     ["danger", "law"],
        "hermit":      ["alchemy", "arcane"],
        "wanderer":    None,  # alles
        # Welle 21
        "mage":        ["arcane", "alchemy"],
        "healer":      ["alchemy"],
        "blacksmith":  ["smithing", "construction"],
        "farmer":      ["construction"],
        "guard":       ["danger", "law"],
        "quest_giver": None,    # gibt alles
        "villager":    ["construction", "alchemy"],
    }
    pref_tags = npc_to_tag.get(npc_kind, None) if npc_kind else None
    if pref_tags:
        prefs = [t for t in candidates if t["tag"] in pref_tags]
        if prefs:
            candidates = prefs
    # Kill-Quests nur wenn entsprechende Creature in der Welt existiert
    valid: list[dict] = []
    for t in candidates:
        if t["type"] == "kill":
            if await _verify_creature_exists(t["creature_kind"], npcs_module):
                valid.append(t)
        else:
            valid.append(t)
    if not valid:
        return None
    return random.choice(valid)


async def generate_quest_for_npc(player_name: str, npc: dict,
                                  npcs_module) -> dict | None:
    """Generiert eine Quest für (player, npc). Returns Quest-Dict oder None."""
    import skills as skills_module
    import random as _r

    # Player-Skill-Info für Schwierigkeit
    player_skills = await skills_module.get_skills(player_name)
    player_lvl = max((s.get("level", 0) for s in player_skills.values()), default=0)

    # Welle 28: 30% Chance auf Multi-Stage-Quest (DAG)
    if _r.random() < 0.30:
        try:
            import quest_stages
            eligible = [t for t in quest_stages.MULTI_STAGE_TEMPLATES
                        if t.get("min_player_level", 0) <= player_lvl]
            # Bevorzuge tag-matching mit npc kind
            npc_tag_map = {
                "merchant": "construction", "scholar": "arcane", "mage": "arcane",
                "guard": "danger", "soldier": "danger",
                "blacksmith": "smithing", "quest_giver": None,
            }
            pref_tag = npc_tag_map.get(npc.get("kind"))
            if pref_tag:
                tagged = [t for t in eligible if t.get("tag") == pref_tag]
                if tagged:
                    eligible = tagged
            if eligible:
                tmpl = _r.choice(eligible)
                return await quest_stages.create_multi_stage_quest(
                    player_name, npc.get("id", 0), tmpl,
                )
        except Exception:
            log.exception("Multi-Stage-Quest-Gen fehlgeschlagen — falle auf Single-Stage zurück")

    # Template wählen (verifiziert)
    template = await _select_template(player_skills, npcs_module, npc.get("kind"))
    if template is None:
        log.info("Kein verfügbares Template für Quest-Gen (player=%s, npc=%s)",
                 player_name, npc.get("kind"))
        return None

    # Slots konkretisieren
    count = random.randint(*template["count_range"])
    if template["type"] == "fetch":
        objective = {"item_kind": template["item_kind"], "count": count}
        progress = {"collected": 0}
        objective_text = f"{count}× {template['item_kind']}"
    else:
        objective = {"creature_kind": template["creature_kind"], "count": count}
        progress = {"killed": 0}
        objective_text = f"{count}× {template['creature_kind']}"

    # Reward konkretisieren
    reward_kind = random.choice(template["reward_pool"])
    reward_count = random.randint(*template["reward_count_range"])
    reward = {reward_kind: reward_count, "xp": 20 + count * 10}

    # LLM-Narrative-Generation
    narrative = await _generate_narrative(npc, template, objective_text, reward)
    if narrative is None:
        # Fallback: deterministischer Text
        title = f"Auftrag: {objective_text}"
        description = (
            f"{npc.get('name', 'Der Auftraggeber')} braucht {objective_text}. "
            f"Bringt es herbei, und die Mühe wird vergolten."
        )
    else:
        title = narrative["title"]
        description = narrative["description"]

    # Persistieren in DB
    row = await db.pool().fetchrow(
        "INSERT INTO quests (player_name, giver_npc_id, quest_type, title, "
        "description, objective, progress, reward) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
        "RETURNING id, player_name, giver_npc_id, target_npc_id, quest_type, "
        "title, description, objective, progress, reward, status, created_at",
        player_name, npc.get("id"), template["type"], title, description,
        json.dumps(objective), json.dumps(progress), json.dumps(reward),
    )
    return quests._row_to_dict(row)


async def _generate_narrative(npc: dict, template: dict, objective_text: str,
                              reward: dict) -> dict | None:
    """Lässt die LLM Titel + Beschreibung generieren."""
    import llm
    npc_name = npc.get("name", "der Auftraggeber")
    npc_kind = npc.get("kind", "wanderer")
    backstory = npc.get("backstory", "")[:200]
    reward_text = ", ".join(f"{v}× {k}" for k, v in reward.items() if k != "xp")

    prompt = f"""Generiere Titel und Auftrags-Beschreibung für folgende Quest:

Quest-Geber: {npc_name} ({npc_kind})
Hintergrund: {backstory}
Aufgabe-Typ: {template['type']}
Ziel: {objective_text}
Belohnung (nur als Kontext, nicht erwähnen!): {reward_text}

Schreibe einen prägnanten Titel und eine Quest-Beschreibung aus Sicht des Quest-Gebers.
KEINE Zahlen oder konkreten Mengen im Beschreibungstext nennen!
"""
    # Welle 24: Semantic-Cache
    import llm_cache
    scope = f"quest_narrative:{template['type']}:{npc_kind}"
    cached = await llm_cache.lookup(scope, prompt, "lore")
    if cached is not None:
        return cached
    result = await llm.fast_brain_structured(
        prompt, QUEST_NARRATIVE_SCHEMA, system=_QUEST_SYSTEM,
    )
    if result is not None:
        await llm_cache.store(scope, prompt, "lore", result, llm.FAST_MODEL)
    return result
