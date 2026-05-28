"""Raid-Director nach RimWorld-Vorbild: bei wachsender Spieler-Basis eskalieren Raids.

Periodisch checken: wenn ein Spieler genug Strukturen hat UND seit letztem Raid genug Zeit
vergangen ist, würfeln + Raid auslösen. Spawnt eine kleine Gruppe Creatures nahe der Base,
plus atmosphärisches Event."""

import asyncio
import logging
import math
import os
import random
import time

import combat
import db

log = logging.getLogger("liege.raid_director")

RAID_CHECK_INTERVAL = int(os.environ.get("RAID_CHECK_INTERVAL", "300"))   # 5 min
RAID_WEALTH_THRESHOLD = int(os.environ.get("RAID_WEALTH_THRESHOLD", "10"))
RAID_COOLDOWN_SECONDS = int(os.environ.get("RAID_COOLDOWN_SECONDS", "1800"))  # 30 min

_last_raid: dict[str, float] = {}


async def player_wealth(player_name: str) -> int:
    """Anzahl vom Spieler platzierter Strukturen (excl. system)."""
    row = await db.pool().fetchrow(
        "SELECT COUNT(*) AS c FROM structures WHERE owner = $1", player_name
    )
    return row["c"] if row else 0


async def group_wealth(member_names: set[str]) -> int:
    """Summe der Wealth aller Online-Mitglieder einer Gruppe."""
    if not member_names:
        return 0
    rows = await db.pool().fetch(
        "SELECT COUNT(*) AS c FROM structures WHERE owner = ANY($1::text[])",
        list(member_names),
    )
    return rows[0]["c"] if rows else 0


async def find_raid_target(player_name: str, world) -> dict | None:
    rows = await db.pool().fetch(
        "SELECT x, y FROM structures WHERE owner = $1 ORDER BY RANDOM() LIMIT 5",
        player_name,
    )
    if not rows:
        return None
    # Wähle Struktur als anker, dann offset
    anchor = random.choice(rows)
    for _ in range(20):
        angle = random.random() * math.tau
        dist = random.randint(8, 16)
        x = anchor["x"] + int(math.cos(angle) * dist)
        y = anchor["y"] + int(math.sin(angle) * dist)
        if await world.is_walkable(x, y):
            return {"x": x, "y": y}
    return None


MANUAL_RAID_TIERS = {
    # tier: (party_size, boss_chance, label)
    1: (5,  0.00, "Plünderer-Welle"),
    2: (10, 0.05, "Räuber-Bande"),
    3: (15, 0.15, "Stamm-Überfall"),
    4: (20, 0.25, "Kriegszug"),
    5: (30, 0.40, "Belagerung"),
}
MANUAL_RAID_COOLDOWN_SECONDS = 900  # 15 min — separat von Auto-Wealth-Cooldown


async def trigger_manual_raid(leader_name: str, tier: int, world, npc_manager,
                              connection_manager, event_manager) -> dict:
    """Manuell von Group-Leader ausgelöste Raid-Welle.

    Spawnt eine Mob-Welle nahe der Leader-Position; verbraucht den manuellen
    Cooldown des Leaders. Returns {'ok': True, 'spawned': N, 'label': ...}
    bei Erfolg, sonst {'ok': False, 'reason': ...}."""
    if tier not in MANUAL_RAID_TIERS:
        return {"ok": False, "reason": "invalid_tier"}
    now = time.time()
    cd_key = f"manual:{leader_name}"
    if now - _last_raid.get(cd_key, 0) < MANUAL_RAID_COOLDOWN_SECONDS:
        remaining = MANUAL_RAID_COOLDOWN_SECONDS - int(now - _last_raid[cd_key])
        return {"ok": False, "reason": "cooldown", "remaining_s": remaining}
    # Anker = aktuelle Leader-Position
    pos = connection_manager.get_players().get(leader_name)
    if not pos:
        return {"ok": False, "reason": "leader_offline"}
    party_size, boss_chance, label = MANUAL_RAID_TIERS[tier]
    raid_kinds = []
    creature_pool = list(combat.CREATURE_KINDS)
    boss_kinds = ["ogre", "necromancer", "dragon_whelp"]
    for _ in range(party_size):
        if random.random() < boss_chance:
            raid_kinds.append(random.choice(boss_kinds))
        else:
            raid_kinds.append(random.choice(creature_pool))
    log.info("MANUAL RAID T%d von %s: %d Mobs @ (%d,%d)",
             tier, leader_name, party_size, pos["x"], pos["y"])
    spawned = 0
    for kind in raid_kinds:
        for _ in range(25):
            angle = random.random() * math.tau
            dist = random.randint(10, 18)
            tx = pos["x"] + int(math.cos(angle) * dist)
            ty = pos["y"] + int(math.sin(angle) * dist)
            if await world.is_walkable(tx, ty):
                max_hp = combat.NPC_HP_BY_KIND.get(kind, 40)
                npc = await npc_manager.create(
                    f"Raid-{kind.title()}", kind, tx, ty,
                    "Spielen-getriggerter Raid",
                    max_hp=max_hp,
                )
                if npc is not None:
                    spawned += 1
                    await connection_manager.broadcast({"type": "npc_spawned", "npc": npc})
                break
    if spawned == 0:
        return {"ok": False, "reason": "no_walkable_spots"}
    saved = await event_manager.save(
        "faction",
        f"⚔️ {label}",
        f"Eine Welle von {spawned} Kreaturen formiert sich. "
        f"Ausgelöst von {leader_name}.",
    )
    await connection_manager.broadcast({"type": "event", "event": saved})
    _last_raid[cd_key] = now
    return {"ok": True, "spawned": spawned, "label": label, "tier": tier}


