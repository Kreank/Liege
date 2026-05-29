"""Storyteller-Director v2 (Welle 20) — Tiered Event-System.

5 Tiers mit eigenem Intervall & Template-Pool:

    Tier              Default-Intervall   Charakter
    ─────────────────────────────────────────────────────────────────
    atmosphere        20 min              Lore/Wetter, keine Gefahr
    encounter         60 min              Begegnung, kleine Mobs/Ruinen
    catastrophe       2.5 h               Bedrohliche Welt-Ereignisse
    boss              5 h                 Welt-Boss erwacht
    cataclysm         18 h                Welt-verändernde Mega-Ereignisse

Storyteller-Modi (chill/balanced/chaos) skalieren die Intervalle weiter:
    chill:    ×1.6  (alles seltener, friedlicher)
    balanced: ×1.0  (Default)
    chaos:    ×0.55 (alles häufiger, Tiers können sich überlappen)

Audience-System (Welle 20):
    Jedes Template hat audience=["warrior","crafter","mage",...,"any"].
    Wenn aktive Spieler-Profile mit Template-Audience matchen, bekommt das
    Template ein 2× Weight. → Schmied-Server bekommt eher Crafting-Events,
    Krieger-Server eher Combat-Events.
"""
import logging
import os
import random
import time

log = logging.getLogger("liege.storyteller")


MODES = ("chill", "balanced", "chaos")
DEFAULT_MODE = os.environ.get("STORYTELLER_MODE", "balanced")

# ─── Tier-Definitionen ──────────────────────────────────────────────────────
# Default-Intervalle in Sekunden. Können per Env überschrieben werden.
TIERS = ("atmosphere", "encounter", "catastrophe", "boss", "cataclysm")

TIER_BASE_INTERVAL = {
    "atmosphere":  int(os.environ.get("EVT_ATMOSPHERE_SEC",  "1200")),     #  20 min
    "encounter":   int(os.environ.get("EVT_ENCOUNTER_SEC",   "3600")),     #  60 min
    "catastrophe": int(os.environ.get("EVT_CATASTROPHE_SEC", "9000")),     # 150 min
    "boss":        int(os.environ.get("EVT_BOSS_SEC",        "18000")),    #   5 h
    "cataclysm":   int(os.environ.get("EVT_CATACLYSM_SEC",   "64800")),    #  18 h
}

# Modus-Profile (Tier-Interval-Multiplier + Audience-Bonus + Variance)
MODE_CONFIG = {
    "chill":    {"interval_mult": 1.6,  "audience_bonus": 2.5, "danger_weight": 0.5},
    "balanced": {"interval_mult": 1.0,  "audience_bonus": 2.0, "danger_weight": 1.0},
    "chaos":    {"interval_mult": 0.55, "audience_bonus": 1.5, "danger_weight": 1.6},
}


# ─── Event-Templates ────────────────────────────────────────────────────────
# Felder pro Template:
#   tier        — atmosphere/encounter/catastrophe/boss/cataclysm
#   tag         — sub-thema für LLM-prompt
#   weight      — Basis-Wahrscheinlichkeit innerhalb des Tiers
#   audience    — ["warrior","crafter","mage","farmer","ranger","any"]
#   danger      — 0.0..1.0  (0=harmlos, 1=tödlich) — für Anti-Streak-Logik
#   min_wealth  — minimale Player-Bauten-Anzahl (optional)
#   effect      — string-tag: was passiert mechanisch (boss_spawn, ruin_spawn, …)

