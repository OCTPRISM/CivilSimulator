"""User accounts — SQLite backed."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from ..config import DEFAULT_AUTH_SECRET, get_settings
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
    _ensure_member_meta_columns()


def _ensure_member_meta_columns() -> None:
    """R1-1: persist civilization / character labels for dead-room listing."""
    with db_lock():
        conn = get_conn()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(session_members)").fetchall()}
        altered = False
        if "world_name" not in cols:
            conn.execute(
                "ALTER TABLE session_members ADD COLUMN world_name TEXT NOT NULL DEFAULT ''"
            )
            altered = True
        if "character_name" not in cols:
            conn.execute(
                "ALTER TABLE session_members ADD COLUMN character_name TEXT NOT NULL DEFAULT ''"
            )
            altered = True
        if altered:
            conn.commit()


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
    raw = getattr(s, "auth_secret", None) or DEFAULT_AUTH_SECRET
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


def _password_too_weak(password: str) -> str | None:
    """Return a Chinese error message if password is too weak, else None."""
    s = get_settings()
    min_len = max(6, int(getattr(s, "min_password_length", 8) or 8))
    if len(password) < min_len:
        return f"密码至少 {min_len} 位"
    lower = password.lower()
    weak = {
        "password", "12345678", "123456789", "qwertyui", "abcdefgh",
        "11111111", "00000000", "civsim12", "password1", "letmein1",
        "welcome1", "admin123", "passw0rd",
    }
    if lower in weak:
        return "密码过弱：请避免常见口令"
    if password.isdigit():
        return "密码过弱：请避免纯数字"
    # Reject trivial repetition (aaaaaaa1 / 1111111a) but allow long passphrases.
    if len(set(password.lower())) <= 2:
        return "密码过弱：请避免重复字符"
    return None


def create_user(username: str, password: str, display_name: str = "") -> User:
    _ensure_schema()
    username = username.strip()
    if len(username) < 3:
        raise ValueError("用户名至少 3 个字符")
    weak = _password_too_weak(password)
    if weak:
        raise ValueError(weak)
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


def link_session_to_user(
    session_id: str,
    user_id: str,
    seed_key: str = "",
    player_id: str = "",
    *,
    world_name: str = "",
    character_name: str = "",
) -> None:
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
            "(session_id, user_id, player_id, seed_key, joined_at, world_name, character_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                user_id,
                player_id or "",
                seed_key,
                now,
                world_name or "",
                character_name or "",
            ),
        )
        conn.commit()


def link_session_member(
    session_id: str,
    user_id: str,
    *,
    player_id: str = "",
    seed_key: str = "",
    world_name: str = "",
    character_name: str = "",
) -> None:
    """Link a joiner (or host) to a shared room without overwriting the host row."""
    _ensure_schema()
    with db_lock():
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO session_members "
            "(session_id, user_id, player_id, seed_key, joined_at, world_name, character_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                user_id,
                player_id or "",
                seed_key,
                time.time(),
                world_name or "",
                character_name or "",
            ),
        )
        conn.commit()


def unlink_session_membership(session_id: str, user_id: str | None = None) -> None:
    """Remove membership / host rows after a failed create (R1-3 orphan cleanup)."""
    _ensure_schema()
    with db_lock():
        conn = get_conn()
        if user_id:
            conn.execute(
                "DELETE FROM session_members WHERE session_id=? AND user_id=?",
                (session_id, user_id),
            )
            conn.execute(
                "DELETE FROM user_sessions WHERE session_id=? AND user_id=?",
                (session_id, user_id),
            )
        else:
            conn.execute("DELETE FROM session_members WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM user_sessions WHERE session_id=?", (session_id,))
        conn.commit()


def get_session_member(session_id: str, user_id: str) -> dict | None:
    """Return membership row or None."""
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            "SELECT session_id, user_id, player_id, seed_key, joined_at "
            "FROM session_members WHERE session_id=? AND user_id=?",
            (session_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            # Legacy host-only row in user_sessions
            cur = get_conn().execute(
                "SELECT session_id, user_id, seed_key, created_at "
                "FROM user_sessions WHERE session_id=? AND user_id=?",
                (session_id, user_id),
            )
            legacy = cur.fetchone()
            if not legacy:
                return None
            return {
                "session_id": legacy[0],
                "user_id": legacy[1],
                "player_id": "",
                "seed_key": legacy[2] or "",
                "joined_at": legacy[3],
            }
    return {
        "session_id": row[0],
        "user_id": row[1],
        "player_id": row[2] or "",
        "seed_key": row[3] or "",
        "joined_at": row[4],
    }


def is_session_member(session_id: str, user_id: str) -> bool:
    return get_session_member(session_id, user_id) is not None


def get_member_player_id(session_id: str, user_id: str) -> str | None:
    m = get_session_member(session_id, user_id)
    if not m:
        return None
    pid = (m.get("player_id") or "").strip()
    return pid or None


def find_member_by_player_id(session_id: str, player_id: str) -> dict | None:
    if not player_id:
        return None
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            "SELECT session_id, user_id, player_id, seed_key, joined_at "
            "FROM session_members WHERE session_id=? AND player_id=?",
            (session_id, player_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "session_id": row[0],
        "user_id": row[1],
        "player_id": row[2] or "",
        "seed_key": row[3] or "",
        "joined_at": row[4],
    }


def bind_member_player_id(session_id: str, user_id: str, player_id: str) -> None:
    """Fill empty player_id binding for an existing member (e.g. legacy host)."""
    if not player_id:
        return
    _ensure_schema()
    with db_lock():
        conn = get_conn()
        cur = conn.execute(
            "SELECT player_id FROM session_members WHERE session_id=? AND user_id=?",
            (session_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return
        if row[0]:
            return
        conn.execute(
            "UPDATE session_members SET player_id=? WHERE session_id=? AND user_id=?",
            (player_id, session_id, user_id),
        )
        conn.commit()


def list_user_sessions(user_id: str, limit: int = 20) -> list[dict]:
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            """
            SELECT session_id, seed_key, created_at, player_id, world_name, character_name FROM (
                SELECT session_id, seed_key, joined_at AS created_at, player_id,
                       world_name, character_name
                FROM session_members WHERE user_id=?
                UNION ALL
                SELECT session_id, seed_key, created_at, '' AS player_id,
                       '' AS world_name, '' AS character_name
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
            "world_name": (r[4] or "").strip() or None,
            "character_name": (r[5] or "").strip() or None,
        }
        for r in rows
    ]


def enrich_user_sessions(user_id: str, limit: int = 20) -> list[dict]:
    """Membership rows + live world metadata when the process still holds the room (R1-1)."""
    from ..session import get_session

    out: list[dict] = []
    for row in list_user_sessions(user_id, limit=limit):
        sid = row["session_id"]
        sess = get_session(sid)
        item = {
            **row,
            "live": sess is not None,
            "genre": None,
            "tick": None,
            "players": None,
            "short_id": sid[-8:] if sid else "",
        }
        if sess is not None:
            item["world_name"] = sess.world.name
            item["genre"] = sess.world.genre
            item["tick"] = sess.world.clock.tick
            item["players"] = len(sess.player_ids)
            if not item.get("seed_key"):
                item["seed_key"] = sess.seed_key or ""
            pid = item.get("player_id")
            if pid:
                player = sess.society.get(pid)
                if player:
                    item["character_name"] = player.name
        out.append(item)
    return out
