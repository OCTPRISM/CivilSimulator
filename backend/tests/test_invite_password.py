"""R1-5: invite-only registration + password strength."""
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


def test_auth_config_public(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    monkeypatch.setenv("INVITE_ONLY", "true")
    monkeypatch.setenv("MIN_PASSWORD_LENGTH", "10")
    from app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/auth/config")
    assert r.status_code == 200
    body = r.json()
    assert body["invite_only"] is True
    assert body["min_password_length"] == 10
    get_settings.cache_clear()


def test_invite_only_blocks_without_code(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    monkeypatch.setenv("INVITE_ONLY", "true")
    monkeypatch.setenv("INVITE_CODE", "preview-code")
    monkeypatch.setenv("MIN_PASSWORD_LENGTH", "8")
    from app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from app.main import app
    from app.layer1_foundation.rate_limit import reset_rate_limits
    reset_rate_limits()

    client = TestClient(app)
    denied = client.post("/api/auth/register", json={
        "username": f"inv_{uuid.uuid4().hex[:6]}",
        "password": "good-pass-99",
    })
    assert denied.status_code == 403

    ok = client.post("/api/auth/register", json={
        "username": f"inv_{uuid.uuid4().hex[:6]}",
        "password": "good-pass-99",
        "invite_code": "preview-code",
    })
    assert ok.status_code == 200, ok.text
    get_settings.cache_clear()
    reset_rate_limits()


def test_weak_password_rejected(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    monkeypatch.setenv("INVITE_ONLY", "false")
    monkeypatch.setenv("MIN_PASSWORD_LENGTH", "8")
    from app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from app.main import app
    from app.layer1_foundation.rate_limit import reset_rate_limits
    reset_rate_limits()

    client = TestClient(app)
    weak = client.post("/api/auth/register", json={
        "username": f"wk_{uuid.uuid4().hex[:6]}",
        "password": "12345678",
    })
    assert weak.status_code == 400

    # Long alphabetic passphrase should be allowed (not blanket-rejected).
    ok = client.post("/api/auth/register", json={
        "username": f"ok_{uuid.uuid4().hex[:6]}",
        "password": "CorrectHorseBattery",
    })
    assert ok.status_code == 200, ok.text
    get_settings.cache_clear()
    reset_rate_limits()


def test_production_forces_invite_only(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("AUTH_SECRET", "prod-secret-for-tests-only-32b")
    monkeypatch.setenv("INVITE_ONLY", "false")
    monkeypatch.setenv("INVITE_CODE", "prod-invite")
    monkeypatch.setenv("MIN_PASSWORD_LENGTH", "8")
    from app.config import get_settings, effective_invite_only, assert_invite_config_safe
    get_settings.cache_clear()
    s = get_settings()
    assert effective_invite_only(s) is True
    assert_invite_config_safe(s)

    from fastapi.testclient import TestClient
    from app.main import app
    from app.layer1_foundation.rate_limit import reset_rate_limits
    reset_rate_limits()
    client = TestClient(app)
    cfg = client.get("/api/auth/config").json()
    assert cfg["invite_only"] is True
    denied = client.post("/api/auth/register", json={
        "username": f"p_{uuid.uuid4().hex[:6]}",
        "password": "good-pass-99",
    })
    assert denied.status_code == 403
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "development")
    get_settings.cache_clear()
    reset_rate_limits()
