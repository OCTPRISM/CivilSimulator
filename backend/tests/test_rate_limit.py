"""R0-5: rate limits on register + play mutation paths."""
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
    return db


def test_register_rate_limit_returns_429(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    monkeypatch.setenv("RATE_LIMIT_REGISTER_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    from app.config import get_settings
    get_settings.cache_clear()

    from app.layer1_foundation.rate_limit import reset_rate_limits
    reset_rate_limits()

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    statuses = []
    for i in range(5):
        r = client.post("/api/auth/register", json={
            "username": f"rl_{uuid.uuid4().hex[:8]}",
            "password": "rate-limit-pass-1",
            "display_name": f"u{i}",
        })
        statuses.append(r.status_code)

    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:]
    get_settings.cache_clear()
    reset_rate_limits()


def test_play_rate_limit_on_step(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    monkeypatch.setenv("RATE_LIMIT_PLAY_PER_MINUTE", "2")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.layer1_foundation.rate_limit import reset_rate_limits
    reset_rate_limits()

    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS

    _SESSIONS.clear()
    client = TestClient(app)
    reg = client.post("/api/auth/register", json={
        "username": f"rlp_{uuid.uuid4().hex[:8]}",
        "password": "rate-limit-pass-1",
        "display_name": "host",
    })
    assert reg.status_code == 200
    token = reg.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=h)
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]
    pid = created.json()["session"]["player_id"]

    reset_rate_limits()  # fresh play bucket after setup
    codes = []
    for i in range(4):
        r = client.post(
            f"/api/sessions/{sid}/step",
            json={"input": f"看一看 {i}", "player_id": pid},
            headers=h,
        )
        codes.append(r.status_code)
    assert codes[:2] == [200, 200]
    assert 429 in codes[2:]

    _SESSIONS.clear()
    get_settings.cache_clear()
    reset_rate_limits()
