"""Talent-Baum-System.

Jeder Skill-Levelup gibt 1 Talent-Punkt. Pro Skill gibt es 5-7 Talente in einer
Baum-Struktur (Tier 1 → Tier 2 → Tier 3). Talente sind passive Boni die
Skill-Effekte verstärken oder neue Fähigkeiten freischalten.

Talent-Effekte werden über `effect_for(player_name, effect_key)` abgefragt
und sind additiv (z.B. `mining_yield_pct = +0.10`).
"""
import json
import logging
import db

log = logging.getLogger("liege.talents")


SCHEMA = """
CREATE TABLE IF NOT EXISTS player_talents (
    player_name  TEXT NOT NULL,
    talent_id    TEXT NOT NULL,
    rank         INTEGER NOT NULL DEFAULT 1,
    learned_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_name, talent_id)
);
ALTER TABLE players ADD COLUMN IF NOT EXISTS talent_points INTEGER NOT NULL DEFAULT 0;
"""


# Talent-Definitionen. Tier 1 hat keine prereq, Tier 2 braucht Talent aus Tier 1
# desselben Skills, etc. Effekte werden additiv über alle Talente summiert.
TALENT_TREE = {
    # — MINING ————————————————————————————————————————————————————————————
    "mining": {
        "ore_eye":           {"tier": 1, "name": "Erzauge",          "icon": "👁️",
                              "desc": "Sieht Erzadern besser — +15% Drop-Chance auf Erze.",
                              "effects": {"mining_ore_chance": 0.15},
                              "skill_min": 2, "prereq": None},
        "stonebreaker":      {"tier": 1, "name": "Steinhauer",       "icon": "🔨",
                              "desc": "Zerschlägt Stein mit Wucht — +25% Stone-Yield.",
                              "effects": {"mining_stone_yield": 0.25},
                              "skill_min": 2, "prereq": None},
        "deep_miner":        {"tier": 2, "name": "Tiefer Bergmann",  "icon": "⛏️",
                              "desc": "Findet tief verborgene Edelsteine — +20% Crystal/Gold Chance.",
                              "effects": {"mining_rare_chance": 0.20},
                              "skill_min": 6, "prereq": "ore_eye"},
        "rock_efficiency":   {"tier": 2, "name": "Effizient",        "icon": "💪",
                              "desc": "Pro Treffer 1 Extra-Damage am Stein.",
                              "effects": {"mining_extra_damage": 1},
                              "skill_min": 6, "prereq": "stonebreaker"},
        "mythril_seer":      {"tier": 3, "name": "Mythril-Seher",    "icon": "💎",
                              "desc": "Selbst Mythril zeigt sich dir — 5% Chance auf Mythril-Drop.",
                              "effects": {"mining_mythril_chance": 0.05},
                              "skill_min": 12, "prereq": "deep_miner"},
    },
    # — WOODCUTTING ———————————————————————————————————————————————————————
    "woodcutting": {
        "lumberjack":        {"tier": 1, "name": "Holzfäller",       "icon": "🪓",
                              "desc": "+25% Wood-Yield aus Bäumen.",
                              "effects": {"woodcutting_yield": 0.25},
                              "skill_min": 2, "prereq": None},
        "forager":           {"tier": 1, "name": "Sammler",          "icon": "🍎",
                              "desc": "Findet Früchte/Mushrooms am Baum — +20% Chance auf Apple-Drop.",
                              "effects": {"woodcutting_apple_chance": 0.20},
                              "skill_min": 2, "prereq": None},
        "fast_chopper":      {"tier": 2, "name": "Schneller Schlag", "icon": "⚡",
                              "desc": "+1 Damage pro Treffer auf Bäume.",
                              "effects": {"woodcutting_extra_damage": 1},
                              "skill_min": 6, "prereq": "lumberjack"},
        "deep_forest":       {"tier": 2, "name": "Waldläufer",       "icon": "🌲",
                              "desc": "Findet seltene Drops im Wald — +10% Chance auf Crystal.",
                              "effects": {"woodcutting_rare_chance": 0.10},
                              "skill_min": 6, "prereq": "forager"},
        "ancient_oak":       {"tier": 3, "name": "Uralter Eiche",    "icon": "🌳",
                              "desc": "Bäume droppen +1 Wood garantiert.",
                              "effects": {"woodcutting_bonus_wood": 1},
                              "skill_min": 12, "prereq": "fast_chopper"},
    },
    # — GATHERING ————————————————————————————————————————————————————————
    "gathering": {
        "herbalist":         {"tier": 1, "name": "Kräuterkundig",    "icon": "🌿",
                              "desc": "+25% Herb-Drop-Chance.",
                              "effects": {"gathering_herb_chance": 0.25},
                              "skill_min": 2, "prereq": None},
        "mushroom_hunter":   {"tier": 1, "name": "Pilzkenner",       "icon": "🍄",
                              "desc": "+20% Mushroom-Food-Drops.",
                              "effects": {"gathering_mushroom_chance": 0.20},
                              "skill_min": 2, "prereq": None},
        "swift_picker":      {"tier": 2, "name": "Geschwinde Hand",  "icon": "✋",
                              "desc": "Pflanzen geben +1 Yield.",
                              "effects": {"gathering_bonus_yield": 1},
                              "skill_min": 6, "prereq": "herbalist"},
        "wild_botanist":     {"tier": 3, "name": "Wild-Botaniker",   "icon": "🌸",
                              "desc": "Doppelte Chance auf Crystal-Drops aus Mushrooms/Flowers.",
                              "effects": {"gathering_crystal_chance": 0.15},
                              "skill_min": 12, "prereq": "swift_picker"},
    },
    # — CONSTRUCTION ——————————————————————————————————————————————————————
    "construction": {
        "fast_builder":      {"tier": 1, "name": "Schnellbauer",     "icon": "🔨",
                              "desc": "+30% Construction-XP.",
                              "effects": {"construction_xp": 0.30},
                              "skill_min": 2, "prereq": None},
        "thrifty":           {"tier": 1, "name": "Sparsam",          "icon": "💰",
                              "desc": "20% Chance Material nicht zu verbrauchen beim Bauen.",
                              "effects": {"construction_save_chance": 0.20},
                              "skill_min": 2, "prereq": None},
        "fortifier":         {"tier": 2, "name": "Befestiger",       "icon": "🛡️",
                              "desc": "Gebaute Strukturen +50% Durability.",
                              "effects": {"construction_durability": 0.50},
                              "skill_min": 6, "prereq": "fast_builder"},
        "master_architect":  {"tier": 3, "name": "Meister-Architekt","icon": "🏛️",
                              "desc": "Strukturen können nicht von Standard-Mobs zerstört werden.",
                              "effects": {"construction_invulnerable": 1},
                              "skill_min": 14, "prereq": "fortifier"},
    },
    # — CRAFTING ——————————————————————————————————————————————————————————
    "crafting": {
        "quick_hands":       {"tier": 1, "name": "Flinke Hände",     "icon": "✋",
                              "desc": "+25% Quality-Roll-Chance beim Crafting.",
                              "effects": {"crafting_quality_bonus": 0.25},
                              "skill_min": 2, "prereq": None},
        "material_economy":  {"tier": 1, "name": "Material-Ökonomie","icon": "♻️",
                              "desc": "15% Chance Material nicht zu verbrauchen beim Craften.",
                              "effects": {"crafting_save_chance": 0.15},
                              "skill_min": 2, "prereq": None},
        "perfectionist":     {"tier": 2, "name": "Perfektionist",    "icon": "⭐",
                              "desc": "Crafting kann nie schlechter als 'fein' werden.",
                              "effects": {"crafting_min_quality": 1},
                              "skill_min": 8, "prereq": "quick_hands"},
        "grandmaster":       {"tier": 3, "name": "Großmeister",      "icon": "👑",
                              "desc": "+5% Chance auf 'legendär' beim Crafting.",
                              "effects": {"crafting_legendary_chance": 0.05},
                              "skill_min": 14, "prereq": "perfectionist"},
    },
    # — COMBAT ————————————————————————————————————————————————————————————
    "combat": {
        "warrior":           {"tier": 1, "name": "Krieger",          "icon": "⚔️",
                              "desc": "+10% Melee-Damage.",
                              "effects": {"combat_melee_damage": 0.10},
                              "skill_min": 2, "prereq": None},
        "marksman":          {"tier": 1, "name": "Schütze",          "icon": "🎯",
                              "desc": "+10% Ranged-Damage und +1 Range.",
                              "effects": {"combat_ranged_damage": 0.10,
                                          "combat_ranged_range": 1},
                              "skill_min": 2, "prereq": None},
        "vampiric":          {"tier": 2, "name": "Vampirisch",       "icon": "🩸",
                              "desc": "Heile 10% deines Schadens als HP.",
                              "effects": {"combat_lifesteal": 0.10},
                              "skill_min": 8, "prereq": "warrior"},
        "deadly_aim":        {"tier": 2, "name": "Tödliches Ziel",   "icon": "💀",
                              "desc": "+15% Crit-Chance.",
                              "effects": {"combat_crit_chance": 0.15},
                              "skill_min": 8, "prereq": "marksman"},
        "berserker":         {"tier": 3, "name": "Berserker",        "icon": "💢",
                              "desc": "Unter 30% HP: +40% Damage.",
                              "effects": {"combat_berserker": 0.40},
                              "skill_min": 14, "prereq": "vampiric"},
        "executioner":       {"tier": 3, "name": "Henker",           "icon": "🗡️",
                              "desc": "Crit-Damage +30%.",
                              "effects": {"combat_crit_damage": 0.30},
                              "skill_min": 14, "prereq": "deadly_aim"},
    },
    # — MAGIC ——————————————————————————————————————————————————————————————
    "magic": {
        "arcanist":          {"tier": 1, "name": "Arkanist",         "icon": "✨",
                              "desc": "+15% Spell-Damage.",
                              "effects": {"magic_spell_damage": 0.15},
                              "skill_min": 2, "prereq": None},
        "mana_efficient":    {"tier": 1, "name": "Mana-Effizient",   "icon": "💧",
                              "desc": "-20% Mana-Kosten.",
                              "effects": {"magic_mana_reduction": 0.20},
                              "skill_min": 2, "prereq": None},
        "pyromancer":        {"tier": 2, "name": "Pyromant",         "icon": "🔥",
                              "desc": "Feuer-Spells verursachen 'burning' für 8s.",
                              "effects": {"magic_burning_apply": 1},
                              "skill_min": 8, "prereq": "arcanist"},
        "channeling":        {"tier": 2, "name": "Kanalisierung",    "icon": "🌀",
                              "desc": "+25% Mana-Pool.",
                              "effects": {"magic_max_mana": 0.25},
                              "skill_min": 8, "prereq": "mana_efficient"},
        "archmage":          {"tier": 3, "name": "Erzmagier",        "icon": "🔮",
                              "desc": "Spells haben +1 AOE-Radius.",
                              "effects": {"magic_aoe_bonus": 1},
                              "skill_min": 14, "prereq": "pyromancer"},
    },
    # — COOKING ——————————————————————————————————————————————————————————
    "cooking": {
        "tasty_meals":       {"tier": 1, "name": "Köstliche Mahlzeiten","icon": "🍳",
                              "desc": "+25% Hunger-Restore von Food.",
                              "effects": {"cooking_hunger_bonus": 0.25},
                              "skill_min": 2, "prereq": None},
        "double_portion":    {"tier": 2, "name": "Doppelte Portion", "icon": "🍖",
                              "desc": "30% Chance 2 Stück beim Kochen zu erhalten.",
                              "effects": {"cooking_extra_chance": 0.30},
                              "skill_min": 6, "prereq": "tasty_meals"},
        "master_chef":       {"tier": 3, "name": "Sterne-Koch",      "icon": "👨‍🍳",
                              "desc": "Gekochte Mahlzeiten heilen zusätzlich 10 HP.",
                              "effects": {"cooking_heal_bonus": 10},
                              "skill_min": 12, "prereq": "double_portion"},
    },
    # — MEDICAL ——————————————————————————————————————————————————————————
    "medical": {
        "healer":            {"tier": 1, "name": "Heiler",           "icon": "❤️‍🩹",
                              "desc": "Heiltränke heilen +25%.",
                              "effects": {"medical_heal_bonus": 0.25},
                              "skill_min": 2, "prereq": None},
        "rejuvenation":      {"tier": 2, "name": "Verjüngung",       "icon": "💖",
                              "desc": "Heiltränke heilen auch Body-Parts +15.",
                              "effects": {"medical_part_heal": 15},
                              "skill_min": 6, "prereq": "healer"},
        "blessed_hands":     {"tier": 3, "name": "Gesegnete Hände",  "icon": "🙏",
                              "desc": "Beim Heilen 30% Chance auf zusätzlichen 'blessed'-Status.",
                              "effects": {"medical_blessed_chance": 0.30},
                              "skill_min": 12, "prereq": "rejuvenation"},
    },
    # — FARMING ——————————————————————————————————————————————————————————
    "farming": {
        "green_thumb":       {"tier": 1, "name": "Grüner Daumen",    "icon": "🌱",
                              "desc": "Pflanzen wachsen 30% schneller.",
                              "effects": {"farming_growth_speed": 0.30},
                              "skill_min": 2, "prereq": None},
        "double_harvest":    {"tier": 2, "name": "Doppel-Ernte",     "icon": "🌾",
                              "desc": "25% Chance auf doppelte Ernte.",
                              "effects": {"farming_double_chance": 0.25},
                              "skill_min": 6, "prereq": "green_thumb"},
        "soil_master":       {"tier": 3, "name": "Boden-Meister",    "icon": "🌻",
                              "desc": "Felder müssen nicht mehr ausgesät werden — wachsen automatisch nach.",
                              "effects": {"farming_auto_replant": 1},
                              "skill_min": 12, "prereq": "double_harvest"},
    },
    # — SOCIAL ————————————————————————————————————————————————————————————
    "social": {
        "haggler":           {"tier": 1, "name": "Feilscher",        "icon": "💬",
                              "desc": "-15% Kaufpreis bei Händlern.",
                              "effects": {"social_buy_discount": 0.15},
                              "skill_min": 2, "prereq": None},
        "charming":          {"tier": 1, "name": "Charmant",         "icon": "😊",
                              "desc": "NPC-Mood +5 beim Dialog.",
                              "effects": {"social_mood_boost": 5},
                              "skill_min": 2, "prereq": None},
        "merchant_friend":   {"tier": 2, "name": "Händlerfreund",    "icon": "💰",
                              "desc": "Händler bieten +20% Verkaufspreis.",
                              "effects": {"social_sell_bonus": 0.20},
                              "skill_min": 6, "prereq": "haggler"},
        "diplomat":          {"tier": 3, "name": "Diplomat",         "icon": "🕊️",
                              "desc": "Feindliche NPCs greifen 20% seltener an.",
                              "effects": {"social_aggro_reduction": 0.20},
                              "skill_min": 12, "prereq": "merchant_friend"},
    },
}


