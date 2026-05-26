"""Auth utilities: password hashing, signed session cookies, dependencies."""
import os
import re
from typing import Optional

from fastapi import Cookie, HTTPException, WebSocket, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

import db

SESSION_COOKIE = "liege_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _secret() -> str:
    s = os.environ.get("SESSION_SECRET")
    if not s:
        raise RuntimeError("SESSION_SECRET env var not set")
    return s


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="liege.session.v1")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _pwd.verify(password, hashed)
    except Exception:
        return False


def make_session_cookie(username: str) -> str:
    return _serializer().dumps({"u": username})


def parse_session_cookie(token: str) -> Optional[str]:
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return data.get("u")
    except (BadSignature, SignatureExpired, Exception):
        return None


def validate_username(name: str) -> None:
    if not _USERNAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="Username: 3-32 Zeichen, nur a-z A-Z 0-9 _",
        )


def validate_password(pw: str) -> None:
    if len(pw) < 8 or len(pw) > 128:
        raise HTTPException(
            status_code=400,
            detail="Passwort: 8-128 Zeichen",
        )


async def user_count() -> int:
    row = await db.pool().fetchrow(
        "SELECT COUNT(*) AS n FROM players WHERE password_hash IS NOT NULL"
    )
    return int(row["n"])


async def get_user(username: str) -> Optional[dict]:
    row = await db.pool().fetchrow(
        "SELECT name, password_hash, role FROM players WHERE name = $1",
        username,
    )
    return dict(row) if row else None


async def get_current_user(
    liege_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict:
    if not liege_session:
        raise HTTPException(status_code=401, detail="Nicht angemeldet")
    username = parse_session_cookie(liege_session)
    if not username:
        raise HTTPException(status_code=401, detail="Session ungültig oder abgelaufen")
    user = await get_user(username)
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="User existiert nicht mehr")
    return user


async def require_admin(user: dict) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin-Rechte erforderlich")
    return user


async def get_admin_user(
    liege_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict:
    user = await get_current_user(liege_session)
    return await require_admin(user)


async def get_user_from_ws(websocket: WebSocket) -> Optional[dict]:
    """Read session cookie from WS handshake; return user dict or None."""
    token = websocket.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    username = parse_session_cookie(token)
    if not username:
        return None
    user = await get_user(username)
    if not user or not user.get("password_hash"):
        return None
    return user
