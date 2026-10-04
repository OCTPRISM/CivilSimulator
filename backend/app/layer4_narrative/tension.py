"""Dramatic tension tracker.

Estimates a 0..1 tension score per page from cheap signals (keyword density,
beat kinds, beat length) — no extra LLM call required.  When the rolling
average drops below threshold, Director injects a conflict event next page.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from .scene import Beat, Page

_HIGH_TENSION_HINTS = (
    # universal
    "杀", "血", "刀", "剑", "枪", "尸", "毒", "陷阱", "刺", "怒", "恨", "怖", "暗",
    "伏击", "对峙", "审讯", "追杀", "逃", "战",
    # mystery / scifi flavor
    "尸体", "证据", "敌舰", "辐射", "警", "罪", "炸",
    # xianxia / wuxia
    "天劫", "走火入魔", "封禁", "决斗", "鲜血",
)
_LOW_TENSION_HINTS = ("酒", "茶", "笑", "歌", "闲", "云", "风轻", "梦")


def beat_tension(b: Beat) -> float:
    text = b.content
    if not text:
        return 0.0
    hi = sum(1 for w in _HIGH_TENSION_HINTS if w in text)
    lo = sum(1 for w in _LOW_TENSION_HINTS if w in text)
    base = {
        "narration": 0.35,
        "speech": 0.45,
        "action": 0.6,
        "system": 0.2,
    }.get(b.kind, 0.4)
    bump = min(0.5, 0.12 * hi) - min(0.3, 0.08 * lo)
    # exclamation / ellipses are cheap proxies of tension.
    if "!" in text or "！" in text:
        bump += 0.08
    return max(0.0, min(1.0, base + bump))


def page_tension(p: Page) -> float:
    if not p.beats:
        return 0.0
    return sum(beat_tension(b) for b in p.beats) / len(p.beats)


@dataclass
class TensionTracker:
    window: int = 4
    history: deque[float] = field(default_factory=lambda: deque(maxlen=4))

    def push(self, p: Page) -> float:
        s = page_tension(p)
        self.history.append(s)
        return s

    @property
    def rolling(self) -> float:
        if not self.history:
            return 0.5
        return sum(self.history) / len(self.history)

    def is_low(self, threshold: float) -> bool:
        return len(self.history) >= 2 and self.rolling < threshold

    def to_curve(self) -> list[float]:
        return list(self.history)


# Conflict templates by genre — cheap, deterministic, no extra LLM cost.
_CONFLICT_TEMPLATES: dict[str, list[str]] = {
    "ancient":  ["远处忽然传来马蹄声，一队禁军正朝此处疾驰。", "一封无名密信落在桌上，火漆未冷。"],
    "scifi":    ["舰桥红灯亮起，未识别飞行器正以攻击航迹切入。", "AI 听涛突然中断对话，警报蜂鸣三声。"],
    "wuxia":    ["檐角飞下三道黑影，刀光直奔咽喉。", "一柄无名剑钉入门板，剑身上一个『仇』字。"],
    "xuanhuan": ["北方天裂处骤然渗出黑雾，灵气逆流。", "一股阴寒鬼气贴着脚踝爬上来。"],
    "mystery":  ["煤气灯忽地灭了，屋外有脚步在迟疑。", "桌底滑出一枚带血的纽扣。"],
}


def make_conflict_injection(genre: str) -> str:
    pool = _CONFLICT_TEMPLATES.get(genre, _CONFLICT_TEMPLATES["ancient"])
    # rotate without random so determinism aids debugging
    return pool[0]
