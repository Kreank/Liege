import asyncio
import json
import logging
import math
import os
import random

import combat
import llm
from world import GRASS, FOREST, MOUNTAIN, DESERT, JUNGLE, LAVA, SNOW, SWAMP, SAND

log = logging.getLogger("liege.npc_worker")

INITIAL_NPC_COUNT = int(os.environ.get("INITIAL_NPC_COUNT", "20"))
# Periodisches Creature-Respawn: hält die Welt belebt nach Tötungen
MIN_CREATURE_COUNT = int(os.environ.get("MIN_CREATURE_COUNT", "30"))
CREATURE_RESPAWN_INTERVAL = int(os.environ.get("CREATURE_RESPAWN_INTERVAL", "45"))

# Sprite-Varianten pro Kind (Waffen/Rollen-Bilder). Beim Spawn wird zufällig
# eine Variante gepickt und in npcs.sprite_variant gespeichert, damit der
# selbe NPC nach Reconnect/Reload dasselbe Sprite zeigt.
SPRITE_VARIANTS_BY_KIND = {
    "bandit":   ["bandit_axe", "bandit_bow", "bandit_dagger", "bandit_spear"],
    "soldier":  ["soldier_axe", "soldier_spear", "soldier_sword_shield"],
    "miner":    ["miner_pickaxe"],
    "watchman": ["watchman_crossbow", "watchman_lantern"],
}


# Pro Creature-Kind: typische Gruppengröße + bevorzugte Biome.
# biomes=None bedeutet "überall walkable". Group-Size (min, max) inklusiv.
CREATURE_SPAWN_PROFILE = {
    "boar":         {"group": (3, 5),  "biomes": {GRASS, FOREST, JUNGLE}},
    "bandit":       {"group": (2, 6),  "biomes": None},
    "goblin":       {"group": (5, 10), "biomes": None},
    "wolf":         {"group": (2, 4),  "biomes": {GRASS, FOREST, SNOW}},
    "spider":       {"group": (1, 1),  "biomes": None},        # Einzelgänger
    "skeleton":     {"group": (1, 3),  "biomes": {SWAMP, DESERT, SNOW}},
    "rat":          {"group": (2, 5),  "biomes": None},
    "bat":          {"group": (1, 3),  "biomes": {FOREST, JUNGLE}},
    "zombie":       {"group": (1, 4),  "biomes": {SWAMP, DESERT}},
    "bear":         {"group": (1, 2),  "biomes": {FOREST, SNOW}},
    "slime":        {"group": (1, 3),  "biomes": {SWAMP, JUNGLE}},
    # Bosse — überwiegend solo, in extremen Gebieten
    "ogre":         {"group": (1, 1),  "biomes": {SNOW, DESERT}},
    "necromancer":  {"group": (1, 1),  "biomes": {SWAMP, DESERT}},
    "dragon_whelp": {"group": (1, 1),  "biomes": {SNOW, DESERT}},  # nahe Berge/Lava

    # — Welle 13 — Tiere (meist Gruppen) —
    "stag":         {"group": (2, 4),  "biomes": {GRASS, FOREST}},
    "lynx":         {"group": (1, 1),  "biomes": {FOREST, SNOW}},     # solo
    "cougar":       {"group": (1, 2),  "biomes": {FOREST, GRASS}},
    "wolverine":    {"group": (1, 1),  "biomes": {SNOW}},
    "dire_wolf":    {"group": (3, 5),  "biomes": {FOREST, SNOW}},
    "wolf_alpha":   {"group": (1, 1),  "biomes": {FOREST, SNOW}},      # solo (anführer)
    "cave_bear":    {"group": (1, 1),  "biomes": {FOREST}},
    "polar_bear":   {"group": (1, 2),  "biomes": {SNOW}},
    "crocodile":    {"group": (1, 2),  "biomes": {SWAMP, JUNGLE}},
    "cobra":        {"group": (1, 1),  "biomes": {DESERT, JUNGLE}},
    # — Insekten/Kleinkram (oft Gruppen) —
    "slimelet":     {"group": (3, 6),  "biomes": {SWAMP, JUNGLE}},
    "fae_mite":     {"group": (4, 8),  "biomes": {JUNGLE, FOREST}},
    "gloom_moth":   {"group": (2, 5),  "biomes": {SWAMP}},
    "ember_newt":   {"group": (2, 4),  "biomes": {DESERT}},
    "ember_rat":    {"group": (3, 6),  "biomes": {DESERT}},
    "shadow_bat":   {"group": (3, 7),  "biomes": {FOREST, SWAMP}},
    "thorn_scarab": {"group": (2, 4),  "biomes": {JUNGLE, FOREST}},
    "crystal_beetle":{"group": (1, 3), "biomes": {SNOW, DESERT}},
    "crystal_tick": {"group": (2, 5),  "biomes": {SNOW}},
    # — Geister/Fae —
    "frost_sprite": {"group": (1, 2),  "biomes": {SNOW}},
    "fire_imp":     {"group": (1, 3),  "biomes": {DESERT}},
    "mushroom_imp": {"group": (2, 4),  "biomes": {JUNGLE, SWAMP}},
    "thornling":    {"group": (2, 4),  "biomes": {FOREST, JUNGLE}},
    "treant":       {"group": (1, 1),  "biomes": {FOREST, JUNGLE}},    # solo
    # — Stein/Kristall (selten, solo) —
    "stone_golem":  {"group": (1, 1),  "biomes": {SNOW, DESERT}},
    "crystal_golem":{"group": (1, 1),  "biomes": {SNOW}},
    "gargoyle":     {"group": (1, 2),  "biomes": {SNOW, DESERT}},
    "bone_crawler": {"group": (1, 3),  "biomes": {DESERT, SWAMP}},
    "giant_spider": {"group": (1, 1),  "biomes": {FOREST, JUNGLE, SWAMP}},
    # — Bosse — alle solo —
    "minotaur":     {"group": (1, 1),  "biomes": {SNOW, DESERT}},
    "harpy":        {"group": (1, 2),  "biomes": {SNOW, DESERT}},
    "basilisk":     {"group": (1, 1),  "biomes": {DESERT}},
    "chimera":      {"group": (1, 1),  "biomes": {SNOW, DESERT}},
    "griffin":      {"group": (1, 1),  "biomes": {SNOW}},
    "hydra":        {"group": (1, 1),  "biomes": {SWAMP}},
    "manticore":    {"group": (1, 1),  "biomes": {DESERT}},
}
FRIENDLY_KINDS = ["wanderer", "merchant", "hermit", "bard", "scholar", "soldier",
                  "mage", "farmer", "villager", "guard", "healer",
                  "quest_giver", "blacksmith",
                  # Asset-Drop 2026-05-26: weitere Rollen + Tiere/Kinder
                  "miner", "village_elder", "watchman",
                  "cat", "dog", "child"]
