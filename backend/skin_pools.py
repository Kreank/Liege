"""Cosmetic-Skin-Pools für Equipment.

Bei jedem Spawn eines Equipment-Items wird zufällig ein Skin aus dem
passenden Pool gewählt (sofern vorhanden) und in items.cosmetic_skin
gespeichert. Das Frontend rendert den Skin statt des Default-Sprites.

Pool-Auswahl per (kind, quality). Wenn kein Pool für die Kombination
existiert → None → Default-Sprite via ITEM_KINDS.

Pro Kind ist eindeutig festgelegt aus welchem Asset-Ordner die Slugs
kommen — siehe SKIN_DIR_BY_KIND. Das Frontend nutzt diese Map zum
Auflösen des vollen Asset-Pfads.
"""
import random

# ───────────────────────────────────────────────────────────────────────
# Pool-Quellen pro Kind (relative Asset-Pfade, ohne /assets/-Prefix)
# ───────────────────────────────────────────────────────────────────────
SKIN_DIR_BY_KIND: dict[str, str] = {
    "sword":      "equipment/weapons/professional/from_neu_pro",
    "greatsword": "equipment/weapons/professional/from_neu_pro",
    "staff":      "equipment/weapons/professional/inspired_arcane_2026_05_27",
    "wand":       "equipment/weapons/professional/inspired_arcane_2026_05_27",
    "helmet":     "equipment/armor/professional/reference_based",
    "chestplate": "equipment/armor/professional/reference_based",
    "gloves":     "equipment/armor/professional/reference_based",
    "boots":      "equipment/armor/professional/reference_based",
    "shield":     "equipment/armor/professional/reference_based",
}

# ───────────────────────────────────────────────────────────────────────
# WEAPONS
# ───────────────────────────────────────────────────────────────────────

# 10 stylized blades (Arthur Malagon) — werden auf 1H-Schwerter verteilt.
_STYLIZED_BLADES = [
    "stylized_blades_arthur_malagon_01",
    "stylized_blades_arthur_malagon_02",
    "stylized_blades_arthur_malagon_03",
    "stylized_blades_arthur_malagon_04",
    "stylized_blades_arthur_malagon_05",
    "stylized_blades_arthur_malagon_06",
    "stylized_blades_arthur_malagon_07",
    "stylized_blades_arthur_malagon_08",
    "stylized_blades_arthur_malagon_09",
    "stylized_blades_arthur_malagon_10",
]

# 20 swordtember Final-Five (Arthur Malagon) — werden auf 2H-Greatswords verteilt.
_SWORDTEMBER = [
    "swordtember_final_five_arthur_malagon_01",
    "swordtember_final_five_arthur_malagon_03",
    "swordtember_final_five_arthur_malagon_09",
    "swordtember_final_five_arthur_malagon_10",
    "swordtember_final_five_arthur_malagon_15",
    "swordtember_final_five_arthur_malagon_16",
    "swordtember_final_five_arthur_malagon_17",
    "swordtember_final_five_arthur_malagon_18",
    "swordtember_final_five_arthur_malagon_19",
    "swordtember_final_five_arthur_malagon_20",
    "swordtember_final_five_arthur_malagon_21",
    "swordtember_final_five_arthur_malagon_22",
    "swordtember_final_five_arthur_malagon_23",
    "swordtember_final_five_arthur_malagon_24",
    "swordtember_final_five_arthur_malagon_25",
    "swordtember_final_five_arthur_malagon_26",
    "swordtember_final_five_arthur_malagon_27",
    "swordtember_final_five_arthur_malagon_28",
    "swordtember_final_five_arthur_malagon_29",
    "swordtember_final_five_arthur_malagon_30",
]

# Arcane Staff-Pool (9 Stück aus inspired_arcane v1) — magisch geprägte Stäbe.
_ARCANE_STAVES = [
    "frost_crystal_staff",
    "sun_reliquary_staff",
    "living_thorn_staff",
    "void_smoke_war_staff",
    "turquoise_rune_staff",
    "bone_eye_necromancer_staff",
    "violet_orb_focus_staff",
    "antler_blossom_witch_staff",
    "blue_arcane_axe_staff",
]

# Arcane Wand-Pool (6 Stück aus inspired_arcane v1) — Zauberstäbe + Szepter.
_ARCANE_WANDS = [
    "pale_moon_wand",
    "brass_oracle_scepter",
    "amethyst_root_wand",
    "twisted_black_iron_wand",
    "green_seedling_wand",
    "ember_priest_rod",
]

