"""Opinion fermentation lab — cycle, nodes, interventions."""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Any


PHASES = [
    {"key": "incubation", "name": "潜伏期", "desc": "议题在小范围传播，情绪尚未聚合。"},
    {"key": "breakout", "name": "爆发期", "desc": "关键节点触发，传播速度陡升。"},
    {"key": "peak", "name": "峰值期", "desc": "舆论声量最大，极化加剧。"},
    {"key": "backlash", "name": "反噬期", "desc": "反转叙事或疲劳导致热度回落。"},
    {"key": "decay", "name": "衰减期", "desc": "议题沉淀为记忆或结构性变化。"},
]

INTERVENTIONS = [
    {"key": "media_guidance", "name": "媒体引导", "effect": -0.15, "lag": 2},
    {"key": "platform_throttle", "name": "平台限流", "effect": -0.25, "lag": 1},
    {"key": "spokesperson", "name": "官方回应", "effect": -0.10, "lag": 3},
    {"key": "fact_check", "name": "事实核查", "effect": -0.12, "lag": 2},
    {"key": "amplify", "name": "议题放大", "effect": 0.20, "lag": 1},
    {"key": "silence", "name": "冷处理", "effect": -0.05, "lag": 4},
]


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:16], 16)


@dataclass
class OpinionLab:
    seed: str
    civilization_key: str = "modern"
    civilization_name: str = "当代社会"
    topic: str = "公共议题"
    tick: int = 0
    heat: float = 0.12
    sentiment: float = 0.0
    polarization: float = 0.25
    phase_index: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    interventions: list[dict[str, Any]] = field(default_factory=list)
    pending_effects: list[dict[str, Any]] = field(default_factory=list)
    key_nodes: list[dict[str, Any]] = field(default_factory=list)
    last_result: dict[str, Any] | None = None

    @classmethod
    def create(cls, *, seed: str, civ_ctx: dict[str, Any], topic: str = "") -> "OpinionLab":
        lab = cls(
            seed=seed,
            civilization_key=civ_ctx.get("key", "modern"),
            civilization_name=civ_ctx.get("name", "文明"),
            topic=topic or f"{civ_ctx.get('name', '社会')}公共议题",
        )
        lab.key_nodes = lab._default_nodes(civ_ctx)
        return lab

    def _rng(self) -> random.Random:
        return random.Random(_seed_int(self.seed, str(self.tick)))

    def _default_nodes(self, ctx: dict[str, Any]) -> list[dict[str, Any]]:
        stage = ctx.get("current_stage") or ctx.get("premise", "")[:40]
        return [
            {"step": 6, "title": "首个爆料节点", "kind": "trigger", "magnitude": 0.35},
            {"step": 14, "title": "意见领袖介入", "kind": "amplify", "magnitude": 0.28},
            {"step": 22, "title": "政策/官方回应窗口", "kind": "intervention", "magnitude": -0.18},
            {"step": 30, "title": "次生议题分叉", "kind": "fork", "magnitude": 0.15},
            {"step": 38, "title": "舆论疲劳拐点", "kind": "decay", "magnitude": -0.25},
        ]

    @property
    def phase(self) -> dict[str, str]:
        return PHASES[min(self.phase_index, len(PHASES) - 1)]

    def apply_intervention(self, key: str, note: str = "") -> dict[str, Any]:
        meta = next((i for i in INTERVENTIONS if i["key"] == key), None)
        if not meta:
            raise ValueError(f"unknown intervention: {key}")
        rec = {
            "at_tick": self.tick,
            "key": key,
            "name": meta["name"],
            "effect": meta["effect"],
            "activates_at": self.tick + int(meta["lag"]),
            "note": note[:200],
        }
        self.interventions.append(rec)
        self.pending_effects.append(rec)
        return rec

    def insert_node(self, *, at_step: int, title: str, kind: str = "custom", magnitude: float = 0.2) -> dict[str, Any]:
        node = {"step": at_step, "title": title, "kind": kind, "magnitude": magnitude}
        self.key_nodes.append(node)
        self.key_nodes.sort(key=lambda n: n["step"])
        return node

    def simulate(self, steps: int = 24) -> dict[str, Any]:
        steps = max(1, min(120, int(steps)))
        events: list[dict[str, Any]] = []
        for _ in range(steps):
            self.tick += 1
            r = self._rng()
            # pending interventions
            active = [p for p in self.pending_effects if p["activates_at"] <= self.tick]
            self.pending_effects = [p for p in self.pending_effects if p["activates_at"] > self.tick]
            int_effect = sum(p["effect"] for p in active)
            # node hits
            node_effect = 0.0
            for node in self.key_nodes:
                if node["step"] == self.tick:
                    node_effect += float(node["magnitude"])
                    events.append({
                        "kind": "node",
                        "title": node["title"],
                        "tick": self.tick,
                    })
            # phase progression
            if self.heat < 0.25:
                self.phase_index = 0
            elif self.heat < 0.45:
                self.phase_index = 1
            elif self.heat < 0.65:
                self.phase_index = 2
            elif self.heat < 0.80:
                self.phase_index = 3
            else:
                self.phase_index = 4
            phase_mul = [0.8, 1.2, 1.0, 0.85, 0.6][self.phase_index]
            noise = (r.random() - 0.5) * 0.08
            delta = (0.04 * phase_mul + node_effect + int_effect + noise)
            self.heat = max(0.0, min(1.0, self.heat + delta))
            self.sentiment = max(-1.0, min(1.0, self.sentiment + (r.random() - 0.5) * 0.12 + node_effect * 0.3))
            self.polarization = max(0.0, min(1.0, self.polarization + abs(node_effect) * 0.15 - abs(int_effect) * 0.08))
            self.history.append({
                "tick": self.tick,
                "heat": round(self.heat, 4),
                "sentiment": round(self.sentiment, 4),
                "polarization": round(self.polarization, 4),
                "phase": self.phase["key"],
            })
        recs = []
        if self.heat > 0.6:
            recs.append("峰值期建议：准备事实核查与分级回应，避免单一口径引发反噬。")
        if self.polarization > 0.55:
            recs.append("极化偏高：考虑引入第三方背书或跨阶层对话节点。")
        if self.phase_index >= 3:
            recs.append("进入衰减/反噬阶段：可将资源转向结构性政策沟通。")
        result = {
            "steps": steps,
            "topic": self.topic,
            "civilization": self.civilization_name,
            "phase": self.phase,
            "metrics": {
                "heat": round(self.heat, 4),
                "sentiment": round(self.sentiment, 4),
                "polarization": round(self.polarization, 4),
            },
            "events": events[-10:],
            "recommendations": recs,
            "cycle_reference": PHASES,
            "intervention_catalog": INTERVENTIONS,
        }
        self.last_result = result
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "civilization_key": self.civilization_key,
            "civilization_name": self.civilization_name,
            "topic": self.topic,
            "tick": self.tick,
            "heat": self.heat,
            "sentiment": self.sentiment,
            "polarization": self.polarization,
            "phase": self.phase,
            "history": self.history[-64:],
            "key_nodes": self.key_nodes,
            "interventions": self.interventions[-20:],
            "last_result": self.last_result,
            "intervention_catalog": INTERVENTIONS,
            "cycle_reference": PHASES,
        }
