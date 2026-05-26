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


async def weather_loop(connection_manager) -> None:
    log.info("Wetter-Worker startet (tick=%ds)", WEATHER_TICK_SECONDS)
    # Erste Phase nach kurzer Verzögerung
    await asyncio.sleep(30)
    current_phase = "clear"
    current_intensity = 0
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
            await asyncio.sleep(WEATHER_TICK_SECONDS)
        except asyncio.CancelledError:
            log.info("Wetter-Worker gestoppt")
            raise
        except Exception:
            log.exception("Wetter-Worker-Iteration fehlgeschlagen")
            await asyncio.sleep(WEATHER_TICK_SECONDS)
