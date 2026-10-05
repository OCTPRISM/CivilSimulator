"""User accounts — SQLite backed."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from ..config import get_settings
from .sqlite_db import db_lock, exec_script, get_conn

# 30 days
TOKEN_TTL_SECONDS = 30 * 86400
_SCHEMA_READY = False


def _ensure_schema() -> None:
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        exec_script("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            seed_key TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_user_sessions_user
                  ON user_sessions(user_id, created_at DESC);
        """)
        _SCHEMA_READY = True
    # M2: multiplayer membership (idempotent even after older schema loads).
    exec_script("""
    CREATE TABLE IF NOT EXISTS session_members (
        session_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        player_id TEXT NOT NULL DEFAULT '',
        seed_key TEXT NOT NULL DEFAULT '',
        joined_at REAL NOT NULL,
        PRIMARY KEY (session_id, user_id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE INDEX IF NOT EXISTS idx_session_members_user
              ON session_members(user_id, joined_at DESC);
    """)


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$", 2)
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _auth_secret() -> bytes:
    s = get_settings()
    # Stable dev secret; override via env in production
    raw = getattr(s, "auth_secret", None) or "civsim-dev-auth-secret-change-me"
    return raw.encode("utf-8")


def make_token(user_id: str) -> str:
    exp = int(time.time()) + TOKEN_TTL_SECONDS
    payload = f"{user_id}:{exp}"
    sig = hmac.new(_auth_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_token(token: str) -> str | None:
    if not token:
        return None
    try:
        user_id, exp_s, sig = token.rsplit(":", 2)
        payload = f"{user_id}:{exp_s}"
        expected = hmac.new(_auth_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(exp_s) < time.time():
            return None
        if not get_user_by_id(user_id):
            return None
        return user_id
    except Exception:
        return None


@dataclass
class User:
    id: str
    username: str
    display_name: str
    created_at: float

    def as_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "created_at": self.created_at,
        }


def _row_to_user(row: tuple) -> User:
    return User(id=row[0], username=row[1], display_name=row[3], created_at=row[4])


def create_user(username: str, password: str, display_name: str = "") -> User:
    _ensure_schema()
    username = username.strip()
    if len(username) < 3:
        raise ValueError("用户名至少 3 个字符")
    if len(password) < 6:
        raise ValueError("密码至少 6 位")
    uid = f"user_{secrets.token_hex(8)}"
    pw = _hash_password(password)
    now = time.time()
    with db_lock():
        try:
            conn = get_conn()
            conn.execute(
                "INSERT INTO users (id, username, password_hash, display_name, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (uid, username, pw, display_name.strip() or username, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("用户名已被占用")
    return User(id=uid, username=username, display_name=display_name.strip() or username, created_at=now)


def authenticate(username: str, password: str) -> User | None:
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            "SELECT id, username, password_hash, display_name, created_at "
            "FROM users WHERE username=? COLLATE NOCASE",
            (username.strip(),),
        )
        row = cur.fetchone()
    if not row or not _verify_password(password, row[2]):
        return None
    return _row_to_user(row)


def get_user_by_id(user_id: str) -> User | None:
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            "SELECT id, username, password_hash, display_name, created_at FROM users WHERE id=?",
            (user_id,),
        )
        row = cur.fetchone()
    return _row_to_user(row) if row else None


def link_session_to_user(session_id: str, user_id: str, seed_key: str = "") -> None:
    """Record host ownership (legacy table) and membership."""
    _ensure_schema()
    now = time.time()
    with db_lock():
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO user_sessions (session_id, user_id, seed_key, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, user_id, seed_key, now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO session_members "
            "(session_id, user_id, player_id, seed_key, joined_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, "", seed_key, now),
        )
        conn.commit()


def link_session_member(
    session_id: str,
    user_id: str,
    *,
    player_id: str = "",
    seed_key: str = "",
) -> None:
    """Link a joiner (or host) to a shared room without overwriting the host row."""
    _ensure_schema()
    with db_lock():
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO session_members "
            "(session_id, user_id, player_id, seed_key, joined_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, player_id, seed_key, time.time()),
        )
        conn.commit()


def list_user_sessions(user_id: str, limit: int = 20) -> list[dict]:
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            """
            SELECT session_id, seed_key, joined_at AS created_at, player_id FROM (
                SELECT session_id, seed_key, joined_at, player_id
                FROM session_members WHERE user_id=?
                UNION ALL
                SELECT session_id, seed_key, created_at AS joined_at, '' AS player_id
                FROM user_sessions WHERE user_id=?
                  AND session_id NOT IN (
                      SELECT session_id FROM session_members WHERE user_id=?
                  )
            )
            ORDER BY created_at DESC LIMIT ?
            """,
            (user_id, user_id, user_id, limit),
        )
        rows = cur.fetchall()
    return [
        {
            "session_id": r[0],
            "seed_key": r[1],
            "created_at": r[2],
            "player_id": r[3] or None,
        }
        for r in rows
    ]
