"""M2 multiplayer room: player identity isolation + join fan-out."""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ["LLM_PROVIDER"] = "mock"
os.environ["QDRANT_ENABLED"] = "false"


@pytest.fixture()
def room(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("QDRANT_ENABLED", "false")

    from app.config import get_settings
    from app.layer1_foundation.factory import get_llm
    from app.session import _SESSIONS, create_session

    get_settings.cache_clear()
    get_llm.cache_clear()
    _SESSIONS.clear()

    host = asyncio.run(create_session(
        "ancient",
        category_key="official",
        variant_key="student",
    ))
    yield host
    _SESSIONS.clear()
    get_settings.cache_clear()
    get_llm.cache_clear()


def test_join_creates_second_player_and_viewer_dict(room):
    from app.session import join_session, session_dict

    async def run():
        sess, joiner = await join_session(room.id, "西域胡商，来长安贩卖香料。")
        assert len(sess.player_ids) == 2
        assert joiner.id in sess.player_ids
        host_view = session_dict(sess, viewer_id=sess.primary_player_id)
        join_view = session_dict(sess, viewer_id=joiner.id)
        assert host_view["player_id"] == sess.primary_player_id
        assert join_view["player_id"] == joiner.id
        assert len(join_view["roster"]) == 2
        assert any(r["is_self"] for r in join_view["roster"] if r["player_id"] == joiner.id)

    asyncio.run(run())


def test_disconnect_sleeps_only_bound_player(room):
    from app.session import join_session, sleep_player

    async def run():
        sess, joiner = await join_session(room.id, "江湖剑客，路过西市。")
        host = sess.society.get(sess.primary_player_id)
        assert host is not None
        assert not host.is_offline()
        await sleep_player(sess, player_id=joiner.id, reason="disconnect")
        host2 = sess.society.get(sess.primary_player_id)
        joiner2 = sess.society.get(joiner.id)
        assert host2 is not None and not host2.is_offline()
        assert joiner2 is not None and joiner2.is_offline()

    asyncio.run(run())


def test_move_is_player_scoped(room):
    from app.session import join_session, move_player

    async def run():
        sess, joiner = await join_session(room.id, "书生乙。")
        host_id = sess.primary_player_id
        assert host_id
        host = sess.society.get(host_id)
        assert host is not None
        hx, hz = float(host.world_x), float(host.world_z)
        await move_player(sess, player_id=joiner.id, world_x=0.42, world_z=-0.31)
        host_after = sess.society.get(host_id)
        guest = sess.society.get(joiner.id)
        assert guest is not None
        assert abs(float(guest.world_x) - 0.42) < 1e-6
        assert abs(float(guest.world_z) + 0.31) < 1e-6
        assert host_after is not None
        assert abs(float(host_after.world_x) - hx) < 1e-6
        assert abs(float(host_after.world_z) - hz) < 1e-6

    asyncio.run(run())
