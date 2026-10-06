"""Simple in-memory sliding-window rate limits (R0-5)."""
from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque

from fastapi import HTTPException, Request

from ..config import get_settings

_LOCK = Lock()
# key → timestamps of recent hits
_HITS: dict[str, Deque[float]] = defaultdict(deque)
_MAX_BUCKETS = 4096


def reset_rate_limits() -> None:
    """Test helper — clear all buckets."""
    with _LOCK:
        _HITS.clear()


def _normalize_ip(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "unknown"
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        # Truncate spoofed garbage; do not invent a new bucket per random string.
        return "invalid"


def _client_ip(request: Request) -> str:
    """Client IP for rate limiting.

    R0-5: do **not** trust ``X-Forwarded-For`` unless ``TRUST_PROXY_HEADERS=true``
    (otherwise attackers rotate spoofed IPs to bypass limits).
    """
    s = get_settings()
    if getattr(s, "trust_proxy_headers", False):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return _normalize_ip(forwarded.split(",")[0])
    if request.client and request.client.host:
        return _normalize_ip(request.client.host)
    return "unknown"


def _evict_locked(now: float, window_seconds: float) -> None:
    """Drop empty/expired buckets so spoofed keys cannot grow forever."""
    cutoff = now - window_seconds
    dead: list[str] = []
    for key, q in _HITS.items():
        while q and q[0] < cutoff:
            q.popleft()
        if not q:
            dead.append(key)
    for key in dead:
        _HITS.pop(key, None)
    # Hard cap: drop oldest-empty-ish keys if still over limit.
    while len(_HITS) > _MAX_BUCKETS:
        _HITS.pop(next(iter(_HITS)))


def _allow(key: str, limit: int, window_seconds: float) -> bool:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        _evict_locked(now, window_seconds)
        q = _HITS[key]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def check_rate_limit(
    request: Request | None = None,
    *,
    bucket: str,
    limit: int,
    window_seconds: float = 60.0,
    subject: str | None = None,
) -> None:
    """Raise 429 when the client exceeds ``limit`` hits in ``window_seconds``.

    ``subject`` overrides IP (used for authenticated WS actions keyed by user id).
    """
    s = get_settings()
    if not getattr(s, "rate_limit_enabled", True):
        return
    if limit <= 0:
        return
    if subject:
        identity = subject.strip() or "unknown"
    elif request is not None:
        identity = _client_ip(request)
    else:
        identity = "unknown"
    key = f"{bucket}:{identity}"
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


def rate_limit_play_user(user_id: str) -> None:
    """Shared play budget for HTTP + WS mutations (R0-5)."""
    s = get_settings()
    check_rate_limit(
        None,
        bucket="play",
        limit=int(getattr(s, "rate_limit_play_per_minute", 60)),
        window_seconds=60.0,
        subject=f"user:{user_id}",
    )


def rate_limit_play(request: Request) -> None:
    """HTTP play dependency: prefer Authorization user id, else client IP."""
    from ..layer6_persistence.users import verify_token

    s = get_settings()
    auth = request.headers.get("authorization") or ""
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else auth.strip()
    uid = verify_token(token) if token else None
    if uid:
        rate_limit_play_user(uid)
        return
    check_rate_limit(
        request,
        bucket="play",
        limit=int(getattr(s, "rate_limit_play_per_minute", 60)),
        window_seconds=60.0,
    )
