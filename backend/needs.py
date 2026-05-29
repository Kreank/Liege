import asyncio
import logging
import os
from typing import Awaitable, Callable

import db

log = logging.getLogger("liege.needs")

# — DB-Schema-Ergänzungen ———————————————————————————————————————————————————————
# In db.py beim Init ausführen (idempotent via IF NOT EXISTS).
SCHEMA_ALTERS: tuple[str, ...] = (
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS hunger INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS max_hunger INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS stamina INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS max_stamina INTEGER NOT NULL DEFAULT 100",
    # Welle 17 — Durst
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS thirst INTEGER NOT NULL DEFAULT 100",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS max_thirst INTEGER NOT NULL DEFAULT 100",
)

# — Tuning-Konstanten —————————————————————————————————————————————————————————
HUNGER_TICK_SECONDS: int = int(os.environ.get("HUNGER_TICK_SECONDS", "30"))
HUNGER_STARVE_HP_DAMAGE: int = 2
# Durst tickt schneller als Hunger (RimWorld/Survival-style ~1.5×)
THIRST_PER_TICK: int = int(os.environ.get("THIRST_PER_TICK", "2"))
THIRST_DEHYDRATE_HP_DAMAGE: int = 3   # mehr als hunger weil schneller tödlich

# — Ausdauer/Stamina-Tuning (Welle 2026-05-29: Überarbeitung) —————————————————
# Eigener schneller Loop (run_stamina) tickt sekündlich. Regeneration hängt vom
# SCHLECHTEREN Wert aus Hunger%/Durst% ab — beide müssen hoch sein für volle Regen.
STAMINA_TICK_SECONDS: float = 1.0
STAMINA_REGEN_FULL: float = 2.0    # min(Hunger%,Durst%) >= 80%  → 2 / s
STAMINA_REGEN_MID:  float = 1.0    #                  50–80%     → 1 / s
STAMINA_REGEN_LOW:  float = 0.5    #                   0–50%     → 0,5 / s
#                                  ==0%                          → 0   / s
SUPPLY_FULL_PCT: float = 0.80
SUPPLY_LOW_PCT:  float = 0.50      # Schwelle für „Spieler merkt es"
# Sprinten (SHIFT): höchster Verbrauch, stoppt automatisch bei 0.
SPRINT_DRAIN_PER_SEC: float = 8.0
# Angriffs-Kosten pro Schlag (alle Waffen kosten jetzt Ausdauer).
STAMINA_ATTACK_HEAVY: int = 8      # 2H-Nahkampf (greatsword/spear/scythe/…)
STAMINA_ATTACK_LIGHT: int = 4      # 1H, Bogen/Armbrust, Magie-Waffen
# Bauen: bei guter Versorgung (>=50%) gratis → erschöpft nie. Unter 50% kostet
# es Ausdauer und kann blockieren — der Spieler merkt seine Mangelversorgung.
BUILD_STAMINA_COST: int = 6
# Bett/Schlafen: ruht bis 100% (≈ max_stamina / Rate Sekunden).
BED_REST_RESTORE_PER_SEC: float = 8.0
# Schlaf heilt auch HP langsam mit (lebensecht).
BED_REST_HP_PER_SEC: int = 4

# — Laufzeit-State (in-memory) ————————————————————————————————————————————————
# Sprint- und Ruhe-Zustand pro Spieler; vom run_stamina-Loop gelesen.
_sprinting: set[str] = set()
_resting: set[str] = set()
_stamina_accum: dict[str, float] = {}   # Sub-Integer-Akkumulator pro Spieler


def set_sprint(player_name: str, on: bool) -> None:
    if on:
        _sprinting.add(player_name)
    else:
        _sprinting.discard(player_name)


def set_resting(player_name: str, on: bool) -> None:
    if on:
        _resting.add(player_name)
        _sprinting.discard(player_name)   # Schlafen + Sprinten schließt sich aus
    else:
        _resting.discard(player_name)


