"""Player-Attribute-System (derived stats).

11 Attribute (DE-Namen) werden aus Skills + Equipment + Talenten abgeleitet:

    Stärke       — primär combat, woodcutting, mining
    Ausdauer     — primär stamina + construction
    Energie      — primär max_mana + magic-Skill
    Intelligenz  — primär magic, research-Gates
    Weisheit     — primär medical, social → bessere LLM-Dialog-Reaktion
    Ausweichen   — boots + dexterity-Talente
    Geschick     — dagger/throwing_knife + finesse-Bonus
    Verteidigung — Summe Armor-Defense + Talente
    Charisma     — social + Mood-Boost beim Dialog
    Krit-Rate    — combat + weapon crit
    Krit-Schaden — combat + weapon crit_mult

Plus "Stealth/Lockpicking" für Diebe (Recherche-Ergebnis):
    Schleichen   — Dagger-Class + dexterity-Talent → weniger Aggro-Range
    Schlossknacken — separater Skill später (jetzt aus Geschick)
"""
import logging

log = logging.getLogger("liege.attributes")


# Skill-Beiträge pro Attribut: skill → multiplier
SKILL_CONTRIBUTIONS = {
    "stärke": {
        "combat": 1.5, "woodcutting": 0.8, "mining": 0.8, "construction": 0.5,
    },
    "ausdauer": {
        "construction": 1.0, "woodcutting": 0.6, "mining": 0.6, "farming": 0.5,
    },
    "energie": {
        "magic": 1.5, "medical": 0.5,
    },
    "intelligenz": {
        "magic": 1.2, "crafting": 0.5, "medical": 0.6,
    },
    "weisheit": {
        "medical": 1.0, "social": 0.6, "magic": 0.4,
    },
    "ausweichen": {
        "combat": 0.4, "gathering": 0.3,
    },
    "geschick": {
        "combat": 0.5, "crafting": 0.8, "gathering": 0.5,
    },
    "verteidigung": {
        "combat": 0.8, "construction": 0.4,
    },
    "charisma": {
        "social": 1.5,
    },
    "krit_rate": {
        "combat": 0.6, "magic": 0.4,
    },
    "krit_schaden": {
        "combat": 0.5,
    },
    "schleichen": {
        "gathering": 0.5, "combat": 0.3,
    },
}

# Affix-Stats die Attribute boosten
AFFIX_TO_ATTR = {
    "damage_pct":       ("stärke", 0.5),
    "speed_pct":        ("geschick", 0.3),
    "crit_chance_pct":  ("krit_rate", 1.0),
    "defense_flat":     ("verteidigung", 1.0),
    "hp_flat":          ("ausdauer", 0.2),
    "mana_flat":        ("energie", 0.2),
    "fire_damage":      ("energie", 0.3),
    "ice_damage":       ("energie", 0.3),
    "lightning_damage": ("energie", 0.3),
    "necrotic_damage":  ("weisheit", 0.2),
    "lifesteal_pct":    ("stärke", 0.4),
    "armor_pen_pct":    ("geschick", 0.3),
}

# Talent-Effekte → Attribute (kleiner additiver Boost pro Talent)
TALENT_TO_ATTR = {
    "combat_melee_damage":  ("stärke", 2),
    "combat_ranged_damage": ("geschick", 2),
    "combat_crit_chance":   ("krit_rate", 4),
    "combat_crit_damage":   ("krit_schaden", 4),
    "combat_lifesteal":     ("weisheit", 2),
    "magic_spell_damage":   ("intelligenz", 3),
    "magic_max_mana":       ("energie", 4),
    "magic_mana_reduction": ("intelligenz", 2),
    "social_buy_discount":  ("charisma", 4),
    "social_sell_bonus":    ("charisma", 3),
    "social_mood_boost":    ("charisma", 2),
    "medical_heal_bonus":   ("weisheit", 3),
    "mining_extra_damage":  ("stärke", 2),
    "woodcutting_extra_damage": ("stärke", 2),
    "construction_save_chance": ("ausdauer", 2),
    "crafting_quality_bonus":   ("geschick", 3),
}