# — DB-Layer ————————————————————————————————————————————————————————————

async def get_talent_points(player_name: str) -> int:
    row = await db.pool().fetchrow(
        "SELECT talent_points FROM players WHERE name = $1", player_name,
    )
    return int(row["talent_points"]) if row else 0


async def grant_talent_point(player_name: str, n: int = 1) -> int:
    """Vergibt Talent-Punkt(e) — typischerweise bei Skill-Levelup."""
    row = await db.pool().fetchrow(
        "UPDATE players SET talent_points = talent_points + $2 "
        "WHERE name = $1 RETURNING talent_points",
        player_name, n,
    )
    return int(row["talent_points"]) if row else 0


async def list_learned(player_name: str) -> list[dict]:
    rows = await db.pool().fetch(
        "SELECT talent_id, rank, learned_at FROM player_talents "
        "WHERE player_name = $1",
        player_name,
    )
    return [{"talent_id": r["talent_id"], "rank": r["rank"],
             "learned_at": r["learned_at"].isoformat()} for r in rows]


async def is_learned(player_name: str, talent_id: str) -> bool:
    row = await db.pool().fetchrow(
        "SELECT 1 FROM player_talents WHERE player_name = $1 AND talent_id = $2",
        player_name, talent_id,
    )
    return row is not None


