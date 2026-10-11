"""HTTP Error envelope + Idempotency-Key helpers (architecture §7.1–7.2)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .runtime.errors import RuntimeAppError, RuntimeErrorCode
from .runtime.idempotency import IdempotencyCache

# Separate HTTP-layer cache (response bodies), distinct from TickCoordinator cache.
_HTTP_IDEMPOTENCY = IdempotencyCache(ttl_s=600.0, max_entries=8192)


def reset_http_idempotency() -> None:
    """Test helper."""
    _HTTP_IDEMPOTENCY.clear()


def request_id_of(request: Request | None) -> str | None:
    if request is None:
        return None
    return getattr(getattr(request, "state", None), "request_id", None) or None


def envelope_from_runtime(
    exc: RuntimeAppError,
    *,
    request: Request | None = None,
    correlation_id: str | None = None,
) -> JSONResponse:
    body = exc.as_envelope(
        request_id=request_id_of(request),
        correlation_id=correlation_id,
    )
    headers: dict[str, str] = {}
    if exc.retry_after_ms is not None and exc.http_status() == 429:
        headers["Retry-After"] = str(max(1, int(exc.retry_after_ms / 1000)))
    return JSONResponse(
        status_code=exc.http_status(), content=body, headers=headers,
    )


def _detail_str(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("detail") or detail)
    if isinstance(detail, list):
        return "validation failed"
    return str(detail) if detail is not None else "error"


def _code_from_http_status(status: int, detail: Any) -> RuntimeErrorCode:
    if isinstance(detail, dict) and detail.get("code"):
        try:
            return RuntimeErrorCode(str(detail["code"]))
        except ValueError:
            pass
    mapping = {
        401: RuntimeErrorCode.AUTH_REQUIRED,
        403: RuntimeErrorCode.SESSION_FORBIDDEN,
        409: RuntimeErrorCode.SESSION_REVISION_CONFLICT,
        422: RuntimeErrorCode.VALIDATION_FAILED,
        503: RuntimeErrorCode.LLM_UNAVAILABLE,
    }
    if status == 429:
        msg = _detail_str(detail)
        if "LLM" in msg or "配额" in msg:
            return RuntimeErrorCode.LLM_QUOTA_EXCEEDED
        return RuntimeErrorCode.RATE_LIMITED
    if status in mapping:
        return mapping[status]
    if status >= 500:
        return RuntimeErrorCode.INTERNAL_ERROR
    return RuntimeErrorCode.VALIDATION_FAILED


def envelope_from_http_exception(
    exc: HTTPException | StarletteHTTPException,
    *,
    request: Request | None = None,
) -> JSONResponse:
    detail = exc.detail
    code = _code_from_http_status(exc.status_code, detail)
    message = _detail_str(detail)
    details: dict[str, Any] = {"http_status": exc.status_code}
    field_errors = None
    if isinstance(detail, dict):
        if isinstance(detail.get("details"), dict):
            details.update(detail["details"])
        if isinstance(detail.get("field_errors"), dict):
            field_errors = detail["field_errors"]
        if detail.get("message"):
            message = str(detail["message"])
    err = RuntimeAppError(
        code=code,
        message=message,
        details=details,
        field_errors=field_errors,
        retry_after_ms=(
            int(detail.get("retry_after_ms"))
            if isinstance(detail, dict) and detail.get("retry_after_ms") is not None
            else None
        ),
    )
    # Preserve the original HTTP status (e.g. 404) even when code maps to 422.
    body = err.as_envelope(request_id=request_id_of(request))
    return JSONResponse(status_code=exc.status_code, content=body)


def envelope_from_validation(
    exc: RequestValidationError,
    *,
    request: Request | None = None,
) -> JSONResponse:
    field_errors: dict[str, list[str]] = {}
    for err in exc.errors():
        loc = err.get("loc") or ()
        key = ".".join(str(x) for x in loc if x != "body")
        field_errors.setdefault(key or "body", []).append(str(err.get("msg") or "invalid"))
    app_err = RuntimeAppError(
        RuntimeErrorCode.VALIDATION_FAILED,
        "Request validation failed",
        details={"error_count": len(exc.errors())},
        field_errors=field_errors,
    )
    return envelope_from_runtime(app_err, request=request)


def envelope_internal(
    exc: Exception,
    *,
    request: Request | None = None,
) -> JSONResponse:
    app_err = RuntimeAppError(
        RuntimeErrorCode.INTERNAL_ERROR,
        "Internal server error",
        details={"type": type(exc).__name__},
    )
    return envelope_from_runtime(app_err, request=request)


@dataclass(frozen=True)
class MutationHeaders:
    idempotency_key: str | None = None
    expected_revision: int | None = None
    correlation_id: str | None = None

    @property
    def command_id(self) -> str | None:
        return self.idempotency_key


def parse_mutation_headers(request: Request) -> MutationHeaders:
    key = (request.headers.get("idempotency-key") or "").strip() or None
    corr = (request.headers.get("x-correlation-id") or "").strip() or None
    rev_raw = (
        request.headers.get("if-match-revision")
        or request.headers.get("x-expected-revision")
        or ""
    ).strip()
    expected: int | None = None
    if rev_raw:
        try:
            expected = int(rev_raw)
        except ValueError as e:
            raise RuntimeAppError(
                RuntimeErrorCode.VALIDATION_FAILED,
                "If-Match-Revision must be an integer",
                field_errors={"If-Match-Revision": ["must be an integer"]},
            ) from e
    return MutationHeaders(
        idempotency_key=key,
        expected_revision=expected,
        correlation_id=corr,
    )


def body_fingerprint(payload: Mapping[str, Any] | None) -> str:
    canonical = json.dumps(
        payload or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class _HttpCached:
    fingerprint: str
    status_code: int
    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)


async def execute_idempotent(
    request: Request,
    *,
    scope: str,
    body: Mapping[str, Any] | None,
    produce: Callable[[], Awaitable[Any]],
) -> Any:
    """Run ``produce`` once per Idempotency-Key; replay or conflict otherwise.

    ``produce`` may return a ``dict`` (→ 200 JSON) or a ``JSONResponse``.
    """
    headers = parse_mutation_headers(request)
    key = headers.idempotency_key
    if not key:
        return await produce()

    fp = body_fingerprint(body)
    cached = _HTTP_IDEMPOTENCY.get(scope, key)
    if isinstance(cached, _HttpCached):
        if cached.fingerprint != fp:
            raise RuntimeAppError(
                RuntimeErrorCode.IDEMPOTENCY_KEY_REUSED,
                "Idempotency-Key was reused with a different request body",
                details={"scope": scope, "key": key},
            )
        resp = JSONResponse(
            status_code=cached.status_code,
            content=cached.body,
            headers={
                **cached.headers,
                "X-Idempotent-Replay": "true",
                "Idempotency-Key": key,
            },
        )
        return resp

    result = await produce()
    if isinstance(result, JSONResponse):
        # Best-effort: only cache JSON dict bodies.
        try:
            payload = json.loads(result.body.decode("utf-8"))
        except Exception:
            return result
        if isinstance(payload, dict):
            _HTTP_IDEMPOTENCY.put(
                scope, key,
                _HttpCached(
                    fingerprint=fp,
                    status_code=result.status_code,
                    body=payload,
                    headers={"Idempotency-Key": key},
                ),
            )
            result.headers["Idempotency-Key"] = key
        return result

    if isinstance(result, dict):
        _HTTP_IDEMPOTENCY.put(
            scope, key,
            _HttpCached(
                fingerprint=fp,
                status_code=200,
                body=result,
                headers={"Idempotency-Key": key},
            ),
        )
        return JSONResponse(
            status_code=200,
            content=result,
            headers={"Idempotency-Key": key},
        )
    return result


def register_error_handlers(app: Any) -> None:
    """Install unified error envelope handlers on a FastAPI app."""
    from .layer1_foundation.llm_quota import LlmQuotaExceeded

    @app.exception_handler(RuntimeAppError)
    async def _runtime_err(request: Request, exc: RuntimeAppError):
        return envelope_from_runtime(exc, request=request)

    @app.exception_handler(LlmQuotaExceeded)
    async def _quota_err(request: Request, exc: LlmQuotaExceeded):
        return envelope_from_runtime(
            RuntimeAppError(
                RuntimeErrorCode.LLM_QUOTA_EXCEEDED,
                exc.message,
                retry_after_ms=3_600_000,
            ),
            request=request,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_err(request: Request, exc: RequestValidationError):
        return envelope_from_validation(exc, request=request)

    @app.exception_handler(HTTPException)
    async def _http_err(request: Request, exc: HTTPException):
        return envelope_from_http_exception(exc, request=request)

    @app.exception_handler(StarletteHTTPException)
    async def _starlette_http_err(request: Request, exc: StarletteHTTPException):
        return envelope_from_http_exception(exc, request=request)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Do not swallow HTTP / runtime errors if they slip through.
        if isinstance(exc, RuntimeAppError):
            return envelope_from_runtime(exc, request=request)
        if isinstance(exc, (HTTPException, StarletteHTTPException)):
            return envelope_from_http_exception(exc, request=request)
        return envelope_internal(exc, request=request)
