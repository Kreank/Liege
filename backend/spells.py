"""Spell-Definitionen — zwei Schulen (Heiler, Magier) mit je 5 Spells.

Jeder Spell hat Cast-Time, Mana-Cost, Cooldown und einen skill_req auf den
'magic'-Skill. Effekte werden über vorhandene Mechaniken (status_effects,
combat.damage, heal) angewendet.

Die Sprite-Icons referenzieren Frames aus den FX-Anims unter
assets/animations/professional/combat_magic/ — jeder Spell setzt seinen
icon_path direkt auf einen passenden Frame.
"""

# target_kind:
#   self    — wirkt auf den Caster (Heal, Mana Shield)
#   single  — wirkt auf ein gewähltes Ziel (NPC oder Spieler)
#   aoe     — wirkt auf alle in radius um Ziel-Tile
#   group   — wirkt auf alle Spieler in radius um Caster
#   ground  — wirkt auf eine angeklickte Tile (Meteor)
#
# effect.kind:
#   heal           — heilt HP (amount)
#   damage         — direkter Schaden (amount, damage_type)
#   status         — wendet Status-Effekt an (effect, magnitude, duration)
#   resurrect      — heilt + setzt down-Status zurück
#
# Ein Spell darf mehrere Effekte haben (effects-Liste).

SPELLS = {
    # ─── Heiler-Schule ─────────────────────────────────────────────────────────
    "lesser_heal": {
        "name":         "Schwache Heilung",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/heal_pulse/heal_pulse_01.png",
        "fx_anim":      "heal_glow",
        "target_kind":  "self",
        "cast_time_ms": 1000,
        "mana_cost":    8,
        "cooldown_ms":  1500,
        "skill_req":    1,
        "threat":       8,
        "effects": [
            {"kind": "heal", "amount": 18},
        ],
        "description":  "Kleine Sofortheilung. Geringer Mana-Verbrauch.",
    },
    "heal": {
        "name":         "Heilung",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/heal_pulse/heal_pulse_08.png",
        "fx_anim":      "heal_glow",
        "target_kind":  "self",
        "cast_time_ms": 2000,
        "mana_cost":    18,
        "cooldown_ms":  3000,
        "skill_req":    4,
        "threat":       18,
        "effects": [
            {"kind": "heal", "amount": 45},
        ],
        "description":  "Mittelstarke Heilung. Längerer Cast.",
    },
    "group_heal": {
        "name":         "Gruppenheilung",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/heal_pulse/heal_pulse_10.png",
        "fx_anim":      "magic_circle",
        "target_kind":  "group",
        "radius":       6,
        "cast_time_ms": 3000,
        "mana_cost":    35,
        "cooldown_ms":  12000,
        "skill_req":    8,
        "threat":       40,
        "effects": [
            {"kind": "heal", "amount": 30},
        ],
        "description":  "Heilt dich und alle Spieler im Umkreis von 6 Feldern.",
    },
    "mana_shield": {
        "name":         "Mana-Schild",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/magic_circle/magic_circle_06.png",
        "fx_anim":      "magic_circle",
        "target_kind":  "self",
        "cast_time_ms": 1500,
        "mana_cost":    20,
        "cooldown_ms":  20000,
        "skill_req":    5,
        "threat":       5,
        "effects": [
            # Magnitude 50 == 50% Damage-Reduktion (siehe status_effects.damage_reduction_for)
            {"kind": "status", "effect": "shielded", "magnitude": 50, "duration": 20},
        ],
        "description":  "Reduziert eingehenden Schaden um 50 % für 20 s.",
    },
    "resurrection": {
        "name":         "Wiederbelebung",
        "school":       "healer",
        "icon_path":    "/assets/animations/professional/combat_magic/holy_shield_aura/holy_shield_aura_04.png",
        "fx_anim":      "heal_glow",
        "target_kind":  "downed",      # zielt auf einen nahen, gefallenen Spieler
        "range":        4,
        "cast_time_ms": 4000,
        "mana_cost":    60,
        "cooldown_ms":  60000,
        "skill_req":    12,
        "threat":       0,
        "effects": [
            {"kind": "revive"},        # Sonderfall: hebt Down-Status auf
            {"kind": "status", "effect": "blessed", "magnitude": 5, "duration": 30},
        ],
        "description":  "Belebt einen gefallenen Mitspieler in der Nähe wieder (max 4 Felder).",
    },

    # ─── Magier-Schule ─────────────────────────────────────────────────────────
    "magic_missile": {
        "name":         "Magisches Geschoss",
        "school":       "mage",
        "icon_path":    "/assets/animations/professional/combat_magic/magic_circle/magic_circle_04.png",
        "fx_anim":      "hit_spark",
        "target_kind":  "single",
        "range":        7,
        "cast_time_ms": 0,            # Instant
        "mana_cost":    6,
        "cooldown_ms":  1200,
        "skill_req":    1,
        "effects": [
            {"kind": "damage", "amount": 14, "damage_type": "magic"},
        ],
        "description":  "Instant-Geschoss. Geringer Schaden, kein Cast.",
    },
    "fireball": {
        "name":         "Feuerball",
        "school":       "mage",
        "icon_path":    "/assets/animations/professional/combat_magic/fireball_explosion/fireball_explosion_06.png",
        "fx_anim":      "fireball_explosion",
        "target_kind":  "aoe",
        "range":        8,
        "radius":       2,
        "cast_time_ms": 1500,
        "mana_cost":    18,
        "cooldown_ms":  4000,
        "skill_req":    4,
        "effects": [
            {"kind": "damage", "amount": 30, "damage_type": "fire"},
            {"kind": "status", "effect": "burning", "magnitude": 4, "duration": 9},
        ],
        "description":  "AoE-Schaden + brennende Wunden (DoT).",
    },
    "frostbolt": {
        "name":         "Frostpfeil",
        "school":       "mage",
        "icon_path":    "/assets/animations/spells/ice_shard_projectile.png",
        "fx_anim":      "ice_shard",
        "target_kind":  "single",
        "range":        7,
        "cast_time_ms": 1200,
        "mana_cost":    12,
        "cooldown_ms":  2500,
        "skill_req":    3,
        "effects": [
            {"kind": "damage", "amount": 22, "damage_type": "ice"},
            {"kind": "status", "effect": "slowed", "magnitude": 50, "duration": 4},
        ],
        "description":  "Eisschaden + verlangsamt das Ziel um 50 % für 4 s.",
    },
    "lightning_bolt": {
        "name":         "Blitzschlag",
        "school":       "mage",
        "icon_path":    "/assets/animations/spells/lightning_bolt_projectile.png",
        "fx_anim":      "lightning_strike",
        "target_kind":  "single",
        "range":        9,
        "cast_time_ms": 1800,
        "mana_cost":    22,
        "cooldown_ms":  5000,
        "skill_req":    6,
        "effects": [
            {"kind": "damage", "amount": 42, "damage_type": "lightning"},
        ],
        "description":  "Hoher Einzelschaden auf große Distanz.",
    },
    "meteor": {
        "name":         "Meteor",
        "school":       "mage",
        "icon_path":    "/assets/animations/professional/combat_magic/fireball_explosion/fireball_explosion_12.png",
        "fx_anim":      "fireball_explosion",
        "target_kind":  "ground",
        "range":        10,
        "radius":       4,
        "cast_time_ms": 4500,
        "mana_cost":    60,
        "cooldown_ms":  45000,
        "skill_req":    14,
        "effects": [
            {"kind": "damage", "amount": 90, "damage_type": "fire"},
            {"kind": "status", "effect": "burning", "magnitude": 8, "duration": 12},
        ],
        "description":  "Ultimativer Flächenschaden. Lange Cast-Zeit, lange Abklingzeit.",
    },
}


