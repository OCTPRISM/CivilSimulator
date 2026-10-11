"""Stable runtime error codes (architecture evolution §7.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeErrorCode(str, Enum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    SESSION_FORBIDDEN = "SESSION_FORBIDDEN"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SESSION_BUSY = "SESSION_BUSY"
    SESSION_LEASE_LOST = "SESSION_LEASE_LOST"
    SESSION_REVISION_CONFLICT = "SESSION_REVISION_CONFLICT"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    LLM_QUOTA_EXCEEDED = "LLM_QUOTA_EXCEEDED"
    QUOTA_BACKEND_UNAVAILABLE = "QUOTA_BACKEND_UNAVAILABLE"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    SIMULATION_OUTPUT_INVALID = "SIMULATION_OUTPUT_INVALID"
    SNAPSHOT_CORRUPT = "SNAPSHOT_CORRUPT"
    SNAPSHOT_VERSION_UNSUPPORTED = "SNAPSHOT_VERSION_UNSUPPORTED"
    LAB_EXPORT_STALE = "LAB_EXPORT_STALE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_CATEGORY: dict[RuntimeErrorCode, str] = {
    RuntimeErrorCode.AUTH_REQUIRED: "auth",
    RuntimeErrorCode.TOKEN_EXPIRED: "auth",
    RuntimeErrorCode.SESSION_FORBIDDEN: "authorization",
    RuntimeErrorCode.VALIDATION_FAILED: "validation",
    RuntimeErrorCode.SESSION_BUSY: "conflict",
    RuntimeErrorCode.SESSION_LEASE_LOST: "conflict",
    RuntimeErrorCode.SESSION_REVISION_CONFLICT: "conflict",
    RuntimeErrorCode.IDEMPOTENCY_KEY_REUSED: "conflict",
    RuntimeErrorCode.LLM_QUOTA_EXCEEDED: "quota",
    RuntimeErrorCode.QUOTA_BACKEND_UNAVAILABLE: "dependency",
    RuntimeErrorCode.LLM_UNAVAILABLE: "dependency",
    RuntimeErrorCode.SIMULATION_OUTPUT_INVALID: "simulation",
    RuntimeErrorCode.SNAPSHOT_CORRUPT: "persistence",
    RuntimeErrorCode.SNAPSHOT_VERSION_UNSUPPORTED: "persistence",
    RuntimeErrorCode.LAB_EXPORT_STALE: "conflict",
    RuntimeErrorCode.INTERNAL_ERROR: "internal",
}

_RETRYABLE: set[RuntimeErrorCode] = {
    RuntimeErrorCode.SESSION_BUSY,
    RuntimeErrorCode.SESSION_LEASE_LOST,
    RuntimeErrorCode.SESSION_REVISION_CONFLICT,
    RuntimeErrorCode.LLM_UNAVAILABLE,
    RuntimeErrorCode.QUOTA_BACKEND_UNAVAILABLE,
}


@dataclass
class RuntimeAppError(Exception):
    code: RuntimeErrorCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    retry_after_ms: int | None = None
    field_errors: dict[str, list[str]] | None = None

    @property
    def category(self) -> str:
        return _CATEGORY.get(self.code, "internal")

    @property
    def retryable(self) -> bool:
        return self.code in _RETRYABLE

    def http_status(self) -> int:
        mapping = {
            "auth": 401,
            "authorization": 403,
            "validation": 422,
            "conflict": 409,
            "quota": 429,
            "dependency": 503,
            "simulation": 422,
            "persistence": 409,
            "internal": 500,
        }
        return mapping.get(self.category, 500)

    def as_envelope(
        self,
        *,
        request_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        err: dict[str, Any] = {
            "code": self.code.value,
            "category": self.category,
            "message": self.message,
            "retryable": self.retryable,
            "details": dict(self.details),
        }
        if self.retry_after_ms is not None:
            err["retry_after_ms"] = self.retry_after_ms
        if self.field_errors:
            err["field_errors"] = self.field_errors
        out: dict[str, Any] = {"error": err}
        if request_id:
            out["request_id"] = request_id
        if correlation_id:
            out["correlation_id"] = correlation_id
        return out
