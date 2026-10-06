"""R0 join integrity: idempotent re-join + invite preview."""
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


def test_join_idempotent_and_invite_preview(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)

    host = client.post("/api/auth/register", json={
        "username": f"h_{uuid.uuid4().hex[:6]}",
        "password": "join-pass-99",
    })
    assert host.status_code == 200
    host_h = {"Authorization": f"Bearer {host.json()['token']}"}
    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=host_h)
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]

    guest = client.post("/api/auth/register", json={
        "username": f"g_{uuid.uuid4().hex[:6]}",
        "password": "join-pass-99",
    })
    assert guest.status_code == 200
    guest_h = {"Authorization": f"Bearer {guest.json()['token']}"}

    preview = client.get(f"/api/sessions/{sid}/invite", headers=guest_h)
    assert preview.status_code == 200
    assert preview.json()["world_name"]
    assert preview.json()["already_member"] is False

    # Non-member cannot get full session, but invite preview works.
    assert client.get(f"/api/sessions/{sid}", headers=guest_h).status_code == 403

    j1 = client.post(f"/api/sessions/{sid}/join", json={
        "description": "一位过路旅人",
    }, headers=guest_h)
    assert j1.status_code == 200, j1.text
    pid1 = j1.json()["player_id"]

    j2 = client.post(f"/api/sessions/{sid}/join", json={
        "description": "另一段描述不应再生角色",
    }, headers=guest_h)
    assert j2.status_code == 200, j2.text
    assert j2.json()["player_id"] == pid1

    sess = _SESSIONS[sid]
    guest_players = [p for p in sess.player_ids if p == pid1]
    assert len(guest_players) == 1

    preview2 = client.get(f"/api/sessions/{sid}/invite", headers=guest_h)
    assert preview2.json()["already_member"] is True
    reset_rate_limits()
