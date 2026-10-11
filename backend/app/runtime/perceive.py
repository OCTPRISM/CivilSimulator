"""Perceive — build a structured observation snapshot for a tick."""
from __future__ import annotations

from typing import Any


def perceive_for_actor(sess: Any, actor_id: str | None) -> dict[str, Any]:
    """Cheap, deterministic perception (no LLM). Used by Plan/Act/UI explainability."""
    world = sess.world
    clock = world.clock
    actor = sess.society.get(actor_id) if actor_id else None
    loc_id = getattr(actor, "location_id", None) if actor else None
    loc = world.locations.get(loc_id) if loc_id else None

    nearby: list[dict[str, Any]] = []
    if loc_id:
        for a in sess.society.all():
            if a.id == actor_id:
                continue
            if getattr(a, "location_id", None) != loc_id:
                continue
            nearby.append({
                "id": a.id,
                "name": a.name,
                "kind": a.kind.value if hasattr(a.kind, "value") else str(a.kind),
                "activity": getattr(a, "current_activity", "") or "",
                "presence": (
                    a.presence.value if hasattr(getattr(a, "presence", None), "value")
                    else str(getattr(a, "presence", ""))
                ),
            })

    recent_mem: list[dict[str, Any]] = []
    if actor_id and hasattr(sess.memory, "recent_for"):
        try:
            for m in sess.memory.recent_for(actor_id, limit=5):
                recent_mem.append({
                    "kind": getattr(m, "kind", "") or "",
                    "text": getattr(m, "content", None) or getattr(m, "text", "") or str(m),
                    "importance": float(getattr(m, "importance", 0) or 0),
                })
        except Exception:
            pass

    open_tasks: list[dict[str, Any]] = []
    if actor_id and hasattr(sess, "tasks"):
        try:
            for t in sess.tasks.snapshot(actor_id) or []:
                if isinstance(t, dict) and t.get("status") in (None, "open", "active", "pending"):
                    open_tasks.append({
                        "id": t.get("id"),
                        "title": t.get("title") or t.get("name"),
                        "status": t.get("status"),
                    })
        except Exception:
            pass

    return {
        "world_tick": int(clock.tick),
        "hour": int(getattr(clock, "hour", 0) or 0),
        "day": int(getattr(clock, "day", 0) or 0),
        "revision": int(getattr(sess, "revision", 0) or 0),
        "actor_id": actor_id,
        "location_id": loc_id,
        "location_name": getattr(loc, "name", None) if loc else None,
        "nearby_agents": nearby,
        "recent_memory": recent_mem,
        "open_tasks": open_tasks,
        "tension": float(getattr(sess.director.tension, "value", 0) or 0)
        if hasattr(sess, "director") else 0.0,
    }
