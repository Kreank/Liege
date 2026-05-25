import db


def _row_to_dict(row) -> dict:
    d = {
        "id":         row["id"],
        "name":       row["name"],
        "kind":       row["kind"],
        "x":          row["x"],
        "y":          row["y"],
        "backstory":  row["backstory"],
        "mood":       row["mood"],
        "hp":         row["hp"],
        "max_hp":     row["max_hp"],
        "created_at": row["created_at"].isoformat(),
        "last_moved": row["last_moved"].isoformat(),
    }
    # Mental-State (Welle 4) — fällt durch wenn Spalte fehlt
    try:
        d["mental_state"] = row["mental_state"]
    except (KeyError, IndexError):
        d["mental_state"] = "normal"
    return d


class NPCManager:
    def __init__(self):
        self._by_id: dict[int, dict] = {}

    async def load(self) -> None:
        rows = await db.pool().fetch(
            "SELECT id, name, kind, x, y, backstory, mood, mental_state, hp, max_hp, "
            "home_x, home_y, created_at, last_moved FROM npcs"
        )
        self._by_id = {}
        for r in rows:
            d = _row_to_dict(r)
            try:
                d["home_x"] = r["home_x"]
                d["home_y"] = r["home_y"]
            except (KeyError, IndexError):
                pass
            self._by_id[r["id"]] = d

    def all(self) -> list[dict]:
        return list(self._by_id.values())

    def get(self, npc_id: int) -> dict | None:
        return self._by_id.get(npc_id)

    def count(self) -> int:
        return len(self._by_id)

    async def create(self, name: str, kind: str, x: int, y: int, backstory: str,
                     max_hp: int = 50) -> dict:
        # Spawn-Position wird Home-Position
        row = await db.pool().fetchrow(
            "INSERT INTO npcs (name, kind, x, y, backstory, hp, max_hp, home_x, home_y) "
            "VALUES ($1, $2, $3, $4, $5, $6, $6, $3, $4) "
            "RETURNING id, name, kind, x, y, backstory, mood, mental_state, hp, max_hp, "
            "created_at, last_moved",
            name, kind, x, y, backstory, max_hp,
        )
        npc = _row_to_dict(row)
        npc["home_x"] = x
        npc["home_y"] = y
        self._by_id[npc["id"]] = npc
        return npc

    async def damage(self, npc_id: int, dmg: int) -> dict | None:
        """Reduziert HP. Wenn HP ≤ 0 wird NPC gelöscht. Returnt aktuellen Stand oder None bei Tod."""
        npc = self._by_id.get(npc_id)
        if npc is None:
            return None
        new_hp = max(0, npc["hp"] - dmg)
        if new_hp == 0:
            await db.pool().execute("DELETE FROM npcs WHERE id = $1", npc_id)
            self._by_id.pop(npc_id, None)
            return None
        await db.pool().execute(
            "UPDATE npcs SET hp = $1 WHERE id = $2", new_hp, npc_id
        )
        npc["hp"] = new_hp
        return npc

    async def move(self, npc_id: int, x: int, y: int) -> bool:
        npc = self._by_id.get(npc_id)
        if npc is None:
            return False
        await db.pool().execute(
            "UPDATE npcs SET x = $1, y = $2, last_moved = NOW() WHERE id = $3",
            x, y, npc_id,
        )
        npc["x"] = x
        npc["y"] = y
        return True

    async def add_talk(self, npc_id: int, player_name: str, role: str, text: str) -> None:
        await db.pool().execute(
            "INSERT INTO talks (npc_id, player_name, role, text) VALUES ($1, $2, $3, $4)",
            npc_id, player_name, role, text,
        )

    async def recent_talks(self, npc_id: int, player_name: str, limit: int = 10) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT role, text FROM talks WHERE npc_id = $1 AND player_name = $2 "
            "ORDER BY id DESC LIMIT $3",
            npc_id, player_name, limit,
        )
        # Älteste zuerst
        return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]
