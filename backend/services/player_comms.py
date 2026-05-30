"""Player-Kommunikations-Helfer (Welle 34c, extrahiert aus main.py).

Dünner Wrapper um manager.connections.send_json — fängt Errors per try/except
ab, damit ein toter Socket den Caller nicht crasht.
"""

import logging


async def send_to_player(manager, player_id: str, payload: dict) -> None:
    ws = manager.connections.get(player_id)
    if ws is not None:
        try:
            await ws.send_json(payload)
        except Exception:
            logging.exception("send_to_player failed")
