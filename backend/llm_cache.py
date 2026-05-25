"""Semantic-Cache für LLM-Outputs (Welle 24).

Spart 50-80% LLM-Calls durch Embedding-basiertes Cache-Hit.

Architektur (Recherche-Empfehlung):
- nomic-embed-text liefert 768-dim Embeddings
- Cache wird mit scope_key (npc:42, global:lore, …) gescoped
- prompt_kind unterscheidet 'factual' / 'lore' / 'intent' / 'creative'
- creative wird NIE gecached
- Threshold pro Kind: factual=0.95, lore=0.92, intent=0.88

Da kein pgvector installiert ist: Embeddings als JSONB float[] gespeichert,
cosine-similarity Python-seitig berechnet. Bei <10k Entries akzeptabel.
Beim Wachsen → pgvector-Migration.
"""
import json
import logging
import math
import os
import time

import db
import llm

log = logging.getLogger("liege.llm_cache")


SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_cache (
    id            BIGSERIAL PRIMARY KEY,
    scope_key     TEXT NOT NULL,
    prompt_kind   TEXT NOT NULL,
    prompt_hash   TEXT NOT NULL,
    prompt_text   TEXT NOT NULL,
    embedding     JSONB NOT NULL,
    response      JSONB NOT NULL,
    model_name    TEXT NOT NULL,
    hit_count     INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS llm_cache_scope_idx
    ON llm_cache (scope_key, prompt_kind);
CREATE INDEX IF NOT EXISTS llm_cache_hash_idx
    ON llm_cache (prompt_hash);
"""


THRESHOLDS = {
    "factual":  0.95,
    "lore":     0.92,
    "intent":   0.88,
    "creative": 1.01,    # immer Miss
}

TTL_SECONDS = {
    "factual":  None,             # persistent
    "lore":     7 * 24 * 3600,
    "intent":   3600,
    "creative": 60,
}

EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")

# Stats
_stats = {"hits": 0, "misses": 0, "writes": 0}


# — Embedding ——————————————————————————————————————————————————————————

async def _embed(text: str) -> list[float] | None:
    """Holt Embedding via Ollama /api/embeddings."""
    if llm._client is None:
        return None
    try:
        r = await llm._client.post(
            "/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text[:4000]},
        )
        r.raise_for_status()
        return r.json().get("embedding")
    except Exception:
        log.debug("Embedding fehlgeschlagen", exc_info=True)
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# — Cache-Operationen ——————————————————————————————————————————————————

import hashlib

def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


async def lookup(scope_key: str, prompt: str, prompt_kind: str) -> dict | None:
    """Versucht Cache-Hit. Returns response-Dict oder None."""
    if prompt_kind == "creative":
        return None
    threshold = THRESHOLDS.get(prompt_kind, 0.92)

    # 1) Exact-Hash-Lookup (schnell, kein embedding)
    h = _prompt_hash(prompt)
    row = await db.pool().fetchrow(
        "SELECT id, response FROM llm_cache "
        "WHERE scope_key = $1 AND prompt_kind = $2 AND prompt_hash = $3 "
        "AND (expires_at IS NULL OR expires_at > NOW()) LIMIT 1",
        scope_key, prompt_kind, h,
    )
    if row:
        await db.pool().execute(
            "UPDATE llm_cache SET hit_count = hit_count + 1 WHERE id = $1", row["id"],
        )
        _stats["hits"] += 1
        resp = row["response"]
        return json.loads(resp) if isinstance(resp, str) else resp

    # 2) Semantic-Lookup
    emb = await _embed(prompt)
    if emb is None:
        _stats["misses"] += 1
        return None
    rows = await db.pool().fetch(
        "SELECT id, embedding, response FROM llm_cache "
        "WHERE scope_key = $1 AND prompt_kind = $2 "
        "AND (expires_at IS NULL OR expires_at > NOW()) "
        "ORDER BY id DESC LIMIT 50",
        scope_key, prompt_kind,
    )
    best = (0.0, None, None)
    for r in rows:
        cached_emb = r["embedding"]
        if isinstance(cached_emb, str):
            cached_emb = json.loads(cached_emb)
        sim = _cosine(emb, cached_emb)
        if sim > best[0]:
            best = (sim, r["id"], r["response"])
    if best[0] >= threshold:
        await db.pool().execute(
            "UPDATE llm_cache SET hit_count = hit_count + 1 WHERE id = $1", best[1],
        )
        _stats["hits"] += 1
        log.debug("Semantic-Hit (sim=%.3f, kind=%s, scope=%s)", best[0], prompt_kind, scope_key)
        resp = best[2]
        return json.loads(resp) if isinstance(resp, str) else resp
    _stats["misses"] += 1
    return None


async def store(scope_key: str, prompt: str, prompt_kind: str,
                response: dict, model_name: str) -> None:
    """Persistiert Cache-Eintrag."""
    if prompt_kind == "creative":
        return
    emb = await _embed(prompt)
    if emb is None:
        return
    h = _prompt_hash(prompt)
    ttl = TTL_SECONDS.get(prompt_kind)
    if ttl is None:
        expires = None
    else:
        from datetime import datetime, timedelta, timezone
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    await db.pool().execute(
        "INSERT INTO llm_cache (scope_key, prompt_kind, prompt_hash, prompt_text, "
        "embedding, response, model_name, expires_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
        scope_key, prompt_kind, h, prompt[:2000],
        json.dumps(emb), json.dumps(response), model_name, expires,
    )
    _stats["writes"] += 1


async def cleanup_expired() -> int:
    """Periodischer Cleanup. Returns Anzahl gelöschter Einträge."""
    row = await db.pool().fetchrow(
        "WITH d AS (DELETE FROM llm_cache WHERE expires_at IS NOT NULL "
        "AND expires_at <= NOW() RETURNING 1) SELECT COUNT(*) AS n FROM d",
    )
    return int(row["n"]) if row else 0


def stats() -> dict:
    total = _stats["hits"] + _stats["misses"]
    return {
        **_stats,
        "hit_rate": _stats["hits"] / total if total else 0,
    }
