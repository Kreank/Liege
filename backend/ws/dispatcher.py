"""WS-Message-Dispatcher.

HANDLERS-Dict: Message-Type → Coroutine-Handler. Jedes neue Domain-Modul
(`movement.py`, `social.py`, ...) füllt sich beim Import in dieses Dict ein.

In Phase B2 ist das Dict noch leer; der /ws-Loop fragt erst dispatch(),
fällt bei Miss in das alte if/elif. Mit jeder weiteren B-Phase wandern
Branches aus dem Monolithen in eigene Handler.

Signatur: `async def handle_<type>(ctx: WsContext, data: dict) -> None`.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from .context import WsContext


Handler = Callable[[WsContext, dict], Awaitable[None]]

HANDLERS: dict[str, Handler] = {}


async def dispatch(ctx: WsContext, data: dict) -> bool:
    """Versucht eine Message via HANDLERS zu behandeln.

    Returns True wenn ein Handler gefunden + ausgeführt wurde, sonst False
    (dann fällt der Aufrufer ins legacy if/elif).
    """
    mtype = data.get("type")
    handler = HANDLERS.get(mtype)
    if handler is None:
        return False
    await handler(ctx, data)
    return True


def register(mtype: str, handler: Handler) -> None:
    """Registriert einen Handler für einen Message-Type."""
    HANDLERS[mtype] = handler
