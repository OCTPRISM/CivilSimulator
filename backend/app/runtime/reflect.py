"""Reflect — post-commit memory / explainability hooks (cheap, sync for now)."""
from __future__ import annotations

from typing import Any

from .commands import TickCommand, TickKind
from .effects import EffectOp, WorldEffect


def reflect_after_commit(
    sess: Any,
    cmd: TickCommand,
    *,
    perception: dict[str, Any],
    plan: dict[str, Any],
    effects: list[WorldEffect],
) -> dict[str, Any]:
    """Write a short reflective memory for the actor when appropriate."""
    actor_id = cmd.actor_id
    notes: list[str] = []
    mem_written = False

    if actor_id and cmd.kind in (TickKind.NARRATIVE, TickKind.DIALOGUE):
        selected = (plan or {}).get("selected") or {}
        text = str(selected.get("text") or cmd.payload.get("input") or "").strip()
        if text:
            summary = text if len(text) <= 80 else text[:77] + "…"
            note = f"行动回顾：{summary}"
            try:
                sess.memory.add(actor_id, "reflection", note, importance=0.35)
                mem_written = True
                notes.append(note)
            except Exception:
                notes.append("reflection_memory_skipped")

    effect_ops = [e.op.value for e in effects]
    return {
        "actor_id": actor_id,
        "kind": cmd.kind.value,
        "memory_written": mem_written,
        "notes": notes,
        "effect_ops": effect_ops,
        "nearby_count": len((perception or {}).get("nearby_agents") or []),
        "intent": (plan or {}).get("intent"),
    }


def derive_narrative_effects(
    *,
    actor_id: str | None,
    player_input: str | None,
    page_dict: dict[str, Any],
    tasks_completed: list[dict[str, Any]] | None = None,
) -> list[WorldEffect]:
    """Map narrative step outcomes to validated WorldEffects."""
    effects: list[WorldEffect] = [
        WorldEffect(
            op=EffectOp.APPEND_PAGE,
            payload={"page": page_dict},
            actor_id=actor_id,
            reason="narrative_page",
        ),
        WorldEffect(op=EffectOp.BUMP_REVISION, payload={}, reason="commit"),
    ]
    if actor_id and player_input and player_input.strip():
        effects.insert(0, WorldEffect(
            op=EffectOp.APPEND_MEMORY,
            payload={
                "agent_id": actor_id,
                "kind": "action",
                "text": player_input.strip()[:400],
                "importance": 0.5,
            },
            actor_id=actor_id,
            reason="player_input",
        ))
    for t in tasks_completed or []:
        effects.append(WorldEffect(
            op=EffectOp.COMPLETE_TASK,
            payload={"task": t, "agent_id": actor_id},
            actor_id=actor_id,
            reason="task_sync",
        ))
    return effects
