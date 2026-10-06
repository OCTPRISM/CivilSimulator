"""Simple in-memory sliding-window rate limits (R0-5)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque

from fastapi import HTTPException, Request

from ..config import get_settings

_LOCK = Lock()
# key → timestamps of recent hits
_HITS: dict[str, Deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    """Test helper — clear all buckets."""
    with _LOCK:
        _HITS.clear()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _allow(key: str, limit: int, window_seconds: float) -> bool:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        q = _HITS[key]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def check_rate_limit(request: Request, *, bucket: str, limit: int, window_seconds: float = 60.0) -> None:
    """Raise 429 when the client exceeds ``limit`` hits in ``window_seconds``."""
    s = get_settings()
    if not getattr(s, "rate_limit_enabled", True):
        return
    if limit <= 0:
        return
    ip = _client_ip(request)
    key = f"{bucket}:{ip}"
    if not _allow(key, limit, window_seconds):
        raise HTTPException(429, f"请求过于频繁，请稍后再试（{bucket}）")


def rate_limit_register(request: Request) -> None:
    s = get_settings()
    check_rate_limit(
        request,
        bucket="register",
        limit=int(getattr(s, "rate_limit_register_per_minute", 5)),
        window_seconds=60.0,
    )


def rate_limit_play(request: Request) -> None:
    s = get_settings()
    check_rate_limit(
        request,
        bucket="play",
        limit=int(getattr(s, "rate_limit_play_per_minute", 60)),
        window_seconds=60.0,
    )
