"""Unified WORLD_HOUR: world clock and finance tick advance together."""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def _fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "uh.db"))
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
    from app.session import create_session, _SESSIONS, ensure_finance
    from app.runtime import get_coordinator
    _SESSIONS.clear()
    get_coordinator().idempotency.clear()
    sess = asyncio.run(create_session(
        "ancient", category_key="official", variant_key="student",
    ))
    ensure_finance(sess)
    return sess


def test_finance_advance_keeps_clocks_in_sync(tmp_path, monkeypatch):
    sess = _fresh(tmp_path, monkeypatch)
    from app.session import run_finance_ticks, ensure_finance

    fin = ensure_finance(sess)
    assert sess.world.clock.tick == 0
    assert fin.tick == 0

    out = asyncio.run(run_finance_ticks(sess, 5))
    assert out["unified"] is True
    assert out["in_sync"] is True
    assert out["world_tick"] == 5
    assert out["finance_tick"] == 5
    assert sess.world.clock.tick == fin.tick == 5
    assert sess.revision >= 1


def test_advance_world_hours_idempotent_command(tmp_path, monkeypatch):
    sess = _fresh(tmp_path, monkeypatch)
    from app.session import advance_world_hours, ensure_finance

    async def run():
        a = await advance_world_hours(sess, 2, command_id="wh_fixed")
        b = await advance_world_hours(sess, 2, command_id="wh_fixed")
        assert a["world_tick"] == 2
        assert b["world_tick"] == 2
        assert sess.world.clock.tick == ensure_finance(sess).tick == 2

    asyncio.run(run())


def test_align_heals_diverged_clocks(tmp_path, monkeypatch):
    sess = _fresh(tmp_path, monkeypatch)
    from app.runtime.world_hour import align_finance_to_world, commit_world_hours_locked
    from app.session import ensure_finance

    fin = ensure_finance(sess)
    # Simulate legacy dual-loop drift: finance ahead.
    fin.advance(sess.world, sess.society)
    fin.advance(sess.world, sess.society)
    assert fin.tick == 2
    assert sess.world.clock.tick == 0

    info = align_finance_to_world(sess)
    assert info["action"] == "catch_up_world"
    assert sess.world.clock.tick == fin.tick == 2

    # Finance behind.
    sess.world.clock.advance(3)
    info2 = align_finance_to_world(sess)
    assert info2["action"] == "catch_up_finance"
    assert sess.world.clock.tick == fin.tick

    commit_world_hours_locked(sess, 1)
    assert sess.world.clock.tick == fin.tick


def test_skip_to_tick_stays_in_sync(tmp_path, monkeypatch):
    sess = _fresh(tmp_path, monkeypatch)
    from app.session import skip_to_tick, ensure_finance

    out = asyncio.run(skip_to_tick(sess, 4))
    assert out["tick"] == 4
    assert out["in_sync"] is True
    assert sess.world.clock.tick == ensure_finance(sess).tick == 4


def test_apply_live_tick_does_not_advance_clock(tmp_path, monkeypatch):
    sess = _fresh(tmp_path, monkeypatch)
    from app.layer2_civilization.live_simulation import LiveTickResult, apply_live_tick

    before = sess.world.clock.tick
    result = LiveTickResult(
        decisions=[],
        events=[],
        environment="薄雾",
        reasoning="test",
        model="mock",
    )
    apply_live_tick(result, {}, sess.world, sess.society, sess.director.stats, sess.memory)
    assert sess.world.clock.tick == before


def test_world_hour_fires_injection_and_records_events(tmp_path, monkeypatch):
    sess = _fresh(tmp_path, monkeypatch)
    from app.session import advance_world_hours, ensure_finance
    from unittest.mock import MagicMock

    summary = "城东突发粮荒告示"
    # Schedule at current tick so the next WORLD_HOUR's process_injections fires it.
    sess.injections.schedule_event(sess.world.clock.tick, summary=summary, importance=0.9)

    schedules = MagicMock()
    monkeypatch.setattr(sess.society, "advance_schedules", schedules)

    out = asyncio.run(advance_world_hours(sess, 1))
    assert out["in_sync"] is True
    assert sess.world.clock.tick == ensure_finance(sess).tick == 1
    schedules.assert_called()
    assert any(summary in (f or "") for f in sess.world.facts)

    kinds = [e.kind for e in sess.events.replay()]
    assert "injection_fired" in kinds or "world_event" in kinds
    assert "finance_event" in kinds or "world_hour" in kinds
    assert "world_hour" in kinds


