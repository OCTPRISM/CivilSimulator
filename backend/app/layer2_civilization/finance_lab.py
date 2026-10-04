"""Finance Lab — structured macro desks + agent-based market kernel.

1. global   : IS-Phillips-Taylor lite + Monte Carlo bands + audit trail
2. city     : macro-mapped local employment / property / liquidity
3. corporate: sector-beta equity path driven by macro factor + firm events
4. retail   : regime-aware GBM sleeves (vol from macro ensemble)
5. market   : agent-based clearing via MarketState (see finance.py)

Quantitative paths are seedable and deterministic. LLM only fills narrative;
numbers come from finance_sim_core / MarketState, never from unconstrained prose.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..layer1_foundation import LLM, Message
from .finance_longrun import _risk_score_to_premium
from .finance_sim_core import (
    METHODOLOGY,
    MacroState,
    bootstrap_macro_history,
    city_from_macro,
    corporate_step_from_macro,
    retail_regime_from_vol,
    simulate_macro_ensemble,
    simulate_macro_path,
    _path_vol,
)


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


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


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------- shared event ----------
@dataclass
class LabEvent:
    id: str
    at_step: int
    title: str
    kind: str          # political | war | rate | earnings | product | scandal | policy | custom
    magnitude: float   # signed impact on risk / growth / equity
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at_step": self.at_step,
            "title": self.title,
            "kind": self.kind,
            "magnitude": self.magnitude,
            "note": self.note,
        }


# ---------- Global desk ----------
_GLOBAL_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "wuxia": [
        {"step": 0, "title": "渡口商路重开", "kind": "policy", "magnitude": 0.15},
        {"step": 8, "title": "门派会盟议税", "kind": "political", "magnitude": -0.08},
        {"step": 16, "title": "边关摩擦升级", "kind": "war", "magnitude": -0.22},
        {"step": 28, "title": "镖局联合降息放贷", "kind": "rate", "magnitude": 0.18},
    ],
    "ancient": [
        {"step": 0, "title": "朝廷开仓平粜", "kind": "policy", "magnitude": 0.12},
        {"step": 10, "title": "藩镇截留税银", "kind": "political", "magnitude": -0.2},
        {"step": 20, "title": "海贸弛禁", "kind": "policy", "magnitude": 0.25},
        {"step": 32, "title": "边军募兵", "kind": "war", "magnitude": -0.15},
    ],
    "scifi": [
        {"step": 0, "title": "轨道港关税下调", "kind": "policy", "magnitude": 0.14},
        {"step": 12, "title": "能源危机警报", "kind": "political", "magnitude": -0.28},
        {"step": 24, "title": "联邦降息周期", "kind": "rate", "magnitude": 0.2},
        {"step": 36, "title": "边境冲突升温", "kind": "war", "magnitude": -0.18},
    ],
    "modern": [
        {"step": 0, "title": "央行维持中性利率", "kind": "rate", "magnitude": 0.08},
        {"step": 12, "title": "就业数据不及预期", "kind": "political", "magnitude": -0.14},
        {"step": 24, "title": "产业补贴加码", "kind": "policy", "magnitude": 0.2},
        {"step": 36, "title": "地缘摩擦升温", "kind": "war", "magnitude": -0.18},
    ],
    "enterprise": [
        {"step": 0, "title": "行业景气回升", "kind": "policy", "magnitude": 0.16},
        {"step": 10, "title": "融资成本上行", "kind": "rate", "magnitude": -0.12},
        {"step": 22, "title": "头部并购传闻", "kind": "custom", "magnitude": 0.1},
        {"step": 34, "title": "监管问询函", "kind": "political", "magnitude": -0.15},
    ],
    "securities": [
        {"step": 0, "title": "流动性宽松窗口", "kind": "rate", "magnitude": 0.18},
        {"step": 8, "title": "杠杆资金升温", "kind": "custom", "magnitude": 0.12},
        {"step": 20, "title": "风险偏好回落", "kind": "political", "magnitude": -0.2},
        {"step": 32, "title": "指数成分调整", "kind": "policy", "magnitude": 0.08},
    ],
    "military": [
        {"step": 0, "title": "边境对峙升级", "kind": "war", "magnitude": -0.22},
        {"step": 10, "title": "国防预算追加", "kind": "policy", "magnitude": 0.15},
        {"step": 22, "title": "补给线受扰", "kind": "custom", "magnitude": -0.18},
        {"step": 34, "title": "停火谈判窗口", "kind": "political", "magnitude": 0.12},
    ],
    "xuanhuan": [
        {"step": 0, "title": "灵脉税赋下调", "kind": "policy", "magnitude": 0.14},
        {"step": 10, "title": "宗门资源争夺", "kind": "political", "magnitude": -0.18},
        {"step": 22, "title": "秘境开启冲击供给", "kind": "custom", "magnitude": 0.12},
        {"step": 32, "title": "丹药价格异动", "kind": "price", "magnitude": 0.2},
    ],
    "mystery": [
        {"step": 0, "title": "雾港贸易萎缩", "kind": "political", "magnitude": -0.2},
        {"step": 8, "title": "码头信贷收紧", "kind": "rate", "magnitude": -0.15},
        {"step": 18, "title": "橡胶期货暴涨", "kind": "price", "magnitude": 0.22},
        {"step": 28, "title": "工会罢工平息", "kind": "policy", "magnitude": 0.1},
    ],
    "default": [
        {"step": 0, "title": "全球宽松预期升温", "kind": "rate", "magnitude": 0.16},
        {"step": 10, "title": "关键选举不确定性", "kind": "political", "magnitude": -0.12},
        {"step": 20, "title": "供应链扰动", "kind": "custom", "magnitude": -0.1},
        {"step": 30, "title": "财政刺激落地", "kind": "policy", "magnitude": 0.22},
    ],
}


@dataclass
class GlobalDesk:
    genre: str = "default"
    seed: str = "global"
    history: list[dict[str, Any]] = field(default_factory=list)
    events: list[LabEvent] = field(default_factory=list)
    last_forecast: dict[str, Any] | None = None
    _terminal_state: MacroState | None = field(default=None, repr=False)
    macro_params: Any = None
    _institutions: list[dict[str, Any]] | None = field(default=None, repr=False)
    _institution_context_kwargs: dict[str, Any] | None = field(default=None, repr=False)

    def bootstrap(self) -> None:
        if self.history:
            return
        tpl = _GLOBAL_TEMPLATES.get(self.genre) or _GLOBAL_TEMPLATES["default"]
        self.events = [
            LabEvent(
                id=f"g_{e['step']}",
                at_step=int(e["step"]),
                title=str(e["title"]),
                kind=str(e["kind"]),
                magnitude=float(e["magnitude"]),
            )
            for e in tpl
        ]
        hist, terminal = bootstrap_macro_history(
            seed=self.seed, events=self.events, n_steps=48,
            params=self.macro_params, genre=self.genre,
        )
        self.history = hist
        self._terminal_state = terminal

    def set_initial_from_market(self, snap: dict[str, Any]) -> None:
        """Micro → macro closure: seed terminal state from MarketState."""
        from .finance_calibration import macro_state_from_market
        m = macro_state_from_market(
            price_index=float(snap.get("price_index") or 100),
            inflation=float(snap.get("inflation") or 0),
            gini=float(snap.get("gini") or 0.35),
            velocity=float(snap.get("velocity") or 0.1),
            money_supply=float(snap.get("money_supply") or 1000),
        )
        self._terminal_state = MacroState(
            output_gap=m["output_gap"],
            inflation=m["inflation"],
            risk_premium=m["risk_premium"],
            liquidity=m["liquidity"],
            index=m["index"],
            policy_rate=self._terminal_state.policy_rate if self._terminal_state else 2.5,
        )
        if self.history:
            self.history[-1] = {
                **self.history[-1],
                "index": round(m["index"], 3),
                "growth": round(m["output_gap"] * 100, 3),
                "risk": round(m["risk_premium"], 3),
                "liquidity": round(m["liquidity"], 3),
                "inflation": round(m["inflation"], 3),
                "output_gap": round(m["output_gap"], 4),
            }

    def insert_event(self, *, at_step: int, title: str, kind: str, magnitude: float, note: str = "") -> LabEvent:
        ev = LabEvent(
            id=f"g_{uuid4().hex[:8]}",
            at_step=max(0, int(at_step)),
            title=title.strip()[:80] or "自定义事件",
            kind=kind or "custom",
            magnitude=_clamp(float(magnitude), -1.0, 1.0),
            note=note[:200],
        )
        self.events.append(ev)
        self.events.sort(key=lambda e: e.at_step)
        return ev

    def simulate_forward(self, horizon: int = 24) -> dict[str, Any]:
        """Structured macro ensemble — returns forecast path + audit + bands."""
        self.bootstrap()
        horizon = max(4, min(90, int(horizon)))
        last = self.history[-1] if self.history else {"step": 47, "index": 100.0}
        start_step = int(last.get("step", 47)) + 1
        start_state = self._terminal_state or MacroState(
            index=float(last.get("index", 100.0)),
            inflation=float(last.get("inflation", 2.0)),
            policy_rate=float(last.get("policy_rate", 2.5)),
            risk_premium=_risk_score_to_premium(float(last.get("risk", 0.46))),
            liquidity=float(last.get("liquidity", 0.55)),
            output_gap=float(last.get("output_gap", 0.0)),
        )
        return simulate_macro_ensemble(
            seed=self.seed,
            events=self.events,
            horizon=horizon,
            start_state=start_state,
            start_step=start_step,
            params=self.macro_params,
            genre=self.genre,
            institutions=self._institutions,
            institution_context_kwargs=self._institution_context_kwargs,
            history_rows=self.history,
            fusion_mode="global",
        )

    def policy_calendar(self, forecast: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Heuristic policy timing from risk/growth regime shifts."""
        tips: list[dict[str, Any]] = []
        if not forecast:
            return tips
        for i, row in enumerate(forecast):
            if row["risk"] >= 0.65 and (i == 0 or forecast[i - 1]["risk"] < 0.65):
                tips.append({
                    "at_step": row["step"],
                    "when": row["label"],
                    "urgency": "high",
                    "action": "收紧流动性 / 提高风险准备金",
                    "reason": f"风险指标升至 {row['risk']:.2f}",
                })
            if row["growth"] <= -1.0 and (i == 0 or forecast[i - 1]["growth"] > -1.0):
                tips.append({
                    "at_step": row["step"],
                    "when": row["label"],
                    "urgency": "high",
                    "action": "财政或定向宽松对冲衰退",
                    "reason": f"增长跌至 {row['growth']:.2f}%",
                })
            if row["growth"] >= 3.0 and row["risk"] <= 0.35:
                tips.append({
                    "at_step": row["step"],
                    "when": row["label"],
                    "urgency": "medium",
                    "action": "渐进退出刺激，防止过热",
                    "reason": f"高增长低风险（g={row['growth']:.2f}%）",
                })
        # de-dupe by action window
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for t in tips:
            key = f"{t['when']}:{t['action']}"
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out[:8]

    async def forecast(self, llm: LLM | None, *, horizon: int = 24) -> dict[str, Any]:
        self.bootstrap()
        sim = self.simulate_forward(horizon)
        path = sim["forecast"]
        calendar = self.policy_calendar(path)
        narrative = {
            "outlook": "中性偏谨慎" if path[-1]["risk"] > 0.5 else "温和复苏",
            "summary": (
                f"结构化宏观推演 {horizon} 步：指数中位数 {path[-1]['index']:.1f}，"
                f"风险 {path[-1]['risk']:.2f}，通胀 {path[-1].get('inflation', 0):.1f}%。"
            ),
            "policy_notes": [c["action"] for c in calendar[:3]],
        }
        if llm is not None:
            try:
                sys = (
                    "你是宏观政策顾问。根据给定的历史与推演数值，给出中文政策建议。"
                    "只输出 JSON："
                    '{"outlook": str, "summary": str, "policy_notes": [str, ...]}'
                )
                usr = json.dumps({
                    "history_tail": self.history[-8:],
                    "events": [e.as_dict() for e in self.events],
                    "forecast_tail": path[-8:],
                    "confidence_bands": sim.get("confidence_bands", [])[-4:],
                    "calendar": calendar,
                    "methodology": sim.get("methodology", {}),
                }, ensure_ascii=False)
                resp = await llm.chat(
                    [Message("system", sys), Message("user", usr)],
                    temperature=0.4, max_tokens=500, json_mode=True,
                )
                data = _safe_json(resp.content)
                if data:
                    narrative = {
                        "outlook": str(data.get("outlook") or narrative["outlook"])[:40],
                        "summary": str(data.get("summary") or narrative["summary"])[:400],
                        "policy_notes": [
                            str(x)[:120] for x in (data.get("policy_notes") or narrative["policy_notes"])
                        ][:6],
                    }
            except Exception:
                pass
        result = {
            "mode": "global",
            "engine": "structured_macro_v2",
            "history": self.history,
            "events": [e.as_dict() for e in self.events],
            "forecast": path,
            "confidence_bands": sim.get("confidence_bands", []),
            "audit_trail": sim.get("audit_trail", []),
            "event_log": sim.get("event_log", []),
            "institutions": sim.get("institutions") or self._institutions,
            "methodology": sim.get("methodology", METHODOLOGY),
            "policy_calendar": calendar,
            "fusion_strategy": sim.get("fusion_strategy"),
            "fusion_log": sim.get("fusion_log"),
            "longrun_fusion": sim.get("longrun_fusion"),
            "narrative": narrative,
            "disclaimer": "沙盘推演，非实盘投资建议。",
        }
        self.last_forecast = result
        return result


