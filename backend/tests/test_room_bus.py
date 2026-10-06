"""v0.4 MP-4: room bus degrades without Redis; fan-out drop-oldest backpressure."""
from __future__ import annotations

import asyncio
import os
import uuid

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def test_room_bus_disabled_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()

    async def _run():
        from app import room_bus
        await room_bus.stop()
        await room_bus.start(handler=None)
        assert room_bus.is_enabled() is False
        st = room_bus.status()
        assert st["redis_bus"] is False
        assert st["started"] is True
        await room_bus.publish("sid-x", {"type": "ping"})
        await room_bus.stop()

    asyncio.run(_run())
    get_settings.cache_clear()


def test_fanout_drop_oldest_backpressure(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "civsim.db"))
    from app.config import get_settings
    get_settings.cache_clear()

    async def _run():
        from app.session import create_session, subscribe, unsubscribe, _fanout, destroy_session
        from app.layer6_persistence.users import create_user

        user = create_user(f"bp_{uuid.uuid4().hex[:6]}", "password-12345")
        sess = await create_session(
            seed_key="ancient",
            user_id=user.id,
            category_key="official",
            variant_key="student",
            max_players=4,
        )
        q = subscribe(sess, player_id=sess.player_ids[0], maxsize=8)
        try:
            for i in range(20):
                _fanout(sess, {"type": "noise", "i": i}, from_remote=True)
            assert q.qsize() <= 8
            assert q.qsize() > 0
            last = None
            while not q.empty():
                last = q.get_nowait()
            assert last is not None
            assert last["i"] == 19
        finally:
            unsubscribe(sess, q)
            destroy_session(sess.id)

    asyncio.run(_run())
    get_settings.cache_clear()


def test_health_reports_room_bus(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "civsim.db"))
    monkeypatch.delenv("REDIS_URL", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "room_bus" in body
        assert body["room_bus"]["redis_bus"] is False
    get_settings.cache_clear()
