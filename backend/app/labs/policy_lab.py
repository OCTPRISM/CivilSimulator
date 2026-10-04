"""Policy decree simulation — government agency focus & execution lag."""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

AGENCIES: list[dict[str, Any]] = [
    {
        "key": "fiscal",
        "name": "财政司",
        "focus": "税赋、国库、转移支付与债务约束",
        "instruments": [
            {"key": "tax_cut", "name": "减税", "effect": 0.12, "lag": 2},
            {"key": "tax_raise", "name": "加税", "effect": -0.10, "lag": 3},
            {"key": "subsidy", "name": "专项补贴", "effect": 0.15, "lag": 4},
        ],
    },
    {
        "key": "civil",
        "name": "民政署",
        "focus": "户籍、赈济、基层治理与民生保障",
        "instruments": [
            {"key": "relief", "name": "开仓赈济", "effect": 0.18, "lag": 2},
            {"key": "hukou", "name": "户籍整顿", "effect": 0.05, "lag": 6},
            {"key": "local_reform", "name": "基层改制", "effect": 0.08, "lag": 8},
        ],
    },
    {
        "key": "market",
        "name": "市监台",
        "focus": "物价、垄断、质量与流通秩序",
        "instruments": [
            {"key": "price_cap", "name": "限价令", "effect": -0.08, "lag": 1},
            {"key": "anti_monopoly", "name": "反垄断", "effect": 0.10, "lag": 5},
            {"key": "standard", "name": "质量标准", "effect": 0.06, "lag": 4},
        ],
    },
    {
        "key": "security",
        "name": "警备府",
        "focus": "治安、边防、缉盗与维稳成本",
        "instruments": [
            {"key": "patrol", "name": "增派巡防", "effect": 0.14, "lag": 1},
            {"key": "curfew", "name": "宵禁", "effect": 0.05, "lag": 1},
            {"key": "arm_border", "name": "加固边关", "effect": 0.11, "lag": 3},
        ],
    },
    {
        "key": "transport",
        "name": "漕运署",
        "focus": "驿道、漕运、仓储与物流通达",
        "instruments": [
            {"key": "canal", "name": "疏浚漕渠", "effect": 0.12, "lag": 6},
            {"key": "road", "name": "修筑驿道", "effect": 0.10, "lag": 5},
            {"key": "toll", "name": "关卡调节", "effect": -0.06, "lag": 2},
        ],
    },
    {
        "key": "justice",
        "name": "刑名司",
        "focus": "律令、诉讼、赦免与政令合法性",
        "instruments": [
            {"key": "amnesty", "name": "大赦", "effect": 0.08, "lag": 1},
            {"key": "strict_law", "name": "严刑峻法", "effect": -0.05, "lag": 2},
            {"key": "codify", "name": "编修律例", "effect": 0.07, "lag": 10},
        ],
    },
]


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:16], 16)


