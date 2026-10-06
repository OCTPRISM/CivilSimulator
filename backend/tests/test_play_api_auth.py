"""R0-1: Play HTTP APIs require login + session membership."""
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


def _register(client, tag: str) -> tuple[str, str]:
    uname = f"r01_{tag}_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/auth/register", json={
        "username": uname, "password": "r01-pass-12345", "display_name": tag,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    return body["token"], body["user"]["id"]


def test_step_requires_auth_and_membership(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS

    _SESSIONS.clear()
    client = TestClient(app)

    host_token, _host_uid = _register(client, "host")
    outsider_token, _out_uid = _register(client, "out")
    h = {"Authorization": f"Bearer {host_token}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=h)
    assert created.status_code == 200, created.text
    sess = created.json()["session"]
    sid = sess["id"]
    pid = sess["player_id"]
    assert sid and pid

    # No token → 401
    bare = client.post(f"/api/sessions/{sid}/step", json={"input": "向前走", "player_id": pid})
    assert bare.status_code == 401

    # Outsider with token → 403
    out_h = {"Authorization": f"Bearer {outsider_token}"}
    denied = client.post(
        f"/api/sessions/{sid}/step",
        json={"input": "偷听", "player_id": pid},
        headers=out_h,
    )
    assert denied.status_code == 403

    # Get session also gated
    assert client.get(f"/api/sessions/{sid}").status_code == 401
    assert client.get(f"/api/sessions/{sid}", headers=out_h).status_code == 403

    # Member OK
    ok = client.post(
        f"/api/sessions/{sid}/step",
        json={"input": "我环顾四周。", "player_id": pid},
        headers=h,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json().get("page")

    # Heartbeat
    hb = client.post(
        f"/api/sessions/{sid}/heartbeat",
        json={"player_id": pid},
        headers=h,
    )
    assert hb.status_code == 200

    # Finance mutation gated
    assert client.post(
        f"/api/sessions/{sid}/finance/advance",
        json={"steps": 1},
    ).status_code == 401
    fin = client.post(
        f"/api/sessions/{sid}/finance/advance",
        json={"steps": 1},
        headers=h,
    )
    assert fin.status_code == 200, fin.text

    # Guest joins then can step as self; cannot hijack host player_id
    join = client.post(
        f"/api/sessions/{sid}/join",
        json={"description": "路过的胡商。"},
        headers=out_h,
    )
    assert join.status_code == 200, join.text
    guest_pid = join.json()["player_id"]
    assert guest_pid != pid

    hijack = client.post(
        f"/api/sessions/{sid}/step",
        json={"input": "冒充房主", "player_id": pid},
        headers=out_h,
    )
    assert hijack.status_code == 403

    guest_ok = client.post(
        f"/api/sessions/{sid}/step",
        json={"input": "打听米价。", "player_id": guest_pid},
        headers=out_h,
    )
    assert guest_ok.status_code == 200, guest_ok.text

    _SESSIONS.clear()
