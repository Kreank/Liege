import asyncio
import json
import logging
import os
import random

import combat
import llm
import npc_worker
import storyteller

log = logging.getLogger("liege.event_worker")

EVENT_INTERVAL_SECONDS = int(os.environ.get("EVENT_INTERVAL_SECONDS", "3600"))
EVENT_KIND_HINTS = ["weather", "creature", "discovery", "faction", "natural", "rumor"]

# Storyteller-Modi nach RimWorld-Vorbild (Cassandra/Phoebe/Randy)
STORYTELLER_MODE = os.environ.get("STORYTELLER_MODE", "balanced").lower()
STORYTELLER_PROMPTS = {
    "chill": (
        "Du bist ein gemächlicher Erzähler — die Welt ist friedlich, "
        "Events sind atmosphärisch, selten gefährlich. Kreaturen tauchen selten auf."
    ),
    "balanced": (
        "Du bist ein ausgewogener Erzähler — Mix aus ruhigen, mysteriösen "
        "und gefährlichen Events. Kreaturen kommen regelmäßig."
    ),
    "chaos": (
        "Du bist ein chaotischer Erzähler — überraschende, oft gefährliche Events. "
        "Häufige Kreaturen-Spawns, manchmal Bosse. Spielspieler werden herausgefordert."
    ),
}
# Spawn-Wahrscheinlichkeit Modifier
STORYTELLER_SPAWN_MULT = {"chill": 0.4, "balanced": 1.0, "chaos": 2.0}

def _system_prompt() -> str:
    mode_hint = STORYTELLER_PROMPTS.get(STORYTELLER_MODE, STORYTELLER_PROMPTS["balanced"])
    return (
        "Du bist der Spielleiter einer lebenden Fantasy-Welt namens 'Liege'. "
        f"{mode_hint} "
        "Du erfindest atmosphärische Welt-Events, die für Spieler interessant sind. "
        "Antworte AUSSCHLIESSLICH als gültiges JSON, ohne Kommentar, ohne Markdown."
    )

SYSTEM_PROMPT = _system_prompt()


def _build_prompt(state_summary: str = "", forced_kind: str | None = None,
                  forced_tag: str | None = None) -> str:
    # Storyteller-Director gibt 'kind' und 'tag' vor; LLM macht nur Narrative
    hint = forced_kind or random.choice(EVENT_KIND_HINTS)
    tag_hint = f" mit dem Sub-Thema '{forced_tag}'" if forced_tag else ""
    base = (
        f"Erfinde EIN unerwartetes Welt-Event vom Typ '{hint}'{tag_hint}, das gerade in der Welt passiert.\n"
        "Felder:\n"
        '  "kind": Kategorie ("weather" | "creature" | "discovery" | "faction" | "natural" | "rumor")\n'
        '  "title": kurzer Titel, max 60 Zeichen, Deutsch\n'
        '  "body": 1-2 Sätze Beschreibung, atmosphärisch, Deutsch\n'
        'Beispiel:\n'
        '{"kind": "weather", "title": "Nebel zieht über die Hügel", '
        '"body": "Ein dichter Silbernebel kriecht aus den Tälern und verschluckt jeden Pfad. '
        'Reisende berichten von flüsternden Stimmen darin."}'
    )
    if state_summary:
        base = (
            f"Aktueller Welt-Zustand:\n{state_summary}\n\n"
            "Das Event soll zu diesem Zustand passen (z.B. viele Kreaturen → Wildnis-Unruhe,\n"
            "viele Bauten → wachsende Zivilisation, wenige Spieler → Stille).\n\n" + base
        )
    return base


def world_state_summary(npc_manager, structure_manager, connection_manager) -> str:
    """Knapper Welt-Zustand für den Slow Brain als Kontext."""
    import combat
    players = connection_manager.get_players()
    npcs_all = npc_manager.all()
    creatures = [n for n in npcs_all if n["kind"] in combat.CREATURE_KINDS]
    friendlies = [n for n in npcs_all if n["kind"] not in combat.CREATURE_KINDS]
    structs = structure_manager.all()
    natural = sum(1 for s in structs if s.get("owner") == "system")
    built = sum(1 for s in structs if s.get("owner") not in (None, "system"))

    lines = [
        f"- Aktive Spieler: {len(players)}",
        f"- Wilde Kreaturen: {len(creatures)}"
        + (f" (z.B. {', '.join(set(c['kind'] for c in creatures[:6]))})" if creatures else ""),
        f"- Bewohner (NPCs): {len(friendlies)}",
        f"- Spieler-Bauten: {built}",
        f"- Natürliche Strukturen geladen: {natural}",
    ]
    return "\n".join(lines)


