"""Combat-Konstanten und einfache Schaden-Logik."""

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
    "boar":     70,
    "bear":     120,
    # Bosse — viel stärker
    "ogre":         200,
    "necromancer":  150,
    "dragon_whelp": 180,
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
    "boar":     11,
    "bear":     20,
    # Bosse — gefährlich
    "ogre":         25,
    "necromancer":  18,
    "dragon_whelp": 30,
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
) -> tuple[int, bool]:
    """Vollständige Damage-Berechnung mit Quality + Skill + Crit-Roll.
    Returns (total_damage, was_crit).

    Formel:
        base       = weapon_base_damage or unarmed 4
        skill_add  = combat_level // 4   (RimWorld-style)
        quality_m  = QUALITY_MULT[quality]
        crit?      = rng_roll < (base_crit + combat_level * 0.005)
        total      = (base + skill_add + base_player) * quality_m * (crit ? crit_mult : 1)
    """
    import item_stats
    import quality as quality_mod

    base = item_stats.weapon_base_damage(weapon_kind)
    cfg = item_stats.WEAPON_STATS.get(weapon_kind) if weapon_kind else None
    crit_chance = (cfg["crit"] if cfg else 0.05) + combat_level * 0.005
    crit_mult   = (cfg["crit_mult"] if cfg else 1.5)
    quality_m   = quality_mod.QUALITY_MULT.get(weapon_quality, 1.0)
    skill_add   = combat_level // 4
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


# Effekte beim Use eines Consumables
USE_EFFECTS = {
    "health_potion": {"hp": 30},
    "mana_potion":   {"mana": 30},
    "herb":          {"hp": 5},
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