# ---------- City finance desk ----------
_CITY_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "modern": [
        {"step": 0, "title": "地铁新线开通", "kind": "policy", "magnitude": 0.12},
        {"step": 10, "title": "核心区限购放松", "kind": "policy", "magnitude": 0.18},
        {"step": 22, "title": "本地银行收紧按揭", "kind": "rate", "magnitude": -0.14},
    ],
    "ancient": [
        {"step": 0, "title": "漕运旺季", "kind": "policy", "magnitude": 0.15},
        {"step": 12, "title": "西市税赋上调", "kind": "political", "magnitude": -0.1},
    ],
    "wuxia": [
        {"step": 0, "title": "镖局联盟降息", "kind": "rate", "magnitude": 0.1},
        {"step": 14, "title": "渡口商战升级", "kind": "war", "magnitude": -0.16},
    ],
    "xuanhuan": [
        {"step": 0, "title": "坊市灵石流通加速", "kind": "policy", "magnitude": 0.12},
        {"step": 12, "title": "宗门封关", "kind": "political", "magnitude": -0.14},
    ],
    "mystery": [
        {"step": 0, "title": "港口信贷扩张", "kind": "rate", "magnitude": 0.1},
        {"step": 10, "title": "雾港工会罢工", "kind": "political", "magnitude": -0.18},
    ],
    "scifi": [
        {"step": 0, "title": "轨道港基建投资", "kind": "policy", "magnitude": 0.13},
        {"step": 16, "title": "能源配额收紧", "kind": "rate", "magnitude": -0.12},
    ],
    "default": [
        {"step": 0, "title": "城市更新启动", "kind": "policy", "magnitude": 0.14},
        {"step": 8, "title": "就业数据走弱", "kind": "political", "magnitude": -0.1},
        {"step": 20, "title": "本地消费刺激", "kind": "policy", "magnitude": 0.12},
    ],
}


