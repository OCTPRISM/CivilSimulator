"""v0.5 P-7: per-user / per-session LLM daily quotas."""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def _isolate(tmp_path, monkeypatch, *, per_user: int = 1, per_session: int = 100):
    db = tmp_path / "civsim.db"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(db))
    monkeypatch.setenv("LLM_QUOTA_ENABLED", "true")
    monkeypatch.setenv("LLM_DAILY_QUOTA_PER_USER", str(per_user))
    monkeypatch.setenv("LLM_DAILY_QUOTA_PER_SESSION", str(per_session))
    from app.config import get_settings
    get_settings.cache_clear()
    from app.layer1_foundation.factory import get_llm
    get_llm.cache_clear()
    from app.layer1_foundation.llm_quota import reset_llm_quotas
    reset_llm_quotas()
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


@pytest.mark.asyncio
async def test_quota_aware_llm_blocks_after_limit(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, per_user=2)
    from app.layer1_foundation.base import Message
    from app.layer1_foundation.factory import get_llm
    from app.layer1_foundation.llm_quota import LlmQuotaExceeded, llm_quota_scope

    llm = get_llm()
    with llm_quota_scope(user_id="u_quota", session_id="s_quota"):
        await llm.chat([Message("user", "a")])
        await llm.chat([Message("user", "b")])
        with pytest.raises(LlmQuotaExceeded):
            await llm.chat([Message("user", "c")])


def test_step_maps_llm_quota_exceeded_to_429(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, per_user=1)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.rate_limit import reset_rate_limits
    from app.layer1_foundation.llm_quota import LlmQuotaExceeded

    reset_rate_limits()
    _SESSIONS.clear()
    client = TestClient(app)
    reg = client.post("/api/auth/register", json={
        "username": f"q_{uuid.uuid4().hex[:6]}",
        "password": "quota-pass-12345",
    })
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    hh = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
        "max_players": 4,
    }, headers=hh)
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]

    async def _boom(*_a, **_k):
        raise LlmQuotaExceeded("今日 LLM 调用已达用户上限（1），请明日再试或联系管理员")

    monkeypatch.setattr("app.main.step", _boom)
    blocked = client.post(
        f"/api/sessions/{sid}/step",
        json={"input": "环顾四周"},
        headers=hh,
    )
    assert blocked.status_code == 429, blocked.text
    assert "上限" in blocked.text
