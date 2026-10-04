"""Layer 6 — Reality Persistence.

Event-sourced log so any session can be replayed.  Snapshot for fast resume.
"""
from .event_store import Event, EventStore

__all__ = ["Event", "EventStore"]
