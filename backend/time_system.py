"""Game-Time-System: In-Game-Uhr läuft schneller als Realzeit.

Standard: 1 real-Sekunde = 2 In-Game-Minuten → ein In-Game-Tag = 12 Realminuten.
Phasen:
    morning  (06:00 - 09:00) — Aufwachen
    day      (09:00 - 17:00) — heller Tag
    evening  (17:00 - 21:00) — Abendrot
    night    (21:00 - 06:00) — Dunkelheit

WS-Broadcast `time_update` mit:
    minute_of_day (0..1439), hour (0..23), phase (string).
"""
import asyncio
import logging
import os
import time

log = logging.getLogger("liege.time_system")

MINUTES_PER_REAL_SECOND = float(os.environ.get("GAME_MINUTES_PER_SECOND", "2"))
TIME_BROADCAST_INTERVAL = float(os.environ.get("TIME_BROADCAST_INTERVAL", "5.0"))

# Welt-Start bei 08:00 (Morgen)
START_MINUTE_OF_DAY = 8 * 60


class GameClock:
    def __init__(self) -> None:
        self._epoch = time.monotonic()

    def minute_of_day(self) -> int:
        elapsed_real = time.monotonic() - self._epoch
        total_minutes = START_MINUTE_OF_DAY + elapsed_real * MINUTES_PER_REAL_SECOND
        return int(total_minutes) % (24 * 60)

    def hour(self) -> int:
        return self.minute_of_day() // 60

    def phase(self) -> str:
        h = self.hour()
        if 6 <= h < 9:
            return "morning"
        if 9 <= h < 17:
            return "day"
        if 17 <= h < 21:
            return "evening"
        return "night"

    def is_night(self) -> bool:
        return self.phase() == "night"


clock = GameClock()


def snapshot() -> dict:
    return {
        "minute_of_day": clock.minute_of_day(),
        "hour":          clock.hour(),
        "phase":         clock.phase(),
    }


async def run(connection_manager) -> None:
    """Broadcasted regelmäßig die Game-Time an alle verbundenen Clients."""
    log.info("Time-System startet (1 sec = %.1f Spielminuten, Broadcast alle %.1fs)",
             MINUTES_PER_REAL_SECOND, TIME_BROADCAST_INTERVAL)
    last_phase: str | None = None
    while True:
        try:
            await asyncio.sleep(TIME_BROADCAST_INTERVAL)
            snap = snapshot()
            await connection_manager.broadcast({
                "type": "time_update", **snap,
            })
            if snap["phase"] != last_phase:
                last_phase = snap["phase"]
                log.info("Welt-Phase wechselt: %s (Stunde %d)", snap["phase"], snap["hour"])
        except asyncio.CancelledError:
            log.info("Time-System gestoppt")
            raise
        except Exception:
            log.exception("Time-System-Iteration fehlgeschlagen")
