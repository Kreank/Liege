"""Spielergruppen-System: Party (5), Raid klein (20), Raid groß (40).

Eine Gruppe ist ein temporärer Verbund von Spielern mit gemeinsamem Chat,
XP-Sharing und Loot-Regel. Drei kinds:
    party       — bis 5 Mitglieder, einfaches Ad-hoc-Team
    raid_small  — bis 20, 4 Sub-Parties × 5
    raid_large  — bis 40, 8 Sub-Parties × 5

Ein Spieler kann gleichzeitig nur in EINER Gruppe sein (DB-seitig via
UNIQUE-Index erzwungen). Rollen: 'leader', 'assist', 'member'.

Lifecycle:
    party       → auto-disband 5 min nach Leader-Disconnect (siehe on_disconnect)
    raid_small  → bleibt 24h aktiv, auch wenn alle offline
    raid_large  → bleibt 24h aktiv, auch wenn alle offline

is_friendly(a, b) ist die Single-Point-Permission-Funktion. Anstatt in jedem
WS-Handler einzeln zu prüfen wird HIER zentral entschieden. Forward-kompatibel
für späteres Gilden-/Allianzen-System (siehe structures.can_modify-Kommentar).
"""
import logging
import time
from typing import Optional

import db

log = logging.getLogger("liege.groups")


# — Konfiguration —————————————————————————————————————————————————————————

GROUP_KINDS = ("party", "raid_small", "raid_large")
MAX_MEMBERS = {
    "party": 5,
    "raid_small": 20,
    "raid_large": 40,
}
SUB_PARTY_SIZE = 5
SUB_PARTIES = {
    "party": 1,
    "raid_small": 4,
    "raid_large": 8,
}

ROLE_LEADER = "leader"
ROLE_ASSIST = "assist"
ROLE_MEMBER = "member"

INVITE_TTL_SECONDS = 60
LEADER_OFFLINE_GRACE_SECONDS = 300  # Party: nach 5 min ohne Leader auto-disband
RAID_KEEPALIVE_SECONDS = 86400      # Raids bleiben 24h auch ohne Online-Mitglieder

# In-Memory: wann ist der Leader einer Party offline gegangen?
# {group_id: timestamp}. Wird bei Reconnect gelöscht.
_party_leader_offline_since: dict[int, float] = {}


SCHEMA = """
CREATE TABLE IF NOT EXISTS player_groups (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT NOT NULL,
    leader        TEXT NOT NULL,
    name          TEXT,
    loot_rule     TEXT NOT NULL DEFAULT 'ffa',
    master_looter TEXT,
    round_robin_ptr INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disbanded_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS player_groups_active_idx
    ON player_groups (kind, disbanded_at);

CREATE TABLE IF NOT EXISTS group_members (
    group_id    BIGINT NOT NULL REFERENCES player_groups(id) ON DELETE CASCADE,
    player_name TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'member',
    sub_party   INTEGER NOT NULL DEFAULT 1,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (group_id, player_name)
);
-- Ein Spieler darf nur in genau einer aktiven Gruppe sein. Da disbanded
-- Gruppen via CASCADE die Memberships mitnehmen, reicht UNIQUE auf player_name.
CREATE UNIQUE INDEX IF NOT EXISTS group_members_player_unique
    ON group_members (player_name);

CREATE TABLE IF NOT EXISTS group_invites (
    id           BIGSERIAL PRIMARY KEY,
    group_id     BIGINT NOT NULL REFERENCES player_groups(id) ON DELETE CASCADE,
    from_player  TEXT NOT NULL,
    to_player    TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS group_invites_to_idx
    ON group_invites (to_player, expires_at);
-- Verhindert doppelte aktive Invites auf denselben Spieler in dieselbe Gruppe.
CREATE UNIQUE INDEX IF NOT EXISTS group_invites_pending_unique
    ON group_invites (group_id, to_player);
"""


async def init_schema() -> None:
    """Idempotent — kann bei jedem Start aufgerufen werden."""
    for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
        await db.pool().execute(stmt)


# — Lookups ———————————————————————————————————————————————————————————————

