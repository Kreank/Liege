"""Combat-Power-Budget — Welle 23 (2026-05-27, ESO-Style Player-Scaling).

Player hat KEIN Single-Level — er hat 11+ Skills, Attribute, Equipment. Daher
`player_power_score(name)`: kontinuierlicher Float ohne Cap, aggregiert alles.

Nominale Skala:
    0–5     Anfänger      (Stunde 1)
    10–20   Aktiv         (paar Stunden)
    30–50   Veteran       (paar Wochen)
    60–100  Long-Term     (Monate)
    120+    Endgame       (Endgame-Bauten, Legendary-Stack)

Sublineare Wachstumskurven (sqrt-basiert) — Mobs werden mit Player stärker,
explodieren aber nicht. Bei Score 100 sind Mob-Stats ~5.5×, nicht 50×.

Gruppen werden über `nearby_player_power(x, y, radius, ...)` aggregiert: HP
skaliert per Gruppen-Mult (1→1.0, 4→2.4), DMG sanfter (1→1.0, 4→1.3).
"""
import math
import time
import logging

log = logging.getLogger("liege.power_budget")

# ─── Player-Power-Score ─────────────────────────────────────────────────────
# Power-Score-Gewichte
WEIGHT_PRIMARY_SKILL    = 1.0    # max(combat, magic) — der primäre Kampf-Skill
WEIGHT_SECONDARY_SKILLS = 0.3    # alle anderen Skills (gesamt)
WEIGHT_ATTRIBUTES       = 0.04   # allocated_attr-Punkte × diesen Faktor
WEIGHT_GEAR_TIER        = 0.5    # equipped Items × (quality_tier_value)

# Quality-Tier-Werte (für Gear-Bonus)
_GEAR_QUALITY_VALUE = {
    "shoddy":   0, "normal": 1, "good": 2, "excellent": 3,
    "masterwork": 4, "legendary": 5,
}

# Sublineare Scaling-Kurven
HP_SCALE_FACTOR  = 0.55    # 1.0 + sqrt(score) × 0.55
DMG_SCALE_FACTOR = 0.32    # 1.0 + sqrt(score) × 0.32

# Cache für player_power_score — Score ändert sich selten (Level-Up, Equip-Wechsel)
_POWER_CACHE: dict = {}     # name → (score, expires_at)
_POWER_CACHE_TTL = 30.0


async def player_power_score(player_name: str) -> float:
    """Kontinuierlicher Power-Score eines Spielers (kein Cap)."""
    now = time.time()
    cached = _POWER_CACHE.get(player_name)
    if cached and cached[1] > now:
        return cached[0]

    # Skills
    try:
        import skills as _skills
        sk = await _skills.get_skills(player_name)
    except Exception:
        sk = {}
    combat_lvl = sk.get("combat", {}).get("level", 0)
    magic_lvl  = sk.get("magic",  {}).get("level", 0)
    primary = max(combat_lvl, magic_lvl)
    others_sum = sum(s.get("level", 0) for k, s in sk.items()
                     if k not in ("combat", "magic"))

    # Allokierte Attribute (JSONB)
    attr_total = 0
    try:
        import db
        row = await db.pool().fetchrow(
            "SELECT allocated_attrs FROM players WHERE name = $1", player_name)
        if row and row["allocated_attrs"]:
            raw = row["allocated_attrs"]
            if isinstance(raw, str):
                import json as _json
                raw = _json.loads(raw)
            if isinstance(raw, dict):
                attr_total = sum(int(v) for v in raw.values() if isinstance(v, (int, float)))
    except Exception:
        pass

    # Equipped Gear (Waffe + Armor + Gloves + Belt + Cape — alle Slots)
    gear_score = 0.0
    try:
        import items as _items
        inv = await _items.get_inventory(player_name)
        for it in inv:
            if not it.get("equipped_slot"):
                continue
            q = it.get("quality") or "normal"
            gear_score += _GEAR_QUALITY_VALUE.get(q, 1)
    except Exception:
        pass

    score = (primary       * WEIGHT_PRIMARY_SKILL
             + others_sum  * WEIGHT_SECONDARY_SKILLS
             + attr_total  * WEIGHT_ATTRIBUTES
             + gear_score  * WEIGHT_GEAR_TIER)
    score = max(0.0, score)
    _POWER_CACHE[player_name] = (score, now + _POWER_CACHE_TTL)
    return score


def invalidate_power_cache(player_name: str | None = None) -> None:
    """Bei Level-Up / Equip-Wechsel / Attr-Allocation aufrufen."""
    if player_name is None:
        _POWER_CACHE.clear()
    else:
        _POWER_CACHE.pop(player_name, None)


# ─── Sublineare Scaling-Kurven (kein Cap) ────────────────────────────────────

