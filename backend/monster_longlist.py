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


# Section → Base-Loot-Pool, je nach Mob-Type sinnvoll thematisiert.
# Wird vom _loot_for_section_tier() mit Tier-Bonus-Items kombiniert.
# Münzen fließen via _drop_loot_for_npc in den Geldbeutel, Equipment via
# Boss-Garantie/Chests.
_SECTION_LOOT = {
    # Section 1 — Kleine/Schwarm-Bestien (T1): Fell, Knochen, Sehnen
    1: [("raw_meat", 35), ("bone", 40), ("leather", 25),
        ("sinew", 20), ("herb", 15), ("copper_coin", 35)],
    # Section 2 — Mittelgroße Bestien (T2): mehr Fleisch/Fell, ggf. Trophäen
    2: [("raw_meat", 55), ("leather", 55), ("bone", 40),
        ("fang", 20), ("horn", 15), ("copper_coin", 30), ("silver_coin", 12)],
    # Section 3 — Apex-Bestien (T3-4): dicke Trophäen, gute Verarbeitungs-Mats
    3: [("raw_meat", 75), ("leather", 75), ("bone", 60),
        ("fang", 35), ("horn", 30), ("silver_coin", 35), ("gold_coin", 12)],
    # Section 4 — Humanoide / Räuber & Banden: Stoff, Leder, Münzen, Waffen-Stücke
    4: [("cloth", 55), ("leather", 45), ("copper_coin", 60),
        ("silver_coin", 25), ("dagger", 8), ("herb", 20)],
    # Section 5 — Untote: Knochen, modrige Lumpen, Seelen-Splitter
    5: [("bone", 80), ("rotten_flesh", 30), ("tattered_cloth", 40),
        ("skull", 12), ("soul_essence", 18), ("silver_coin", 15)],
    # Section 6 — Magisch/Faye/Elementare: Kristalle, Tränke, Elementar-Essenzen
    6: [("crystal", 50), ("rune_stone", 22), ("mana_potion", 18),
        ("essence_arcane", 25), ("scroll", 30), ("silver_coin", 20)],
    # Section 7 — Eldritch/Aberration: Lore-Items, exotische Reagenzien
    7: [("aberrant_eye", 20), ("void_essence", 30), ("lore_fragment", 12),
        ("scroll", 25), ("rune_stone", 18), ("gold_coin", 25)],
    # Section 8 — Konstrukte: Stein, Erz, Kristall, Mythril
    8: [("stone", 60), ("iron_ore", 35), ("crystal", 30),
        ("steel_ingot", 18), ("mythril_ore", 10), ("rune_stone", 12)],
    # Section 9 — Drachen: Schuppen, Zähne, Hörner, viel Gold
    9: [("drake_scale", 80), ("dragon_tooth", 50), ("dragon_horn", 25),
        ("gold_coin", 60), ("crystal", 35), ("mythril_ore", 18)],
    # Section 10 — Setting-Bosse (T5): premium loot, viel Gold + Boss-Trophäe
    10: [("gold_coin", 80), ("crystal", 40), ("mythril_ore", 25),
         ("rune_stone", 25), ("scroll", 30), ("boss_trophy", 100)],
    # Section 11 — Disaster-Mobs: nur per Event, niedriger Standard-Loot
    11: [("bone", 20), ("rotten_flesh", 20), ("copper_coin", 25)],
    # Section 12 — Lore-Carrier: einzigartig, oft Quest-Item
    12: [("lore_fragment", 80), ("gold_coin", 50), ("scroll", 30),
         ("rune_stone", 25), ("unique_lore_item", 100)],
}

# Tier-Bonus: zusätzlich zum Section-Loot rollt jedes Mob nach Tier eine
# weitere Chance auf Münze/Material. Höhere Tier → wertvoller.
_TIER_BONUS = {
    1: [("copper_coin", 15)],
    2: [("silver_coin", 10), ("iron_ore", 8)],
    3: [("silver_coin", 18), ("steel_ingot", 10), ("crystal", 12)],
    4: [("gold_coin", 20), ("steel_ingot", 15), ("crystal", 18), ("mythril_ore", 8)],
    5: [("gold_coin", 35), ("mythril_ore", 18), ("crystal", 25), ("rune_stone", 15)],
}

