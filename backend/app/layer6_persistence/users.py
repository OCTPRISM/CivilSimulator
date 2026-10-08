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
    _ensure_auth_email_and_tokens()


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


def _ensure_auth_email_and_tokens() -> None:
    """v0.5 P-1: optional email + single-use auth tokens (reset / magic / verify)."""
    with db_lock():
        conn = get_conn()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        altered = False
        if "email" not in cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''"
            )
            altered = True
        if "email_verified_at" not in cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN email_verified_at REAL"
            )
            altered = True
        if altered:
            conn.commit()
    exec_script("""
    CREATE TABLE IF NOT EXISTS auth_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        purpose TEXT NOT NULL,
        expires_at REAL NOT NULL,
        used_at REAL,
        created_at REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE INDEX IF NOT EXISTS idx_auth_tokens_user
              ON auth_tokens(user_id, purpose);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_nonempty
              ON users(email) WHERE email != '';
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
    email: str = ""
    email_verified_at: float | None = None

    def as_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "created_at": self.created_at,
            "email": self.email or "",
            "email_verified": bool(self.email_verified_at),
        }


def _row_to_user(row: tuple) -> User:
    # (id, username, password_hash, display_name, created_at[, email, email_verified_at])
    email = row[5] if len(row) > 5 else ""
    verified = row[6] if len(row) > 6 else None
    return User(
        id=row[0],
        username=row[1],
        display_name=row[3],
        created_at=row[4],
        email=email or "",
        email_verified_at=verified,
    )


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _valid_email(email: str) -> bool:
    if not email or len(email) > 254 or " " in email:
        return False
    if email.count("@") != 1:
        return False
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain


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


def create_user(
    username: str,
    password: str,
    display_name: str = "",
    email: str = "",
) -> User:
    _ensure_schema()
    username = username.strip()
    if len(username) < 3:
        raise ValueError("用户名至少 3 个字符")
    email_n = _normalize_email(email)
    if email_n and not _valid_email(email_n):
        raise ValueError("邮箱格式无效")
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
                "INSERT INTO users "
                "(id, username, password_hash, display_name, created_at, email, email_verified_at) "
                "VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (uid, username, pw, display_name.strip() or username, now, email_n),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            msg = str(exc).lower()
            if "email" in msg:
                raise ValueError("邮箱已被占用") from exc
            raise ValueError("用户名已被占用") from exc
    return User(
        id=uid,
        username=username,
        display_name=display_name.strip() or username,
        created_at=now,
        email=email_n,
    )


_USER_SELECT = (
    "SELECT id, username, password_hash, display_name, created_at, "
    "COALESCE(email, ''), email_verified_at FROM users "
)


def authenticate(username: str, password: str) -> User | None:
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            _USER_SELECT + "WHERE username=? COLLATE NOCASE",
            (username.strip(),),
        )
        row = cur.fetchone()
    if not row or not _verify_password(password, row[2]):
        return None
    return _row_to_user(row)


def get_user_by_id(user_id: str) -> User | None:
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(_USER_SELECT + "WHERE id=?", (user_id,))
        row = cur.fetchone()
    return _row_to_user(row) if row else None


def find_user_by_username_or_email(identity: str) -> User | None:
    _ensure_schema()
    text = (identity or "").strip()
    if not text:
        return None
    email = _normalize_email(text)
    with db_lock():
        conn = get_conn()
        cur = conn.execute(
            _USER_SELECT + "WHERE username=? COLLATE NOCASE",
            (text,),
        )
        row = cur.fetchone()
        if not row and "@" in email:
            cur = conn.execute(_USER_SELECT + "WHERE email=?", (email,))
            row = cur.fetchone()
    return _row_to_user(row) if row else None


def _hash_auth_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_auth_token(user_id: str, purpose: str, *, ttl_seconds: int) -> str:
    """Create a single-use opaque token; returns the raw token (show once)."""
    _ensure_schema()
    if purpose not in ("reset", "magic", "verify"):
        raise ValueError("invalid token purpose")
    raw = secrets.token_urlsafe(32)
    th = _hash_auth_token(raw)
    now = time.time()
    with db_lock():
        conn = get_conn()
        # Invalidate prior unused tokens of the same purpose.
        conn.execute(
            "UPDATE auth_tokens SET used_at=? "
            "WHERE user_id=? AND purpose=? AND used_at IS NULL",
            (now, user_id, purpose),
        )
        conn.execute(
            "INSERT INTO auth_tokens "
            "(token_hash, user_id, purpose, expires_at, used_at, created_at) "
            "VALUES (?, ?, ?, ?, NULL, ?)",
            (th, user_id, purpose, now + ttl_seconds, now),
        )
        conn.commit()
    return raw


def consume_auth_token(raw: str, purpose: str) -> User | None:
    """Validate + mark used. Returns user or None."""
    _ensure_schema()
    th = _hash_auth_token((raw or "").strip())
    now = time.time()
    with db_lock():
        conn = get_conn()
        cur = conn.execute(
            "SELECT user_id, expires_at, used_at FROM auth_tokens "
            "WHERE token_hash=? AND purpose=?",
            (th, purpose),
        )
        row = cur.fetchone()
        if not row:
            return None
        user_id, expires_at, used_at = row
        if used_at is not None or float(expires_at) < now:
            return None
        conn.execute(
            "UPDATE auth_tokens SET used_at=? WHERE token_hash=?",
            (now, th),
        )
        if purpose == "verify":
            conn.execute(
                "UPDATE users SET email_verified_at=? WHERE id=?",
                (now, user_id),
            )
        conn.commit()
    return get_user_by_id(user_id)


def set_password(user_id: str, new_password: str) -> None:
    weak = _password_too_weak(new_password)
    if weak:
        raise ValueError(weak)
    _ensure_schema()
    pw = _hash_password(new_password)
    with db_lock():
        conn = get_conn()
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (pw, user_id),
        )
        conn.commit()


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


def get_session_host_user_id(session_id: str) -> str | None:
    """Host is the owner row in user_sessions (created the room)."""
    _ensure_schema()
    with db_lock():
        conn = get_conn()
        row = conn.execute(
            "SELECT user_id FROM user_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
    return row[0] if row else None


def transfer_session_host(session_id: str, *, from_user_id: str, to_user_id: str) -> None:
    """Move host ownership row; keep both as members."""
    _ensure_schema()
    now = time.time()
    with db_lock():
        conn = get_conn()
        row = conn.execute(
            "SELECT seed_key FROM user_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        seed_key = row[0] if row else ""
        conn.execute("DELETE FROM user_sessions WHERE session_id=?", (session_id,))
        conn.execute(
            "INSERT INTO user_sessions (session_id, user_id, seed_key, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, to_user_id, seed_key, now),
        )
        # Ensure both remain members.
        for uid in (from_user_id, to_user_id):
            exists = conn.execute(
                "SELECT 1 FROM session_members WHERE session_id=? AND user_id=?",
                (session_id, uid),
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO session_members "
                    "(session_id, user_id, player_id, seed_key, joined_at, world_name, character_name) "
                    "VALUES (?, ?, '', ?, ?, '', '')",
                    (session_id, uid, seed_key, now),
                )
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
    """Membership rows + live / restorable metadata (R1-1 / B-3)."""
    from ..session import get_session
    from ..session_persist import latest_snapshot_meta

    out: list[dict] = []
    for row in list_user_sessions(user_id, limit=limit):
        sid = row["session_id"]
        sess = get_session(sid)
        item = {
            **row,
            "live": sess is not None,
            "restorable": False,
            "snapshot_tick": None,
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
        else:
            try:
                meta = latest_snapshot_meta(sid)
            except Exception:
                meta = None
            if meta and meta.get("compatible"):
                item["restorable"] = True
                item["snapshot_tick"] = meta.get("tick")
                if not item.get("world_name"):
                    item["world_name"] = meta.get("world_name")
                if not item.get("seed_key") and meta.get("seed_key"):
                    item["seed_key"] = meta["seed_key"]
                if not item.get("character_name") and meta.get("character_name"):
                    item["character_name"] = meta["character_name"]
                if meta.get("genre"):
                    item["genre"] = meta["genre"]
                item["tick"] = meta.get("tick")
                item["players"] = len(meta.get("player_ids") or []) or None
        out.append(item)
    return out
