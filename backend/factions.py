"""Faction-System mit Beziehungs-Graph (Welle 27).

Datenmodell folgt der Recherche-Empfehlung:
- Faktionen sind statisch + dynamisch (goodwill driftet zurück zu natural-range)
- Spieler-Reputation pro Faction (-100..+100)
- Stufen-Overlay für UI: hostile/unfriendly/neutral/friendly/allied
- Propagation: Aktion auf Faction A → 30% Auswirkung auf verbündete/feindliche

Default-Factions:
    villagers      — friedliche Dorfbewohner (neutral start)
    goblins        — feindlich (hostile start)
    bandits        — feindlich (hostile start)
    kings_guard    — Ordnungsmacht (neutral start)
    merchants_guild — Händler (neutral, freut sich über Gold)
    arcane_circle  — Magier-Zirkel (neutral)
"""
import json
import logging

import db

log = logging.getLogger("liege.factions")

PROPAGATION_FACTOR = 0.3   # 30% der Aktion schwingt auf Verbündete/Feinde
GOODWILL_MIN = -100
GOODWILL_MAX = 100


# Default-Factions (auto-seeded beim init)
DEFAULT_FACTIONS = {
    "villagers": {
        "name": "Dorfbewohner", "color": "#a0c060",
        "description": "Friedliche Bauern und Handwerker. Schätzen Hilfe und Höflichkeit.",
        "natural_min": 0, "natural_max": 50,
    },
    "goblins": {
        "name": "Goblin-Sippe", "color": "#60a040",
        "description": "Wilde Räuberbande, immer auf Beute aus.",
        "natural_min": -90, "natural_max": -40,
    },
    "bandits": {
        "name": "Räuberbande", "color": "#8a3030",
        "description": "Vertriebene und Verbrecher, leben vom Überfall.",
        "natural_min": -80, "natural_max": -30,
    },
    "kings_guard": {
        "name": "Wache des Königs", "color": "#4060a0",
        "description": "Ordnungsmacht. Belohnt Loyalität, straft Verbrechen.",
        "natural_min": -20, "natural_max": 40,
    },
    "merchants_guild": {
        "name": "Händlergilde", "color": "#c0a040",
        "description": "Verbund reicher Händler. Geld öffnet jede Tür.",
        "natural_min": -10, "natural_max": 60,
    },
    "arcane_circle": {
        "name": "Arkaner Zirkel", "color": "#8060c0",
        "description": "Magier und Gelehrte. Wertschätzen Wissen über Gold.",
        "natural_min": -10, "natural_max": 50,
    },
    "undead_cult": {
        "name": "Kult der Toten", "color": "#603060",
        "description": "Düstere Anhänger uralter Mächte. Niemand vertraut ihnen.",
        "natural_min": -80, "natural_max": -20,
    },
    "wild_beasts": {
        "name": "Wilde Tiere", "color": "#705030",
        "description": "Wölfe, Bären, Bestien des Waldes.",
        "natural_min": -50, "natural_max": -10,
    },
}

# Initiale Beziehungen zwischen Factions (-100..+100)
DEFAULT_RELATIONS = [
    ("villagers", "kings_guard",    50),
    ("villagers", "merchants_guild", 30),
    ("villagers", "goblins",        -60),
    ("villagers", "bandits",        -70),
    ("villagers", "undead_cult",    -80),
    ("kings_guard", "bandits",      -90),
    ("kings_guard", "goblins",      -80),
    ("kings_guard", "undead_cult",  -90),
    ("merchants_guild", "bandits",  -50),
    ("goblins", "wild_beasts",       40),
    ("arcane_circle", "undead_cult", -40),
    ("arcane_circle", "kings_guard",  20),
]

