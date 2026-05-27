import asyncio
import json
import logging
import math
import os
import random

import combat
import llm
import npc_chatter
import npc_goals
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

    # — Welle 14 — professional monster asset-drop (2026-05-26b) —
    "razorback_vermin":      {"group": (3, 6),  "biomes": {GRASS, FOREST, DESERT}},
    "spined_abyss_larva":    {"group": (2, 4),  "biomes": {SWAMP, JUNGLE}},
    "reed_walker":           {"group": (1, 3),  "biomes": {SWAMP, JUNGLE}},
    "redland_scavenger":     {"group": (2, 4),  "biomes": {DESERT}},
    "mossback_warden":       {"group": (1, 2),  "biomes": {FOREST, JUNGLE}},
    "grave_wraith":          {"group": (1, 2),  "biomes": {SWAMP, DESERT}},
    "serpent_oracle":        {"group": (1, 1),  "biomes": {DESERT, JUNGLE}},
    "urtikus_eye_fiend":     {"group": (1, 1),  "biomes": {SWAMP}},
    "mantis_chimera":        {"group": (1, 2),  "biomes": {JUNGLE, FOREST}},
    "iron_spider":           {"group": (1, 1),  "biomes": {DESERT}},
    "dendroid_guardian":     {"group": (1, 1),  "biomes": {FOREST, JUNGLE}},
    "blood_antler_drake":    {"group": (1, 1),  "biomes": {FOREST, SNOW}},
    # Bosse — alle solo
    "kaiju_thornback":       {"group": (1, 1),  "biomes": {JUNGLE, SWAMP}},
    "void_eye_brute":        {"group": (1, 1),  "biomes": {SWAMP}},
    "frost_rune_boar_prime": {"group": (1, 1),  "biomes": {SNOW}},
    "magma_shell_devourer":  {"group": (1, 1),  "biomes": {DESERT}},
    "rockshell_colossus":    {"group": (1, 1),  "biomes": {SNOW, DESERT}},
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
    # Welle 14 — professional asset-drop (2026-05-26b)
    "razorback_vermin", "spined_abyss_larva", "reed_walker", "redland_scavenger",
    "mossback_warden", "grave_wraith", "serpent_oracle", "urtikus_eye_fiend",
    "mantis_chimera", "iron_spider", "dendroid_guardian", "blood_antler_drake",
    "kaiju_thornback", "void_eye_brute", "frost_rune_boar_prime",
    "magma_shell_devourer", "rockshell_colossus",
]
BOSS_KINDS = ["ogre", "necromancer", "dragon_whelp",
              "minotaur", "harpy", "basilisk", "chimera", "griffin", "hydra", "manticore",
              # Welle 14 — neue Bosse
              "kaiju_thornback", "void_eye_brute", "frost_rune_boar_prime",
              "magma_shell_devourer", "rockshell_colossus"]
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
    # Welle 14 — professional asset-drop (2026-05-26b)
    "razorback_vermin":      0.45,  # huschig
    "spined_abyss_larva":    0.20,  # kriecht
    "reed_walker":           0.25,
    "redland_scavenger":     0.30,
    "mossback_warden":       0.12,  # bedacht
    "grave_wraith":          0.22,  # gleitet
    "serpent_oracle":        0.15,  # kontemplativ
    "urtikus_eye_fiend":     0.18,
    "mantis_chimera":        0.30,  # zwitschernd schnell
    "iron_spider":           0.20,  # mechanisch
    "dendroid_guardian":     0.05,  # baum-langsam
    "blood_antler_drake":    0.25,
    # Bosse — bedächtig
    "kaiju_thornback":       0.10,
    "void_eye_brute":        0.08,
    "frost_rune_boar_prime": 0.18,
    "magma_shell_devourer":  0.06,
    "rockshell_colossus":    0.04,
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
                               biomes: set[int] | None = None,
                               strict: bool = True) -> tuple[int, int] | None:
    """Findet ein walkbares Tile in der Nähe eines aktiven Spielers.
    Wenn `biomes` gegeben und `strict`: NUR Tiles dieser Biome (kein
    Fallback auf irgendwelches walkable — sonst landen Schweine in der
    Wüste oder Drachen im Wald).
    Bei strict + Fehlschlag → None (Spawn überspringen).
    Ohne biome-filter / strict=False: jedes walkbare Tile."""
    center_x, center_y = 60, 40
    if connection_manager is not None:
        players = connection_manager.get_players()
        if players:
            p = random.choice(list(players.values()))
            center_x, center_y = p["x"], p["y"]
    if biomes:
        # Strikter Versuch — wirklich nur passende Biome
        for _ in range(400):
            angle = random.random() * 6.283
            dist = random.randint(8, 35)
            x = center_x + int(math.cos(angle) * dist)
            y = center_y + int(math.sin(angle) * dist)
            tile = await world.tile_at(x, y)
            if tile in biomes:
                return x, y
        if strict:
            return None  # Kein passendes Biome erreichbar → kein Spawn
    # Ohne biome-filter / non-strict: irgendein walkbares Tile
    for _ in range(200):
        angle = random.random() * 6.283
        dist = random.randint(8, 25)
        x = center_x + int(math.cos(angle) * dist)
        y = center_y + int(math.sin(angle) * dist)
        if await world.is_walkable(x, y):
            return x, y
    s = await world.find_spawn(center_x, center_y)
    return (s["x"], s["y"])


