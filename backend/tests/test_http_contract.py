"""HTTP Error envelope + Idempotency-Key (architecture §7.1–7.2)."""
from __future__ import annotations

import os
import uuid

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "http_contract.db"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("QDRANT_ENABLED", "false")
    from app.config import get_settings
    from app.layer1_foundation.factory import get_llm
    get_settings.cache_clear()
    get_llm.cache_clear()
    import app.layer6_persistence.sqlite_db as sqlite_db
    import app.layer6_persistence.event_store as event_store
    import app.layer6_persistence.users as users
    if sqlite_db._CONN is not None:
        try:
            sqlite_db._CONN.close()
        except Exception:
            pass
        sqlite_db._CONN = None
    users._SCHEMA_READY = False
    event_store._SCHEMA_READY = False
    from app.http_contract import reset_http_idempotency
    from app.layer1_foundation.rate_limit import reset_rate_limits
    from app.runtime import get_coordinator
    from app.session import _SESSIONS
    reset_http_idempotency()
    reset_rate_limits()
    get_coordinator().idempotency.clear()
    _SESSIONS.clear()


def _register_and_session(client):
    uname = f"hc_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/auth/register", json={
        "username": uname, "password": "hc-pass-12345", "display_name": "hc",
    })
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=h)
    assert created.status_code == 200, created.text
    sess = created.json()["session"]
    return h, sess["id"], sess["player_id"]


def test_unauthorized_returns_error_envelope(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/api/sessions/x/step", json={"input": "hi"})
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert body["error"]["category"] == "auth"
    assert body["error"]["retryable"] is False
    assert r.headers.get("X-Request-ID")


def test_validation_error_envelope(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    h, sid, _pid = _register_and_session(client)
    # steps must be int — send invalid type
    r = client.post(
        f"/api/sessions/{sid}/finance/advance",
        json={"steps": "not-a-number"},
        headers=h,
    )
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_FAILED"
    assert err["category"] == "validation"
    assert err.get("field_errors")


def test_idempotency_key_replays_finance_advance(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS, ensure_finance

    client = TestClient(app)
    h, sid, _pid = _register_and_session(client)
    key = f"idem_{uuid.uuid4().hex}"
    headers = {**h, "Idempotency-Key": key}

    r1 = client.post(
        f"/api/sessions/{sid}/finance/advance",
        json={"steps": 2},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["world_tick"] == 2
    assert r1.headers.get("Idempotency-Key") == key

    r2 = client.post(
        f"/api/sessions/{sid}/finance/advance",
        json={"steps": 2},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.headers.get("X-Idempotent-Replay") == "true"
    assert r2.json()["world_tick"] == b1["world_tick"] == 2
    # Clock must not have advanced again.
    sess = _SESSIONS[sid]
    assert sess.world.clock.tick == ensure_finance(sess).tick == 2


def test_idempotency_key_reuse_different_body_conflicts(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    h, sid, _pid = _register_and_session(client)
    key = f"idem_{uuid.uuid4().hex}"
    headers = {**h, "Idempotency-Key": key}

    assert client.post(
        f"/api/sessions/{sid}/finance/advance",
        json={"steps": 1},
        headers=headers,
    ).status_code == 200

    r = client.post(
        f"/api/sessions/{sid}/finance/advance",
        json={"steps": 3},
        headers=headers,
    )
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert err["category"] == "conflict"


def test_if_match_revision_conflict_envelope(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    h, sid, pid = _register_and_session(client)
    r = client.post(
        f"/api/sessions/{sid}/step",
        json={"input": "环顾四周。", "player_id": pid},
        headers={**h, "If-Match-Revision": "999"},
    )
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "SESSION_REVISION_CONFLICT"
    assert err["retryable"] is True


def test_step_idempotency_key_as_command_id(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS

    client = TestClient(app)
    h, sid, pid = _register_and_session(client)
    key = f"step_{uuid.uuid4().hex}"
    headers = {**h, "Idempotency-Key": key}
    body = {"input": "向前一步。", "player_id": pid}

    r1 = client.post(f"/api/sessions/{sid}/step", json=body, headers=headers)
    assert r1.status_code == 200, r1.text
    assert r1.json().get("command_id") == key
    rev = r1.json()["revision"]

    r2 = client.post(f"/api/sessions/{sid}/step", json=body, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.headers.get("X-Idempotent-Replay") == "true"
    assert r2.json()["revision"] == rev
    assert _SESSIONS[sid].revision == rev


def test_talk_idempotency_key_replays(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS

    client = TestClient(app)
    h, sid, pid = _register_and_session(client)
    sess = _SESSIONS[sid]
    npcs = sess.society.npcs()
    assert npcs, "seed should include NPCs"
    npc = npcs[0]
    key = f"talk_{uuid.uuid4().hex}"
    headers = {**h, "Idempotency-Key": key}
    body = {"npc_id": npc.id, "text": "你好", "player_id": pid}

    r1 = client.post(f"/api/sessions/{sid}/talk", json=body, headers=headers)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()

    r2 = client.post(f"/api/sessions/{sid}/talk", json=body, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.headers.get("X-Idempotent-Replay") == "true"
    assert r2.json() == b1


def test_use_skill_idempotency_key_replays(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    h, sid, pid = _register_and_session(client)
    sess = client.get(f"/api/sessions/{sid}", headers=h).json()["session"]
    player = next(a for a in sess["agents"] if a["id"] == pid)
    skills = player.get("skills") or []
    assert skills, "player should have basic skills"
    key = f"skill_{uuid.uuid4().hex}"
    headers = {**h, "Idempotency-Key": key}
    body = {"skill_id": skills[0]["id"], "player_id": pid}

    r1 = client.post(f"/api/sessions/{sid}/use-skill", json=body, headers=headers)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    r2 = client.post(f"/api/sessions/{sid}/use-skill", json=body, headers=headers)
    assert r2.status_code == 200
    assert r2.headers.get("X-Idempotent-Replay") == "true"
    assert r2.json()["page"] == b1["page"]
    assert r2.json()["session"]["revision"] == b1["session"]["revision"]