async def trigger_raid(player_name: str, wealth: int, world, npc_manager,
                      connection_manager, event_manager) -> None:
    target = await find_raid_target(player_name, world)
    if target is None:
        log.warning("Raid abort: kein target für %s", player_name)
        return
    party_size = min(2 + wealth // 10, 6)
    raid_kinds = []
    creature_pool = list(combat.CREATURE_KINDS)
    # Bei high wealth: chance auf bosse
    boss_kinds = ["ogre", "necromancer", "dragon_whelp"]
    for _ in range(party_size):
        if wealth > 30 and random.random() < 0.15:
            raid_kinds.append(random.choice(boss_kinds))
        else:
            raid_kinds.append(random.choice(creature_pool))
    log.info("RAID auf %s: %d × %s @ (%d,%d)", player_name, party_size,
             raid_kinds, target["x"], target["y"])
    spawned = 0
    for kind in raid_kinds:
        # Walkable spot near target
        for _ in range(20):
            tx = target["x"] + random.randint(-3, 3)
            ty = target["y"] + random.randint(-3, 3)
            if await world.is_walkable(tx, ty):
                max_hp = combat.NPC_HP_BY_KIND.get(kind, 40)
                npc = await npc_manager.create(
                    f"Räuber-{kind.title()}", kind, tx, ty,
                    "Mitglied einer Raubparty, die nach Beute sucht",
                    max_hp=max_hp,
                )
                if npc is not None:
                    spawned += 1
                    await connection_manager.broadcast({"type": "npc_spawned", "npc": npc})
                break
    if spawned == 0:
        return
    saved = await event_manager.save(
        "faction",
        f"⚠️ Überfall auf {player_name}",
        f"Eine Gruppe von {spawned} wilden Kreaturen taucht in der Nähe "
        f"deiner Festung auf. Bereite dich vor!",
    )
    await connection_manager.broadcast({"type": "event", "event": saved})
    _last_raid[player_name] = time.time()


async def run(world, npc_manager, connection_manager, event_manager) -> None:
    log.info("Raid-Director startet (check alle %ds, threshold=%d)",
             RAID_CHECK_INTERVAL, RAID_WEALTH_THRESHOLD)
    await asyncio.sleep(120)
    # Lazy-Import von groups, weil raid_director vor groups in main.py geladen wird.
    import groups
    while True:
        try:
            await asyncio.sleep(RAID_CHECK_INTERVAL)
            now = time.time()
            # Pro Iteration: gruppieren wir Online-Spieler, sodass jede Gruppe
            # nur einmal pro Check ge-raided wird (statt pro Mitglied einmal).
            online = list(connection_manager.get_players().keys())
            processed: set[str] = set()
            for player_name in online:
                if player_name in processed:
                    continue
                g = await groups.get_group_for(player_name)
                if g:
                    members = await groups.get_member_names(g["id"])
                    online_members = [m for m in members if m in connection_manager.get_players()]
                    wealth = await group_wealth(set(online_members))
                    raid_key = f"group:{g['id']}"
                    raid_target = random.choice(online_members) if online_members else player_name
                    processed.update(members)
                else:
                    wealth = await player_wealth(player_name)
                    raid_key = player_name
                    raid_target = player_name
                    processed.add(player_name)
                if wealth < RAID_WEALTH_THRESHOLD:
                    continue
                if now - _last_raid.get(raid_key, 0) < RAID_COOLDOWN_SECONDS:
                    continue
                chance = min(0.6, wealth * 0.02)
                if random.random() > chance:
                    continue
                await trigger_raid(
                    raid_target, wealth, world, npc_manager,
                    connection_manager, event_manager,
                )
                # Cooldown auf Gruppen-Key (statt Per-Player), damit Gruppe nicht
                # 5x in einer Iteration ge-raided wird.
                _last_raid[raid_key] = now
        except asyncio.CancelledError:
            log.info("Raid-Director gestoppt")
            raise
        except Exception:
            log.exception("Raid-Director-Iteration fehlgeschlagen")
