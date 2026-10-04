"""Environmental evolution lab — regional pollution from enterprise emissions."""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

REGIONS: list[dict[str, Any]] = [
    {"key": "pond", "name": "池塘", "sensitivity": 1.35, "recovery": 0.12, "asset_base": 80},
    {"key": "river", "name": "江河", "sensitivity": 1.10, "recovery": 0.08, "asset_base": 200},
    {"key": "lake", "name": "湖泊", "sensitivity": 1.20, "recovery": 0.06, "asset_base": 350},
    {"key": "sea", "name": "海域", "sensitivity": 0.85, "recovery": 0.04, "asset_base": 800},
    {"key": "forest", "name": "林地", "sensitivity": 1.05, "recovery": 0.10, "asset_base": 260},
    {"key": "mountain", "name": "山地", "sensitivity": 0.95, "recovery": 0.09, "asset_base": 180},
    {"key": "field", "name": "农田", "sensitivity": 1.25, "recovery": 0.11, "asset_base": 420},
    {"key": "desert", "name": "沙地", "sensitivity": 0.70, "recovery": 0.03, "asset_base": 60},
]

MEASURES: list[dict[str, Any]] = [
    {"key": "none", "name": "无措施", "emit_factor": 1.0, "recovery_boost": 0.0, "cost": 0},
    {"key": "emission_cap", "name": "排放总量控制", "emit_factor": 0.65, "recovery_boost": 0.02, "cost": 40},
    {"key": "treatment", "name": "末端治理设施", "emit_factor": 0.45, "recovery_boost": 0.05, "cost": 80},
    {"key": "relocate", "name": "企业搬迁", "emit_factor": 0.25, "recovery_boost": 0.08, "cost": 120},
    {"key": "restore", "name": "生态修复", "emit_factor": 0.85, "recovery_boost": 0.18, "cost": 90},
]


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:16], 16)


