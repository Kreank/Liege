"""NPC-Chatter — Welle 26 (2026-05-27) Anti-Wiederholungs-Redesign.

Was sich geändert hat ggü. Welle 20 (Welle-20-canned-only):

1. **Persönlichkeit pro NPC**: 8 Archetypen (cheerful/grumpy/gossip/philosophical
   /anxious/boastful/stoic/curious), beim Spawn random zugewiesen, persistiert
   in `npcs.personality`. Der gleiche Bauer klingt immer aus seinem Archetyp.

2. **LLM-Hybrid via Ollama**: bei Cache-Miss generiert das Fast-Brain frische
   2-4-Wechsel-Konversationen und speichert sie in `npc_chatter_cache`. Bei
   LLM-Fail Fallback auf canned Pool.

3. **Cache + Recency**: Cache-Lookup mit Schlüssel `<kind>:<archetype>:<phase>`.
   Pro NPC werden die letzten 3 gesagten Lines getrackt → keine Wiederholung in
   Folge.

4. **Konversations-Flow**: 2-4 abwechselnde Lines (Initiator → Responder →
   Initiator → optional Responder) statt nur 1 Paar. Frontend schedult Bubbles
   mit ~2-2.5s Delays.

5. **Staggering**: globaler Throttle (max 1 Konversation pro 5s) + initial
   random Cooldown beim Worker-Start damit nicht alle gleichzeitig feuern.

6. **Event-Reactive**: optionaler Pool aus `event_chatter` (z.B. nach Boss-
   Spawn) wird mit 25% Chance bevorzugt gepickt — NPCs reden über Welt-Events.
"""
import json
import logging
import random
import time
from typing import Optional

import combat
import db
import llm
import time_system

log = logging.getLogger("liege.npc_chatter")

SPEECH_CHANCE_PER_TICK   = 0.04
SPEECH_COOLDOWN_PER_NPC  = 90.0     # Sekunden
GLOBAL_CONVERSATION_THROTTLE_S = 5.0  # max 1 Konversation pro 5s server-weit
INITIAL_STAGGER_MAX_S    = 180.0    # erstes Speech 0-180s nach NPC-Spawn

CACHE_MIN_POOL_SIZE      = 6        # weniger → trigger LLM-Refill
CACHE_MAX_POOL_SIZE      = 24       # cap pro key
LLM_REFILL_BATCH         = 4        # wieviele neue Konversationen pro LLM-Call
EVENT_CHATTER_PICK_CHANCE = 0.25    # Chance Event-Line statt regulärer Cache-Line

# Per-NPC In-Memory State (nicht persistiert)
_last_speech:        dict[int, float] = {}     # npc_id → letzter speech unix-time
_recent_lines:       dict[int, list[str]] = {} # npc_id → letzte 3 lines (Anti-Repeat)
_in_conversation:    set[int] = set()           # npc_ids gerade in laufender Konversation
_global_last_chat:   float = 0.0                # letzte Konversation server-weit
_llm_refill_pending: set[str] = set()           # cache_keys mit laufender LLM-Generation

# Archetypen
PERSONALITIES = [
    "cheerful", "grumpy", "gossip", "philosophical",
    "anxious", "boastful", "stoic", "curious",
]
PERSONALITY_DESCRIPTIONS = {
    "cheerful":      "fröhlich, optimistisch, lacht viel, sieht das Gute",
    "grumpy":        "mürrisch, brummig, beschwert sich gerne, sarkastisch",
    "gossip":        "klatschsüchtig, will alles wissen, erzählt Gerüchte",
    "philosophical": "nachdenklich, redet über Sinn und Schicksal, Zitate",
    "anxious":       "ängstlich, sieht überall Gefahr, sorgt sich um andere",
    "boastful":      "prahlerisch, übertreibt eigene Taten, vergleicht",
    "stoic":         "wortkarg, ruhig, sachlich, kurz und knapp",
    "curious":       "neugierig, stellt viele Fragen, will Neues erfahren",
}


def assign_personality() -> str:
    """Wird beim NPC-Spawn aufgerufen. Random Archetyp."""
    return random.choice(PERSONALITIES)


