"""Monster-Longlist (Welle 34) — daten-getriebene Integration der 133
generated_longlist-Monster ins Combat-/Spawn-/Loot-System.

Liest die beiden Manifeste:
  - world_sprites/generated_longlist/manifest.json  (id, name, tier, section)
  - generated_longlist/manifest.json                (source_columns: Größe/Biome/Mechanik)

und leitet daraus Stats, Spawn-Profile, Boss-Flags und Loot-Tabellen ab.
combat.py / npc_worker.py / loot.py mergen diese Daten in ihre Tabellen.

Die Sprite-Verdrahtung passiert im Frontend (eigene generierte Liste).
"""

import json
import os
import re
import logging

log = logging.getLogger("liege.monster_longlist")

# Biome-IDs — identisch zu world.py (bewusst dupliziert, kein Import-Coupling).
WATER, SAND, GRASS, FOREST, MOUNTAIN = 0, 1, 2, 3, 4
DESERT, JUNGLE, LAVA, SNOW, SWAMP = 5, 6, 7, 8, 9
# MOUNTAIN/LAVA/WATER sind NICHT begehbar → nie als Spawn-Biome verwenden.

_BASE = os.path.join(os.path.dirname(__file__), "..", "assets", "monsters")
_WORLD_MF = os.path.join(_BASE, "world_sprites", "generated_longlist", "manifest.json")
_CELLS_MF = os.path.join(_BASE, "generated_longlist", "manifest.json")

# Tier → (base_hp, base_dmg, defense, speed, aggro)
_TIER_STATS = {
    1: (28,  5,  0, 1.05, 5),
    2: (60,  11, 2, 1.0,  6),
    3: (120, 18, 5, 0.95, 7),
    4: (230, 27, 9, 0.9,  8),
    5: (420, 38, 14, 0.85, 9),
}

# Biome-Keywords (lowercase) → Biome-ID-Set. Erste Treffer akkumulieren.
_BIOME_KEYWORDS = [
    (("sumpf", "moor", "marsch", "morast"),                {SWAMP}),
    (("wald", "hain", "forst", "hecke", "grove", "dryad"), {FOREST}),
    (("wüste", "wueste", "düne", "dune", "trockenland", "canyon", "pyramide", "sand"), {DESERT}),
    (("tundra", "eis", "schnee", "frost", "glacier", "gletscher", "polar", "eisberg", "arkt"), {SNOW}),
    (("berg", "klippe", "alp", "gebirge", "fels", "höhe", "hoehe", "ridge"), {SNOW, FOREST}),
    (("grasland", "feld", "wiese", "gras", "steppe"),      {GRASS}),
    (("fluss", "küste", "kueste", "see", "untiefe", "brunnen", "quelle", "ufer", "teich"), {SWAMP, SAND}),
    (("höhle", "hoehle", "krypta", "ruine", "grab", "ossuar", "knochen", "katakombe", "gruft"), {FOREST, SWAMP}),
    (("dschungel", "jungle", "regenwald"),                 {JUNGLE}),
    (("vulkan", "lava", "asche", "glut", "feuer", "flamme", "esse", "schmiede"), {DESERT}),
    (("stadt", "straße", "strasse", "lager", "camp", "karawane", "hauptstadt", "dorf"), {GRASS, FOREST, DESERT}),
    (("überall", "ueberall"),                              {GRASS, FOREST, DESERT, SWAMP, SNOW}),
]
_DEFAULT_BIOMES = {GRASS, FOREST}


def _biomes_from_text(text: str) -> set:
    t = text.lower()
    out = set()
    for kws, bio in _BIOME_KEYWORDS:
        if any(k in t for k in kws):
            out |= bio
    return out or set(_DEFAULT_BIOMES)


