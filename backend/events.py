import db


def _row_to_dict(row) -> dict:
    return {
        "id":         row["id"],
        "kind":       row["kind"],
        "title":      row["title"],
        "body":       row["body"],
        "created_at": row["created_at"].isoformat(),
    }


class EventManager:
    async def save(self, kind: str, title: str, body: str) -> dict:
        row = await db.pool().fetchrow(
            "INSERT INTO events (kind, title, body) VALUES ($1, $2, $3) "
            "RETURNING id, kind, title, body, created_at",
            kind, title, body,
        )
        return _row_to_dict(row)

    async def recent(self, n: int = 20) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, title, body, created_at FROM events "
            "ORDER BY id DESC LIMIT $1",
            n,
        )
        # Älteste zuerst, damit das Log natürlich liest
        return [_row_to_dict(r) for r in reversed(rows)]