CREATURE_KINDS = [
    # Welle 1-3
    "goblin", "wolf", "skeleton", "spider", "slime",
    "rat", "bat", "zombie", "bandit", "boar", "bear",
    # Welle 13 — neue Tiere
    "stag", "lynx", "cougar", "wolverine", "dire_wolf", "wolf_alpha",
    "cave_bear", "polar_bear", "crocodile", "cobra",
    # Welle 13 — Insekten/Kleinkram
    "slimelet", "fae_mite", "gloom_moth", "ember_newt", "ember_rat",
    "shadow_bat", "thorn_scarab", "crystal_beetle", "crystal_tick",
    # Welle 13 — Geister/Fae/Plants
    "frost_sprite", "fire_imp", "mushroom_imp", "thornling", "treant",
    # Welle 13 — Stein/Kristall/Untot
    "stone_golem", "crystal_golem", "gargoyle", "bone_crawler", "giant_spider",
    # Welle 13 — Bosse
    "minotaur", "harpy", "basilisk", "chimera", "griffin", "hydra", "manticore",
]
BOSS_KINDS = ["ogre", "necromancer", "dragon_whelp",
              "minotaur", "harpy", "basilisk", "chimera", "griffin", "hydra", "manticore"]
NPC_KINDS = FRIENDLY_KINDS + CREATURE_KINDS