# Slug-spezifische Overrides für Iconic Mobs — diese REPLACEN die
# section-basierte Default-Drop-Tabelle komplett (nicht extend).
_SLUG_LOOT_OVERRIDES = {
    # Untote-Spezifika
    "creature_lich_archivist": [
        ("bone", 100), ("phylactery_shard", 100), ("spell_book", 50),
        ("rune_stone", 60), ("scroll", 80), ("gold_coin", 100), ("mythril_ore", 30),
    ],
    "creature_vampire_lordling": [
        ("bone", 60), ("vampire_fang", 80), ("noble_cloak", 50),
        ("blood_chalice", 40), ("gold_coin", 80), ("silver_coin", 100), ("amulet", 30),
    ],
    "creature_ossuary_titan": [
        ("bone", 200), ("skull", 80), ("ossuary_core", 100),
        ("crystal", 50), ("gold_coin", 100), ("mythril_ore", 25),
    ],
    "creature_crypt_lord": [
        ("bone", 100), ("crypt_signet", 50), ("ancient_bandage", 60),
        ("scroll", 40), ("gold_coin", 80), ("silver_coin", 80),
    ],
    # Drachen-Spezifika
    "creature_chromatic_drake_red":   [("drake_scale", 100), ("fire_gland", 80),  ("dragon_tooth", 60), ("dragon_horn", 40), ("gold_coin", 80), ("mythril_ore", 25)],
    "creature_chromatic_drake_white": [("drake_scale", 100), ("frost_gland", 80), ("dragon_tooth", 60), ("dragon_horn", 40), ("gold_coin", 80), ("mythril_ore", 25)],
    "creature_chromatic_drake_black": [("drake_scale", 100), ("acid_gland", 80),  ("dragon_tooth", 60), ("dragon_horn", 40), ("gold_coin", 80), ("mythril_ore", 25)],
    "creature_chromatic_drake_green": [("drake_scale", 100), ("poison_gland", 80),("dragon_tooth", 60), ("dragon_horn", 40), ("gold_coin", 80), ("mythril_ore", 25)],
    "creature_chromatic_drake_blue":  [("drake_scale", 100), ("storm_gland", 80), ("dragon_tooth", 60), ("dragon_horn", 40), ("gold_coin", 80), ("mythril_ore", 25)],
    "creature_ancient_dragon_lord": [
        ("drake_scale", 200), ("dragon_heart", 100), ("dragon_horn", 80),
        ("dragon_tooth", 100), ("ancient_treasure", 100), ("gold_coin", 200),
        ("mythril_ore", 60), ("rune_stone", 50),
    ],
    # Eldritch-Spezifika
    "creature_thing_in_the_well": [
        ("tentacle_meat", 60), ("aberrant_eye", 50), ("void_essence", 80),
        ("well_idol", 30), ("scroll", 25),
    ],
    "creature_geometry_horror": [
        ("aberrant_eye", 60), ("void_essence", 100), ("impossible_angle", 100),
        ("rune_stone", 40), ("gold_coin", 50),
    ],
    "creature_choir_of_mouths": [
        ("aberrant_eye", 40), ("void_essence", 70), ("sanity_shard", 60),
        ("scroll", 30),
    ],
    # Elementare
    "creature_fire_elemental_lord": [
        ("fire_core", 100), ("essence_fire", 80), ("crystal", 50),
        ("mythril_ore", 35), ("rune_stone", 30), ("gold_coin", 60),
    ],
    "creature_water_elemental_brine": [
        ("essence_water", 60), ("crystal", 30), ("brine_pearl", 25),
        ("salt_lump", 40), ("silver_coin", 20),
    ],
    "creature_stone_elemental_lumbering": [
        ("stone", 100), ("iron_ore", 50), ("crystal", 30),
        ("granite_core", 25), ("silver_coin", 18),
    ],
    "creature_lightning_djinn": [
        ("essence_lightning", 80), ("storm_glass", 30), ("crystal", 40),
        ("mythril_ore", 20), ("scroll", 25), ("gold_coin", 50),
    ],
    "creature_frost_revenant_yeti": [
        ("arctic_pelt", 100), ("frost_fang", 60), ("essence_frost", 50),
        ("crystal", 30), ("silver_coin", 35),
    ],
    # Setting-Bosse
    "creature_boss_forest_old_mother": [
        ("ancient_silk", 100), ("spider_eye", 60), ("dryad_sap", 40),
        ("emerald_egg", 30), ("boss_trophy", 100), ("gold_coin", 100),
    ],
    "creature_boss_swamp_witchking": [
        ("witchking_crown", 100), ("ancient_bandage", 80), ("plague_phial", 50),
        ("scroll", 60), ("boss_trophy", 100), ("gold_coin", 100),
    ],
    "creature_boss_volcano_smith_demon": [
        ("demon_forge_hammer", 100), ("magma_heart", 80), ("mythril_ingot", 40),
        ("essence_fire", 50), ("boss_trophy", 100), ("gold_coin", 100),
    ],
    "creature_boss_mountain_avalanche_giant": [
        ("giant_femur", 100), ("avalanche_core", 80), ("stone", 80),
        ("essence_frost", 35), ("boss_trophy", 100), ("gold_coin", 100),
    ],
    "creature_boss_desert_pharaoh_revenant": [
        ("pharaoh_mask", 100), ("ancient_bandage", 100), ("scarab_amulet", 50),
        ("gold_coin", 150), ("boss_trophy", 100),
    ],
    "creature_boss_dungeon_undying_king": [
        ("undying_crown", 100), ("bone", 80), ("scroll", 60),
        ("amulet", 40), ("boss_trophy", 100), ("gold_coin", 100),
    ],
    "creature_boss_river_kelpie_queen": [
        ("kelpie_mane", 100), ("river_pearl", 60), ("ancient_silk", 35),
        ("scroll", 25), ("boss_trophy", 100), ("gold_coin", 80),
    ],
    "creature_boss_coast_kraken_arm": [
        ("kraken_ink", 100), ("tentacle_meat", 100), ("pearl_great", 50),
        ("boss_trophy", 100), ("gold_coin", 90),
    ],
    "creature_boss_capital_traitor_general": [
        ("traitor_signet", 100), ("steel_ingot", 60), ("noble_cloak", 50),
        ("crossbow", 30), ("boss_trophy", 100), ("gold_coin", 120),
    ],
    "creature_boss_sky_bound_roc": [
        ("roc_feather", 100), ("roc_talon", 80), ("essence_storm", 30),
        ("boss_trophy", 100), ("gold_coin", 80),
    ],
    # Humanoid-Bosse (Section 4 Captains)
    "creature_grin_goblin_warchief": [
        ("warchief_crown", 80), ("goblin_ear", 100), ("crude_steel_ingot", 60),
        ("iron_sword", 35), ("gold_coin", 60), ("silver_coin", 80),
    ],
    "creature_void_speaker": [
        ("void_essence", 100), ("aberrant_eye", 60), ("dark_grimoire", 50),
        ("scroll", 50), ("gold_coin", 80),
    ],
    "creature_brigand_captain": [
        ("silver_coin", 100), ("iron_sword", 40), ("leather_armor_piece", 50),
        ("captain_banner", 12), ("herb", 20), ("dagger", 15),
    ],
    # Apex-Section-3-Highlights
    "creature_thornmaw": [
        ("thornmaw_seed", 60), ("plant_fiber", 80), ("herb_bundle", 50),
        ("dryad_sap", 30), ("silver_coin", 30),
    ],
    "creature_marsh_naga": [
        ("naga_scale", 80), ("poison_gland", 40), ("scroll", 35),
        ("staff", 18), ("silver_coin", 35), ("gold_coin", 15),
    ],
    "creature_bog_titan_elk": [
        ("titan_antler", 80), ("raw_meat", 100), ("leather", 80),
        ("bone", 60), ("silver_coin", 40), ("gold_coin", 18),
    ],
    "creature_dune_terror_worm": [
        ("worm_chitin", 100), ("acid_gland", 60), ("sand_crystal", 40),
        ("gold_coin", 50), ("silver_coin", 50),
    ],
    "creature_canyon_wyrm": [
        ("wyrm_scale", 100), ("dragon_tooth", 40), ("wing_membrane", 35),
        ("gold_coin", 50), ("silver_coin", 50),
    ],
    "creature_glacier_juggernaut_bear": [
        ("arctic_pelt", 100), ("titan_femur", 50), ("frost_fang", 60),
        ("essence_frost", 25), ("silver_coin", 50),
    ],
    "creature_grove_stag_corrupted": [
        ("corrupted_antler", 80), ("raw_meat", 60), ("leather", 70),
        ("dryad_sap", 25), ("silver_coin", 35),
    ],
    "creature_ridgeback_drake": [
        ("drake_scale", 100), ("acid_gland", 50), ("drake_horn", 40),
        ("crystal", 25), ("gold_coin", 50),
    ],
    "creature_iron_horn_aurochs": [
        ("raw_meat", 100), ("leather", 100), ("iron_horn", 60),
        ("bone", 60), ("silver_coin", 30),
    ],
    # Lore-Carrier (Section 12)
    "creature_silent_pilgrim_white": [
        ("white_pilgrim_token", 100), ("pilgrim_robe", 80),
        ("lore_fragment", 50), ("gold_coin", 80),
    ],
    "creature_clockwork_messenger": [
        ("clockwork_gear", 100), ("tech_print", 80),
        ("messenger_capsule", 60), ("silver_coin", 50),
    ],
    "creature_starfall_traveller": [
        ("starfall_ingot", 100), ("astral_dust", 80),
        ("unique_lore_item", 100), ("gold_coin", 60),
    ],
    "creature_old_god_avatar_fragment": [
        ("old_god_shard", 100), ("void_essence", 100),
        ("unique_lore_item", 100), ("rune_stone", 50),
    ],
    "creature_dream_walker": [
        ("dream_silk", 100), ("sleep_essence", 60),
        ("astral_dust", 40),
    ],
}


def _loot_for_section_tier(section_idx: int, tier: int, slug: str) -> list:
    """Drops für ein Monster: Slug-Override (wenn vorhanden) ELSE
    Section-Pool + Tier-Bonus extend."""
    if slug in _SLUG_LOOT_OVERRIDES:
        return _SLUG_LOOT_OVERRIDES[slug]
    base = list(_SECTION_LOOT.get(section_idx,
                                   [("copper_coin", 50), ("bone", 25)]))
    base.extend(_TIER_BONUS.get(tier, []))
    return base


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
        loot[kid] = _loot_for_section_tier(sec_idx, tier, kid)
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