@dataclass
class CityDesk:
    genre: str = "default"
    seed: str = "city"
    city_key: str = "default"
    city_name: str = "本城"
    history: list[dict[str, Any]] = field(default_factory=list)
    events: list[LabEvent] = field(default_factory=list)
    last_forecast: dict[str, Any] | None = None
    _terminal_state: MacroState | None = field(default=None, repr=False)
    _macro_history: list[dict[str, Any]] = field(default_factory=list, repr=False)
    macro_params: Any = None
    _institutions: list[dict[str, Any]] | None = field(default=None, repr=False)
    _institution_context_kwargs: dict[str, Any] | None = field(default=None, repr=False)

    def select(self, *, city_key: str, city_name: str, genre: str, seed_prefix: str) -> None:
        city_key = city_key or "default"
        if self.city_key == city_key and self.history:
            self.city_name = city_name[:24]
            return
        self.city_key = city_key
        self.city_name = city_name[:24]
        self.genre = genre if genre in _CITY_TEMPLATES else "default"
        self.seed = f"{seed_prefix}:cy:{city_key}"
        self.history = []
        self.events = []
        self.last_forecast = None
        self._terminal_state = None
        self._macro_history = []
        self.bootstrap()

    def bootstrap(self) -> None:
        if self.history:
            return
        tpl = _CITY_TEMPLATES.get(self.genre) or _CITY_TEMPLATES["default"]
        self.events = [
            LabEvent(
                id=f"cy_{e['step']}",
                at_step=int(e["step"]),
                title=str(e["title"]),
                kind=str(e["kind"]),
                magnitude=float(e["magnitude"]),
            )
            for e in tpl
        ]
        macro_hist, terminal = bootstrap_macro_history(
            seed=self.seed, events=self.events, n_steps=48,
            params=self.macro_params, genre=self.genre,
        )
        self._macro_history = macro_hist
        self.history = [city_from_macro(row, scale=1.08) for row in macro_hist]
        self._terminal_state = terminal

    def insert_event(self, *, at_step: int, title: str, kind: str, magnitude: float, note: str = "") -> LabEvent:
        ev = LabEvent(
            id=f"cy_{uuid4().hex[:8]}",
            at_step=max(0, int(at_step)),
            title=title.strip()[:80] or "城市事件",
            kind=kind or "custom",
            magnitude=_clamp(float(magnitude), -1.0, 1.0),
            note=note[:200],
        )
        self.events.append(ev)
        self.events.sort(key=lambda e: e.at_step)
        return ev

    def simulate_forward(self, horizon: int = 24) -> dict[str, Any]:
        self.bootstrap()
        horizon = max(4, min(90, int(horizon)))
        last = self.history[-1] if self.history else {"step": 47}
        start_step = int(last.get("step", 47)) + 1
        start_state = self._terminal_state or MacroState()
        sim = simulate_macro_ensemble(
            seed=self.seed,
            events=self.events,
            horizon=horizon,
            start_state=start_state,
            start_step=start_step,
            params=self.macro_params,
            genre=self.genre,
            institutions=self._institutions,
            institution_context_kwargs=self._institution_context_kwargs,
            history_rows=self._macro_history,
            fusion_mode="city",
        )
        sim["forecast"] = [city_from_macro(row, scale=1.08) for row in sim["forecast"]]
        return sim

    async def forecast(self, llm: LLM | None, *, horizon: int = 24) -> dict[str, Any]:
        self.bootstrap()
        sim = self.simulate_forward(horizon)
        path = sim["forecast"]
        narrative = {
            "outlook": "城市景气回暖" if path[-1]["employment"] > 0.68 else "城市承压",
            "summary": (
                f"{self.city_name} 结构化推演：城市指数 {path[-1]['city_index']:.1f}，"
                f"地产 {path[-1]['property_index']:.1f}，就业 {path[-1]['employment']*100:.0f}%。"
            ),
            "policy_notes": [
                "关注本地信贷与按揭政策" if path[-1]["liquidity"] < 0.45 else "流动性充裕，警惕资产过热",
                "就业走弱时优先基建与消费券" if path[-1]["employment"] < 0.65 else "维持中性财政",
            ],
        }
        if llm is not None:
            try:
                sys = (
                    "你是城市金融顾问。根据城市指数、地产、就业与流动性推演，给出中文建议。"
                    '只输出 JSON：{"outlook": str, "summary": str, "policy_notes": [str,...]}'
                )
                usr = json.dumps({
                    "city": self.city_name,
                    "history_tail": self.history[-6:],
                    "forecast_tail": path[-6:],
                    "events": [e.as_dict() for e in self.events],
                    "methodology": sim.get("methodology", {}),
                }, ensure_ascii=False)
                resp = await llm.chat(
                    [Message("system", sys), Message("user", usr)],
                    temperature=0.4, max_tokens=450, json_mode=True,
                )
                data = _safe_json(resp.content)
                if data:
                    narrative = {
                        "outlook": str(data.get("outlook") or narrative["outlook"])[:40],
                        "summary": str(data.get("summary") or narrative["summary"])[:400],
                        "policy_notes": [str(x)[:120] for x in (data.get("policy_notes") or [])][:5],
                    }
            except Exception:
                pass
        result = {
            "mode": "city",
            "engine": "structured_macro_v2_city",
            "city_key": self.city_key,
            "city_name": self.city_name,
            "history": self.history,
            "events": [e.as_dict() for e in self.events],
            "forecast": path,
            "confidence_bands": sim.get("confidence_bands", []),
            "audit_trail": sim.get("audit_trail", []),
            "methodology": sim.get("methodology", METHODOLOGY),
            "fusion_strategy": sim.get("fusion_strategy"),
            "fusion_log": sim.get("fusion_log"),
            "longrun_fusion": sim.get("longrun_fusion"),
            "narrative": narrative,
            "disclaimer": "城市金融沙盘推演，非实盘建议。",
        }
        self.last_forecast = result
        return result


