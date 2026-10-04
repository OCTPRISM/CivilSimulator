"""LLM-assisted event structuring — NER → LabEvent fields only.

LLM never generates simulation numbers (index, price, etc.).
On failure, falls back to rule-based parser.
"""
from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from ..layer1_foundation import LLM, Message
from .datasets import TimelineEvent, _parse_step_from_text, parse_manual_events
from ..layer2_civilization.finance_sim_core import TRANSMISSION, CHANNEL_LABELS

_VALID_KINDS = set(TRANSMISSION.keys()) | {
    "political", "policy", "rate", "war", "plague", "earthquake",
    "price", "property", "earnings", "product", "scandal", "custom",
}


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


def _rule_parse_one(item: dict[str, Any], idx: int) -> TimelineEvent | None:
    parsed = parse_manual_events([item])
    return parsed[0] if parsed else None


async def structure_event_with_llm(
    llm: LLM | None,
    *,
    title: str,
    time_label: str = "",
    description: str = "",
    civilization_name: str = "",
    genre: str = "modern",
    institutions: list[dict[str, Any]] | None = None,
) -> TimelineEvent:
    """Infer kind, magnitude, channels from prose. No forecast numbers."""
    fallback_item = {
        "title": title,
        "time": time_label or "T+8",
        "description": description,
        "kind": "custom",
        "magnitude": 0.15,
    }
    if llm is None:
        ev = _rule_parse_one(fallback_item, 0)
        return ev or TimelineEvent(
            id=f"ev_{uuid4().hex[:8]}",
            time_label=time_label or "T+8",
            at_step=8,
            title=title[:120],
            description=description[:300],
            magnitude=0.15,
            kind="custom",
            source="rule",
        )

    inst_names = [i.get("name", "") for i in (institutions or [])[:6]]
    channel_hint = "、".join(f"{k}({v})" for k, v in list(CHANNEL_LABELS.items())[:6])
    sys = (
        "你是金融事件结构化器。根据用户描述，输出 JSON，不要输出任何指数/股价/预测数字。"
        '{"title": str, "time_label": str, "at_step": int, "kind": str, '
        '"magnitude": float(-1..1), "channels": {str: float}, '
        '"entities": [str], "rationale": str}'
        f"\n合法 kind: {', '.join(sorted(_VALID_KINDS))}"
        f"\n通道参考: {channel_hint}"
        "\nmagnitude 表示冲击强度与方向，不是百分比预测。"
    )
    usr = json.dumps({
        "title": title,
        "time": time_label,
        "description": description,
        "civilization": civilization_name,
        "genre": genre,
        "institutions": inst_names,
    }, ensure_ascii=False)

    try:
        resp = await llm.chat(
            [Message("system", sys), Message("user", usr)],
            temperature=0.2, max_tokens=400, json_mode=True,
        )
        data = _safe_json(resp.content)
        if not data:
            raise ValueError("invalid json")
        kind = str(data.get("kind") or "custom")
        if kind not in _VALID_KINDS:
            kind = "custom"
        mag = max(-1.0, min(1.0, float(data.get("magnitude") or 0.15)))
        tl = str(data.get("time_label") or time_label or "T+8")[:40]
        step = int(data.get("at_step") if data.get("at_step") is not None else _parse_step_from_text(tl, 8))
        channels = data.get("channels") if isinstance(data.get("channels"), dict) else {}
        rationale = str(data.get("rationale") or description)[:300]
        ch_preview = {
            k: round(float(v), 4) for k, v in channels.items()
            if isinstance(v, (int, float))
        }
        return TimelineEvent(
            id=f"ev_{uuid4().hex[:8]}",
            time_label=tl,
            at_step=max(0, step),
            title=str(data.get("title") or title)[:120],
            description=rationale,
            magnitude=mag,
            kind=kind,
            source="llm_ner",
            channel_preview=ch_preview,
            entities=[str(x) for x in (data.get("entities") or [])][:8],
            rationale=rationale,
        )
    except Exception:
        ev = _rule_parse_one(fallback_item, 0)
        if ev:
            ev.source = "rule_fallback"
            return ev
        return TimelineEvent(
            id=f"ev_{uuid4().hex[:8]}",
            time_label=time_label or "T+8",
            at_step=8,
            title=title[:120],
            description=description[:300],
            magnitude=0.15,
            kind="custom",
            source="rule_fallback",
        )


async def structure_events_batch(
    llm: LLM | None,
    items: list[dict[str, Any]],
    *,
    civilization_name: str = "",
    genre: str = "modern",
    institutions: list[dict[str, Any]] | None = None,
    use_llm: bool = True,
) -> list[TimelineEvent]:
    out: list[TimelineEvent] = []
    for i, it in enumerate(items):
        title = str(it.get("title") or it.get("text") or "").strip()
        if not title:
            continue
        if use_llm and llm is not None:
            ev = await structure_event_with_llm(
                llm,
                title=title,
                time_label=str(it.get("time") or it.get("time_label") or f"T+{i * 4}")[:40],
                description=str(it.get("description") or it.get("note") or "")[:300],
                civilization_name=civilization_name,
                genre=genre,
                institutions=institutions,
            )
        else:
            ev = _rule_parse_one(it, i)
            if not ev:
                continue
        out.append(ev)
    return out


def enrich_timeline_event(ev: dict[str, Any]) -> dict[str, Any]:
    """Attach channel preview for UI from kind."""
    kind = str(ev.get("kind") or "custom")
    tx = TRANSMISSION.get(kind) or TRANSMISSION["custom"]
    ev = dict(ev)
    if not ev.get("channel_preview"):
        ev["channel_preview"] = {
            ch: round(float(coef) * float(ev.get("magnitude") or 0.15), 4)
            for ch, coef in tx.items()
        }
    return ev