def find_talent(talent_id: str) -> tuple[str, dict] | None:
    """Returns (skill, talent_dict) oder None."""
    for skill, talents in TALENT_TREE.items():
        if talent_id in talents:
            return skill, talents[talent_id]
    return None


async def learn_talent(player_name: str, talent_id: str,
                        skill_level: int) -> dict:
    """Versucht ein Talent zu lernen. Returns {ok, reason?, points_left?}."""
    found = find_talent(talent_id)
    if found is None:
        return {"ok": False, "reason": "unknown_talent"}
    skill, talent = found

    if skill_level < talent["skill_min"]:
        return {"ok": False, "reason": "skill_too_low",
                "needed": talent["skill_min"], "have": skill_level}

    if talent["prereq"] and not await is_learned(player_name, talent["prereq"]):
        return {"ok": False, "reason": "prereq_missing",
                "prereq": talent["prereq"]}

    if await is_learned(player_name, talent_id):
        return {"ok": False, "reason": "already_learned"}

    pts = await get_talent_points(player_name)
    if pts < 1:
        return {"ok": False, "reason": "no_points"}

    # Punkt abziehen + Talent setzen
    await db.pool().execute(
        "UPDATE players SET talent_points = talent_points - 1 "
        "WHERE name = $1", player_name,
    )
    await db.pool().execute(
        "INSERT INTO player_talents (player_name, talent_id, rank) "
        "VALUES ($1, $2, 1)",
        player_name, talent_id,
    )
    return {"ok": True, "talent_id": talent_id,
            "points_left": pts - 1, "effects": talent["effects"]}