# ─── Canned Fallback-Pool (klein, nur als Ollama-Down-Backup) ──────────────
CANNED_FALLBACK = [
    ["Hallo.", "Tag."],
    ["Heute alles in Ordnung?", "Soweit ja."],
    ["Hast du was Neues gehört?", "Nur Gerüchte."],
    ["Die Zeiten ändern sich.", "Stimmt wohl."],
]


# ─── Cache-Management ──────────────────────────────────────────────────────

def _cache_key(kind: str, personality: str, phase: str) -> str:
    return f"{kind}:{personality}:{phase}"


async def _load_cache_pool(cache_key: str) -> list[list[str]]:
    """Lädt den Pool aus DB. Leer wenn nicht da."""
    try:
        row = await db.pool().fetchrow(
            "SELECT lines FROM npc_chatter_cache WHERE cache_key = $1", cache_key)
    except Exception:
        return []
    if not row:
        return []
    raw = row["lines"]
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw or []


async def _save_cache_pool(cache_key: str, pool: list[list[str]]) -> None:
    try:
        await db.pool().execute(
            "INSERT INTO npc_chatter_cache (cache_key, lines, last_used_at) "
            "VALUES ($1, $2::jsonb, NOW()) "
            "ON CONFLICT (cache_key) DO UPDATE SET "
            "  lines = $2::jsonb, last_used_at = NOW()",
            cache_key, json.dumps(pool),
        )
    except Exception:
        log.exception("Chatter-Cache speichern fehlgeschlagen für %s", cache_key)


async def _llm_generate_conversations(
    kind: str, personality: str, phase: str, recent_events: list[str],
) -> list[list[str]]:
    """Ollama-Call: generiert LLM_REFILL_BATCH frische Konversationen.
    Jede Konversation ist eine Liste von 2-4 Lines (abwechselnd)."""
    persona_desc = PERSONALITY_DESCRIPTIONS.get(personality, "neutral")
    phase_de = {"morning": "morgens", "day": "tagsüber",
                "evening": "abends", "night": "nachts"}.get(phase, "tagsüber")
    events_hint = ""
    if recent_events:
        events_hint = ("\n\nKürzliche Welt-Ereignisse (DARFST du erwähnen):\n  - "
                       + "\n  - ".join(recent_events[:3]))
    system_prompt = (
        "Du erfindest kurze, lebendige Konversationen zwischen mittelalterlichen "
        "Dorfbewohnern für ein Fantasy-Spiel. Halte sie kurz (max 8 Wörter pro Zeile) "
        "und alltäglich. Keine Story-Bögen, keine Quests, einfach Plauderei. "
        "Antwort auf Deutsch.")
    prompt = (
        f"NPC-Beruf: {kind}\n"
        f"Persönlichkeit: {personality} ({persona_desc})\n"
        f"Tageszeit: {phase_de}"
        f"{events_hint}\n\n"
        f"Generiere {LLM_REFILL_BATCH} verschiedene, kurze Konversationen zwischen "
        f"diesem NPC und einem anderen Dorfbewohner. Jede Konversation hat 2-4 "
        f"abwechselnde Lines. Der Stil muss zur Persönlichkeit passen."
    )
    schema = {
        "type": "object",
        "properties": {
            "conversations": {
                "type": "array",
                "minItems": LLM_REFILL_BATCH,
                "maxItems": LLM_REFILL_BATCH,
                "items": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 4,
                    "items": {"type": "string", "minLength": 1, "maxLength": 80},
                },
            },
        },
        "required": ["conversations"],
    }
    try:
        result = await llm.fast_brain_structured(prompt, schema, system=system_prompt)
        if result and isinstance(result.get("conversations"), list):
            out = []
            for conv in result["conversations"]:
                if isinstance(conv, list) and 2 <= len(conv) <= 4:
                    out.append([str(line)[:80] for line in conv])
            return out
    except Exception:
        log.exception("LLM-Chatter-Generation fehlgeschlagen für %s", personality)
    return []


