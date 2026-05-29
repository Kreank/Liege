"""Dungeon-Instanzen-Manager mit Multi-Floor + Tier + Lifetime.

Persistierte Dungeon-Instanzen, jeweils mit floor_count Floors. Beim
ersten Betreten wird Floor 0 generiert + Mobs gespawnt; Stairs-Down auf
nicht-letzter Floor erzeugt lazy die nächste Floor beim Klick.

Player-State im DB-Feld players.world_id:
    'overworld'           — auf der Hauptwelt
    'dungeon:<id>:<floor>' — in Floor <floor> der Instanz <id>
Und players.overworld_x/y für Rückkehr.

Lifetimes (siehe dungeon_tiers.py): pro Tier-Klasse 2h..7 Tage.
Reaper-Worker (siehe reap_expired_dungeons) teleportiert Spieler vor
Despawn raus und löscht die Instanz.
"""
import json
import logging
import random

import db
import dungeon_world
import dungeon_themes
import dungeon_tiers

log = logging.getLogger("liege.dungeon_instance")


# ─── Public Entry Points ───────────────────────────────────────────────────

async def spawn_dungeon(entrance_x: int, entrance_y: int, tier: int,
                         theme: str | None = None) -> dict:
    """Erzeugt eine neue Dungeon-Instanz mit gegebenem Tier an Welt-Position
    (entrance_x, entrance_y). Generiert Floor 0; weitere Floors lazy.
    Returns die Dungeon-Row als dict."""
    seed = random.randint(1, 2**31 - 1)
    if theme is None:
        theme = dungeon_tiers.pick_theme(tier, seed)
    floor_count = dungeon_tiers.random_floor_count(tier)
    label = dungeon_tiers.TIER_LABEL.get(tier, "Dungeon")
    name = f"{label}:{theme}"
    lifetime_s = dungeon_tiers.random_lifetime_seconds(tier)
    row = await db.pool().fetchrow(
        "INSERT INTO dungeons "
        "  (seed, name, size, tiles, spawn_x, spawn_y, tier, floor_count, "
        "   expires_at, entrance_x, entrance_y, theme) "
        "VALUES ($1, $2, 0, '[]'::jsonb, 0, 0, $3, $4, "
        "        NOW() + ($5 || ' seconds')::interval, $6, $7, $8) "
        "RETURNING id, seed, tier, floor_count, expires_at",
        seed, name, tier, floor_count, str(lifetime_s),
        entrance_x, entrance_y, theme,
    )
    log.info("Dungeon-Instanz erzeugt: id=%d tier=%d theme=%s floors=%d "
             "expires_at=%s entrance=(%d,%d)",
             row["id"], tier, theme, floor_count, row["expires_at"],
             entrance_x, entrance_y)
    # Floor 0 vorbereiten
    await _ensure_floor(row["id"], seed, tier, theme, 0, floor_count)
    return {
        "id":          row["id"],
        "seed":        seed,
        "tier":        tier,
        "floor_count": floor_count,
        "theme":       theme,
        "expires_at":  row["expires_at"].isoformat() if row["expires_at"] else None,
        "entrance":    (entrance_x, entrance_y),
    }


async def get_dungeon(dungeon_id: int) -> dict | None:
    row = await db.pool().fetchrow(
        "SELECT id, seed, name, tier, floor_count, expires_at, theme, "
        "       entrance_x, entrance_y, warned "
        "FROM dungeons WHERE id = $1", dungeon_id,
    )
    if not row:
        return None
    return {
        "id":          row["id"],
        "seed":        row["seed"],
        "name":        row["name"],
        "tier":        row["tier"],
        "floor_count": row["floor_count"],
        "theme":       row["theme"],
        "entrance":    (row["entrance_x"], row["entrance_y"]),
        "expires_at":  row["expires_at"].isoformat() if row["expires_at"] else None,
        "warned":      row["warned"],
    }


