"""Per-user / per-session LLM daily quotas (v0.5 P-7 / v0.5.1 shared).

Backends:
  - memory — process-local (default for unit tests / single worker)
  - sqlite — shared SQLite table (multi-worker invite); falls back to memory on error
"""
from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Iterator, Literal

from fastapi import HTTPException

from ..config import get_settings
from .base import LLM, LLMResponse, Message

log = logging.getLogger("civsim.llm_quota")

_USER: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "llm_quota_user", default=None
)
_SESSION: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "llm_quota_session", default=None
)

_LOCK = Lock()
# (day, kind, id) → count  (memory backend)
_COUNTS: dict[tuple[str, str, str], int] = {}
_SQLITE_DEGRADED = False

BackendName = Literal["memory", "sqlite"]


class LlmQuotaExceeded(RuntimeError):
    """Raised when a bound user/session exceeds its daily LLM budget."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def reset_llm_quotas() -> None:
    """Test helper — clear memory counters and SQLite table when available."""
    global _SQLITE_DEGRADED
    with _LOCK:
        _COUNTS.clear()
        _SQLITE_DEGRADED = False
    try:
        from ..layer6_persistence import llm_quota_store
        llm_quota_store.clear_all()
    except Exception:
        pass


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _backend_name() -> BackendName:
    raw = (getattr(get_settings(), "llm_quota_backend", None) or "sqlite").strip().lower()
    if raw in ("memory", "mem", "process"):
        return "memory"
    return "sqlite"


@contextmanager
def llm_quota_scope(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Iterator[None]:
    """Bind quota subjects for nested ``LLM.chat`` calls."""
    t_user = _USER.set((user_id or "").strip() or None)
    t_sess = _SESSION.set((session_id or "").strip() or None)
    try:
        yield
    finally:
        _USER.reset(t_user)
        _SESSION.reset(t_sess)


def _bump_memory(kind: str, subject: str, limit: int) -> None:
    day = _utc_day()
    key = (day, kind, subject)
    with _LOCK:
        stale = [k for k in _COUNTS if k[0] != day]
        for k in stale:
            _COUNTS.pop(k, None)
        n = _COUNTS.get(key, 0)
        if n >= limit:
            label = "用户" if kind == "user" else "房间"
            raise LlmQuotaExceeded(
                f"今日 LLM 调用已达{label}上限（{limit}），请明日再试或联系管理员"
            )
        _COUNTS[key] = n + 1


def _bump_sqlite(kind: str, subject: str, limit: int) -> None:
    global _SQLITE_DEGRADED
    from ..layer6_persistence import llm_quota_store

    day = _utc_day()
    try:
        llm_quota_store.bump(day, kind, subject, limit)
    except ValueError as e:
        label = "用户" if kind == "user" else "房间"
        raise LlmQuotaExceeded(
            f"今日 LLM 调用已达{label}上限（{limit}），请明日再试或联系管理员"
        ) from e
    except Exception as exc:
        if not _SQLITE_DEGRADED:
            log.warning(
                "LLM quota SQLite unavailable (%s); falling back to memory",
                type(exc).__name__,
            )
            _SQLITE_DEGRADED = True
        _bump_memory(kind, subject, limit)


def _bump(kind: str, subject: str, limit: int) -> None:
    if limit <= 0 or not subject:
        return
    if _backend_name() == "memory" or _SQLITE_DEGRADED:
        _bump_memory(kind, subject, limit)
        return
    _bump_sqlite(kind, subject, limit)


def consume_llm_quota() -> None:
    """Spend one unit against the currently bound user / session budgets."""
    s = get_settings()
    if not getattr(s, "llm_quota_enabled", True):
        return
    user_id = _USER.get()
    session_id = _SESSION.get()
    if user_id:
        _bump("user", user_id, int(getattr(s, "llm_daily_quota_per_user", 200)))
    if session_id:
        _bump(
            "session",
            session_id,
            int(getattr(s, "llm_daily_quota_per_session", 800)),
        )


def _get_used(day: str, kind: str, subject: str) -> int:
    if not subject:
        return 0
    if _backend_name() == "memory" or _SQLITE_DEGRADED:
        with _LOCK:
            return int(_COUNTS.get((day, kind, subject), 0))
    try:
        from ..layer6_persistence import llm_quota_store
        return llm_quota_store.get_count(day, kind, subject)
    except Exception:
        with _LOCK:
            return int(_COUNTS.get((day, kind, subject), 0))


def quota_status(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Snapshot used by health / diagnostics."""
    s = get_settings()
    day = _utc_day()
    backend = _backend_name()
    return {
        "enabled": bool(getattr(s, "llm_quota_enabled", True)),
        "backend": backend if not _SQLITE_DEGRADED else f"{backend}+memory_fallback",
        "day_utc": day,
        "per_user_limit": int(getattr(s, "llm_daily_quota_per_user", 200)),
        "per_session_limit": int(getattr(s, "llm_daily_quota_per_session", 800)),
        "user_used": _get_used(day, "user", user_id or ""),
        "session_used": _get_used(day, "session", session_id or ""),
    }


@dataclass
class QuotaAwareLLM:
    """Decorator that meters ``chat`` against the active quota scope."""

    inner: LLM

    @property
    def name(self) -> str:
        return getattr(self.inner, "name", "quota-wrapped")

    async def chat(
        self,
        messages,
        *,
        temperature: float = 0.8,
        max_tokens: int = 512,
        **kwargs,
    ) -> LLMResponse:
        consume_llm_quota()
        return await self.inner.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def complete(self, prompt: str, *, system: str | None = None, **kw) -> str:
        msgs: list[Message] = []
        if system:
            msgs.append(Message("system", system))
        msgs.append(Message("user", prompt))
        resp = await self.chat(msgs, **kw)
        return resp.content


def wrap_llm_quota(inner: LLM) -> LLM:
    return QuotaAwareLLM(inner=inner)


def raise_http_for_quota(exc: LlmQuotaExceeded) -> HTTPException:
    return HTTPException(
        429,
        {
            "code": "LLM_QUOTA_EXCEEDED",
            "message": exc.message,
            "retry_after_ms": 3_600_000,
        },
    )