def test_hours_clamped_to_zero_and_168(tmp_path, monkeypatch):
    sess = _fresh(tmp_path, monkeypatch)
    from app.runtime.world_hour import commit_world_hours_locked
    from app.session import ensure_finance

    fin = ensure_finance(sess)
    before = sess.world.clock.tick
    zero = commit_world_hours_locked(sess, 0)
    assert zero["hours"] == 0
    assert sess.world.clock.tick == before == fin.tick

    # 200 → clamped to 168
    big = commit_world_hours_locked(sess, 200)
    assert big["hours"] == 168
    assert sess.world.clock.tick == fin.tick == before + 168


def test_background_pass_advances_hour_then_llm_without_double_clock(
    tmp_path, monkeypatch,
):
    sess = _fresh(tmp_path, monkeypatch)
    from app.session import _background_session_pass, ensure_finance
    from app.runtime import get_coordinator

    get_coordinator().idempotency.clear()
    calls: list[str] = []
    real_advance = __import__("app.session", fromlist=["advance_world_hours"]).advance_world_hours
    real_llm = __import__("app.session", fromlist=["run_background_tick"]).run_background_tick

    async def wrap_advance(s, hours=1, **kwargs):
        calls.append(f"hour@{s.world.clock.tick}")
        return await real_advance(s, hours, **kwargs)

    async def wrap_llm(s):
        calls.append(f"llm@{s.world.clock.tick}")
        # Ensure LLM path does not move clocks.
        before_w = s.world.clock.tick
        before_f = ensure_finance(s).tick
        n = await real_llm(s)
        assert s.world.clock.tick == before_w
        assert ensure_finance(s).tick == before_f
        return n

    monkeypatch.setattr("app.session.advance_world_hours", wrap_advance)
    monkeypatch.setattr("app.session.run_background_tick", wrap_llm)

    # Keep player active so presence timeout does not interfere.
    pid = sess.primary_player_id
    assert pid
    player = sess.society.get(pid)
    player.last_heartbeat_ts = 1e12

    out = asyncio.run(_background_session_pass(sess, now=0.0, timeout=9999.0))
    assert out["hour_ok"] is True
    assert out["llm_ran"] is True
    assert out["world_tick"] == out["finance_tick"] == 1
    assert calls[0].startswith("hour@")
    assert calls[1].startswith("llm@")
    # LLM saw the post-hour clock (no second advance).
    assert calls[1] == "llm@1"


def test_api_finance_advance_and_skip_return_sync_fields(tmp_path, monkeypatch):
    sess = _fresh(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS, ensure_finance
    from app.layer6_persistence.users import create_user, link_session_to_user, make_token
    import uuid

    user = create_user(
        username=f"uh_{uuid.uuid4().hex[:6]}",
        password="uh-pass-12345",
        display_name="uh",
    )
    link_session_to_user(sess.id, user.id, player_id=sess.primary_player_id or "")
    sess.user_id = user.id
    _SESSIONS[sess.id] = sess
    client = TestClient(app)
    h = {"Authorization": f"Bearer {make_token(user.id)}"}

    fin = client.post(
        f"/api/sessions/{sess.id}/finance/advance",
        json={"steps": 3},
        headers=h,
    )
    assert fin.status_code == 200, fin.text
    body = fin.json()
    assert body.get("unified") is True
    assert body.get("in_sync") is True
    assert body["world_tick"] == body["finance_tick"] == 3
    assert body["finance"]["tick"] == 3
    assert sess.world.clock.tick == ensure_finance(sess).tick == 3

    skip = client.post(
        f"/api/sessions/{sess.id}/skip-to-tick",
        json={"target_tick": 5},
        headers=h,
    )
    assert skip.status_code == 200, skip.text
    sb = skip.json()
    assert sb["tick"] == 5
    assert sb.get("in_sync") is True
    assert sb.get("finance_tick") == 5
    assert sess.world.clock.tick == ensure_finance(sess).tick == 5
