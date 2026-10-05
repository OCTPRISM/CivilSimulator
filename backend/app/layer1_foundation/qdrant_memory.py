"""Qdrant-backed vector index for agent memory (M1).

Defaults to an embedded on-disk store so local dev needs no Docker.
Set QDRANT_URL to point at a running Qdrant server instead.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)

_lock = threading.Lock()
_client: Any | None = None
_client_failed = False
_ensured_dims: set[tuple[str, int]] = set()


def reset_qdrant_client() -> None:
    """Test helper: drop the process-wide client singleton."""
    global _client, _client_failed, _ensured_dims
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
        _client = None
        _client_failed = False
        _ensured_dims = set()


def get_qdrant_client():
    """Return a shared Qdrant client, or None if disabled / unavailable."""
    global _client, _client_failed
    s = get_settings()
    if not s.qdrant_enabled or _client_failed:
        return None
    if _client is not None:
        return _client
    with _lock:
        if _client is not None or _client_failed:
            return _client
        try:
            from qdrant_client import QdrantClient

            if s.qdrant_url:
                _client = QdrantClient(
                    url=s.qdrant_url.rstrip("/"),
                    api_key=s.qdrant_api_key,
                    prefer_grpc=False,
                )
                log.info("Qdrant memory using server %s", s.qdrant_url)
            elif s.qdrant_path.strip() == ":memory:":
                _client = QdrantClient(location=":memory:")
                log.info("Qdrant memory using in-memory store")
            else:
                from pathlib import Path

                path = Path(s.qdrant_path)
                path.mkdir(parents=True, exist_ok=True)
                _client = QdrantClient(path=str(path))
                log.info("Qdrant memory using local path %s", path)
        except Exception as exc:
            _client_failed = True
            log.warning("Qdrant unavailable; falling back to in-process recall: %s", exc)
            return None
        return _client


def ensure_collection(dim: int) -> str | None:
    """Create the memories collection for this vector size if needed."""
    s = get_settings()
    client = get_qdrant_client()
    if client is None:
        return None
    name = s.qdrant_collection
    key = (name, int(dim))
    if key in _ensured_dims:
        return name
    try:
        from qdrant_client.http import models as qm

        existing = {c.name for c in client.get_collections().collections}
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=qm.VectorParams(size=int(dim), distance=qm.Distance.COSINE),
            )
            log.info("Created Qdrant collection %s (dim=%s)", name, dim)
        else:
            info = client.get_collection(name)
            # qdrant-client versions expose size differently; be defensive.
            vectors = getattr(getattr(info, "config", None), "params", None)
            size = None
            if vectors is not None:
                vc = getattr(vectors, "vectors", None)
                size = getattr(vc, "size", None) if vc is not None else None
            if size is not None and int(size) != int(dim):
                log.warning(
                    "Qdrant collection %s dim=%s but embedder dim=%s; recreating",
                    name, size, dim,
                )
                client.delete_collection(name)
                client.create_collection(
                    collection_name=name,
                    vectors_config=qm.VectorParams(size=int(dim), distance=qm.Distance.COSINE),
                )
        _ensured_dims.add(key)
        return name
    except Exception as exc:
        log.warning("Failed to ensure Qdrant collection: %s", exc)
        return None


def upsert_memory(
    *,
    point_id: str,
    vector: list[float],
    session_id: str,
    actor_id: str,
    kind: str,
    content: str,
    importance: float,
    ts: float,
) -> bool:
    client = get_qdrant_client()
    if client is None:
        return False
    collection = ensure_collection(len(vector))
    if collection is None:
        return False
    try:
        from qdrant_client.http import models as qm

        client.upsert(
            collection_name=collection,
            points=[
                qm.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "session_id": session_id,
                        "actor_id": actor_id,
                        "kind": kind,
                        "content": content,
                        "importance": float(importance),
                        "ts": float(ts),
                    },
                )
            ],
        )
        return True
    except Exception as exc:
        log.warning("Qdrant upsert failed: %s", exc)
        return False


def search_memories(
    *,
    query_vector: list[float],
    session_id: str,
    actor_id: str | None,
    limit: int = 6,
) -> list[dict]:
    """Return payload dicts scored by cosine similarity (highest first)."""
    client = get_qdrant_client()
    if client is None:
        return []
    collection = ensure_collection(len(query_vector))
    if collection is None:
        return []
    try:
        from qdrant_client.http import models as qm

        must = [qm.FieldCondition(key="session_id", match=qm.MatchValue(value=session_id))]
        if actor_id is not None:
            must.append(qm.FieldCondition(key="actor_id", match=qm.MatchValue(value=actor_id)))

        hits = client.query_points(
            collection_name=collection,
            query=query_vector,
            query_filter=qm.Filter(must=must),
            limit=max(1, int(limit)),
            with_payload=True,
        )
        points = getattr(hits, "points", hits) or []
        out: list[dict] = []
        for h in points:
            payload = dict(getattr(h, "payload", None) or {})
            payload["_id"] = str(getattr(h, "id", ""))
            payload["_score"] = float(getattr(h, "score", 0.0) or 0.0)
            out.append(payload)
        return out
    except Exception as exc:
        log.warning("Qdrant search failed: %s", exc)
        return []
