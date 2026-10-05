from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np

from ..layer1_foundation import Embedder, get_embedder
from ..layer1_foundation.qdrant_memory import search_memories, upsert_memory

log = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    ts: float
    actor_id: str
    kind: str            # observation | dialogue | action | reflection | plan | belief
    content: str
    importance: float = 0.5
    embedding: list[float] | None = None
    id: str = field(default_factory=lambda: str(uuid4()))


class MemoryStore:
    """Hybrid memory: local buffer + optional Qdrant vector index.

    Recall = top-k semantic (Qdrant when available) ∪ last-m by time.
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        *,
        session_id: str | None = None,
    ) -> None:
        self.session_id = session_id or f"mem_{uuid4().hex[:10]}"
        self._items: list[MemoryItem] = []
        self._by_id: dict[str, MemoryItem] = {}
        self._embedder = embedder or get_embedder()
        self._embed_lock: asyncio.Lock | None = None
        self._qdrant_ok = True  # flipped off after first hard failure path

    def _lock(self) -> asyncio.Lock:
        # Python 3.9 requires a running loop when constructing asyncio.Lock.
        if self._embed_lock is None:
            self._embed_lock = asyncio.Lock()
        return self._embed_lock

    # ---------- write ----------
    def add(self, actor_id: str, kind: str, content: str, importance: float = 0.5) -> MemoryItem:
        item = MemoryItem(
            ts=time.time(),
            actor_id=actor_id,
            kind=kind,
            content=content,
            importance=importance,
        )
        self._items.append(item)
        self._by_id[item.id] = item
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._embed_one(item))
        except RuntimeError:
            pass
        return item

    async def _embed_one(self, item: MemoryItem) -> None:
        async with self._lock():
            try:
                vecs = await self._embedder.embed([item.content])
                item.embedding = vecs[0]
            except Exception as exc:
                log.warning("embed failed for memory %s: %s", item.id, exc)
                item.embedding = None
                return
        self._persist_vector(item)

    def _persist_vector(self, item: MemoryItem) -> None:
        if not self._qdrant_ok or item.embedding is None:
            return
        ok = upsert_memory(
            point_id=item.id,
            vector=item.embedding,
            session_id=self.session_id,
            actor_id=item.actor_id,
            kind=item.kind,
            content=item.content,
            importance=item.importance,
            ts=item.ts,
        )
        if not ok:
            # Keep serving from the in-process list; avoid spamming upserts.
            self._qdrant_ok = False

    async def aembed_pending(self) -> None:
        pending = [m for m in self._items if m.embedding is None]
        if not pending:
            return
        async with self._lock():
            still = [m for m in pending if m.embedding is None]
            if not still:
                return
            try:
                vecs = await self._embedder.embed([m.content for m in still])
                for m, v in zip(still, vecs):
                    m.embedding = v
            except Exception as exc:
                log.warning("batch embed failed: %s", exc)
                return
        for m in still:
            self._persist_vector(m)

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
        """Hybrid recall: top-k by vector similarity ∪ last-m by time."""
        await self.aembed_pending()

        pool = (
            [m for m in self._items if m.actor_id == actor_id]
            if scope == "self" else list(self._items)
        )
        if not pool:
            return []

        recent = pool[-m_recent:]
        relevant = await self._relevant(actor_id, query, k_relevant=k_relevant, scope=scope)

        merged_ids: set[str] = set()
        out: list[MemoryItem] = []
        for m in sorted(relevant + recent, key=lambda x: x.ts):
            if m.id in merged_ids:
                continue
            merged_ids.add(m.id)
            out.append(m)
        return out

    async def _relevant(
        self,
        actor_id: str,
        query: str,
        *,
        k_relevant: int,
        scope: str,
    ) -> list[MemoryItem]:
        try:
            qvec = (await self._embedder.embed([query]))[0]
        except Exception:
            return []

        filter_actor = actor_id if scope == "self" else None
        if self._qdrant_ok:
            hits = search_memories(
                query_vector=qvec,
                session_id=self.session_id,
                actor_id=filter_actor,
                limit=max(k_relevant * 3, k_relevant),
            )
            if hits:
                now = time.time()
                scored: list[tuple[float, MemoryItem]] = []
                for h in hits:
                    mid = str(h.get("_id") or "")
                    item = self._by_id.get(mid)
                    if item is None:
                        # Point from a previous process / cold load — rebuild lightly.
                        item = MemoryItem(
                            id=mid or str(uuid4()),
                            ts=float(h.get("ts") or now),
                            actor_id=str(h.get("actor_id") or ""),
                            kind=str(h.get("kind") or "observation"),
                            content=str(h.get("content") or ""),
                            importance=float(h.get("importance") or 0.5),
                        )
                        self._by_id[item.id] = item
                    sim = float(h.get("_score") or 0.0)
                    age_h = max(0.0, (now - item.ts) / 3600.0)
                    recency = 0.5 ** (age_h / 6.0)
                    score = 0.7 * sim + 0.2 * item.importance + 0.1 * recency
                    scored.append((score, item))
                scored.sort(key=lambda x: x[0], reverse=True)
                return [m for _, m in scored[:k_relevant]]

        return self._relevant_local(qvec, actor_id=actor_id, k_relevant=k_relevant, scope=scope)

    def _relevant_local(
        self,
        qvec: list[float],
        *,
        actor_id: str,
        k_relevant: int,
        scope: str,
    ) -> list[MemoryItem]:
        pool = (
            [m for m in self._items if m.actor_id == actor_id]
            if scope == "self" else list(self._items)
        )
        items_with_embed = [m for m in pool if m.embedding is not None]
        if not items_with_embed:
            return []
        q = np.asarray(qvec, dtype=np.float32)
        qn = float(np.linalg.norm(q)) or 1.0
        now = time.time()
        scored: list[tuple[float, MemoryItem]] = []
        for m in items_with_embed:
            v = np.asarray(m.embedding, dtype=np.float32)
            sim = float(np.dot(q, v) / (qn * (float(np.linalg.norm(v)) or 1.0)))
            age_h = max(0.0, (now - m.ts) / 3600.0)
            recency = 0.5 ** (age_h / 6.0)
            score = 0.7 * sim + 0.2 * m.importance + 0.1 * recency
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:k_relevant]]