async def get_group_for(player_name: str) -> Optional[dict]:
    """Liefert die aktuelle Gruppe eines Spielers (oder None)."""
    row = await db.pool().fetchrow(
        "SELECT g.id, g.kind, g.leader, g.name, g.loot_rule, g.master_looter, "
        "       g.round_robin_ptr, g.created_at, "
        "       m.role, m.sub_party "
        "FROM group_members m JOIN player_groups g ON g.id = m.group_id "
        "WHERE m.player_name = $1 AND g.disbanded_at IS NULL",
        player_name,
    )
    if not row:
        return None
    return dict(row)


async def get_group(group_id: int) -> Optional[dict]:
    row = await db.pool().fetchrow(
        "SELECT id, kind, leader, name, loot_rule, master_looter, "
        "       round_robin_ptr, created_at, last_active_at "
        "FROM player_groups WHERE id = $1 AND disbanded_at IS NULL",
        group_id,
    )
    return dict(row) if row else None


async def get_members(group_id: int) -> list[dict]:
    rows = await db.pool().fetch(
        "SELECT player_name, role, sub_party, joined_at "
        "FROM group_members WHERE group_id = $1 "
        "ORDER BY (role = 'leader') DESC, (role = 'assist') DESC, joined_at",
        group_id,
    )
    return [dict(r) for r in rows]


async def get_member_names(group_id: int) -> set[str]:
    """Schnelle Set-Lookup, z.B. für XP-Split / Loot-Filter."""
    rows = await db.pool().fetch(
        "SELECT player_name FROM group_members WHERE group_id = $1", group_id
    )
    return {r["player_name"] for r in rows}


async def is_friendly(player_a: str, player_b: str) -> bool:
    """Zentrale Permission-Funktion: sind a und b in derselben Gruppe?
    Self-Check zählt als 'friendly'. Forward-kompatibel — wenn Gilden/
    Allianzen kommen, wird HIER erweitert (NICHT in jedem WS-Handler)."""
    if player_a == player_b:
        return True
    row = await db.pool().fetchrow(
        "SELECT 1 FROM group_members a "
        "JOIN group_members b ON a.group_id = b.group_id "
        "JOIN player_groups g ON g.id = a.group_id "
        "WHERE a.player_name = $1 AND b.player_name = $2 "
        "  AND g.disbanded_at IS NULL "
        "LIMIT 1",
        player_a, player_b,
    )
    return row is not None


# — Permission-Helper ————————————————————————————————————————————————————

async def _role_in(group_id: int, player_name: str) -> Optional[str]:
    row = await db.pool().fetchrow(
        "SELECT role FROM group_members WHERE group_id = $1 AND player_name = $2",
        group_id, player_name,
    )
    return row["role"] if row else None


async def can_invite(group_id: int, player_name: str) -> bool:
    r = await _role_in(group_id, player_name)
    return r in (ROLE_LEADER, ROLE_ASSIST)


async def can_kick(group_id: int, by_player: str, target: str) -> bool:
    """Leader darf jeden außer sich kicken. Assist darf nur normale Members."""
    if by_player == target:
        return False
    by_role = await _role_in(group_id, by_player)
    tgt_role = await _role_in(group_id, target)
    if not by_role or not tgt_role:
        return False
    if by_role == ROLE_LEADER:
        return True
    if by_role == ROLE_ASSIST and tgt_role == ROLE_MEMBER:
        return True
    return False


async def can_promote(group_id: int, by_player: str) -> bool:
    return (await _role_in(group_id, by_player)) == ROLE_LEADER


# — Mutations: Gruppe erstellen / auflösen ———————————————————————————————

async def create_party(leader: str) -> dict:
    """Erstellt eine neue Party mit `leader` als einzigem Mitglied.
    Fehlt: leader ist schon in einer Gruppe → wirft ValueError."""
    existing = await get_group_for(leader)
    if existing:
        raise ValueError("already_in_group")
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO player_groups (kind, leader) VALUES ('party', $1) "
                "RETURNING id, kind, leader, name, loot_rule, "
                "          round_robin_ptr, created_at",
                leader,
            )
            await conn.execute(
                "INSERT INTO group_members (group_id, player_name, role) "
                "VALUES ($1, $2, 'leader')",
                row["id"], leader,
            )
    log.info("Party %d von %s erstellt", row["id"], leader)
    return dict(row)


