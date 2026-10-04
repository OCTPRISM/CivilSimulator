from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import numpy as np

from ..layer1_foundation import Embedder, get_embedder


@dataclass
class MemoryItem:
    ts: float
    actor_id: str
    kind: str            # observation | dialogue | action | reflection | plan | belief
    content: str
    importance: float = 0.5
    embedding: list[float] | None = None


class MemoryStore:
    """Hybrid memory: stores items with embeddings; recall = recency + relevance."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._items: list[MemoryItem] = []
        self._embedder = embedder or get_embedder()
        self._embed_lock = asyncio.Lock()

    # ---------- write ----------
    def add(self, actor_id: str, kind: str, content: str, importance: float = 0.5) -> MemoryItem:
        item = MemoryItem(ts=time.time(), actor_id=actor_id, kind=kind,
                          content=content, importance=importance)
        self._items.append(item)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._embed_one(item))
        except RuntimeError:
            pass
        return item

    async def _embed_one(self, item: MemoryItem) -> None:
        async with self._embed_lock:
            try:
                vecs = await self._embedder.embed([item.content])
                item.embedding = vecs[0]
            except Exception:
                item.embedding = None

    async def aembed_pending(self) -> None:
        pending = [m for m in self._items if m.embedding is None]
        if not pending:
            return
        try:
            vecs = await self._embedder.embed([m.content for m in pending])
            for m, v in zip(pending, vecs):
                m.embedding = v
        except Exception:
            pass

    # ---------- read ----------
    def recent_for(self, actor_id: str, limit: int = 12) -> list[MemoryItem]:
        own = [m for m in self._items if m.actor_id == actor_id]
        return own[-limit:]

    def world_recent(self, limit: int = 20) -> list[MemoryItem]:
        return self._items[-limit:]

    def all(self) -> list[MemoryItem]:
        return list(self._items)

    async def recall(
        self,
        actor_id: str,
        query: str,
        *,
        k_relevant: int = 6,
        m_recent: int = 4,
        scope: str = "self",        # "self" | "world"
    ) -> list[MemoryItem]:
        """Hybrid recall: top-k by cosine similarity ∪ last-m by time."""
        pool = (
            [m for m in self._items if m.actor_id == actor_id]
            if scope == "self" else list(self._items)
        )
        if not pool:
            return []

        recent = pool[-m_recent:]
        relevant: list[MemoryItem] = []
        items_with_embed = [m for m in pool if m.embedding is not None]
        if items_with_embed:
            try:
                qvec = (await self._embedder.embed([query]))[0]
            except Exception:
                qvec = None
            if qvec is not None:
                q = np.asarray(qvec, dtype=np.float32)
                qn = float(np.linalg.norm(q)) or 1.0
                now = time.time()
                scored: list[tuple[float, MemoryItem]] = []
                for m in items_with_embed:
                    v = np.asarray(m.embedding, dtype=np.float32)
                    sim = float(np.dot(q, v) / (qn * (float(np.linalg.norm(v)) or 1.0)))
                    age_h = max(0.0, (now - m.ts) / 3600.0)
                    recency = 0.5 ** (age_h / 6.0)   # half-life: 6h
                    score = 0.7 * sim + 0.2 * m.importance + 0.1 * recency
                    scored.append((score, m))
                scored.sort(key=lambda x: x[0], reverse=True)
                relevant = [m for _, m in scored[:k_relevant]]

        merged_ids: set[int] = set()
        out: list[MemoryItem] = []
        for m in sorted(relevant + recent, key=lambda x: x.ts):
            key = id(m)
            if key in merged_ids:
                continue
            merged_ids.add(key)
            out.append(m)
        return out
