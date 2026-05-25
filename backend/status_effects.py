"""Status-Effekte für Spieler und NPCs.

Effekte sind zeitlich begrenzt und ticken periodisch:
    burning   — DoT (Feuer-Schaden)
    poisoned  — DoT (Gift)
    bleeding  — DoT (langsam, lang)
    blessed   — HoT (heilung)
    shielded  — reduziert eingehenden Schaden (Faktor)
    slowed    — reduziert NPC-Movement-Chance

Aktuell only Player-Side implementiert; NPC-Effekte folgen.
"""
import asyncio
import json
import logging
import time
from datetime import timedelta

import db

log = logging.getLogger("liege.status_effects")


SCHEMA = """
CREATE TABLE IF NOT EXISTS status_effects (
    id            BIGSERIAL PRIMARY KEY,
    target_type   TEXT NOT NULL,   -- 'player' oder 'npc'
    target_id     TEXT NOT NULL,   -- player_name oder npc_id (als TEXT)
    effect        TEXT NOT NULL,
    magnitude     INTEGER NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS status_effects_target_idx
    ON status_effects (target_type, target_id, expires_at);
"""


EFFECT_TICK_SECONDS = 3

# Welche Effekte ticken DoT und mit welchem damage_per_tick (relativ zu magnitude)
DOT_EFFECTS = {
    "burning":  1.0,
    "poisoned": 0.5,
    "bleeding": 0.3,
}
HOT_EFFECTS = {
    "blessed":  1.0,
}


def _row_to_dict(row) -> dict:
    return {
        "id":          row["id"],
        "target_type": row["target_type"],
        "target_id":   row["target_id"],
        "effect":      row["effect"],
        "magnitude":   row["magnitude"],
        "expires_at":  row["expires_at"].isoformat(),
    }


async def apply(target_type: str, target_id: str, effect: str,
                magnitude: int, duration_seconds: int) -> dict:
    """Fügt einen Status-Effekt hinzu. Wenn ein gleichnamiger existiert,
    wird Magnitude addiert und Expiry verlängert."""
    existing = await db.pool().fetchrow(
        "SELECT id, magnitude FROM status_effects "
        "WHERE target_type = $1 AND target_id = $2 AND effect = $3 "
        "ORDER BY expires_at DESC LIMIT 1",
        target_type, target_id, effect,
    )
    delta = timedelta(seconds=duration_seconds)
    if existing:
        row = await db.pool().fetchrow(
            "UPDATE status_effects "
            "SET magnitude = magnitude + $2, "
            "    expires_at = GREATEST(expires_at, NOW() + $3::interval) "
            "WHERE id = $1 "
            "RETURNING id, target_type, target_id, effect, magnitude, expires_at",
            existing["id"], magnitude, delta,
        )
    else:
        row = await db.pool().fetchrow(
            "INSERT INTO status_effects (target_type, target_id, effect, magnitude, expires_at) "
            "VALUES ($1, $2, $3, $4, NOW() + $5::interval) "
            "RETURNING id, target_type, target_id, effect, magnitude, expires_at",
            target_type, target_id, effect, magnitude, delta,
        )
    return _row_to_dict(row)


async def list_for_target(target_type: str, target_id: str) -> list[dict]:
    rows = await db.pool().fetch(
        "SELECT id, target_type, target_id, effect, magnitude, expires_at "
        "FROM status_effects "
        "WHERE target_type = $1 AND target_id = $2 AND expires_at > NOW() "
        "ORDER BY id",
        target_type, target_id,
    )
    return [_row_to_dict(r) for r in rows]


async def cleanup_expired() -> int:
    row = await db.pool().fetchrow(
        "DELETE FROM status_effects WHERE expires_at <= NOW() RETURNING 1",
    )
    return 1 if row else 0


async def damage_reduction_for(target_type: str, target_id: str) -> float:
    """Returns Faktor 0..1 — 1.0 = kein Schutz, 0.5 = halb so viel Schaden."""
    rows = await db.pool().fetch(
        "SELECT magnitude FROM status_effects "
        "WHERE target_type = $1 AND target_id = $2 AND effect = 'shielded' "
        "AND expires_at > NOW()",
        target_type, target_id,
    )
    if not rows:
        return 1.0
    # Magnitude 50 == 50% Reduktion
    total = sum(r["magnitude"] for r in rows)
    return max(0.1, 1.0 - min(0.9, total / 100.0))


async def run(connection_manager, damage_player_cb, heal_player_cb) -> None:
    """Periodischer Worker: tickt DOT/HOT-Effekte für alle Spieler."""
    log.info("Status-Effekt-Worker startet (tick=%ds)", EFFECT_TICK_SECONDS)
    while True:
        try:
            await asyncio.sleep(EFFECT_TICK_SECONDS)
            await cleanup_expired()
            # Pro aktivem Spieler alle DOT/HOT-Effekte anwenden
            players = list(connection_manager.get_players().keys())
            for name in players:
                effects = await list_for_target("player", name)
                if not effects:
                    continue
                # WS-Update über aktive Effekte
                ws = connection_manager.connections.get(name)
                if ws is not None:
                    try:
                        await ws.send_json({
                            "type":    "status_effects",
                            "effects": effects,
                        })
                    except Exception:
                        log.debug("status_effects send fehlgeschlagen für %s", name)
                # DoT
                for eff in effects:
                    factor = DOT_EFFECTS.get(eff["effect"])
                    if factor is not None:
                        dmg = max(1, int(eff["magnitude"] * factor))
                        try:
                            await damage_player_cb(name, dmg)
                        except Exception:
                            log.exception("DoT-Damage für %s schlug fehl", name)
                    hot_factor = HOT_EFFECTS.get(eff["effect"])
                    if hot_factor is not None:
                        heal = max(1, int(eff["magnitude"] * hot_factor))
                        try:
                            await heal_player_cb(name, heal)
                        except Exception:
                            log.exception("HoT-Heal für %s schlug fehl", name)
        except asyncio.CancelledError:
            log.info("Status-Effekt-Worker gestoppt")
            raise
        except Exception:
            log.exception("Status-Effekt-Worker-Iteration fehlgeschlagen")
