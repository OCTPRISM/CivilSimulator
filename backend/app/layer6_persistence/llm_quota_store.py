"""Shared LLM daily quota counters in SQLite (multi-worker safe)."""
from __future__ import annotations

import logging

from .sqlite_db import db_lock, exec_script, get_conn

log = logging.getLogger("civsim.llm_quota.sqlite")

_SCHEMA_READY = False


def _ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    exec_script("""
    CREATE TABLE IF NOT EXISTS llm_quota_counters (
        day_utc TEXT NOT NULL,
        kind TEXT NOT NULL,
        subject TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (day_utc, kind, subject)
    );
    """)
    _SCHEMA_READY = True


def reset_schema_flag() -> None:
    """Test helper after DB reconnect."""
    global _SCHEMA_READY
    _SCHEMA_READY = False


def bump(day_utc: str, kind: str, subject: str, limit: int) -> int:
    """Atomically increment; raise ValueError if at/over limit. Returns new count."""
    _ensure_schema()
    with db_lock():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO llm_quota_counters (day_utc, kind, subject, count) "
            "VALUES (?, ?, ?, 1) "
            "ON CONFLICT(day_utc, kind, subject) DO UPDATE SET "
            "count = llm_quota_counters.count + 1 "
            "WHERE llm_quota_counters.count < ?",
            (day_utc, kind, subject, limit),
        )
        if cur.rowcount == 0:
            raise ValueError(f"quota exceeded: {kind}/{subject}>={limit}")
        conn.commit()
        cur.execute(
            "SELECT count FROM llm_quota_counters "
            "WHERE day_utc=? AND kind=? AND subject=?",
            (day_utc, kind, subject),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 1


def get_count(day_utc: str, kind: str, subject: str) -> int:
    _ensure_schema()
    with db_lock():
        cur = get_conn().cursor()
        cur.execute(
            "SELECT count FROM llm_quota_counters "
            "WHERE day_utc=? AND kind=? AND subject=?",
            (day_utc, kind, subject),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0


def clear_all() -> None:
    """Test helper — wipe counters table."""
    _ensure_schema()
    with db_lock():
        conn = get_conn()
        conn.execute("DELETE FROM llm_quota_counters")
        conn.commit()
