"""Offline mode decision: sleep vs continue as NPC-proxy while the user is away."""
from __future__ import annotations

import json
import random

from ..layer1_foundation import LLM, Message
from ..layer2_civilization import World
from .agent import Agent, PresenceState


def default_wander_schedule(world: World, player: Agent) -> list[dict]:
    """Fallback daily rhythm when the player has no profession schedule."""
    locs = list(world.locations.values())
    if not locs:
        return []
    home = world.locations.get(player.location_id) if player.location_id else locs[0]
    home_name = home.name if home else locs[0].name
    other = [l for l in locs if l.id != (home.id if home else None)]
    mid = other[0].name if other else home_name
    late = other[1].name if len(other) > 1 else mid
    return [
        {"from": 6, "to": 10, "location": home_name, "activity": "晨起整装，打听近况"},
        {"from": 10, "to": 14, "location": mid, "activity": "四处走动，与人攀谈"},
        {"from": 14, "to": 18, "location": late, "activity": "办手头之事，留意风声"},
        {"from": 18, "to": 22, "location": mid, "activity": "夜间活动，观察往来"},
        {"from": 22, "to": 30, "location": home_name, "activity": "歇脚休整，却未沉睡"},
    ]


def heuristic_offline_choice(player: Agent) -> tuple[str, str]:
    """No-LLM fallback: traits/goals bias toward sleep or proxy."""
    traits = " ".join(player.traits or [])
    goals = " ".join(player.goals or [])
    persona = player.persona or ""
    text = traits + goals + persona
    sleep_hints = ("谨慎", "怕事", "怯", "隐", "遁", "疲", "懒", "安稳", "守拙")
    proxy_hints = ("好奇", "执拗", "野心", "热血", "好战", "仗义", "探", "查", "寻仇", "使命")
    sleep_score = sum(1 for h in sleep_hints if h in text)
    proxy_score = sum(1 for h in proxy_hints if h in text)
    # Profession suggests staying active
    if player.profession:
        proxy_score += 1
    if proxy_score > sleep_score:
        return "proxy", f"凭性格与目标，{player.name}选择在主人离线时继续奔走。"
    if sleep_score > proxy_score:
        return "sleep", f"{player.name}决定闭目养神，错过的事明日再说。"
    # Tie-break: slight preference to proxy if they have goals, else sleep
    if player.goals:
        return "proxy", f"{player.name}心有未了之事，离线后仍以自身意志行事。"
    return "sleep", f"{player.name}选择沉睡，以待归来。"


async def decide_offline_mode(
    llm: LLM,
    world: World,
    player: Agent,
    *,
    reason: str = "offline",
) -> tuple[str, str]:
    """Return (mode, rationale) where mode is ``sleep`` or ``proxy``.

    The character decides autonomously from persona / goals / world context.
    """
    # Prefer character-driven heuristic first when persona/goals clearly lean
    # one way; LLM may refine when available.
    hinted, hint_r = heuristic_offline_choice(player)
    sys = (
        f"你是《{world.name}》中角色【{player.name}】的内心。用户（主人）即将离线。"
        "你必须以角色身份决定：继续以自主意志参与世界（proxy），还是沉睡休息（sleep）。"
        "考虑：性格、目标、当前处境、是否还有未竟之事。不要讨好用户。"
        "输出严格 JSON：{\"mode\": \"sleep\"|\"proxy\", \"rationale\": str}"
    )
    usr = (
        f"角色设定：{player.persona}\n"
        f"目标：{'；'.join(player.goals) or '无'}\n"
        f"性格：{', '.join(player.traits) or '中性'}\n"
        f"职业：{player.profession or '无'}\n"
        f"离线原因：{reason}\n"
        f"初步倾向（可覆盖）：{hinted} — {hint_r}\n"
        f"世界：{world.premise[:120]}\n"
        f"此刻：{world.clock.label()}\n"
        "请决定 mode。"
    )
    try:
        resp = await llm.chat(
            [Message("system", sys), Message("user", usr)],
            temperature=0.7, max_tokens=200,
        )
        data = _safe_json(resp.content)
        if data:
            mode = str(data.get("mode", "")).strip().lower()
            if mode in ("sleep", "proxy", "dormant"):
                if mode == "dormant":
                    mode = "sleep"
                rationale = str(data.get("rationale") or "").strip() or hint_r
                return mode, rationale
    except Exception:
        pass
    return hinted, hint_r


def _safe_json(text: str) -> dict | None:
    text = (text or "").strip()
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


def maybe_proxy_act(
    world: World,
    player: Agent,
    *,
    rng: random.Random | None = None,
) -> str | None:
    """Lightweight autonomous activity line for a proxy player this tick."""
    rng = rng or random.Random()
    if player.presence != PresenceState.PROXY:
        return None
    if rng.random() > 0.4:
        return None
    loc = world.locations.get(player.location_id) if player.location_id else None
    loc_name = loc.name if loc else "某处"
    templates = [
        f"{player.name}在{loc_name}继续谋划：{player.goals[0] if player.goals else '活下去'}。",
        f"{player.name}于{loc_name}留意往来，{player.current_activity or '悄然行动'}。",
        f"离线代行中，{player.name}在{loc_name}与人擦肩而未交手。",
    ]
    return rng.choice(templates)