async def disband(group_id: int, by_player: Optional[str] = None) -> bool:
    """Löst eine Gruppe auf. by_player=None erlaubt System-Auflösung
    (Auto-Disband nach Leader-Offline-Timeout)."""
    g = await get_group(group_id)
    if not g:
        return False
    if by_player is not None and g["leader"] != by_player:
        return False
    await db.pool().execute(
        "UPDATE player_groups SET disbanded_at = NOW() WHERE id = $1", group_id
    )
    # ON DELETE CASCADE bei group_members ist on disband nicht aktiv (wir soft-deleten),
    # also Memberships manuell entfernen, damit der UNIQUE-Constraint frei wird.
    await db.pool().execute("DELETE FROM group_members WHERE group_id = $1", group_id)
    await db.pool().execute("DELETE FROM group_invites WHERE group_id = $1", group_id)
    _party_leader_offline_since.pop(group_id, None)
    log.info("Gruppe %d aufgelöst (by=%s)", group_id, by_player or "system")
    return True


# — Mutations: Invite / Join / Leave ——————————————————————————————————————

async def invite(group_id: int, from_player: str, to_player: str) -> dict:
    """Sendet ein Invite. Return-Dict beschreibt das Ergebnis:
       {"ok": True, "invite_id": ..., "expires_at": ...} oder
       {"ok": False, "reason": "..."}.
    Mögliche Gründe: no_group, no_permission, target_in_other_group,
                     target_is_self, group_full, already_invited."""
    if from_player == to_player:
        return {"ok": False, "reason": "target_is_self"}
    g = await get_group(group_id)
    if not g:
        return {"ok": False, "reason": "no_group"}
    if not await can_invite(group_id, from_player):
        return {"ok": False, "reason": "no_permission"}
    target_group = await get_group_for(to_player)
    if target_group:
        return {"ok": False, "reason": "target_in_other_group"}
    cnt = await db.pool().fetchval(
        "SELECT COUNT(*) FROM group_members WHERE group_id = $1", group_id
    )
    if cnt >= MAX_MEMBERS[g["kind"]]:
        return {"ok": False, "reason": "group_full"}
    # Cleanup abgelaufener Invites BEVOR wir prüfen, damit
    # der UNIQUE-Index (group_id, to_player) nicht durch
    # eine Karteileiche blockiert wird.
    await db.pool().execute(
        "DELETE FROM group_invites WHERE expires_at < NOW()"
    )
    try:
        row = await db.pool().fetchrow(
            "INSERT INTO group_invites (group_id, from_player, to_player, expires_at) "
            "VALUES ($1, $2, $3, NOW() + ($4 || ' seconds')::INTERVAL) "
            "RETURNING id, expires_at",
            group_id, from_player, to_player, str(INVITE_TTL_SECONDS),
        )
    except Exception as e:
        # UNIQUE-Conflict: schon eingeladen
        if "group_invites_pending_unique" in str(e):
            return {"ok": False, "reason": "already_invited"}
        raise
    return {"ok": True, "invite_id": row["id"], "expires_at": row["expires_at"]}


async def list_invites_for(player_name: str) -> list[dict]:
    rows = await db.pool().fetch(
        "SELECT i.id, i.group_id, i.from_player, i.expires_at, "
        "       g.kind, g.name AS group_name, g.leader "
        "FROM group_invites i JOIN player_groups g ON g.id = i.group_id "
        "WHERE i.to_player = $1 AND i.expires_at > NOW() "
        "  AND g.disbanded_at IS NULL "
        "ORDER BY i.created_at",
        player_name,
    )
    return [dict(r) for r in rows]


async def accept_invite(invite_id: int, player_name: str) -> dict:
    """Spieler nimmt Invite an. Return:
       {"ok": True, "group_id": ..., "kind": ...} oder
       {"ok": False, "reason": "..."}."""
    row = await db.pool().fetchrow(
        "SELECT i.group_id, i.expires_at, g.kind "
        "FROM group_invites i JOIN player_groups g ON g.id = i.group_id "
        "WHERE i.id = $1 AND i.to_player = $2 AND g.disbanded_at IS NULL",
        invite_id, player_name,
    )
    if not row:
        return {"ok": False, "reason": "invite_not_found"}
    if row["expires_at"] < _now_db():
        await db.pool().execute("DELETE FROM group_invites WHERE id = $1", invite_id)
        return {"ok": False, "reason": "invite_expired"}
    if await get_group_for(player_name):
        return {"ok": False, "reason": "already_in_group"}
    group_id = row["group_id"]
    cnt = await db.pool().fetchval(
        "SELECT COUNT(*) FROM group_members WHERE group_id = $1", group_id
    )
    if cnt >= MAX_MEMBERS[row["kind"]]:
        return {"ok": False, "reason": "group_full"}
    sp = await _next_sub_party_for(group_id, row["kind"], cnt)
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO group_members (group_id, player_name, role, sub_party) "
                "VALUES ($1, $2, 'member', $3)",
                group_id, player_name, sp,
            )
            await conn.execute("DELETE FROM group_invites WHERE id = $1", invite_id)
            await conn.execute(
                "UPDATE player_groups SET last_active_at = NOW() WHERE id = $1",
                group_id,
            )
    return {"ok": True, "group_id": group_id, "kind": row["kind"]}