def is_resting(player_name: str) -> bool:
    return player_name in _resting


def clear_player_state(player_name: str) -> None:
    """Bei Disconnect/Reset aufräumen."""
    _sprinting.discard(player_name)
    _resting.discard(player_name)
    _stamina_accum.pop(player_name, None)

# Drink-Werte pro Item-Kind (analog FOOD_RESTORE)
THIRST_RESTORE: dict[str, int] = {
    "water_drink":   25,    # generischer Wasser-Trink (Brunnen / Wasser-Tile)
    "well_drink":    30,    # Brunnen direkt = etwas mehr
    "fish":           5,    # rohes Fleisch/Fisch hat etwas Flüssigkeit
    "raw_meat":       3,
    # Beeren/Obst geben Mini-Hydratation
    "strawberry":     3,
    "blueberry":      3,
    "blackberry":     3,
    "raspberry":      3,
    "berries":        3,
    "apple":          4,
    "pear":           4,
    "plum":           3,
    "cherry":         3,
    "cucumber":       6,    # Gurke = viel Wasser
    "tomato":         5,
    "grapes_blue":    5,
    "grapes_green":   5,
    "pumpkin":        4,
    # Tränke
    "health_potion":  8,    # auch ein bisschen Flüssigkeit
    "mana_potion":    8,
    # — Asset-Drop 2026-05-27b: Dairy/Drinks (Hydration) —
    "milk_bucket":   20,    # voller Eimer
    "milk_jug":      15,    # Krug Milch
    "cream_bowl":     8,
    "curds_bowl":     5,
}


def thirst_value(kind: str) -> int:
    return THIRST_RESTORE.get(kind, 0)

# Welche Items füllen Hunger auf (0 oder Abwesenheit => kein Food).
# Balance-Achsen:
#   - Größe → Sättigung (Beere 10, Apfel 16, Kohl 20, Kürbis 28, gegartes
#     Fleisch 50)
#   - Verarbeitung → Bonus (gegart > roh; Brot 38 vs Weizen 5)
#   - Tränke sind Spezialisten: kleine Sättigung, dafür großer HP/Mana-Effekt
FOOD_RESTORE: dict[str, int] = {
    # Tränke / Kraut
    "herb":           6,
    "health_potion": 25,
    "mana_potion":   15,
    # Beeren — alle gleich (4× Snack)
    "strawberry":    10,
    "blueberry":     10,
    "blackberry":    10,
    "raspberry":     10,
    "berries":       10,    # Legacy-Alias
    # Obst
    "apple":         16,
    "pear":          16,
    "plum":          12,
    "cherry":        10,
    # Pilze
    "mushroom_food": 18,
    # Feldfrüchte — sortiert nach Größe
    "wheat":          5,    # Rohstoff, kaum essbar
    "cucumber":      10,
    "onion":         10,
    "carrot":        12,
    "tomato":        12,
    "potato":        18,
    "cabbage":       20,
    "corn":          22,
    "pumpkin":       28,
    # Welle 16 — neue Pflanzen
    "garlic":         8,    # Würzig, mehr Aroma als Sättigung
    "grapes_blue":   12,    # Wie kleine Beeren-Cluster
    "grapes_green":  12,
    # Fleisch / Fisch
    "raw_meat":      16,    # Sättigend, aber kein HP
    "fish":          22,
    # Verarbeitet — höchste Sättigung
    "bread":         38,
    "food_ration":   35,
    "cooked_meat":   50,
    # — Asset-Drop 2026-05-27b: Dairy & Processed Food —
    # Dairy — moderate Sättigung, gute Hydration (siehe THIRST_RESTORE)
    "milk_bucket":     12,
    "milk_jug":         8,
    "cream_bowl":      10,
    "curds_bowl":      14,
    "butter_pat":      10,    # konzentriert, klein aber kalorienreich
    "cheese_wedge":    22,    # nahrhaft
    "cheese_wheel":    45,    # ganzes Rad, riesige Mahlzeit
    "egg":              8,
    "egg_basket":      32,    # 4-5 Eier
    # Processed — Vorräte, hochkalorisch
    "lard_pot":        15,
    "salted_meat":     40,
    "smoked_meat":     45,
    "sausage":         32,
    "dried_fish":      28,
    "honey_jar":       18,    # süß, energiereich
    # Nicht-Food (explizit 0)
    "wood": 0, "stone": 0, "iron_ore": 0, "bone": 0, "plant_fiber": 0,
}


