"""Handels-Logik. Welle 33: Bezahlt wird aus dem Geldbeutel (currency.py),
Preise sind in KUPFER. gold_ore ist wieder ein normales (verkaufbares) Erz.

Warenwert-Hinweis: Diese Zahlen sind 1:1 aus dem alten gold_ore-System
übernommen (jetzt als Kupfer interpretiert). Das eigentliche Preis-Balancing
über die drei Münz-Stufen kommt in einem separaten Warenwert-Pass."""

import random

# Marktpreise pro Item-Kind in KUPFER. Höhere Werte = wertvoller.
ITEM_VALUES = {
    # Resources
    "wood":         2,
    "stone":        3,
    "bone":         3,
    "cloth":        5,
    "leather":      8,
    "herb":         4,
    "iron_ore":     8,
    "silver_ore":   15,
    "gold_ore":     30,   # Welle 33: normales Erz, kein Geld mehr
    "mythril_ore":  40,
    "steel_ingot":  12,
    "crystal":      25,
    # Consumables
    "health_potion": 20,
    "mana_potion":   18,
    # Equipment
    "sword":      80,
    "axe":        90,
    "bow":        70,
    "staff":      60,
    "helmet":     50,
    "chestplate": 100,
    "shield":     70,
    "boots":      40,
    "ring":       60,
    "amulet":     80,
    # Magic
    "scroll":      30,
    "rune_stone":  100,
    "spell_book":  150,
}

MERCHANT_POOL = [
    "wood", "stone", "iron_ore", "silver_ore", "herb", "cloth", "leather", "bone",
    "health_potion", "mana_potion",
    "sword", "axe", "bow", "staff", "helmet", "shield", "boots", "ring",
    "scroll", "rune_stone",
]


def buy_price(kind: str) -> int:
    return max(1, ITEM_VALUES.get(kind, 10))


def sell_price(kind: str) -> int:
    return max(1, ITEM_VALUES.get(kind, 10) // 2)


def generate_offerings(n: int = 8) -> list[str]:
    return random.sample(MERCHANT_POOL, min(n, len(MERCHANT_POOL)))
