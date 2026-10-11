"""Session Runtime — TickCommand pipeline unit tests."""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def _isolate_db(tmp_path, monkeypatch):
    db = tmp_path / "runtime.db"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(db))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("QDRANT_ENABLED", "false")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.layer1_foundation.factory import get_llm
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


def _fresh_session(tmp_path, monkeypatch, *, with_user: bool = False):
    _isolate_db(tmp_path, monkeypatch)
    from app.session import create_session, _SESSIONS
    from app.runtime import get_coordinator

    _SESSIONS.clear()
    get_coordinator().idempotency.clear()
    user = None
    if with_user:
        from app.layer6_persistence.users import create_user
        user = create_user(
            username=f"rt_{uuid.uuid4().hex[:6]}",
            password="rt-pass-12345",
            display_name="rt",
        )
    sess = asyncio.run(create_session(
        "ancient",
        category_key="official",
        variant_key="student",
        user_id=user.id if user else None,
    ))
    return sess, user


def test_world_effect_validation_rejects_bad_relation():
    from app.runtime.effects import WorldEffect, EffectOp, validate_effects
    from app.runtime.errors import RuntimeAppError

    bad = [WorldEffect(
        op=EffectOp.ADJUST_RELATION,
        payload={"from_id": "a", "to_id": "b", "delta": 9.0},
    )]
    with pytest.raises(RuntimeAppError) as ei:
        validate_effects(bad, known_agent_ids={"a", "b"})
    assert ei.value.code.value == "VALIDATION_FAILED"


def test_event_envelope_store_and_ws_shapes():
    from app.runtime.events import EventEnvelope

    env = EventEnvelope(
        session_id="s1",
        kind="page",
        payload={"page": {"page_no": 1}},
        tick=3,
        revision=7,
        command_id="cmd_1",
        correlation_id="corr_1",
        actor_id="p1",
        effects=[{"op": "bump_revision"}],
    )
    store = env.as_store_payload()
    assert store["_envelope"]["revision"] == 7
    assert store["_envelope"]["command_id"] == "cmd_1"
    ws = env.as_ws_message()
    assert ws["type"] == "page"
    assert ws["revision"] == 7
    assert ws["event_id"].startswith("evt_")


def test_lease_serializes_holders():
    from app.runtime.leases import InProcessLeaseManager
    from app.runtime.errors import RuntimeAppError

    lm = InProcessLeaseManager(default_ttl_s=5.0)

    async def _run():
        async with lm.hold("s", owner="a"):
            with pytest.raises(RuntimeAppError) as ei:
                await lm.try_acquire("s", owner="b", wait_timeout_s=0.05)
            assert ei.value.code.value == "SESSION_BUSY"
        token = await lm.try_acquire("s", owner="b", wait_timeout_s=1.0)
        lm.release("s", token)

    asyncio.run(_run())


def test_perceive_plan_reflect_pipeline(tmp_path, monkeypatch):
    sess, _ = _fresh_session(tmp_path, monkeypatch)
    from app.runtime.perceive import perceive_for_actor
    from app.runtime.plan import plan_from_command
    from app.runtime.commands import TickCommand, TickKind
    from app.runtime.reflect import reflect_after_commit, derive_narrative_effects
    from app.runtime.effects import validate_effects

    pid = sess.primary_player_id
    assert pid
    perc = perceive_for_actor(sess, pid)
    assert perc["actor_id"] == pid
    assert "nearby_agents" in perc

    cmd = TickCommand(
        session_id=sess.id,
        kind=TickKind.NARRATIVE,
        actor_id=pid,
        payload={"input": "我环顾四周。"},
    )
    plan = plan_from_command(cmd, perc)
    assert plan["intent"] == "narrate"
    assert plan["selected"]["action"] == "player_input"

    effects = derive_narrative_effects(
        actor_id=pid,
        player_input="我环顾四周。",
        page_dict={"page_no": 1, "beats": []},
        tasks_completed=[],
    )
    known = {a.id for a in sess.society.all()}
    effects = validate_effects(
        effects,
        known_agent_ids=known,
        known_location_ids=set(sess.world.locations.keys()),
    )
    ref = reflect_after_commit(sess, cmd, perception=perc, plan=plan, effects=effects)
    assert ref["memory_written"] is True


def test_coordinator_narrative_bumps_revision_and_idempotent(tmp_path, monkeypatch):
    sess, _ = _fresh_session(tmp_path, monkeypatch)
    from app.session import step
    from app.runtime import get_coordinator
    from app.runtime.errors import RuntimeAppError

    pid = sess.primary_player_id
    assert pid
    assert sess.revision == 0

    async def run():
        page1 = await step(
            sess, player_id=pid, player_input="向前走一步。", command_id="cmd_fixed_1",
        )
        assert page1 is not None
        assert sess.revision == 1
        tick = sess._last_tick_result
        assert tick.command_id == "cmd_fixed_1"
        assert tick.perception is not None
        assert tick.plan is not None
        assert tick.event_ids

        page2 = await step(
            sess, player_id=pid, player_input="向前走一步。", command_id="cmd_fixed_1",
        )
        assert page2 is page1
        assert sess.revision == 1
        assert sess._last_tick_result.deduplicated is True

        with pytest.raises(RuntimeAppError) as ei:
            await step(
                sess,
                player_id=pid,
                player_input="再走。",
                command_id="cmd_fixed_2",
                expected_revision=99,
            )
        assert ei.value.code.value == "SESSION_REVISION_CONFLICT"

        events = sess.events.replay()
        page_events = [e for e in events if e.kind == "page"]
        assert page_events
        assert page_events[-1].payload.get("_envelope", {}).get("command_id") == "cmd_fixed_1"

    asyncio.run(run())
    get_coordinator().idempotency.clear()


def test_api_step_returns_runtime_fields(tmp_path, monkeypatch):
    sess, user = _fresh_session(tmp_path, monkeypatch, with_user=True)
    assert user is not None
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer6_persistence.users import make_token

    token = make_token(user.id)
    _SESSIONS[sess.id] = sess

    client = TestClient(app)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(
        f"/api/sessions/{sess.id}/step",
        json={
            "input": "我环顾四周。",
            "player_id": sess.primary_player_id,
            "command_id": f"api_{uuid.uuid4().hex[:8]}",
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("page")
    assert body.get("revision") == 1
    assert body.get("command_id")
    assert body.get("perception")
    assert body.get("plan")
    assert body.get("effects")
    assert body.get("session", {}).get("revision") == 1