def _swarm_count(text: str) -> int | None:
    m = re.search(r"[×x]\s*(\d+)", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _is_boss(item: dict, text: str) -> bool:
    if item.get("section_index") == 10:
        return True
    if "boss" in item["id"]:
        return True
    tl = text.lower()
    return ("boss" in tl) and (item.get("tier") in ("4", "5"))


def _loot_for_tier(tier: int) -> list:
    """Gewichtete Drop-Tabelle pro Tier (Münzen fließen via _drop_loot_for_npc
    in den Geldbeutel). Equipment kommt separat über Boss-Garantie/Chests."""
    return {
        1: [("copper_coin", 60), ("bone", 30), ("cloth", 25), ("herb", 20), ("raw_meat", 20)],
        2: [("copper_coin", 50), ("silver_coin", 20), ("leather", 30), ("iron_ore", 18), ("bone", 25)],
        3: [("silver_coin", 45), ("iron_ore", 25), ("steel_ingot", 18), ("crystal", 15), ("gold_coin", 10)],
        4: [("gold_coin", 35), ("crystal", 30), ("mythril_ore", 18), ("steel_ingot", 20), ("silver_coin", 25)],
        5: [("gold_coin", 55), ("mythril_ore", 30), ("crystal", 35), ("rune_stone", 15), ("silver_coin", 20)],
    }.get(tier, [("copper_coin", 50), ("bone", 25)])


def _build():
    kinds, damage, hp, overrides = [], {}, {}, {}
    spawn, boss, loot, no_wild, names = {}, set(), {}, set(), {}
    try:
        wmf = json.load(open(_WORLD_MF, encoding="utf-8"))
        cmf = json.load(open(_CELLS_MF, encoding="utf-8"))
    except Exception:
        log.exception("monster_longlist: Manifest laden fehlgeschlagen")
        return dict(KINDS=[], DAMAGE={}, HP={}, STAT_OVERRIDES={}, SPAWN_PROFILE={},
                    BOSS_KINDS=set(), LOOT={}, NO_WILD=set(), NAMES={})

    # Slug → zusammengefügter source_columns-Text (für Biome/Größe/Mechanik)
    slug_text = {}
    for sec in cmf.get("sections", []):
        for a in sec.get("assets", []):
            slug_text[a["slug"]] = " | ".join(str(c) for c in a.get("source_columns", []))

    for it in wmf.get("items", []):
        kid = it["id"]
        sec_idx = it.get("section_index", 0)
        # Sektion 13 = Reittiere/Begleiter (nicht feindlich) → nicht ins Combat.
        if sec_idx == 13:
            continue
        text = slug_text.get(kid, "")
        try:
            tier = int(it.get("tier"))
        except (TypeError, ValueError):
            tier = 2
        tier = max(1, min(5, tier))
        base_hp, base_dmg, defense, speed, aggro = _TIER_STATS[tier]

        is_boss = _is_boss(it, text)
        swarm_n = _swarm_count(text)
        # Gruppengröße
        if swarm_n and swarm_n >= 2:
            group = (max(2, swarm_n - 3), swarm_n)
        elif is_boss:
            group = (1, 1)
        elif tier <= 1:
            group = (2, 4)
        elif tier == 2:
            group = (1, 3)
        else:
            group = (1, 2)

        # HP/DMG-Modifikatoren
        h, d = float(base_hp), float(base_dmg)
        if is_boss:
            h *= 1.8; d *= 1.2; speed = min(speed, 0.85); aggro += 1
        if group[1] >= 4:          # Schwarm → einzeln schwächer
            h *= 0.6; d *= 0.8; speed += 0.2

        kinds.append(kid)
        damage[kid] = max(1, int(round(d)))
        hp[kid] = max(8, int(round(h)))
        overrides[kid] = {"defense": defense, "speed": round(speed, 2),
                          "tier": tier, "aggro_range": int(aggro)}
        names[kid] = it.get("name", kid)
        loot[kid] = _loot_for_tier(tier)
        if is_boss:
            boss.add(kid)

        # Spawn: Sektion 11 (Disaster) + 12 (Lore-Carrier) NICHT im Wild-Respawn.
        if sec_idx in (11, 12):
            no_wild.add(kid)
        else:
            spawn[kid] = {"group": group, "biomes": _biomes_from_text(text)}

    log.info("monster_longlist: %d Kinds geladen (%d Bosse, %d no-wild)",
             len(kinds), len(boss), len(no_wild))
    return dict(KINDS=kinds, DAMAGE=damage, HP=hp, STAT_OVERRIDES=overrides,
                SPAWN_PROFILE=spawn, BOSS_KINDS=boss, LOOT=loot,
                NO_WILD=no_wild, NAMES=names)


_data = _build()
KINDS = _data["KINDS"]
DAMAGE = _data["DAMAGE"]
HP = _data["HP"]
STAT_OVERRIDES = _data["STAT_OVERRIDES"]
SPAWN_PROFILE = _data["SPAWN_PROFILE"]
BOSS_KINDS = _data["BOSS_KINDS"]
LOOT = _data["LOOT"]
NO_WILD = _data["NO_WILD"]
NAMES = _data["NAMES"]