async def _generate_event(state_summary: str = "",
                          forced_kind: str | None = None,
                          forced_tag: str | None = None) -> dict | None:
    raw = await llm.slow_brain(
        _build_prompt(state_summary, forced_kind, forced_tag),
        system=SYSTEM_PROMPT, json_mode=True,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("LLM lieferte kein valides JSON: %s — raw: %s", e, raw[:200])
        return None
    if not all(k in data for k in ("kind", "title", "body")):
        log.warning("Event fehlen Felder: %s", data)
        return None
    return {
        "kind":  str(data["kind"])[:32],
        "title": str(data["title"])[:120],
        "body":  str(data["body"])[:1000],
    }


async def run(event_manager, connection_manager, world=None,
              npc_manager=None, structure_manager=None) -> None:
    """Hintergrund-Loop: alle EVENT_INTERVAL_SECONDS ein Welt-Event.
    Welt-Zustand wird dem Slow Brain als Kontext mitgegeben → KI reagiert
    auf was gerade los ist.
    Zusätzlich: bei 'creature'-Events spawnt der Worker passende Creatures."""
    log.info("Event-Worker startet, Intervall %ss", EVENT_INTERVAL_SECONDS)
    await asyncio.sleep(15)
    while True:
        try:
            state = ""
            ws_state = {}
            if npc_manager and structure_manager:
                state = world_state_summary(npc_manager, structure_manager, connection_manager)
                # Numerischer State für Storyteller
                npcs_all = npc_manager.all()
                creatures = [n for n in npcs_all if n["kind"] in combat.CREATURE_KINDS]
                structs = structure_manager.all()
                ws_state = {
                    "active_players":  len(connection_manager.get_players()),
                    "wealth_score":    sum(1 for s in structs if s.get("owner") not in (None, "system")),
                    "creature_count":  len(creatures),
                    "structure_count": len(structs),
                }
            # Welle 22: Storyteller-Director wählt Event-Typ deterministisch
            forced_kind = None
            forced_tag = None
            tmpl = storyteller.select_event(ws_state)
            if tmpl is not None:
                forced_kind = tmpl["kind"]
                forced_tag = tmpl.get("tag")
                log.info("Storyteller (%s) → kind=%s tag=%s",
                         storyteller.get_mode(), forced_kind, forced_tag)
            ev = await _generate_event(state, forced_kind, forced_tag)
            if ev is not None:
                saved = await event_manager.save(ev["kind"], ev["title"], ev["body"])
                await connection_manager.broadcast({
                    "type":  "event",
                    "event": saved,
                })
                storyteller.mark_event_fired()
                log.info("Event geschickt: %s — %s", saved["kind"], saved["title"])
                if world is not None and npc_manager is not None:
                    await _maybe_spawn_event_creatures(
                        ev, world, npc_manager, connection_manager
                    )
        except asyncio.CancelledError:
            log.info("Event-Worker gestoppt")
            raise
        except Exception:
            log.exception("Event-Worker iteration fehlgeschlagen")
        await asyncio.sleep(EVENT_INTERVAL_SECONDS)


async def _maybe_spawn_event_creatures(event, world, npc_manager, connection_manager) -> None:
    """Wenn das Event Creatures andeutet, spawne welche in der Nähe der Spieler."""
    kind = event["kind"]
    body = event["body"].lower()
    if not connection_manager.get_players():
        return

    # Heuristik: Event-Kind oder Body legt Creature nahe
    spawn_kind = None
    for creature_kind in combat.CREATURE_KINDS:
        if creature_kind in body:
            spawn_kind = creature_kind
            break
    if spawn_kind is None and kind == "creature":
        spawn_kind = random.choice(list(combat.CREATURE_KINDS))
    if spawn_kind is None and random.random() < 0.25 * STORYTELLER_SPAWN_MULT.get(STORYTELLER_MODE, 1.0):
        spawn_kind = random.choice(list(combat.CREATURE_KINDS))
    if spawn_kind is None:
        return

    # 1-3 Creatures spawnen (mehr bei chaos)
    n = random.randint(1, 2)
    if STORYTELLER_MODE == "chaos" and random.random() < 0.3:
        n += random.randint(1, 2)
    log.info("Event-Spawn: %d × %s nahe Spieler", n, spawn_kind)
    for _ in range(n):
        await npc_worker.spawn_one(world, npc_manager, connection_manager, kind=spawn_kind)
