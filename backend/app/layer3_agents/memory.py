from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import numpy as np

from ..layer1_foundation import Embedder, get_embedder
from ..layer1_foundation.qdrant_memory import search_memories, upsert_memory

log = logging.getLogger(__name__)

# Memory checkpoint MVP knobs (architecture §2.4).
MEMORY_CHECKPOINT_RECENT_K = 100
MEMORY_CHECKPOINT_IMPORTANCE_MIN = 0.8
MEMORY_CHECKPOINT_CONTENT_MAX = 2000
MEMORY_CHECKPOINT_SCHEMA = 1


@dataclass
class MemoryItem:
    ts: float
    actor_id: str
    kind: str            # observation | dialogue | action | reflection | plan | belief
    content: str
    importance: float = 0.5
    embedding: list[float] | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def as_checkpoint_dict(self) -> dict[str, Any]:
        """Serialize for Scheme B snapshot (embeddings omitted)."""
        content = self.content or ""
        if len(content) > MEMORY_CHECKPOINT_CONTENT_MAX:
            content = content[: MEMORY_CHECKPOINT_CONTENT_MAX - 1] + "…"
        return {
            "id": self.id,
            "ts": float(self.ts),
            "actor_id": self.actor_id,
            "kind": self.kind,
            "content": content,
            "importance": float(self.importance),
        }


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

    # ---------- checkpoint (Scheme B / snapshot v2) ----------
    def select_checkpoint_items(
        self,
        *,
        recent_k: int = MEMORY_CHECKPOINT_RECENT_K,
        importance_min: float = MEMORY_CHECKPOINT_IMPORTANCE_MIN,
    ) -> list[MemoryItem]:
        """recent(K) ∪ importance≥min ∪ plan/belief — stable sort by (ts, id)."""
        by_id: dict[str, MemoryItem] = {}
        # Global recent window (covers multi-agent rooms without exploding size).
        for m in self._items[-max(1, int(recent_k)) :]:
            by_id[m.id] = m
        # Per-actor recent K (doc: each agent keeps recent K).
        actors = {m.actor_id for m in self._items}
        for aid in actors:
            for m in self.recent_for(aid, limit=recent_k):
                by_id[m.id] = m
        for m in self._items:
            if m.importance >= importance_min or m.kind in ("plan", "belief"):
                by_id[m.id] = m
        return sorted(by_id.values(), key=lambda m: (m.ts, m.id))

    def build_checkpoint(
        self,
        *,
        revision: int = 0,
        recent_k: int = MEMORY_CHECKPOINT_RECENT_K,
        importance_min: float = MEMORY_CHECKPOINT_IMPORTANCE_MIN,
    ) -> dict[str, Any]:
        items = [
            m.as_checkpoint_dict()
            for m in self.select_checkpoint_items(
                recent_k=recent_k, importance_min=importance_min,
            )
        ]
        canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return {
            "schema_version": MEMORY_CHECKPOINT_SCHEMA,
            "checkpoint_id": f"memcp_{uuid4().hex[:16]}",
            "revision": int(revision),
            "item_count": len(items),
            "items": items,
            "content_sha256": digest,
        }

    def hydrate_from_checkpoint(self, checkpoint: dict[str, Any] | None) -> int:
        """Load checkpoint items into the local buffer. Returns count hydrated."""
        if not checkpoint or not isinstance(checkpoint, dict):
            return 0
        items = checkpoint.get("items")
        if not isinstance(items, list):
            return 0
        # Optional integrity check — skip bad checksum rather than abort restore.
        expected = checkpoint.get("content_sha256")
        if expected:
            try:
                canonical = json.dumps(
                    items, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                )
                actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if actual != expected:
                    log.warning(
                        "memory checkpoint checksum mismatch for %s — hydrating anyway",
                        self.session_id,
                    )
            except Exception:
                pass
        n = 0
        for raw in items:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("id") or "").strip() or str(uuid4())
            if mid in self._by_id:
                continue
            content = str(raw.get("content") or "")[:MEMORY_CHECKPOINT_CONTENT_MAX]
            if not content.strip():
                continue
            item = MemoryItem(
                ts=float(raw.get("ts") or time.time()),
                actor_id=str(raw.get("actor_id") or "world"),
                kind=str(raw.get("kind") or "observation")[:40],
                content=content,
                importance=max(0.0, min(1.0, float(raw.get("importance") or 0.5))),
                embedding=None,
                id=mid,
            )
            self._items.append(item)
            self._by_id[item.id] = item
            n += 1
        self._items.sort(key=lambda m: (m.ts, m.id))
        return n
