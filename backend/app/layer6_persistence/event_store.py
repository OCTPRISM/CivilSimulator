"""SQLite-backed event store + periodic snapshots.

Schema:
  events    (id, session_id, ts, kind, payload_json, tick)
  snapshots (id, session_id, ts, tick, state_json)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .sqlite_db import db_lock, exec_script, get_conn

_SCHEMA_READY = False


@dataclass
class Event:
    ts: float
    session_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    tick: int = 0


def _ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    exec_script("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        ts REAL NOT NULL,
        tick INTEGER NOT NULL,
        kind TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_events_sess_tick
              ON events(session_id, tick);
    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        ts REAL NOT NULL,
        tick INTEGER NOT NULL,
        state_json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_snap_sess_tick
              ON snapshots(session_id, tick);
    """)
    _SCHEMA_READY = True


class EventStore:
    """Append-only events for one session, plus periodic snapshots."""

    SNAPSHOT_EVERY = 5  # ticks

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        _ensure_schema()

    def append(self, kind: str, payload: dict[str, Any], tick: int = 0) -> Event:
        ev = Event(ts=time.time(), session_id=self.session_id, kind=kind,
                   payload=payload, tick=tick)
        with db_lock():
            conn = get_conn()
            conn.execute(
                "INSERT INTO events (session_id, ts, tick, kind, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (self.session_id, ev.ts, ev.tick, ev.kind,
                 json.dumps(ev.payload, ensure_ascii=False)),
            )
            conn.commit()
        return ev

    def replay(self, *, to_tick: int | None = None) -> list[Event]:
        with db_lock():
            conn = get_conn()
            cur = conn.cursor()
            if to_tick is None:
                cur.execute(
                    "SELECT ts, tick, kind, payload_json FROM events "
                    "WHERE session_id=? ORDER BY id ASC",
                    (self.session_id,),
                )
            else:
                cur.execute(
                    "SELECT ts, tick, kind, payload_json FROM events "
                    "WHERE session_id=? AND tick<=? ORDER BY id ASC",
                    (self.session_id, to_tick),
                )
            rows = cur.fetchall()
        return [Event(ts=r[0], session_id=self.session_id, tick=r[1],
                      kind=r[2], payload=json.loads(r[3])) for r in rows]

    def save_snapshot(self, tick: int, state: dict[str, Any]) -> None:
        with db_lock():
            conn = get_conn()
            conn.execute(
                "INSERT INTO snapshots (session_id, ts, tick, state_json) VALUES (?, ?, ?, ?)",
                (self.session_id, time.time(), tick,
                 json.dumps(state, ensure_ascii=False)),
            )
            conn.commit()

    def latest_snapshot(self, *, max_tick: int | None = None) -> tuple[int, dict] | None:
        with db_lock():
            conn = get_conn()
            cur = conn.cursor()
            if max_tick is None:
                cur.execute(
                    "SELECT tick, state_json FROM snapshots WHERE session_id=? "
                    "ORDER BY tick DESC LIMIT 1",
                    (self.session_id,),
                )
            else:
                cur.execute(
                    "SELECT tick, state_json FROM snapshots WHERE session_id=? AND tick<=? "
                    "ORDER BY tick DESC LIMIT 1",
                    (self.session_id, max_tick),
                )
            row = cur.fetchone()
        if not row:
            return None
        return int(row[0]), json.loads(row[1])

    def maybe_snapshot(self, tick: int, state: dict[str, Any]) -> bool:
        if tick > 0 and tick % self.SNAPSHOT_EVERY == 0:
            self.save_snapshot(tick, state)
            return True
        return False