# ---------- Corporate desk ----------
@dataclass
class CorporateDesk:
    seed: str = "corp"
    company_key: str = "default"
    company_name: str = "风波渡航运"
    sector: str = "贸易"
    base_price: float = 100.0
    history: list[dict[str, Any]] = field(default_factory=list)
    events: list[LabEvent] = field(default_factory=list)
    last_forecast: dict[str, Any] | None = None
    genre: str = "default"
    macro_params: Any = None
    _macro_history: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _institutions: list[dict[str, Any]] | None = field(default=None, repr=False)
    _institution_context_kwargs: dict[str, Any] | None = field(default=None, repr=False)

    def select(
        self, *, company_key: str, company_name: str, sector: str,
        base_price: float, seed_prefix: str, genre: str = "default",
        macro_params: Any = None,
    ) -> None:
        company_key = company_key or "default"
        if self.company_key == company_key and self.history:
            self.company_name = company_name[:40]
            self.sector = sector[:24]
            return
        self.company_key = company_key
        self.company_name = company_name[:40]
        self.sector = sector[:24]
        self.base_price = max(1.0, float(base_price))
        self.genre = genre
        self.macro_params = macro_params
        self.seed = f"{seed_prefix}:c:{company_key}"
        self.history = []
        self.events = []
        self.last_forecast = None
        self._macro_history = []
        self.bootstrap()

    def bootstrap(self) -> None:
        if self.history:
            return
        macro_hist, _ = bootstrap_macro_history(
            seed=self.seed, events=[], n_steps=36,
            params=self.macro_params, genre=self.genre,
        )
        self._macro_history = macro_hist
        px = self.base_price
        r = random.Random(_seed_int(self.seed, "equity"))
        self.history = []
        prev = None
        for row in macro_hist:
            px = corporate_step_from_macro(
                price=px, macro_row=row, prev_macro_row=prev,
                sector=self.sector, idio_shock=0.0, rng=r,
            )
            self.history.append({"step": row["step"], "price": round(px, 3), "label": f"T+{row['step']}"})
            prev = row
        self.events = [
            LabEvent("c0", 6, "签订长约订单", "earnings", 0.18),
            LabEvent("c1", 18, "融资传闻", "policy", 0.1),
        ]

    def insert_event(self, *, at_step: int, title: str, kind: str, magnitude: float, note: str = "") -> LabEvent:
        ev = LabEvent(
            id=f"c_{uuid4().hex[:8]}",
            at_step=max(0, int(at_step)),
            title=title.strip()[:80] or "关键事件",
            kind=kind or "custom",
            magnitude=_clamp(float(magnitude), -1.0, 1.0),
            note=note[:200],
        )
        self.events.append(ev)
        self.events.sort(key=lambda e: e.at_step)
        return ev

    def simulate_forward(self, horizon: int = 24) -> dict[str, Any]:
        self.bootstrap()
        horizon = max(4, min(90, int(horizon)))
        start_step = int(self.history[-1]["step"]) + 1
        terminal = self._macro_history[-1] if self._macro_history else {}
        start_state = MacroState(
            index=float(terminal.get("index", 100.0)),
            inflation=float(terminal.get("inflation", 2.0)),
            policy_rate=float(terminal.get("policy_rate", 2.5)),
            risk_premium=_risk_score_to_premium(float(terminal.get("risk", 0.46))),
            liquidity=float(terminal.get("liquidity", 0.55)),
            output_gap=float(terminal.get("output_gap", 0.0)),
        )
        macro_sim = simulate_macro_ensemble(
            seed=f"{self.seed}:macro",
            events=self.events,
            horizon=horizon,
            start_state=start_state,
            start_step=start_step,
            params=self.macro_params,
            genre=self.genre,
            institutions=self._institutions,
            institution_context_kwargs=self._institution_context_kwargs,
            history_rows=self._macro_history,
            fusion_mode="corporate",
        )
        r = random.Random(_seed_int(self.seed, "cfwd", str(len(self.events)), str(horizon)))
        px = float(self.history[-1]["price"])
        prev_macro = {"index": self.history[-1]["price"] / self.base_price * 100.0, "step": self.history[-1]["step"]}
        path: list[dict[str, Any]] = []
        audit: list[dict[str, Any]] = []
        for i, macro_row in enumerate(macro_sim["forecast"]):
            step = macro_row["step"]
            idio = sum(e.magnitude for e in self.events if e.at_step == step) * 0.025
            px = corporate_step_from_macro(
                price=px, macro_row=macro_row, prev_macro_row=prev_macro,
                sector=self.sector, idio_shock=idio, rng=r,
            )
            path.append({
                "step": step,
                "price": round(px, 3),
                "label": f"F+{i + 1}",
                "forecast": True,
                "event": next((e.title for e in self.events if e.at_step == step), None),
                "macro_index": macro_row.get("index"),
            })
            audit.append({
                "step": step,
                "equations": ["r_stock = β_sector·r_market + idio_shock + ε"],
                "inputs": {"idio_shock": round(idio, 4), "sector": self.sector, "macro_index": macro_row.get("index")},
                "outputs": {"price": round(px, 3)},
            })
            prev_macro = macro_row
        return {
            "forecast": path,
            "audit_trail": audit,
            "confidence_bands": macro_sim.get("confidence_bands", []),
            "methodology": {**METHODOLOGY, "corporate": "sector_beta_factor_model"},
            "implied_vol_pct": macro_sim.get("implied_vol_pct", 0),
            "fusion_strategy": macro_sim.get("fusion_strategy"),
            "fusion_log": macro_sim.get("fusion_log"),
            "longrun_fusion": macro_sim.get("longrun_fusion"),
            "macro_forecast": macro_sim.get("forecast"),
        }

    def financing_advice(self, path: list[dict[str, Any]]) -> list[str]:
        if not path or not self.history:
            return ["数据不足，暂缓决策。"]
        start = self.history[-1]["price"]
        end = path[-1]["price"]
        ret = (end / start - 1.0) * 100.0
        tips: list[str] = []
        if ret >= 12:
            tips.append("股价推演偏强，可优先考虑可转债或延后股权稀释。")
            tips.append("若需扩张，短债滚动 + 经营现金流覆盖更优。")
        elif ret <= -8:
            tips.append("股价承压，避免高估值增发；优先银行授信与供应链融资。")
            tips.append("可谈判政府/联盟专项纾困或资产出售回笼现金。")
        else:
            tips.append("震荡市：保持现金缓冲，小额定增优于一次性大额稀释。")
            tips.append("用远期合同锁定收入，降低再融资频率。")
        vol = 0.0
        if len(path) > 2:
            rets = [
                path[i]["price"] / path[i - 1]["price"] - 1.0
                for i in range(1, len(path))
            ]
            mean = sum(rets) / len(rets)
            vol = math.sqrt(sum((x - mean) ** 2 for x in rets) / len(rets))
        if vol > 0.03:
            tips.append("波动偏高，建议对冲关键敞口或缩短融资窗口。")
        return tips

    async def forecast(self, llm: LLM | None, *, horizon: int = 24) -> dict[str, Any]:
        self.bootstrap()
        sim = self.simulate_forward(horizon)
        path = sim["forecast"]
        start = self.history[-1]["price"]
        end = path[-1]["price"]
        expected_return = round((end / start - 1.0) * 100.0, 2)
        advice = self.financing_advice(path)
        narrative = {
            "summary": (
                f"{self.company_name} 因子模型推演期末价约 {end:.2f}（区间收益 {expected_return:+.1f}%）。"
            ),
            "financing": advice,
        }
        if llm is not None:
            try:
                sys = (
                    "你是企业融资顾问。根据股价推演与事件，给出中文建议。"
                    "只输出 JSON："
                    '{"summary": str, "financing": [str, ...]}'
                )
                usr = json.dumps({
                    "company": self.company_name,
                    "sector": self.sector,
                    "events": [e.as_dict() for e in self.events],
                    "expected_return_pct": expected_return,
                    "path_tail": path[-6:],
                    "baseline_advice": advice,
                    "methodology": sim.get("methodology", {}),
                }, ensure_ascii=False)
                resp = await llm.chat(
                    [Message("system", sys), Message("user", usr)],
                    temperature=0.45, max_tokens=450, json_mode=True,
                )
                data = _safe_json(resp.content)
                if data:
                    narrative = {
                        "summary": str(data.get("summary") or narrative["summary"])[:400],
                        "financing": [
                            str(x)[:160] for x in (data.get("financing") or advice)
                        ][:6],
                    }
            except Exception:
                pass
        result = {
            "mode": "corporate",
            "engine": "sector_beta_factor_v2",
            "company": {
                "key": self.company_key,
                "name": self.company_name,
                "sector": self.sector,
                "base_price": self.base_price,
            },
            "history": self.history,
            "events": [e.as_dict() for e in self.events],
            "forecast": path,
            "expected_return_pct": expected_return,
            "audit_trail": sim.get("audit_trail", []),
            "methodology": sim.get("methodology", METHODOLOGY),
            "fusion_strategy": sim.get("fusion_strategy"),
            "fusion_log": sim.get("fusion_log"),
            "longrun_fusion": sim.get("longrun_fusion"),
            "narrative": narrative,
            "disclaimer": "沙盘推演，非实盘投资建议。",
        }
        self.last_forecast = result
        return result