async def find_event_cluster_center(world, connection_manager,
                                     biomes: set[int] | None = None,
                                     min_dist: int = 18,
                                     max_dist: int = 32) -> tuple[int, int] | None:
    """Welle 21: Pickt EINEN Cluster-Mittelpunkt in einer zufälligen Richtung
    um einen aktiven Spieler — für 'Welle-Spawns'. Returns (x,y) oder None.

    Wenn biomes gesetzt: muss in passendem Biome liegen.
    Distanz min_dist..max_dist Tiles vom Spieler (Standard 18-32: außerhalb
    der Sicht aber so dass die Welle sich bewegen kann)."""
    players = list(connection_manager.get_players().values()) if connection_manager else []
    if not players:
        return None
    p = random.choice(players)
    cx, cy = p["x"], p["y"]
    for _ in range(200):
        angle = random.random() * 6.283
        dist = random.randint(min_dist, max_dist)
        x = cx + int(math.cos(angle) * dist)
        y = cy + int(math.sin(angle) * dist)
        if not await world.is_walkable(x, y):
            continue
        if biomes:
            tile = await world.tile_at(x, y)
            if tile not in biomes:
                continue
        return (x, y)
    return None


async def spawn_cluster(world, npc_manager, connection_manager, kind: str,
                        count: int, jitter: int = 4) -> tuple[int, int] | None:
    """Welle 21: spawn `count` Mobs in einem Cluster um EINEN gemeinsamen
    Mittelpunkt (echte 'Welle' / 'Horde' / 'Raid'). Returns Cluster-Center
    oder None wenn kein passender Spawnpunkt."""
    biomes = (CREATURE_SPAWN_PROFILE.get(kind) or {}).get("biomes")
    center = await find_event_cluster_center(world, connection_manager, biomes=biomes)
    if center is None:
        # Fallback: ohne Biome-Filter
        center = await find_event_cluster_center(world, connection_manager, biomes=None)
    if center is None:
        return None
    cx, cy = center
    for _ in range(count):
        # Jitter um den Cluster-Center
        for _try in range(20):
            jx = cx + random.randint(-jitter, jitter)
            jy = cy + random.randint(-jitter, jitter)
            if await world.is_walkable(jx, jy):
                await spawn_one(world, npc_manager, connection_manager,
                                 kind=kind, at=(jx, jy))
                break
    return center


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
        pos = await _find_spawn_position(world, connection_manager, biomes=biomes, strict=True)
        if pos is None:
            log.info("Spawn-Skip: kein passendes Biome für %s erreichbar", kind)
            return None
        x, y = pos
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
            # Center für Gruppe finden (strict biome) — kein Spawn wenn nichts passt
            pos = await _find_spawn_position(world, connection_manager, biomes=biomes, strict=True)
            if pos is None:
                log.info("Gruppen-Respawn-Skip: kein passendes Biome für %s", kind)
                continue
            cx, cy = pos
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


