"""Weather evolution lab — role-specific impact reports."""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

WEATHER_PATTERNS = [
    {"key": "drought", "name": "持续干旱", "temp_delta": 1.2, "precip_delta": -0.35, "extreme": 0.2},
    {"key": "flood", "name": "暴雨洪涝", "temp_delta": -0.3, "precip_delta": 0.45, "extreme": 0.35},
    {"key": "cold_snap", "name": "寒潮冻害", "temp_delta": -2.0, "precip_delta": 0.05, "extreme": 0.25},
    {"key": "heat_wave", "name": "高温热浪", "temp_delta": 2.5, "precip_delta": -0.15, "extreme": 0.30},
    {"key": "windstorm", "name": "大风沙尘", "temp_delta": 0.5, "precip_delta": -0.20, "extreme": 0.22},
    {"key": "normal_var", "name": "季节波动", "temp_delta": 0.0, "precip_delta": 0.0, "extreme": 0.08},
]

ROLES: list[dict[str, Any]] = [
    {
        "key": "farmer",
        "name": "农户",
        "focus": "作物收成、灌溉、霜冻与病虫害风险",
        "metrics": ["crop_yield", "irrigation_stress", "loss_risk"],
    },
    {
        "key": "herder",
        "name": "牧民",
        "focus": "草场载畜、转场、雪灾与饲草储备",
        "metrics": ["pasture_index", "livestock_stress", "feed_reserve"],
    },
    {
        "key": "government",
        "name": "政府",
        "focus": "赈济、粮储、迁移安置与财政压力",
        "metrics": ["relief_burden", "grain_reserve", "fiscal_stress"],
    },
    {
        "key": "transport",
        "name": "运输",
        "focus": "路网中断、运费、时效与货损",
        "metrics": ["route_disruption", "freight_cost", "delay_hours"],
    },
]


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:16], 16)