async def get_floor(dungeon_id: int, floor_idx: int) -> dict | None:
    """Lädt eine Floor-Row. Generiert sie lazy wenn nicht vorhanden."""
    row = await db.pool().fetchrow(
        "SELECT dungeon_id, floor_idx, size, tiles, spawn_x, spawn_y, "
        "       next_stair_x, next_stair_y, populated "
        "FROM dungeon_floors WHERE dungeon_id = $1 AND floor_idx = $2",
        dungeon_id, floor_idx,
    )
    if row:
        tiles = row["tiles"]
        if isinstance(tiles, str):
            tiles = json.loads(tiles)
        return {
            "dungeon_id":   row["dungeon_id"],
            "floor_idx":    row["floor_idx"],
            "size":         row["size"],
            "tiles":        tiles,
            "spawn":        (row["spawn_x"], row["spawn_y"]),
            "next_stair":   (row["next_stair_x"], row["next_stair_y"])
                            if row["next_stair_x"] is not None else None,
            "populated":    row["populated"],
        }
    # Lazy generate: dafür Dungeon-Metadata brauchen
    dungeon = await get_dungeon(dungeon_id)
    if dungeon is None:
        return None
    return await _ensure_floor(dungeon_id, dungeon["seed"], dungeon["tier"],
                                dungeon["theme"], floor_idx,
                                dungeon["floor_count"])


async def _ensure_floor(dungeon_id: int, dungeon_seed: int, tier: int,
                         theme: str, floor_idx: int, floor_count: int) -> dict:
    """Generiert eine Floor wenn sie nicht in der DB ist."""
    existing = await db.pool().fetchrow(
        "SELECT 1 FROM dungeon_floors WHERE dungeon_id = $1 AND floor_idx = $2",
        dungeon_id, floor_idx,
    )
    if existing:
        return await get_floor(dungeon_id, floor_idx)
    # Eigene Seed pro Floor — sonst sehen alle Floors identisch aus
    floor_seed = (dungeon_seed * 1009 + floor_idx * 31337) & 0x7FFFFFFF
    size = dungeon_tiers.FLOOR_SIZE.get(tier, 24)
    is_last = (floor_idx >= floor_count - 1)
    layout = dungeon_world.generate(
        floor_seed, size=size, theme=theme,
        with_stairs_down=(not is_last),
    )
    spawn_x, spawn_y = layout["spawn"]
    nx, ny = (layout["stairs_down"] or (None, None))
    await db.pool().execute(
        "INSERT INTO dungeon_floors "
        "  (dungeon_id, floor_idx, size, tiles, spawn_x, spawn_y, "
        "   next_stair_x, next_stair_y, populated) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE) "
        "ON CONFLICT DO NOTHING",
        dungeon_id, floor_idx, layout["size"],
        json.dumps(layout["tiles"]),
        spawn_x, spawn_y, nx, ny,
    )
    log.info("Floor erzeugt: dungeon=%d floor=%d/%d size=%d theme=%s",
             dungeon_id, floor_idx, floor_count, size, theme)
    return await get_floor(dungeon_id, floor_idx)


# ─── Player-State ──────────────────────────────────────────────────────────

async def enter_dungeon(player_name: str, dungeon_id: int,
                         overworld_x: int, overworld_y: int,
                         floor_idx: int = 0) -> dict | None:
    """Setzt Player in Floor floor_idx eines Dungeons. Returns Floor-Daten oder None."""
    floor = await get_floor(dungeon_id, floor_idx)
    if floor is None:
        return None
    world_id = f"dungeon:{dungeon_id}:{floor_idx}"
    await db.pool().execute(
        "UPDATE players SET world_id = $1, x = $2, y = $3, "
        "overworld_x = COALESCE(overworld_x, $4), "
        "overworld_y = COALESCE(overworld_y, $5) "
        "WHERE name = $6",
        world_id, floor["spawn"][0], floor["spawn"][1],
        overworld_x, overworld_y, player_name,
    )
    return floor


async def change_floor(player_name: str, dungeon_id: int,
                        new_floor: int) -> dict | None:
    """Wechselt zur next/previous Floor. Returns Floor-Daten."""
    floor = await get_floor(dungeon_id, new_floor)
    if floor is None:
        return None
    world_id = f"dungeon:{dungeon_id}:{new_floor}"
    await db.pool().execute(
        "UPDATE players SET world_id = $1, x = $2, y = $3 WHERE name = $4",
        world_id, floor["spawn"][0], floor["spawn"][1], player_name,
    )
    return floor


