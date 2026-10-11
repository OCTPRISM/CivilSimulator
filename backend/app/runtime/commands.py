"""TickCommand / TickResult contracts."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class TickKind(str, Enum):
    WORLD_HOUR = "world_hour"
    NARRATIVE = "narrative"
    DIALOGUE = "dialogue"
    PRESENCE = "presence"
    INJECTION = "injection"
    LAB_IMPORT = "lab_import"
    RESTORE = "restore"


@dataclass(frozen=True)
class TickCommand:
    session_id: str
    kind: TickKind
    command_id: str = field(default_factory=lambda: f"cmd_{uuid4().hex}")
    actor_id: str | None = None
    user_id: str | None = None
    expected_revision: int | None = None
    advance_hours: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    requested_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid4().hex[:12]}")

    def __post_init__(self) -> None:
        if self.advance_hours < 0:
            raise ValueError("advance_hours must be >= 0")
        if self.kind == TickKind.WORLD_HOUR and self.advance_hours == 0:
            object.__setattr__(self, "advance_hours", 1)


@dataclass
class TickResult:
    command_id: str
    session_id: str
    kind: TickKind
    base_revision: int
    revision: int
    world_tick: int
    event_ids: list[str] = field(default_factory=list)
    effects: list[dict[str, Any]] = field(default_factory=list)
    envelopes: list[dict[str, Any]] = field(default_factory=list)
    page: Any = None
    stats: dict[str, Any] | None = None
    tasks_completed: list[dict[str, Any]] = field(default_factory=list)
    reply: dict[str, Any] | None = None
    perception: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    reflection: dict[str, Any] | None = None
    deduplicated: bool = False
    correlation_id: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_public(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "command_id": self.command_id,
            "kind": self.kind.value,
            "revision": self.revision,
            "world_tick": self.world_tick,
            "event_ids": list(self.event_ids),
            "effects": list(self.effects),
            "deduplicated": self.deduplicated,
            "correlation_id": self.correlation_id,
        }
        if self.page is not None:
            out["page"] = self.page
        if self.stats is not None:
            out["stats"] = self.stats
        if self.tasks_completed:
            out["tasks_completed"] = list(self.tasks_completed)
        if self.reply is not None:
            out["reply"] = self.reply
        if self.perception is not None:
            out["perception"] = self.perception
        if self.plan is not None:
            out["plan"] = self.plan
        if self.reflection is not None:
            out["reflection"] = self.reflection
        return out
