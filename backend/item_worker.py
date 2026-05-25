import asyncio
import logging
import os
import random

log = logging.getLogger("liege.item_worker")

ITEM_SPAWN_INTERVAL_SECONDS = int(os.environ.get("ITEM_SPAWN_INTERVAL_SECONDS", "60"))
ITEM_SPAWN_MAX = int(os.environ.get("ITEM_SPAWN_MAX", "30"))  # max Items gleichzeitig auf Boden

# Spawn-Verteilung: Resources häufig, Equipment selten
SPAWN_TABLE = (
    # (kind, weight)
    # Häufige Ressourcen
    ("wood",          20),
    ("stone",         18),
    ("herb",          15),
    ("bone",          10),
    ("cloth",         10),
    ("leather",       8),
    ("iron_ore",      8),
    ("silver_ore",    5),
    ("gold_ore",      4),
    ("crystal",       3),
    ("mythril_ore",   1),
    ("steel_ingot",   2),
    # Consumables
    ("health_potion", 6),
    ("mana_potion",   4),
    # Equipment (selten)
    ("sword",         2),
    ("axe",           2),
    ("bow",           2),
    ("staff",         2),
    ("helmet",        2),
    ("chestplate",    2),
    ("shield",        2),
    ("boots",         2),
    ("ring",          1),
    ("amulet",        1),
    # Magic (sehr selten)
    ("scroll",        2),
    ("rune_stone",    1),
    ("spell_book",    1),
)
_kinds, _weights = zip(*SPAWN_TABLE)


async def _find_spawn_position(world, connection_manager) -> tuple[int, int] | None:
    """Spawnt nahe einem aktiven Spieler — Loot fern vom Geschehen ist unsinnig."""
    import math as _math
    center_x, center_y = 60, 40
    players = connection_manager.get_players()
    if players:
        p = random.choice(list(players.values()))
        center_x, center_y = p["x"], p["y"]
    for _ in range(50):
        angle = random.random() * 6.283
        dist = random.randint(3, 20)
        x = center_x + int(_math.cos(angle) * dist)
        y = center_y + int(_math.sin(angle) * dist)
        if await world.is_walkable(x, y):
            return x, y
    return None


async def run(world, item_manager, connection_manager) -> None:
    """Periodisches Spawning von Items auf der Welt."""
    log.info("Item-Worker startet (intervall=%ss)", ITEM_SPAWN_INTERVAL_SECONDS)
    await asyncio.sleep(20)  # Anlaufzeit
    while True:
        try:
            await asyncio.sleep(ITEM_SPAWN_INTERVAL_SECONDS)
            current = await item_manager.get_on_ground()
            if len(current) >= ITEM_SPAWN_MAX:
                continue
            pos = await _find_spawn_position(world, connection_manager)
            if pos is None:
                continue
            kind = random.choices(_kinds, weights=_weights, k=1)[0]
            item = await item_manager.spawn_on_ground(kind, pos[0], pos[1])
            if item is not None:
                await connection_manager.broadcast({
                    "type": "item_spawned",
                    "item": item,
                })
                log.info("Item gespawnt: %s @ (%d, %d)", kind, pos[0], pos[1])
        except asyncio.CancelledError:
            log.info("Item-Worker gestoppt")
            raise
        except Exception:
            log.exception("Item-Worker-Iteration fehlgeschlagen")
