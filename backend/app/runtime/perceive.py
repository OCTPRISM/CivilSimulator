"""Perceive — build a structured observation snapshot for a tick."""
from __future__ import annotations

from typing import Any


def _dist2(ax: float, az: float, bx: float, bz: float) -> float:
    dx, dz = ax - bx, az - bz
    return (dx * dx + dz * dz) ** 0.5


def perceive_for_actor(sess: Any, actor_id: str | None) -> dict[str, Any]:
    """Cheap, deterministic perception (no LLM). Used by Plan/Act/UI explainability.

    Coarse filter: same location_id.
    Fine filter (optional): world_x/world_z within the actor's perception radius.
    """
    world = sess.world
    clock = world.clock
    actor = sess.society.get(actor_id) if actor_id else None
    loc_id = getattr(actor, "location_id", None) if actor else None
    loc = world.locations.get(loc_id) if loc_id else None

    radius = None
    if actor is not None:
        try:
            from ..layer3_agents.context import perception_radius_for
            radius = perception_radius_for(actor)
        except Exception:
            from ..config import get_settings
            radius = float(getattr(get_settings(), "perception_radius", 0.18) or 0.18)

    ax = float(getattr(actor, "world_x", 0.0) or 0.0) if actor else 0.0
    az = float(getattr(actor, "world_z", 0.0) or 0.0) if actor else 0.0
    use_dist = bool(actor) and radius is not None and radius > 0

    nearby: list[dict[str, Any]] = []
    if loc_id:
        for a in sess.society.all():
            if a.id == actor_id:
                continue
            if getattr(a, "location_id", None) != loc_id:
                continue
            dist = None
            if use_dist:
                bx = float(getattr(a, "world_x", 0.0) or 0.0)
                bz = float(getattr(a, "world_z", 0.0) or 0.0)
                dist = _dist2(ax, az, bx, bz)
                # If both are still at origin (unset), keep co-location awareness.
                if (ax or az or bx or bz) and dist > float(radius):
                    continue
            nearby.append({
                "id": a.id,
                "name": a.name,
                "kind": a.kind.value if hasattr(a.kind, "value") else str(a.kind),
                "activity": getattr(a, "current_activity", "") or "",
                "profession": getattr(a, "profession", "") or "",
                "distance": round(dist, 4) if dist is not None else None,
                "presence": (
                    a.presence.value if hasattr(getattr(a, "presence", None), "value")
                    else str(getattr(a, "presence", ""))
                ),
            })
        if use_dist:
            nearby.sort(key=lambda r: (r.get("distance") is None, r.get("distance") or 0.0))

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
        "perception_radius": radius,
        "nearby_agents": nearby,
        "recent_memory": recent_mem,
        "open_tasks": open_tasks,
        "tension": float(getattr(sess.director.tension, "value", 0) or 0)
        if hasattr(sess, "director") else 0.0,
    }
