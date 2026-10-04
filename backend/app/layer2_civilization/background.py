"""Background world advancement while player agents are dormant.

Lightweight ticks: schedules / economy / occasional world_events — no full
LLM pages. Dormant players are never added to ``observed_by``, so they miss
events and only learn fragments on wake.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..layer3_agents import Society
    from ..layer4_narrative.tension import TensionTracker
    from .stats import WorldStats
    from .world import World


# Genre-flavoured incident templates (summary only; LLM wake layer embellishes).
_INCIDENTS: dict[str, list[str]] = {
    "ancient": [
        "{who}在{loc}听见商队喧嚷，据说税吏又加了一成关卡。",
        "{loc}巷口贴出了府衙手令，夜里要清查户籍。",
        "有人在{loc}发现未署名的密信，已悄然传开。",
    ],
    "wuxia": [
        "{who}于{loc}过招断了一根剑穗，旁人议论纷纷。",
        "{loc}酒楼有客悬赏寻人，江湖传闻又起。",
        "夜半{loc}传来打斗声，天明只余一滩血迹。",
    ],
    "xuanhuan": [
        "{loc}灵气异常波动，{who}感应到远处阵法启封。",
        "有妖异气息掠过{loc}，门派弟子正四处追查。",
        "{who}拾得半枚玉简残片，上面符文尚未辨清。",
    ],
    "scifi": [
        "{loc}区段通信迟滞三分钟，系统日志已被归档。",
        "{who}的终端收到未署名加密包，来源不明。",
        "轨道侧发生未知辐射尖峰，{loc}进入黄色警戒。",
    ],
    "mystery": [
        "{loc}旧宅的灯夜里又亮了一次，无人承认进过门。",
        "{who}发现一张被撕掉一角的照片，背面写着日期。",
        "雨后{loc}水洼映出不属于这座城的倒影。",
    ],
}


@dataclass
class WorldEvent:
    summary: str
    kind: str                  # schedule | economy | incident | rumour
    importance: float
    location_id: str | None = None
    actor_ids: list[str] = field(default_factory=list)
    observed_by: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "kind": self.kind,
            "importance": self.importance,
            "location_id": self.location_id,
            "actor_ids": list(self.actor_ids),
            "observed_by": list(self.observed_by),
        }


def _observers_at(
    society: "Society", location_id: str | None,
) -> list[str]:
    """Online players + offline-proxy (not sleeping) observe events."""
    from ..layer3_agents.agent import PresenceState
    out: list[str] = []
    for a in society.players():
        if a.presence not in (PresenceState.ACTIVE, PresenceState.PROXY):
            continue
        if location_id is None or a.location_id == location_id:
            out.append(a.id)
    return out


def background_tick(
    world: "World",
    society: "Society",
    *,
    tension: "TensionTracker | None" = None,
    stats: "WorldStats | None" = None,
    rng: random.Random | None = None,
) -> list[WorldEvent]:
    """Advance one in-world hour without player involvement.

    Returns newly generated world events (may be empty).
    """
    rng = rng or random.Random()
    events: list[WorldEvent] = []

    # 1. Schedules & economy
    econ = society.advance_schedules(world)
    for e in econ:
        ag = society.get(e.get("agent_id", ""))
        loc_id = ag.location_id if ag else None
        events.append(WorldEvent(
            summary=f"{ag.name if ag else '某人'}今日多接了一单生意（+{e.get('income_delta', 0)}）。",
            kind="economy",
            importance=0.25,
            location_id=loc_id,
            actor_ids=[e["agent_id"]] if e.get("agent_id") else [],
            observed_by=_observers_at(society, loc_id),
        ))

    # 1b. Proxy players leave autonomous footprints
    from ..layer3_agents.offline_choice import maybe_proxy_act
    for p in society.players():
        line = maybe_proxy_act(world, p, rng=rng)
        if line:
            events.append(WorldEvent(
                summary=line,
                kind="proxy_act",
                importance=0.45,
                location_id=p.location_id,
                actor_ids=[p.id],
                observed_by=[p.id],  # they lived it
            ))
            # also include other active/proxy observers at same place
            for oid in _observers_at(society, p.location_id):
                if oid not in events[-1].observed_by:
                    events[-1].observed_by.append(oid)

    # 2. Schedule movement rumour (sample a few NPCs who moved / are busy)
    busy = [a for a in society.npcs() if a.current_activity]
    if busy and rng.random() < 0.35:
        ag = rng.choice(busy)
        loc = world.locations.get(ag.location_id) if ag.location_id else None
        loc_name = loc.name if loc else "某处"
        events.append(WorldEvent(
            summary=f"{ag.name}正在{loc_name}：{ag.current_activity}",
            kind="schedule",
            importance=0.2,
            location_id=ag.location_id,
            actor_ids=[ag.id],
            observed_by=_observers_at(society, ag.location_id),
        ))

    # 3. Occasional incident
    if rng.random() < 0.28:
        pool = _INCIDENTS.get(world.genre) or _INCIDENTS["ancient"]
        npcs = society.npcs()
        who = rng.choice(npcs).name if npcs else "过路人"
        locs = list(world.locations.values())
        loc = rng.choice(locs) if locs else None
        loc_name = loc.name if loc else "某处"
        tpl = rng.choice(pool)
        summary = tpl.format(who=who, loc=loc_name)
        events.append(WorldEvent(
            summary=summary,
            kind="incident",
            importance=0.55 + rng.random() * 0.35,
            location_id=loc.id if loc else None,
            actor_ids=[],
            observed_by=_observers_at(society, loc.id if loc else None),
        ))

    # 4. Advance clock + light tension/stats drift
    world.clock.advance(1)
    if tension is not None and stats is not None:
        base = tension.rolling if tension.history else 0.4
        score = max(0.05, min(0.95, base + rng.uniform(-0.08, 0.12)))
        tension.history.append(score)
        stats.evolve(score, rng)
        stats.update_summaries(world.genre)

    return events
