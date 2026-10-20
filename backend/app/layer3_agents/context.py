"""Shared NPC reaction context — civilization, personal life, cognition, ability.

Used by Agent.think / reply_to, Director casting, and live_simulation so every
reaction path shares the same grounding rules.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..layer2_civilization.world import World
    from .agent import Agent
    from .society import Society


def relation_label(score: float) -> str:
    if score >= 0.55:
        return "亲近"
    if score >= 0.2:
        return "友善"
    if score <= -0.55:
        return "敌视"
    if score <= -0.2:
        return "戒备"
    return "寻常"


def format_life_ctx(agent: "Agent") -> str:
    lines: list[str] = []
    if agent.profession:
        lines.append(f"职业：{agent.profession}")
    if agent.current_activity:
        lines.append(f"此刻正在：{agent.current_activity}")
    if agent.economy:
        unit = agent.economy.get("unit", "笔")
        label = agent.economy.get("income_label", "收入")
        lines.append(
            f"今日已得 {label} {agent.today_income:g}（共 {agent.today_customers} {unit}），"
            f"手头积蓄约 {agent.savings:g}，最近一餐：{agent.last_meal_tier or '未记'}"
        )
    elif agent.savings:
        lines.append(f"手头积蓄约 {agent.savings:g}")
    return "\n".join(lines) or "（无特别生计状态）"


def format_relation_line(agent: "Agent", other_id: str | None, other_name: str = "") -> str:
    if not other_id:
        return ""
    score = float(agent.relations.get(other_id, 0.0) or 0.0)
    whom = other_name or other_id
    return f"你对【{whom}】的观感：{relation_label(score)}（{score:+.2f}）"


def format_inventory_snippet(agent: "Agent", *, max_items: int = 5) -> str:
    inv = list(getattr(agent, "inventory", None) or [])
    if not inv:
        return "随身物品：无（或未点检）"
    parts: list[str] = []
    for it in inv[:max_items]:
        name = getattr(it, "name", None) or (it.get("name") if isinstance(it, dict) else str(it))
        qty = getattr(it, "qty", None)
        if qty is None and isinstance(it, dict):
            qty = it.get("qty")
        if qty is not None and float(qty) != 1:
            parts.append(f"{name}×{qty:g}" if isinstance(qty, float) else f"{name}×{qty}")
        else:
            parts.append(str(name))
    more = f" 等{len(inv)}件" if len(inv) > max_items else ""
    return "随身物品：" + "、".join(parts) + more


def format_skills_snippet(agent: "Agent", *, max_n: int = 6) -> str:
    skills = list(getattr(agent, "skills", None) or [])
    if not skills:
        return "擅长：寻常生计手段（无特别技能登记）"
    names: list[str] = []
    for sk in skills[:max_n]:
        name = getattr(sk, "name", None) or (sk.get("name") if isinstance(sk, dict) else None)
        if name:
            names.append(str(name))
    return "擅长：" + ("、".join(names) if names else "寻常生计手段")


def format_nearby_line(
    society: "Society | None",
    location_id: str | None,
    self_id: str,
    *,
    max_n: int = 4,
    perception: dict[str, Any] | None = None,
) -> str:
    names: list[str] = []
    if perception and isinstance(perception.get("nearby_agents"), list):
        for row in perception["nearby_agents"][:max_n]:
            if not isinstance(row, dict):
                continue
            n = row.get("name") or row.get("id")
            act = (row.get("activity") or "").strip()
            if n:
                names.append(f"{n}" + (f"（{act}）" if act else ""))
    elif society and location_id:
        for a in society.at(location_id):
            if a.id == self_id:
                continue
            act = (a.current_activity or "").strip()
            names.append(f"{a.name}" + (f"（{act}）" if act else ""))
            if len(names) >= max_n:
                break
    if not names:
        return "近旁可见之人：无人（或你未留意）"
    return "近旁可见之人：" + "、".join(names)


def format_cast_line(agents: list["Agent"], *, max_n: int = 6) -> str:
    parts: list[str] = []
    for a in agents[:max_n]:
        tag = a.profession or (a.traits[0] if a.traits else "")
        act = (a.current_activity or "").strip()
        bits = [a.name]
        if tag:
            bits.append(tag)
        if act:
            bits.append(act)
        parts.append("·".join(bits) if len(bits) > 1 else a.name)
    return "、".join(parts) if parts else "（无人）"


def perception_radius_for(agent: "Agent") -> float:
    """Map-unit radius for fine-grained awareness within/near a location.

    Profession / trait / skills can slightly widen or shrink cognition.
    """
    from ..config import get_settings
    base = float(getattr(get_settings(), "perception_radius", 0.18) or 0.18)
    blob = " ".join([
        agent.profession or "",
        " ".join(agent.traits or []),
        " ".join(getattr(sk, "name", "") or "" for sk in (agent.skills or [])),
    ])
    if any(k in blob for k in ("眼观", "耳报", "斥候", "探子", "听江", "暗哨", "打听")):
        return base * 1.45
    if any(k in blob for k in ("醉", "沉睡", "盲目", "耳背")):
        return base * 0.65
    return base


def ability_scope_rules(agent: "Agent") -> str:
    """Hard constraints: do not claim powers beyond profession/skills."""
    skills = format_skills_snippet(agent)
    profession = agent.profession or "无固定职业"
    return (
        f"能力边界：你是【{profession}】；{skills}。"
        "不得声称或施展未列出的武功、法术、官印、器械或情报渠道；"
        "若对方要求超出能力，应以本分推辞、回避或转求他人，不可凭空成功。"
    )


def cognitive_scope_rules(agent: "Agent", *, location_name: str | None = None) -> str:
    loc = location_name or agent.location_id or "当下所在之处"
    return (
        f"认知边界：你只确知【{loc}】视野/听力范围内刚刚发生、"
        "自己亲历、以及记忆里留下的事；不得知晓远方密室、他人内心独白、"
        "未传入此地的军政机密。对不确定之事用猜测口吻，不可当作既定事实。"
    )


def civilization_grounding(world: "World") -> str:
    rules = "；".join(world.rules[:6]) if world.rules else "无额外明文法则"
    return (
        f"文明环境：《{world.name}》（{world.genre}）。"
        f"世界前提：{(world.premise or '')[:180]}。"
        f"须遵守的世界法则：{rules}。"
        "言谈举止、称谓、物价直觉与道德判断须符合该文明，勿串入现代用语或他界设定。"
    )


def build_reaction_brief(
    agent: "Agent",
    world: "World",
    *,
    location_name: str | None = None,
    society: "Society | None" = None,
    perception: dict[str, Any] | None = None,
    other_id: str | None = None,
    other_name: str = "",
) -> str:
    """Compact block injected into think / reply_to user messages."""
    loc = location_name or (
        perception.get("location_name") if perception else None
    ) or agent.location_id or "未知之地"
    chunks = [
        civilization_grounding(world),
        cognitive_scope_rules(agent, location_name=str(loc)),
        ability_scope_rules(agent),
        f"你正在【{loc}】。",
        f"你的当下生活状态：\n{format_life_ctx(agent)}",
        format_inventory_snippet(agent),
        format_nearby_line(
            society, agent.location_id, agent.id, perception=perception,
        ),
    ]
    rel = format_relation_line(agent, other_id, other_name)
    if rel:
        chunks.append(rel)
    return "\n".join(chunks)


def enrich_agent_for_live(agent: "Agent", society: "Society") -> dict[str, Any]:
    """Extra fields for live_simulation compact context."""
    nearby = []
    if agent.location_id:
        for o in society.at(agent.location_id):
            if o.id == agent.id:
                continue
            nearby.append(o.id)
            if len(nearby) >= 6:
                break
    inv_names: list[str] = []
    for it in list(getattr(agent, "inventory", None) or [])[:5]:
        name = getattr(it, "name", None) or (it.get("name") if isinstance(it, dict) else None)
        if name:
            inv_names.append(str(name))
    skill_names: list[str] = []
    for sk in list(getattr(agent, "skills", None) or [])[:6]:
        name = getattr(sk, "name", None) or (sk.get("name") if isinstance(sk, dict) else None)
        if name:
            skill_names.append(str(name))
    return {
        "inventory": inv_names,
        "skills": skill_names,
        "nearby_ids": nearby,
        "perception_radius": round(perception_radius_for(agent), 3),
    }
