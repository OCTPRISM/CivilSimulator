"""Optional Redis pub/sub for cross-worker WS fan-out (v0.4 MP-4).

When ``REDIS_URL`` is unset or Redis is unreachable, the bus is a no-op and
rooms stay single-process (local ``Session.subscribers`` only). Startup never
fails solely because Redis is missing.

Multi-worker note: session *state* remains in-process; Redis only relays
already-serialized room events. Prefer sticky routing by ``session_id``.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Awaitable
from uuid import uuid4

log = logging.getLogger(__name__)

CHANNEL_PREFIX = "civsim:room:"
_WORKER_ID = uuid4().hex

_redis: Any = None
_listener_task: asyncio.Task | None = None
_local_handler: Callable[[str, dict], Awaitable[None] | None] | None = None
_enabled = False
_started = False


def is_enabled() -> bool:
    return _enabled


def status() -> dict:
    return {
        "redis_bus": _enabled,
        "started": _started,
        "connected": _redis is not None,
    }


async def _close_redis(client: Any) -> None:
    """redis-py 5 exposes ``aclose``; older stubs only know ``close``."""
    if client is None:
        return
    close = getattr(client, "aclose", None) or getattr(client, "close", None)
    if close is None:
        return
    try:
        result = close()
        if asyncio.iscoroutine(result):
            await result
    except Exception:
        pass


async def start(handler: Callable[[str, dict], Awaitable[None] | None] | None = None) -> None:
    """Connect if ``REDIS_URL`` is set; otherwise stay disabled."""
    global _redis, _listener_task, _local_handler, _enabled, _started
    _local_handler = handler
    from .config import get_settings

    url = (get_settings().redis_url or "").strip()
    if not url:
        _enabled = False
        _started = True
        log.info("Room bus: Redis unset — single-process fan-out only")
        return

    try:
        import redis.asyncio as redis_async
    except ImportError:
        log.warning("Room bus: redis package missing — single-process fallback")
        _enabled = False
        _started = True
        return

    client = None
    try:
        client = redis_async.from_url(url, decode_responses=True)
        await client.ping()
    except Exception as exc:
        log.warning("Room bus: Redis unreachable (%s) — single-process fallback", exc)
        await _close_redis(client)
        _enabled = False
        _started = True
        return

    _redis = client
    _enabled = True
    _started = True
    _listener_task = asyncio.create_task(_listen_loop(), name="civsim-room-bus")
    log.info("Room bus: Redis pub/sub enabled")


async def stop() -> None:
    global _redis, _listener_task, _enabled, _started
    task = _listener_task
    _listener_task = None
    if task:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    client = _redis
    _redis = None
    await _close_redis(client)
    _enabled = False
    _started = False


async def publish(session_id: str, payload: dict) -> None:
    """Best-effort publish; never raises into gameplay path."""
    if not _enabled or _redis is None:
        return
    sid = (session_id or "").strip()
    if not sid:
        return
    try:
        body = json.dumps(
            {"sid": sid, "payload": payload, "origin": _WORKER_ID},
            ensure_ascii=False,
            default=str,
        )
        await _redis.publish(f"{CHANNEL_PREFIX}{sid}", body)
    except Exception as exc:
        log.debug("Room bus publish failed: %s", exc)


async def _listen_loop() -> None:
    global _enabled, _redis
    assert _redis is not None
    pubsub = _redis.pubsub()
    try:
        await pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") not in ("pmessage", "message"):
                continue
            data = message.get("data")
            if not isinstance(data, str):
                continue
            try:
                envelope = json.loads(data)
            except json.JSONDecodeError:
                continue
            if envelope.get("origin") == _WORKER_ID:
                continue
            sid = str(envelope.get("sid") or "")
            payload = envelope.get("payload")
            if not sid or not isinstance(payload, dict):
                continue
            if _local_handler is None:
                continue
            try:
                result = _local_handler(sid, payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                log.exception("Room bus local handler failed for %s", sid)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Room bus listener crashed — disabling Redis relay")
        _enabled = False
        client = _redis
        _redis = None
        await _close_redis(client)
    finally:
        close_ps = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
        if close_ps is not None:
            try:
                result = close_ps()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass
