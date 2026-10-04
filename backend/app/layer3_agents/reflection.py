"""Generative-Agents-style reflection.

Periodically: take an agent's recent observations -> ask LLM for 2-3
high-level beliefs/plans -> store back as `reflection`/`belief`/`plan`
memories with high importance.
"""
from __future__ import annotations

import json

from ..layer1_foundation import LLM, Message
from .agent import Agent
from .memory import MemoryStore


_PROMPT_SYS = (
    "你是角色心智的内观器。给定该角色最近发生的事件，"
    "请输出 2-3 条**高层信念或下一步计划**，浓缩为短句。"
    "严格 JSON：{\"beliefs\":[str,...], \"plans\":[str,...]}"
)


async def reflect(agent: Agent, memory: MemoryStore, llm: LLM) -> dict:
    """Run one reflection pass; mutates memory; returns the parsed result."""
    recent = memory.recent_for(agent.id, limit=20)
    if len(recent) < 4:
        return {"beliefs": [], "plans": []}

    bullets = "\n".join(f"- [{m.kind}] {m.content}" for m in recent)
    msgs = [
        Message("system", _PROMPT_SYS),
        Message("user",
                f"角色：{agent.name}\n"
                f"性格：{', '.join(agent.traits)}\n"
                f"目标：{'; '.join(agent.goals)}\n\n"
                f"最近经历：\n{bullets}\n\n请返回 JSON。"),
    ]
    resp = await llm.chat(msgs, temperature=0.6, max_tokens=300)

    data = _safe_json(resp.content) or {"beliefs": [], "plans": []}
    for b in data.get("beliefs", [])[:3]:
        memory.add(agent.id, "belief", str(b), importance=0.8)
    for p in data.get("plans", [])[:3]:
        memory.add(agent.id, "plan", str(p), importance=0.85)
    return data


def _safe_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    l, r = text.find("{"), text.rfind("}")
    if l == -1 or r == -1:
        return None
    try:
        return json.loads(text[l : r + 1])
    except Exception:
        return None
