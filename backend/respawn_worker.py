"""Welt-Respawn: Bäume/Felsen wachsen über Zeit nach.

Iteriert periodisch über bekannte Chunks, prüft pro Chunk die Dichte
natürlicher Deko und spawnt fehlende nach."""

import asyncio
import logging
import os
import random

import harvest as harvest_module
import world_populator
from world import CHUNK_SIZE

log = logging.getLogger("liege.respawn_worker")

RESPAWN_TICK_SECONDS = int(os.environ.get("WORLD_RESPAWN_TICK_SECONDS", "300"))
RESPAWN_PER_TICK = int(os.environ.get("WORLD_RESPAWN_PER_TICK", "15"))


async def run(world, structure_manager, connection_manager) -> None:
    """Spawnt periodisch ein paar Bäume/Felsen/Gräser in geladenen Chunks."""
    log.info("Welt-Respawn-Worker startet (tick=%ds, per-tick=%d)",
             RESPAWN_TICK_SECONDS, RESPAWN_PER_TICK)
    await asyncio.sleep(60)
    while True:
        try:
            await asyncio.sleep(RESPAWN_TICK_SECONDS)
            cached = world.chunks_in_cache()
            if not cached:
                continue
            placed = 0
            attempts = 0
            while placed < RESPAWN_PER_TICK and attempts < RESPAWN_PER_TICK * 5:
                attempts += 1
                cx, cy = random.choice(cached)
                chunk = await world.get_chunk(cx, cy)
                lx = random.randint(0, CHUNK_SIZE - 1)
                ly = random.randint(0, CHUNK_SIZE - 1)
                wx = cx * CHUNK_SIZE + lx
                wy = cy * CHUNK_SIZE + ly
                tile = chunk[ly][lx]
                if tile in (0, 4, 7):  # Wasser, Berg, Lava skip
                    continue
                if structure_manager.at(wx, wy) is not None:
                    continue
                chosen = world_populator._pick_for_tile(world, wx, wy, tile)
                if chosen is None:
                    continue
                dur = harvest_module.initial_durability(chosen)
                struct = await structure_manager.place(
                    wx, wy, chosen, "system", material="stone", durability=dur
                )
                if struct is not None:
                    placed += 1
                    await connection_manager.broadcast({
                        "type": "structure_placed", "structure": struct,
                    })
            if placed > 0:
                log.info("Welt-Respawn: %d Strukturen nachgewachsen", placed)
        except asyncio.CancelledError:
            log.info("Welt-Respawn-Worker gestoppt")
            raise
        except Exception:
            log.exception("Welt-Respawn-Iteration fehlgeschlagen")