async def _ensure_pool_filled(cache_key: str, kind: str, personality: str,
                                phase: str) -> list[list[str]]:
    """Lädt Cache-Pool. Wenn unter Minimum: triggert LLM-Refill ASYNC und
    returnt was da ist (möglicherweise leer → Fallback)."""
    pool = await _load_cache_pool(cache_key)
    if len(pool) < CACHE_MIN_POOL_SIZE and cache_key not in _llm_refill_pending:
        _llm_refill_pending.add(cache_key)
        try:
            # Recent Events optional — kommt aus events.recent()
            events_strs: list[str] = []
            try:
                import events as _ev_mod
                recent = await _ev_mod.recent(3)
                events_strs = [e.get("title") or e.get("body") or "" for e in recent if e]
                events_strs = [s for s in events_strs if s]
            except Exception:
                pass
            new_convos = await _llm_generate_conversations(
                kind, personality, phase, events_strs)
            if new_convos:
                pool = (pool + new_convos)[-CACHE_MAX_POOL_SIZE:]
                await _save_cache_pool(cache_key, pool)
        finally:
            _llm_refill_pending.discard(cache_key)
    return pool


async def _pick_conversation(npc: dict, partner: dict, phase: str) -> Optional[list[str]]:
    """Wählt eine Konversation für (npc, partner). Bevorzugt Event-Chatter
    der Region (25% Chance), sonst Cache-Pool, sonst canned fallback. Recency-
    Filter: keine Line die einer der beiden in den letzten 3 gesagt hat."""
    # Event-Chatter check (Region des NPCs)
    if random.random() < EVENT_CHATTER_PICK_CHANCE:
        evt_conv = await _pick_event_chatter(npc["x"], npc["y"])
        if evt_conv:
            return evt_conv

    kind, persona = npc["kind"], npc.get("personality") or "stoic"
    cache_key = _cache_key(kind, persona, phase)
    pool = await _ensure_pool_filled(cache_key, kind, persona, phase)
    if not pool:
        return random.choice(CANNED_FALLBACK)
    # Recency-Filter: nimm eine Konversation deren erste Line in letzten 3
    # von beiden NPCs nicht vorkommt.
    recent_a = set(_recent_lines.get(npc["id"], []))
    recent_b = set(_recent_lines.get(partner["id"], []))
    candidates = [
        conv for conv in pool
        if conv and conv[0] not in recent_a and (
            len(conv) < 2 or conv[1] not in recent_b
        )
    ]
    if not candidates:
        # Recency-Filter hat alles gefiltert → trotzdem random aus full pool
        candidates = pool
    return random.choice(candidates)


async def _pick_event_chatter(x: int, y: int) -> Optional[list[str]]:
    """Sucht ein aktives event_chatter für die Region in der (x,y) liegt."""
    try:
        import region_difficulty
        rx, ry = region_difficulty.region_for_world(x, y)
    except Exception:
        return None
    try:
        rows = await db.pool().fetch(
            "SELECT lines FROM event_chatter "
            "WHERE region_x = $1 AND region_y = $2 AND expires_at > NOW()",
            rx, ry,
        )
    except Exception:
        return None
    convs: list[list[str]] = []
    for r in rows:
        raw = r["lines"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, list):
            for conv in raw:
                if isinstance(conv, list) and 2 <= len(conv) <= 4:
                    convs.append([str(s)[:80] for s in conv])
    return random.choice(convs) if convs else None


async def set_event_chatter(region_x: int, region_y: int, event_kind: str,
                             lines: list[list[str]], duration_s: int = 7200) -> None:
    """Storyteller-Hook: schreibt Event-spezifische Konversationen für die Region.
    Default-TTL 2h (7200s)."""
    try:
        await db.pool().execute(
            "INSERT INTO event_chatter (region_x, region_y, event_kind, lines, expires_at) "
            "VALUES ($1, $2, $3, $4::jsonb, NOW() + ($5 || ' seconds')::INTERVAL)",
            region_x, region_y, event_kind, json.dumps(lines), str(int(duration_s)),
        )
        log.info("Event-Chatter gesetzt: region=(%d,%d) kind=%s %d convos %ds",
                 region_x, region_y, event_kind, len(lines), duration_s)
    except Exception:
        log.exception("Event-Chatter speichern fehlgeschlagen")


# ─── Cooldown + Throttle ───────────────────────────────────────────────────

def is_on_cooldown(npc_id: int) -> bool:
    now = time.monotonic()
    last = _last_speech.get(npc_id)
    if last is None:
        # Erster Speech-Versuch: random initial stagger 0-180s damit nicht alle
        # gleichzeitig feuern. Wir setzen einen virtuellen "letzten Speech".
        _last_speech[npc_id] = now - random.uniform(0, INITIAL_STAGGER_MAX_S)
        return (now - _last_speech[npc_id]) < SPEECH_COOLDOWN_PER_NPC
    return (now - last) < SPEECH_COOLDOWN_PER_NPC