EVENT_TEMPLATES = [
    # ── Tier 1: Atmosphäre (~20min) ─────────────────────────────────────────
    {"tier": "atmosphere", "tag": "rain",         "weight": 20, "audience": ["any"], "danger": 0.0},
    {"tier": "atmosphere", "tag": "fog",          "weight": 18, "audience": ["any","ranger"], "danger": 0.05},
    {"tier": "atmosphere", "tag": "snow",         "weight": 12, "audience": ["any"], "danger": 0.0},
    {"tier": "atmosphere", "tag": "wind",         "weight": 10, "audience": ["any"], "danger": 0.0},
    {"tier": "atmosphere", "tag": "lore_whisper", "weight": 15, "audience": ["any","mage"], "danger": 0.0},
    {"tier": "atmosphere", "tag": "wandering_bard","weight": 12, "audience": ["any"], "danger": 0.0},
    {"tier": "atmosphere", "tag": "ancient_song", "weight": 8,  "audience": ["mage","ranger"], "danger": 0.0},
    {"tier": "atmosphere", "tag": "lost_coin",    "weight": 10, "audience": ["any","crafter"], "danger": 0.0, "effect": "drop_coin"},
    {"tier": "atmosphere", "tag": "blessed_breeze","weight": 6,  "audience": ["any"], "danger": 0.0, "effect": "small_buff"},

    # ── Tier 2: Begegnung (~60min) ──────────────────────────────────────────
    {"tier": "encounter", "tag": "ruin_appears",  "weight": 20, "audience": ["any","ranger","mage"], "danger": 0.2, "effect": "ruin_spawn"},
    {"tier": "encounter", "tag": "wolf_pack",     "weight": 18, "audience": ["warrior","ranger"], "danger": 0.5},
    {"tier": "encounter", "tag": "bandit_scout",  "weight": 16, "audience": ["warrior"], "danger": 0.6, "effect": "spawn_bandits"},
    {"tier": "encounter", "tag": "wandering_trader","weight":15, "audience": ["any","crafter"], "danger": 0.0, "effect": "spawn_merchant"},
    {"tier": "encounter", "tag": "merchant_caravan","weight":10, "audience": ["any","crafter"], "danger": 0.0, "effect": "spawn_caravan"},
    {"tier": "encounter", "tag": "rare_herb",     "weight": 12, "audience": ["any","farmer","mage"], "danger": 0.0, "effect": "spawn_herb"},
    {"tier": "encounter", "tag": "ore_vein",      "weight": 12, "audience": ["crafter"], "danger": 0.1, "effect": "spawn_ore"},
    {"tier": "encounter", "tag": "lost_caravan",  "weight": 10, "audience": ["any","ranger"], "danger": 0.3, "effect": "drop_items"},
    {"tier": "encounter", "tag": "haunted_tree",  "weight": 8,  "audience": ["mage","ranger"], "danger": 0.4},
    {"tier": "encounter", "tag": "spider_nest",   "weight": 9,  "audience": ["warrior"], "danger": 0.5, "effect": "spawn_spiders"},
    {"tier": "encounter", "tag": "skeleton_grave","weight": 10, "audience": ["warrior","mage"], "danger": 0.6, "effect": "spawn_undead"},

    # ── Tier 3: Katastrophe (~2.5h) ─────────────────────────────────────────
    {"tier": "catastrophe", "tag": "locust_swarm",  "weight": 14, "audience": ["farmer","any"], "danger": 0.7, "effect": "destroy_farms"},
    {"tier": "catastrophe", "tag": "wildfire",       "weight": 12, "audience": ["any","ranger"], "danger": 0.8, "effect": "burn_area"},
    {"tier": "catastrophe", "tag": "poison_spring", "weight": 10, "audience": ["any","ranger"], "danger": 0.6, "effect": "taint_water"},
    {"tier": "catastrophe", "tag": "earthquake",    "weight": 10, "audience": ["any","crafter"], "danger": 0.7, "effect": "damage_structures"},
    {"tier": "catastrophe", "tag": "raid_warning",  "weight": 16, "audience": ["warrior"], "danger": 0.8, "effect": "spawn_raid"},
    {"tier": "catastrophe", "tag": "plague_rumor",  "weight": 8,  "audience": ["any","mage"], "danger": 0.6, "effect": "plague_npcs"},
    {"tier": "catastrophe", "tag": "blood_moon_prelude","weight": 6, "audience": ["any","warrior"], "danger": 0.9},
    {"tier": "catastrophe", "tag": "elite_pack",    "weight": 10, "audience": ["warrior"], "danger": 0.8, "effect": "spawn_elites"},
    # Welle 2026-05-29: 5 neue Disaster (Art-Packs verdrahtet).
    {"tier": "catastrophe", "tag": "thunderstorm",   "weight": 14, "audience": ["any"], "danger": 0.7, "effect": "thunderstorm"},
    {"tier": "catastrophe", "tag": "toxic_fog",      "weight": 11, "audience": ["any","mage"], "danger": 0.7, "effect": "toxic_fog"},
    {"tier": "catastrophe", "tag": "ash_rain",       "weight": 11, "audience": ["any"], "danger": 0.6, "effect": "ash_rain"},
    {"tier": "catastrophe", "tag": "scorching_heat", "weight": 11, "audience": ["any","farmer"], "danger": 0.7, "effect": "scorching_heat"},
    {"tier": "catastrophe", "tag": "frog_plague",    "weight": 10, "audience": ["any","farmer"], "danger": 0.6, "effect": "frog_plague"},

    # ── Tier 4: Welt-Boss (~5h) ─────────────────────────────────────────────
    {"tier": "boss", "tag": "dragon_awakens",     "weight": 18, "audience": ["warrior"], "danger": 1.0, "effect": "boss_spawn:dragon_whelp"},
    {"tier": "boss", "tag": "lich_risen",         "weight": 14, "audience": ["warrior","mage"], "danger": 1.0, "effect": "boss_spawn:necromancer"},
    {"tier": "boss", "tag": "ancient_treant",     "weight": 12, "audience": ["warrior","ranger"], "danger": 1.0, "effect": "boss_spawn:dendroid_guardian"},
    {"tier": "boss", "tag": "void_brute",         "weight": 10, "audience": ["warrior","mage"], "danger": 1.0, "effect": "boss_spawn:void_eye_brute"},
    {"tier": "boss", "tag": "magma_lord",         "weight": 10, "audience": ["warrior"], "danger": 1.0, "effect": "boss_spawn:magma_shell_devourer"},
    {"tier": "boss", "tag": "frost_warlord",      "weight": 10, "audience": ["warrior"], "danger": 1.0, "effect": "boss_spawn:frost_rune_boar_prime"},
    {"tier": "boss", "tag": "kaiju_awakening",    "weight": 8,  "audience": ["warrior"], "danger": 1.0, "effect": "boss_spawn:kaiju_thornback"},
    {"tier": "boss", "tag": "colossus_emerges",   "weight": 8,  "audience": ["warrior"], "danger": 1.0, "effect": "boss_spawn:rockshell_colossus"},
    {"tier": "boss", "tag": "blood_drake",        "weight": 8,  "audience": ["warrior","ranger"], "danger": 1.0, "effect": "boss_spawn:blood_antler_drake"},

    # ── Tier 5: Kataklysmus (~18h) ──────────────────────────────────────────
    {"tier": "cataclysm", "tag": "blood_moon",    "weight": 20, "audience": ["any"], "danger": 1.0, "effect": "blood_moon"},
    {"tier": "cataclysm", "tag": "dying_sun",     "weight": 16, "audience": ["any"], "danger": 1.0, "effect": "dying_sun"},
    {"tier": "cataclysm", "tag": "goblin_invasion","weight": 14, "audience": ["warrior"], "danger": 1.0, "effect": "spawn_invasion:goblin:50"},
    {"tier": "cataclysm", "tag": "void_storm",    "weight": 10, "audience": ["mage"], "danger": 1.0, "effect": "void_storm"},
    {"tier": "cataclysm", "tag": "blessing_of_dawn","weight": 8, "audience": ["any"], "danger": 0.0, "effect": "world_buff"},
]