async def _try_aggression(npc, world, npc_manager, connection_manager, damage_cb,
                           structures_mgr=None) -> bool:
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
    # Welle 15: per-Kind Aggro-Range (Stalker sehen weiter, Scheue weniger)
    _kind_aggro = combat.creature_stats(npc["kind"]).get("aggro_range", combat.AGGRO_RANGE)
    if nearest_name is None or nearest_dist > _kind_aggro:
        return False
    if nearest_dist <= combat.ATTACK_RANGE:
        # Welle 17: LoS-Check — Wand/Geschlossene Tür zwischen NPC und Spieler
        # blockt den Angriff. Gebäude sind dadurch echter Schutz.
        if not _has_attack_los(npc, nearest_data["x"], nearest_data["y"],
                                world, structures_mgr):
            return False
        dmg = combat.creature_damage(npc["kind"])
        # Power-Budget: Damage skaliert mit Player-Level
        try:
            import power_budget, skills as _skills
            sk = await _skills.get_skills(nearest_name)
            plvl = power_budget.player_level_estimate(sk)
            dmg = power_budget.kalibrate_mob_damage(dmg, plvl)
        except Exception:
            pass
        # Welle 15: themed-Mobs verursachen typed damage (fire/ice/...)
        _dmg_type = combat.creature_stats(npc["kind"]).get("damage_type", "physical")
        await damage_cb(nearest_name, dmg, npc["id"], _dmg_type)
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
        if _can_walk(nx, ny, world, structures_mgr):
            await npc_manager.move(npc["id"], nx, ny)
            await connection_manager.broadcast({
                "type":   "npc_moved",
                "npc_id": npc["id"],
                "x":      nx,
                "y":      ny,
            })
            return True
    return False


def _can_walk(x: int, y: int, world, structures_mgr) -> bool:
    """Walkable = TILE ist begehbar UND keine blockende Struktur drauf.
    structures_mgr=None disabled den Struktur-Check (Legacy-Fallback)."""
    if not world.is_walkable_sync(x, y):
        return False
    if structures_mgr is not None and structures_mgr.blocks(x, y):
        return False
    return True


def _has_attack_los(npc, target_x: int, target_y: int, world,
                     structures_mgr) -> bool:
    """Line-of-Sight für Attack: NPC kann Player NICHT angreifen wenn dazwischen
    eine Wand/geschlossene Tür/Felsen liegt. Verwendet Bresenham für Distanz>1,
    bei Distanz 1 (adjacent) ist LoS immer klar.

    Wichtig: ein geschlossenes Tor zwischen NPC und Spieler blockt den Angriff.
    Damit bietet ein Gebäude echten Schutz, solange Türen zu sind."""
    if structures_mgr is None:
        return True
    dx = target_x - npc["x"]
    dy = target_y - npc["y"]
    steps = max(abs(dx), abs(dy))
    if steps <= 1:
        return True   # adjacent → kein Tile zwischen
    # Bresenham — gehe alle Zwischen-Tiles ab, ohne start und end
    for i in range(1, steps):
        ix = npc["x"] + round(dx * i / steps)
        iy = npc["y"] + round(dy * i / steps)
        if structures_mgr.blocks(ix, iy):
            return False
    return True


async def _try_move_toward(npc, tx, ty, world, npc_manager, connection_manager,
                            structures_mgr=None) -> bool:
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
        if _can_walk(nx, ny, world, structures_mgr):
            await npc_manager.move(npc["id"], nx, ny)
            await connection_manager.broadcast({
                "type": "npc_moved", "npc_id": npc["id"], "x": nx, "y": ny,
            })
            return True
    return False


async def _try_random_move(npc, world, npc_manager, connection_manager,
                            structures_mgr=None) -> None:
    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    random.shuffle(dirs)
    for dx, dy in dirs:
        nx, ny = npc["x"] + dx, npc["y"] + dy
        if _can_walk(nx, ny, world, structures_mgr):
            await npc_manager.move(npc["id"], nx, ny)
            await connection_manager.broadcast({
                "type":   "npc_moved",
                "npc_id": npc["id"],
                "x":      nx,
                "y":      ny,
            })
            return


