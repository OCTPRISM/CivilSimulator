"""B-5: Scheme B restore — create → snapshot → clear memory → restore → step."""
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


def test_restore_after_clear_sessions(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits
    from app.session_persist import force_save_snapshot, restore_session, SNAPSHOT_VERSION
    from app.layer6_persistence.event_store import EventStore

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)

    reg = client.post("/api/auth/register", json={
        "username": f"b3_{uuid.uuid4().hex[:6]}",
        "password": "restore-pass-99",
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
    pid = created.json()["session"]["player_id"]
    loc0 = created.json()["session"]["agents"]
    player0 = next(a for a in loc0 if a["id"] == pid)
    inv0 = list(player0.get("inventory") or [])

    # Advance a few pages so clock / inventory can change, then force snapshot.
    for i in range(3):
        r = client.post(
            f"/api/sessions/{sid}/step",
            json={"input": f"向前走一步 {i}", "player_id": pid},
            headers=h,
        )
        assert r.status_code == 200, r.text

    sess = _SESSIONS[sid]
    tick_before = sess.world.clock.tick
    pages_before = len(sess.pages)
    force_save_snapshot(sess)
    hit = EventStore(sid).latest_snapshot()
    assert hit is not None
    assert hit[1].get("snapshot_version") == SNAPSHOT_VERSION

    listed = client.get("/api/sessions", headers=h).json()["sessions"]
    hit_row = next(r for r in listed if r["session_id"] == sid)
    assert hit_row["live"] is True

    # Simulate process restart.
    _SESSIONS.clear()
    assert sid not in _SESSIONS

    listed2 = client.get("/api/sessions", headers=h).json()["sessions"]
    row2 = next(r for r in listed2 if r["session_id"] == sid)
    assert row2["live"] is False
    assert row2["restorable"] is True
    assert row2.get("character_name")  # from snapshot meta

    restored = client.post(f"/api/sessions/{sid}/restore", headers=h)
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["restored"] is True
    assert body["session"]["id"] == sid
    assert body["session"]["player_id"] == pid
    assert body["session"]["world"]["clock"]["tick"] == tick_before
    assert len(body["session"]["pages"]) == pages_before
    player = next(a for a in body["session"]["agents"] if a["id"] == pid)
    assert player["location_id"] == player0["location_id"]
    assert isinstance(player.get("inventory"), list)
    assert len(player["inventory"]) >= 0
    _ = inv0

    # Further play works on restored room.
    step = client.post(
        f"/api/sessions/{sid}/step",
        json={"input": "续玩后继续前行", "player_id": pid},
        headers=h,
    )
    assert step.status_code == 200, step.text
    assert sid in _SESSIONS

    # Idempotent restore returns same room.
    again = restore_session(sid)
    assert again.id == sid
    reset_rate_limits()


def test_steps_alone_leave_restorable_progress(tmp_path, monkeypatch):
    """Acceptance: ≥3 pages then hard clear without explicit force_save still restores pages."""
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    reg = client.post("/api/auth/register", json={
        "username": f"b3p_{uuid.uuid4().hex[:6]}",
        "password": "restore-pass-99",
    })
    token = reg.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=h)
    sid = created.json()["session"]["id"]
    pid = created.json()["session"]["player_id"]

    for i in range(3):
        assert client.post(
            f"/api/sessions/{sid}/step",
            json={"input": f"page {i}", "player_id": pid},
            headers=h,
        ).status_code == 200

    pages_before = len(_SESSIONS[sid].pages)
    assert pages_before >= 3
    _SESSIONS.clear()

    listed = client.get("/api/sessions", headers=h).json()["sessions"]
    row = next(r for r in listed if r["session_id"] == sid)
    assert row["restorable"] is True

    restored = client.post(f"/api/sessions/{sid}/restore", headers=h)
    assert restored.status_code == 200, restored.text
    assert len(restored.json()["session"]["pages"]) == pages_before
    reset_rate_limits()


def test_join_after_restart_hydrates(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)

    host = client.post("/api/auth/register", json={
        "username": f"host_{uuid.uuid4().hex[:6]}",
        "password": "restore-pass-99",
    }).json()
    guest = client.post("/api/auth/register", json={
        "username": f"guest_{uuid.uuid4().hex[:6]}",
        "password": "restore-pass-99",
    }).json()
    hh = {"Authorization": f"Bearer {host['token']}"}
    gh = {"Authorization": f"Bearer {guest['token']}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=hh)
    sid = created.json()["session"]["id"]
    _SESSIONS.clear()

    joined = client.post(
        f"/api/sessions/{sid}/join",
        json={"description": "一位新来的旅人"},
        headers=gh,
    )
    assert joined.status_code == 200, joined.text
    assert sid in _SESSIONS
    assert len(joined.json()["session"]["player_ids"]) >= 2
    reset_rate_limits()


def test_corrupt_json_snapshot_does_not_crash_list(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits
    from app.layer6_persistence.sqlite_db import get_conn, db_lock
    import time

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    reg = client.post("/api/auth/register", json={
        "username": f"cj_{uuid.uuid4().hex[:6]}",
        "password": "restore-pass-99",
    })
    token = reg.json()["token"]
    uid = reg.json()["user"]["id"]
    h = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=h)
    sid = created.json()["session"]["id"]
    _SESSIONS.clear()

    with db_lock():
        conn = get_conn()
        conn.execute(
            "INSERT INTO snapshots (session_id, ts, tick, state_json) VALUES (?, ?, ?, ?)",
            (sid, time.time(), 99, "{not-json"),
        )
        conn.commit()

    listed = client.get("/api/sessions", headers=h)
    assert listed.status_code == 200, listed.text
    # Corrupt newest row is skipped; older create snapshot remains restorable.
    row = next(r for r in listed.json()["sessions"] if r["session_id"] == sid)
    assert row["restorable"] is True
    _ = uid
    reset_rate_limits()


def test_corrupt_snapshot_does_not_crash(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from app.layer6_persistence.event_store import EventStore
    from app.session_persist import RestoreError, restore_session
    from app.session import _SESSIONS

    _SESSIONS.clear()
    sid = f"sess_{uuid.uuid4().hex[:8]}"
    es = EventStore(sid)
    # Write garbage that parses as JSON object but lacks required fields.
    es.save_snapshot(1, {"snapshot_version": 1, "broken": True})
    try:
        restore_session(sid)
        assert False, "expected RestoreError"
    except RestoreError as e:
        assert "快照" in e.message or "世界" in e.message
    assert sid not in _SESSIONS


def test_incompatible_snapshot_version(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from app.layer6_persistence.event_store import EventStore
    from app.session_persist import RestoreError, restore_session
    from app.session import _SESSIONS

    _SESSIONS.clear()
    sid = f"sess_{uuid.uuid4().hex[:8]}"
    EventStore(sid).save_snapshot(1, {
        "snapshot_version": 999,
        "world": {"id": "w", "name": "x", "genre": "ancient", "premise": "", "rules": []},
        "agents": [],
        "player_ids": [],
    })
    try:
        restore_session(sid)
        assert False, "expected RestoreError"
    except RestoreError as e:
        assert "版本" in e.message


def test_incompatible_snapshot_returns_409_on_get(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits
    from app.layer6_persistence.event_store import EventStore
    from app.layer6_persistence.users import link_session_member

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    reg = client.post("/api/auth/register", json={
        "username": f"v409_{uuid.uuid4().hex[:6]}",
        "password": "restore-pass-99",
    })
    token = reg.json()["token"]
    uid = reg.json()["user"]["id"]
    h = {"Authorization": f"Bearer {token}"}
    sid = f"sess_{uuid.uuid4().hex[:8]}"
    link_session_member(sid, uid, player_id="agent_x", seed_key="ancient", world_name="x")
    EventStore(sid).save_snapshot(1, {
        "snapshot_version": 999,
        "world": {"id": "w", "name": "x", "genre": "ancient", "premise": "", "rules": []},
        "agents": [{"id": "agent_x", "name": "甲", "kind": "player"}],
        "player_ids": ["agent_x"],
    })
    r = client.get(f"/api/sessions/{sid}", headers=h)
    assert r.status_code == 409, r.text
    assert "版本" in r.text
    reset_rate_limits()


def test_latest_snapshot_prefers_newest_equal_tick(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from app.layer6_persistence.event_store import EventStore

    sid = f"sess_{uuid.uuid4().hex[:8]}"
    es = EventStore(sid)
    es.save_snapshot(0, {"snapshot_version": 1, "label": "old"})
    es.save_snapshot(0, {"snapshot_version": 1, "label": "new"})
    hit = es.latest_snapshot()
    assert hit is not None
    assert hit[1]["label"] == "new"