# Wander-Tick alle N Sekunden, pro NPC unabhängige Wahrscheinlichkeit zu bewegen
NPC_WANDER_TICK_SECONDS = float(os.environ.get("NPC_WANDER_TICK_SECONDS", "2.0"))
# Bewegungs-Wahrscheinlichkeit pro Tick, pro Kind unterschiedlich
NPC_MOVE_CHANCE = {
    "wanderer":  0.25,  # läuft viel rum
    "merchant":  0.10,  # bleibt eher
    "hermit":    0.05,  # bleibt fast immer
    "bard":      0.20,
    "scholar":   0.08,
    "soldier":   0.15,
    # Welle 21 — neue NPC-Kinds
    "mage":        0.10,  # konzentriert
    "farmer":      0.15,  # arbeitet auf Feld
    "villager":    0.22,
    "guard":       0.18,  # patrouilliert
    "healer":      0.08,
    "quest_giver": 0.05,  # bleibt am Platz
    "blacksmith":  0.05,  # bleibt an der Schmiede
    # Asset-Drop 2026-05-26
    "miner":        0.20,  # gräbt in einer Region
    "village_elder":0.05,  # bleibt fast immer
    "watchman":     0.18,  # patrouilliert
    "cat":          0.40,  # streunt
    "dog":          0.30,
    "child":        0.35,  # spielt, läuft viel
    "goblin":    0.30,  # nervös
    "wolf":      0.35,
    "skeleton":  0.15,
    "spider":    0.20,
    "slime":     0.10,
    # Welle 3
    "rat":       0.45,  # huschig
    "bat":       0.55,  # fliegt schnell
    "zombie":    0.08,  # schlurft
    "bandit":    0.25,  # patrouilliert
    "boar":      0.30,  # wild
    "bear":      0.18,  # gemächlich
    "ogre":         0.08,
    "necromancer":  0.10,
    "dragon_whelp": 0.25,
    # Welle 13
    "stag":         0.35,  # scheu, schnell
    "lynx":         0.40,  # lauernd, schnell
    "cougar":       0.30,
    "wolverine":    0.28,
    "dire_wolf":    0.38,
    "wolf_alpha":   0.30,  # bedacht, führt Rudel
    "cave_bear":    0.20,
    "polar_bear":   0.18,
    "crocodile":    0.10,  # lauernd
    "cobra":        0.25,
    "slimelet":     0.18,
    "fae_mite":     0.45,  # flink
    "gloom_moth":   0.35,
    "ember_newt":   0.20,
    "ember_rat":    0.50,  # huschig
    "shadow_bat":   0.55,
    "thorn_scarab": 0.25,
    "crystal_beetle":0.20,
    "crystal_tick": 0.30,
    "frost_sprite": 0.30,
    "fire_imp":     0.35,
    "mushroom_imp": 0.22,
    "thornling":    0.20,
    "treant":       0.05,  # langsam
    "stone_golem":  0.04,  # sehr langsam
    "crystal_golem":0.05,
    "gargoyle":     0.08,
    "bone_crawler": 0.18,
    "giant_spider": 0.22,
    "minotaur":     0.18,
    "harpy":        0.30,
    "basilisk":     0.12,
    "chimera":      0.20,
    "griffin":      0.28,
    "hydra":        0.10,
    "manticore":    0.22,
}

IDENTITY_SYSTEM = (
    "Du erfindest Bewohner einer Fantasy-Welt. Antworte AUSSCHLIESSLICH als gültiges JSON."
)


def _identity_prompt(kind: str) -> str:
    is_creature = kind in CREATURE_KINDS
    type_hint = "eine wilde Kreatur" if is_creature else "einen Bewohner"
    name_hint = (
        "eine kurze Bezeichnung dieser Kreatur, ggf. mit charakteristischem Beinamen"
        if is_creature
        else "fantasievoller Eigenname"
    )
    story_hint = (
        "1-2 Sätze: ihr Habitat, Verhalten oder eine Begegnung mit Reisenden"
        if is_creature
        else "1-2 Sätze: was diese Person hierher führte"
    )
    return (
        f'Erfinde {type_hint} vom Typ "{kind}" für eine lebende Fantasy-Welt. Felder:\n'
        f'  "name": {name_hint} (max 24 Zeichen, Deutsch)\n'
        f'  "backstory": {story_hint} (Deutsch)\n'
        '  "mood": eine kurze Stimmung ("freundlich" | "misstrauisch" | "fröhlich" | '
        '"melancholisch" | "neugierig" | "stolz" | "müde" | "wütend" | "scheu")\n'
        'Beispiel: {"name": "Grimm Eberzahn", "backstory": "Ein einsamer Wolfsanführer, '
        'der seit Wochen die Wege jenseits des Waldes belauert.", "mood": "misstrauisch"}'
    )


