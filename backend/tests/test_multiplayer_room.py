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


def test_create_persists_outfit_style(room):
    host = room.society.get(room.primary_player_id)
    assert host is not None
    # Default create path without outfit_style still writes the field.
    assert (host.appearance or {}).get("outfit_style") == "default"


def test_join_catalog_carries_full_appearance(room):
    from app.session import join_session, session_dict

    async def run():
        sess, joiner = await join_session(
            room.id,
            "ignored when catalog keys present",
            category_key="martial",
            variant_key="guard",
            skin="tan",
            equipped_props=["朴刀"],
            outfit_style="青衫",
        )
        app = joiner.appearance or {}
        assert app.get("figure")
        assert app.get("skin") == "tan"
        assert app.get("equipped_props") == ["朴刀"]
        assert app.get("outfit_style") == "青衫"
        snap = session_dict(sess, viewer_id=room.primary_player_id)
        peer = next(a for a in snap["agents"] if a["id"] == joiner.id)
        assert peer["appearance"]["outfit_style"] == "青衫"
        assert peer["appearance"]["equipped_props"] == ["朴刀"]
        assert peer["kind"] == "player"

    asyncio.run(run())


def test_player_to_player_talk_delivers_without_llm(room):
    from app.session import join_session, npc_reply

    async def run():
        sess, joiner = await join_session(
            room.id, "",
            category_key="merchant",
            variant_key="trader",
        )
        host_id = sess.primary_player_id
        assert host_id
        out = await npc_reply(
            sess, npc_id=joiner.id, text="兄台少停。", player_id=host_id,
        )
        assert out["target_kind"] == "player"
        assert out["delivered"] is True
        assert out["reply"] == ""
        assert out["to_id"] == joiner.id
        assert out.get("message_id")

        try:
            await npc_reply(sess, npc_id=host_id, text="自言自语", player_id=host_id)
            raise AssertionError("self-talk should fail")
        except ValueError:
            pass

        from app.session import hydrate_player_talk_inbox, session_dict
        guest_view = session_dict(sess, viewer_id=joiner.id)
        inbox = guest_view.get("player_talk_inbox") or []
        assert any(m.get("text") == "兄台少停。" and m.get("from_id") == host_id for m in inbox)
        host_view = session_dict(sess, viewer_id=host_id)
        assert any(m.get("to_id") == joiner.id for m in (host_view.get("player_talk_inbox") or []))

        sess.player_talk_inbox = {}
        setattr(sess, "_talk_inbox_hydrated", False)
        hydrate_player_talk_inbox(sess)
        assert any(
            m.get("text") == "兄台少停。"
            for m in (sess.player_talk_inbox.get(joiner.id) or [])
        )

    asyncio.run(run())


def test_npc_talk_keeps_thread_and_rehydrates(room):
    from app.session import (
        _thread_between, hydrate_player_talk_inbox, npc_reply, session_dict,
    )

    async def run():
        sess = room
        pid = sess.primary_player_id
        assert pid
        npc = next(iter(sess.society.npcs()), None)
        assert npc is not None
        first = await npc_reply(
            sess, npc_id=npc.id, text="今日可有新鲜鱼货？", player_id=pid,
        )
        assert first["target_kind"] == "npc"
        assert first["delivered"] is True
        assert first.get("reply")
        assert first.get("player_message_id")
        await npc_reply(
            sess, npc_id=npc.id, text="那便称二斤。", player_id=pid,
        )
        inbox = session_dict(sess, viewer_id=pid).get("player_talk_inbox") or []
        texts = [m.get("text") for m in inbox]
        assert "今日可有新鲜鱼货？" in texts
        assert "那便称二斤。" in texts
        assert any(m.get("from_kind") == "npc" for m in inbox)
        thread = _thread_between(sess, pid, npc.id)
        assert len(thread) >= 4
        sess.player_talk_inbox = {}
        setattr(sess, "_talk_inbox_hydrated", False)
        hydrate_player_talk_inbox(sess)
        restored = _thread_between(sess, pid, npc.id)
        assert len(restored) >= 4
        player = sess.society.get(pid)
        dlg = sess.memory.recent_dialogue(npc.id, other_name=player.name if player else None)
        assert dlg

    asyncio.run(run())


def test_talk_thread_cap_keeps_other_peer(room):
    from app.session import _TALK_THREAD_CAP, join_session, npc_reply, session_dict

    async def run():
        sess, joiner = await join_session(
            room.id, "", category_key="merchant", variant_key="trader",
        )
        pid = sess.primary_player_id
        assert pid
        await npc_reply(sess, npc_id=joiner.id, text="兄台少停。", player_id=pid)
        npc = next(iter(sess.society.npcs()), None)
        assert npc is not None
        for i in range(_TALK_THREAD_CAP + 3):
            await npc_reply(sess, npc_id=npc.id, text=f"再问一句{i}。", player_id=pid)
        inbox = session_dict(sess, viewer_id=pid).get("player_talk_inbox") or []
        assert any(m.get("text") == "兄台少停。" and m.get("to_id") == joiner.id for m in inbox)
        npc_lines = [
            m for m in inbox
            if {m.get("from_id"), m.get("to_id")} == {pid, npc.id}
        ]
        assert len(npc_lines) <= _TALK_THREAD_CAP

    asyncio.run(run())