def _initial_tier_state() -> dict[str, float]:
    """Initial-Cooldown beim Server-Start:
    - atmosphere darf sofort feuern (kleines Welt-Geflüster gleich nach Login)
    - alle höheren Tiers warten ein volles Intervall bevor sie fällig werden
      (sonst feuerten Boss + Cataclysm + Catastrophe + Encounter in den ersten
      Minuten nach Start alle nacheinander = "4 Events in 4 Minuten")
    """
    now = time.monotonic()
    return {
        "atmosphere":  0.0,        # sofort fällig
        "encounter":   now,        # +60min
        "catastrophe": now,        # +2.5h
        "boss":        now,        # +5h
        "cataclysm":   now,        # +18h
    }


_state = {
    "mode": DEFAULT_MODE if DEFAULT_MODE in MODES else "balanced",
    "last_tier_event_at": _initial_tier_state(),
    "events_count":  0,
    "danger_streak": 0,
}


def set_mode(mode: str) -> None:
    if mode in MODES:
        _state["mode"] = mode
        log.info("Storyteller-Modus gewechselt zu: %s", mode)


def get_mode() -> str:
    return _state["mode"]


def _time_since(tier: str) -> float:
    last = _state["last_tier_event_at"].get(tier, 0.0)
    if last == 0.0:
        return 999999.0
    return time.monotonic() - last


