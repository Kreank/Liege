import os
from typing import Any

import httpx

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
FAST_MODEL  = "qwen3.5:0.8b"
SLOW_MODEL  = "qwen3.5:9b"

_client: httpx.AsyncClient | None = None


async def init_llm() -> None:
    global _client
    _client = httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=180.0)


async def close_llm() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _generate(
    model: str,
    prompt: str,
    system: str | None = None,
    options: dict[str, Any] | None = None,
    json_mode: bool = False,
    think: bool = False,
    json_schema: dict | None = None,
) -> str:
    if _client is None:
        raise RuntimeError("LLM client not initialized — call init_llm() first")

    payload: dict[str, Any] = {
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "think":  think,
    }
    if system:
        payload["system"] = system
    if options:
        payload["options"] = options
    # Structured-Output: bevorzugt JSON-Schema vor reinem "json"-Mode
    if json_schema is not None:
        payload["format"] = json_schema
    elif json_mode:
        payload["format"] = "json"

    r = await _client.post("/api/generate", json=payload)
    r.raise_for_status()
    return r.json()["response"]


async def fast_brain_structured(
    prompt: str,
    schema: dict,
    system: str | None = None,
) -> dict | None:
    """Strukturierter Output vom Fast-Brain mit JSON-Schema. Returns geparseter
    Dict oder None bei Fehler."""
    import json as _json
    try:
        raw = await _generate(FAST_MODEL, prompt, system=system, json_schema=schema)
        return _json.loads(raw)
    except Exception:
        import logging
        logging.getLogger("liege.llm").exception("fast_brain_structured failed")
        return None


async def slow_brain_structured(
    prompt: str,
    schema: dict,
    system: str | None = None,
) -> dict | None:
    """Strukturierter Output vom Slow-Brain (CPU). Für sensible Generation."""
    import json as _json
    try:
        raw = await _generate(
            SLOW_MODEL, prompt, system=system,
            options={"num_gpu": 0}, json_schema=schema,
        )
        return _json.loads(raw)
    except Exception:
        import logging
        logging.getLogger("liege.llm").exception("slow_brain_structured failed")
        return None


async def fast_brain(
    prompt: str,
    system: str | None = None,
    think: bool = False,
) -> str:
    """Schnelle Inferenz auf GPU — NPC-Dialoge, Item-Flavor, <1s. think=False per default."""
    return await _generate(FAST_MODEL, prompt, system=system, think=think)


async def slow_brain(
    prompt: str,
    system: str | None = None,
    json_mode: bool = False,
    think: bool = False,
) -> str:
    """Hintergrund-DM auf CPU — Welt-Events, Quests. num_gpu=0 zwingt CPU-only.
    think=False per default; mit think=True für komplexe Entscheidungen, kostet aber Latenz."""
    return await _generate(
        SLOW_MODEL,
        prompt,
        system=system,
        options={"num_gpu": 0},
        json_mode=json_mode,
        think=think,
    )
