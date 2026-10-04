"""Ollama-driven continuous simulation.

One inference produces a coherent atomic tick for the whole world.  No random
or rule-based fallback mutates simulation state: if Ollama is unavailable the
tick is left untouched and the caller can expose the failure to the UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from ..layer1_foundation import LLM, Message

if TYPE_CHECKING:
    from ..layer3_agents import MemoryStore, Society
    from ..layer4_narrative.tension import TensionTracker
    from .stats import WorldStats
    from .world import World


_BEHAVIORS = {"idle", "walk", "work", "drink", "climb", "swim", "farm"}


@dataclass
class LiveTickResult:
    events: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    environment: str = ""
    reasoning: str = ""
    model: str = ""


def _safe_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    left, right = text.find("{"), text.rfind("}")
    if left < 0 or right <= left:
        return None
    try:
        data = json.loads(text[left:right + 1])
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _compact_context(
    world: "World", society: "Society", stats: "WorldStats",
    memory: "MemoryStore",
    finance: dict | None = None,
) -> dict[str, Any]:
    agents = []
    for a in society.all():
        agents.append({
            "id": a.id,
            "name": a.name,
            "kind": a.kind.value,
            "presence": a.presence.value,
            "persona": a.persona[:240],
            "goals": list(a.goals)[:4],
            "traits": list(a.traits)[:6],
            "profession": a.profession,
            "location_id": a.location_id,
            "activity": a.current_activity,
            "savings": round(a.savings, 2),
            "relations": dict(list(a.relations.items())[:8]),
        })
    recent = [
        {"actor_id": m.actor_id, "kind": m.kind, "content": m.content[:240]}
        for m in memory.world_recent(limit=16)
    ]
    return {
        "world": {
            "name": world.name,
            "genre": world.genre,
            "premise": world.premise,
            "rules": world.rules,
            "clock": world.clock.label(),
            "tick": world.clock.tick,
            "facts": world.facts[-16:],
            "locations": [
                {"id": l.id, "name": l.name, "tags": l.tags}
                for l in world.locations.values()
            ],
            "factions": [
                {
                    "id": f.id, "name": f.name, "ideology": f.ideology,
                    "relations": f.relations,
                }
                for f in world.factions.values()
            ],
        },
        "stats": stats.snapshot(),
        "finance": finance,
        "agents": agents,
        "recent_memory": recent,
    }


async def infer_live_tick(
    llm: LLM,
    world: "World",
    society: "Society",
    stats: "WorldStats",
    memory: "MemoryStore",
    finance: dict | None = None,
) -> tuple[LiveTickResult, dict[str, Any]]:
    """Ask Ollama for one coherent world-and-agent update."""
    if llm.name != "ollama":
        raise RuntimeError(
            f"实时模拟要求 Ollama，当前 provider={llm.name!r}；本 tick 未更新"
        )

    context = _compact_context(world, society, stats, memory, finance=finance)
    system = (
        "你是一个持续运行的文明世界模拟内核。你必须同时推演所有未休眠角色的"
        "自主行为，以及环境、事件、经济、政治、民生、军事的因果演化。"
        "角色决策必须忠于人设、目标、记忆、关系和资源；世界变化必须由当前状态"
        "与角色行为推出，禁止无因果的随机事件。玩家在线时不得替玩家做重大选择，"
        "但要推演其已表达意图造成的即时状态与周围人的反应。每次代表世界内一小时。"
        "只输出严格 JSON，不要 Markdown。"
    )
    schema = {
        "reasoning": "简短说明本 tick 的主要因果链",
        "environment": "天气、生态、基础设施或空间环境的变化",
        "decisions": [{
            "agent_id": "必须是输入中的角色 id",
            "action": "此角色本小时实际采取的行动",
            "dialogue": "可为空；符合角色口吻的一句话",
            "location_id": "必须是输入地点 id；在线玩家非必要不移动",
            "behavior": "idle|walk|work|drink|climb|swim|farm",
            "goal_updates": ["仅有真实变化时填写"],
            "relation_changes": [{"target_id": "角色id", "delta": 0.0}],
            "economy_delta": 0.0,
        }],
        "events": [{
            "summary": "已经发生、可被世界记录的事实",
            "kind": "agent|environment|economy|politics|livelihood|military",
            "importance": 0.0,
            "location_id": "地点 id 或 null",
            "actor_ids": ["角色 id"],
        }],
        "stats": {
            "politics_delta": 0.0,
            "economy_delta": 0.0,
            "livelihood_delta": 0.0,
            "military_delta": 0.0,
            "environment_delta": 0.0,
            "summary": {
                "politics": "一句话",
                "economy": "一句话",
                "livelihood": "一句话",
                "military": "一句话",
                "environment": "一句话",
            },
        },
        "facts_add": ["应成为世界长期事实的新变化"],
    }
    user = (
        "当前完整状态：\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        + "\n\n严格按以下结构返回；decisions 必须覆盖每个未休眠角色：\n"
        + json.dumps(schema, ensure_ascii=False)
    )
    response = await llm.chat(
        [Message("system", system), Message("user", user)],
        temperature=0.55,
        max_tokens=4096,
        json_mode=True,  # Ollama native JSON grammar; provider was checked above.
    )
    data = _safe_json(response.content)
    if not data:
        raise ValueError("Ollama 未返回有效的实时模拟 JSON；本 tick 未更新")
    decisions = data.get("decisions")
    events = data.get("events")
    if not isinstance(decisions, list) or not isinstance(events, list):
        raise ValueError("Ollama 实时模拟结果缺少 decisions/events；本 tick 未更新")
    expected = {a.id for a in society.all() if not a.is_dormant()}
    covered = {
        str(item.get("agent_id") or "")
        for item in decisions if isinstance(item, dict)
    }
    missing = expected - covered
    if missing:
        raise ValueError(
            f"Ollama 未覆盖全部活跃角色（缺少 {len(missing)} 个）；本 tick 未更新"
        )
    return LiveTickResult(
        decisions=decisions,
        events=events,
        environment=str(data.get("environment") or "")[:500],
        reasoning=str(data.get("reasoning") or "")[:800],
        model=response.model,
    ), data


def apply_live_tick(
    result: LiveTickResult,
    raw: dict[str, Any],
    world: "World",
    society: "Society",
    stats: "WorldStats",
    memory: "MemoryStore",
) -> list[dict[str, Any]]:
    """Validate and atomically apply a successful Ollama inference."""
    location_ids = set(world.locations)
    agent_ids = {a.id for a in society.all()}

    for item in result.decisions:
        if not isinstance(item, dict):
            continue
        agent = society.get(str(item.get("agent_id") or ""))
        if not agent or agent.is_dormant():
            continue
        action = str(item.get("action") or "").strip()[:500]
        dialogue = str(item.get("dialogue") or "").strip()[:240]
        if action:
            agent.current_activity = action
            memory.add(agent.id, "action", action, importance=0.55)
        if dialogue:
            memory.add(agent.id, "dialogue", dialogue, importance=0.45)
        behavior = str(item.get("behavior") or "")
        if behavior in _BEHAVIORS:
            agent.behavior = behavior
        location_id = str(item.get("location_id") or "")
        # Online player movement remains bound to explicit user intent.
        if location_id in location_ids and (agent.kind.value != "player" or agent.is_proxy()):
            agent.location_id = location_id
        goals = item.get("goal_updates")
        if isinstance(goals, list) and goals:
            agent.goals = [str(g)[:160] for g in goals if str(g).strip()][:6]
        try:
            economy_delta = max(-10000.0, min(10000.0, float(item.get("economy_delta", 0))))
        except (TypeError, ValueError):
            economy_delta = 0.0
        agent.savings += economy_delta
        if economy_delta > 0:
            agent.today_income += economy_delta
        for rel in item.get("relation_changes") or []:
            if not isinstance(rel, dict):
                continue
            target = str(rel.get("target_id") or "")
            if target not in agent_ids:
                continue
            try:
                delta = max(-0.25, min(0.25, float(rel.get("delta", 0))))
            except (TypeError, ValueError):
                continue
            society.adjust_relation(agent.id, target, delta)

    stat_data = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
    for name in ("politics", "economy", "livelihood", "military", "environment"):
        try:
            delta = max(-12.0, min(12.0, float(stat_data.get(f"{name}_delta", 0))))
        except (TypeError, ValueError):
            delta = 0.0
        setattr(stats, name, max(0.0, min(100.0, getattr(stats, name) + delta)))
    summaries = stat_data.get("summary")
    if isinstance(summaries, dict):
        for name in ("politics", "economy", "livelihood", "military", "environment"):
            text = str(summaries.get(name) or "").strip()
            if text:
                stats.summary[name] = text[:180]
    stats.push_history()

    for fact in raw.get("facts_add") or []:
        fact = str(fact).strip()[:300]
        if fact and fact not in world.facts:
            world.facts.append(fact)
    world.facts[:] = world.facts[-100:]

    applied_events: list[dict[str, Any]] = []
    for item in result.events[:20]:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or "").strip()[:500]
        if not summary:
            continue
        location_id = item.get("location_id")
        if location_id not in location_ids:
            location_id = None
        actor_ids = [str(a) for a in item.get("actor_ids") or [] if str(a) in agent_ids]
        try:
            importance = max(0.0, min(1.0, float(item.get("importance", 0.5))))
        except (TypeError, ValueError):
            importance = 0.5
        applied_events.append({
            "summary": summary,
            "kind": str(item.get("kind") or "agent")[:40],
            "importance": importance,
            "location_id": location_id,
            "actor_ids": actor_ids,
            "observed_by": [
                a.id for a in society.players()
                if not a.is_dormant() and (location_id is None or a.location_id == location_id)
            ],
            "source": "ollama",
            "model": result.model,
        })
    if result.environment:
        memory.add("world", "observation", result.environment, importance=0.6)
    world.clock.advance(1)
    return applied_events
