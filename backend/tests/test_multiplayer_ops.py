"""v0.4 MP-1 / MP-2: room capacity + host kick / transfer."""
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


def _register(client, tag: str):
    r = client.post("/api/auth/register", json={
        "username": f"mp_{tag}_{uuid.uuid4().hex[:6]}",
        "password": "mp-pass-12345",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    return body["token"], body["user"]["id"]


def test_max_players_enforced(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    host_tok, _ = _register(client, "h")
    g1, _ = _register(client, "g1")
    g2, _ = _register(client, "g2")
    hh = {"Authorization": f"Bearer {host_tok}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
        "max_players": 2,
    }, headers=hh)
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]
    assert created.json()["session"]["max_players"] == 2

    j1 = client.post(f"/api/sessions/{sid}/join", json={"description": "旅人甲"},
                     headers={"Authorization": f"Bearer {g1}"})
    assert j1.status_code == 200, j1.text

    j2 = client.post(f"/api/sessions/{sid}/join", json={"description": "旅人乙"},
                     headers={"Authorization": f"Bearer {g2}"})
    assert j2.status_code == 400, j2.text
    assert "满" in j2.text
    reset_rate_limits()


def test_host_kick_and_transfer(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits
    from app.layer6_persistence.users import get_session_host_user_id, is_session_member

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    host_tok, host_uid = _register(client, "host")
    guest_tok, guest_uid = _register(client, "guest")
    hh = {"Authorization": f"Bearer {host_tok}"}
    gh = {"Authorization": f"Bearer {guest_tok}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
        "max_players": 4,
    }, headers=hh)
    sid = created.json()["session"]["id"]
    joined = client.post(f"/api/sessions/{sid}/join", json={"description": "客"}, headers=gh)
    assert joined.status_code == 200, joined.text
    guest_pid = joined.json()["player_id"]
    assert len(joined.json()["session"]["player_ids"]) == 2

    # Guest cannot kick
    bad = client.post(f"/api/sessions/{sid}/kick", json={"player_id": guest_pid}, headers=gh)
    assert bad.status_code == 403

    kick = client.post(f"/api/sessions/{sid}/kick", json={"player_id": guest_pid}, headers=hh)
    assert kick.status_code == 200, kick.text
    assert guest_pid not in kick.json()["session"]["player_ids"]
    assert not is_session_member(sid, guest_uid)

    # Re-join guest, then transfer host
    joined2 = client.post(f"/api/sessions/{sid}/join", json={"description": "客再来"}, headers=gh)
    assert joined2.status_code == 200, joined2.text
    xfer = client.post(
        f"/api/sessions/{sid}/transfer-host",
        json={"to_user_id": guest_uid},
        headers=hh,
    )
    assert xfer.status_code == 200, xfer.text
    assert get_session_host_user_id(sid) == guest_uid
    reset_rate_limits()


def test_max_players_api_bounds(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    tok, _ = _register(client, "bound")
    h = {"Authorization": f"Bearer {tok}"}
    low = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
        "max_players": 1,
    }, headers=h)
    assert low.status_code == 422
    high = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
        "max_players": 20,
    }, headers=h)
    assert high.status_code == 422
    reset_rate_limits()


def test_kick_close_survives_backpressure(tmp_path, monkeypatch):
    """_close must not be dropped when the subscriber queue is full."""
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS, subscribe, unsubscribe, _fanout, kick_player
    from app.layer1_foundation.rate_limit import reset_rate_limits
    from app.layer3_agents import AgentKind

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    host_tok, host_uid = _register(client, "h2")
    guest_tok, _ = _register(client, "g2")
    hh = {"Authorization": f"Bearer {host_tok}"}
    gh = {"Authorization": f"Bearer {guest_tok}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
        "max_players": 4,
    }, headers=hh)
    sid = created.json()["session"]["id"]
    joined = client.post(f"/api/sessions/{sid}/join", json={"description": "客"}, headers=gh)
    guest_pid = joined.json()["player_id"]
    sess = _SESSIONS[sid]

    q = subscribe(sess, player_id=guest_pid, maxsize=8)
    try:
        for i in range(30):
            _fanout(sess, {"type": "noise", "i": i}, from_remote=True)
        kick_player(sess, host_user_id=host_uid, target_player_id=guest_pid)
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        types = [m.get("type") for m in msgs]
        assert "player_kicked" in types, types
        assert "_close" in types, types
        assert types.index("player_kicked") < types.index("_close")
        agent = sess.society.get(guest_pid)
        assert agent is not None
        assert agent.kind == AgentKind.NPC
        assert guest_pid not in sess.player_ids
    finally:
        unsubscribe(sess, q)
    reset_rate_limits()
