"""Dungeon-Encounter — MVP-Variante.

Klick auf stairs_down → Spieler erkundet kurz einen Dungeon und kommt
mit Beute zurück. Risiko: Trap-Schaden. Cooldown verhindert Spam.

Spätere Welle: echtes begehbares Dungeon mit eigener Map."""

import random

# Encounter-Loot: Mischung aus seltenen Resources, Equipment und Magic
ENCOUNTER_LOOT_TABLE = [
    ("bone", 30), ("iron_ore", 25), ("silver_ore", 20), ("gold_ore", 15),
    ("crystal", 12), ("mythril_ore", 5), ("steel_ingot", 8),
    ("leather", 25), ("cloth", 20), ("herb", 30),
    ("health_potion", 15), ("mana_potion", 12),
    ("sword", 3), ("axe", 3), ("bow", 3), ("staff", 3),
    ("helmet", 3), ("chestplate", 2), ("shield", 3), ("boots", 3),
    ("ring", 2), ("amulet", 2),
    ("scroll", 5), ("rune_stone", 2), ("spell_book", 1),
]

ENCOUNTER_COOLDOWN_SECONDS = 300  # 5 Minuten pro Spieler
ENCOUNTER_MIN_DROPS = 3
ENCOUNTER_MAX_DROPS = 5
ENCOUNTER_DAMAGE_CHANCE = 0.7    # 70% Risiko Schaden
ENCOUNTER_DAMAGE_MIN = 10
ENCOUNTER_DAMAGE_MAX = 30


def roll_encounter(theme: str | None = None) -> dict:
    """Returnt das Resultat eines Dungeon-Encounters.

    theme: wenn gesetzt (Welle 29), nutzt themen-spezifische Loot-Pools.
    """
    n_drops = random.randint(ENCOUNTER_MIN_DROPS, ENCOUNTER_MAX_DROPS)
    if theme is not None:
        import dungeon_themes
        drops = []
        for _ in range(n_drops):
            # 70% normal loot, 30% rare loot
            if random.random() < 0.3:
                drops.append(dungeon_themes.random_loot_for_theme(theme, rare=True))
            else:
                drops.append(dungeon_themes.random_loot_for_theme(theme, rare=False))
    else:
        kinds = [k for k, _ in ENCOUNTER_LOOT_TABLE]
        weights = [w for _, w in ENCOUNTER_LOOT_TABLE]
        drops = random.choices(kinds, weights=weights, k=n_drops)

    damage = 0
    if random.random() < ENCOUNTER_DAMAGE_CHANCE:
        damage = random.randint(ENCOUNTER_DAMAGE_MIN, ENCOUNTER_DAMAGE_MAX)

    return {"drops": drops, "damage": damage, "theme": theme}


def encounter_story(drops: list[str], damage: int,
                    theme: str | None = None) -> str:
    """Kurzer atmosphärischer Text für den Toast."""
    theme_intro = "🏚️"
    if theme:
        try:
            import dungeon_themes
            t = dungeon_themes.THEMES.get(theme)
            if t: theme_intro = f"🏚️ {t['label']}:"
        except Exception:
            pass
    if damage > 0:
        damage_text = f" Eine Falle erwischt dich (-{damage} HP)."
    else:
        damage_text = " Du kommst unversehrt zurück."
    n = len(drops)
    return f"{theme_intro} Du steigst hinab und kehrst mit {n} Gegenständen zurück.{damage_text}"


# ─── Welle 34c: WS-Side Dungeon-Helpers (extrahiert aus main.py) ─────────────

async def active_dungeon_markers() -> list[dict]:
    """Aktive Dungeon-Eingänge (für Minimap-Ortung). Client blendet sie nur im
    Spür-Radius ein, daher reicht die volle Liste (Cap ~28)."""
    import db
    rows = await db.pool().fetch(
        "SELECT tier, entrance_x, entrance_y FROM dungeons "
        "WHERE expires_at > NOW() AND entrance_x IS NOT NULL"
    )
    return [{"x": r["entrance_x"], "y": r["entrance_y"], "tier": r["tier"]}
            for r in rows]


async def dungeon_floor_payload(npcs, dungeon_id: int, floor_idx: int) -> dict:
    """Zusatz-Daten für dungeon_enter/floor_change: Theme-Tint, sichtbare
    Features (Kisten/Decor/ausgelöste Fallen) und die NPCs dieser Floor."""
    import dungeon_themes
    import dungeon_instance
    dungeon = await dungeon_instance.get_dungeon(dungeon_id)
    theme = dungeon["theme"] if dungeon else "cave"
    td = dungeon_themes.THEMES.get(theme, {})
    world_id = f"dungeon:{dungeon_id}:{floor_idx}"
    return {
        "theme": theme,
        "theme_data": {
            "label":         td.get("label"),
            "wall_tint":     td.get("wall_tint"),
            "floor_tint":    td.get("floor_tint"),
            "ambient_color": td.get("ambient_color"),
            "ambient":       td.get("ambient"),
        },
        "features": await dungeon_instance.visible_features(dungeon_id, floor_idx),
        "npcs":     dungeon_instance.npcs_in_world(npcs, world_id),
    }