async def _find_spawn_position(world, connection_manager=None,
                               biomes: set[int] | None = None) -> tuple[int, int]:
    """Findet ein walkbares Tile in der Nähe eines aktiven Spielers (sonst nahe Welt-Mitte).
    Wenn `biomes` gegeben: bevorzugt Tiles dieser Biome; fällt nach Versuchen auf
    irgendein walkbares Tile zurück."""
    center_x, center_y = 60, 40
    if connection_manager is not None:
        players = connection_manager.get_players()
        if players:
            p = random.choice(list(players.values()))
            center_x, center_y = p["x"], p["y"]
    # Erst Versuch mit Biome-Match
    if biomes:
        for _ in range(160):
            angle = random.random() * 6.283
            dist = random.randint(8, 30)
            x = center_x + int(math.cos(angle) * dist)
            y = center_y + int(math.sin(angle) * dist)
            tile = await world.tile_at(x, y)
            if tile in biomes:
                return x, y
    # Fallback: irgendein walkbares Tile
    for _ in range(200):
        angle = random.random() * 6.283
        dist = random.randint(8, 25)
        x = center_x + int(math.cos(angle) * dist)
        y = center_y + int(math.sin(angle) * dist)
        if await world.is_walkable(x, y):
            return x, y
    s = await world.find_spawn(center_x, center_y)
    return s["x"], s["y"]


async def _find_nearby_walkable(world, cx: int, cy: int, radius: int = 3) -> tuple[int, int]:
    """Findet ein walkbares Tile im Quadrat radius um (cx, cy) — für Gruppen-Spawning."""
    for _ in range(50):
        x = cx + random.randint(-radius, radius)
        y = cy + random.randint(-radius, radius)
        if await world.is_walkable(x, y):
            return x, y
    return cx, cy


async def spawn_one(world, npc_manager, connection_manager, kind: str | None = None,
                    at: tuple[int, int] | None = None) -> dict | None:
    kind = kind or random.choice(NPC_KINDS)
    try:
        raw = await llm.slow_brain(_identity_prompt(kind), system=IDENTITY_SYSTEM, json_mode=True)
        data = json.loads(raw)
        name = str(data.get("name", "")).strip()[:24]
        backstory = str(data.get("backstory", "")).strip()[:500]
        mood = str(data.get("mood", "neutral")).strip()[:32]
        if not name or not backstory:
            log.warning("NPC-Identität unvollständig: %s", data)
            return None
    except (json.JSONDecodeError, Exception) as e:
        log.warning("NPC-Identität LLM-Fehler: %s", e)
        return None

    if at is not None:
        x, y = at
    else:
        biomes = (CREATURE_SPAWN_PROFILE.get(kind) or {}).get("biomes")
        x, y = await _find_spawn_position(world, connection_manager, biomes=biomes)
    base_hp = combat.NPC_HP_BY_KIND.get(kind, 40)
    # Welle 30: Power-Budget — Mob-HP skaliert mit nahem Player-Level
    try:
        import power_budget, skills as _skills
        player_lvl = 0
        for pname in connection_manager.get_players().keys():
            sk = await _skills.get_skills(pname)
            player_lvl = max(player_lvl, power_budget.player_level_estimate(sk))
        max_hp = power_budget.kalibrate_mob_hp(base_hp, player_lvl)
    except Exception:
        max_hp = base_hp
    # Sprite-Variante pro spawn random aus dem Pool (bandit_axe, soldier_spear, …).
    variant_pool = SPRITE_VARIANTS_BY_KIND.get(kind)
    sprite_variant = random.choice(variant_pool) if variant_pool else None
    npc = await npc_manager.create(name, kind, x, y, backstory,
                                   max_hp=max_hp, sprite_variant=sprite_variant)
    if mood != "neutral":
        npc["mood"] = mood  # nur in-memory, mood-update in DB können wir später wenn nötig
    await connection_manager.broadcast({"type": "npc_spawned", "npc": npc})
    log.info("NPC gespawnt: %s (%s) @ (%d, %d)", npc["name"], npc["kind"], x, y)
    return npc


