"""R1-3: LLM failures must surface as 503 — not silent local narration."""
from __future__ import annotations

import os
import uuid

import pytest

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


@pytest.mark.asyncio
async def test_ollama_connect_error_is_user_facing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    from app.config import get_settings
    get_settings.cache_clear()

    from app.layer1_foundation.base import LLMServiceError, Message
    from app.layer1_foundation.ollama_llm import OllamaLLM

    llm = OllamaLLM(model="nomic-embed-text")
    with pytest.raises(LLMServiceError) as ei:
        await llm.chat([Message("user", "hi")], max_tokens=8)
    assert "Ollama" in ei.value.message or "无法连接" in ei.value.message
    get_settings.cache_clear()


def test_create_session_llm_error_returns_503_and_cleans_orphan(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS
    from app.layer1_foundation.base import LLMServiceError
    from app.layer1_foundation.rate_limit import reset_rate_limits
    import app.layer4_narrative.director as director_mod

    reset_rate_limits()
    _SESSIONS.clear()

    async def boom(*_a, **_k):
        raise LLMServiceError("无法连接 Ollama（测试）。")

    monkeypatch.setattr(director_mod.Director, "_narrate", boom)

    client = TestClient(app)
    reg = client.post("/api/auth/register", json={
        "username": f"llm_{uuid.uuid4().hex[:6]}",
        "password": "llm-pass-99",
    })
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    before = set(_SESSIONS.keys())
    created = client.post("/api/sessions", json={
        "seed_key": "ancient",
        "category_key": "official",
        "variant_key": "student",
    }, headers=h)
    assert created.status_code == 503, created.text
    assert "Ollama" in created.json()["detail"] or "无法连接" in created.json()["detail"]
    assert set(_SESSIONS.keys()) == before

    listed = client.get("/api/sessions", headers=h)
    assert listed.status_code == 200
    assert listed.json()["sessions"] == []
    reset_rate_limits()
