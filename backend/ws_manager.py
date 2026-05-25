from fastapi import WebSocket
from typing import Dict

class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.players: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, player_id: str, x: int, y: int):
        await websocket.accept()
        self.connections[player_id] = websocket
        self.players[player_id] = {"x": x, "y": y, "name": player_id[:8]}

    def disconnect(self, player_id: str):
        self.connections.pop(player_id, None)
        self.players.pop(player_id, None)

    def update_player(self, player_id: str, x: int, y: int):
        if player_id in self.players:
            self.players[player_id]["x"] = x
            self.players[player_id]["y"] = y

    def get_players(self) -> dict:
        return self.players

    async def broadcast(self, message: dict, exclude: str = None):
        dead = []
        for pid, ws in self.connections.items():
            if pid == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(pid)
        for pid in dead:
            self.disconnect(pid)