@dataclass
class WeatherLab:
    seed: str
    civilization_key: str = ""
    civilization_name: str = ""
    role_key: str = "farmer"
    pattern_key: str = "normal_var"
    temperature: float = 18.0
    precipitation: float = 0.55
    extreme_index: float = 0.12
    tick: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    last_result: dict[str, Any] | None = None

    @classmethod
    def create(cls, *, seed: str, civ_ctx: dict[str, Any]) -> "WeatherLab":
        return cls(
            seed=seed,
            civilization_key=civ_ctx.get("key", ""),
            civilization_name=civ_ctx.get("name", ""),
        )

    def _pattern(self) -> dict[str, Any]:
        return next((p for p in WEATHER_PATTERNS if p["key"] == self.pattern_key), WEATHER_PATTERNS[-1])

    def _role(self) -> dict[str, Any]:
        return next((r for r in ROLES if r["key"] == self.role_key), ROLES[0])

    def _rng(self) -> random.Random:
        return random.Random(_seed_int(self.seed, str(self.tick)))

    def prepare_simulation(
        self,
        *,
        role_key: str | None = None,
        pattern_key: str | None = None,
        timeline_events: list[dict[str, Any]] | None = None,
    ) -> None:
        if role_key and role_key in {r["key"] for r in ROLES}:
            self.role_key = role_key
        if pattern_key and pattern_key in {p["key"] for p in WEATHER_PATTERNS}:
            self.pattern_key = pattern_key
        pat = self._pattern()
        self.temperature = 18.0 + pat["temp_delta"]
        self.precipitation = max(0.05, min(1.0, 0.55 + pat["precip_delta"]))
        self.extreme_index = pat["extreme"]
        self.tick = 0
        self.history = []
        self.last_result = None
        self.timeline_events = list(timeline_events or [])

    def _role_metrics(self) -> dict[str, float]:
        role = self._role()
        t, p, e = self.temperature, self.precipitation, self.extreme_index
        if role["key"] == "farmer":
            return {
                "crop_yield": max(0.0, 1.0 - abs(p - 0.5) * 1.2 - e * 0.8),
                "irrigation_stress": max(0.0, min(1.0, (0.5 - p) * 1.5 + e * 0.4)),
                "loss_risk": max(0.0, min(1.0, e + abs(t - 20) * 0.04)),
            }
        if role["key"] == "herder":
            return {
                "pasture_index": max(0.0, min(1.0, p * 0.9 - e * 0.5)),
                "livestock_stress": max(0.0, min(1.0, e + max(0, -t) * 0.08)),
                "feed_reserve": max(0.0, min(1.0, 0.7 - e * 0.6 - (0.5 - p) * 0.3)),
            }
        if role["key"] == "government":
            burden = e * 0.6 + max(0, 0.45 - p) * 0.5 + max(0, t - 28) * 0.05
            return {
                "relief_burden": max(0.0, min(1.0, burden)),
                "grain_reserve": max(0.0, min(1.0, 0.75 - burden * 0.5)),
                "fiscal_stress": max(0.0, min(1.0, burden * 0.85)),
            }
        # transport
        return {
            "route_disruption": max(0.0, min(1.0, e * 0.7 + max(0, 0.6 - p) * 0.4)),
            "freight_cost": max(1.0, 1.0 + e * 0.9 + max(0, -t) * 0.03),
            "delay_hours": max(0.0, e * 48 + max(0, 0.55 - p) * 24),
        }

    def simulate(self, steps: int = 24) -> dict[str, Any]:
        steps = max(1, min(120, int(steps)))
        pat = self._pattern()
        role = self._role()
        events_by_step: dict[int, list] = {}
        for ev in self.timeline_events:
            events_by_step.setdefault(int(ev.get("at_step") or 0), []).append(ev)

        for _ in range(steps):
            self.tick += 1
            r = self._rng()
            for ev in events_by_step.get(self.tick, []):
                mag = float(ev.get("magnitude") or 0.1)
                self.extreme_index = max(0.0, min(1.0, self.extreme_index + abs(mag) * 0.2))
                self.precipitation = max(0.05, min(1.0, self.precipitation + mag * 0.1))

            self.temperature += pat["temp_delta"] * 0.02 + (r.random() - 0.5) * 0.4
            self.precipitation = max(0.05, min(1.0, self.precipitation + pat["precip_delta"] * 0.03 + (r.random() - 0.5) * 0.05))
            self.extreme_index = max(0.0, min(1.0, self.extreme_index + pat["extreme"] * 0.02 - 0.005))

            metrics = self._role_metrics()
            row: dict[str, Any] = {"tick": self.tick, "temperature": round(self.temperature, 2), "precipitation": round(self.precipitation, 3)}
            row.update({k: round(v, 3) if isinstance(v, float) else v for k, v in metrics.items()})
            self.history.append(row)

        tail = self.history[-1] if self.history else {}
        result = {
            "steps": steps,
            "role": role,
            "pattern": pat,
            "metrics": tail,
            "role_summary": _role_summary(role, pat, tail),
            "recommendations": _role_recommendations(role, pat, tail),
        }
        self.last_result = result
        return result

    def snapshot(self) -> dict[str, Any]:
        role = self._role()
        pat = self._pattern()
        return {
            "seed": self.seed,
            "civilization_key": self.civilization_key,
            "civilization_name": self.civilization_name,
            "role_key": self.role_key,
            "pattern_key": self.pattern_key,
            "role_name": role["name"],
            "pattern_name": pat["name"],
            "roles": ROLES,
            "patterns": WEATHER_PATTERNS,
            "temperature": self.temperature,
            "precipitation": self.precipitation,
            "extreme_index": self.extreme_index,
            "history": self.history[-48:],
            "last_result": self.last_result,
        }


def _role_summary(role: dict, pat: dict, tail: dict) -> str:
    if role["key"] == "farmer":
        y = tail.get("crop_yield", 0)
        return f"在「{pat['name']}」下，预计收成指数 {y:.0%}，需关注灌溉与减损。"
    if role["key"] == "herder":
        return f"草场指数 {tail.get('pasture_index', 0):.0%}，牲畜应激 {tail.get('livestock_stress', 0):.0%}。"
    if role["key"] == "government":
        return f"赈济负担 {tail.get('relief_burden', 0):.0%}，粮储 {tail.get('grain_reserve', 0):.0%}。"
    return f"路网中断风险 {tail.get('route_disruption', 0):.0%}，运费倍数 {tail.get('freight_cost', 1):.2f}。"


def _role_recommendations(role: dict, pat: dict, tail: dict) -> list[str]:
    recs = [f"{role['name']}视角：{role['focus']}"]
    if role["key"] == "farmer" and tail.get("irrigation_stress", 0) > 0.5:
        recs.append("灌溉压力偏高：优先保障水源调度与改种耐旱作物。")
    if role["key"] == "herder" and tail.get("feed_reserve", 1) < 0.4:
        recs.append("饲草储备不足：提前转场或控畜头数。")
    if role["key"] == "government" and tail.get("relief_burden", 0) > 0.55:
        recs.append("赈济压力上升：启动粮储释放与跨区调运预案。")
    if role["key"] == "transport" and tail.get("route_disruption", 0) > 0.5:
        recs.append("路网风险高：切换铁路/水运并上调应急运力。")
    recs.append(f"气候模式：{pat['name']}。")
    return recs
