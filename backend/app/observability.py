"""Structured JSON logging + request metrics (v0.5 P-2)."""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections import defaultdict
from threading import Lock
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import get_settings

_METRICS_LOCK = Lock()
_COUNTERS: dict[str, int] = defaultdict(int)
_LATENCIES_MS: dict[str, list[float]] = defaultdict(list)
_MAX_LAT_SAMPLES = 200


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "latency_ms", "user_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    s = get_settings()
    level_name = (getattr(s, "log_level", "INFO") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    fmt = (getattr(s, "log_format", "json") or "json").strip().lower()
    if fmt == "text":
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    else:
        handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    # Quiet noisy libs in production previews.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def bump_metric(name: str, *, latency_ms: float | None = None) -> None:
    with _METRICS_LOCK:
        _COUNTERS[name] += 1
        if latency_ms is not None:
            q = _LATENCIES_MS[name]
            q.append(float(latency_ms))
            if len(q) > _MAX_LAT_SAMPLES:
                del q[: len(q) - _MAX_LAT_SAMPLES]


def metrics_snapshot() -> dict[str, Any]:
    with _METRICS_LOCK:
        lat: dict[str, Any] = {}
        for key, samples in _LATENCIES_MS.items():
            if not samples:
                continue
            ordered = sorted(samples)
            p50 = ordered[len(ordered) // 2]
            p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
            lat[key] = {
                "count": len(ordered),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
            }
        return {"counters": dict(_COUNTERS), "latency": lat}


def reset_metrics() -> None:
    with _METRICS_LOCK:
        _COUNTERS.clear()
        _LATENCIES_MS.clear()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID and emit one structured access log per request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            latency_ms = (time.perf_counter() - started) * 1000.0
            path = request.url.path
            # Critical-path buckets
            bucket = "http.other"
            if path.startswith("/api/auth/"):
                bucket = "http.auth"
            elif path.startswith("/api/sessions") and path.endswith("/step"):
                bucket = "http.play_step"
            elif path.startswith("/api/media/scene-art"):
                bucket = "http.scene_art"
            elif path == "/api/health":
                bucket = "http.health"
            bump_metric(bucket, latency_ms=latency_ms)
            bump_metric(f"http.status.{status // 100}xx")
            log = logging.getLogger("civsim.access")
            extra = {
                "request_id": rid,
                "method": request.method,
                "path": path,
                "status": status,
                "latency_ms": round(latency_ms, 2),
            }
            log.info(
                "%s %s → %s (%.1fms)",
                request.method,
                path,
                status,
                latency_ms,
                extra=extra,
            )