# — Helper für use_item-Integration ——————————————————————————————————————————

def is_food(kind: str) -> bool:
    """True wenn das Item-Kind Hunger auffüllt (Wert > 0)."""
    return FOOD_RESTORE.get(kind, 0) > 0


def food_value(kind: str) -> int:
    """Wieviel Hunger füllt dieses Item auf? 0 wenn unbekannt/kein Food."""
    return FOOD_RESTORE.get(kind, 0)


# — DB-Queries ————————————————————————————————————————————————————————————————

def _row_to_needs(row) -> dict:
    return {
        "hunger":      row["hunger"],
        "max_hunger":  row["max_hunger"],
        "stamina":     row["stamina"],
        "max_stamina": row["max_stamina"],
        "thirst":      row["thirst"],
        "max_thirst":  row["max_thirst"],
    }


async def get_needs(player_name: str) -> dict | None:
    row = await db.pool().fetchrow(
        "SELECT hunger, max_hunger, stamina, max_stamina, thirst, max_thirst "
        "FROM players WHERE name = $1",
        player_name,
    )
    return _row_to_needs(row) if row else None


async def restore_thirst(player_name: str, amount: int) -> dict | None:
    if amount <= 0:
        return None
    row = await db.pool().fetchrow(
        "UPDATE players "
        "SET thirst = LEAST(max_thirst, thirst + $2) "
        "WHERE name = $1 AND thirst < max_thirst "
        "RETURNING hunger, max_hunger, stamina, max_stamina, thirst, max_thirst",
        player_name, amount,
    )
    return _row_to_needs(row) if row else None


async def restore_hunger(player_name: str, amount: int) -> dict | None:
    """Füllt Hunger auf bis max. Returns neuen State, oder None wenn Spieler
    nicht existiert oder Hunger bereits voll war."""
    if amount <= 0:
        return None
    row = await db.pool().fetchrow(
        "UPDATE players "
        "SET hunger = LEAST(max_hunger, hunger + $2) "
        "WHERE name = $1 AND hunger < max_hunger "
        "RETURNING hunger, max_hunger, stamina, max_stamina, thirst, max_thirst",
        player_name, amount,
    )
    return _row_to_needs(row) if row else None


async def restore_stamina(player_name: str, amount: int) -> dict | None:
    """Füllt Stamina auf bis max. Returns neuen State, oder None wenn Spieler
    nicht existiert oder Stamina bereits voll war."""
    if amount <= 0:
        return None
    row = await db.pool().fetchrow(
        "UPDATE players "
        "SET stamina = LEAST(max_stamina, stamina + $2) "
        "WHERE name = $1 AND stamina < max_stamina "
        "RETURNING hunger, max_hunger, stamina, max_stamina, thirst, max_thirst",
        player_name, amount,
    )
    return _row_to_needs(row) if row else None


async def use_stamina(player_name: str, amount: int) -> bool:
    """Versucht Stamina abzuziehen. Returns True bei Erfolg, False wenn nicht
    genug verfügbar oder Spieler nicht existiert."""
    if amount <= 0:
        return True
    row = await db.pool().fetchrow(
        "UPDATE players SET stamina = stamina - $2 "
        "WHERE name = $1 AND stamina >= $2 "
        "RETURNING stamina",
        player_name, amount,
    )
    return row is not None


