"""Player-Stat-Sheet Persistierung + Allokation (Welle 15).

Build auf attributes.py auf — DB-Layer für die ELEMENT-Resistances und für
Stat-Allocation, die der Spieler beim Level-Up bekommt.

Stat-Sheet = {
    "attributes": {de_name: int},     # 12 derived (aus attributes.calculate_attributes)
    "allocated":  {de_name: int},     # vom User verteilt — Modifier auf attributes
    "totals":     {de_name: int},     # attributes + allocated
    "resistances": {                  # gesamt = base_from_columns + equipped affixes
        "fire": int, "ice": int, "lightning": int, "necrotic": int, "magic": int,
    },
    "unspent_points": int,
}
"""
import json
import logging

import db
import skills as _skills
import attributes as _attrs

log = logging.getLogger("liege.player_stats")

# Wie viele Attr-Punkte pro Skill-Level. 1 = sehr großzügig (~110 Punkte bei
# allen Skills auf 10). Reduzieren wenn Inflation.
POINTS_PER_LEVEL = 1
# Max-Allocation pro einzelnem Attribut (Hard-Cap gegen All-Stärke-Builds)
PER_ATTR_CAP = 50

# Valide Attr-Namen (gleich wie in attributes.py)
ATTR_NAMES = list(_attrs.ATTR_LABELS.keys())

RESIST_KEYS = ["fire_resist", "ice_resist", "lightning_resist",
               "necrotic_resist", "magic_resist"]

# Affix-Stat-Key → Resistance-Spalte. Affixes geben Equipped-Boni.
AFFIX_TO_RESIST = {
    "fire_resist_pct":      "fire_resist",
    "ice_resist_pct":       "ice_resist",
    "lightning_resist_pct": "lightning_resist",
    "necrotic_resist_pct":  "necrotic_resist",
    "magic_resist_pct":     "magic_resist",
}


async def grant_attr_points(player_name: str, n: int) -> None:
    """Beim Level-Up: addiere n freie Allocation-Punkte."""
    if n <= 0:
        return
    await db.pool().execute(
        "UPDATE players SET unspent_attr_points = unspent_attr_points + $1 "
        "WHERE name = $2",
        n, player_name,
    )


async def allocate_point(player_name: str, attr: str, n: int = 1) -> dict | None:
    """Verteile n Punkte auf ein Attribut. Returns updated state oder None bei
    Fehler. n kann negativ sein (Rücknahme), aber allocated[attr] >= 0."""
    if attr not in ATTR_NAMES:
        return {"error": "unknown_attr"}
    row = await db.pool().fetchrow(
        "SELECT unspent_attr_points, allocated_attrs FROM players WHERE name = $1",
        player_name,
    )
    if row is None:
        return {"error": "no_player"}
    raw = row["allocated_attrs"]
    allocated = raw if isinstance(raw, dict) else (json.loads(raw) if raw else {})
    unspent = int(row["unspent_attr_points"])
    cur = int(allocated.get(attr, 0))
    new_alloc = cur + n
    new_unspent = unspent - n
    if new_alloc < 0:
        return {"error": "negative"}
    if new_alloc > PER_ATTR_CAP:
        return {"error": "cap_reached"}
    if new_unspent < 0:
        return {"error": "not_enough_points"}
    allocated[attr] = new_alloc
    await db.pool().execute(
        "UPDATE players SET allocated_attrs = $1::jsonb, unspent_attr_points = $2 "
        "WHERE name = $3",
        json.dumps(allocated), new_unspent, player_name,
    )
    return {"ok": True, "allocated": allocated, "unspent": new_unspent}


async def get_stat_sheet(player_name: str, equipped_items: list[dict],
                         talent_effects: dict, body_parts: dict | None) -> dict:
    """Vollständiges Stat-Sheet für UI. Caller liefert bereits-aggregiertes
    equipped + talents + body_parts."""
    row = await db.pool().fetchrow(
        "SELECT allocated_attrs, unspent_attr_points, "
        "fire_resist, ice_resist, lightning_resist, necrotic_resist, magic_resist "
        "FROM players WHERE name = $1",
        player_name,
    )
    raw = (row["allocated_attrs"] if row else {}) or {}
    allocated = raw if isinstance(raw, dict) else json.loads(raw)
    unspent = int(row["unspent_attr_points"]) if row else 0

    # Skills laden für attributes-Berechnung
    skills_dict = await _skills.get_skills(player_name)
    attrs = _attrs.calculate_attributes(skills_dict, equipped_items,
                                        talent_effects, body_parts)
    totals = {k: attrs.get(k, 0) + int(allocated.get(k, 0)) for k in ATTR_NAMES}

    # Resistances: Basis aus Player-DB + Affixe von equipped
    base_resists = {
        "fire":      int(row["fire_resist"]) if row else 0,
        "ice":       int(row["ice_resist"]) if row else 0,
        "lightning": int(row["lightning_resist"]) if row else 0,
        "necrotic":  int(row["necrotic_resist"]) if row else 0,
        "magic":     int(row["magic_resist"]) if row else 0,
    }
    for it in equipped_items:
        for af in it.get("affixes", []) or []:
            for sk, sv in (af.get("stats") or {}).items():
                target = AFFIX_TO_RESIST.get(sk)
                if target:
                    # Resist-Werte direkt addieren (sind in %)
                    key = target.replace("_resist", "")
                    base_resists[key] = base_resists.get(key, 0) + int(sv)

    return {
        "attributes": attrs,
        "allocated":  allocated,
        "totals":     totals,
        "resistances": base_resists,
        "unspent_points": unspent,
    }


async def player_resistance(player_name: str, dmg_type: str) -> int:
    """Schnell-Lookup für damage_player(): nur Resistance gegen einen einzelnen
    Element/Magic-Typ. Affixe von equipped werden nicht zusätzlich addiert hier
    (das wäre teuer pro Hit) — nur die DB-Spalte. Affix-Bonus passiert pro
    Equip-Wechsel via apply_equipment_to_resists()."""
    key = f"{dmg_type}_resist"
    if key not in RESIST_KEYS:
        return 0
    row = await db.pool().fetchrow(
        f"SELECT {key} AS r FROM players WHERE name = $1", player_name,
    )
    return int(row["r"]) if row else 0


def apply_resist_to_damage(raw: int, resist_pct: int) -> int:
    """Wendet Resist auf einen Roh-Schaden an. Mindestens 1 wenn raw > 0."""
    if raw <= 0:
        return 0
    factor = max(0.0, (100 - resist_pct) / 100.0)
    return max(1, int(round(raw * factor)))