async def exit_dungeon(player_name: str) -> tuple[int, int] | None:
    """Player zurück auf Overworld an alter Position."""
    row = await db.pool().fetchrow(
        "SELECT overworld_x, overworld_y FROM players WHERE name = $1",
        player_name,
    )
    if not row or row["overworld_x"] is None:
        return None
    x, y = row["overworld_x"], row["overworld_y"]
    await db.pool().execute(
        "UPDATE players SET world_id = 'overworld', x = $1, y = $2, "
        "overworld_x = NULL, overworld_y = NULL WHERE name = $3",
        x, y, player_name,
    )
    return (x, y)


async def get_player_world(player_name: str) -> str:
    row = await db.pool().fetchrow(
        "SELECT world_id FROM players WHERE name = $1", player_name,
    )
    return row["world_id"] if row and row["world_id"] else "overworld"


def parse_world_id(world_id: str) -> tuple[int, int] | None:
    """Parst 'dungeon:<id>:<floor>' → (dungeon_id, floor_idx) oder None."""
    if not world_id or not world_id.startswith("dungeon:"):
        return None
    parts = world_id.split(":")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[1]), int(parts[2]))
    except ValueError:
        return None


# ─── Helpers ───────────────────────────────────────────────────────────────

def is_walkable_tile(tile_id: int) -> bool:
    return dungeon_world.is_walkable_tile(tile_id)


def tile_at(dungeon_tiles: list, x: int, y: int) -> int:
    size = len(dungeon_tiles)
    if not (0 <= x < size and 0 <= y < size):
        return dungeon_world.WALL
    return dungeon_tiles[y][x]


async def get_players_in_dungeon(dungeon_id: int) -> list[str]:
    rows = await db.pool().fetch(
        "SELECT name FROM players WHERE world_id LIKE $1",
        f"dungeon:{dungeon_id}:%",
    )
    return [r["name"] for r in rows]


async def expiring_soon(within_seconds: int = 600) -> list[dict]:
    """Liste der Dungeons die in N Sekunden ablaufen und noch nicht warned wurden."""
    rows = await db.pool().fetch(
        "SELECT id, expires_at, name FROM dungeons "
        "WHERE expires_at IS NOT NULL "
        "  AND expires_at <= NOW() + ($1 || ' seconds')::interval "
        "  AND expires_at > NOW() "
        "  AND warned = FALSE",
        str(within_seconds),
    )
    return [dict(r) for r in rows]


async def mark_warned(dungeon_id: int) -> None:
    await db.pool().execute(
        "UPDATE dungeons SET warned = TRUE WHERE id = $1", dungeon_id,
    )


async def list_expired() -> list[dict]:
    """Dungeons deren Lifetime abgelaufen ist."""
    rows = await db.pool().fetch(
        "SELECT id, name, entrance_x, entrance_y FROM dungeons "
        "WHERE expires_at IS NOT NULL AND expires_at <= NOW()",
    )
    return [dict(r) for r in rows]


async def delete_dungeon(dungeon_id: int) -> None:
    """Entfernt Dungeon + alle Floors (CASCADE). Player im Dungeon müssen
    VORHER teleportiert worden sein (Caller-Verantwortung)."""
    await db.pool().execute("DELETE FROM dungeons WHERE id = $1", dungeon_id)


