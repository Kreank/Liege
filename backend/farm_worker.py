import asyncio
import logging
import os
from datetime import timedelta

import db

log = logging.getLogger("liege.farm_worker")

GROWTH_TICK_SECONDS = int(os.environ.get("FARM_GROWTH_TICK_SECONDS", "30"))
GROWTH_DURATION_SECONDS = int(os.environ.get("FARM_GROWTH_DURATION_SECONDS", "60"))
# Welle 17: Bewässerung muss innerhalb dieser Zeit erfolgt sein damit gewachsen wird
WATER_VALIDITY_SECONDS = int(os.environ.get("FARM_WATER_VALIDITY_SECONDS", "600"))


async def run(item_manager, connection_manager) -> None:
    log.info("Farm-Worker startet (tick=%ds, growth=%ds, water_validity=%ds)",
             GROWTH_TICK_SECONDS, GROWTH_DURATION_SECONDS, WATER_VALIDITY_SECONDS)
    while True:
        try:
            await asyncio.sleep(GROWTH_TICK_SECONDS)
            rows = await db.pool().fetch(
                "SELECT p.structure_id, p.plant_kind, s.x, s.y "
                "FROM plantings p JOIN structures s ON s.id = p.structure_id "
                "WHERE p.planted_at < NOW() - $1::interval "
                "  AND p.last_watered_at IS NOT NULL "
                "  AND p.last_watered_at > NOW() - $2::interval",
                timedelta(seconds=GROWTH_DURATION_SECONDS),
                timedelta(seconds=WATER_VALIDITY_SECONDS),
            )
            for r in rows:
                # Check ob da schon was am Boden ist (vermeidet double-spawn bei langen Outages)
                existing = await db.pool().fetchrow(
                    "SELECT id FROM items WHERE x = $1 AND y = $2 AND owner IS NULL "
                    "AND kind = $3 LIMIT 1",
                    r["x"], r["y"], r["plant_kind"],
                )
                await db.pool().execute(
                    "DELETE FROM plantings WHERE structure_id = $1", r["structure_id"]
                )
                if existing:
                    continue
                spawned = await item_manager.spawn_on_ground(r["plant_kind"], r["x"], r["y"])
                if spawned is not None:
                    await connection_manager.broadcast({
                        "type": "item_spawned", "item": spawned,
                    })
                    # Welle 50: harvest_crop-Pop am Feld, wenn die Pflanze reif ist
                    await connection_manager.broadcast({
                        "type": "visual_effect", "kind": "wp_harvest_crop",
                        "x": r["x"], "y": r["y"],
                    })
                    log.info("Pflanze gewachsen: %s @ (%d, %d)",
                             r["plant_kind"], r["x"], r["y"])
                    # Farming-XP an den Acker-Besitzer (Struktur-Owner)
                    try:
                        owner_row = await db.pool().fetchrow(
                            "SELECT owner FROM structures WHERE id = $1", r["structure_id"]
                        )
                        if owner_row and owner_row["owner"] not in (None, "system"):
                            import skills as _skills
                            await _skills.gain_xp(owner_row["owner"], "farming", 15)
                    except Exception:
                        log.debug("Farming-XP-Hook fehlgeschlagen", exc_info=True)
        except asyncio.CancelledError:
            log.info("Farm-Worker gestoppt")
            raise
        except Exception:
            log.exception("Farm-Worker-Iteration fehlgeschlagen")
