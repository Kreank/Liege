"""Globaler State für aktive Welt-Disaster — Welle 24 (2026-05-27).

Persistenter Flag-Store, der Catastrophe/Cataclysm-Events mit echter Dauer
und Game-Effekten erlaubt. Beispiel: Blutmond aktivieren für 1 Game-Stunde
→ mob_damage × 1.3, mob-spawn-rate × 2.

Lookup-Pfad: Spieler-Damage-Berechnung, Spawn-Loop, Needs-Worker prüfen
`is_active("blood_moon")` etc.

Persistiert in DB damit Server-Restart die laufenden Disasters nicht reset.
"""
import logging
import time
from typing import Optional

import db

log = logging.getLogger("liege.disaster_state")


# Bekannte Disaster-Kinds + Default-Dauer (Sekunden Echtzeit)
DISASTER_DEFAULT_DURATION = {
    "blood_moon":   1800,    # 30 min Echtzeit ≈ 1 Game-Stunde
    "dying_sun":    1800,    # 30 min
    "plague":       1200,    # 20 min
    "wildfire":     180,     # 3 min initial — Brand-Effekt läuft danach via fire_tiles weiter
    "tainted_well": 1800,    # 30 min
    "locust":       300,     # 5 min Schwarm wandert
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS disaster_state (
    kind         TEXT PRIMARY KEY,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL,
    metadata     JSONB
);
"""

# In-memory Cache für schnellen is_active-Lookup (Hot-Path: jeder NPC-Attack ruft das)
_CACHE: dict[str, float] = {}     # kind -> expires_at_unix
_CACHE_REFRESH_AT = 0.0
_CACHE_TTL = 5.0                  # alle 5s frisch aus DB ziehen


async def init_schema() -> None:
    await db.pool().execute(SCHEMA)
    await _refresh_cache()


async def _refresh_cache() -> None:
    global _CACHE_REFRESH_AT
    rows = await db.pool().fetch(
        "SELECT kind, EXTRACT(EPOCH FROM expires_at) AS exp_s FROM disaster_state "
        "WHERE expires_at > NOW()"
    )
    new_cache: dict[str, float] = {}
    for r in rows:
        new_cache[r["kind"]] = float(r["exp_s"])
    _CACHE.clear()
    _CACHE.update(new_cache)
    _CACHE_REFRESH_AT = time.time()


async def activate(kind: str, duration_s: Optional[int] = None,
                    metadata: Optional[dict] = None) -> dict:
    """Startet (oder verlängert) ein Disaster. Returns Status-Dict für Broadcast."""
    if duration_s is None:
        duration_s = DISASTER_DEFAULT_DURATION.get(kind, 600)
    import json as _json
    meta_json = _json.dumps(metadata) if metadata else None
    await db.pool().execute(
        "INSERT INTO disaster_state (kind, expires_at, metadata) "
        "VALUES ($1, NOW() + ($2 || ' seconds')::INTERVAL, $3::jsonb) "
        "ON CONFLICT (kind) DO UPDATE SET "
        "  expires_at = NOW() + ($2 || ' seconds')::INTERVAL, "
        "  metadata = $3::jsonb",
        kind, str(int(duration_s)), meta_json,
    )
    await _refresh_cache()
    log.info("Disaster aktiviert: %s (Dauer %ds, meta=%s)", kind, duration_s, metadata)
    return {"kind": kind, "duration_s": int(duration_s), "metadata": metadata or {}}


async def deactivate(kind: str) -> None:
    await db.pool().execute("DELETE FROM disaster_state WHERE kind = $1", kind)
    _CACHE.pop(kind, None)
    log.info("Disaster deaktiviert: %s", kind)


def is_active(kind: str) -> bool:
    """Hot-path Lookup — nutzt In-Memory-Cache. Cache wird alle 5s refresht.

    SYNC weil aus Hot-Path (combat) gerufen. Wenn Cache stale ist (>5s), wird
    er beim nächsten async-Tick refresht — kurzer Lag akzeptabel."""
    now = time.time()
    exp = _CACHE.get(kind)
    if exp is None:
        return False
    if exp < now:
        _CACHE.pop(kind, None)
        return False
    return True


async def tick() -> None:
    """Wird alle ~10s vom Disaster-Tick-Loop gerufen. Refresht Cache + räumt
    abgelaufene Disasters auf."""
    await db.pool().execute("DELETE FROM disaster_state WHERE expires_at <= NOW()")
    await _refresh_cache()


async def list_active() -> list[dict]:
    rows = await db.pool().fetch(
        "SELECT kind, EXTRACT(EPOCH FROM (expires_at - NOW())) AS remaining_s, metadata "
        "FROM disaster_state WHERE expires_at > NOW()"
    )
    return [{"kind": r["kind"], "remaining_s": float(r["remaining_s"]),
             "metadata": r["metadata"]} for r in rows]


async def run(connection_manager) -> None:
    """Periodischer Tick-Loop. Refresht Cache + broadcastet Disaster-Ended-Events
    wenn ein Flag abläuft, damit das Frontend Tints/Overlays wegnimmt."""
    import asyncio
    log.info("Disaster-Tick-Loop startet (tick=10s)")
    last_active: set[str] = set(_CACHE.keys())
    while True:
        try:
            await asyncio.sleep(10)
            await tick()
            now_active = set(_CACHE.keys())
            ended = last_active - now_active
            for kind in ended:
                try:
                    await connection_manager.broadcast({
                        "type": "disaster_ended", "kind": kind,
                    })
                    log.info("Disaster vorbei: %s", kind)
                except Exception:
                    pass
            last_active = now_active
        except asyncio.CancelledError:
            log.info("Disaster-Tick-Loop gestoppt")
            raise
        except Exception:
            log.exception("Disaster-Tick-Iteration fehlgeschlagen")
