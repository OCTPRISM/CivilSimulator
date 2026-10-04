"""Shared SQLite connection for users + event store.

Both modules previously opened separate connections to the same file; concurrent
writes then surfaced as ``database is locked``. One process-wide connection,
WAL mode, and a busy timeout keep auth and session writes from colliding.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from ..config import get_settings

_DB_LOCK = threading.RLock()
_CONN: sqlite3.Connection | None = None


def db_lock() -> threading.RLock:
    return _DB_LOCK


def get_conn() -> sqlite3.Connection:
    global _CONN
    with _DB_LOCK:
        if _CONN is None:
            s = get_settings()
            Path(s.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            _CONN = sqlite3.connect(
                s.sqlite_path,
                check_same_thread=False,
                timeout=30.0,
            )
            _CONN.execute("PRAGMA journal_mode=WAL")
            _CONN.execute("PRAGMA busy_timeout=30000")
            _CONN.execute("PRAGMA synchronous=NORMAL")
            _CONN.execute("PRAGMA foreign_keys=ON")
        return _CONN


def exec_script(script: str) -> None:
    with _DB_LOCK:
        get_conn().executescript(script)
        get_conn().commit()