def attack_stamina_cost(weapon_kind: str | None) -> int:
    """Ausdauer-Kosten eines Angriffs je nach Waffe.
    2H-Nahkampf (physical/finesse, two_handed) = HEAVY; Bogen/Armbrust (ranged),
    1H und Magie-Waffen = LIGHT. Unbewaffnet/unbekannt = LIGHT."""
    try:
        import item_stats
        cfg = item_stats.WEAPON_STATS.get(weapon_kind or "")
    except Exception:
        cfg = None
    if not cfg:
        return STAMINA_ATTACK_LIGHT
    if cfg.get("two_handed") and cfg.get("class") in ("physical", "finesse"):
        return STAMINA_ATTACK_HEAVY
    return STAMINA_ATTACK_LIGHT


# — Worker ————————————————————————————————————————————————————————————————————

DamagePlayerCb = Callable[[str, int], Awaitable[None]]


async def _send_needs(connection_manager, player_name: str, needs: dict) -> None:
    """Schickt den aktuellen Needs-State nur an den jeweiligen Spieler."""
    ws = connection_manager.connections.get(player_name)
    if ws is None:
        return
    try:
        await ws.send_json({
            "type":        "player_needs",
            "hunger":      needs["hunger"],
            "max_hunger":  needs["max_hunger"],
            "stamina":     needs["stamina"],
            "max_stamina": needs["max_stamina"],
            "thirst":      needs["thirst"],
            "max_thirst":  needs["max_thirst"],
        })
    except Exception:
        log.debug("send_needs an %s fehlgeschlagen", player_name, exc_info=True)


async def run(connection_manager, damage_player_cb: DamagePlayerCb) -> None:
    """Hintergrund-Loop: tickt Hunger runter und regeneriert Stamina für alle
    aktiv verbundenen Spieler."""
    log.info("Needs-Worker startet (tick=%ds)", HUNGER_TICK_SECONDS)
    while True:
        try:
            await asyncio.sleep(HUNGER_TICK_SECONDS)

            # Snapshot der aktuell verbundenen Spielernamen
            player_names = list(connection_manager.get_players().keys())
            if not player_names:
                continue

            # Welle 24: Sterbende-Sonne-Disaster verdoppelt Hunger+Thirst-Drain
            drain_mult = 1
            try:
                import disaster_state
                if disaster_state.is_active("dying_sun"):
                    drain_mult = 2
            except Exception:
                pass
            hunger_drain = 1 * drain_mult
            thirst_drain = THIRST_PER_TICK * drain_mult

            for name in player_names:
                # 1) Hunger -hunger_drain, Durst -thirst_drain
                #    (Stamina-Regen läuft im separaten run_stamina-Sekunden-Loop)
                row = await db.pool().fetchrow(
                    "UPDATE players "
                    "SET hunger  = GREATEST(0, hunger - $3), "
                    "    thirst  = GREATEST(0, thirst - $2) "
                    "WHERE name = $1 "
                    "RETURNING hunger, max_hunger, stamina, max_stamina, thirst, max_thirst",
                    name, thirst_drain, hunger_drain,
                )
                if row is None:
                    continue

                needs = _row_to_needs(row)

                # 2) Starvation-Damage bei Hunger == 0
                if needs["hunger"] == 0:
                    try:
                        await damage_player_cb(name, HUNGER_STARVE_HP_DAMAGE)
                    except Exception:
                        log.exception("Starve-Damage fehlgeschlagen für %s", name)
                # 3) Dehydration-Damage bei Durst == 0
                if needs["thirst"] == 0:
                    try:
                        await damage_player_cb(name, THIRST_DEHYDRATE_HP_DAMAGE)
                    except Exception:
                        log.exception("Dehydration-Damage fehlgeschlagen für %s", name)

                # 4) WS-Update an diesen Spieler
                await _send_needs(connection_manager, name, needs)

        except asyncio.CancelledError:
            log.info("Needs-Worker gestoppt")
            raise
        except Exception:
            log.exception("Needs-Worker-Iteration fehlgeschlagen")