async def wander_loop(world, npc_manager, connection_manager,
                       damage_player_cb=None, structures_mgr=None) -> None:
    """Pro Tick (~2s): Creatures versuchen Aggression, andere random walken.
    damage_player_cb: async function (player_name, dmg, source_npc_id, dmg_type).
    structures_mgr: StructureManager — verhindert NPC durch Wände/Türen."""
    log.info("NPC-Wander-Loop startet (tick=%.1fs)", NPC_WANDER_TICK_SECONDS)
    await asyncio.sleep(10)
    while True:
        try:
            await asyncio.sleep(NPC_WANDER_TICK_SECONDS)
            for npc in list(npc_manager.all()):  # copy weil damage löschen kann
                # Creatures: Aggression versuchen (jeden Tick — Verfolgung soll konsistent sein)
                if npc["kind"] in combat.CREATURE_KINDS and damage_player_cb is not None:
                    if await _try_aggression(npc, world, npc_manager, connection_manager,
                                              damage_player_cb, structures_mgr):
                        continue
                # Random Wander mit kind-spezifischer Chance — Tag/Nacht modulieren
                chance = NPC_MOVE_CHANCE.get(npc["kind"], 0.15)
                try:
                    import time_system  # lokaler Import — Avoid circular bei Tests
                    is_night = time_system.clock.is_night()
                except Exception:
                    is_night = False
                is_friendly = npc["kind"] in FRIENDLY_KINDS
                # Welle 20: NPC-Chatter — adjacent friendly NPCs plaudern
                if is_friendly:
                    try:
                        await npc_chatter.maybe_chat(npc, npc_manager, connection_manager)
                    except Exception:
                        log.debug("npc_chatter failed", exc_info=True)
                if is_night and is_friendly:
                    chance *= 0.2   # Friendlies schlafen / bleiben in Hütte
                elif is_night and not is_friendly:
                    chance *= 1.3   # Creatures aktiver nachts
                if random.random() >= chance:
                    continue

                # ── Welle 20: NPC-Goal-System (friendly NPCs mit Tagesplan) ──
                if is_friendly and structures_mgr is not None:
                    # Goal repicken wenn nötig (Phase gewechselt, Reached, Stuck)
                    if npc_goals.should_repick_goal(npc):
                        g = npc_goals.pick_goal(npc, structures_mgr, npc_manager)
                        if g is not None:
                            goal, gx, gy = g
                            old_goal = npc.get("_goal")
                            npc_goals.assign_goal(npc, goal, gx, gy)
                            # Broadcast Goal-Change damit Frontend Icon zeigt
                            if old_goal != goal:
                                await connection_manager.broadcast({
                                    "type":    "npc_goal",
                                    "npc_id":  npc["id"],
                                    "goal":    goal,
                                    "emoji":   npc_goals.goal_emoji(goal),
                                })
                        else:
                            npc_goals.clear_goal(npc)
                    # Wenn aktives Goal: gezielt dorthin laufen statt random
                    gtx, gty = npc.get("_goal_target_x"), npc.get("_goal_target_y")
                    if gtx is not None and gty is not None and not npc_goals.goal_reached(npc):
                        prev_d = abs(gtx - npc["x"]) + abs(gty - npc["y"])
                        moved = await _try_move_toward(
                            npc, gtx, gty, world, npc_manager, connection_manager,
                            structures_mgr,
                        )
                        new_d = abs(gtx - npc["x"]) + abs(gty - npc["y"])
                        if not moved or new_d >= prev_d:
                            npc["_goal_stuck_count"] = npc.get("_goal_stuck_count", 0) + 1
                        else:
                            npc["_goal_stuck_count"] = 0
                        continue

                # Fallback: random walk
                await _try_random_move(npc, world, npc_manager, connection_manager,
                                        structures_mgr)
        except asyncio.CancelledError:
            log.info("NPC-Wander-Loop gestoppt")
            raise
        except Exception:
            log.exception("NPC-Wander-Iteration fehlgeschlagen")