# ───────────────────────────────────────────────────────────────────────
# ARMOR (reference_based_professional_armor — slot + rarity tagged)
# ───────────────────────────────────────────────────────────────────────

_ARMOR_HELMET = [
    "crested_hoplite_helm", "black_knight_helm",
    "winged_crusader_helm", "winged_knight_helm", "crowned_steel_helm",
    "templar_visor_helm", "plague_doctor_helm", "antlered_dark_helm",
]
_ARMOR_CHESTPLATE = [
    "grey_landsknecht_armor", "black_tactical_armor",
    "green_hooded_mantle", "wandering_knight_armor",
    "mercenary_plate_cuirass", "linothorax_cuirass",
    "spiked_war_cuirass", "samurai_war_armor",
]
_ARMOR_GLOVES = [
    "black_leather_glove",
    "thief_buckled_gloves", "heavy_iron_gauntlet",
    "stone_guard_gauntlets", "fur_cuffed_brawler_gloves", "black_thievery_gloves",
    "noble_gilded_gloves", "void_claw_gauntlets",
]
_ARMOR_BOOTS = [
    "wrapped_ranger_boots", "dwarven_field_boots",
    "black_iron_greaves", "runeplate_greaves", "middle_earth_plate_boots",
    "ember_wolf_greaves",
]
_ARMOR_SHIELD = [
    "ornate_guard_shield",
]

# ───────────────────────────────────────────────────────────────────────
# POOL-LOOKUP
# ───────────────────────────────────────────────────────────────────────

SKIN_POOLS: dict[tuple[str, str], list[str]] = {
    # 1H Schwerter
    ("sword",      "fine"):       _STYLIZED_BLADES,
    ("sword",      "masterwork"): _STYLIZED_BLADES,
    ("sword",      "legendary"):  _STYLIZED_BLADES,
    # 2H Greatswords
    ("greatsword", "fine"):       _SWORDTEMBER,
    ("greatsword", "masterwork"): _SWORDTEMBER,
    ("greatsword", "legendary"):  _SWORDTEMBER,
    # Stäbe + Wands
    ("staff",      "fine"):       _ARCANE_STAVES,
    ("staff",      "masterwork"): _ARCANE_STAVES,
    ("staff",      "legendary"):  _ARCANE_STAVES,
    ("wand",       "fine"):       _ARCANE_WANDS,
    ("wand",       "masterwork"): _ARCANE_WANDS,
    ("wand",       "legendary"):  _ARCANE_WANDS,
    # Rüstung: pro Slot kompletter Pool ab 'fine'
    ("helmet",     "fine"):       _ARMOR_HELMET,
    ("helmet",     "masterwork"): _ARMOR_HELMET,
    ("helmet",     "legendary"):  _ARMOR_HELMET,
    ("chestplate", "fine"):       _ARMOR_CHESTPLATE,
    ("chestplate", "masterwork"): _ARMOR_CHESTPLATE,
    ("chestplate", "legendary"):  _ARMOR_CHESTPLATE,
    ("gloves",     "fine"):       _ARMOR_GLOVES,
    ("gloves",     "masterwork"): _ARMOR_GLOVES,
    ("gloves",     "legendary"):  _ARMOR_GLOVES,
    ("boots",      "fine"):       _ARMOR_BOOTS,
    ("boots",      "masterwork"): _ARMOR_BOOTS,
    ("boots",      "legendary"):  _ARMOR_BOOTS,
    ("shield",     "fine"):       _ARMOR_SHIELD,
    ("shield",     "masterwork"): _ARMOR_SHIELD,
    ("shield",     "legendary"):  _ARMOR_SHIELD,
}


def roll_skin(kind: str, quality: str) -> str | None:
    """Wählt zufällig einen Cosmetic-Skin-Slug für (kind, quality).
    Returns None wenn kein Pool für die Kombination existiert."""
    pool = SKIN_POOLS.get((kind, quality))
    if not pool:
        return None
    return random.choice(pool)


def all_skin_slugs() -> set[str]:
    """Alle in irgendeinem Pool vorkommenden Slugs (für Manifest/Preload)."""
    out: set[str] = set()
    for slugs in SKIN_POOLS.values():
        out.update(slugs)
    return out