# NPC-Kind → Default-Faction
NPC_KIND_FACTIONS = {
    "wanderer":    "villagers",
    "villager":    "villagers",
    "farmer":      "villagers",
    "merchant":    "merchants_guild",
    "blacksmith":  "villagers",
    "hermit":      None,            # neutral
    "bard":        "villagers",
    "scholar":     "arcane_circle",
    "mage":        "arcane_circle",
    "healer":      "villagers",
    "soldier":     "kings_guard",
    "guard":       "kings_guard",
    "quest_giver": "villagers",
    # Hostile
    "goblin":      "goblins",
    "wolf":        "wild_beasts",
    "bear":        "wild_beasts",
    "boar":        "wild_beasts",
    "bat":         "wild_beasts",
    "rat":         "wild_beasts",
    "spider":      "wild_beasts",
    "skeleton":    "undead_cult",
    "zombie":      "undead_cult",
    "necromancer": "undead_cult",
    "bandit":      "bandits",
    "robber":      "bandits",
    "thief":       "bandits",
    "slime":       None,
    "ogre":        None,
    "dragon_whelp":None,
    # — Welle 14 — professional asset-drop (2026-05-26b) —
    # Tiere / Bestien → wild_beasts
    "razorback_vermin":      "wild_beasts",
    "reed_walker":           "wild_beasts",
    "redland_scavenger":     "wild_beasts",
    "mossback_warden":       "wild_beasts",
    "mantis_chimera":        "wild_beasts",
    "dendroid_guardian":     "wild_beasts",
    "blood_antler_drake":    "wild_beasts",
    "kaiju_thornback":       "wild_beasts",
    "frost_rune_boar_prime": "wild_beasts",
    # Untot
    "grave_wraith":          "undead_cult",
    # Magisch / eldritch — keine klare Faction
    "spined_abyss_larva":    None,
    "serpent_oracle":        None,
    "urtikus_eye_fiend":     None,
    "iron_spider":           None,
    "void_eye_brute":        None,
    "magma_shell_devourer":  None,
    "rockshell_colossus":    None,
    # — Asset-Drop 2026-05-27b: Nutztiere (Livestock + Poultry) → villagers —
    "cow":           "villagers", "bull":         "villagers", "calf":          "villagers",
    "ox":            "villagers", "sheep":        "villagers", "ram":           "villagers",
    "lamb":          "villagers", "sheared_sheep":"villagers", "pig":           "villagers",
    "piglet":        "villagers", "boar_domestic":"villagers", "goat":          "villagers",
    "buck_goat":     "villagers", "kid_goat":     "villagers", "horse":         "villagers",
    "draft_horse":   "villagers", "foal":         "villagers", "donkey":        "villagers",
    "mule":          "villagers",
    "chicken_hen":   "villagers", "rooster":      "villagers", "chick":         "villagers",
    "duck":          "villagers", "drake":        "villagers", "duckling":      "villagers",
    "goose":         "villagers", "gander":       "villagers", "gosling":       "villagers",
}


SCHEMA = """
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
"""


def reputation_tier(goodwill: int) -> str:
    if goodwill <= -75: return "hostile"
    if goodwill <= -25: return "unfriendly"
    if goodwill <= 24:  return "neutral"
    if goodwill <= 74:  return "friendly"
    return "allied"


def clamp(v: int) -> int:
    return max(GOODWILL_MIN, min(GOODWILL_MAX, v))


# — Seeding ——————————————————————————————————————————————————————————————

async def seed_defaults() -> None:
    """Idempotentes Seeding der Default-Faktionen + Relationen."""
    for fid, cfg in DEFAULT_FACTIONS.items():
        await db.pool().execute(
            "INSERT INTO factions (id, name, description, color, natural_min, natural_max) "
            "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO NOTHING",
            fid, cfg["name"], cfg["description"], cfg["color"],
            cfg["natural_min"], cfg["natural_max"],
        )
    for a, b, gw in DEFAULT_RELATIONS:
        # Sortieren weil CHECK (a < b)
        fa, fb = (a, b) if a < b else (b, a)
        await db.pool().execute(
            "INSERT INTO faction_relations (faction_a_id, faction_b_id, goodwill) "
            "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            fa, fb, gw,
        )
    log.info("Factions seeded: %d factions, %d relations",
             len(DEFAULT_FACTIONS), len(DEFAULT_RELATIONS))


# — Spieler-Reputation —————————————————————————————————————————————————

async def get_reputation(player_name: str, faction_id: str) -> int:
    row = await db.pool().fetchrow(
        "SELECT goodwill FROM player_faction_reputation "
        "WHERE player_name = $1 AND faction_id = $2",
        player_name, faction_id,
    )
    return int(row["goodwill"]) if row else 0


