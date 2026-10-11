"""EventEnvelope — versioned, correlatable session events."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class EventEnvelope:
    session_id: str
    kind: str
    payload: dict[str, Any]
    tick: int = 0
    revision: int = 0
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    schema_version: int = 1
    command_id: str | None = None
    correlation_id: str | None = None
    actor_id: str | None = None
    ts_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    effects: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "kind": self.kind,
            "tick": self.tick,
            "revision": self.revision,
            "command_id": self.command_id,
            "correlation_id": self.correlation_id,
            "actor_id": self.actor_id,
            "ts_ms": self.ts_ms,
            "payload": dict(self.payload),
            "effects": list(self.effects),
        }

    def as_store_payload(self) -> dict[str, Any]:
        """Legacy EventStore stores kind+payload; nest envelope metadata."""
        body = dict(self.payload)
        body["_envelope"] = {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "revision": self.revision,
            "command_id": self.command_id,
            "correlation_id": self.correlation_id,
            "actor_id": self.actor_id,
            "ts_ms": self.ts_ms,
            "effects": list(self.effects),
        }
        return body

    def as_ws_message(self) -> dict[str, Any]:
        """Wire shape for WebSocket / room_bus clients."""
        msg = dict(self.payload)
        msg["type"] = self.kind
        msg["event_id"] = self.event_id
        msg["revision"] = self.revision
        msg["tick"] = self.tick
        msg["command_id"] = self.command_id
        msg["correlation_id"] = self.correlation_id
        return msg