def mark_spoke(npc_id: int) -> None:
    _last_speech[npc_id] = time.monotonic()


def _record_recent_line(npc_id: int, line: str) -> None:
    rec = _recent_lines.setdefault(npc_id, [])
    rec.append(line)
    if len(rec) > 3:
        del rec[0]


def _global_throttle_ok() -> bool:
    global _global_last_chat
    now = time.monotonic()
    if now - _global_last_chat < GLOBAL_CONVERSATION_THROTTLE_S:
        return False
    _global_last_chat = now
    return True


# ─── Partner-Finding ───────────────────────────────────────────────────────

def find_chatter_partner(npc: dict, npc_manager) -> dict | None:
    """Sucht einen friendly NPC der direkt adjacent ist und nicht busy."""
    if is_on_cooldown(npc["id"]):
        return None
    if npc["id"] in _in_conversation:
        return None
    if npc["kind"] in combat.CREATURE_KINDS:
        return None
    nx, ny = npc["x"], npc["y"]
    for other in npc_manager.all():
        if other["id"] == npc["id"]:
            continue
        if other["id"] in _in_conversation:
            continue
        if other["kind"] in combat.CREATURE_KINDS:
            continue
        d = abs(other["x"] - nx) + abs(other["y"] - ny)
        if d == 1 and not is_on_cooldown(other["id"]):
            return other
    return None


# ─── Konversations-Flow ────────────────────────────────────────────────────

async def maybe_chat(npc: dict, npc_manager, connection_manager) -> bool:
    """Pro NPC-Tick: chance auf Sprechblase. Returns True wenn ein Dialog
    abgefeuert wurde."""
    if random.random() >= SPEECH_CHANCE_PER_TICK:
        return False
    if not _global_throttle_ok():
        return False
    partner = find_chatter_partner(npc, npc_manager)
    if partner is None:
        return False
    phase = time_system.clock.phase()
    conv = await _pick_conversation(npc, partner, phase)
    if not conv or len(conv) < 2:
        return False
    # Beide NPCs sind während der ganzen Konversation "busy"
    _in_conversation.add(npc["id"])
    _in_conversation.add(partner["id"])
    mark_spoke(npc["id"])
    mark_spoke(partner["id"])
    speakers = [npc, partner]
    # Lines abwechselnd Initiator/Responder mit ~2-2.5s Delay pro Line
    delay = 0
    for i, line in enumerate(conv):
        speaker = speakers[i % 2]
        await connection_manager.broadcast({
            "type":     "npc_speech",
            "npc_id":   speaker["id"],
            "text":     line,
            "delay_ms": delay,
        })
        _record_recent_line(speaker["id"], line)
        # Delay zur nächsten Line: 2.2s + Lese-Variabilität
        delay += 2200 + random.randint(0, 400)

    # Conversation-End: nach allen Lines + Letzter-Bubble-Display (6s) sind beide
    # wieder verfügbar. Wir markieren das via einen kleinen async task der
    # _in_conversation discardiert.
    total_duration_ms = delay + 6000
    import asyncio
    async def _release():
        await asyncio.sleep(total_duration_ms / 1000.0)
        _in_conversation.discard(npc["id"])
        _in_conversation.discard(partner["id"])
    asyncio.create_task(_release())

    log.debug("NPC-conv: %s(%s) ↔ %s(%s) %d-line phase=%s",
              npc["kind"], npc.get("personality"),
              partner["kind"], partner.get("personality"),
              len(conv), phase)
    return True


# ─── Helper für npc_manager.create (Personality zuweisen) ─────────────────

async def assign_personality_to_existing_npcs() -> int:
    """One-shot beim Server-Start: friendly NPCs ohne personality kriegen einen."""
    try:
        rows = await db.pool().fetch(
            "SELECT id FROM npcs WHERE personality IS NULL"
        )
    except Exception:
        return 0
    n = 0
    for r in rows:
        try:
            await db.pool().execute(
                "UPDATE npcs SET personality = $1 WHERE id = $2",
                assign_personality(), r["id"],
            )
            n += 1
        except Exception:
            pass
    if n > 0:
        log.info("Personality zugewiesen für %d existierende NPCs", n)
    return n
