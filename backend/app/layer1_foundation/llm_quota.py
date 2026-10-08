"""Per-user / per-session LLM daily quotas (v0.5 P-7).

In-process counters keyed by UTC calendar day. Multi-worker deployments need
sticky routing or a shared store — same class of limitation as R0 rate limits.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Iterator

from fastapi import HTTPException

from ..config import get_settings
from .base import LLM, LLMResponse, Message

_USER: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "llm_quota_user", default=None
)
_SESSION: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "llm_quota_session", default=None
)

_LOCK = Lock()
# (day, kind, id) → count
_COUNTS: dict[tuple[str, str, str], int] = {}


class LlmQuotaExceeded(RuntimeError):
    """Raised when a bound user/session exceeds its daily LLM budget."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def reset_llm_quotas() -> None:
    """Test helper — clear counters."""
    with _LOCK:
        _COUNTS.clear()


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


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


def _bump(kind: str, subject: str, limit: int) -> None:
    if limit <= 0 or not subject:
        return
    day = _utc_day()
    key = (day, kind, subject)
    with _LOCK:
        # Drop previous days opportunistically.
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


def quota_status(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Snapshot used by health / diagnostics."""
    s = get_settings()
    day = _utc_day()
    with _LOCK:
        user_used = _COUNTS.get((day, "user", user_id or ""), 0) if user_id else 0
        sess_used = (
            _COUNTS.get((day, "session", session_id or ""), 0) if session_id else 0
        )
    return {
        "enabled": bool(getattr(s, "llm_quota_enabled", True)),
        "day_utc": day,
        "per_user_limit": int(getattr(s, "llm_daily_quota_per_user", 200)),
        "per_session_limit": int(getattr(s, "llm_daily_quota_per_session", 800)),
        "user_used": user_used,
        "session_used": sess_used,
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
    return HTTPException(429, exc.message)
