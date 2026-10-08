"""v0.5 P-1: email, password reset, magic link."""
from __future__ import annotations

import os
import uuid

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("MAIL_BACKEND", "log")


def _isolate(tmp_path, monkeypatch):
    db = tmp_path / "civsim.db"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(db))
    monkeypatch.setenv("MAIL_BACKEND", "log")
    monkeypatch.setenv("PUBLIC_APP_URL", "http://localhost:3000")
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
    from app.layer1_foundation.rate_limit import reset_rate_limits
    reset_rate_limits()


def test_register_with_email_and_reset_password(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    uname = f"acc_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@example.com"
    reg = client.post("/api/auth/register", json={
        "username": uname,
        "password": "reset-pass-12345",
        "email": email,
    })
    assert reg.status_code == 200, reg.text
    assert reg.json()["user"]["email"] == email

    forgot = client.post("/api/auth/forgot-password", json={"identity": email})
    assert forgot.status_code == 200, forgot.text
    link = forgot.json().get("dev_link")
    assert link and "token=" in link
    token = link.split("token=", 1)[1]

    bad = client.post("/api/auth/login", json={
        "username": uname, "password": "wrong-pass-99999",
    })
    assert bad.status_code == 401

    reset = client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "brand-new-pass-99",
    })
    assert reset.status_code == 200, reset.text
    assert "token" in reset.json()

    ok = client.post("/api/auth/login", json={
        "username": uname, "password": "brand-new-pass-99",
    })
    assert ok.status_code == 200, ok.text


def test_magic_link_login(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    uname = f"mag_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@example.com"
    assert client.post("/api/auth/register", json={
        "username": uname,
        "password": "magic-pass-12345",
        "email": email,
    }).status_code == 200

    issued = client.post("/api/auth/magic-link", json={"identity": uname})
    assert issued.status_code == 200, issued.text
    link = issued.json()["dev_link"]
    token = link.split("token=", 1)[1]

    consumed = client.post("/api/auth/magic", json={"token": token})
    assert consumed.status_code == 200, consumed.text
    assert consumed.json()["user"]["username"] == uname

    # single-use
    again = client.post("/api/auth/magic", json={"token": token})
    assert again.status_code == 400
