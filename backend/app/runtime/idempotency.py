"""In-process command_id → TickResult cache (strangler; Redis later)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    result: Any
    expires_at: float


class IdempotencyCache:
    def __init__(self, *, ttl_s: float = 600.0, max_entries: int = 4096) -> None:
        self._ttl_s = ttl_s
        self._max = max_entries
        self._by_key: dict[str, _Entry] = {}

    def _key(self, session_id: str, command_id: str) -> str:
        return f"{session_id}:{command_id}"

    def _purge(self) -> None:
        now = time.monotonic()
        dead = [k for k, v in self._by_key.items() if v.expires_at < now]
        for k in dead:
            del self._by_key[k]
        if len(self._by_key) > self._max:
            # Drop oldest by expiry.
            ordered = sorted(self._by_key.items(), key=lambda kv: kv[1].expires_at)
            for k, _ in ordered[: len(self._by_key) - self._max]:
                del self._by_key[k]

    def get(self, session_id: str, command_id: str) -> Any | None:
        self._purge()
        ent = self._by_key.get(self._key(session_id, command_id))
        if not ent:
            return None
        if ent.expires_at < time.monotonic():
            del self._by_key[self._key(session_id, command_id)]
            return None
        return ent.result

    def put(self, session_id: str, command_id: str, result: Any) -> None:
        self._purge()
        self._by_key[self._key(session_id, command_id)] = _Entry(
            result=result,
            expires_at=time.monotonic() + self._ttl_s,
        )

    def clear(self) -> None:
        self._by_key.clear()
