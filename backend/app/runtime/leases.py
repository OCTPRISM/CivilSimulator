"""In-process exclusive lease per session (single-writer gate)."""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator
from uuid import uuid4

from .errors import RuntimeAppError, RuntimeErrorCode


@dataclass
class _Lease:
    token: str
    owner: str
    expires_at: float


class InProcessLeaseManager:
    """Mutex + soft TTL lease. One holder per session_id."""

    def __init__(self, *, default_ttl_s: float = 120.0) -> None:
        self._default_ttl_s = default_ttl_s
        self._locks: dict[str, asyncio.Lock] = {}
        self._leases: dict[str, _Lease] = {}
        # Lazy: Python 3.9 asyncio.Lock() requires a running/set loop.
        self._meta_lock: asyncio.Lock | None = None

    def _meta(self) -> asyncio.Lock:
        if self._meta_lock is None:
            self._meta_lock = asyncio.Lock()
        return self._meta_lock

    async def _lock_for(self, session_id: str) -> asyncio.Lock:
        async with self._meta():
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            return self._locks[session_id]

    def _purge_expired(self, session_id: str) -> None:
        lease = self._leases.get(session_id)
        if lease and lease.expires_at < time.monotonic():
            del self._leases[session_id]

    async def try_acquire(
        self,
        session_id: str,
        *,
        owner: str,
        ttl_s: float | None = None,
        wait_timeout_s: float = 30.0,
    ) -> str:
        lock = await self._lock_for(session_id)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=wait_timeout_s)
        except asyncio.TimeoutError as e:
            raise RuntimeAppError(
                RuntimeErrorCode.SESSION_BUSY,
                "session is busy; retry shortly",
                details={"session_id": session_id},
                retry_after_ms=500,
            ) from e

        ttl = self._default_ttl_s if ttl_s is None else ttl_s
        token = f"lease_{uuid4().hex}"
        self._leases[session_id] = _Lease(
            token=token,
            owner=owner,
            expires_at=time.monotonic() + ttl,
        )
        return token

    def renew(self, session_id: str, token: str, *, ttl_s: float | None = None) -> None:
        lease = self._leases.get(session_id)
        if not lease or lease.token != token:
            raise RuntimeAppError(
                RuntimeErrorCode.SESSION_LEASE_LOST,
                "lease token mismatch or expired",
                details={"session_id": session_id},
            )
        ttl = self._default_ttl_s if ttl_s is None else ttl_s
        lease.expires_at = time.monotonic() + ttl

    def release(self, session_id: str, token: str) -> None:
        lease = self._leases.get(session_id)
        if lease and lease.token == token:
            del self._leases[session_id]
        lock = self._locks.get(session_id)
        if lock and lock.locked():
            lock.release()

    def holder(self, session_id: str) -> str | None:
        self._purge_expired(session_id)
        lease = self._leases.get(session_id)
        return lease.owner if lease else None

    @asynccontextmanager
    async def hold(
        self,
        session_id: str,
        *,
        owner: str,
        ttl_s: float | None = None,
        wait_timeout_s: float = 30.0,
    ) -> AsyncIterator[str]:
        token = await self.try_acquire(
            session_id, owner=owner, ttl_s=ttl_s, wait_timeout_s=wait_timeout_s,
        )
        try:
            yield token
        finally:
            self.release(session_id, token)
