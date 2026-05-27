"""Combat-Konstanten und einfache Schaden-Logik.

Stat-System (Welle 15, 2026-05-26e):
    NPC_STATS pro Creature-Kind enthält HP, DMG, Defense, Element-Resistances
    (fire/ice/lightning/necrotic/magic in %), Movement-Speed-Multiplier,
    Aggro-Range, Tier (1=trash, 4=boss). Backwards-Compat: NPC_HP_BY_KIND und
    CREATURE_DAMAGE bleiben als abgeleitete Maps existieren.
"""

# Default-HP pro Creature-Kind
NPC_HP_BY_KIND = {
    "goblin":   30,
    "wolf":     50,
    "skeleton": 40,
    "spider":   25,
    "slime":    35,
    # Welle 3 — neue Creatures
    "rat":      15,
    "bat":      20,
    "zombie":   60,
    "bandit":   45,
    "robber":   55,    # robuster als bandit
    "thief":    30,    # schwächer, fokussiert auf flinke Angriffe
    "boar":     70,
    "bear":     120,
    # Bosse — viel stärker
    "ogre":         200,
    "necromancer":  150,
    "dragon_whelp": 180,
    # Welle 13 — neue Monster (asset-drop 2026-05-26)
    # Kleine Insekten/Imps (10-25 HP)
    "slimelet":     18,
    "fae_mite":     14,
    "crystal_tick": 16,
    "gloom_moth":   20,
    "ember_newt":   22,
    "mushroom_imp": 25,
    "thornling":    22,
    "ember_rat":    18,
    "frost_sprite": 22,
    "fire_imp":     28,
    "crystal_beetle":24,
    "thorn_scarab": 28,
    "shadow_bat":   22,
    # Mittlere Tiere/Geister (40-70 HP)
    "stag":         55,
    "lynx":         50,
    "cougar":       60,
    "wolverine":    65,
    "cobra":        45,
    "dire_wolf":    70,
    "wolf_alpha":   85,
    "gargoyle":     70,
    "treant":       90,
    "bone_crawler": 55,
    # Schwere (80-150 HP)
    "cave_bear":    140,
    "polar_bear":   135,
    "crocodile":    110,
    "stone_golem":  150,
    "crystal_golem":160,
    "giant_spider": 90,
    "harpy":        85,
    "minotaur":     130,
    # Bosse (180-260 HP)
    "basilisk":     200,
    "chimera":      230,
    "griffin":      210,
    "hydra":        260,
    "manticore":    220,
    # Friendly NPCs
    "wanderer": 50,
    "merchant": 40,
    "hermit":   30,
    "bard":     35,
    "scholar":  30,
    "soldier":  70,
    # Welle 21
    "mage":        45,
    "farmer":      40,
    "villager":    40,
    "guard":       80,    # zäh, beschützt Siedlung
    "healer":      45,
    "quest_giver": 50,
    "blacksmith":  65,
    "miner":         55,
    "village_elder": 40,
    "watchman":      75,
    "cat":           8,
    "dog":           15,
    "child":         20,
    # Asset-Drop 2026-05-27b: Nutztiere (friendly, passiv)
    "cow":             80, "bull":          110, "calf":          25,
    "ox":             120, "sheep":          40, "ram":           55,
    "lamb":            18, "sheared_sheep":  35, "pig":           60,
    "piglet":          15, "boar_domestic":  75, "goat":          35,
    "buck_goat":       50, "kid_goat":       15, "horse":         85,
    "draft_horse":    110, "foal":           25, "donkey":        65,
    "mule":            80,
    # Geflügel — leicht
    "chicken_hen":      8, "rooster":        12, "chick":          3,
    "duck":            10, "drake":          12, "duckling":       3,
    "goose":           18, "gander":         22, "gosling":        4,
    # Karawanen-Wagen — leicht zerstörbar aber nicht im Fokus
    "farm_cart_hay":          25, "handcart_empty":         20,
    "horse_cart_single":      30, "market_wagon_covered":   40,
    # — Welle 14 — professional monster asset-drop (2026-05-26b) —
    # Vermin / Larva (15–35 HP)
    "razorback_vermin":      20,
    "spined_abyss_larva":    35,
    # Medium (60–100 HP)
    "reed_walker":           60,
    "redland_scavenger":     65,
    "grave_wraith":          80,
    "serpent_oracle":        90,
    "mossback_warden":       95,
    # Heavy (110–170 HP)
    "urtikus_eye_fiend":    110,
    "mantis_chimera":       120,
    "iron_spider":          130,
    "dendroid_guardian":    150,
    "blood_antler_drake":   170,
    # Bosse (200+ HP)
    "kaiju_thornback":      200,
    "void_eye_brute":       220,
    "frost_rune_boar_prime":240,
    "magma_shell_devourer": 270,
    "rockshell_colossus":   320,
}