def get(spell_id: str) -> dict | None:
    return SPELLS.get(spell_id)


def all_ids() -> list[str]:
    return list(SPELLS.keys())


def all_for_school(school: str) -> list[str]:
    return [sid for sid, s in SPELLS.items() if s["school"] == school]


# ─── Spell-Books — Items zum Spell-Lernen ────────────────────────────────────
# spell_book_<id> Items werden in ITEM_KINDS (items.py) ergänzt; beim use wird
# der zugehörige Spell gelernt.

def book_to_spell_id(book_kind: str) -> str | None:
    """spell_book_fireball → 'fireball'."""
    if not book_kind.startswith("spell_book_"):
        return None
    return book_kind[len("spell_book_"):]


async def try_unlock_by_level(player_name: str, magic_level: int) -> list[str]:
    """Schaltet alle Spells frei, deren skill_req der Spieler erreicht hat.
    Returns Liste der NEU gelernten spell_ids."""
    import db
    eligible = [
        sid for sid, s in SPELLS.items()
        if magic_level >= int(s.get("skill_req", 0))
    ]
    if not eligible:
        return []
    existing_rows = await db.pool().fetch(
        "SELECT spell_kind FROM learned_spells WHERE player_name = $1",
        player_name,
    )
    existing = {r["spell_kind"] for r in existing_rows}
    new_ones = [sid for sid in eligible if sid not in existing]
    for sid in new_ones:
        await db.pool().execute(
            "INSERT INTO learned_spells (player_name, spell_kind) "
            "VALUES ($1, $2) ON CONFLICT DO NOTHING",
            player_name, sid,
        )
    return new_ones
