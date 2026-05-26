"""Dev-Chat: Admin-only WebSocket der via Host-Bridge eine Claude-CLI-Session anspricht."""
import logging
import os

import httpx
from fastapi import WebSocket, WebSocketDisconnect

import auth

BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://host.docker.internal:11500")
BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
BRIDGE_TIMEOUT = float(os.environ.get("BRIDGE_TIMEOUT", "300"))

log = logging.getLogger("liege.dev_chat")


async def dev_chat_handler(websocket: WebSocket) -> None:
    user = await auth.get_user_from_ws(websocket)
    if not user:
        await websocket.accept()
        await websocket.close(code=1008)
        return
    if user.get("role") != "admin":
        await websocket.accept()
        await websocket.send_json({"type": "error", "error": "Admin-Rechte erforderlich"})
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await websocket.send_json({"type": "ready", "username": user["name"]})

    headers = {"X-Bridge-Token": BRIDGE_TOKEN} if BRIDGE_TOKEN else {}
    try:
        async with httpx.AsyncClient(timeout=BRIDGE_TIMEOUT) as client:
            while True:
                data = await websocket.receive_json()
                mtype = data.get("type")

                if mtype == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if mtype != "message":
                    continue

                msg = (data.get("message") or "").strip()
                reset = bool(data.get("reset", False))
                if not msg:
                    continue

                await websocket.send_json({"type": "thinking"})

                try:
                    resp = await client.post(
                        f"{BRIDGE_URL}/chat",
                        json={"message": msg, "reset": reset},
                        headers=headers,
                    )
                except httpx.HTTPError as e:
                    log.exception("Bridge HTTP error")
                    await websocket.send_json({
                        "type": "reply",
                        "ok": False,
                        "response": "",
                        "stderr": f"Bridge nicht erreichbar: {e}",
                    })
                    continue

                if resp.status_code != 200:
                    await websocket.send_json({
                        "type": "reply",
                        "ok": False,
                        "response": "",
                        "stderr": f"Bridge HTTP {resp.status_code}: {resp.text[:300]}",
                    })
                    continue

                try:
                    result = resp.json()
                except Exception as e:
                    await websocket.send_json({
                        "type": "reply",
                        "ok": False,
                        "response": "",
                        "stderr": f"Bridge gab kein JSON: {e}",
                    })
                    continue

                await websocket.send_json({
                    "type": "reply",
                    "ok": bool(result.get("ok")),
                    "response": result.get("response", ""),
                    "stderr": result.get("stderr", ""),
                })
    except WebSocketDisconnect:
        return
    except Exception:
        log.exception("dev_chat_handler crashed")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
