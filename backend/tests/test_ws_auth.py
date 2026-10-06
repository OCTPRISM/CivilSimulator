"""R0-2: WebSocket requires token + session membership before snapshot."""
from __future__ import annotations

import json
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


def _register(client, tag: str) -> tuple[str, str]:
    uname = f"r02_{tag}_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/auth/register", json={
        "username": uname, "password": "r02-pass-12345", "display_name": tag,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    return body["token"], body["user"]["id"]


def _recv_json(ws):
    raw = ws.receive_text()
    return json.loads(raw)


def test_ws_requires_token_and_membership(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS

    _SESSIONS.clear()
    client = TestClient(app)

    host_token, _ = _register(client, "host")
    outsider_token, _ = _register(client, "out")
    h = {"Authorization": f"Bearer {host_token}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=h)
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]
    pid = created.json()["session"]["player_id"]

    # No token → first non-auth frame rejected (server waits for hello|token)
    with client.websocket_connect(f"/ws/sessions/{sid}") as ws:
        ws.send_json({"type": "ping"})
        msg = _recv_json(ws)
        assert msg["type"] == "error"
        assert "登录" in msg["message"] or "过期" in msg["message"]

    # Bad token → error
    with client.websocket_connect(f"/ws/sessions/{sid}?token=not-a-real-token") as ws:
        msg = _recv_json(ws)
        assert msg["type"] == "error"

    # Outsider token → 非成员
    with client.websocket_connect(
        f"/ws/sessions/{sid}?token={outsider_token}&player_id={pid}"
    ) as ws:
        msg = _recv_json(ws)
        assert msg["type"] == "error"
        assert "成员" in msg["message"]

    # Host token → snapshot
    with client.websocket_connect(
        f"/ws/sessions/{sid}?token={host_token}&player_id={pid}"
    ) as ws:
        snap = _recv_json(ws)
        assert snap["type"] == "snapshot"
        assert snap["session"]["id"] == sid
        assert snap["session"]["player_id"] == pid
        ws.send_json({"type": "ping"})
        pong = _recv_json(ws)
        assert pong["type"] == "pong"

    # Hello-carried token (no query token)
    with client.websocket_connect(f"/ws/sessions/{sid}") as ws:
        ws.send_json({"type": "hello", "token": host_token, "player_id": pid})
        # May get snapshot then hello_ack
        first = _recv_json(ws)
        assert first["type"] in ("snapshot", "hello_ack")
        if first["type"] == "snapshot":
            assert first["session"]["id"] == sid
            second = _recv_json(ws)
            assert second["type"] == "hello_ack"
            assert second["player_id"] == pid
        else:
            assert first["player_id"] == pid

    _SESSIONS.clear()