# Default-Schaden eines Spielers ohne Waffe (Faust)
PLAYER_BASE_DAMAGE = 4

# Legacy-Konstante (Backwards-Compat). Bevorzugt item_stats.weapon_base_damage nutzen.
WEAPON_DAMAGE = {
    "sword": 10, "axe": 14, "bow": 8, "staff": 7,
    "wand": 6, "greatsword": 22, "spear": 12, "crossbow": 16,
    "throwing_knife": 5, "mace": 13, "scythe": 16, "dagger": 6,
}

# Schaden den Creatures austeilen
CREATURE_DAMAGE = {
    "goblin":   5,
    "wolf":     12,
    "skeleton": 8,
    "spider":   6,
    "slime":    4,
    # Welle 3
    "rat":      3,
    "bat":      4,
    "zombie":   10,
    "bandit":   14,    # bewaffnet
    "robber":   16,    # stärkerer Hieb
    "thief":    9,     # weniger Damage, schnell
    "boar":     11,
    "bear":     20,
    # Bosse — gefährlich
    "ogre":         25,
    "necromancer":  18,
    "dragon_whelp": 30,
    # Welle 13
    "slimelet":     3, "fae_mite": 2, "crystal_tick": 4, "gloom_moth": 3,
    "ember_newt":   5, "mushroom_imp": 6, "thornling": 5, "ember_rat": 4,
    "frost_sprite": 6, "fire_imp": 8, "crystal_beetle": 6, "thorn_scarab": 7,
    "shadow_bat":   5,
    "stag":         8,  "lynx": 11, "cougar": 13, "wolverine": 14,
    "cobra":        12, "dire_wolf": 15, "wolf_alpha": 18, "gargoyle": 14,
    "treant":       16, "bone_crawler": 11,
    "cave_bear":    22, "polar_bear": 21, "crocodile": 18, "stone_golem": 20,
    "crystal_golem":22, "giant_spider": 16, "harpy": 14, "minotaur": 24,
    "basilisk":     28, "chimera": 32, "griffin": 26, "hydra": 35, "manticore": 30,
    # — Welle 14 — professional monster asset-drop (2026-05-26b) —
    "razorback_vermin":       4,
    "spined_abyss_larva":     6,
    "reed_walker":            9,
    "redland_scavenger":     10,
    "grave_wraith":          13,
    "serpent_oracle":        16,
    "mossback_warden":       14,
    "urtikus_eye_fiend":     17,
    "mantis_chimera":        18,
    "iron_spider":           18,
    "dendroid_guardian":     20,
    "blood_antler_drake":    22,
    "kaiju_thornback":       25,
    "void_eye_brute":        26,
    "frost_rune_boar_prime": 28,
    "magma_shell_devourer":  32,
    "rockshell_colossus":    35,
}

CREATURE_KINDS = set(CREATURE_DAMAGE.keys())

PLAYER_MAX_HP = 100
PLAYER_MAX_MANA = 50

# Range in Tiles (Manhattan)
ATTACK_RANGE = 1   # 1 Tile entfernt (orthogonal benachbart oder gleiches Tile)
AGGRO_RANGE  = 6   # Bei dieser Distanz beginnt eine Creature dem Spieler zu folgen


