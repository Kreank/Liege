"""Wetter-Worker: zufällige Wetter-Phasen, broadcasted an alle Clients.

Phasen: clear, rain, snow, fog, swamp_mist
Intensität: 0 (clear) bis 4 (Peak: downpour/blizzard, mit storm_lightning bei rain).

Frontend rendert stapelbar — bei intensity=3 werden light + medium + heavy
gleichzeitig animiert (siehe setWeather in index.html).

Aktuell global pro Welt (nicht pro Biome) — eine Wetterphase betrifft alle
verbundenen Spieler. Pro-Biome-Wetter wäre später möglich, würde aber pro
Spieler einen eigenen Sync brauchen."""

import asyncio
import logging
import os
import random

log = logging.getLogger("liege.weather_worker")

WEATHER_TICK_SECONDS = int(os.environ.get("WEATHER_TICK_SECONDS", "180"))  # 3 min

# Übergangs-Wahrscheinlichkeiten — clear ist häufiger als extremes Wetter
PHASE_WEIGHTS = [
    ("clear",      55),
    ("rain",       18),
    ("snow",       10),
    ("fog",         8),
    ("swamp_mist",  4),
]


def _pick_phase() -> str:
    kinds = [k for k, _ in PHASE_WEIGHTS]
    weights = [w for _, w in PHASE_WEIGHTS]
    return random.choices(kinds, weights=weights, k=1)[0]


def _pick_intensity(phase: str) -> int:
    if phase == "clear":
        return 0
    # Beim Wetter selbst: meistens leicht/mittel, selten heavy/peak
    return random.choices([1, 2, 3, 4], weights=[40, 35, 18, 7], k=1)[0]


async def weather_loop(connection_manager, world=None) -> None:
    log.info("Wetter-Worker startet (tick=%ds, real effects: rain→water plantings, "
             "storm→lightning strikes)", WEATHER_TICK_SECONDS)
    # Erste Phase nach kurzer Verzögerung
    await asyncio.sleep(30)
    current_phase = "clear"
    current_intensity = 0
    last_rain_tick = 0.0
    last_lightning_tick = 0.0
    import time as _time
    while True:
        try:
            next_phase = _pick_phase()
            next_intensity = _pick_intensity(next_phase)
            if (next_phase, next_intensity) != (current_phase, current_intensity):
                current_phase, current_intensity = next_phase, next_intensity
                await connection_manager.broadcast({
                    "type": "weather",
                    "phase": current_phase,
                    "intensity": current_intensity,
                })
                log.info("Wetter wechselt: %s intensity=%d",
                         current_phase, current_intensity)
            # Welle 24: Echte Wetter-Effekte
            now = _time.time()
            if current_phase == "rain" and current_intensity >= 1:
                if now - last_rain_tick >= 60:  # 1× pro Minute echte rain-Effekte
                    last_rain_tick = now
                    await _rain_water_plantings(connection_manager, current_intensity)
                if current_intensity >= 3 and now - last_lightning_tick >= 90:
                    # Bei storm/downpour: alle 90s 1 Lightning-Strike
                    last_lightning_tick = now
                    await _lightning_strike(connection_manager, world)
            await asyncio.sleep(WEATHER_TICK_SECONDS)
        except asyncio.CancelledError:
            log.info("Wetter-Worker gestoppt")
            raise
        except Exception:
            log.exception("Wetter-Worker-Iteration fehlgeschlagen")
            await asyncio.sleep(WEATHER_TICK_SECONDS)


async def _rain_water_plantings(connection_manager, intensity: int) -> None:
    """Regen wässert alle plantings im aktiven Spieler-Bereich."""
    import db
    players = list(connection_manager.get_players().values())
    if not players:
        return
    # Wässere plantings im Radius 40 Tiles um jeden Spieler
    total_updated = 0
    for p in players:
        try:
            result = await db.pool().execute(
                "UPDATE plantings SET last_watered_at = NOW() "
                "FROM structures "
                "WHERE plantings.structure_id = structures.id "
                "  AND structures.x BETWEEN $1 AND $2 "
                "  AND structures.y BETWEEN $3 AND $4",
                p["x"] - 40, p["x"] + 40, p["y"] - 40, p["y"] + 40,
            )
            # Anzahl von "UPDATE N" parsen
            if isinstance(result, str) and result.startswith("UPDATE "):
                total_updated += int(result.split()[1])
        except Exception:
            log.exception("Rain-Water-Update fehlgeschlagen für %s", p.get("name"))
    if total_updated > 0:
        log.info("Regen wässerte %d plantings (intensity=%d)", total_updated, intensity)


async def _lightning_strike(connection_manager, world=None) -> None:
    """Während eines Sturms: 1 Lightning-Strike auf ein Tile im Spieler-Range.
    Welle 53: Die Position wird gegen den Tile-Typ validiert — ein Blitz schlägt
    auf LAND ein, nicht sinnlos mitten im Wasser (Berge/Lava ebenfalls gemieden).
    Bis zu 8 Versuche; findet sich kein Land-Tile, wird der Strike übersprungen."""
    from world import WATER, MOUNTAIN, LAVA
    players = list(connection_manager.get_players().values())
    if not players:
        return
    p = random.choice(players)
    sx = sy = None
    for _try in range(8):
        # Strike-Position: 6-15 Tiles entfernt
        dx = random.randint(-15, 15)
        dy = random.randint(-15, 15)
        if abs(dx) < 6 and abs(dy) < 6:
            dx = (15 if dx >= 0 else -15)
        cx, cy = p["x"] + dx, p["y"] + dy
        if world is not None:
            try:
                if world.tile_at_sync(cx, cy) in (WATER, MOUNTAIN, LAVA):
                    continue   # kein Blitz im Wasser/Berg/Lava
            except Exception:
                pass
        sx, sy = cx, cy
        break
    if sx is None:
        return   # kein geeignetes Land-Tile gefunden — Strike auslassen
    await connection_manager.broadcast({
        "type": "lightning_strike", "x": sx, "y": sy,
    })
    # Schaden: alle Spieler auf genau diesem Tile (extrem unwahrscheinlich,
    # aber wenn → 15 lightning-dmg). Wir broadcasten den Strike visuell für
    # alle, der Damage ist nur für ein eventuell direkt getroffenes Ziel.
    log.info("Lightning strike at (%d,%d)", sx, sy)
