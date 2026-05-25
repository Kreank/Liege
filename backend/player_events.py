import asyncio
import json
import logging
import time

import llm

log = logging.getLogger("liege.player_events")

# Welche Struktur-Typen lösen ein KI-Event aus
TRIGGER_TYPES = {"campfire", "marker"}

# Cooldown pro Spieler in Sekunden — kein Event-Spam wenn jemand viel baut
COOLDOWN_SECONDS = 60

# Mappings für lesbare Kontext-Beschreibungen
STRUCT_NAMES = {
    "campfire": "ein Lagerfeuer",
    "marker":   "einen Wegweiser",
    "wall":     "eine Mauer",
    "floor":    "einen Bodenbelag",
}
TILE_NAMES = ["Wasser", "Strand", "Grasland", "Wald", "Gebirge"]

SYSTEM_PROMPT = (
    "Du bist der Spielleiter einer lebenden Fantasy-Welt namens 'Liege'. "
    "Wenn ein Reisender eine Handlung in der Welt vollzieht, beschreibst du eine "
    "kurze atmosphärische Konsequenz oder Beobachtung. "
    "Antworte AUSSCHLIESSLICH als gültiges JSON, ohne Kommentar, ohne Markdown."
)

_cooldown: dict[str, float] = {}


def can_trigger(player_name: str, struct_type: str) -> bool:
    if struct_type not in TRIGGER_TYPES:
        return False
    last = _cooldown.get(player_name, 0.0)
    return (time.time() - last) >= COOLDOWN_SECONDS


def mark_triggered(player_name: str) -> None:
    _cooldown[player_name] = time.time()


def _build_prompt(player_name: str, struct_type: str, x: int, y: int, tile_id: int) -> str:
    struct = STRUCT_NAMES.get(struct_type, struct_type)
    tile = TILE_NAMES[tile_id] if 0 <= tile_id < len(TILE_NAMES) else "unbekanntem Gelände"
    return (
        f'Der Reisende "{player_name}" hat soeben {struct} bei Position ({x}, {y}) auf {tile} platziert.\n'
        "Erfinde EIN kurzes Welt-Event als atmosphärische Reaktion oder Folge. Maximal 2 Sätze. Deutsch.\n"
        "Felder im JSON:\n"
        '  "kind": Kategorie ("rumor" | "discovery" | "faction" | "natural")\n'
        '  "title": max 60 Zeichen, Deutsch\n'
        '  "body": 1-2 Sätze, atmosphärisch, Deutsch, kann den Spielernamen erwähnen\n'
        'Beispiel:\n'
        '{"kind": "rumor", "title": "Ein Feuer im Grasland", '
        '"body": "Reisende erzählen sich, dass Ana am Hügelrand ein Lager aufgeschlagen hat. '
        'Mehr als ein Schatten beobachtet das Lodern."}'
    )


async def trigger(player_name: str, struct_type: str, x: int, y: int, tile_id: int,
                  event_manager, connection_manager) -> None:
    """Fire-and-forget Task: generiert ein Event und broadcastet es."""
    try:
        raw = await llm.slow_brain(
            _build_prompt(player_name, struct_type, x, y, tile_id),
            system=SYSTEM_PROMPT,
            json_mode=True,
        )
        data = json.loads(raw)
        if not all(k in data for k in ("kind", "title", "body")):
            log.warning("Player-Event hat fehlende Felder: %s", data)
            return
        saved = await event_manager.save(
            str(data["kind"])[:32],
            str(data["title"])[:120],
            str(data["body"])[:1000],
        )
        await connection_manager.broadcast({"type": "event", "event": saved})
        log.info("Player-Event geschickt (%s): %s", player_name, saved["title"])
    except json.JSONDecodeError as e:
        log.warning("Player-Event LLM lieferte kein JSON: %s — raw: %s", e, raw[:200] if 'raw' in dir() else '')
    except Exception:
        log.exception("Player-Event Trigger fehlgeschlagen")
