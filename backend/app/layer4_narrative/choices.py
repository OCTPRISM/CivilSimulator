"""Structured player choices — clear UI labels + narrative actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Choice:
    label: str      # short button title
    hint: str       # one-line consequence / meaning
    action: str     # full text fed to director as player_input

    def as_dict(self) -> dict[str, str]:
        return {"label": self.label, "hint": self.hint, "action": self.action}


# 风波渡开场：直白说明每个选项在做什么
FENGBO_FERRY_CHOICES: list[Choice] = [
    Choice(
        label="走近对峙",
        hint="站到岸上无名长剑前，当面质问来者",
        action="我走上渡口木桩，站到无名长剑前，直视眼前之人并开口质问。",
    ),
    Choice(
        label="戒备观察",
        hint="不贸然靠近，按剑而立，留意渡口上下动静",
        action="我停在原地，手按剑柄戒备，打量渡口与在场各路人马。",
    ),
    Choice(
        label="暂时离开",
        hint="不与当下风波纠缠，先抽身离开渡口",
        action="我收住脚步，转身离开渡口，记下此地蹊跷日后再查。",
    ),
]

_GENRE_DEFAULTS: dict[str, list[Choice]] = {
    "wuxia": FENGBO_FERRY_CHOICES,
    "ancient": [
        Choice("当面陈情", "走到堂前，把来意当面说清楚", "我上前一步，向堂上之人拱手陈情。"),
        Choice("静观其变", "先不表态，观察局势再作打算", "我退后半步，静观堂上众人神色。"),
        Choice("告辞离去", "觉得不宜久留，先行告退", "我拱手告辞，转身退出厅堂。"),
    ],
    "scifi": [
        Choice("上前交涉", "靠近对方，尝试直接沟通", "我走向对方，打开通讯频道尝试交涉。"),
        Choice("扫描环境", "用设备扫描周围，收集情报", "我启动扫描仪，分析周围能量与生命体征。"),
        Choice("撤离现场", "情况不明，先撤出当前区域", "我标记坐标后，沿安全路线撤离。"),
    ],
    "mystery": [
        Choice("追问线索", "就疑点继续追问在场之人", "我盯住关键证人，就疑点追问到底。"),
        Choice("搜查现场", "趁人不备，仔细搜查现场", "我借口踱步，暗中搜查现场蛛丝马迹。"),
        Choice("暂且回避", "先离开现场，从别处打听", "我装作无事，离开现场从旁打听消息。"),
    ],
}


def choices_for_scene(*, location_name: str = "", genre: str = "ancient") -> list[Choice]:
    if "风波渡" in location_name or "渡船" in location_name:
        return list(FENGBO_FERRY_CHOICES)
    return list(_GENRE_DEFAULTS.get(genre, _GENRE_DEFAULTS["ancient"]))


def normalize_choices(raw: Any, *, location_name: str = "", genre: str = "ancient") -> list[dict]:
    """Accept legacy string[] or structured objects; always return dicts."""
    if not raw:
        return [c.as_dict() for c in choices_for_scene(location_name=location_name, genre=genre)]

    out: list[dict] = []
    for item in raw:
        if isinstance(item, str):
            out.append(_legacy_string_to_choice(item).as_dict())
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or "").strip()
            hint = str(item.get("hint") or item.get("description") or "").strip()
            action = str(item.get("action") or item.get("text") or label).strip()
            if not label:
                continue
            if not hint:
                hint = action[:48] if action else label
            if not action:
                action = label
            out.append({"label": label, "hint": hint, "action": action})
    return out or [c.as_dict() for c in choices_for_scene(location_name=location_name, genre=genre)]


def _legacy_string_to_choice(s: str) -> Choice:
    legacy = {
        "上前一步": Choice("走近对峙", "靠近眼前之人或事发中心", "我上前一步，逼近眼前之人。"),
        "按住腰间": Choice("戒备观察", "手按兵器，提防四周", "我按住腰间兵刃，戒备地打量四周。"),
        "转身离去": Choice("暂时离开", "不与当下风波纠缠，先离开", "我转身离去，暂避锋芒。"),
        "环顾四周": Choice("观察四周", "打量环境与人物动向", "我环顾四周，打量此地人事。"),
        "保持沉默": Choice("静观其变", "不表态，先看局势如何发展", "我保持沉默，静观局势。"),
    }
    return legacy.get(s, Choice(s, s, s))