async def populate_floor_mobs(dungeon_id: int, floor_idx: int,
                               npc_manager, connection_manager) -> int:
    """Spawnt Mobs auf einer Floor falls sie noch nicht populated ist.
    Returns Anzahl gespawnter Mobs."""
    row = await db.pool().fetchrow(
        "SELECT populated, size, tiles FROM dungeon_floors "
        "WHERE dungeon_id = $1 AND floor_idx = $2",
        dungeon_id, floor_idx,
    )
    if row is None or row["populated"]:
        return 0
    dungeon = await get_dungeon(dungeon_id)
    if dungeon is None:
        return 0
    tier = dungeon["tier"]
    theme = dungeon["theme"]
    is_last = (floor_idx >= dungeon["floor_count"] - 1)
    tiles = row["tiles"]
    if isinstance(tiles, str):
        tiles = json.loads(tiles)
    size = row["size"]
    # Walkable spots sammeln (außer dem spawn-tile = STAIRS_UP)
    walkable: list[tuple[int, int]] = []
    for y in range(size):
        for x in range(size):
            if dungeon_world.is_walkable_tile(tiles[y][x]) \
               and tiles[y][x] not in (dungeon_world.STAIRS_UP, dungeon_world.STAIRS_DOWN):
                walkable.append((x, y))
    if not walkable:
        return 0
    rng = random.Random((dungeon["seed"] * 31337 + floor_idx) & 0x7FFFFFFF)
    mob_count = dungeon_tiers.random_mob_count(tier)
    theme_data = dungeon_themes.THEMES.get(theme, {})
    mob_pool = theme_data.get("mob_pool", ["goblin"])
    boss_pool = theme_data.get("boss_pool", ["ogre"])
    hp_mult = dungeon_tiers.MOB_HP_MULT.get(tier, 1.0)
    world_id = f"dungeon:{dungeon_id}:{floor_idx}"
    spawned = 0
    used_spots: set[tuple[int, int]] = set()
    # Normale Mobs
    for _ in range(mob_count):
        if not walkable:
            break
        spot = rng.choice(walkable)
        if spot in used_spots:
            continue
        used_spots.add(spot)
        kind = rng.choice(mob_pool)
        import combat as _combat
        base_hp = _combat.NPC_HP_BY_KIND.get(kind, 40)
        max_hp = int(base_hp * hp_mult)
        npc = await npc_manager.create(
            f"{kind.title()}",
            kind, spot[0], spot[1],
            f"Bewohner von {theme}",
            max_hp=max_hp,
            world_id=world_id,
        )
        if npc:
            spawned += 1
            await _broadcast_to_dungeon_floor(connection_manager,
                                              dungeon_id, floor_idx,
                                              {"type": "npc_spawned", "npc": npc})
    # Boss-Spawns auf letzter Floor
    if is_last:
        boss_count = dungeon_tiers.BOSS_COUNT.get(tier, 1)
        for _ in range(boss_count):
            if not walkable:
                break
            spot = rng.choice(walkable)
            kind = rng.choice(boss_pool)
            import combat as _combat
            base_hp = _combat.NPC_HP_BY_KIND.get(kind, 200)
            max_hp = int(base_hp * hp_mult * 1.5)   # Boss-Premium
            npc = await npc_manager.create(
                f"{theme_data.get('label', 'Boss')}-{kind.title()}",
                kind, spot[0], spot[1],
                f"Wächter der tiefsten Kammer",
                max_hp=max_hp,
                world_id=world_id,
            )
            if npc:
                spawned += 1
                await _broadcast_to_dungeon_floor(connection_manager,
                                                  dungeon_id, floor_idx,
                                                  {"type": "npc_spawned", "npc": npc})
    await db.pool().execute(
        "UPDATE dungeon_floors SET populated = TRUE "
        "WHERE dungeon_id = $1 AND floor_idx = $2",
        dungeon_id, floor_idx,
    )
    log.info("Floor populated: dungeon=%d floor=%d, %d mobs",
             dungeon_id, floor_idx, spawned)
    return spawned


async def _broadcast_to_dungeon_floor(connection_manager, dungeon_id: int,
                                       floor_idx: int, message: dict) -> None:
    """Sendet eine Message nur an Spieler die auf dieser Dungeon-Floor sind."""
    target_world = f"dungeon:{dungeon_id}:{floor_idx}"
    for pid, _pos in connection_manager.get_players().items():
        w = await get_player_world(pid)
        if w != target_world:
            continue
        ws = connection_manager.connections.get(pid)
        if ws is None:
            continue
        try: await ws.send_json(message)
        except Exception: pass


# ─── Features (Kisten / Fallen / Decor) + Floor-NPCs ────────────────────────
# Features werden deterministisch aus dem Floor-Seed neu berechnet (kein Extra-
# DB-Feld nötig). Trigger-/Öffnungs-Status liegt in-memory (Reset bei Restart ok,
# Dungeons sind ephemer).
_floor_feature_cache: dict = {}      # (did, fidx) -> layout-features dict
_triggered_traps: dict = {}          # (did, fidx) -> set((x,y))
_opened_chests: dict = {}            # (did, fidx) -> set((x,y))


