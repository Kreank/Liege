"""Dungeon-Director — Welle 32.

Zwei Hintergrund-Loops:
  1) reaper_loop: prüft expires_at, schickt 10-min-Warning an Spieler in
     der Instanz, teleportiert sie raus, löscht Instanz + Eingangs-Struktur
  2) spawn_loop: würfelt periodisch neue Tier-1/2-Dungeon-Eingänge in der
     Welt. Tier-3/4/5 kommen via Key-Items (siehe items.py
     `dungeon_map`/`rift_lore`/`kings_seal`).

Reaper läuft alle 30s, Spawn alle 5 min.
"""
import asyncio
import logging
import os
import random

import db
import dungeon_instance
import dungeon_tiers

log = logging.getLogger("liege.dungeon_director")

REAPER_INTERVAL = int(os.environ.get("DUNGEON_REAPER_INTERVAL", "30"))   # 30s
SPAWN_INTERVAL  = int(os.environ.get("DUNGEON_SPAWN_INTERVAL",  "300"))  # 5 min
WARN_BEFORE_S   = int(os.environ.get("DUNGEON_WARN_BEFORE_S",   "600"))  # 10 min

# Pro Welt: maximale Anzahl aktiver Tier-1/2-Dungeons. Verhindert dass die
# Welt mit zu vielen Eingängen vollläuft.
MAX_AUTO_DUNGEONS = {
    dungeon_tiers.TIER_SMALL:  20,
    dungeon_tiers.TIER_MEDIUM: 8,
    dungeon_tiers.TIER_LARGE:  0,   # nur via Key-Item
    dungeon_tiers.TIER_RAID20: 0,   # nur via Key-Item
    dungeon_tiers.TIER_RAID40: 0,   # nur via Key-Item
}

# Pro Iteration die Chance einen neuen Dungeon zu spawnen
SPAWN_CHANCE = {
    dungeon_tiers.TIER_SMALL:  0.6,
    dungeon_tiers.TIER_MEDIUM: 0.25,
}


# ─── Reaper ────────────────────────────────────────────────────────────────

async def reaper_loop(connection_manager, world, structures_module) -> None:
    log.info("Dungeon-Reaper startet (tick=%ds, warn=%ds)",
             REAPER_INTERVAL, WARN_BEFORE_S)
    while True:
        try:
            await asyncio.sleep(REAPER_INTERVAL)
            # 1) Vor-Warnungen schicken (10 min vor Ablauf)
            soon = await dungeon_instance.expiring_soon(WARN_BEFORE_S)
            for d in soon:
                player_names = await dungeon_instance.get_players_in_dungeon(d["id"])
                for pid in player_names:
                    ws = connection_manager.connections.get(pid)
                    if ws is None:
                        continue
                    try:
                        await ws.send_json({
                            "type": "toast",
                            "text": "⏳ Dieser Dungeon kollabiert in 10 Minuten — kehre rechtzeitig zurück!",
                        })
                    except Exception:
                        pass
                await dungeon_instance.mark_warned(d["id"])

            # 2) Abgelaufene Instanzen aufräumen
            expired = await dungeon_instance.list_expired()
            for d in expired:
                player_names = await dungeon_instance.get_players_in_dungeon(d["id"])
                for pid in player_names:
                    # Teleport raus zur Overworld
                    ow = await dungeon_instance.exit_dungeon(pid)
                    ws = connection_manager.connections.get(pid)
                    if ws is None:
                        continue
                    if ow:
                        connection_manager.update_player(pid, ow[0], ow[1])
                        try:
                            await ws.send_json({
                                "type": "dungeon_collapsed",
                                "spawn": {"x": ow[0], "y": ow[1]},
                            })
                            await ws.send_json({
                                "type": "toast",
                                "text": "💥 Der Dungeon kollabiert! Du wirst hinausgeschleudert.",
                            })
                        except Exception:
                            pass
                # Eingangs-Struktur entfernen
                ex, ey = d.get("entrance_x"), d.get("entrance_y")
                if ex is not None and ey is not None:
                    try:
                        await structures_module.remove(ex, ey)
                        await connection_manager.broadcast({
                            "type": "structure_removed",
                            "x": ex, "y": ey,
                        })
                    except Exception:
                        log.exception("Eingangs-Struktur-Remove fehlgeschlagen für %d", d["id"])
                await dungeon_instance.delete_dungeon(d["id"])
                log.info("Dungeon %d abgelaufen + gelöscht", d["id"])
            if expired:
                # Minimap-Ortung der Spieler aktualisieren (Eingang ist weg).
                await broadcast_dungeon_sense(connection_manager)
        except asyncio.CancelledError:
            log.info("Dungeon-Reaper gestoppt")
            raise
        except Exception:
            log.exception("Reaper-Iteration fehlgeschlagen")


