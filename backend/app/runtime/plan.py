"""Plan — turn perception + intent into an action candidate (no world writes)."""
from __future__ import annotations

from typing import Any

from .commands import TickCommand, TickKind


def plan_from_command(
    cmd: TickCommand,
    perception: dict[str, Any],
) -> dict[str, Any]:
    """Heuristic planner for the strangler phase (LLM planner lands later)."""
    text = str(cmd.payload.get("input") or cmd.payload.get("text") or "").strip()
    intent = "idle"
    if cmd.kind == TickKind.NARRATIVE:
        intent = "narrate" if text else "observe"
    elif cmd.kind == TickKind.DIALOGUE:
        intent = "talk"
    elif cmd.kind == TickKind.WORLD_HOUR:
        intent = "advance_world"
    elif cmd.kind == TickKind.PRESENCE:
        intent = str(cmd.payload.get("action") or "presence")
    elif cmd.kind == TickKind.INJECTION:
        intent = "inject"
    elif cmd.kind == TickKind.LAB_IMPORT:
        intent = "lab_import"

    candidates: list[dict[str, Any]] = []
    if intent == "narrate" and text:
        candidates.append({
            "action": "player_input",
            "text": text,
            "rationale": "player authored narrative beat",
        })
    elif intent == "talk":
        candidates.append({
            "action": "npc_dialogue",
            "npc_id": cmd.payload.get("npc_id"),
            "text": text,
            "rationale": "direct dialogue",
        })
    elif intent == "advance_world":
        candidates.append({
            "action": "advance_clock",
            "hours": cmd.advance_hours,
            "rationale": "world hour tick",
        })
    else:
        candidates.append({
            "action": intent,
            "rationale": "default plan",
            "payload": dict(cmd.payload),
        })

    # Soft ranking: prefer actions that involve nearby agents when text mentions them.
    nearby_names = {
        (a.get("name") or "").lower(): a.get("id")
        for a in (perception.get("nearby_agents") or [])
        if a.get("name")
    }
    mentioned = [
        aid for name, aid in nearby_names.items() if name and name in text.lower()
    ]

    return {
        "intent": intent,
        "actor_id": cmd.actor_id,
        "candidates": candidates,
        "selected": candidates[0] if candidates else {"action": "noop"},
        "mentioned_agent_ids": mentioned,
        "perception_tick": perception.get("world_tick"),
    }
