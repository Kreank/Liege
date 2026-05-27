"""Auth + admin HTTP routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

import db
from auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    get_admin_user,
    get_current_user,
    hash_password,
    make_session_cookie,
    user_count,
    validate_password,
    validate_username,
    verify_password,
)

router = APIRouter()


class Credentials(BaseModel):
    username: str
    password: str


class CreateUser(BaseModel):
    username: str
    password: str
    role: str = "user"


class UpdateRole(BaseModel):
    role: str


def _set_session(resp: Response, username: str) -> None:
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=make_session_cookie(username),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def _clear_session(resp: Response) -> None:
    resp.delete_cookie(key=SESSION_COOKIE, path="/")


@router.get("/auth/status")
async def auth_status():
    """Public: returns whether any user exists yet (used by login page)."""
    return {"has_users": (await user_count()) > 0}


@router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {"username": user["name"], "role": user["role"]}


@router.post("/auth/register")
async def auth_register(creds: Credentials, response: Response):
    """Only allowed if no users exist yet — creates the first admin.

    Race-safe: the whole check-and-insert runs in one transaction with
    a SERIALIZABLE isolation level so two concurrent first-time registrations
    cannot both succeed.
    """
    validate_username(creds.username)
    validate_password(creds.password)
    username = creds.username.lower()
    pw_hash = hash_password(creds.password)

    pool = db.pool()
    async with pool.acquire() as conn:
        async with conn.transaction(isolation="serializable"):
            n = await conn.fetchval(
                "SELECT COUNT(*) FROM players WHERE password_hash IS NOT NULL"
            )
            if int(n) > 0:
                raise HTTPException(
                    status_code=403,
                    detail="Registrierung geschlossen. Wende dich an einen Admin.",
                )
            existing = await conn.fetchrow(
                "SELECT name FROM players WHERE LOWER(name) = $1", username
            )
            if existing:
                await conn.execute(
                    "UPDATE players SET password_hash = $1, role = 'admin' "
                    "WHERE LOWER(name) = $2",
                    pw_hash, username,
                )
            else:
                await conn.execute(
                    "INSERT INTO players (name, x, y, password_hash, role) "
                    "VALUES ($1, 0, 0, $2, 'admin')",
                    username, pw_hash,
                )

    _set_session(response, username)
    return {"username": username, "role": "admin"}


@router.post("/auth/login")
async def auth_login(creds: Credentials, response: Response):
    pool = db.pool()
    row = await pool.fetchrow(
        "SELECT name, password_hash, role FROM players WHERE LOWER(name) = LOWER($1)",
        creds.username,
    )
    if not row or not row["password_hash"] or not verify_password(creds.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Username oder Passwort falsch")
    _set_session(response, row["name"])
    return {"username": row["name"], "role": row["role"]}


@router.post("/auth/logout")
async def auth_logout(response: Response):
    _clear_session(response)
    return {"ok": True}


# --- Admin ---


@router.get("/admin/users")
async def admin_list_users(_admin: dict = Depends(get_admin_user)):
    rows = await db.pool().fetch(
        "SELECT name, role, created_at, last_seen, "
        "(password_hash IS NOT NULL) AS has_password "
        "FROM players ORDER BY created_at DESC NULLS LAST, name"
    )
    return [
        {
            "username": r["name"],
            "role": r["role"] or "user",
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            "has_password": r["has_password"],
        }
        for r in rows
    ]


@router.post("/admin/users")
async def admin_create_user(data: CreateUser, _admin: dict = Depends(get_admin_user)):
    validate_username(data.username)
    validate_password(data.password)
    if data.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role muss 'user' oder 'admin' sein")

    username = data.username.lower()
    pool = db.pool()
    existing = await pool.fetchrow(
        "SELECT name, password_hash FROM players WHERE LOWER(name) = $1", username
    )
    if existing and existing["password_hash"]:
        raise HTTPException(status_code=409, detail="Username existiert bereits")

    pw_hash = hash_password(data.password)
    if existing:
        await pool.execute(
            "UPDATE players SET password_hash = $1, role = $2 WHERE LOWER(name) = $3",
            pw_hash, data.role, username,
        )
    else:
        await pool.execute(
            "INSERT INTO players (name, x, y, password_hash, role) "
            "VALUES ($1, 0, 0, $2, $3)",
            username, pw_hash, data.role,
        )
    return {"username": username, "role": data.role}


@router.patch("/admin/users/{username}")
async def admin_update_role(
    username: str,
    data: UpdateRole,
    admin: dict = Depends(get_admin_user),
):
    if data.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role muss 'user' oder 'admin' sein")
    pool = db.pool()
    row = await pool.fetchrow(
        "SELECT name FROM players WHERE LOWER(name) = LOWER($1)", username
    )
    if not row:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    canonical = row["name"]
    if canonical == admin["name"] and data.role != "admin":
        raise HTTPException(
            status_code=400,
            detail="Du kannst dir nicht selbst die Admin-Rechte entziehen",
        )
    await pool.execute(
        "UPDATE players SET role = $1 WHERE name = $2", data.role, canonical
    )
    return {"username": canonical, "role": data.role}


@router.delete("/admin/users/{username}")
async def admin_delete_user(username: str, admin: dict = Depends(get_admin_user)):
    pool = db.pool()
    row = await pool.fetchrow(
        "SELECT name FROM players WHERE LOWER(name) = LOWER($1)", username
    )
    if not row:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    canonical = row["name"]
    if canonical == admin["name"]:
        raise HTTPException(status_code=400, detail="Du kannst dich nicht selbst löschen")
    # Soft-disable: Login entfernen, Spielfortschritt erhalten
    await pool.execute(
        "UPDATE players SET password_hash = NULL, role = 'user' WHERE name = $1",
        canonical,
    )
    return {"ok": True, "soft_deleted": True}