async def floor_features(dungeon_id: int, floor_idx: int) -> dict:
    """Kisten/Fallen/Decor einer Floor (deterministisch aus Seed reproduziert)."""
    key = (dungeon_id, floor_idx)
    if key in _floor_feature_cache:
        return _floor_feature_cache[key]
    dungeon = await get_dungeon(dungeon_id)
    if dungeon is None:
        return {"theme": "cave", "chests": [], "traps": [], "decor": []}
    floor_seed = (dungeon["seed"] * 1009 + floor_idx * 31337) & 0x7FFFFFFF
    # WICHTIG: tatsächliche gespeicherte Floor-Größe verwenden (alte Dungeons
    # wurden mit kleinerer Größe generiert) — sonst liegen Features außerhalb.
    srow = await db.pool().fetchrow(
        "SELECT size FROM dungeon_floors WHERE dungeon_id = $1 AND floor_idx = $2",
        dungeon_id, floor_idx,
    )
    size = (srow["size"] if srow and srow["size"]
            else dungeon_tiers.FLOOR_SIZE.get(dungeon["tier"], 24))
    is_last = (floor_idx >= dungeon["floor_count"] - 1)
    layout = dungeon_world.generate(
        floor_seed, size=size, theme=dungeon["theme"],
        with_stairs_down=(not is_last),
    )
    feats = {
        "theme":  dungeon["theme"],
        "chests": layout["chests"],
        "traps":  layout["traps"],
        "decor":  layout["decor"],
    }
    _floor_feature_cache[key] = feats
    return feats


async def visible_features(dungeon_id: int, floor_idx: int) -> dict:
    """Features für den Client: Kisten mit opened-Flag, Fallen NUR wenn schon
    ausgelöst (versteckt bis getriggert), Decor immer."""
    feats = await floor_features(dungeon_id, floor_idx)
    key = (dungeon_id, floor_idx)
    opened = _opened_chests.get(key, set())
    triggered = _triggered_traps.get(key, set())
    chests = [{"x": c["x"], "y": c["y"], "opened": (c["x"], c["y"]) in opened}
              for c in feats["chests"]]
    traps = [{"x": t["x"], "y": t["y"], "kind": t["kind"]}
             for t in feats["traps"] if (t["x"], t["y"]) in triggered]
    return {"theme": feats["theme"], "chests": chests,
            "traps": traps, "decor": feats["decor"]}


async def trap_at(dungeon_id: int, floor_idx: int, x: int, y: int) -> str | None:
    """Gibt die Fallen-Art an (x,y) zurück, falls dort eine noch nicht
    ausgelöste Falle liegt — sonst None."""
    feats = await floor_features(dungeon_id, floor_idx)
    key = (dungeon_id, floor_idx)
    if (x, y) in _triggered_traps.get(key, set()):
        return None
    for t in feats["traps"]:
        if t["x"] == x and t["y"] == y:
            return t["kind"]
    return None


def mark_trap_triggered(dungeon_id: int, floor_idx: int, x: int, y: int) -> None:
    _triggered_traps.setdefault((dungeon_id, floor_idx), set()).add((x, y))


async def chest_at(dungeon_id: int, floor_idx: int, x: int, y: int) -> bool:
    """True wenn an (x,y) eine noch nicht geöffnete Kiste liegt."""
    feats = await floor_features(dungeon_id, floor_idx)
    key = (dungeon_id, floor_idx)
    if (x, y) in _opened_chests.get(key, set()):
        return False
    return any(c["x"] == x and c["y"] == y for c in feats["chests"])


def mark_chest_opened(dungeon_id: int, floor_idx: int, x: int, y: int) -> None:
    _opened_chests.setdefault((dungeon_id, floor_idx), set()).add((x, y))


def npcs_in_world(npc_manager, world_id: str) -> list[dict]:
    """Alle (lebenden) NPCs in einer Welt — zum Senden beim Floor-Betreten."""
    return [n for n in npc_manager.all()
            if (n.get("world_id") or "overworld") == world_id]


async def list_active_dungeons() -> list[dict]:
    """Aktuell aktive Dungeons (für Welt-Marker etc.)."""
    rows = await db.pool().fetch(
        "SELECT id, tier, theme, entrance_x, entrance_y, expires_at "
        "FROM dungeons WHERE expires_at > NOW() ORDER BY tier, id",
    )
    return [{
        "id":         r["id"],
        "tier":       r["tier"],
        "theme":      r["theme"],
        "entrance":   (r["entrance_x"], r["entrance_y"]),
        "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
    } for r in rows]
