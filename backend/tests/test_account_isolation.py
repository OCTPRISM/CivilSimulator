"""Cross-account isolation: generator jobs and private talk fan-out."""
from __future__ import annotations

import asyncio
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
    uname = f"iso_{tag}_{uuid.uuid4().hex[:6]}"
    r = client.post("/api/auth/register", json={
        "username": uname, "password": "iso-pass-12345", "display_name": tag,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    return body["token"], body["user"]["id"]


def test_generator_job_is_owner_scoped(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.generator import jobs as gen_jobs

    client = TestClient(app)
    a_token, a_uid = _register(client, "a")
    b_token, _b_uid = _register(client, "b")
    job_id = gen_jobs.create_job("character", "青衫书生", user_id=a_uid)

    own = client.get(
        f"/api/generator/jobs/{job_id}",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert own.status_code == 200, own.text
    assert own.json()["job_id"] == job_id

    other = client.get(
        f"/api/generator/jobs/{job_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert other.status_code == 404

    glb = client.get(
        f"/api/generator/models/{job_id}/model.glb",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert glb.status_code == 404


def test_talk_ws_stays_between_participants():
    from app.session import (
        _SESSIONS, create_session, join_session, npc_reply, subscribe, unsubscribe,
    )

    async def run():
        _SESSIONS.clear()
        sess = await create_session(
            "ancient", category_key="official", variant_key="student",
        )
        _, guest = await join_session(
            sess.id, "", category_key="merchant", variant_key="trader",
        )
        _, bystander = await join_session(
            sess.id, "", category_key="martial", variant_key="guard",
        )
        host_id = sess.primary_player_id
        assert host_id
        q_host = subscribe(sess, player_id=host_id)
        q_guest = subscribe(sess, player_id=guest.id)
        q_other = subscribe(sess, player_id=bystander.id)
        try:
            for q in (q_host, q_guest, q_other):
                while not q.empty():
                    q.get_nowait()
            await npc_reply(
                sess, npc_id=guest.id, text="兄台少停。", player_id=host_id,
            )
            host_types = []
            while not q_host.empty():
                host_types.append(q_host.get_nowait().get("type"))
            guest_types = []
            while not q_guest.empty():
                guest_types.append(q_guest.get_nowait().get("type"))
            other_types = []
            while not q_other.empty():
                other_types.append(q_other.get_nowait().get("type"))
            assert "player_dialogue" in host_types
            assert "player_dialogue" in guest_types
            assert "player_dialogue" not in other_types
        finally:
            unsubscribe(sess, q_host)
            unsubscribe(sess, q_guest)
            unsubscribe(sess, q_other)
            _SESSIONS.clear()

    asyncio.run(run())


def test_npc_talk_ws_is_speaker_only():
    from app.session import (
        _SESSIONS, create_session, join_session, npc_reply, subscribe, unsubscribe,
    )

    async def run():
        _SESSIONS.clear()
        sess = await create_session(
            "ancient", category_key="official", variant_key="student",
        )
        _, guest = await join_session(
            sess.id, "", category_key="merchant", variant_key="trader",
        )
        host_id = sess.primary_player_id
        npc = next(iter(sess.society.npcs()), None)
        assert host_id and npc
        q_host = subscribe(sess, player_id=host_id)
        q_guest = subscribe(sess, player_id=guest.id)
        try:
            while not q_host.empty():
                q_host.get_nowait()
            while not q_guest.empty():
                q_guest.get_nowait()
            await npc_reply(
                sess, npc_id=npc.id, text="今日可有新鲜鱼货？", player_id=host_id,
            )
            host_types = []
            while not q_host.empty():
                host_types.append(q_host.get_nowait().get("type"))
            guest_types = []
            while not q_guest.empty():
                guest_types.append(q_guest.get_nowait().get("type"))
            assert "npc_dialogue" in host_types
            assert "npc_dialogue" not in guest_types
        finally:
            unsubscribe(sess, q_host)
            unsubscribe(sess, q_guest)
            _SESSIONS.clear()

    asyncio.run(run())


def test_room_snapshot_does_not_leak_host_inbox():
    from app.session import (
        _SESSIONS, create_session, hydrate_player_talk_inbox, join_session,
        npc_reply, session_dict,
    )

    async def run():
        _SESSIONS.clear()
        sess = await create_session(
            "ancient", category_key="official", variant_key="student",
        )
        _, guest = await join_session(
            sess.id, "", category_key="merchant", variant_key="trader",
        )
        _, bystander = await join_session(
            sess.id, "", category_key="martial", variant_key="guard",
        )
        host_id = sess.primary_player_id
        assert host_id
        await npc_reply(sess, npc_id=guest.id, text="兄台少停。", player_id=host_id)
        host_inbox = session_dict(sess, viewer_id=host_id).get("player_talk_inbox") or []
        guest_inbox = session_dict(sess, viewer_id=guest.id).get("player_talk_inbox") or []
        other_inbox = session_dict(sess, viewer_id=bystander.id).get("player_talk_inbox") or []
        room_wide = session_dict(sess).get("player_talk_inbox") or []
        assert any(m.get("text") == "兄台少停。" for m in host_inbox)
        assert any(m.get("text") == "兄台少停。" for m in guest_inbox)
        assert not any(m.get("text") == "兄台少停。" for m in other_inbox)
        assert room_wide == []

        sess.events.append("player_dialogue", {
            "from_id": host_id,
            "from_name": "甲",
            "to_id": guest.id,
            "to_name": "乙",
            "text": "无编号旧线",
        }, tick=sess.world.clock.tick)
        sess.player_talk_inbox = {}
        setattr(sess, "_talk_inbox_hydrated", False)
        hydrate_player_talk_inbox(sess)
        first = {
            m.get("message_id")
            for m in (sess.player_talk_inbox.get(host_id) or [])
            if m.get("text") == "无编号旧线"
        }
        sess.player_talk_inbox = {}
        setattr(sess, "_talk_inbox_hydrated", False)
        hydrate_player_talk_inbox(sess)
        second = {
            m.get("message_id")
            for m in (sess.player_talk_inbox.get(host_id) or [])
            if m.get("text") == "无编号旧线"
        }
        assert first == second
        assert first
        _SESSIONS.clear()

    asyncio.run(run())


def test_http_talk_and_session_are_viewer_scoped(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits
    from app.http_contract import reset_http_idempotency

    reset_rate_limits()
    reset_http_idempotency()
    _SESSIONS.clear()
    client = TestClient(app)

    host_tok, _ = _register(client, "host")
    guest_tok, _ = _register(client, "guest")
    other_tok, _ = _register(client, "other")
    out_tok, _ = _register(client, "out")
    host_h = {"Authorization": f"Bearer {host_tok}"}
    guest_h = {"Authorization": f"Bearer {guest_tok}"}
    other_h = {"Authorization": f"Bearer {other_tok}"}
    out_h = {"Authorization": f"Bearer {out_tok}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=host_h)
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]
    host_pid = created.json()["session"]["player_id"]

    guest = client.post(f"/api/sessions/{sid}/join", json={
        "description": "",
        "category_key": "merchant",
        "variant_key": "trader",
    }, headers=guest_h)
    assert guest.status_code == 200, guest.text
    guest_pid = guest.json()["player_id"]

    bystander = client.post(f"/api/sessions/{sid}/join", json={
        "description": "",
        "category_key": "martial",
        "variant_key": "guard",
    }, headers=other_h)
    assert bystander.status_code == 200, bystander.text

    secret = "私下说一句，旁人不当听。"
    talked = client.post(
        f"/api/sessions/{sid}/talk",
        json={"npc_id": guest_pid, "text": secret, "player_id": host_pid},
        headers=host_h,
    )
    assert talked.status_code == 200, talked.text
    assert talked.json()["target_kind"] == "player"

    def inbox(headers):
        r = client.get(f"/api/sessions/{sid}", headers=headers)
        assert r.status_code == 200, r.text
        return r.json()["session"].get("player_talk_inbox") or []

    assert any(m.get("text") == secret for m in inbox(host_h))
    assert any(m.get("text") == secret for m in inbox(guest_h))
    assert not any(m.get("text") == secret for m in inbox(other_h))
    assert client.get(f"/api/sessions/{sid}", headers=out_h).status_code == 403

    replay = client.get(f"/api/sessions/{sid}/replay", headers=other_h)
    assert replay.status_code == 200, replay.text
    assert secret not in replay.text

    injected = client.post(
        f"/api/sessions/{sid}/inject/event",
        json={"tick": 999, "summary": "市集鼓声"},
        headers=other_h,
    )
    assert injected.status_code == 200, injected.text
    inj_inbox = injected.json()["session"].get("player_talk_inbox") or []
    assert not any(m.get("text") == secret for m in inj_inbox)
    assert injected.json()["session"]["player_id"] == bystander.json()["player_id"]

    _SESSIONS.clear()


def test_generator_glb_owner_sidecar_after_job_evicted(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    monkeypatch.setenv("GENERATOR_OUTPUT_DIR", str(tmp_path / "gen"))
    from app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from app.main import app
    from app.generator import jobs as gen_jobs
    from app.generator.service import _write_model_owner, output_root
    from app.layer1_foundation.rate_limit import reset_rate_limits

    reset_rate_limits()

    client = TestClient(app)
    a_token, a_uid = _register(client, "own")
    b_token, _ = _register(client, "oth")
    job_id = gen_jobs.create_job("character", "青衫", user_id=a_uid)
    out = output_root() / "models" / job_id
    out.mkdir(parents=True)
    (out / "model.glb").write_bytes(b"glb")
    _write_model_owner(out, job_id)
    gen_jobs._jobs.pop(job_id, None)

    own = client.get(
        f"/api/generator/models/{job_id}/model.glb",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert own.status_code == 200, own.text
    other = client.get(
        f"/api/generator/models/{job_id}/model.glb",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert other.status_code == 404