async def respawn_loop(world, npc_manager, connection_manager) -> None:
    """Periodisch: wenn weniger als MIN_CREATURE_COUNT Creatures existieren, spawne nach.
    Gruppen-Größe und Biome richten sich nach CREATURE_SPAWN_PROFILE pro Kind."""
    log.info("Creature-Respawn-Loop startet (interval=%ds, min=%d)",
             CREATURE_RESPAWN_INTERVAL, MIN_CREATURE_COUNT)
    await asyncio.sleep(60)  # Lange Anlaufzeit damit Initial-Spawn vorbei ist
    while True:
        try:
            await asyncio.sleep(CREATURE_RESPAWN_INTERVAL)
            creatures = [n for n in npc_manager.all() if n["kind"] in CREATURE_KINDS]
            deficit = MIN_CREATURE_COUNT - len(creatures)
            if deficit <= 0:
                continue
            kind = random.choice(CREATURE_KINDS)
            profile = CREATURE_SPAWN_PROFILE.get(kind, {"group": (1, 1), "biomes": None})
            group_min, group_max = profile["group"]
            group_size = min(random.randint(group_min, group_max), deficit)
            biomes = profile["biomes"]
            # Center für Gruppe finden (biome-präferiert), dann Gruppen-Mitglieder in radius
            cx, cy = await _find_spawn_position(world, connection_manager, biomes=biomes)
            log.info("Gruppen-Respawn: %d × %s @(%d,%d) biome=%s (deficit=%d)",
                     group_size, kind, cx, cy, biomes, deficit)
            await spawn_one(world, npc_manager, connection_manager, kind=kind, at=(cx, cy))
            for _ in range(group_size - 1):
                nx, ny = await _find_nearby_walkable(world, cx, cy, radius=3)
                await spawn_one(world, npc_manager, connection_manager, kind=kind, at=(nx, ny))
        except asyncio.CancelledError:
            log.info("Creature-Respawn-Loop gestoppt")
            raise
        except Exception:
            log.exception("Creature-Respawn-Iteration fehlgeschlagen")