def power_to_hp_mult(score: float) -> float:
    """HP-Multiplier basierend auf Power-Score (sqrt-Wachstum, kein Cap)."""
    return 1.0 + math.sqrt(max(0.0, score)) * HP_SCALE_FACTOR


def power_to_dmg_mult(score: float) -> float:
    """DMG-Multiplier basierend auf Power-Score."""
    return 1.0 + math.sqrt(max(0.0, score)) * DMG_SCALE_FACTOR


# ─── Gruppen-Aggregation (Stage-1-Foundation für Gruppen-System) ─────────────

GROUP_RADIUS_DEFAULT = 24    # Tiles: Spieler innerhalb dieser Distanz zählen als Gruppe

# HP-Mult pro Gruppen-Count (ESO-Style)
_GROUP_HP_MULT  = {1: 1.0, 2: 1.55, 3: 2.0, 4: 2.4, 5: 2.7, 6: 2.85}
_GROUP_DMG_MULT = {1: 1.0, 2: 1.10, 3: 1.20, 4: 1.30, 5: 1.35, 6: 1.40}


def group_hp_mult(count: int) -> float:
    return _GROUP_HP_MULT.get(count, 2.85 if count > 6 else 1.0)


def group_dmg_mult(count: int) -> float:
    return _GROUP_DMG_MULT.get(count, 1.40 if count > 6 else 1.0)


async def nearby_player_power(x: int, y: int, connection_manager,
                                radius: int = GROUP_RADIUS_DEFAULT) -> dict:
    """Aggregiert die Power-Score(s) aller Spieler innerhalb von `radius` Tiles
    um (x, y). Returns Dict mit:
        score       — höchster Einzel-Score (für Tier-Baseline)
        count       — Anzahl Spieler im Radius (für Group-Mult)
        hp_mult     — kombiniert: power_to_hp_mult × group_hp_mult
        dmg_mult    — kombiniert
        names       — Namen der nahen Spieler (Debug)
    Wenn niemand in Reichweite ist: Score 0, count 0, Default-Mults (1.0)."""
    players = connection_manager.get_players() if connection_manager else {}
    nearby = []
    for pname, pdata in players.items():
        px = pdata.get("x", 0)
        py = pdata.get("y", 0)
        if abs(px - x) + abs(py - y) <= radius:
            score = await player_power_score(pname)
            nearby.append((pname, score))
    if not nearby:
        return {"score": 0.0, "count": 0, "hp_mult": 1.0, "dmg_mult": 1.0,
                "names": []}
    top_score = max(s for _, s in nearby)
    count = len(nearby)
    hp_mult  = power_to_hp_mult(top_score)  * group_hp_mult(count)
    dmg_mult = power_to_dmg_mult(top_score) * group_dmg_mult(count)
    return {"score": top_score, "count": count,
            "hp_mult": hp_mult, "dmg_mult": dmg_mult,
            "names": [n for n, _ in nearby]}


# ─── Region-Difficulty (Stage-2-Hook, Default-Passthrough) ───────────────────

async def region_modifier(x: int, y: int) -> dict:
    """Lädt regionspezifische Modifier (gesetzt vom Storyteller/World-Brain).
    Stage-2-Hook — gibt aktuell immer Defaults zurück."""
    try:
        import region_difficulty
        return await region_difficulty.get_modifier_for_world_pos(x, y)
    except Exception:
        return {"hp_mod": 1.0, "dmg_mod": 1.0, "tier_bias": 0}


# ─── Legacy (alte Konstanten + Helper, deprecated aber backwards-compat) ─────
BASE_PLAYER_DPS = 10.0
GROWTH_RATE     = 1.15
BOSS_GROWTH     = 1.12
SOFT_CAP_LEVEL  = 999     # effektiv kein Cap mehr — bleibt nur für alte Callers
MOB_HP_FLOOR_MULT = 1.0
MOB_HP_CAP_MULT   = 999.0
MOB_DMG_GROWTH    = 1.06


def expected_player_dps(level: int) -> float:
    """LEGACY."""
    lvl = max(0, min(SOFT_CAP_LEVEL, level))
    return BASE_PLAYER_DPS * (GROWTH_RATE ** lvl)


def expected_boss_dps(level: int) -> float:
    """LEGACY."""
    lvl = max(0, min(SOFT_CAP_LEVEL, level))
    return BASE_PLAYER_DPS * (BOSS_GROWTH ** lvl)


def mob_hp_multiplier(player_level: int) -> float:
    """Skaliert Base-HP von Mobs basierend auf Player-Level."""
    lvl = max(0, player_level)
    mult = 1.0 + lvl * 0.10
    return min(MOB_HP_CAP_MULT, max(MOB_HP_FLOOR_MULT, mult))


