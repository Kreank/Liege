"""Player-Attribute-System (derived stats).

Saubere Trennung Kern-Attribute ↔ abgeleitete Werte (Redesign 2026-05-31):

  KERN-ATTRIBUTE (definieren den Charakter):
    Stärke       — physischer Schaden, Abbau-Ertrag (Roh-Yield), Tragelast
    Geschick     — Krit-Rate, Ausweichen, Crafting-Präzision, Heimlichkeit (passiv)
    Vitalität    — max. Leben (HP-Cap), HP-Regeneration, Körper-Widerstand
    Intelligenz  — max. Mana, Magieschaden, Forschungstempo
    Willenskraft — Mana-Regeneration, Status-Resistenzen, Heileffizienz
    Charisma     — Handelspreise, NPC-Stimmung

  ABGELEITETE WERTE (zusätzlich direkt verteilbar):
    Verteidigung — Schadensreduktion (Summe Armor-Defense + Talente + Punkte)
    Ausweichen   — Negier-Chance (Geschick + boots + Punkte)
    Krit-Rate    — Krit-Chance (Geschick + weapon crit + Punkte)
    Krit-Schaden — Krit-Multiplier (combat + weapon crit_mult + Punkte)

Hinweis Migration: „Ausdauer" (Attr) → Vitalität; „Energie"+„Weisheit" →
Willenskraft; „Schleichen" entfällt (passiv aus Geschick). Die Ressource
Ausdauer (Stamina) bleibt davon unberührt. Bestehende Punkte werden per
Respec (db.py) als freie Punkte zurückgegeben.
"""
import logging

log = logging.getLogger("liege.attributes")


# Skill-Beiträge pro Attribut: skill → multiplier (ausgewogene Gewichtung).
SKILL_CONTRIBUTIONS = {
    # — Kern-Attribute —
    "stärke": {
        "combat": 1.5, "woodcutting": 0.8, "mining": 0.8, "construction": 0.5,
    },
    "geschick": {
        "combat": 0.5, "crafting": 0.8, "gathering": 0.5,
    },
    "vitalität": {
        "construction": 1.0, "woodcutting": 0.6, "mining": 0.6, "farming": 0.5,
    },
    "intelligenz": {
        "magic": 1.4, "crafting": 0.5, "medical": 0.4,
    },
    "willenskraft": {
        "medical": 1.0, "magic": 0.6, "social": 0.4,
    },
    "charisma": {
        "social": 1.5,
    },
    # — Abgeleitete (zusätzlich verteilbar) —
    "verteidigung": {
        "combat": 0.8, "construction": 0.4,
    },
    "ausweichen": {
        "combat": 0.4, "gathering": 0.3,
    },
    "krit_rate": {
        "combat": 0.6, "magic": 0.4,
    },
    "krit_schaden": {
        "combat": 0.5,
    },
}

# Affix-Stats die Attribute boosten
AFFIX_TO_ATTR = {
    "damage_pct":       ("stärke", 0.5),
    "speed_pct":        ("geschick", 0.3),
    "crit_chance_pct":  ("krit_rate", 1.0),
    "defense_flat":     ("verteidigung", 1.0),
    "hp_flat":          ("vitalität", 0.2),
    "mana_flat":        ("intelligenz", 0.2),
    "fire_damage":      ("intelligenz", 0.3),
    "ice_damage":       ("intelligenz", 0.3),
    "lightning_damage": ("intelligenz", 0.3),
    "necrotic_damage":  ("willenskraft", 0.2),
    "lifesteal_pct":    ("stärke", 0.4),
    "armor_pen_pct":    ("geschick", 0.3),
}

# Talent-Effekte → Attribute (kleiner additiver Boost pro Talent)
TALENT_TO_ATTR = {
    "combat_melee_damage":  ("stärke", 2),
    "combat_ranged_damage": ("geschick", 2),
    "combat_crit_chance":   ("krit_rate", 4),
    "combat_crit_damage":   ("krit_schaden", 4),
    "combat_lifesteal":     ("willenskraft", 2),
    "magic_spell_damage":   ("intelligenz", 3),
    "magic_max_mana":       ("intelligenz", 4),
    "magic_mana_reduction": ("intelligenz", 2),
    "social_buy_discount":  ("charisma", 4),
    "social_sell_bonus":    ("charisma", 3),
    "social_mood_boost":    ("charisma", 2),
    "medical_heal_bonus":   ("willenskraft", 3),
    "mining_extra_damage":  ("stärke", 2),
    "woodcutting_extra_damage": ("stärke", 2),
    "construction_save_chance": ("vitalität", 2),
    "crafting_quality_bonus":   ("geschick", 3),
}


