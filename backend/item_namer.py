"""KI-Item-Namer: Slow-Brain generiert Unique-Namen + Flavor für besondere Items.

LLM bekommt ein vollständig gerolltes Item (mit Stats und Affixes) und liefert
NUR `name` und `flavor`. Sie hat KEINE Kontrolle über Stats.
"""
import logging
import db

log = logging.getLogger("liege.item_namer")


ITEM_NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string",
                      "description": "Kurz: warum dieser Name zu Item+Affixes passt (max 2 Sätze)."},
        "name": {"type": "string",
                 "description": "Eigenname für das Item, fantasy-stilig, prägnant (3-6 Worte)."},
        "flavor": {"type": "string",
                   "description": "1-2 Sätze atmosphärischer Lore-Text, lyrisch und ohne Stats zu erwähnen."},
    },
    "required": ["reasoning", "name", "flavor"],
}


_NAMER_SYSTEM = (
    "Du bist ein lyrischer Item-Namer für ein dunkles Fantasy-RPG. "
    "Du erfindest Namen und kurze atmosphärische Texte für Waffen, Rüstungen und Schmuck. "
    "WICHTIG: Du benennst nur das Aussehen und die Aura — niemals Zahlen, Prozente oder Stats. "
    "Antworte AUSSCHLIESSLICH als gültiges JSON gemäß Schema."
)


def _affix_descriptors(affixes: list[dict]) -> str:
    """Beschreibt Affixes textuell für die LLM."""
    desc = []
    for a in affixes:
        kind = a.get("kind", "prefix")
        tier = a.get("tier", 1)
        name_part = a.get("name_part", "")
        # Stat-Themes erkennen (Feuer, Eis, Vampir etc.)
        stats = a.get("stats", {})
        themes = []
        if "fire_damage" in stats or "burn_chance_pct" in stats:    themes.append("Feuer")
        if "ice_damage" in stats or "slow_chance_pct" in stats:     themes.append("Eis")
        if "lightning_damage" in stats:                              themes.append("Blitz")
        if "necrotic_damage" in stats or "lifesteal_pct" in stats:  themes.append("Untot/Vampir")
        if "speed_pct" in stats:                                     themes.append("Geschwindigkeit")
        if "hp_flat" in stats:                                       themes.append("Lebenskraft")
        if "mana_flat" in stats:                                     themes.append("Arkanmacht")
        if "defense_flat" in stats:                                  themes.append("Schutz")
        theme_str = f" [Themen: {', '.join(themes)}]" if themes else ""
        desc.append(f"- {kind} (T{tier}): {name_part}{theme_str}")
    return "\n".join(desc) if desc else "(keine)"


async def generate_name_and_flavor(item_base_kind: str, item_base_name: str,
                                     quality_kind: str, affixes: list[dict],
                                     use_slow_brain: bool = False) -> dict | None:
    """Lässt die LLM einen Namen + Flavor erzeugen.
    use_slow_brain=True für legendäre Items (höhere Qualität), sonst fast brain.
    Returns {name, flavor} oder None bei Fehler."""
    import llm
    affix_text = _affix_descriptors(affixes)
    prompt = f"""Erfinde einen Namen und einen kurzen Lore-Text für folgendes Item:

Basis-Typ: {item_base_kind} (deutscher Name: {item_base_name})
Qualität: {quality_kind}
Affixes (bestimmen Aura/Thema):
{affix_text}

Der Name soll zum Thema der Affixes passen und legendär klingen.
Der Flavor-Text (1-2 Sätze) soll atmosphärisch sein, ohne Stats oder Zahlen zu nennen.
"""
    # Welle 24: Semantic-Cache prüfen
    import llm_cache
    scope = f"item_name:{item_base_kind}:{quality_kind}"
    cached = await llm_cache.lookup(scope, prompt, "lore")
    if cached is not None:
        result = cached
    else:
        if use_slow_brain:
            result = await llm.slow_brain_structured(prompt, ITEM_NAME_SCHEMA, system=_NAMER_SYSTEM)
        else:
            result = await llm.fast_brain_structured(prompt, ITEM_NAME_SCHEMA, system=_NAMER_SYSTEM)
        if result is not None:
            await llm_cache.store(scope, prompt, "lore", result,
                                  llm.SLOW_MODEL if use_slow_brain else llm.FAST_MODEL)
    if result is None:
        return None
    # Validierung
    name = (result.get("name") or "").strip()[:120]
    flavor = (result.get("flavor") or "").strip()[:400]
    if not name:
        return None
    return {"name": name, "flavor": flavor}
