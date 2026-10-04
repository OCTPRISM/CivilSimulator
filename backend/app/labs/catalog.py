"""Experiment platform catalog — labs detached from play sessions."""
from __future__ import annotations

from typing import Any

LAB_CATALOG: list[dict[str, Any]] = [
    {
        "key": "finance",
        "name": "金融实验室",
        "blurb": "全局走势、城市金融、企业估值与散户量化沙盘；数值可复现，文案可由模型润色。",
        "status": "ready",
        "accent": "cyan",
    },
    {
        "key": "weather",
        "name": "气象演化实验室",
        "blurb": "按农户、牧民、政府、运输等视角，推演气候扰动与极端天气的区域影响。",
        "status": "ready",
        "accent": "sky",
    },
    {
        "key": "opinion",
        "name": "舆情发酵实验室",
        "blurb": "议题扩散、情绪极化与舆论场反馈回路的可控实验。",
        "status": "ready",
        "accent": "violet",
    },
    {
        "key": "policy",
        "name": "政令推演实验室",
        "blurb": "按政府机关职能与关注点，推演政令组合、执行时滞与社会响应。",
        "status": "ready",
        "accent": "amber",
    },
    {
        "key": "environment",
        "name": "环保演化实验室",
        "blurb": "池塘、江河、湖海、林山、田沙等区域的企业排放污染演化与治理措施效果。",
        "status": "ready",
        "accent": "lime",
    },
    {
        "key": "population",
        "name": "人口发展实验室",
        "blurb": "战争、天灾、政策与认知发展对人口结构的长期推演。",
        "status": "ready",
        "accent": "emerald",
    },
    {
        "key": "military",
        "name": "军事推演实验室",
        "blurb": "红蓝对抗、历史战役与战场地形对照推演。",
        "status": "ready",
        "accent": "rose",
    },
]


def list_labs() -> list[dict[str, Any]]:
    return [dict(x) for x in LAB_CATALOG]


def get_lab_meta(key: str) -> dict[str, Any] | None:
    for lab in LAB_CATALOG:
        if lab["key"] == key:
            return dict(lab)
    return None