def tier_due(tier: str) -> bool:
    """True wenn ein Event dieses Tiers fällig ist (Intervall × Modus-Multiplier abgelaufen)."""
    cfg = MODE_CONFIG[_state["mode"]]
    interval = TIER_BASE_INTERVAL[tier] * cfg["interval_mult"]
    return _time_since(tier) >= interval


def due_tiers() -> list[str]:
    """Liste aller Tiers die JETZT abfeuern dürften — in absteigender Priorität.
    Bei chaos können mehrere gleichzeitig zurückgegeben werden."""
    return [t for t in TIERS if tier_due(t)]


def select_event(tier: str, world_state: dict) -> dict | None:
    """Wählt ein Event aus dem gegebenen Tier basierend auf Welt-Zustand,
    Audience-Match und Modus-Weighting.

    world_state: {
        "active_players":   N,
        "active_audiences": {"warrior", "crafter", ...},   # Profile aller verbundenen
        "wealth_score":     N,
        "creature_count":   N,
        "structure_count":  N,
    }
    """
    cfg = MODE_CONFIG[_state["mode"]]
    pool = [t for t in EVENT_TEMPLATES if t["tier"] == tier]
    if not pool:
        return None

    wealth = world_state.get("wealth_score", 0)
    audiences = world_state.get("active_audiences", set())
    candidates = []

    for tmpl in pool:
        if tmpl.get("min_wealth", 0) > wealth:
            continue
        weight = float(tmpl["weight"])
        danger = tmpl.get("danger", 0.0)
        # Audience-Match-Bonus
        if audiences and (set(tmpl.get("audience", [])) & audiences):
            weight *= cfg["audience_bonus"]
        # Anti-Streak: nach 2 gefährlichen Events in Folge → weniger Gefahr
        if _state["danger_streak"] >= 2 and danger > 0.5:
            weight *= 0.4
        # Modus-Danger-Skalierung
        if danger > 0.5:
            weight *= cfg["danger_weight"]
        candidates.append((tmpl, max(0.01, weight)))

    if not candidates:
        return None
    chosen = random.choices(
        [c[0] for c in candidates], weights=[c[1] for c in candidates], k=1
    )[0]
    return chosen


def mark_event_fired(tier: str, danger: float = 0.0) -> None:
    _state["last_tier_event_at"][tier] = time.monotonic()
    _state["events_count"] += 1
    if danger > 0.5:
        _state["danger_streak"] += 1
    else:
        _state["danger_streak"] = 0


def status_summary() -> dict:
    return {
        "mode":          _state["mode"],
        "events_fired":  _state["events_count"],
        "danger_streak": _state["danger_streak"],
        "tiers": {
            t: {
                "interval_s": int(TIER_BASE_INTERVAL[t] * MODE_CONFIG[_state["mode"]]["interval_mult"]),
                "since_last_s": int(_time_since(t)),
                "due": tier_due(t),
            } for t in TIERS
        },
    }