def mob_damage_multiplier(player_level: int) -> float:
    """Skaliert Mob-Damage sanft mit Player-Level."""
    lvl = max(0, min(SOFT_CAP_LEVEL, player_level))
    return MOB_DMG_GROWTH ** lvl


def player_level_estimate(skills_dict: dict) -> int:
    """Schätzt 'Player-Level' aus Skills-Dict.

    Kombiniert höchsten Combat-Wert (zählt am meisten) mit zweithöchster Skill.
    Beispiel: combat=10, mining=8 → ~9.
    """
    if not skills_dict:
        return 0
    combat_lvl = skills_dict.get("combat", {}).get("level", 0)
    magic_lvl = skills_dict.get("magic", {}).get("level", 0)
    others = sorted(
        (s.get("level", 0) for k, s in skills_dict.items()
         if k not in ("combat", "magic")),
        reverse=True,
    )
    second = others[0] if others else 0
    # Combat/Magic ist primär; restliche bringen 50% mit
    primary = max(combat_lvl, magic_lvl)
    return int(round(primary + second * 0.5))


def kalibrate_mob_hp(base_hp: int, player_level: int) -> int:
    """LEGACY — multiplikative Skalierung des per-kind base_hp. Wird ersetzt
    durch tier_baseline_hp() + flavor-Mult (siehe combat.kalibrated_npc_hp).
    Bleibt für Backwards-Compat."""
    return int(round(base_hp * mob_hp_multiplier(player_level)))


def kalibrate_mob_damage(base_dmg: int, player_level: int) -> int:
    """LEGACY — siehe kalibrate_mob_hp."""
    return int(round(base_dmg * mob_damage_multiplier(player_level)))


# ─── Tier-Baseline-System (ESO-Style Player-Scaling) ─────────────────────────
# Jedes Mob-Tier hat einen Ziel-Stat-Pool, der mit Player-Level wächst. Innerhalb
# eines Tiers wird per Flavor-Mult variiert (in combat.py), sodass z.B. wolf
# und skeleton beide Tier-2 sind, aber unterschiedlich „schmeckt".
#
# Standard-Mob (Tier 2) bei Level 0:
#     HP  = 35      (≈3-4 Hits zum Kill mit Fauste/Holzwaffe)
#     DMG = 8       (≈12 Hits bis Tod bei 100 HP — fair)
#
# Bosse (Tier 4) haben einen festen FLOOR + Bonus-Multiplier, damit sie auch
# bei Level 0 nicht trivialisieren — wer auf Boss-Tier kommt, ist gewarnt.

TIER_MULTS = {
    1: {"hp": 0.45, "dmg": 0.55},   # Trash — schnell weg
    2: {"hp": 1.00, "dmg": 1.00},   # Standard-Mob (Referenz)
    3: {"hp": 1.80, "dmg": 1.35},   # Elite — Vorsicht
    4: {"hp": 3.50, "dmg": 1.80},   # Boss — Killer-Build nötig
}

# Boss-spezifisch — Floor, damit T4 nie zu leicht (auch bei Lvl 0)
BOSS_HP_FLOOR        = 200
BOSS_DMG_FLOOR       = 22
BOSS_LEVEL_HP_BONUS  = 20    # +20 HP pro Player-Level (zusätzlich zum Tier-Scale)
BOSS_LEVEL_DMG_BONUS = 0.5   # +0.5 DMG pro Player-Level (zusätzlich)

# Standard-Mob Referenz-Stats bei Power-Score 0 (Anfänger)
STANDARD_BASE_HP  = 35.0
STANDARD_BASE_DMG = 8.0


def tier_baseline_hp(tier: int, player_power) -> int:
    """Ziel-HP für ein Mob dieses Tiers bei diesem Power-Score.

    Akzeptiert int (legacy: Level) oder float (neu: Power-Score) — sind
    nominal in ähnlicher Größenordnung.
    """
    score = float(player_power)
    lvl_mult = power_to_hp_mult(score)
    tier_m = TIER_MULTS.get(tier, TIER_MULTS[2])["hp"]
    val = STANDARD_BASE_HP * lvl_mult * tier_m
    if tier == 4:
        # Boss-Floor + zusätzlicher per-score-Bonus (linear)
        val = max(val, BOSS_HP_FLOOR + score * BOSS_LEVEL_HP_BONUS)
    return int(round(val))


def tier_baseline_dmg(tier: int, player_power) -> int:
    """Ziel-Schaden für ein Mob dieses Tiers bei diesem Power-Score."""
    score = float(player_power)
    lvl_mult = power_to_dmg_mult(score)
    tier_m = TIER_MULTS.get(tier, TIER_MULTS[2])["dmg"]
    val = STANDARD_BASE_DMG * lvl_mult * tier_m
    if tier == 4:
        val = max(val, BOSS_DMG_FLOOR + score * BOSS_LEVEL_DMG_BONUS)
    return int(round(val))