# ---------- Retail / SME quant desk ----------
@dataclass
class RetailDesk:
    seed: str = "retail"
    capital: float = 100_000.0
    genre: str = "modern"
    last_result: dict[str, Any] | None = None
    macro_vol_pct: float = 1.0

    def calibrate_vol(self, events: list[Any] | None = None, *, genre: str | None = None) -> float:
        """Derive sleeve volatility from macro ensemble (regime-aware)."""
        g = genre or self.genre
        sim = simulate_macro_path(
            seed=f"{self.seed}:vol",
            events=events or [],
            horizon=24,
            path_tag="retail_cal",
            collect_audit=False,
            genre=g,
            fusion_mode="retail",
            use_longrun_fusion=True,
        )
        vol = _path_vol(sim.get("forecast") or []) * 100.0
        self.macro_vol_pct = max(0.5, vol)
        return self.macro_vol_pct

    def _synthetic_path(self, *, n: int, mu: float, sigma: float, tag: str) -> list[float]:
        r = random.Random(_seed_int(self.seed, tag, str(mu), str(sigma), str(n)))
        px = 100.0
        out = [px]
        for _ in range(n - 1):
            px *= math.exp((mu - 0.5 * sigma * sigma) + sigma * r.gauss(0, 1))
            out.append(max(1.0, px))
        return out

    @staticmethod
    def _stats(path: list[float], capital: float) -> dict[str, float]:
        if len(path) < 2:
            return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "vol_pct": 0.0, "end_value": capital}
        rets = [path[i] / path[i - 1] - 1.0 for i in range(1, len(path))]
        total = path[-1] / path[0] - 1.0
        peak = path[0]
        mdd = 0.0
        for p in path:
            peak = max(peak, p)
            mdd = min(mdd, p / peak - 1.0)
        mean = sum(rets) / len(rets)
        vol = math.sqrt(sum((x - mean) ** 2 for x in rets) / len(rets))
        return {
            "return_pct": round(total * 100, 2),
            "max_drawdown_pct": round(mdd * 100, 2),
            "vol_pct": round(vol * 100 * math.sqrt(252 if len(path) > 60 else 52), 2),
            "end_value": round(capital * (1.0 + total), 2),
        }

    def run(
        self,
        *,
        risk: str = "balanced",
        horizon: str = "auto",
        capital: float | None = None,
        events: list[Any] | None = None,
    ) -> dict[str, Any]:
        if capital is not None:
            self.capital = max(1000.0, float(capital))
        risk = risk if risk in ("conservative", "balanced", "aggressive") else "balanced"
        vol_pct = self.calibrate_vol(events, genre=self.genre)
        sleeves = retail_regime_from_vol(vol_pct)
        for name, cfg in sleeves.items():
            cfg["label"] = {
                "conservative": "稳健票息+防御",
                "balanced": "股债均衡",
                "aggressive": "成长动量",
            }[name]
        short_n, long_n = 21, 126
        results = {}
        for name, cfg in sleeves.items():
            short_path = self._synthetic_path(n=short_n, mu=cfg["mu"], sigma=cfg["sigma"], tag=f"{name}-s")
            long_path = self._synthetic_path(n=long_n, mu=cfg["mu"] * 0.9, sigma=cfg["sigma"] * 0.85, tag=f"{name}-l")
            results[name] = {
                "label": cfg["label"],
                "short": self._stats(short_path, self.capital),
                "long": self._stats(long_path, self.capital),
                "short_path": [round(x, 2) for x in short_path],
                "long_path": [round(x, 2) for x in long_path[::3]],  # downsample for UI
            }

        chosen = sleeves[risk]
        short_s = results[risk]["short"]
        long_s = results[risk]["long"]
        # score: return / |drawdown|
        def score(s: dict[str, float]) -> float:
            dd = abs(s["max_drawdown_pct"]) + 1.0
            return s["return_pct"] / dd

        prefer = "long" if score(long_s) >= score(short_s) else "short"
        if horizon in ("short", "long"):
            prefer = horizon
        elif risk == "conservative":
            prefer = "long"
        elif risk == "aggressive" and short_s["return_pct"] > long_s["return_pct"] * 0.45:
            prefer = "short"

        pick = short_s if prefer == "short" else long_s
        result = {
            "mode": "retail",
            "engine": "regime_gbm_v2",
            "capital": self.capital,
            "risk": risk,
            "sleeve": chosen["label"],
            "macro_vol_pct": round(vol_pct, 3),
            "methodology": {
                **METHODOLOGY,
                "retail": "GBM sleeves with σ calibrated from macro ensemble",
            },
            "recommendation": {
                "horizon": prefer,
                "horizon_label": "短期持仓（约 1 个月）" if prefer == "short" else "长期持仓（约 6 个月）",
                "expected_return_pct": pick["return_pct"],
                "expected_end_value": pick["end_value"],
                "max_drawdown_pct": pick["max_drawdown_pct"],
                "vol_pct": pick["vol_pct"],
                "rationale": (
                    f"在「{chosen['label']}」风险偏好下，"
                    f"{'短期' if prefer == 'short' else '长期'}路径的收益/回撤比更优。"
                ),
            },
            "comparison": {
                name: {
                    "label": data["label"],
                    "short_return_pct": data["short"]["return_pct"],
                    "long_return_pct": data["long"]["return_pct"],
                    "short_mdd_pct": data["short"]["max_drawdown_pct"],
                    "long_mdd_pct": data["long"]["max_drawdown_pct"],
                }
                for name, data in results.items()
            },
            "paths": {
                "short": results[risk]["short_path"],
                "long": results[risk]["long_path"],
            },
            "disclaimer": "量化沙盘基于合成路径，非实盘回测，不构成投资建议。",
        }
        self.last_result = result
        return result


