"""Apply validated WorldEffects under the session write lock."""
from __future__ import annotations

from typing import Any

from .effects import EffectOp, WorldEffect


def apply_effects(sess: Any, effects: list[WorldEffect]) -> list[WorldEffect]:
    """Mutate session state. Caller must hold the session lock / lease."""
    applied: list[WorldEffect] = []
    for eff in effects:
        if eff.op == EffectOp.NOOP:
            applied.append(eff)
            continue
        if eff.op == EffectOp.BUMP_REVISION:
            sess.revision = int(getattr(sess, "revision", 0) or 0) + 1
            applied.append(eff)
            continue
        if eff.op == EffectOp.ADVANCE_CLOCK:
            hours = int(eff.payload.get("hours", 0) or 0)
            if hours > 0 and hasattr(sess.world.clock, "advance"):
                sess.world.clock.advance(hours)
            applied.append(eff)
            continue
        if eff.op == EffectOp.MOVE_AGENT:
            aid = str(eff.payload.get("agent_id") or "")
            lid = str(eff.payload.get("location_id") or "")
            agent = sess.society.get(aid)
            if agent and lid:
                agent.location_id = lid
            applied.append(eff)
            continue
        if eff.op == EffectOp.SET_PRESENCE:
            from ..layer3_agents import PresenceState
            aid = str(eff.payload.get("agent_id") or "")
            agent = sess.society.get(aid)
            if agent:
                raw = str(eff.payload.get("presence") or "active")
                try:
                    agent.presence = PresenceState(raw)
                except Exception:
                    pass
            applied.append(eff)
            continue
        if eff.op == EffectOp.ADJUST_RELATION:
            a = str(eff.payload.get("from_id") or "")
            b = str(eff.payload.get("to_id") or "")
            delta = float(eff.payload.get("delta", 0) or 0)
            if a and b and delta:
                sess.society.adjust_relation(a, b, delta)
            applied.append(eff)
            continue
        if eff.op == EffectOp.APPEND_MEMORY:
            aid = str(eff.payload.get("agent_id") or "")
            kind = str(eff.payload.get("kind") or "note")
            text = str(eff.payload.get("text") or "")
            importance = float(eff.payload.get("importance", 0.5) or 0.5)
            if aid and text:
                sess.memory.add(aid, kind, text, importance=importance)
            applied.append(eff)
            continue
        if eff.op == EffectOp.COMPLETE_TASK:
            # Task completion already applied by _sync_player_tasks; record only.
            applied.append(eff)
            continue
        if eff.op == EffectOp.APPLY_FINANCE_DELTA:
            if sess.finance is not None:
                cash = float(eff.payload.get("cash_delta", 0) or 0)
                if cash and hasattr(sess.finance, "cash"):
                    sess.finance.cash = float(sess.finance.cash) + cash
            applied.append(eff)
            continue
        if eff.op == EffectOp.APPEND_PAGE:
            # Page already appended by narrative handler; revision-only bookkeeping.
            applied.append(eff)
            continue
        if eff.op == EffectOp.APPEND_EVENT:
            applied.append(eff)
            continue
        if eff.op == EffectOp.SET_ACTIVITY:
            aid = str(eff.payload.get("agent_id") or "")
            agent = sess.society.get(aid)
            if agent:
                agent.current_activity = str(eff.payload.get("activity") or "")
            applied.append(eff)
            continue
        applied.append(eff)
    return applied
