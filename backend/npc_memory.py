"""NPC Long-Term-Memory (Generative-Agents + MemGPT-Hybrid).

3-Schichten-Architektur:
1. Persona-Card (immutable): wer der NPC ist, immer im Context
2. Short-Term: letzte 8-10 Turns vollständig
3. Long-Term: RAG via Embeddings, score = α·sim + β·recency + γ·importance

Top-k=5 Retrieval, Recency-Decay = exp(-Δt / 1 Tag).
Importance wird vom kleinen Modell beim Speichern gescored.
"""
import json
import logging
import math
import time
from datetime import datetime, timezone

import db

log = logging.getLogger("liege.npc_memory")

TOP_K = 5
SCORE_W_SIM = 1.0
SCORE_W_RECENCY = 0.5
SCORE_W_IMPORTANCE = 0.3
IMPORTANCE_MIN_PERSIST = 2   # <2 → transient, nicht persistieren


SCHEMA = """
CREATE TABLE IF NOT EXISTS npc_memory_episode (
    id           BIGSERIAL PRIMARY KEY,
    npc_id       BIGINT NOT NULL,
    player_name  TEXT NULL,
    content      TEXT NOT NULL,
    embedding    JSONB NOT NULL,
    importance   SMALLINT NOT NULL DEFAULT 5,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_access  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS npc_memory_lookup_idx
    ON npc_memory_episode (npc_id, player_name, created_at DESC);
"""


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def _embed(text: str) -> list[float] | None:
    import llm_cache
    return await llm_cache._embed(text)


# Importance-Scoring via Fast-Brain (kleines Modell genügt)
IMPORTANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer",
                  "description": "Wichtigkeit (1=trivial Smalltalk, 10=Lebensereignis)."},
    },
    "required": ["score"],
}


async def _score_importance(turn_text: str) -> int:
    """Lässt das Fast-Brain die Wichtigkeit eines Turns scoren."""
    import llm
    prompt = (
        "Bewerte die Wichtigkeit folgender Gesprächs-Sequenz für die Erinnerung eines NPCs:\n\n"
        f"{turn_text}\n\n"
        "1 = trivialer Smalltalk, 5 = beachtenswert, 10 = lebensveränderndes Ereignis."
    )
    try:
        result = await llm.fast_brain_structured(prompt, IMPORTANCE_SCHEMA)
        if result and 1 <= int(result.get("score", 5)) <= 10:
            return int(result["score"])
    except Exception:
        log.debug("Importance-Scoring fehlgeschlagen", exc_info=True)
    return 5


async def write_memory(npc_id: int, player_name: str | None,
                        turn_text: str, importance: int | None = None) -> None:
    """Speichert ein Memory-Episode. Importance wird ggf. via Fast-Brain ermittelt."""
    if importance is None:
        importance = await _score_importance(turn_text)
    if importance < IMPORTANCE_MIN_PERSIST:
        return
    emb = await _embed(turn_text)
    if emb is None:
        return
    await db.pool().execute(
        "INSERT INTO npc_memory_episode (npc_id, player_name, content, embedding, importance) "
        "VALUES ($1, $2, $3, $4, $5)",
        npc_id, player_name, turn_text[:2000], json.dumps(emb), importance,
    )


async def retrieve_top_k(npc_id: int, player_name: str | None,
                          query: str, k: int = TOP_K) -> list[dict]:
    """Holt die top-k relevantesten Memories für den aktuellen Query.
    Score = α·similarity + β·recency_decay + γ·importance_norm
    """
    emb = await _embed(query)
    if emb is None:
        return []
    rows = await db.pool().fetch(
        "SELECT id, content, embedding, importance, created_at, last_access "
        "FROM npc_memory_episode "
        "WHERE npc_id = $1 AND (player_name = $2 OR player_name IS NULL) "
        "ORDER BY id DESC LIMIT 40",
        npc_id, player_name,
    )
    now = time.time()
    scored = []
    for r in rows:
        cached_emb = r["embedding"]
        if isinstance(cached_emb, str):
            cached_emb = json.loads(cached_emb)
        sim = _cosine(emb, cached_emb)
        # Recency: exp(-Δt / 86400)
        access_ts = r["last_access"].timestamp()
        recency = math.exp(-(now - access_ts) / 86400.0)
        importance_norm = r["importance"] / 10.0
        score = (SCORE_W_SIM * sim
                 + SCORE_W_RECENCY * recency
                 + SCORE_W_IMPORTANCE * importance_norm)
        scored.append({
            "id": r["id"], "content": r["content"],
            "importance": r["importance"], "sim": sim, "score": score,
        })
    scored.sort(key=lambda x: -x["score"])
    top = scored[:k]
    # last_access touchen
    if top:
        ids = [x["id"] for x in top]
        await db.pool().execute(
            "UPDATE npc_memory_episode SET last_access = NOW() WHERE id = ANY($1::bigint[])",
            ids,
        )
    return top


def format_memories_for_prompt(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = ["Frühere Erinnerungen (auswählend einflechten):"]
    for m in memories:
        lines.append(f"  • (Wichtigkeit {m['importance']}/10) {m['content']}")
    return "\n".join(lines)