# ─── Auto-Spawn ────────────────────────────────────────────────────────────

async def broadcast_dungeon_sense(connection_manager) -> None:
    """Schickt allen Spielern die aktuelle Liste aktiver Dungeon-Eingänge.
    Der Client blendet sie nur im Spür-Radius (~70 Tiles) auf der Minimap ein."""
    rows = await db.pool().fetch(
        "SELECT tier, entrance_x, entrance_y FROM dungeons "
        "WHERE expires_at > NOW() AND entrance_x IS NOT NULL"
    )
    payload = {
        "type": "dungeon_sense",
        "dungeons": [{"x": r["entrance_x"], "y": r["entrance_y"], "tier": r["tier"]}
                     for r in rows],
    }
    try:
        await connection_manager.broadcast(payload)
    except Exception:
        log.debug("dungeon_sense broadcast fehlgeschlagen", exc_info=True)


async def _count_active_by_tier() -> dict[int, int]:
    rows = await db.pool().fetch(
        "SELECT tier, COUNT(*) AS c FROM dungeons "
        "WHERE expires_at > NOW() GROUP BY tier",
    )
    return {r["tier"]: r["c"] for r in rows}


async def _find_random_spawn_location(world, connection_manager) -> tuple[int, int] | None:
    """Findet einen walkable Tile irgendwo in den geladenen Chunks für
    einen neuen Dungeon-Eingang. Mindestabstand zu Spielern + bestehenden
    Eingängen."""
    players = list(connection_manager.get_players().values())
    if not players:
        return None
    # Zufälligen Spieler-Anker wählen
    anchor = random.choice(players)
    for _ in range(30):
        # Streuradius: 40-120 Tiles vom Spieler-Anker entfernt
        angle = random.random() * 2 * 3.14159
        dist = random.randint(40, 120)
        import math as _m
        wx = int(anchor["x"] + _m.cos(angle) * dist)
        wy = int(anchor["y"] + _m.sin(angle) * dist)
        if not await world.is_walkable(wx, wy):
            continue
        if world.is_settlement_area(wx, wy):
            continue
        # Mindestabstand zu existierenden Eingängen
        too_close = await db.pool().fetchval(
            "SELECT 1 FROM dungeons WHERE expires_at > NOW() "
            "AND abs(entrance_x - $1) < 20 AND abs(entrance_y - $2) < 20 LIMIT 1",
            wx, wy,
        )
        if too_close:
            continue
        return (wx, wy)
    return None


async def spawn_loop(connection_manager, world, structures_module) -> None:
    log.info("Dungeon-Spawn-Worker startet (tick=%ds)", SPAWN_INTERVAL)
    await asyncio.sleep(60)  # Warm-up
    while True:
        try:
            await asyncio.sleep(SPAWN_INTERVAL)
            if not connection_manager.get_players():
                continue
            counts = await _count_active_by_tier()
            for tier in (dungeon_tiers.TIER_SMALL, dungeon_tiers.TIER_MEDIUM):
                cap = MAX_AUTO_DUNGEONS.get(tier, 0)
                cur = counts.get(tier, 0)
                if cur >= cap:
                    continue
                if random.random() > SPAWN_CHANCE.get(tier, 0):
                    continue
                pos = await _find_random_spawn_location(world, connection_manager)
                if pos is None:
                    continue
                wx, wy = pos
                meta = await dungeon_instance.spawn_dungeon(wx, wy, tier)
                # Stairs-Down-Struktur auf der Welt-Position platzieren
                try:
                    s = await structures_module.place(
                        wx, wy, "stairs_down", "system",
                        material="stone", durability=999,
                    )
                    if s:
                        await connection_manager.broadcast({
                            "type": "structure_placed", "structure": s,
                        })
                except Exception:
                    log.exception("Stairs-Spawn fehlgeschlagen @(%d,%d)", wx, wy)
                # Welt-Event-Broadcast für Tier ≥ 2 (Mittel sichtbar machen)
                if tier >= dungeon_tiers.TIER_MEDIUM:
                    label = dungeon_tiers.TIER_LABEL.get(tier, "Verlies")
                    await connection_manager.broadcast({
                        "type": "world_event",
                        "kind": "dungeon_spawned",
                        "text": f"🏚️ Ein {label} öffnet sich bei ({wx}, {wy})!",
                        "x": wx, "y": wy,
                    })
                log.info("Auto-Dungeon T%d gespawnt: id=%d @(%d,%d)",
                         tier, meta["id"], wx, wy)
                # Minimap-Ortung aktualisieren (neuer Eingang spürbar).
                await broadcast_dungeon_sense(connection_manager)
        except asyncio.CancelledError:
            log.info("Dungeon-Spawn-Worker gestoppt")
            raise
        except Exception:
            log.exception("Spawn-Iteration fehlgeschlagen")