async def list_all_reputations(player_name: str) -> list[dict]:
    rows = await db.pool().fetch(
        "SELECT f.id, f.name, f.color, "
        "COALESCE(r.goodwill, 0) AS goodwill, r.updated_at "
        "FROM factions f "
        "LEFT JOIN player_faction_reputation r "
        "  ON r.faction_id = f.id AND r.player_name = $1 "
        "ORDER BY f.name",
        player_name,
    )
    return [
        {"id": r["id"], "name": r["name"], "color": r["color"],
         "goodwill": r["goodwill"], "tier": reputation_tier(r["goodwill"])}
        for r in rows
    ]


async def _adjust_one(player_name: str, faction_id: str, delta: int,
                       reason: str) -> tuple[int, int, bool]:
    """Direkte Reputations-Änderung. Returns (old, new, tier_changed)."""
    old = await get_reputation(player_name, faction_id)
    new = clamp(old + delta)
    await db.pool().execute(
        "INSERT INTO player_faction_reputation (player_name, faction_id, goodwill) "
        "VALUES ($1, $2, $3) "
        "ON CONFLICT (player_name, faction_id) DO UPDATE "
        "SET goodwill = $3, updated_at = NOW()",
        player_name, faction_id, new,
    )
    await db.pool().execute(
        "INSERT INTO reputation_events (player_name, faction_id, delta, reason) "
        "VALUES ($1, $2, $3, $4)",
        player_name, faction_id, new - old, reason[:200],
    )
    tier_changed = reputation_tier(old) != reputation_tier(new)
    return old, new, tier_changed


async def _get_related_factions(faction_id: str) -> list[tuple[str, int]]:
    """Liste (other_id, goodwill) aller Beziehungen dieser Faction."""
    rows = await db.pool().fetch(
        "SELECT faction_a_id, faction_b_id, goodwill FROM faction_relations "
        "WHERE faction_a_id = $1 OR faction_b_id = $1",
        faction_id,
    )
    out = []
    for r in rows:
        other = r["faction_b_id"] if r["faction_a_id"] == faction_id else r["faction_a_id"]
        out.append((other, int(r["goodwill"])))
    return out


async def apply_action(player_name: str, faction_id: str, delta: int,
                        reason: str) -> dict:
    """Hauptfunktion: Spieler-Aktion verändert Reputation + propagiert.
    Returns {direct: [(faction, old, new, tier_changed)], propagated: [...]}.
    """
    if not faction_id:
        return {"direct": [], "propagated": []}
    direct = []
    propagated = []
    # 1) Direkter Effekt
    old, new, tier_changed = await _adjust_one(player_name, faction_id, delta, reason)
    direct.append((faction_id, old, new, tier_changed))
    # 2) Propagation entlang faction_relations
    related = await _get_related_factions(faction_id)
    for other_id, rel_goodwill in related:
        if rel_goodwill > 50:
            # Verbündete: gleichgerichteter Effekt
            p_delta = int(delta * PROPAGATION_FACTOR)
            if p_delta == 0: continue
            o, n, tc = await _adjust_one(player_name, other_id, p_delta,
                                          f"ally_of:{faction_id}")
            propagated.append((other_id, o, n, tc))
        elif rel_goodwill < -50:
            # Feinde: inverser Effekt
            p_delta = int(-delta * PROPAGATION_FACTOR)
            if p_delta == 0: continue
            o, n, tc = await _adjust_one(player_name, other_id, p_delta,
                                          f"enemy_of:{faction_id}")
            propagated.append((other_id, o, n, tc))
    return {"direct": direct, "propagated": propagated}


# — NPC-Faction-Lookup ——————————————————————————————————————————————————

def faction_for_kind(npc_kind: str) -> str | None:
    return NPC_KIND_FACTIONS.get(npc_kind)


async def assign_faction_to_existing_npcs() -> int:
    """Setzt für NPCs ohne faction_id einen Default basierend auf kind."""
    rows = await db.pool().fetch(
        "SELECT id, kind FROM npcs WHERE faction_id IS NULL"
    )
    updated = 0
    for r in rows:
        fid = faction_for_kind(r["kind"])
        if fid:
            await db.pool().execute(
                "UPDATE npcs SET faction_id = $1 WHERE id = $2", fid, r["id"]
            )
            updated += 1
    return updated
