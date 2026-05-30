"""WebSocket-Smoke-Harness für das Refactoring-Sicherheitsnetz.

Loggt einen festen Test-User ein, öffnet /ws, schickt eine feste Sequenz
repräsentativer Messages und schreibt einen normalisierten Bericht raus,
der als Golden-Output gegen Refactor-Stände diffbar ist.

Usage:
    python backend/tools/ws_smoke.py [output_file]

Default output_file: docu/ws_smoke_golden.txt (relativ zum Repo-Root).

Erwartet:
- Backend läuft auf $LIEGE_BASE_URL (default http://localhost:8000)
- Postgres erreichbar (für Auth + Player-State)
- SESSION_SECRET im Backend gesetzt

Determinismus-Strategie:
- Async-Broadcast-Types (time_update, npc_pos, weather, ...) werden gefiltert,
  damit Tick-Worker-Lärm nicht ins Golden rinnt.
- Dynamische Felder (timestamps, random IDs, last_seen) werden gestrippt.
- Pro Step wird die Sequenz "SEND → 500ms Antworten sammeln → normalisieren" abgespielt.
- Der erste Lauf gegen einen unveränderten Stand wird als Golden gespeichert,
  spätere Läufe vergleichen via `diff`.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import httpx
    import websockets
except ImportError as exc:
    sys.exit(f"Missing dep: {exc}. Run inside the backend venv or pip install httpx websockets.")


BASE_URL = os.environ.get("LIEGE_BASE_URL", "http://localhost:8000")
WS_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

TEST_USER = os.environ.get("SMOKE_USER", "smoketest")
TEST_PASSWORD = os.environ.get("SMOKE_PASSWORD", "smoketest12345")

# Server→Client-Types, die von Welt-Tick-Workern ungeplant kommen und kein
# direktes Echo unserer Requests sind. Werden aus dem Golden gefiltert.
# Basis: WS_PROTOCOL.md Anhang + Cross-Domain-Liste.
ASYNC_BROADCAST_TYPES = {
    # time_system
    "time_tick",
    "time_update",
    # event_worker / storyteller / raid_director
    "event",
    "world_event",
    "disaster_started",
    "disaster_ended",
    # npc_worker
    "npc_moved",
    "npc_spawned",
    "npc_damaged",
    "npc_died",
    "npc_goal",
    # ambient chatter / dev_chat
    "npc_chatter",
    "ambient_chatter",
    # player needs / stamina (kommen aus needs-loop alle 30s)
    "player_needs",
    # spawn / despawn-flows aus respawn_worker / world_populator
    "item_spawned",
    # world_populator spawnt zufällig Strukturen / Dungeon-Eingänge.
    "structure_placed",
    "structure_removed",
    "structure_replaced",
    "structure_damaged",
    "structure_repaired",
    "structure_upgraded",
    # dungeon_director spawnt neue Dungeons / Aktualisierungen.
    "dungeon_sense",
    # andere Spieler — in unserem 1-User-Smoke leer, defensiv
    "player_joined",
    "player_left",
    "player_moved",
    # FX, die durch Welt-Events ausgelöst werden
    "earthquake_shake",
    "visual_effect",
    # status_effects-Worker
    "status_effects",
}

# Felder, die sich pro Lauf ändern und keinen Erkenntniswert für Diff haben.
DYNAMIC_FIELDS = {
    "timestamp",
    "ts",
    "time",
    "created_at",
    "updated_at",
    "last_seen",
    "last_moved",
    "now",
    "expires_at",
    # Inkrementelle Datenbank-IDs ändern sich pro Lauf (BIGSERIAL).
    "id",
    "group_id",
    "invite_id",
    "roll_id",
    # Welt-Zeit innerhalb von Frames (in init durch INIT_VOLATILE bereits weg).
    "hour",
    "minute_of_day",
    "phase",
}

# Felder im init-Payload, die volatil oder zu groß sind. Werden für
# CONNECT-Step gestrippt. Strategie: Wir wollen Form prüfen, nicht volle
# Welt — Chunks/Structures/NPCs ändern sich pro Lauf und sind 100ke Tiles.
INIT_VOLATILE_FIELDS = {
    # Volatil (Welt-Worker schreiben dauernd):
    "time",
    "events",
    "active_disasters",
    "npcs",
    "items_ground",
    "players",
    # Needs-Werte ticken alle 30s — zwischen 2 Smoke-Läufen messbar.
    "hp",
    "mana",
    "hunger",
    "thirst",
    "stamina",
    # Riesig (Welt-Daten, deterministisch pro Seed aber irrelevant für Refactor-Diff):
    "chunks",
    "structures",
    "dungeons",
    # Schemas / Kataloge — zu groß und nicht refactor-relevant:
    "spell_catalog",
    "factions",
    "talents",
    "learned_spells",
    "quests",
    # Stat-Sheet enthält Equipment-snapshot, kann variieren:
    "stats",
    "attributes",
    "skills",
    "research",
    "group",
    "group_invites",
}


def normalize(obj: Any, extra_drop: Iterable[str] = ()) -> Any:
    drop = DYNAMIC_FIELDS | set(extra_drop)
    if isinstance(obj, dict):
        return {k: normalize(v, extra_drop) for k, v in sorted(obj.items()) if k not in drop}
    if isinstance(obj, list):
        return [normalize(x, extra_drop) for x in obj]
    return obj


async def login_or_register(client: httpx.AsyncClient) -> None:
    status = await client.get("/auth/status")
    status.raise_for_status()
    has_users = bool(status.json().get("has_users"))

    if not has_users:
        r = await client.post(
            "/auth/register",
            json={"username": TEST_USER, "password": TEST_PASSWORD},
        )
        if r.status_code != 200:
            sys.exit(f"Register failed: {r.status_code} {r.text}")
        return

    r = await client.post(
        "/auth/login",
        json={"username": TEST_USER, "password": TEST_PASSWORD},
    )
    if r.status_code == 200:
        return
    if r.status_code == 401:
        sys.exit(
            f"Test-User '{TEST_USER}' existiert nicht oder Passwort falsch. "
            "Lege ihn als Admin im Backend an oder lösche die DB neu."
        )
    sys.exit(f"Login failed: {r.status_code} {r.text}")


async def collect(ws, duration_ms: int, *, drop_async: bool = True) -> list[dict]:
    out: list[dict] = []
    loop = asyncio.get_event_loop()
    end = loop.time() + duration_ms / 1000
    while True:
        remaining = end - loop.time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if drop_async and msg.get("type") in ASYNC_BROADCAST_TYPES:
            continue
        out.append(msg)
    return out


async def run_smoke(output_path: Path) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=False) as client:
        await login_or_register(client)
        cookies = "; ".join(f"{k}={v}" for k, v in client.cookies.items())

    steps: list[tuple[str, dict | None, list[dict]]] = []

    async with websockets.connect(
        WS_URL, extra_headers=[("Cookie", cookies)], max_size=2**24
    ) as ws:
        init_msgs = await collect(ws, 1500)
        init_norm = [
            normalize(m, extra_drop=INIT_VOLATILE_FIELDS) for m in init_msgs
        ]
        steps.append(("CONNECT", None, init_norm))

        async def step(label: str, payload: dict, wait_ms: int = 500) -> None:
            await ws.send(json.dumps(payload))
            received = await collect(ws, wait_ms)
            steps.append((label, payload, [normalize(m) for m in received]))

        # --- Fixe Sequenz (read-only und idempotent) ---
        await step("list_attributes", {"type": "list_attributes"})
        await step("list_talents", {"type": "list_talents"})
        # list_quests übersprungen — quests.all_reputation crasht wegen
        # alter Spaltennamen (siehe docu/REFACTOR_NOTES.md #1).
        await step("list_bills", {"type": "list_bills"})
        await step("character_check_name", {"type": "character_check_name", "name": "SmokeHero"})

        # Bewegung: 1 Tile rechts, dann wieder zurück → idempotente Position.
        await step("move_east", {"type": "move", "x": 61, "y": 40})
        await step("move_back", {"type": "move", "x": 60, "y": 40})

        # Crafting-Menü öffnen (read-only)
        await step("open_hand_crafting", {"type": "open_hand_crafting"})

        # Gruppe: party erstellen, refresh, disband
        await step("group_create_party", {"type": "group_create_party"})
        await step("group_refresh", {"type": "group_refresh"})
        await step("group_disband", {"type": "group_disband"})

        # Versuch eines invalid place_structure (kein Material) — deterministischer Fehler
        await step(
            "place_structure_invalid",
            {"type": "place_structure", "x": 60, "y": 40, "structure_type": "wall_stone"},
        )

        # Versuch eines invalid attack_npc — deterministischer Fehler
        await step(
            "attack_npc_invalid",
            {"type": "attack_npc", "npc_id": -1},
        )

        # Versuch eines learn_talent ohne Punkte / ohne Skill — deterministischer Fehler
        await step(
            "learn_talent_invalid",
            {"type": "learn_talent", "talent_id": "smoke_nonexistent"},
        )

        # Chat
        await step("chat", {"type": "chat", "text": "smoke-test-message"})

        # Inventory-Read via use_item invalid
        await step(
            "use_item_invalid",
            {"type": "use_item", "item_id": -1},
        )

    write_report(output_path, steps)


def write_report(path: Path, steps: list[tuple[str, dict | None, list[dict]]]) -> None:
    lines: list[str] = []
    lines.append(f"# ws_smoke golden output")
    lines.append(f"# steps={len(steps)}")
    lines.append("")
    for label, sent, received in steps:
        lines.append(f"=== {label} ===")
        if sent is not None:
            lines.append(f"SENT: {json.dumps(normalize(sent), sort_keys=True)}")
        lines.append(f"RECEIVED ({len(received)}):")
        for msg in received:
            lines.append(f"  {json.dumps(msg, sort_keys=True)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {path} ({len(steps)} steps)")


def main(argv: list[str]) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    default_out = repo_root / "docu" / "ws_smoke_golden.txt"
    out = Path(argv[1]) if len(argv) > 1 else default_out
    out.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(run_smoke(out))


if __name__ == "__main__":
    main(sys.argv)
