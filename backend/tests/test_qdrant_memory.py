"""Qdrant-backed MemoryStore recall tests."""
from __future__ import annotations

import asyncio
import os

import pytest

# Force in-memory Qdrant before settings are cached.
os.environ["QDRANT_ENABLED"] = "true"
os.environ["QDRANT_PATH"] = ":memory:"
os.environ["LLM_PROVIDER"] = "mock"


@pytest.fixture()
def memory_store(monkeypatch):
    monkeypatch.setenv("QDRANT_ENABLED", "true")
    monkeypatch.setenv("QDRANT_PATH", ":memory:")
    monkeypatch.delenv("QDRANT_URL", raising=False)

    from app.config import get_settings
    from app.layer1_foundation import reset_qdrant_client
    from app.layer1_foundation.embeddings import HashEmbedder
    from app.layer3_agents.memory import MemoryStore

    get_settings.cache_clear()
    reset_qdrant_client()
    store = MemoryStore(embedder=HashEmbedder(), session_id="sess_test_qdrant")
    yield store
    reset_qdrant_client()
    get_settings.cache_clear()


def test_qdrant_indexes_and_recalls(memory_store):
    store = memory_store
    target = "长安东市 米价 上涨 商贾 忧心"
    store.add("hero", "observation", target, importance=0.9)
    store.add("hero", "observation", "宫门 春雨 石阶", importance=0.2)

    async def run():
        await store.aembed_pending()
        assert store._qdrant_ok is True
        # Exact-ish overlap query against HashEmbedder token bags.
        hits = await store.recall("hero", "米价 商贾 市场", k_relevant=2, m_recent=0)
        assert hits
        assert any("米价" in h.content for h in hits)

        from app.layer1_foundation.qdrant_memory import search_memories

        qvec = (await store._embedder.embed(["米价 商贾 市场"]))[0]
        raw = search_memories(
            query_vector=qvec,
            session_id=store.session_id,
            actor_id="hero",
            limit=3,
        )
        assert raw
        assert any("米价" in (h.get("content") or "") for h in raw)

    asyncio.run(run())


def test_qdrant_scopes_by_session(memory_store):
    from app.layer1_foundation.embeddings import HashEmbedder
    from app.layer1_foundation.qdrant_memory import search_memories
    from app.layer3_agents.memory import MemoryStore

    other = MemoryStore(embedder=HashEmbedder(), session_id="sess_other")
    memory_store.add("a", "observation", "西域 商队 抵达 长安", importance=0.9)
    other.add("a", "observation", "江南 梅雨 连绵", importance=0.9)

    async def run():
        await memory_store.aembed_pending()
        await other.aembed_pending()
        qvec = (await memory_store._embedder.embed(["商队 贸易 长安"]))[0]
        raw = search_memories(
            query_vector=qvec,
            session_id=memory_store.session_id,
            actor_id="a",
            limit=5,
        )
        texts = " ".join(h.get("content") or "" for h in raw)
        assert "西域" in texts
        assert "江南" not in texts

    asyncio.run(run())