async def initial_spawn(world, npc_manager, connection_manager) -> None:
    """Spawnt INITIAL_NPC_COUNT NPCs, falls die Welt noch keine hat.
    Mischt friendly + creatures je ~50/50."""
    if npc_manager.count() > 0:
        log.info("NPCs bereits vorhanden (%d) — kein Initial-Spawn", npc_manager.count())
        return
    log.info("Spawne %d initiale NPCs …", INITIAL_NPC_COUNT)
    half = max(1, INITIAL_NPC_COUNT // 2)
    kinds = (
        random.sample(FRIENDLY_KINDS, min(half, len(FRIENDLY_KINDS)))
        + random.sample(CREATURE_KINDS, min(INITIAL_NPC_COUNT - half, len(CREATURE_KINDS)))
    )
    random.shuffle(kinds)
    for kind in kinds:
        await spawn_one(world, npc_manager, connection_manager, kind=kind)
    log.info("Initial-Spawn fertig.")


async def _try_aggression(npc, world, npc_manager, connection_manager, damage_cb) -> bool:
    """Creature-Verhalten: Spieler in Aggro-Range jagen, Spieler in Attack-Range angreifen.
    Returnt True wenn ein Verhalten ausgelöst wurde."""
    players = connection_manager.get_players()
    if not players:
        return False
    nearest_name, nearest_dist, nearest_data = None, float("inf"), None
    for pname, pdata in players.items():
        d = combat.manhattan(npc["x"], npc["y"], pdata["x"], pdata["y"])
        if d < nearest_dist:
            nearest_name, nearest_dist, nearest_data = pname, d, pdata
    if nearest_name is None or nearest_dist > combat.AGGRO_RANGE:
        return False
    if nearest_dist <= combat.ATTACK_RANGE:
        dmg = combat.creature_damage(npc["kind"])
        # Power-Budget: Damage skaliert mit Player-Level
        try:
            import power_budget, skills as _skills
            sk = await _skills.get_skills(nearest_name)
            plvl = power_budget.player_level_estimate(sk)
            dmg = power_budget.kalibrate_mob_damage(dmg, plvl)
        except Exception:
            pass
        await damage_cb(nearest_name, dmg, npc["id"])
        await connection_manager.broadcast({
            "type":   "npc_attacked",
            "npc_id": npc["id"],
            "target": nearest_name,
            "dmg":    dmg,
        })
        return True
    # Approach — bevorzugt Achse mit größerem Abstand
    dx_sign = 0 if nearest_data["x"] == npc["x"] else (1 if nearest_data["x"] > npc["x"] else -1)
    dy_sign = 0 if nearest_data["y"] == npc["y"] else (1 if nearest_data["y"] > npc["y"] else -1)
    if abs(nearest_data["x"] - npc["x"]) >= abs(nearest_data["y"] - npc["y"]):
        dirs = [(dx_sign, 0), (0, dy_sign)]
    else:
        dirs = [(0, dy_sign), (dx_sign, 0)]
    for dx, dy in dirs:
        if dx == 0 and dy == 0:
            continue
        nx, ny = npc["x"] + dx, npc["y"] + dy
        if world.is_walkable_sync(nx, ny):
            await npc_manager.move(npc["id"], nx, ny)
            await connection_manager.broadcast({
                "type":   "npc_moved",
                "npc_id": npc["id"],
                "x":      nx,
                "y":      ny,
            })
            return True
    return False


async def _try_move_toward(npc, tx, ty, world, npc_manager, connection_manager) -> bool:
    """Bewegt NPC einen Schritt Richtung (tx, ty). Returns True wenn bewegt."""
    dx = 0 if tx == npc["x"] else (1 if tx > npc["x"] else -1)
    dy = 0 if ty == npc["y"] else (1 if ty > npc["y"] else -1)
    # Bevorzuge größere Achse
    if abs(tx - npc["x"]) >= abs(ty - npc["y"]):
        dirs = [(dx, 0), (0, dy)]
    else:
        dirs = [(0, dy), (dx, 0)]
    for ddx, ddy in dirs:
        if ddx == 0 and ddy == 0:
            continue
        nx, ny = npc["x"] + ddx, npc["y"] + ddy
        if world.is_walkable_sync(nx, ny):
            await npc_manager.move(npc["id"], nx, ny)
            await connection_manager.broadcast({
                "type": "npc_moved", "npc_id": npc["id"], "x": nx, "y": ny,
            })
            return True
    return False


async def _try_random_move(npc, world, npc_manager, connection_manager) -> None:
    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    random.shuffle(dirs)
    for dx, dy in dirs:
        nx, ny = npc["x"] + dx, npc["y"] + dy
        if world.is_walkable_sync(nx, ny):
            await npc_manager.move(npc["id"], nx, ny)
            await connection_manager.broadcast({
                "type":   "npc_moved",
                "npc_id": npc["id"],
                "x":      nx,
                "y":      ny,
            })
            return


async def wander_loop(world, npc_manager, connection_manager, damage_player_cb=None) -> None:
    """Pro Tick (~2s): Creatures versuchen Aggression, andere random walken.
    damage_player_cb: async function (player_name, dmg, source_npc_id) — Aggression callback."""
    log.info("NPC-Wander-Loop startet (tick=%.1fs)", NPC_WANDER_TICK_SECONDS)
    await asyncio.sleep(10)
    while True:
        try:
            await asyncio.sleep(NPC_WANDER_TICK_SECONDS)
            for npc in list(npc_manager.all()):  # copy weil damage löschen kann
                # Creatures: Aggression versuchen (jeden Tick — Verfolgung soll konsistent sein)
                if npc["kind"] in combat.CREATURE_KINDS and damage_player_cb is not None:
                    if await _try_aggression(npc, world, npc_manager, connection_manager, damage_player_cb):
                        continue
                # Random Wander mit kind-spezifischer Chance — Tag/Nacht modulieren
                chance = NPC_MOVE_CHANCE.get(npc["kind"], 0.15)
                try:
                    import time_system  # lokaler Import — Avoid circular bei Tests
                    is_night = time_system.clock.is_night()
                except Exception:
                    is_night = False
                is_friendly = npc["kind"] in FRIENDLY_KINDS
                if is_night and is_friendly:
                    chance *= 0.2   # Friendlies schlafen / bleiben in Hütte
                elif is_night and not is_friendly:
                    chance *= 1.3   # Creatures aktiver nachts
                if random.random() >= chance:
                    continue
                # Tagesablauf: nachts wandert friendly NPC zum home zurück
                home_x = npc.get("home_x")
                home_y = npc.get("home_y")
                if (is_night and is_friendly and home_x is not None
                        and home_y is not None
                        and (abs(npc["x"] - home_x) + abs(npc["y"] - home_y)) > 2):
                    await _try_move_toward(npc, home_x, home_y, world,
                                            npc_manager, connection_manager)
                    continue
                await _try_random_move(npc, world, npc_manager, connection_manager)
        except asyncio.CancelledError:
            log.info("NPC-Wander-Loop gestoppt")
            raise
        except Exception:
            log.exception("NPC-Wander-Iteration fehlgeschlagen")