async def decline_invite(invite_id: int, player_name: str) -> bool:
    res = await db.pool().execute(
        "DELETE FROM group_invites WHERE id = $1 AND to_player = $2",
        invite_id, player_name,
    )
    return res.endswith(" 1")


async def leave(player_name: str) -> dict:
    """Spieler verlässt seine Gruppe. Spezialfälle:
       - Letztes Mitglied → Gruppe wird aufgelöst
       - Leader verlässt, andere noch da → Auto-Succession an Assist oder
         dienstältesten Member
    Return: {"ok": True, "group_id": ..., "disbanded": bool,
             "new_leader": Optional[str]}"""
    g = await get_group_for(player_name)
    if not g:
        return {"ok": False, "reason": "not_in_group"}
    group_id = g["id"]
    was_leader = g["role"] == ROLE_LEADER
    await db.pool().execute(
        "DELETE FROM group_members WHERE group_id = $1 AND player_name = $2",
        group_id, player_name,
    )
    remaining = await db.pool().fetchval(
        "SELECT COUNT(*) FROM group_members WHERE group_id = $1", group_id
    )
    if remaining == 0:
        await disband(group_id)
        return {"ok": True, "group_id": group_id, "disbanded": True,
                "new_leader": None}
    new_leader = None
    if was_leader:
        # Auto-Succession: bevorzugt Assist, sonst ältestes Member
        succ = await db.pool().fetchrow(
            "SELECT player_name FROM group_members WHERE group_id = $1 "
            "ORDER BY (role = 'assist') DESC, joined_at LIMIT 1",
            group_id,
        )
        if succ:
            new_leader = succ["player_name"]
            await db.pool().execute(
                "UPDATE group_members SET role = 'leader' "
                "WHERE group_id = $1 AND player_name = $2",
                group_id, new_leader,
            )
            await db.pool().execute(
                "UPDATE player_groups SET leader = $2 WHERE id = $1",
                group_id, new_leader,
            )
    await db.pool().execute(
        "UPDATE player_groups SET last_active_at = NOW() WHERE id = $1",
        group_id,
    )
    return {"ok": True, "group_id": group_id, "disbanded": False,
            "new_leader": new_leader}


async def kick(group_id: int, by_player: str, target: str) -> dict:
    if not await can_kick(group_id, by_player, target):
        return {"ok": False, "reason": "no_permission"}
    # Leverage leave-Logik nicht — kick implies kein Auto-Succession
    res = await db.pool().execute(
        "DELETE FROM group_members WHERE group_id = $1 AND player_name = $2",
        group_id, target,
    )
    if not res.endswith(" 1"):
        return {"ok": False, "reason": "not_in_group"}
    await db.pool().execute(
        "UPDATE player_groups SET last_active_at = NOW() WHERE id = $1", group_id,
    )
    return {"ok": True, "kicked": target}


async def promote(group_id: int, by_player: str, target: str) -> dict:
    """Macht `target` zum Assist. Leader-Wechsel ist separate Funktion."""
    if not await can_promote(group_id, by_player):
        return {"ok": False, "reason": "no_permission"}
    if by_player == target:
        return {"ok": False, "reason": "target_is_self"}
    tgt_role = await _role_in(group_id, target)
    if tgt_role is None:
        return {"ok": False, "reason": "not_in_group"}
    if tgt_role == ROLE_ASSIST:
        return {"ok": False, "reason": "already_assist"}
    await db.pool().execute(
        "UPDATE group_members SET role = 'assist' "
        "WHERE group_id = $1 AND player_name = $2",
        group_id, target,
    )
    return {"ok": True, "promoted": target}


