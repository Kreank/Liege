"""Cosmetic-Skin-Pools für Equipment.

Bei jedem Spawn eines Equipment-Items wird zufällig ein Skin aus dem
passenden Pool gewählt (sofern vorhanden) und in items.cosmetic_skin
gespeichert. Das Frontend rendert den Skin statt des Default-Sprites.

Pool-Auswahl per (kind, quality). Wenn kein Pool für die Kombination
existiert → None → Default-Sprite via PRO_WEAPON_MAP.

Quelle der Sprites:
  assets/equipment/weapons/professional/from_neu_pro/icons_128/*.png
"""
import random

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

# Map: (kind, quality) → Pool. Quality kann '*' sein als Fallback für alle.
# 1H Schwerter: stylized_blades-Pool ab Quality 'fine' aufwärts (common =
# default-Skin, damit nicht jeder Loot-Drop spektakulär aussieht).
SKIN_POOLS: dict[tuple[str, str], list[str]] = {
    ("sword",      "fine"):       _STYLIZED_BLADES,
    ("sword",      "masterwork"): _STYLIZED_BLADES,
    ("sword",      "legendary"):  _STYLIZED_BLADES,
    # 2H Greatswords: swordtember-Pool ab Quality 'fine'
    ("greatsword", "fine"):       _SWORDTEMBER,
    ("greatsword", "masterwork"): _SWORDTEMBER,
    ("greatsword", "legendary"):  _SWORDTEMBER,
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
