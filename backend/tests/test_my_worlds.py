"""R1-1: my worlds list exposes live flag from in-memory sessions."""
from __future__ import annotations

import os
import uuid

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def _isolate_db(tmp_path, monkeypatch):
    db = tmp_path / "civsim.db"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(db))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.layer6_persistence.sqlite_db as sqlite_db
    import app.layer6_persistence.users as users
    import app.layer6_persistence.event_store as event_store
    if sqlite_db._CONN is not None:
        try:
            sqlite_db._CONN.close()
        except Exception:
            pass
        sqlite_db._CONN = None
    users._SCHEMA_READY = False
    event_store._SCHEMA_READY = False


def test_list_sessions_marks_live(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    reg = client.post("/api/auth/register", json={
        "username": f"w_{uuid.uuid4().hex[:6]}",
        "password": "worlds-pass-99",
        "display_name": "w",
    })
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=h)
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]

    listed = client.get("/api/sessions", headers=h)
    assert listed.status_code == 200
    rows = listed.json()["sessions"]
    assert any(r["session_id"] == sid and r.get("live") is True for r in rows)
    hit = next(r for r in rows if r["session_id"] == sid)
    assert hit.get("world_name")
    assert hit.get("player_id")
    assert hit.get("character_name")
    assert hit.get("short_id")
    assert len(hit["short_id"]) <= 8

    bare = client.get("/api/sessions")
    assert bare.status_code == 401

    _SESSIONS.clear()
    listed2 = client.get("/api/sessions", headers=h)
    rows2 = listed2.json()["sessions"]
    hit2 = next(r for r in rows2 if r["session_id"] == sid)
    assert hit2.get("live") is False
    assert hit2.get("world_name")  # persisted for dead rooms
    assert hit2.get("character_name")
    reset_rate_limits()