# — Effekt-Aggregation für Game-Code ————————————————————————————————————

async def aggregate_effects(player_name: str) -> dict[str, float]:
    """Summiert alle Talent-Effekte des Spielers über alle gelernten Talente.
    Returns dict {effect_key: total_value}."""
    rows = await db.pool().fetch(
        "SELECT talent_id FROM player_talents WHERE player_name = $1",
        player_name,
    )
    out: dict[str, float] = {}
    for r in rows:
        found = find_talent(r["talent_id"])
        if not found:
            continue
        _, talent = found
        for key, val in talent["effects"].items():
            out[key] = out.get(key, 0) + val
    return out


async def effect_for(player_name: str, key: str) -> float:
    """Single-Effect-Lookup. Standard 0 wenn nicht vorhanden."""
    effects = await aggregate_effects(player_name)
    return float(effects.get(key, 0))


def tree_for_ui(skill_levels: dict[str, dict],
                learned_set: set[str], points: int) -> dict:
    """Vollständige Tree-Repräsentation fürs Frontend — pro Skill
    eine Liste von Talenten mit Status (locked/available/learned)."""
    out: dict[str, list[dict]] = {}
    for skill, talents in TALENT_TREE.items():
        level = skill_levels.get(skill, {}).get("level", 0)
        items: list[dict] = []
        for tid, t in talents.items():
            status = "learned" if tid in learned_set else "locked"
            if status == "locked":
                prereq_ok = (t["prereq"] is None or t["prereq"] in learned_set)
                if level >= t["skill_min"] and prereq_ok and points >= 1:
                    status = "available"
                elif level >= t["skill_min"] and prereq_ok:
                    status = "needs_points"
            items.append({
                "id":         tid,
                "name":       t["name"],
                "icon":       t["icon"],
                "desc":       t["desc"],
                "tier":       t["tier"],
                "skill_min":  t["skill_min"],
                "prereq":     t["prereq"],
                "status":     status,
            })
        out[skill] = items
    return out