@dataclass
class EnvironmentLab:
    seed: str
    civilization_key: str = ""
    civilization_name: str = ""
    region_key: str = "river"
    measure_key: str = "none"
    emission_intensity: float = 0.6
    enterprise_name: str = "示范企业"
    pollution: float = 0.08
    pollution_rate: float = 0.0
    health_index: float = 0.92
    property_damage: float = 0.0
    tick: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    last_result: dict[str, Any] | None = None

    @classmethod
    def create(cls, *, seed: str, civ_ctx: dict[str, Any]) -> "EnvironmentLab":
        label = (civ_ctx.get("name") or "本地").split("·")[0][:12]
        return cls(
            seed=seed,
            civilization_key=civ_ctx.get("key", ""),
            civilization_name=civ_ctx.get("name", ""),
            enterprise_name=f"{label}工业",
        )

    def _region(self) -> dict[str, Any]:
        return next((r for r in REGIONS if r["key"] == self.region_key), REGIONS[1])

    def _measure(self) -> dict[str, Any]:
        return next((m for m in MEASURES if m["key"] == self.measure_key), MEASURES[0])

    def _rng(self) -> random.Random:
        return random.Random(_seed_int(self.seed, str(self.tick)))

    def prepare_simulation(
        self,
        *,
        region_key: str | None = None,
        measure_key: str | None = None,
        emission_intensity: float | None = None,
        enterprise_name: str | None = None,
        timeline_events: list[dict[str, Any]] | None = None,
    ) -> None:
        if region_key and region_key in {r["key"] for r in REGIONS}:
            self.region_key = region_key
        if measure_key and measure_key in {m["key"] for m in MEASURES}:
            self.measure_key = measure_key
        if emission_intensity is not None:
            self.emission_intensity = max(0.05, min(1.0, float(emission_intensity)))
        if enterprise_name:
            self.enterprise_name = enterprise_name[:40]
        self.pollution = 0.08
        self.pollution_rate = 0.0
        self.health_index = 0.92
        self.property_damage = 0.0
        self.tick = 0
        self.history = []
        self.last_result = None
        self.timeline_events = list(timeline_events or [])

    def simulate(self, steps: int = 36) -> dict[str, Any]:
        steps = max(1, min(120, int(steps)))
        region = self._region()
        measure = self._measure()
        sens = region["sensitivity"]
        recover_base = region["recovery"] + measure["recovery_boost"]
        emit = self.emission_intensity * measure["emit_factor"]
        events_by_step: dict[int, list] = {}
        for ev in self.timeline_events:
            events_by_step.setdefault(int(ev.get("at_step") or 0), []).append(ev)

        for _ in range(steps):
            self.tick += 1
            r = self._rng()
            for ev in events_by_step.get(self.tick, []):
                mag = float(ev.get("magnitude") or 0.1)
                kind = str(ev.get("kind") or "")
                if kind in ("spill", "accident", "emission"):
                    emit = min(1.0, emit + abs(mag) * 0.15)
                elif kind in ("policy", "restore"):
                    emit = max(0.05, emit - abs(mag) * 0.1)

            delta = emit * sens * 0.025 * (0.85 + r.random() * 0.3)
            recovery = recover_base * (0.8 + r.random() * 0.4) * max(0.2, 1.0 - self.pollution)
            self.pollution = max(0.0, min(1.0, self.pollution + delta - recovery * 0.015))
            self.pollution_rate = delta
            self.health_index = max(0.0, min(1.0, 0.95 - self.pollution * 0.85))
            dmg_inc = delta * region["asset_base"] * 0.6 * (1.1 - self.health_index)
            self.property_damage += dmg_inc

            self.history.append({
                "tick": self.tick,
                "pollution": round(self.pollution, 4),
                "pollution_rate": round(self.pollution_rate, 4),
                "health_index": round(self.health_index, 3),
                "property_damage": round(self.property_damage, 1),
            })

        tail = self.history[-1] if self.history else {}
        time_to_threshold = _estimate_threshold_steps(self.history, 0.5)
        recovery_eta = _estimate_recovery_steps(self.history)
        result = {
            "steps": steps,
            "region": region,
            "measure": measure,
            "enterprise": self.enterprise_name,
            "emission_intensity": self.emission_intensity,
            "effective_emission": emit,
            "pollution": tail.get("pollution", 0),
            "pollution_rate": tail.get("pollution_rate", 0),
            "health_index": tail.get("health_index", 0),
            "property_damage": tail.get("property_damage", 0),
            "time_to_threshold": time_to_threshold,
            "recovery_eta": recovery_eta,
            "recommendations": _recommendations(region, measure, tail, time_to_threshold, recovery_eta),
        }
        self.last_result = result
        return result

    def snapshot(self) -> dict[str, Any]:
        region = self._region()
        measure = self._measure()
        return {
            "seed": self.seed,
            "civilization_key": self.civilization_key,
            "civilization_name": self.civilization_name,
            "region_key": self.region_key,
            "measure_key": self.measure_key,
            "region_name": region["name"],
            "measure_name": measure["name"],
            "enterprise_name": self.enterprise_name,
            "emission_intensity": self.emission_intensity,
            "regions": REGIONS,
            "measures": MEASURES,
            "pollution": self.pollution,
            "health_index": self.health_index,
            "property_damage": self.property_damage,
            "history": self.history[-48:],
            "last_result": self.last_result,
        }


def _estimate_threshold_steps(history: list[dict], threshold: float) -> int | None:
    for row in history:
        if row.get("pollution", 0) >= threshold:
            return int(row["tick"])
    return None


def _estimate_recovery_steps(history: list[dict]) -> int | None:
    if len(history) < 4:
        return None
    peak = max(h.get("pollution", 0) for h in history)
    if peak < 0.2:
        return 0
    for i in range(len(history) - 3, -1, -1):
        if history[i]["pollution"] > history[-1]["pollution"] + 0.05:
            return max(0, len(history) - i)
    return None


def _recommendations(region, measure, tail, t_thresh, rec_eta) -> list[str]:
    recs = [
        f"{region['name']}区域 · 企业排放经「{measure['name']}」后的污染演化。",
        f"当前污染强度 {tail.get('pollution', 0):.1%}，健康指数 {tail.get('health_index', 0):.0%}。",
        f"累计财产损失（相对单位）{tail.get('property_damage', 0):.0f}。",
    ]
    if t_thresh:
        recs.append(f"预计第 {t_thresh} 周期污染超 50% 警戒阈值。")
    else:
        recs.append("本周期内未突破 50% 污染阈值。")
    if measure["key"] == "none":
        recs.append("建议至少启动排放总量控制或末端治理以延缓污染累积。")
    if rec_eta is not None and rec_eta > 0:
        recs.append(f"若维持当前措施，生态恢复可见拐点约需 {rec_eta} 个周期。")
    if measure["recovery_boost"] > 0.1:
        recs.append("生态修复措施显著抬升恢复速度，但需持续投入。")
    return recs
