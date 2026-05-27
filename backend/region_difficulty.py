"""Region-Difficulty — Welle 23 Hook für Stage-2 World-Brain-Integration.

Pro Region (Chunk-Cluster) speichert eine DB-Tabelle einen Schwierigkeits-
Modifier-Block. Der Storyteller / das LLM kann hier reinschreiben:
    {"hp_mod": 1.4, "dmg_mod": 1.2, "tier_bias": 1, "reason": "Boss kürzlich besiegt"}

Spawn-Pfade lesen das via region_modifier(x, y). Aktuell sind alle Defaults
1.0 / 0 — bis das Gruppen-System steht und der Storyteller schreibt.

Region-Größe: 4×4 Chunks = 128×128 Tiles. Passt zu region_history.py.
"""
import logging
from typing import Dict, Optional

import db

log = logging.getLogger("liege.region_difficulty")

REGION_TILE_SIZE = 128       # 4 Chunks × 32 Tiles

DEFAULT_MODIFIER = {
    "hp_mod":    1.0,
    "dmg_mod":   1.0,
    "tier_bias": 0,      # +1 = öfter höheres Tier, -1 = öfter niedrigeres
    "reason":    None,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS region_difficulty (
    region_x    INTEGER NOT NULL,
    region_y    INTEGER NOT NULL,
    hp_mod      REAL NOT NULL DEFAULT 1.0,
    dmg_mod     REAL NOT NULL DEFAULT 1.0,
    tier_bias   INTEGER NOT NULL DEFAULT 0,
    reason      TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (region_x, region_y)
);
CREATE INDEX IF NOT EXISTS region_difficulty_updated_idx
    ON region_difficulty (updated_at DESC);
"""


def region_for_world(x: int, y: int) -> tuple[int, int]:
    """Welt-Koordinaten → Region-Koordinaten (4×4 Chunk-Block)."""
    return (x // REGION_TILE_SIZE, y // REGION_TILE_SIZE)


async def get_modifier_for_world_pos(x: int, y: int) -> Dict:
    """Lädt Modifier für die Region, in der (x, y) liegt. Defaults wenn nichts
    gesetzt ist."""
    rx, ry = region_for_world(x, y)
    return await get_modifier(rx, ry)


async def get_modifier(region_x: int, region_y: int) -> Dict:
    try:
        row = await db.pool().fetchrow(
            "SELECT hp_mod, dmg_mod, tier_bias, reason "
            "FROM region_difficulty WHERE region_x = $1 AND region_y = $2",
            region_x, region_y,
        )
    except Exception:
        return dict(DEFAULT_MODIFIER)
    if not row:
        return dict(DEFAULT_MODIFIER)
    return {
        "hp_mod":    float(row["hp_mod"]),
        "dmg_mod":   float(row["dmg_mod"]),
        "tier_bias": int(row["tier_bias"]),
        "reason":    row["reason"],
    }


async def set_modifier(region_x: int, region_y: int, *,
                       hp_mod: Optional[float] = None,
                       dmg_mod: Optional[float] = None,
                       tier_bias: Optional[int] = None,
                       reason: Optional[str] = None) -> None:
    """Storyteller / World-Brain ruft das auf, um eine Region zu rebalanced.
    None-Werte werden NICHT überschrieben."""
    existing = await get_modifier(region_x, region_y)
    new = {
        "hp_mod":    hp_mod    if hp_mod    is not None else existing["hp_mod"],
        "dmg_mod":   dmg_mod   if dmg_mod   is not None else existing["dmg_mod"],
        "tier_bias": tier_bias if tier_bias is not None else existing["tier_bias"],
        "reason":    reason    if reason    is not None else existing.get("reason"),
    }
    # Clamp auf sensible Range
    new["hp_mod"]    = max(0.3, min(3.0, new["hp_mod"]))
    new["dmg_mod"]   = max(0.3, min(2.5, new["dmg_mod"]))
    new["tier_bias"] = max(-2, min(2, new["tier_bias"]))
    await db.pool().execute(
        "INSERT INTO region_difficulty (region_x, region_y, hp_mod, dmg_mod, tier_bias, reason) "
        "VALUES ($1, $2, $3, $4, $5, $6) "
        "ON CONFLICT (region_x, region_y) DO UPDATE SET "
        "  hp_mod = $3, dmg_mod = $4, tier_bias = $5, reason = $6, updated_at = NOW()",
        region_x, region_y,
        new["hp_mod"], new["dmg_mod"], new["tier_bias"], new["reason"],
    )
    log.info("Region (%d,%d) modifier: hp×%.2f dmg×%.2f tier_bias=%d (%s)",
             region_x, region_y, new["hp_mod"], new["dmg_mod"],
             new["tier_bias"], new["reason"] or "—")


async def init_schema() -> None:
    """Wird beim Server-Start aufgerufen (db.init)."""
    await db.pool().execute(SCHEMA)