def calculate_attributes(skills_dict: dict, equipped_items: list[dict],
                         talent_effects: dict, body_parts: dict | None = None) -> dict:
    """Berechnet alle 10 Attribute aus Skills + Equipment + Talenten.

    Returns {attr_name_de: int} — Werte runden auf int.
    """
    attrs: dict[str, float] = {
        # Kern
        "stärke": 0, "geschick": 0, "vitalität": 0, "intelligenz": 0,
        "willenskraft": 0, "charisma": 0,
        # Abgeleitet (zusätzlich verteilbar)
        "verteidigung": 0, "ausweichen": 0, "krit_rate": 0, "krit_schaden": 0,
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
            elif kind in item_stats.JEWELRY_STATS:
                # Welle 53: Schmuck (Ring/Amulett) wirkte bisher GAR NICHT — die
                # JEWELRY_STATS wurden nirgends verdrahtet. Wir mappen sie auf
                # Kern-Attribute, von denen sich Max-HP/Mana/Regen/Magie ableiten:
                #   hp_bonus    → vitalität   (+HP, HP-Regen)
                #   mana_bonus  → intelligenz (+Mana)
                #   magic_bonus → intelligenz (Magieschaden)
                #   regen_bonus → willenskraft (Mana-Regen/Resistenz)
                js = item_stats.JEWELRY_STATS[kind]
                attrs["vitalität"]    += js.get("hp_bonus", 0) / HP_PER_VITALITAET
                attrs["intelligenz"]  += js.get("mana_bonus", 0) / MANA_PER_INTELLIGENZ
                attrs["intelligenz"]  += js.get("magic_bonus", 0.0) * 40
                attrs["willenskraft"] += js.get("regen_bonus", 0.0) * 40
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


# Deutsche Labels für UI — Reihenfolge bestimmt die UI-Reihenfolge
# (ATTR_NAMES = list(ATTR_LABELS.keys())). Kern zuerst, dann Abgeleitete.
ATTR_LABELS = {
    # — Kern-Attribute —
    "stärke":       ("💪 Stärke",         "Physischer Schaden, Abbau-Ertrag, Tragelast"),
    "geschick":     ("🎯 Geschick",       "Krit-Rate, Ausweichen, Crafting, Heimlichkeit"),
    "vitalität":    ("❤️ Vitalität",      "Max. Leben, HP-Regeneration, Körper-Widerstand"),
    "intelligenz":  ("🧠 Intelligenz",    "Max. Mana, Magieschaden, Forschungstempo"),
    "willenskraft": ("🔮 Willenskraft",   "Mana-Regeneration, Status-Resistenz, Heileffizienz"),
    "charisma":     ("💬 Charisma",       "Handelspreise, NPC-Stimmung"),
    # — Abgeleitete Werte (zusätzlich verteilbar) —
    "verteidigung": ("🛡️ Verteidigung",   "Schadensreduktion gegen Angriffe"),
    "ausweichen":   ("💨 Ausweichen",     "Chance, Angriffe komplett zu negieren"),
    "krit_rate":    ("💥 Krit-Rate",      "Chance auf kritischen Treffer (%)"),
    "krit_schaden": ("✨ Krit-Schaden",   "Schadensbonus bei kritischen Treffern (%)"),
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


# ─── Attribut → Ressourcen-Caps & Regeneration (mechanische Verdrahtung) ─────
# Vitalität hebt das HP-Cap, Intelligenz den Mana-Pool. Regen pro Needs-Tick
# (30s): HP aus Vitalität, Mana aus Willenskraft. Werte bewusst moderat —
# leicht justierbar.
BASE_MAX_HP = 100
BASE_MAX_MANA = 50
HP_PER_VITALITAET = 5
MANA_PER_INTELLIGENZ = 5


def effective_max_hp(totals: dict) -> int:
    return BASE_MAX_HP + int(totals.get("vitalität", 0)) * HP_PER_VITALITAET


def effective_max_mana(totals: dict) -> int:
    return BASE_MAX_MANA + int(totals.get("intelligenz", 0)) * MANA_PER_INTELLIGENZ


def hp_regen_per_tick(totals: dict) -> float:
    return 1.0 + int(totals.get("vitalität", 0)) * 0.25


def mana_regen_per_tick(totals: dict) -> float:
    return 2.0 + int(totals.get("willenskraft", 0)) * 0.4


async def player_combat_sheet(items, player_name: str) -> dict:
    """FE-konformer Snapshot fürs Charakter-UI: FLACHE `attributes` (deutsche
    Keys + `unspent`) und FLACHE `stats` (damage/defense/crit/attack_speed).

    Verdrahtet zugleich die Ressourcen-Caps: persistiert effektives
    max_hp/max_mana (aus Vitalität/Intelligenz), klemmt aktuelles hp/mana
    darauf und cached die Regen-Raten für den Needs-Loop. Liefert die
    aktuellen Resource-Werte mit zurück (für init/attrs_update → HUD)."""
    import combat
    import item_stats
    import db
    import needs
    import skills as _sk
    sheet = await build_stat_sheet(items, player_name)
    totals = sheet.get("totals", {})

    # — Ressourcen-Caps aus Attributen anwenden (persistieren + klemmen) —
    max_hp = effective_max_hp(totals)
    max_mana = effective_max_mana(totals)
    res = await db.pool().fetchrow(
        "UPDATE players SET max_hp = $1, max_mana = $2, "
        "hp = LEAST(hp, $1), mana = LEAST(mana, $2) "
        "WHERE name = $3 RETURNING hp, mana",
        max_hp, max_mana, player_name,
    )
    cur_hp = res["hp"] if res else max_hp
    cur_mana = res["mana"] if res else max_mana
    # Regen-Raten für den Needs-Loop cachen (vermeidet Attribut-Neuberechnung
    # pro Tick/Spieler).
    needs.set_regen_rates(
        player_name, hp_regen_per_tick(totals), mana_regen_per_tick(totals),
    )

    # Angelegte Waffe → Schaden/Tempo (Anzeige analog combat.calc_player_damage:
    # Durchschnitts-Swing OHNE Crit = base + skill_add + PLAYER_BASE_DAMAGE//2).
    inv = await items.get_inventory(player_name)
    weapon = next(
        (it for it in inv
         if it.get("equipped_slot")
         and (it.get("category") == "weapon" or it.get("kind") in item_stats.WEAPON_STATS)),
        None,
    )
    combat_lvl = await _sk.get_skill_level(player_name, "combat")
    skill_add = combat_lvl // 4
    wkind = weapon.get("kind") if weapon else None
    rolled = (weapon.get("rolled_stats") if weapon else None) or {}
    if "damage_min" in rolled and "damage_max" in rolled:
        base = (rolled["damage_min"] + rolled["damage_max"]) / 2.0
        speed = rolled.get("speed") or item_stats.weapon_attack_speed(wkind)
    else:
        base = item_stats.weapon_base_damage(wkind)
        speed = item_stats.weapon_attack_speed(wkind)
    # Stärke skaliert den physischen Schaden (Welle 51) — denselben Multiplikator
    # cachen wir für den Combat-Pfad (combat.attack_npc), damit angezeigter und
    # tatsächlicher Schaden konsistent sind und Stats mit dem Grundangriff
    # kumulieren. Stärke enthält bereits Equipment-Affixe (damage_pct→stärke).
    str_total = int(totals.get("stärke", 0))
    dmg_mult = 1.0 + str_total * combat.STR_DMG_PER_POINT
    combat.set_player_damage_mult(player_name, dmg_mult)
    # Welle 52: Die vier bisher „toten" Kampfwerte ebenfalls cachen, damit sie im
    # echten Combat wirken (gleiches Pattern wie dmg_mult — eine Stelle, aktuell
    # bei Login/Equip/Allocation). Einheiten siehe combat.py-Setter:
    #   verteidigung → flat defense (combat.damage_reduction in damage_player)
    #   krit_rate    → % Crit-Chance (auf den crit_roll im Attack-Handler)
    #   krit_schaden → additiver % Crit-Schaden-Bonus
    #   ausweichen   → % Dodge-Chance (Roll am Anfang von damage_player, gecappt)
    combat.set_player_defense(player_name, int(totals.get("verteidigung", 0)))
    combat.set_player_crit_chance(player_name, float(totals.get("krit_rate", 0)))
    combat.set_player_crit_damage(player_name, float(totals.get("krit_schaden", 0)))
    combat.set_player_dodge(player_name, float(totals.get("ausweichen", 0)))
    avg_damage = int(round(
        (base + skill_add + combat.PLAYER_BASE_DAMAGE // 2) * dmg_mult))

    stats = {
        "damage":       avg_damage,
        "defense":      totals.get("verteidigung", 0),
        "crit_chance":  totals.get("krit_rate", 0),
        "crit_damage":  totals.get("krit_schaden", 0),
        "attack_speed": round(float(speed), 2),
    }
    attributes = {**totals, "unspent": sheet.get("unspent_points", 0)}
    return {
        "attributes": attributes,
        "stats": stats,
        "max_hp": max_hp,
        "max_mana": max_mana,
        "hp": cur_hp,
        "mana": cur_mana,
    }


async def send_attrs_update(items, websocket, player_name: str) -> None:
    """Schickt einen frischen Stat-Snapshot. Bei jedem Equip/Allocation."""
    import logging
    try:
        cs = await player_combat_sheet(items, player_name)
        await websocket.send_json({
            "type": "attrs_update",
            "attributes": cs["attributes"],
            "stats": cs["stats"],
            "max_hp": cs["max_hp"],
            "max_mana": cs["max_mana"],
            "hp": cs["hp"],
            "mana": cs["mana"],
        })
    except Exception:
        logging.exception("attrs_update fehlgeschlagen")