# ---------- Lab container ----------
@dataclass
class FinanceLab:
    seed: str
    genre: str
    civilization_key: str = ""
    cities: list[dict[str, Any]] = field(default_factory=list)
    companies: list[dict[str, Any]] = field(default_factory=list)
    institutions: list[dict[str, Any]] = field(default_factory=list)
    calibration: dict[str, Any] = field(default_factory=dict)
    institution_context_kwargs: dict[str, Any] = field(default_factory=dict)
    baseline_population: float = 0.0
    macro_params: Any = None
    global_desk: GlobalDesk = field(default_factory=GlobalDesk)
    city_desk: CityDesk = field(default_factory=CityDesk)
    corporate: CorporateDesk = field(default_factory=CorporateDesk)
    retail: RetailDesk = field(default_factory=RetailDesk)

    def reset_institutions(self, demographics: dict[str, Any] | None = None) -> None:
        from .finance_institution_dynamics import initialize_dynamic_institutions
        demo = demographics or self.institution_context_kwargs.get("demographics") or {}
        self.baseline_population = float(demo.get("total_pop") or 1_000_000)
        self.institutions = initialize_dynamic_institutions(
            self.genre, self.civilization_key, demo,
        )
        keep = {k: v for k, v in self.institution_context_kwargs.items()
                if k in ("market_snap", "population_snap", "corporate_history")}
        self.institution_context_kwargs = {
            "demographics": demo,
            "baseline_population": self.baseline_population,
            **keep,
        }
        self.bind_institutions_to_desks()

    def configure_institution_context(
        self,
        *,
        market_snap: dict[str, Any] | None = None,
        population_snap: dict[str, Any] | None = None,
        corporate_history: list[dict[str, Any]] | None = None,
    ) -> None:
        if market_snap is not None:
            self.institution_context_kwargs["market_snap"] = market_snap
        if population_snap is not None:
            self.institution_context_kwargs["population_snap"] = population_snap
        if corporate_history is not None:
            self.institution_context_kwargs["corporate_history"] = corporate_history
        self.bind_institutions_to_desks()

    def bind_institutions_to_desks(self) -> None:
        ctx = self.institution_context_kwargs
        for desk in (self.global_desk, self.city_desk, self.corporate):
            desk._institutions = self.institutions
            desk._institution_context_kwargs = ctx

    def select_city(self, city_key: str) -> dict[str, Any] | None:
        match = next((c for c in self.cities if c["key"] == city_key), None)
        if not match:
            return None
        self.city_desk.select(
            city_key=match["key"],
            city_name=match["name"],
            genre=self.genre,
            seed_prefix=self.seed,
        )
        self.city_desk.macro_params = self.macro_params
        return match

    def select_company(self, company_key: str) -> dict[str, Any] | None:
        match = next((c for c in self.companies if c["key"] == company_key), None)
        if not match:
            return None
        self.corporate.select(
            company_key=match["key"],
            company_name=match["name"],
            sector=str(match.get("sector") or "工商"),
            base_price=float(match.get("base_price") or 100.0),
            seed_prefix=self.seed,
            genre=self.genre,
            macro_params=self.macro_params,
        )
        return match

    @classmethod
    def create(
        cls,
        *,
        seed: str,
        genre: str,
        world_name: str = "",
        civilization_key: str = "",
        user_id: str | None = None,
    ) -> "FinanceLab":
        from .finance_entities import get_finance_entities
        from .finance_calibration import calibrate_macro_params
        from .finance_institution_dynamics import initialize_dynamic_institutions
        from .civilization_resolver import civilization_context
        from .civilization_demographics import get_demographics

        civ_key = civilization_key or seed.split(":")[0]
        civ_ctx = civilization_context(civ_key, user_id=user_id)
        entities = get_finance_entities(civ_key, user_id=user_id)
        cities = entities["cities"]
        companies = entities["companies"]
        demo = get_demographics(civ_ctx)
        institutions = initialize_dynamic_institutions(genre, civ_key, demo)
        cal = calibrate_macro_params(genre, gdp_index=float(demo.get("gdp_index") or 100))
        macro_params = cal.params

        lab = cls(
            seed=seed,
            genre=genre,
            civilization_key=civ_key,
            cities=cities,
            companies=companies,
            institutions=institutions,
            calibration=cal.as_dict(),
            macro_params=macro_params,
            institution_context_kwargs={"demographics": demo, "baseline_population": float(demo.get("total_pop") or 1_000_000)},
            baseline_population=float(demo.get("total_pop") or 1_000_000),
        )
        g_genre = genre if genre in _GLOBAL_TEMPLATES else "default"
        lab.global_desk = GlobalDesk(genre=g_genre, seed=f"{seed}:g", macro_params=macro_params)
        lab.retail = RetailDesk(seed=f"{seed}:r", genre=genre)

        first_city = cities[0]
        lab.city_desk = CityDesk()
        lab.city_desk.macro_params = macro_params
        lab.city_desk.select(
            city_key=first_city["key"],
            city_name=first_city["name"],
            genre=genre if genre in _CITY_TEMPLATES else "default",
            seed_prefix=seed,
        )

        first_co = companies[0]
        lab.corporate = CorporateDesk()
        lab.corporate.select(
            company_key=first_co["key"],
            company_name=first_co["name"],
            sector=str(first_co.get("sector") or "工商"),
            base_price=float(first_co.get("base_price") or 100.0),
            seed_prefix=seed,
        )

        lab.global_desk.bootstrap()
        lab.bind_institutions_to_desks()
        return lab

    def prepare_simulation(self, *, city_key: str | None = None, company_key: str | None = None) -> None:
        """Reset desks to baseline, then caller applies timeline events."""
        demo = self.institution_context_kwargs.get("demographics") or {}
        self.reset_institutions(demo)
        g_genre = self.genre if self.genre in _GLOBAL_TEMPLATES else "default"
        self.global_desk = GlobalDesk(
            genre=g_genre, seed=f"{self.seed}:g", macro_params=self.macro_params,
        )
        self.global_desk.bootstrap()
        ck = city_key or (self.cities[0]["key"] if self.cities else "default")
        self.select_city(ck)
        co = company_key or (self.companies[0]["key"] if self.companies else "default")
        self.select_company(co)
        self.bind_institutions_to_desks()

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "genre": self.genre,
            "civilization_key": self.civilization_key,
            "available_cities": self.cities,
            "available_companies": self.companies,
            "institutions": self.institutions,
            "calibration": self.calibration,
            "global": {
                "history": self.global_desk.history,
                "events": [e.as_dict() for e in self.global_desk.events],
                "last_forecast": self.global_desk.last_forecast,
            },
            "city": {
                "city_key": self.city_desk.city_key,
                "city_name": self.city_desk.city_name,
                "history": self.city_desk.history,
                "events": [e.as_dict() for e in self.city_desk.events],
                "last_forecast": self.city_desk.last_forecast,
            },
            "corporate": {
                "company": {
                    "key": self.corporate.company_key,
                    "name": self.corporate.company_name,
                    "sector": self.corporate.sector,
                    "base_price": self.corporate.base_price,
                },
                "history": self.corporate.history,
                "events": [e.as_dict() for e in self.corporate.events],
                "last_forecast": self.corporate.last_forecast,
            },
            "retail": {
                "capital": self.retail.capital,
                "last_result": self.retail.last_result,
            },
        }
