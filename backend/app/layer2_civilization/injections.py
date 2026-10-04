"""User-scheduled events & characters at specific world ticks."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from ..layer3_agents.agent import Agent, AgentKind
from ..layer3_agents.society import Society
from .world import World, new_id


class InjectionKind(str, Enum):
    EVENT = "event"
    CHARACTER = "character"


@dataclass
class ScheduledInjection:
    id: str
    tick: int
    kind: InjectionKind
    payload: dict[str, Any] = field(default_factory=dict)
    fired: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "tick": self.tick,
            "kind": self.kind.value,
            "payload": dict(self.payload),
            "fired": self.fired,
        }


@dataclass
class InjectionQueue:
    items: list[ScheduledInjection] = field(default_factory=list)

    def schedule_event(
        self, tick: int, *, summary: str, importance: float = 0.8,
        location_id: str | None = None, kind: str = "custom",
    ) -> ScheduledInjection:
        inj = ScheduledInjection(
            id=f"inj_{uuid4().hex[:8]}",
            tick=max(0, tick),
            kind=InjectionKind.EVENT,
            payload={
                "summary": summary,
                "importance": importance,
                "location_id": location_id,
                "event_kind": kind,
            },
        )
        self.items.append(inj)
        self.items.sort(key=lambda x: x.tick)
        return inj

    def schedule_character(
        self, tick: int, *, name: str, persona: str, profession: str = "",
        location_id: str | None = None, traits: list[str] | None = None,
        goals: list[str] | None = None, avatar: str = "👤",
        agent_kind: str = "npc",
    ) -> ScheduledInjection:
        inj = ScheduledInjection(
            id=f"inj_{uuid4().hex[:8]}",
            tick=max(0, tick),
            kind=InjectionKind.CHARACTER,
            payload={
                "name": name,
                "persona": persona,
                "profession": profession,
                "location_id": location_id,
                "traits": traits or [],
                "goals": goals or [],
                "avatar": avatar,
                "agent_kind": agent_kind,
            },
        )
        self.items.append(inj)
        self.items.sort(key=lambda x: x.tick)
        return inj

    def pending_at(self, tick: int) -> list[ScheduledInjection]:
        return [i for i in self.items if not i.fired and i.tick <= tick]

    def snapshot(self) -> list[dict]:
        return [i.as_dict() for i in self.items]


def apply_injections(
    queue: InjectionQueue,
    tick: int,
    world: World,
    society: Society,
) -> list[dict]:
    """Fire all injections due at or before ``tick``. Returns fired records."""
    fired: list[dict] = []
    for inj in queue.pending_at(tick):
        if inj.kind == InjectionKind.EVENT:
            rec = _fire_event(inj, world)
            inj.payload["fired_at_tick"] = tick
        elif inj.kind == InjectionKind.CHARACTER:
            rec = _fire_character(inj, world, society)
            inj.payload["agent_id"] = rec.get("agent_id")
            inj.payload["fired_at_tick"] = tick
        else:
            continue
        fired.append(rec)
        inj.fired = True
    return fired


def _fire_event(inj: ScheduledInjection, world: World) -> dict:
    p = inj.payload
    world.facts.append(p.get("summary", ""))
    return {
        "injection_id": inj.id,
        "kind": "event",
        "tick": inj.tick,
        "summary": p.get("summary"),
        "importance": p.get("importance", 0.8),
        "location_id": p.get("location_id"),
        "event_kind": p.get("event_kind", "custom"),
    }


def _fire_character(inj: ScheduledInjection, world: World, society: Society) -> dict:
    p = inj.payload
    loc_id = p.get("location_id")
    if not loc_id and world.locations:
        loc_id = next(iter(world.locations))
    kind = AgentKind.NPC if p.get("agent_kind", "npc") != "animal" else AgentKind.NPC
    # animals use NPC kind but tagged in traits
    traits = list(p.get("traits") or [])
    if p.get("agent_kind") == "animal":
        traits.append("动物")
    agent = Agent(
        id=new_id("agent"),
        name=p.get("name", "来客"),
        kind=kind,
        persona=p.get("persona", ""),
        goals=list(p.get("goals") or []),
        traits=traits,
        location_id=loc_id,
        profession=p.get("profession", ""),
        avatar=p.get("avatar", "👤"),
    )
    agent.ensure_skills(getattr(world, "genre", "ancient") or "ancient")
    from .player_catalog import npc_figure_from_archetype
    figure = p.get("figure") or npc_figure_from_archetype(p, getattr(world, "genre", "ancient"))
    agent.appearance = {"figure": figure}
    society.add(agent)
    world.agents.append(agent.id)
    return {
        "injection_id": inj.id,
        "kind": "character",
        "tick": inj.tick,
        "agent_id": agent.id,
        "name": agent.name,
    }