def calculate_attributes(skills_dict: dict, equipped_items: list[dict],
                         talent_effects: dict, body_parts: dict | None = None) -> dict:
    """Berechnet alle 12 Attribute aus Skills + Equipment + Talenten.

    Returns {attr_name_de: int} — Werte runden auf int.
    """
    attrs: dict[str, float] = {
        "stärke": 0, "ausdauer": 0, "energie": 0, "intelligenz": 0,
        "weisheit": 0, "ausweichen": 0, "geschick": 0, "verteidigung": 0,
        "charisma": 0, "krit_rate": 0, "krit_schaden": 0, "schleichen": 0,
    }

    # Skills → Attribute
    for attr, contribs in SKILL_CONTRIBUTIONS.items():
        for skill, mult in contribs.items():
            lvl = skills_dict.get(skill, {}).get("level", 0)
            attrs[attr] += lvl * mult

    # Equipment-Affixes
    for item in equipped_items:
        for affix in item.get("affixes", []) or []:
            for stat_key, stat_val in affix.get("stats", {}).items():
                if stat_key in AFFIX_TO_ATTR:
                    attr, mult = AFFIX_TO_ATTR[stat_key]
                    attrs[attr] += stat_val * mult

    # Equipment-Base-Stats (Defense aus Rüstung)
    try:
        import item_stats
        for item in equipped_items:
            kind = item.get("kind")
            quality_kind = item.get("quality", "normal")
            if kind in item_stats.ARMOR_STATS:
                d = item_stats.armor_defense(kind, quality_kind)
                attrs["verteidigung"] += d
            elif kind in item_stats.WEAPON_STATS:
                cfg = item_stats.WEAPON_STATS[kind]
                attrs["krit_rate"] += cfg["crit"] * 100   # in %
                attrs["krit_schaden"] += (cfg["crit_mult"] - 1.0) * 50
    except ImportError:
        pass

    # Talente → Attribute
    for tkey, val in talent_effects.items():
        if tkey in TALENT_TO_ATTR:
            attr, scale = TALENT_TO_ATTR[tkey]
            attrs[attr] += val * scale

    # Body-Parts modulieren Verteidigung + Geschick (verletzte legs/arms)
    if body_parts:
        leg_factor = (body_parts.get("legs", 100) / 100.0)
        arm_factor = (body_parts.get("arms", 100) / 100.0)
        attrs["ausweichen"] *= leg_factor
        attrs["geschick"]   *= arm_factor

    # Auf Integer runden
    return {k: int(round(v)) for k, v in attrs.items()}


# Deutsche Labels für UI
ATTR_LABELS = {
    "stärke":       ("💪 Stärke",         "Erhöht physischen Schaden und Roh-Yield"),
    "ausdauer":     ("🫁 Ausdauer",       "Höhere HP-Cap, weniger Erschöpfung"),
    "energie":      ("⚡ Energie",        "Größerer Mana-Pool, bessere Spell-Regen"),
    "intelligenz":  ("🧠 Intelligenz",    "Stärkere Spells, Forschungs-Gates"),
    "weisheit":     ("📖 Weisheit",       "Heilkunst, Status-Resistenz, Lore"),
    "ausweichen":   ("💨 Ausweichen",     "Chance Angriffe komplett zu negieren"),
    "geschick":     ("🎯 Geschick",       "Genauigkeit, Speed, Crafting-Präzision"),
    "verteidigung": ("🛡️ Verteidigung",   "Schadensreduktion gegen Angriffe"),
    "charisma":     ("💬 Charisma",       "Handelspreise, NPC-Mood, Diplomatie"),
    "krit_rate":    ("💥 Krit-Rate",      "Chance auf kritischen Treffer (%)"),
    "krit_schaden": ("✨ Krit-Schaden",   "Multiplier bei kritischen Treffern"),
    "schleichen":   ("👤 Schleichen",     "Reduziert Aggro-Reichweite, Diebe-Skills"),
}


# ─── Welle 34c: WS-Side Attribute-Helpers (extrahiert aus main.py) ───────────

async def compute_attributes(items, player_name: str) -> dict:
    """Sammelt Skills + Equipment + Talents und berechnet Attribute."""
    import skills
    import talents
    import body_parts
    sk = await skills.get_skills(player_name)
    inv = await items.get_inventory(player_name)
    equipped = [it for it in inv if it.get("equipped_slot")]
    te = await talents.aggregate_effects(player_name)
    bp = await body_parts.get_body_parts(player_name)
    attrs = calculate_attributes(sk, equipped, te, bp)
    return {"values": attrs, "labels": ATTR_LABELS}


async def build_stat_sheet(items, player_name: str) -> dict:
    """Vollständiges Stat-Sheet (Welle 15): Attribute + Allokation + Resistances."""
    import player_stats as _ps
    import talents
    import body_parts
    inv = await items.get_inventory(player_name)
    equipped = [it for it in inv if it.get("equipped_slot")]
    te = await talents.aggregate_effects(player_name)
    bp = await body_parts.get_body_parts(player_name)
    sheet = await _ps.get_stat_sheet(player_name, equipped, te, bp)
    sheet["labels"] = ATTR_LABELS
    return sheet


async def send_attrs_update(items, websocket, player_name: str) -> None:
    """Schickt einen frischen Stat-Sheet-Snapshot. Bei jedem Equip/Allocation."""
    import logging
    try:
        sheet = await build_stat_sheet(items, player_name)
        await websocket.send_json({"type": "attrs_update", "stats": sheet})
    except Exception:
        logging.exception("attrs_update fehlgeschlagen")
