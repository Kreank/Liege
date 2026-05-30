"""Player-Equipment-Queries (Welle 34c, extrahiert aus main.py).

Reine SQL-Queries auf items.equipped_slot. Werden vom WS-Handler vor
Combat/Harvest-Branches aufgerufen, um zu prüfen welche Waffe/Tool aktuell
equipped ist.
"""

import db


# Welche Tools/Waffen welchem Harvest-Skill genügen.
# Werden gegen items.equipped_slot IN ('tool', 'weapon') geprüft.
TOOL_FOR_SKILL = {
    "mining":       {"pickaxe"},
    "woodcutting":  {"axe"},
    "gathering":    {"sickle", "scythe", "hoe", "shovel"},  # Sichel (tool), Sense (weapon), oder Hacke/Schaufel
    "construction": {"hammer"},
}

# Welche Strukturen welches Tool brauchen.
# Mapping prop_type → skill_name. Default ist "gathering" (Sichel/Hacke).
PROP_SKILL = {
    # Holz → Axt
    "tree_oak": "woodcutting", "tree_pine": "woodcutting", "tree_dead": "woodcutting",
    "tree_stump": "woodcutting", "fallen_log": "woodcutting", "palm_tree": "woodcutting",
    "swamp_log": "woodcutting",
    "broken_cart": "woodcutting", "barrel": "woodcutting", "crate": "woodcutting",
    "fence": "woodcutting", "dock_straight": "woodcutting", "dock_corner": "woodcutting",
    "wooden_bridge": "woodcutting", "shipwreck": "woodcutting", "boat_small": "woodcutting",
    "driftwood": "woodcutting", "camp_tent": "woodcutting",
    # Stein → Spitzhacke
    "rock_small": "mining", "rock_large": "mining", "rock_mossy": "mining",
    "ruin_pillar": "mining", "rubble": "mining", "statue_broken": "mining",
    "gravestone": "mining", "lava_rock": "mining", "snow_rock": "mining",
    "ice_crystal": "mining", "anchor": "mining", "cooking_pot": "mining",
    # Pflanzen/Stoff → Sichel/Hacke/Schaufel
    "bush": "gathering", "tall_grass": "gathering", "flowers": "gathering",
    "mushrooms": "gathering", "reeds": "gathering", "lily_pads": "gathering",
    "sack": "gathering", "fishing_net": "gathering",
    "cactus": "gathering", "desert_skull": "gathering", "dry_bush": "gathering",
    "jungle_flower": "gathering", "jungle_vines": "gathering",
    "frozen_bush": "gathering", "swamp_bubbles": "gathering",
    "bones_scatter": "gathering",
}

# Tool-Hint-Text pro Skill für UI-Feedback
TOOL_HINT = {
    "mining":      "⛏️ Du brauchst eine Spitzhacke",
    "woodcutting": "🪓 Du brauchst eine Axt",
    "gathering":   "🌿 Du brauchst eine Sichel oder Hacke",
}

# Basic-Props die OHNE Tool harvestbar bleiben — wichtig damit neue Spieler
# überhaupt Wood/Stone für die ersten Tools bekommen.
NO_TOOL_PROPS = {"tree_stump", "fallen_log", "rubble", "driftwood"}


async def get_equipped_weapon_kind(player_name: str) -> str | None:
    row = await db.pool().fetchrow(
        "SELECT kind FROM items WHERE owner = $1 AND equipped_slot = 'weapon'",
        player_name,
    )
    return row["kind"] if row else None


async def get_equipped_tool_kind(player_name: str) -> str | None:
    row = await db.pool().fetchrow(
        "SELECT kind FROM items WHERE owner = $1 AND equipped_slot = 'tool'",
        player_name,
    )
    return row["kind"] if row else None


async def has_tool_for_skill(player_name: str, skill: str) -> bool:
    """Prüft ob ein passendes Tool/Waffe equipped ist für diesen Skill."""
    tools = TOOL_FOR_SKILL.get(skill, set())
    if not tools:
        return False
    row = await db.pool().fetchrow(
        "SELECT 1 FROM items WHERE owner = $1 "
        "AND equipped_slot IN ('tool', 'weapon') AND kind = ANY($2::text[]) LIMIT 1",
        player_name, list(tools),
    )
    return row is not None
