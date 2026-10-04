"""Deterministic, dependency-free LLM used for offline development & tests."""
from __future__ import annotations

import hashlib
import json
import random
from typing import Iterable

from .base import LLM, LLMResponse, Message

_FLAVORS = {
    "ancient": ["拱手", "执剑", "策马", "举杯", "焚香"],
    "scifi":   ["启动反应堆", "调取舰桥日志", "扫描生命体征", "校准跃迁坐标"],
    "wuxia":   ["剑指", "运起内力", "袖中飞针", "踏雪无痕"],
    "xuanhuan":["凝聚灵力", "结印", "掐诀念咒", "踏星辰步"],
    "mystery": ["皱眉", "压低声音", "翻开案卷", "凝视那道血痕"],
}

# Narration branches keyed by choice label substring
_FENGBO_OUTCOMES: dict[str, str] = {
    "走近": "木桩吱呀作响，你踏过血色江波映出的夕照，站到那柄无名长剑之前。剑身寒光微颤，对岸有人抬眼。",
    "戒备": "你未再往前，只将手掌压在剑柄上。渡口风紧，说书人的醒木停了半拍，无面客的目光从斗笠下掠过。",
    "离开": "你转身沿栈道退去，江风把衣袂吹得猎猎。身后有人低语「此人倒识趣」，你却把渡口乱象牢牢记下。",
    "对峙": "木桩吱呀作响，你踏过血色江波映出的夕照，站到那柄无名长剑之前。剑身寒光微颤，对岸有人抬眼。",
    "观察": "你未再往前，只将手掌压在剑柄上。渡口风紧，说书人的醒木停了半拍，无面客的目光从斗笠下掠过。",
    "暂时": "你转身沿栈道退去，江风把衣袂吹得猎猎。身后有人低语「此人倒识趣」，你却把渡口乱象牢牢记下。",
}


def _pick_fengbo_narration(player_action: str, beat: str) -> str:
    for key, text in _FENGBO_OUTCOMES.items():
        if key in player_action:
            return text
    return f"江面夕照如血，{beat}，渡口上的气氛陡然一紧。"


def _fengbo_opening() -> str:
    return (
        "黄昏的风波渡，江面映着血色残阳。渡船系在木桩上咿呀轻晃，"
        "岸上斜插一柄无名长剑。醉狐倚着酒葫芦打量来客，无面客立在暗处，"
        "苏怀玉剑穗微动——众人似乎都在等一个人先开口。"
    )


class MockLLM(LLM):
    name = "mock"

    async def chat(
        self,
        messages: Iterable[Message],
        *,
        temperature: float = 0.8,
        max_tokens: int = 512,
        **_kwargs,
    ) -> LLMResponse:
        msgs = list(messages)
        last = msgs[-1].content if msgs else ""
        sys = next((m.content for m in msgs if m.role == "system"), "")
        seed = int(hashlib.sha1((sys + last).encode()).hexdigest(), 16) % (2**31)
        rng = random.Random(seed)

        flavor_key = next((k for k in _FLAVORS if k in (sys + last).lower()), "ancient")
        beat = rng.choice(_FLAVORS[flavor_key])

        if "JSON" in sys or "json" in last:
            from ..layer4_narrative.choices import choices_for_scene, normalize_choices

            location = ""
            if "地点：" in last:
                location = last.split("地点：", 1)[1].split("\n", 1)[0].strip()

            player_choice = ""
            if "上一幕玩家选择：" in last:
                player_choice = last.split("上一幕玩家选择：", 1)[1].split("\n", 1)[0].strip()
                if player_choice == "（开场）":
                    player_choice = ""

            is_fengbo = "风波渡" in location or "渡船" in location
            if is_fengbo and not player_choice:
                narr = _fengbo_opening()
            elif is_fengbo and player_choice:
                narr = _pick_fengbo_narration(player_choice, beat)
            elif player_choice:
                short = player_choice[:20].replace('"', "")
                narr = f"你选择了「{short}」——{beat}，周遭局势随之生变。"
            else:
                narr = f"{beat}，空气仿佛凝固了一瞬。"

            genre = "wuxia" if flavor_key == "wuxia" or is_fengbo else flavor_key
            choices = [c.as_dict() for c in choices_for_scene(location_name=location, genre=genre)]
            payload = {"narration": narr, "choices": choices}
            content = json.dumps(payload, ensure_ascii=False)
        else:
            content = f"{beat}。{last[-40:]}……（mock-llm）"

        return LLMResponse(content=content, model="mock-1", raw=None)