def player_damage(equipped_weapon_kind: str | None) -> int:
    """Legacy: einfacher Schaden ohne Skill/Quality. Bevorzugt
    calc_player_damage() unten benutzen."""
    return PLAYER_BASE_DAMAGE + WEAPON_DAMAGE.get(equipped_weapon_kind or "", 0)


def calc_player_damage(
    weapon_kind: str | None,
    weapon_quality: str = "normal",
    combat_level: int = 0,
    rng_roll: float = 0.5,
    rolled_stats: dict | None = None,
) -> tuple[int, bool]:
    """Vollständige Damage-Berechnung mit Quality + Skill + Crit-Roll.
    Returns (total_damage, was_crit).

    Welle 23: Wenn `rolled_stats` (per-instance) gesetzt ist:
      - base wird pro swing innerhalb (damage_min, damage_max) gerollt
      - crit/crit_mult/speed kommen aus rolled_stats statt aus WEAPON_STATS
    Quality-Multiplier ist bereits in rolled_stats eingeflossen (Roll-Zeit)
    und wird daher hier NICHT nochmal angewendet.

    Legacy-Fallback (kein rolled_stats):
        base       = weapon_base_damage or unarmed 4
        quality_m  = QUALITY_MULT[quality]
        total      = (base + skill_add + base_player) * quality_m * (crit ? crit_mult : 1)
    """
    import item_stats
    import quality as quality_mod
    import random as _r

    skill_add = combat_level // 4

    if rolled_stats and "damage_min" in rolled_stats and "damage_max" in rolled_stats:
        base = item_stats.roll_swing_damage(rolled_stats, fallback_kind=weapon_kind)
        crit_chance = rolled_stats.get("crit", 0.05) + combat_level * 0.005
        crit_mult   = rolled_stats.get("crit_mult", 1.5)
        base_total  = base + skill_add + (PLAYER_BASE_DAMAGE // 2)
        is_crit     = rng_roll < crit_chance
        raw         = base_total * (crit_mult if is_crit else 1.0)
        return int(round(raw)), is_crit

    # Legacy-Pfad für Items ohne rolled_stats (Pre-Welle-23-Inventar)
    base = item_stats.weapon_base_damage(weapon_kind)
    cfg = item_stats.WEAPON_STATS.get(weapon_kind) if weapon_kind else None
    crit_chance = (cfg["crit"] if cfg else 0.05) + combat_level * 0.005
    crit_mult   = (cfg["crit_mult"] if cfg else 1.5)
    quality_m   = quality_mod.QUALITY_MULT.get(weapon_quality, 1.0)
    base_total  = base + skill_add + (PLAYER_BASE_DAMAGE // 2)
    is_crit     = rng_roll < crit_chance
    raw         = base_total * quality_m
    if is_crit:
        raw *= crit_mult
    return int(round(raw)), is_crit


def creature_damage(kind: str) -> int:
    return CREATURE_DAMAGE.get(kind, 5)


def manhattan(ax: int, ay: int, bx: int, by: int) -> int:
    return abs(ax - bx) + abs(ay - by)


# Effekte beim Use eines Consumables / Lebensmittels.
# Hunger-Restoration läuft separat über needs.FOOD_RESTORE.
# HP-Werte koordiniert mit needs.py:
#   - Tränke sind Spezialisten (HP/Mana primär, kaum Sättigung)
#   - Vitaminreich (Pilze, Kohl, Kürbis) → mehr HP
#   - Reine Stärke-Sättigung (Kartoffel, Mais) → moderater HP
#   - Snacks (Beeren) → kleiner HP
USE_EFFECTS = {
    # Tränke
    "health_potion": {"hp": 30},
    "mana_potion":   {"mana": 30},
    "herb":          {"hp": 5},
    # Beeren — alle gleich
    "strawberry":    {"hp": 2},
    "blueberry":     {"hp": 2},
    "blackberry":    {"hp": 2},
    "raspberry":     {"hp": 2},
    "berries":       {"hp": 2},
    # Obst
    "apple":         {"hp": 3},
    "pear":          {"hp": 3},
    "plum":          {"hp": 2},
    "cherry":        {"hp": 2},
    # Pilze
    "mushroom_food": {"hp": 3},
    # Gemüse — größer / vitaminreicher = mehr HP
    "carrot":        {"hp": 2},
    "tomato":        {"hp": 2},
    "potato":        {"hp": 2},
    "cabbage":       {"hp": 3},
    "corn":          {"hp": 3},
    "pumpkin":       {"hp": 5},
    # Welle 16 — neue Pflanzen
    "garlic":        {"hp": 2},   # mild antibakteriell-vibe
    "grapes_blue":   {"hp": 3},
    "grapes_green":  {"hp": 3},
    # cucumber + onion bleiben pure Sättigung (kein HP)
    # Fleisch / Fisch
    "fish":          {"hp": 4},
    # raw_meat: kein HP (roh, sättigt aber heilt nicht)
    # Verarbeitet
    "bread":         {"hp": 4},
    "food_ration":   {"hp": 6},
    "cooked_meat":   {"hp": 8},
}

# Spells aus Magic-Items
SPELLS = {
    "spell_book": {
        "name": "Feuerball", "icon": "🔥",
        "damage": 25, "range": 7, "aoe_radius": 1,
        "mana": 20, "consume": False,
        "learnable": True,
    },
    "scroll": {
        "name": "Magisches Geschoss", "icon": "✨",
        "damage": 30, "range": 8, "aoe_radius": 0,
        "mana": 12, "consume": True,
        "learnable": True,
    },
    "rune_stone": {
        "name": "Heilrune", "icon": "💎",
        "damage": 0, "heal_self": 30, "range": 0, "aoe_radius": 0,
        "mana": 15, "consume": False,
        "self_effect": {"effect": "blessed", "magnitude": 4, "duration": 20},
        "learnable": True,
    },
}

# Heal-Strukturen (Klick → HP-Boost)
STRUCTURE_HEAL = {
    "bed":  100,   # voll heilen
    "well": 20,
}
STRUCTURE_HEAL_COOLDOWN = 30  # Sekunden pro Spieler pro Struktur

# Traps (Damage beim Drüberlaufen)
TRAP_DAMAGE = {
    "spike_trap":  10,
    "poison_trap": 15,
}


# ─── Monster-Stat-System (Welle 15) ──────────────────────────────────────────
# Pro Creature-Kind: zusätzliche Stats jenseits von HP+DMG.
#   defense       : physical damage reduction (formel: dr = def/(def+100))
#   *_resist      : prozentuale Reduktion für Element/Magic-Schaden (0..100)
#   speed         : movement-speed-multiplier (1.0 = normal, 1.5 = 50% schneller)
#   aggro_range   : Tiles in denen Creature einen Player verfolgt (default 6)
#   tier          : 1=trash, 2=normal, 3=elite, 4=boss (für Loot-Skalierung)
#
# Werte sind sparsam: nicht jedes Monster braucht alle Resists. Defaults siehe
# _DEFAULT_NPC_STATS. Nur thematisch passende Kinds werden überschrieben.

_DEFAULT_NPC_STATS = {
    "defense": 0, "fire_resist": 0, "ice_resist": 0, "lightning_resist": 0,
    "necrotic_resist": 0, "magic_resist": 0, "speed": 1.0, "aggro_range": 6,
    "tier": 2,
}

# Per-Kind Overrides — nur Werte die vom Default abweichen
_NPC_STAT_OVERRIDES = {
    # ─── Tier 1 — Vermin/Imps (trash) ───────────────────────────────────────
    "rat":             {"defense": 0, "speed": 1.4, "tier": 1, "aggro_range": 4},
    "bat":             {"defense": 0, "speed": 1.6, "tier": 1, "aggro_range": 5},
    "spider":          {"defense": 1, "speed": 1.1, "tier": 1, "necrotic_resist": 20},
    "slime":           {"defense": 2, "speed": 0.6, "tier": 1, "magic_resist": 30, "ice_resist": 20},
    "goblin":          {"defense": 2, "speed": 1.0, "tier": 1},
    "slimelet":        {"defense": 1, "speed": 0.5, "tier": 1, "magic_resist": 25, "ice_resist": 20},
    "fae_mite":        {"defense": 0, "speed": 1.7, "tier": 1, "magic_resist": 30},
    "crystal_tick":    {"defense": 4, "speed": 0.9, "tier": 1, "ice_resist": 40, "magic_resist": 20},
    "gloom_moth":      {"defense": 0, "speed": 1.5, "tier": 1, "necrotic_resist": 25},
    "ember_newt":      {"defense": 2, "speed": 1.0, "tier": 1, "fire_resist": 60, "damage_type": "fire"},
    "mushroom_imp":    {"defense": 1, "speed": 0.9, "tier": 1, "necrotic_resist": 30, "magic_resist": 15},
    "thornling":       {"defense": 3, "speed": 0.8, "tier": 1, "magic_resist": 15},
    "ember_rat":       {"defense": 1, "speed": 1.5, "tier": 1, "fire_resist": 50, "damage_type": "fire"},
    "frost_sprite":    {"defense": 1, "speed": 1.2, "tier": 1, "ice_resist": 70, "magic_resist": 25, "damage_type": "ice"},
    "fire_imp":        {"defense": 2, "speed": 1.2, "tier": 1, "fire_resist": 80, "magic_resist": 20, "damage_type": "fire"},
    "crystal_beetle":  {"defense": 6, "speed": 0.8, "tier": 1, "ice_resist": 30, "lightning_resist": 30},
    "thorn_scarab":    {"defense": 4, "speed": 0.9, "tier": 1, "necrotic_resist": 20},
    "shadow_bat":      {"defense": 1, "speed": 1.5, "tier": 1, "necrotic_resist": 50, "ice_resist": 15, "damage_type": "necrotic"},
    "razorback_vermin":{"defense": 2, "speed": 1.4, "tier": 1, "aggro_range": 5},
    "spined_abyss_larva":{"defense": 3, "speed": 0.7, "tier": 1, "necrotic_resist": 40, "magic_resist": 20},

    # ─── Tier 2 — Standard-Mobs ─────────────────────────────────────────────
    "skeleton":        {"defense": 5, "speed": 0.8, "tier": 2, "necrotic_resist": 70, "ice_resist": 30},
    "zombie":          {"defense": 4, "speed": 0.5, "tier": 2, "necrotic_resist": 60},
    "bandit":          {"defense": 6, "speed": 1.0, "tier": 2, "aggro_range": 8},
    "robber":          {"defense": 8, "speed": 0.9, "tier": 2, "aggro_range": 7},
    "thief":           {"defense": 3, "speed": 1.4, "tier": 1, "aggro_range": 9},
    "wolf":            {"defense": 3, "speed": 1.3, "tier": 2, "aggro_range": 7},
    "boar":            {"defense": 5, "speed": 1.1, "tier": 2, "aggro_range": 5},
    "stag":            {"defense": 4, "speed": 1.4, "tier": 2, "aggro_range": 3},
    "lynx":            {"defense": 3, "speed": 1.5, "tier": 2, "aggro_range": 7},
    "cougar":          {"defense": 5, "speed": 1.4, "tier": 2, "aggro_range": 8},
    "wolverine":       {"defense": 7, "speed": 1.2, "tier": 2, "aggro_range": 8},
    "cobra":           {"defense": 3, "speed": 1.1, "tier": 2, "necrotic_resist": 30},
    "dire_wolf":       {"defense": 6, "speed": 1.4, "tier": 2, "aggro_range": 8},
    "wolf_alpha":      {"defense": 8, "speed": 1.3, "tier": 2, "aggro_range": 9},
    "gargoyle":        {"defense": 12, "speed": 0.6, "tier": 2, "magic_resist": 30, "lightning_resist": 20},
    "treant":          {"defense": 8, "speed": 0.4, "tier": 2, "fire_resist": -50, "magic_resist": 20},
    "bone_crawler":    {"defense": 6, "speed": 1.0, "tier": 2, "necrotic_resist": 50},
    "reed_walker":     {"defense": 5, "speed": 1.1, "tier": 2, "fire_resist": -30, "ice_resist": 15},
    "redland_scavenger":{"defense": 7, "speed": 1.2, "tier": 2, "fire_resist": 40},
    "grave_wraith":    {"defense": 4, "speed": 1.0, "tier": 2, "necrotic_resist": 80, "magic_resist": 30, "fire_resist": -30, "damage_type": "necrotic"},

    # ─── Tier 3 — Schwere/Elite ─────────────────────────────────────────────
    "bear":            {"defense": 9, "speed": 0.9, "tier": 3, "aggro_range": 6},
    "cave_bear":       {"defense": 12, "speed": 0.9, "tier": 3, "aggro_range": 7},
    "polar_bear":      {"defense": 10, "speed": 0.9, "tier": 3, "ice_resist": 60, "fire_resist": -30},
    "crocodile":       {"defense": 14, "speed": 0.7, "tier": 3, "fire_resist": -20},
    "stone_golem":     {"defense": 30, "speed": 0.5, "tier": 3, "fire_resist": 30, "lightning_resist": 50, "magic_resist": 25},
    "crystal_golem":   {"defense": 25, "speed": 0.5, "tier": 3, "ice_resist": 60, "lightning_resist": 50, "magic_resist": 30},
    "giant_spider":    {"defense": 8, "speed": 1.1, "tier": 3, "necrotic_resist": 40},
    "harpy":           {"defense": 6, "speed": 1.4, "tier": 3, "lightning_resist": 30},
    "minotaur":        {"defense": 18, "speed": 1.0, "tier": 3, "aggro_range": 8},
    "serpent_oracle":  {"defense": 8, "speed": 0.8, "tier": 3, "magic_resist": 60, "necrotic_resist": 30, "damage_type": "magic"},
    "mossback_warden": {"defense": 14, "speed": 0.7, "tier": 3, "fire_resist": -30, "ice_resist": 30},
    "urtikus_eye_fiend":{"defense": 10, "speed": 0.8, "tier": 3, "magic_resist": 50, "necrotic_resist": 40, "damage_type": "magic"},
    "mantis_chimera":  {"defense": 12, "speed": 1.2, "tier": 3, "aggro_range": 8},
    "iron_spider":     {"defense": 22, "speed": 0.9, "tier": 3, "fire_resist": 30, "lightning_resist": -30, "magic_resist": 20},

    # ─── Tier 4 — Bosse ─────────────────────────────────────────────────────
    "ogre":            {"defense": 20, "speed": 0.8, "tier": 4, "aggro_range": 9},
    "necromancer":     {"defense": 8,  "speed": 1.0, "tier": 4, "necrotic_resist": 70, "magic_resist": 60, "aggro_range": 10, "damage_type": "necrotic"},
    "dragon_whelp":    {"defense": 22, "speed": 1.1, "tier": 4, "fire_resist": 75, "magic_resist": 25, "aggro_range": 10, "damage_type": "fire"},
    "basilisk":        {"defense": 20, "speed": 0.9, "tier": 4, "necrotic_resist": 50, "magic_resist": 30},
    "chimera":         {"defense": 25, "speed": 1.0, "tier": 4, "fire_resist": 50, "lightning_resist": 30, "aggro_range": 9},
    "griffin":         {"defense": 18, "speed": 1.3, "tier": 4, "lightning_resist": 40, "aggro_range": 9},
    "hydra":           {"defense": 30, "speed": 0.6, "tier": 4, "ice_resist": 40, "fire_resist": -40, "magic_resist": 30},
    "manticore":       {"defense": 22, "speed": 1.1, "tier": 4, "magic_resist": 25, "aggro_range": 9},
    "dendroid_guardian":{"defense": 28, "speed": 0.4, "tier": 4, "fire_resist": -50, "magic_resist": 25, "lightning_resist": 30},
    "blood_antler_drake":{"defense": 24, "speed": 1.1, "tier": 4, "necrotic_resist": 40, "magic_resist": 25, "aggro_range": 9},
    "kaiju_thornback": {"defense": 35, "speed": 0.8, "tier": 4, "fire_resist": 30, "aggro_range": 9},
    "void_eye_brute":  {"defense": 28, "speed": 0.7, "tier": 4, "magic_resist": 65, "necrotic_resist": 50, "aggro_range": 10, "damage_type": "necrotic"},
    "frost_rune_boar_prime":{"defense": 30, "speed": 1.0, "tier": 4, "ice_resist": 80, "fire_resist": -40, "magic_resist": 30, "aggro_range": 9, "damage_type": "ice"},
    "magma_shell_devourer":{"defense": 38, "speed": 0.6, "tier": 4, "fire_resist": 90, "ice_resist": -40, "lightning_resist": 30, "aggro_range": 10, "damage_type": "fire"},
    "rockshell_colossus":{"defense": 50, "speed": 0.4, "tier": 4, "fire_resist": 20, "lightning_resist": 60, "magic_resist": 35, "aggro_range": 8},
}


def creature_stats(kind: str) -> dict:
    """Vollständiger Stat-Block für ein Monster-Kind, gemerged mit Defaults.

    Returns ein neues dict — der Caller darf ihn modifizieren ohne Defaults
    zu beeinflussen.
    """
    out = dict(_DEFAULT_NPC_STATS)
    out["hp"]  = NPC_HP_BY_KIND.get(kind, 30)
    out["dmg"] = CREATURE_DAMAGE.get(kind, 5)
    out.update(_NPC_STAT_OVERRIDES.get(kind, {}))
    return out


def damage_reduction(total_defense: int) -> float:
    """Diminishing-returns Defense: 100 Def = 50% DR, 200 Def = 66.7% DR."""
    if total_defense <= 0:
        return 0.0
    return total_defense / (total_defense + 100.0)


def apply_creature_resists(kind: str, raw_damage: int,
                           dmg_type: str = "physical",
                           armor_pen: float = 0.0) -> int:
    """Wendet Defense/Resists eines Monsters auf einen Roh-Schaden an.

    dmg_type ∈ {physical, fire, ice, lightning, necrotic, magic}.
    armor_pen ∈ [0..1] ignoriert anteilig die physische Defense.
    Mindestschaden ist immer 1 (auch wenn Resists das auf <1 drücken würden).
    """
    if raw_damage <= 0:
        return 0
    stats = creature_stats(kind)
    if dmg_type == "physical":
        defense = max(0, int(stats["defense"] * (1 - armor_pen)))
        dr = damage_reduction(defense)
        return max(1, int(round(raw_damage * (1 - dr))))
    resist_key = {
        "fire": "fire_resist", "ice": "ice_resist",
        "lightning": "lightning_resist", "necrotic": "necrotic_resist",
        "magic": "magic_resist",
    }.get(dmg_type)
    if resist_key is None:
        return raw_damage   # unbekannter type → ungehindert
    resist = stats.get(resist_key, 0)
    # Resist kann negativ sein (Vulnerability) → mehr Schaden
    factor = max(0.0, (100 - resist) / 100.0)
    return max(1, int(round(raw_damage * factor)))


def weapon_damage_type(weapon_kind: str | None) -> str:
    """Default damage type per Waffen-Class. Affixes können später typed damage
    on top hinzufügen."""
    if weapon_kind is None:
        return "physical"
    try:
        import item_stats
        cls = item_stats.weapon_class(weapon_kind)
    except Exception:
        return "physical"
    return "magic" if cls == "magic" else "physical"


# ═══════════════════════════════════════════════════════════════════════════
# ESO-Style Player-Scaling (Welle 23, 2026-05-27)
#
# Normale Mobs (Tier 1-3) skalieren mit Player-Level. Bosse (Tier 4) skalieren
# auch, haben aber zusätzlich Boss-Bonus + Floor (siehe power_budget).
#
# Die existierenden NPC_HP_BY_KIND/CREATURE_DAMAGE-Werte werden zu FLAVOR-
# Gewichten innerhalb des Tiers umgedeutet:
#     final_hp = tier_baseline(tier, lvl) × (NPC_HP_BY_KIND[kind] / tier_avg_hp)
# Ein wolf (50 HP, Tier 2, Tier-Avg ~50) bleibt also = baseline. wolf_alpha
# (85 HP, Tier 2) = baseline × 1.7. fae_mite (14 HP, Tier 1) = T1-baseline × 0.6.
# ═══════════════════════════════════════════════════════════════════════════

def _compute_tier_averages():
    """Einmal beim Import: durchschnittliches base_hp und base_dmg pro Tier."""
    hp_by_tier:  dict[int, list[int]] = {}
    dmg_by_tier: dict[int, list[int]] = {}
    # Iteriere über alle Kinds mit Stat-Daten — friendly NPCs ignorieren
    for kind in CREATURE_KINDS:
        tier = _NPC_STAT_OVERRIDES.get(kind, {}).get("tier", 2)
        if kind in NPC_HP_BY_KIND:
            hp_by_tier.setdefault(tier, []).append(NPC_HP_BY_KIND[kind])
        if kind in CREATURE_DAMAGE:
            dmg_by_tier.setdefault(tier, []).append(CREATURE_DAMAGE[kind])
    avg_hp  = {t: sum(v) / len(v) for t, v in hp_by_tier.items()}
    avg_dmg = {t: sum(v) / len(v) for t, v in dmg_by_tier.items()}
    return avg_hp, avg_dmg


_TIER_AVG_HP, _TIER_AVG_DMG = _compute_tier_averages()


def flavor_mult_hp(kind: str) -> float:
    """Wie zäh ist dieser Mob im Vergleich zum Tier-Durchschnitt?"""
    tier = _NPC_STAT_OVERRIDES.get(kind, {}).get("tier", 2)
    base = NPC_HP_BY_KIND.get(kind, 35)
    avg = _TIER_AVG_HP.get(tier) or 35
    # Clamp 0.5-1.6 — zu extreme Werte ergeben kein gutes Game-Feel
    return max(0.5, min(1.6, base / avg))


def flavor_mult_dmg(kind: str) -> float:
    """Wie hart haut dieser Mob im Vergleich zum Tier-Durchschnitt?"""
    tier = _NPC_STAT_OVERRIDES.get(kind, {}).get("tier", 2)
    base = CREATURE_DAMAGE.get(kind, 8)
    avg = _TIER_AVG_DMG.get(tier) or 8
    return max(0.5, min(1.5, base / avg))


def kalibrated_npc_hp(kind: str, player_power, group_mult: float = 1.0,
                       region_mod: float = 1.0) -> int:
    """ESO-Style scaling: HP folgt Power-Score + Tier + per-kind Flavor +
    Group-Mult + Region-Modifier.

    Tier 1-3 sind „adaptive" (entspricht Spieler ± Flavor). Tier 4 (Boss) hat
    festen Floor + zusätzlichen Per-Score-Bonus, damit er immer fies bleibt.
    """
    import power_budget
    tier = _NPC_STAT_OVERRIDES.get(kind, {}).get("tier", 2)
    base = power_budget.tier_baseline_hp(tier, player_power)
    val = base * flavor_mult_hp(kind) * group_mult * region_mod
    return max(1, int(round(val)))


def kalibrated_creature_damage(kind: str, player_power, group_mult: float = 1.0,
                                region_mod: float = 1.0) -> int:
    """ESO-Style scaling: DMG folgt Power-Score + Tier + per-kind Flavor.

    Welle 24: Blutmond-Effekt — wenn blood_moon aktiv, ×1.3 Damage."""
    import power_budget
    tier = _NPC_STAT_OVERRIDES.get(kind, {}).get("tier", 2)
    base = power_budget.tier_baseline_dmg(tier, player_power)
    val = base * flavor_mult_dmg(kind) * group_mult * region_mod
    # Disaster-Buff (Blutmond)
    try:
        import disaster_state
        if disaster_state.is_active("blood_moon"):
            val *= 1.3
    except Exception:
        pass
    return max(1, int(round(val)))
