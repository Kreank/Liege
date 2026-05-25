"""Welt-Historie pro Region (Caves-of-Qud / Dwarf-Fortress-Pattern).

Beim ersten Besuch einer Region (8×8-Chunk-Cluster) generiert der Slow-Brain
3-5 historische Events: Götter, Tragödien, Kriege, Helden. Diese werden in
NPC-/Quest-/Dungeon-Prompts als Plot-Essentials durchgereicht.

Region = (rx, ry) = (cx // REGION_SIZE, cy // REGION_SIZE).
"""
import json
import logging
import random

import db

log = logging.getLogger("liege.region_history")

REGION_SIZE = 8   # 8 chunks × 32 tiles = 256-Tile-Region


SCHEMA = """
CREATE TABLE IF NOT EXISTS region_history (
    world_seed   INTEGER NOT NULL,
    region_x     INTEGER NOT NULL,
    region_y     INTEGER NOT NULL,
    history      JSONB NOT NULL,
    region_name  TEXT NULL,
    theme        TEXT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (world_seed, region_x, region_y)
);
"""


REGION_HISTORY_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning":   {"type": "string"},
        "region_name": {"type": "string",
                        "description": "Eigenname der Region (2-3 Worte, fantasy-Stil)."},
        "theme":       {"type": "string",
                        "enum": ["verflucht", "heilig", "vergessen", "krieg",
                                 "wohlhabend", "wild", "geheimnisvoll"],
                        "description": "Übergeordnetes Theme der Region."},
        "events": {
            "type": "array",
            "minItems": 3, "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "year":  {"type": "integer",
                              "description": "Jahr in der Vergangenheit (negativ = lange her)."},
                    "title": {"type": "string"},
                    "body":  {"type": "string",
                              "description": "1-2 Sätze über das Ereignis."},
                },
                "required": ["year", "title", "body"],
            },
        },
    },
    "required": ["reasoning", "region_name", "theme", "events"],
}


_HIST_SYSTEM = (
    "Du bist ein lyrischer Welt-Chronist für ein dunkles Fantasy-RPG. "
    "Du erfindest die Geschichte einer Region: Götter, Tragödien, Helden, Kriege. "
    "Schreibe auf Deutsch, atmosphärisch, prägnant. "
    "Antworte AUSSCHLIESSLICH als gültiges JSON gemäß Schema."
)


def region_for_chunk(cx: int, cy: int) -> tuple[int, int]:
    """Chunk-Koord → Region-Koord."""
    return (cx // REGION_SIZE, cy // REGION_SIZE)


async def get_region_history(world_seed: int, rx: int, ry: int) -> dict | None:
    """Lädt Historie aus DB. Returns None wenn nicht generiert."""
    row = await db.pool().fetchrow(
        "SELECT history, region_name, theme FROM region_history "
        "WHERE world_seed = $1 AND region_x = $2 AND region_y = $3",
        world_seed, rx, ry,
    )
    if row is None:
        return None
    hist = row["history"]
    if isinstance(hist, str):
        hist = json.loads(hist)
    return {
        "events":      hist if isinstance(hist, list) else hist.get("events", []),
        "region_name": row["region_name"],
        "theme":       row["theme"],
    }


async def ensure_region_history(world_seed: int, rx: int, ry: int) -> dict:
    """Lädt vorhandene Historie ODER generiert eine neue. Idempotent."""
    existing = await get_region_history(world_seed, rx, ry)
    if existing:
        return existing
    # Generieren
    try:
        import llm
        prompt = (
            f"Erfinde die Geschichte einer noch unentdeckten Region in der Fantasy-Welt 'Liege'. "
            f"Region-Koordinaten: ({rx}, {ry}) — sei zufällig & kreativ. "
            "Generiere 3-5 historische Ereignisse aus verschiedenen Epochen (negative Jahre für lange her), "
            "einen Region-Namen und ein Theme."
        )
        result = await llm.slow_brain_structured(
            prompt, REGION_HISTORY_SCHEMA, system=_HIST_SYSTEM,
        )
        if result is None:
            raise RuntimeError("llm returned None")
        events = result.get("events", [])
        region_name = result.get("region_name", f"Region {rx},{ry}")
        theme = result.get("theme", "wild")
    except Exception:
        log.exception("Region-Historie-Gen fehlgeschlagen — Fallback")
        events = _fallback_history(rx, ry)
        region_name = f"Vergessene Lande ({rx},{ry})"
        theme = random.choice(["wild", "vergessen", "geheimnisvoll"])

    # Persistieren
    await db.pool().execute(
        "INSERT INTO region_history (world_seed, region_x, region_y, "
        "history, region_name, theme) VALUES ($1, $2, $3, $4, $5, $6) "
        "ON CONFLICT (world_seed, region_x, region_y) DO NOTHING",
        world_seed, rx, ry, json.dumps(events), region_name, theme,
    )
    log.info("Region-Historie generiert: (%d,%d) '%s' [%s] %d events",
             rx, ry, region_name, theme, len(events))
    return {"events": events, "region_name": region_name, "theme": theme}


def _fallback_history(rx: int, ry: int) -> list[dict]:
    """Statischer Fallback wenn LLM nicht antwortet."""
    return [
        {"year": -500, "title": "Großer Wald-Brand",
         "body": "Vor Jahrhunderten verschlang ein Feuer die alten Wälder dieser Region."},
        {"year": -120, "title": "Wandernde Karawane",
         "body": "Reisende kamen, bauten Lager — und verschwanden ohne Spur."},
        {"year":  -20, "title": "Letzter Hüter fortgegangen",
         "body": "Der letzte Wächter dieser Lande verließ den Posten — niemand weiß warum."},
    ]


def format_for_prompt(history: dict, max_events: int = 3) -> str:
    """Formatiert Historie kompakt für System-Prompts (NPCs/Quests/Dungeons)."""
    if not history:
        return ""
    name = history.get("region_name", "diese Region")
    theme = history.get("theme", "")
    events = history.get("events", [])[:max_events]
    lines = [f"Region: {name} ({theme})"]
    for e in events:
        lines.append(f"  • Jahr {e.get('year','?')}: {e.get('title','?')} — {e.get('body','')}")
    return "\n".join(lines)
