"""WorldEffect contracts + pure validation (before single-writer commit)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import RuntimeAppError, RuntimeErrorCode


class EffectOp(str, Enum):
    ADVANCE_CLOCK = "advance_clock"
    MOVE_AGENT = "move_agent"
    SET_PRESENCE = "set_presence"
    ADJUST_RELATION = "adjust_relation"
    APPEND_MEMORY = "append_memory"
    COMPLETE_TASK = "complete_task"
    APPLY_FINANCE_DELTA = "apply_finance_delta"
    APPEND_PAGE = "append_page"
    APPEND_EVENT = "append_event"
    SET_ACTIVITY = "set_activity"
    BUMP_REVISION = "bump_revision"
    NOOP = "noop"


@dataclass(frozen=True)
class WorldEffect:
    op: EffectOp
    payload: dict[str, Any] = field(default_factory=dict)
    actor_id: str | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "op": self.op.value,
            "payload": dict(self.payload),
            "actor_id": self.actor_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorldEffect":
        return cls(
            op=EffectOp(str(raw["op"])),
            payload=dict(raw.get("payload") or {}),
            actor_id=raw.get("actor_id"),
            reason=str(raw.get("reason") or ""),
        )


def validate_effects(
    effects: list[WorldEffect],
    *,
    known_agent_ids: set[str] | None = None,
    known_location_ids: set[str] | None = None,
) -> list[WorldEffect]:
    """Reject malformed / unauthorized-looking effects before commit."""
    if not effects:
        return []
    agents = known_agent_ids or set()
    locations = known_location_ids or set()
    out: list[WorldEffect] = []
    errors: list[str] = []

    for i, eff in enumerate(effects):
        if not isinstance(eff, WorldEffect):
            errors.append(f"effects[{i}]: not a WorldEffect")
            continue
        p = eff.payload
        if eff.op == EffectOp.ADVANCE_CLOCK:
            hours = int(p.get("hours", 0) or 0)
            if hours < 0 or hours > 168:
                errors.append(f"effects[{i}]: advance_clock hours out of range")
                continue
        elif eff.op == EffectOp.MOVE_AGENT:
            aid = str(p.get("agent_id") or "")
            lid = str(p.get("location_id") or "")
            if agents and aid not in agents:
                errors.append(f"effects[{i}]: unknown agent_id")
                continue
            if locations and lid and lid not in locations:
                errors.append(f"effects[{i}]: unknown location_id")
                continue
        elif eff.op == EffectOp.SET_PRESENCE:
            aid = str(p.get("agent_id") or "")
            if agents and aid not in agents:
                errors.append(f"effects[{i}]: unknown agent_id")
                continue
            if not p.get("presence"):
                errors.append(f"effects[{i}]: presence required")
                continue
        elif eff.op == EffectOp.ADJUST_RELATION:
            a = str(p.get("from_id") or "")
            b = str(p.get("to_id") or "")
            if agents and (a not in agents or b not in agents):
                errors.append(f"effects[{i}]: unknown relation endpoints")
                continue
            delta = float(p.get("delta", 0) or 0)
            if abs(delta) > 1.0:
                errors.append(f"effects[{i}]: relation delta too large")
                continue
        elif eff.op == EffectOp.APPEND_MEMORY:
            aid = str(p.get("agent_id") or "")
            if agents and aid not in agents:
                errors.append(f"effects[{i}]: unknown agent_id")
                continue
            if not str(p.get("text") or "").strip():
                errors.append(f"effects[{i}]: memory text required")
                continue
        elif eff.op == EffectOp.APPLY_FINANCE_DELTA:
            cash = float(p.get("cash_delta", 0) or 0)
            if abs(cash) > 1_000_000:
                errors.append(f"effects[{i}]: finance delta too large")
                continue
        elif eff.op == EffectOp.APPEND_PAGE:
            if not isinstance(p.get("page"), dict):
                errors.append(f"effects[{i}]: page dict required")
                continue
        out.append(eff)

    if errors:
        raise RuntimeAppError(
            RuntimeErrorCode.VALIDATION_FAILED,
            "WorldEffect validation failed",
            details={"errors": errors},
            field_errors={"effects": errors},
        )
    return out
