"""WsContext — per-connection state, an alle Handler durchgereicht.

Aus Phase B2 des refectoring-plan.md (§3.1, §7.1): Statt dass jeder
Handler-Branch auf Closure-Variablen oder Modul-Globals zugreift, halten
wir die nötigen Refs in einer einzigen Dataclass. Jede Domänen-Migration
(B3...B16) reicht ctx an die Handler durch.

Bewusst KEIN Per-Request-State (das kommt aus `data`), nur per-Connection.
Module-Refs wie `db`, `groups`, `combat`, `items_module` sind direkt
importierbar — die kommen NICHT in den Context.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import WebSocket

from events import EventManager
from items import ItemManager
from npcs import NPCManager
from structures import StructureManager
from world import World
from ws_manager import ConnectionManager


@dataclass
class WsContext:
    websocket: WebSocket
    player_id: str
    manager: ConnectionManager
    world: World
    structures: StructureManager
    npcs: NPCManager
    items: ItemManager
    events: EventManager
    user: dict | None = None  # auth-User-Dict (role etc.) — Dev/Admin-Gates