async def run_stamina(connection_manager, heal_player_cb=None) -> None:
    """Sekündlicher Loop für Ausdauer: Regeneration (abhängig von Hunger/Durst),
    Sprint-Verbrauch und Bett-Ruhe. Stamina ist INTEGER in der DB; Sub-Integer-
    Raten (0,5/s) werden über einen In-Memory-Akkumulator pro Spieler exakt
    abgebildet."""
    log.info("Stamina-Worker startet (tick=%.0fs)", STAMINA_TICK_SECONDS)
    while True:
        try:
            await asyncio.sleep(STAMINA_TICK_SECONDS)
            for name in list(connection_manager.get_players().keys()):
                row = await db.pool().fetchrow(
                    "SELECT hunger, max_hunger, thirst, max_thirst, "
                    "       stamina, max_stamina FROM players WHERE name = $1",
                    name,
                )
                if row is None:
                    clear_player_state(name)
                    continue
                st = row["stamina"]
                maxst = row["max_stamina"] or 100
                resting = name in _resting
                sprinting = name in _sprinting

                # Rate pro Sekunde bestimmen
                if sprinting and st > 0:
                    rate = -SPRINT_DRAIN_PER_SEC
                elif resting:
                    rate = BED_REST_RESTORE_PER_SEC
                else:
                    hp = row["hunger"] / max(1, row["max_hunger"])
                    tp = row["thirst"] / max(1, row["max_thirst"])
                    supply = min(hp, tp)
                    if supply <= 0:
                        rate = 0.0
                    elif supply < SUPPLY_LOW_PCT:
                        rate = STAMINA_REGEN_LOW
                    elif supply < SUPPLY_FULL_PCT:
                        rate = STAMINA_REGEN_MID
                    else:
                        rate = STAMINA_REGEN_FULL

                # Akkumulieren → ganzzahliges Delta
                acc = _stamina_accum.get(name, 0.0) + rate
                delta = int(acc)            # Richtung 0 (truncate)
                _stamina_accum[name] = acc - delta

                new_st = max(0, min(maxst, st + delta))
                changed = new_st != st
                if changed:
                    await db.pool().execute(
                        "UPDATE players SET stamina = $2 WHERE name = $1",
                        name, new_st,
                    )
                # Akkumulator an den Grenzen zurücksetzen (kein Aufstauen)
                if (new_st >= maxst and rate > 0) or (new_st <= 0 and rate < 0):
                    _stamina_accum[name] = 0.0

                # HP-Heilung während des Schlafens
                if resting and heal_player_cb is not None:
                    try:
                        await heal_player_cb(name, BED_REST_HP_PER_SEC)
                    except Exception:
                        log.debug("Rest-Heal für %s fehlgeschlagen", name, exc_info=True)

                if changed:
                    needs = await get_needs(name)
                    if needs:
                        await _send_needs(connection_manager, name, needs)

                # Sprint automatisch beenden wenn leer
                if sprinting and new_st <= 0:
                    _sprinting.discard(name)
                    ws = connection_manager.connections.get(name)
                    if ws is not None:
                        try:
                            await ws.send_json({
                                "type": "sprint_state", "on": False,
                                "reason": "exhausted",
                            })
                            await ws.send_json({
                                "type": "toast",
                                "text": "🥵 Keine Puste mehr — du fällst in normales Tempo.",
                            })
                        except Exception:
                            pass

                # Ruhe automatisch beenden wenn voll ausgeruht
                if resting and new_st >= maxst:
                    _resting.discard(name)
                    ws = connection_manager.connections.get(name)
                    if ws is not None:
                        try:
                            await ws.send_json({
                                "type": "rest_end", "reason": "rested",
                            })
                            await ws.send_json({
                                "type": "toast",
                                "text": "😴 Vollständig ausgeruht.",
                            })
                        except Exception:
                            pass

        except asyncio.CancelledError:
            log.info("Stamina-Worker gestoppt")
            raise
        except Exception:
            log.exception("Stamina-Worker-Iteration fehlgeschlagen")