LOOT_RULES = ("ffa", "need_greed")


async def set_loot_rule(group_id: int, by_player: str, rule: str) -> dict:
    """Setzt die Loot-Regel der Gruppe. Nur Leader.
    'ffa'        — alles fällt auf den Boden, jeder darf aufheben (default)
    'need_greed' — rollwürdige Drops (equipment/magic/affix) lösen Roll aus
                   (siehe loot_rolls.py). Resources/Food/Consumables bleiben FFA."""
    if rule not in LOOT_RULES:
        return {"ok": False, "reason": "invalid_rule"}
    if not await can_promote(group_id, by_player):
        return {"ok": False, "reason": "no_permission"}
    await db.pool().execute(
        "UPDATE player_groups SET loot_rule = $2, last_active_at = NOW() "
        "WHERE id = $1", group_id, rule,
    )
    return {"ok": True, "rule": rule}


async def convert_to_raid(group_id: int, by_player: str, new_kind: str) -> dict:
    """Wandelt eine Gruppe in einen größeren Container um. Nur Leader.
    Erlaubte Up-Konvertierungen: party → raid_small → raid_large.
    Down-Konvertierung ist nicht erlaubt (zu viele Edge-Cases mit Members
    außerhalb der neuen Max-Grenze)."""
    if new_kind not in ("raid_small", "raid_large"):
        return {"ok": False, "reason": "invalid_kind"}
    if not await can_promote(group_id, by_player):
        return {"ok": False, "reason": "no_permission"}
    g = await get_group(group_id)
    if not g:
        return {"ok": False, "reason": "no_group"}
    # Down-Konvertierung ausschließen
    order = {"party": 0, "raid_small": 1, "raid_large": 2}
    if order[new_kind] <= order[g["kind"]]:
        return {"ok": False, "reason": "no_downgrade"}
    await db.pool().execute(
        "UPDATE player_groups SET kind = $2, last_active_at = NOW() WHERE id = $1",
        group_id, new_kind,
    )
    log.info("Gruppe %d konvertiert: %s → %s (by=%s)",
             group_id, g["kind"], new_kind, by_player)
    return {"ok": True, "from_kind": g["kind"], "to_kind": new_kind}


async def transfer_leader(group_id: int, by_player: str, target: str) -> dict:
    """Leader übergibt seine Rolle an `target`. Vorheriger Leader wird Assist."""
    if not await can_promote(group_id, by_player):
        return {"ok": False, "reason": "no_permission"}
    if by_player == target:
        return {"ok": False, "reason": "target_is_self"}
    tgt_role = await _role_in(group_id, target)
    if tgt_role is None:
        return {"ok": False, "reason": "not_in_group"}
    async with db.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE group_members SET role = 'assist' "
                "WHERE group_id = $1 AND player_name = $2",
                group_id, by_player,
            )
            await conn.execute(
                "UPDATE group_members SET role = 'leader' "
                "WHERE group_id = $1 AND player_name = $2",
                group_id, target,
            )
            await conn.execute(
                "UPDATE player_groups SET leader = $2 WHERE id = $1",
                group_id, target,
            )
    return {"ok": True, "new_leader": target}


# — Sub-Party-Zuteilung ————————————————————————————————————————————————

async def _next_sub_party_for(group_id: int, kind: str, current_count: int) -> int:
    """Wählt die kleinste Sub-Party mit Platz (<5)."""
    if kind == "party":
        return 1
    n_sub = SUB_PARTIES[kind]
    rows = await db.pool().fetch(
        "SELECT sub_party, COUNT(*) AS c FROM group_members "
        "WHERE group_id = $1 GROUP BY sub_party",
        group_id,
    )
    counts = {i: 0 for i in range(1, n_sub + 1)}
    for r in rows:
        counts[r["sub_party"]] = r["c"]
    for i in range(1, n_sub + 1):
        if counts[i] < SUB_PARTY_SIZE:
            return i
    return 1  # Fallback (sollte nie passieren, da group_full schon abgefangen)


# — Disconnect-Handling ————————————————————————————————————————————————

def mark_leader_offline(group_id: int) -> None:
    _party_leader_offline_since[group_id] = time.time()


def mark_leader_online(group_id: int) -> None:
    _party_leader_offline_since.pop(group_id, None)


