"""Geldbeutel-Währung (Welle 33).

Eine Spieler-Geldbörse statt Münz-Items im Inventar. Intern wird ALLES in
Kupfer (kleinste Einheit) gerechnet und in players.wallet_copper gespeichert.

Umrechnung (User-Entscheidung 2026-05-29):
    100 Kupfer = 1 Silber
    100 Silber = 1 Gold       →  1 Gold = 10.000 Kupfer

`gold_ore` ist KEINE Währung mehr — es ist wieder ein normales Erz (verkaufbar
beim Händler). Nur copper/silver/gold_coin sind Geld und existieren nicht mehr
als Items, sondern fließen direkt in den Geldbeutel.
"""

import logging

import db

log = logging.getLogger("liege.currency")

COPPER_PER_SILVER = 100
COPPER_PER_GOLD = 100 * COPPER_PER_SILVER  # 10.000

# Münz-Item-Kinds → Wert in Kupfer. Quelle für Loot/Quest/Truhen-Mapping.
COIN_VALUES = {
    "copper_coin": 1,
    "silver_coin": COPPER_PER_SILVER,
    "gold_coin":   COPPER_PER_GOLD,
}


def is_currency(kind: str) -> bool:
    return kind in COIN_VALUES


def coin_to_copper(kind: str, count: int = 1) -> int:
    return COIN_VALUES.get(kind, 0) * int(count)


def split(copper: int) -> tuple[int, int, int]:
    """Kupfer-Gesamtbetrag → (gold, silber, kupfer)."""
    copper = max(0, int(copper))
    g = copper // COPPER_PER_GOLD
    s = (copper % COPPER_PER_GOLD) // COPPER_PER_SILVER
    c = copper % COPPER_PER_SILVER
    return g, s, c


def format(copper: int) -> str:
    """'1g 23s 45k' — leere höhere Stellen werden weggelassen."""
    g, s, c = split(copper)
    parts = []
    if g:
        parts.append(f"{g}g")
    if s or g:
        parts.append(f"{s}s")
    parts.append(f"{c}k")
    return " ".join(parts)


async def balance(player_name: str) -> int:
    val = await db.pool().fetchval(
        "SELECT wallet_copper FROM players WHERE name = $1", player_name,
    )
    return int(val or 0)


async def add(player_name: str, copper: int) -> int:
    """Schreibt copper gut (copper kann negativ sein → nutze besser spend()).
    Returnt neuen Kontostand."""
    copper = int(copper)
    if copper == 0:
        return await balance(player_name)
    row = await db.pool().fetchrow(
        "UPDATE players SET wallet_copper = GREATEST(0, wallet_copper + $2) "
        "WHERE name = $1 RETURNING wallet_copper",
        player_name, copper,
    )
    return int(row["wallet_copper"]) if row else 0


async def add_coin(player_name: str, kind: str, count: int = 1) -> int:
    """Gutschrift anhand eines Münz-Kinds (copper/silver/gold_coin)."""
    return await add(player_name, coin_to_copper(kind, count))


async def spend(player_name: str, copper: int) -> bool:
    """Versucht copper abzubuchen. True wenn genug Guthaben, sonst False
    (atomar — bucht nur wenn der Kontostand reicht)."""
    copper = int(copper)
    if copper <= 0:
        return True
    row = await db.pool().fetchrow(
        "UPDATE players SET wallet_copper = wallet_copper - $2 "
        "WHERE name = $1 AND wallet_copper >= $2 RETURNING wallet_copper",
        player_name, copper,
    )
    return row is not None