def get_agencies_for_civ(civ_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    genre = civ_ctx.get("genre", "modern")
    if genre == "ancient":
        return [a for a in AGENCIES if a["key"] != "market"] + [
            {**AGENCIES[2], "name": "市舶司", "focus": "盐铁专卖、坊市秩序与货殖"},
        ]
    return list(AGENCIES)


@dataclass
class PolicyLab:
    seed: str
    civilization_key: str = ""
    civilization_name: str = ""
    agency_key: str = "fiscal"
    instrument_key: str = ""
    compliance: float = 0.65
    legitimacy: float = 0.58
    execution: float = 0.50
    social_response: float = 0.0
    tick: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    decrees: list[dict[str, Any]] = field(default_factory=list)
    pending: list[dict[str, Any]] = field(default_factory=list)
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    agencies: list[dict[str, Any]] = field(default_factory=list)
    last_result: dict[str, Any] | None = None

    @classmethod
    def create(cls, *, seed: str, civ_ctx: dict[str, Any]) -> "PolicyLab":
        agencies = get_agencies_for_civ(civ_ctx)
        first = agencies[0]
        inst = first["instruments"][0]
        return cls(
            seed=seed,
            civilization_key=civ_ctx.get("key", ""),
            civilization_name=civ_ctx.get("name", ""),
            agency_key=first["key"],
            instrument_key=inst["key"],
            agencies=agencies,
        )

    def _agency(self) -> dict[str, Any]:
        return next((a for a in self.agencies if a["key"] == self.agency_key), self.agencies[0])

    def _instrument(self) -> dict[str, Any]:
        ag = self._agency()
        return next(
            (i for i in ag["instruments"] if i["key"] == self.instrument_key),
            ag["instruments"][0],
        )

    def _rng(self) -> random.Random:
        return random.Random(_seed_int(self.seed, str(self.tick)))

    def prepare_simulation(
        self,
        *,
        agency_key: str | None = None,
        instrument_key: str | None = None,
        timeline_events: list[dict[str, Any]] | None = None,
    ) -> None:
        if agency_key:
            self.agency_key = agency_key
        ag = self._agency()
        if instrument_key and any(i["key"] == instrument_key for i in ag["instruments"]):
            self.instrument_key = instrument_key
        else:
            self.instrument_key = ag["instruments"][0]["key"]
        self.compliance = 0.65
        self.legitimacy = 0.58
        self.execution = 0.50
        self.social_response = 0.0
        self.tick = 0
        self.history = []
        self.decrees = []
        self.pending = []
        self.last_result = None
        self.timeline_events = list(timeline_events or [])
        inst = self._instrument()
        self.pending.append({
            "activates_at": 1,
            "effect": inst["effect"],
            "title": f"政令：{inst['name']}",
            "agency": ag["name"],
        })

    def _apply_event(self, ev: dict[str, Any]) -> None:
        mag = float(ev.get("magnitude") or 0.1)
        kind = str(ev.get("kind") or "custom")
        title = str(ev.get("title") or "事件")
        if kind in ("protest", "riot", "war"):
            self.legitimacy = max(0.05, self.legitimacy - abs(mag) * 0.25)
            self.social_response -= mag * 0.3
        elif kind in ("policy", "decree"):
            self.pending.append({
                "activates_at": self.tick + 1,
                "effect": mag,
                "title": title,
                "agency": "事件介入",
            })
        else:
            self.compliance = max(0.1, min(1.0, self.compliance + mag * 0.15))

    def simulate(self, steps: int = 24) -> dict[str, Any]:
        steps = max(1, min(120, int(steps)))
        ag = self._agency()
        inst = self._instrument()
        events_by_step: dict[int, list[dict[str, Any]]] = {}
        for ev in self.timeline_events:
            events_by_step.setdefault(int(ev.get("at_step") or 0), []).append(ev)

        battle_events: list[dict[str, Any]] = []
        for _ in range(steps):
            self.tick += 1
            for ev in events_by_step.get(self.tick, []):
                self._apply_event(ev)
                battle_events.append({"tick": self.tick, "summary": ev.get("title", "")})

            active = [p for p in self.pending if p["activates_at"] <= self.tick]
            self.pending = [p for p in self.pending if p["activates_at"] > self.tick]
            effect = sum(float(p["effect"]) for p in active)
            r = self._rng()
            noise = (r.random() - 0.5) * 0.06
            self.execution = max(0.05, min(1.0, self.execution + effect * 0.35 + noise))
            self.compliance = max(0.05, min(1.0, self.compliance + effect * 0.2 - abs(noise)))
            self.legitimacy = max(0.05, min(1.0, self.legitimacy + effect * 0.12 + self.compliance * 0.02 - 0.01))
            self.social_response = max(-1.0, min(1.0, self.social_response + effect * 0.25 + noise))

            if active:
                for p in active:
                    battle_events.append({
                        "tick": self.tick,
                        "summary": f"{p.get('agency', ag['name'])} · {p.get('title', inst['name'])}生效",
                    })

            self.history.append({
                "tick": self.tick,
                "compliance": round(self.compliance, 3),
                "legitimacy": round(self.legitimacy, 3),
                "execution": round(self.execution, 3),
                "social_response": round(self.social_response, 3),
            })

        result = {
            "steps": steps,
            "agency": ag,
            "instrument": inst,
            "compliance": round(self.compliance, 3),
            "legitimacy": round(self.legitimacy, 3),
            "execution": round(self.execution, 3),
            "social_response": round(self.social_response, 3),
            "events": battle_events[-12:],
            "recommendations": _recommendations(ag, inst, self.compliance, self.legitimacy, self.execution),
        }
        self.last_result = result
        return result

    def snapshot(self) -> dict[str, Any]:
        ag = self._agency()
        inst = self._instrument()
        return {
            "seed": self.seed,
            "civilization_key": self.civilization_key,
            "civilization_name": self.civilization_name,
            "agency_key": self.agency_key,
            "instrument_key": self.instrument_key,
            "agency_name": ag["name"],
            "instrument_name": inst["name"],
            "agencies": self.agencies,
            "compliance": self.compliance,
            "legitimacy": self.legitimacy,
            "execution": self.execution,
            "history": self.history[-48:],
            "last_result": self.last_result,
        }


def _recommendations(ag: dict, inst: dict, comp: float, legit: float, exe: float) -> list[str]:
    recs = [f"{ag['name']}关注：{ag['focus']}"]
    recs.append(f"主政令「{inst['name']}」预计滞后 {inst['lag']} 个执行周期生效。")
    if comp < 0.45:
        recs.append("基层执行率偏低：建议简化政令口径或增加督查频次。")
    if legit < 0.45:
        recs.append("合法性不足：需配套说明或有限豁免以缓和反弹。")
    if exe > 0.75:
        recs.append("执行力度较强：注意溢出成本与相邻部门协调。")
    return recs