async def reap_idle_groups() -> list[int]:
    """Wird vom Background-Worker aufgerufen. Räumt auf:
       - Parties deren Leader >5 min offline ist
       - Raids mit last_active_at >24h
       - Abgelaufene Invites
    Return: Liste aufgelöster group_ids (für Broadcast)."""
    disbanded: list[int] = []
    now = time.time()
    # 1) Parties mit offline-Leader
    for gid, since in list(_party_leader_offline_since.items()):
        if now - since >= LEADER_OFFLINE_GRACE_SECONDS:
            g = await get_group(gid)
            if g and g["kind"] == "party":
                if await disband(gid):
                    disbanded.append(gid)
            _party_leader_offline_since.pop(gid, None)
    # 2) Raids mit 24h Inaktivität
    rows = await db.pool().fetch(
        "SELECT id FROM player_groups "
        "WHERE kind IN ('raid_small', 'raid_large') "
        "  AND disbanded_at IS NULL "
        "  AND last_active_at < NOW() - ($1 || ' seconds')::INTERVAL",
        str(RAID_KEEPALIVE_SECONDS),
    )
    for r in rows:
        if await disband(r["id"]):
            disbanded.append(r["id"])
    # 3) Abgelaufene Invites
    await db.pool().execute("DELETE FROM group_invites WHERE expires_at < NOW()")
    return disbanded


# — Helpers ————————————————————————————————————————————————————————————

def _now_db():
    """Vergleichbar mit asyncpg-Timestamps (timezone-aware)."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


# — Background-Reaper ————————————————————————————————————————————————

REAPER_INTERVAL_SECONDS = 30


async def reaper_loop(connection_manager) -> None:
    """Periodischer Cleanup: idle Parties, abgelaufene Invites, alte Raids.
    Bei jeder Auflösung wird `group_disbanded` an die Restmitglieder gesendet
    (die ohnehin schon offline sind oder bei Reconnect den Zustand neu laden,
    aber so können online Verbliebene sofort reagieren)."""
    import asyncio
    log.info("Groups-Reaper startet (alle %ds)", REAPER_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.sleep(REAPER_INTERVAL_SECONDS)
            disbanded = await reap_idle_groups()
            for gid in disbanded:
                await connection_manager.broadcast(
                    {"type": "group_disbanded", "group_id": gid,
                     "reason": "idle_timeout"}
                )
        except asyncio.CancelledError:
            log.info("Groups-Reaper gestoppt")
            raise
        except Exception:
            log.exception("Groups-Reaper-Iteration fehlgeschlagen")


# — WS-Push-Helper (Welle 34c: aus main.py extrahiert) ———————————————————

async def group_snapshot(manager, player_id: str) -> dict | None:
    """Komplettes Group-Bild für einen Spieler (oder None wenn nicht in Gruppe)."""
    g = await get_group_for(player_id)
    if not g:
        return None
    members = await get_members(g["id"])
    member_states = []
    for m in members:
        pid = m["player_name"]
        pos = manager.get_players().get(pid)
        member_states.append({
            "name": pid,
            "role": m["role"],
            "sub_party": m["sub_party"],
            "online": pid in manager.connections,
            "x": pos["x"] if pos else None,
            "y": pos["y"] if pos else None,
        })
    return {
        "id": g["id"],
        "kind": g["kind"],
        "leader": g["leader"],
        "name": g["name"],
        "loot_rule": g["loot_rule"],
        "your_role": g["role"],
        "members": member_states,
    }


async def broadcast_to_group(manager, group_id: int, message: dict,
                              exclude: str | None = None) -> None:
    """Sendet `message` an alle online Mitglieder einer Gruppe."""
    names = await get_member_names(group_id)
    for pid in names:
        if pid == exclude:
            continue
        ws = manager.connections.get(pid)
        if ws is None:
            continue
        try:
            await ws.send_json(message)
        except Exception:
            pass


async def push_group_state(manager, player_id: str) -> None:
    """Schickt dem Spieler sein aktuelles group_state-Snapshot."""
    ws = manager.connections.get(player_id)
    if ws is None:
        return
    snap = await group_snapshot(manager, player_id)
    try:
        await ws.send_json({"type": "group_state", "group": snap})
    except Exception:
        pass


async def push_group_state_to_all_members(manager, group_id: int) -> None:
    names = await get_member_names(group_id)
    for pid in names:
        await push_group_state(manager, pid)
