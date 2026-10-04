"""Population development lab — demographics, shocks, policy, scoped regions."""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

DISASTER_TYPES = [
    {"key": "war", "name": "战争", "mortality": 0.025, "migration": 0.08, "fertility": -0.15},
    {"key": "plague", "name": "瘟疫", "mortality": 0.035, "migration": 0.03, "fertility": -0.10},
    {"key": "earthquake", "name": "地震", "mortality": 0.012, "migration": 0.05, "fertility": -0.05},
    {"key": "flood", "name": "洪涝", "mortality": 0.008, "migration": 0.06, "fertility": -0.04},
    {"key": "pest", "name": "虫灾/饥荒", "mortality": 0.015, "migration": 0.04, "fertility": -0.08},
]

POLICY_TYPES = [
    {"key": "pro_natal", "name": "鼓励生育", "fertility": 0.12, "migration": 0.02},
    {"key": "education", "name": "教育扩张", "cognition": 0.15, "fertility": -0.04},
    {"key": "healthcare", "name": "公共卫生", "mortality": -0.20, "fertility": 0.03},
    {"key": "migration_open", "name": "开放移民", "migration": 0.15, "fertility": 0.0},
    {"key": "migration_close", "name": "限制迁移", "migration": -0.12, "fertility": 0.0},
]

COGNITION_TYPES = [
    {"key": "literacy", "name": "识字率提升", "cognition": 0.10, "fertility": -0.03},
    {"key": "industrial", "name": "工业化认知", "cognition": 0.12, "fertility": -0.06},
    {"key": "digital", "name": "信息时代", "cognition": 0.15, "fertility": -0.08},
]

_SHOCK_KEYS = {d["key"] for d in DISASTER_TYPES}
_POLICY_KEYS = {p["key"] for p in POLICY_TYPES}
_COGNITION_KEYS = {c["key"] for c in COGNITION_TYPES}


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:16], 16)


def _city_pop_share(city_key: str, index: int, total_cities: int) -> float:
    h = int(hashlib.sha256(city_key.encode()).hexdigest()[:8], 16)
    raw = 0.04 + (h % 1000) / 1000.0 * 0.22
    return round(raw / max(1, total_cities ** 0.5), 4)


def get_population_regions(civ_ctx: dict[str, Any], user_id: str | None = None) -> list[dict[str, Any]]:
    from ..layer2_civilization.finance_entities import get_finance_cities

    seed_key = civ_ctx.get("key", "modern")
    cities = get_finance_cities(seed_key, user_id=user_id)
    regions: list[dict[str, Any]] = [
        {
            "key": "global",
            "name": "全局",
            "scope": "global",
            "description": "文明总人口与整体结构",
            "pop_share": 1.0,
        },
    ]
    n = max(1, len(cities))
    for i, c in enumerate(cities):
        share = _city_pop_share(c["key"], i, n)
        regions.append({
            "key": c["key"],
            "name": c["name"],
            "scope": "city",
            "description": c.get("description", ""),
            "pop_share": share,
        })
    for loc in civ_ctx.get("locations") or []:
        raw_name = str(loc.get("name") or "").strip()
        if not raw_name:
            continue
        name = raw_name.split("·")[0].split("—")[0][:20]
        key = hashlib.sha256(f"region:{name}".encode()).hexdigest()[:10]
        if any(r["key"] == key or r["name"] == name for r in regions):
            continue
        regions.append({
            "key": key,
            "name": name,
            "scope": "region",
            "description": str(loc.get("description") or "")[:100],
            "pop_share": _city_pop_share(key, len(regions), n + 2),
        })
    return regions[:10]


@dataclass
class PopulationLab:
    seed: str
    civilization_key: str = "modern"
    civilization_name: str = "文明"
    scope: str = "global"
    region_key: str = "global"
    region_name: str = "全局"
    region_pop_share: float = 1.0
    base_total_pop: float = 1_000_000.0
    operating_logic: str = ""
    year: int = 0
    total_pop: float = 1_000_000.0
    class_structure: dict[str, float] = field(default_factory=dict)
    age_structure: dict[str, float] = field(default_factory=dict)
    fertility_rate: float = 1.8
    mortality_rate: float = 0.008
    migration_rate: float = 0.002
    cognition_index: float = 0.45
    history: list[dict[str, Any]] = field(default_factory=list)
    shocks: list[dict[str, Any]] = field(default_factory=list)
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    available_regions: list[dict[str, Any]] = field(default_factory=list)
    last_result: dict[str, Any] | None = None
    _base_fertility: float = 1.8
    _base_mortality: float = 0.008
    _base_migration: float = 0.002
    _base_cognition: float = 0.45

    @classmethod
    def create(cls, *, seed: str, civ_ctx: dict[str, Any], user_id: str | None = None) -> "PopulationLab":
        from ..layer2_civilization.civilization_demographics import get_demographics

        demo = get_demographics(civ_ctx)
        cls_struct = civ_ctx.get("class_structure") or demo.get("class_structure") or {
            "ruling": 0.05, "middle": 0.35, "labor": 0.50, "marginal": 0.10,
        }
        age_struct = civ_ctx.get("age_structure") or {
            "child": 0.18, "youth": 0.22, "adult": 0.40, "middle_aged": 0.12, "elder": 0.08,
        }
        base_pop = float(demo.get("total_pop") or 1_000_000)
        fert = float(demo.get("fertility_rate") or 1.8)
        cog_raw = float(demo.get("literacy_pct") or 0.45)
        cog = cog_raw if cog_raw <= 1 else cog_raw / 100
        regions = get_population_regions(civ_ctx, user_id=user_id)
        logic = str(civ_ctx.get("operating_logic") or civ_ctx.get("premise") or "")[:200]
        lab = cls(
            seed=seed,
            civilization_key=civ_ctx.get("key", "modern"),
            civilization_name=civ_ctx.get("name", "文明"),
            base_total_pop=base_pop,
            total_pop=base_pop,
            class_structure=dict(cls_struct) if isinstance(cls_struct, dict) else {},
            age_structure=dict(age_struct),
            fertility_rate=fert,
            cognition_index=min(1.0, cog),
            available_regions=regions,
            operating_logic=logic,
            _base_fertility=fert,
            _base_mortality=0.008,
            _base_migration=0.002,
            _base_cognition=min(1.0, cog),
        )
        return lab

    def _rng(self) -> random.Random:
        return random.Random(_seed_int(self.seed, str(self.year), self.region_key))

    def select_scope(self, scope: str, region_key: str | None = None) -> dict[str, Any] | None:
        key = region_key or ("global" if scope == "global" else self.region_key)
        if scope == "global" or key == "global":
            self.scope = "global"
            self.region_key = "global"
            self.region_name = "全局"
            self.region_pop_share = 1.0
            return self.available_regions[0] if self.available_regions else None
        match = next((r for r in self.available_regions if r["key"] == key), None)
        if not match:
            match = next((r for r in self.available_regions if r["scope"] == scope), None)
        if not match:
            return None
        self.scope = match.get("scope", scope)
        self.region_key = match["key"]
        self.region_name = match["name"]
        self.region_pop_share = float(match.get("pop_share") or 0.1)
        return match

    def prepare_simulation(
        self,
        *,
        scope: str = "global",
        region_key: str | None = None,
        timeline_events: list[dict[str, Any]] | None = None,
    ) -> None:
        self.select_scope(scope, region_key)
        self.year = 0
        self.total_pop = max(1000, self.base_total_pop * self.region_pop_share)
        self.fertility_rate = self._base_fertility
        self.mortality_rate = self._base_mortality
        self.migration_rate = self._base_migration
        self.cognition_index = self._base_cognition
        self.history = []
        self.shocks = []
        self.last_result = None
        self.timeline_events = list(timeline_events or [])

    def apply_shock(self, kind: str, magnitude: float = 1.0, note: str = "") -> dict[str, Any]:
        meta = next((d for d in DISASTER_TYPES if d["key"] == kind), None)
        if not meta:
            raise ValueError(f"unknown disaster: {kind}")
        rec = {"year": self.year, "kind": kind, "name": meta["name"], "magnitude": magnitude, "note": note[:200]}
        self.shocks.append(rec)
        m = magnitude
        self.mortality_rate += meta["mortality"] * m
        self.migration_rate += meta["migration"] * m
        self.fertility_rate = max(0.5, self.fertility_rate + meta["fertility"] * m)
        return rec

    def apply_policy(self, kind: str, magnitude: float = 1.0) -> dict[str, Any]:
        meta = next((p for p in POLICY_TYPES if p["key"] == kind), None)
        if not meta:
            raise ValueError(f"unknown policy: {kind}")
        m = magnitude
        self.fertility_rate = max(0.5, self.fertility_rate + meta.get("fertility", 0) * m)
        self.migration_rate = max(-0.05, self.migration_rate + meta.get("migration", 0) * m)
        self.mortality_rate = max(0.001, self.mortality_rate + meta.get("mortality", 0) * m)
        if "cognition" in meta:
            self.cognition_index = min(1.0, self.cognition_index + meta["cognition"] * m)
        return {"kind": kind, "name": meta["name"], "year": self.year}

    def apply_cognition(self, kind: str, magnitude: float = 1.0) -> dict[str, Any]:
        meta = next((c for c in COGNITION_TYPES if c["key"] == kind), None)
        if not meta:
            raise ValueError(f"unknown cognition: {kind}")
        m = magnitude
        self.cognition_index = min(1.0, self.cognition_index + meta["cognition"] * m)
        self.fertility_rate = max(0.5, self.fertility_rate + meta.get("fertility", 0) * m)
        return {"kind": kind, "name": meta["name"], "year": self.year}

    def _apply_timeline_event(self, ev: dict[str, Any]) -> None:
        kind = str(ev.get("kind") or "custom").lower()
        mag = float(ev.get("magnitude") or 0.15)
        title = str(ev.get("title") or "事件")
        m = max(0.1, min(3.0, abs(mag) * 2 if mag else 1.0))
        if kind in _SHOCK_KEYS:
            self.apply_shock(kind, magnitude=m, note=title)
        elif kind in _POLICY_KEYS:
            self.apply_policy(kind, magnitude=m)
        elif kind in _COGNITION_KEYS:
            self.apply_cognition(kind, magnitude=m)
        elif kind in ("policy", "political", "decree"):
            self.apply_policy("pro_natal" if mag >= 0 else "migration_close", magnitude=abs(mag))
        else:
            self.fertility_rate = max(0.5, self.fertility_rate + mag * 0.15)
            self.migration_rate += mag * 0.005

    def simulate(self, years: int = 10) -> dict[str, Any]:
        years = max(1, min(100, int(years)))
        events_by_year: dict[int, list[dict[str, Any]]] = {}
        for ev in self.timeline_events:
            y = max(1, int(ev.get("at_step") or ev.get("year") or 1))
            events_by_year.setdefault(y, []).append(ev)
        applied_events: list[dict[str, Any]] = []

        for _ in range(years):
            self.year += 1
            for ev in events_by_year.get(self.year, []):
                self._apply_timeline_event(ev)
                applied_events.append({"year": self.year, "title": ev.get("title", ""), "kind": ev.get("kind", "")})

            r = self._rng()
            birth = self.total_pop * (self.fertility_rate / 100.0) * (0.9 + r.random() * 0.2)
            deaths = self.total_pop * self.mortality_rate * (0.85 + r.random() * 0.3)
            net_mig = self.total_pop * self.migration_rate * (0.8 + r.random() * 0.4)
            self.total_pop = max(1000, self.total_pop + birth - deaths + net_mig)
            if self.cognition_index > 0.5:
                self.fertility_rate = max(0.8, self.fertility_rate - 0.01 * (self.cognition_index - 0.5))
            self.mortality_rate = max(0.003, self.mortality_rate * 0.95)
            self.migration_rate *= 0.92
            elder = self.age_structure.get("elder", 0.08)
            child = self.age_structure.get("child", 0.18)
            self.age_structure["elder"] = min(0.35, elder + 0.002)
            self.age_structure["child"] = max(0.08, child + (self.fertility_rate - 1.8) * 0.005)
            self.history.append({
                "year": self.year,
                "total_pop": round(self.total_pop),
                "fertility_rate": round(self.fertility_rate, 3),
                "mortality_rate": round(self.mortality_rate, 4),
                "migration_rate": round(self.migration_rate, 4),
                "cognition_index": round(self.cognition_index, 3),
            })

        scope_label = {"global": "全局", "city": "城市", "region": "地区"}.get(self.scope, self.scope)
        result = {
            "years": years,
            "scope": self.scope,
            "scope_label": scope_label,
            "region_key": self.region_key,
            "region_name": self.region_name,
            "civilization": self.civilization_name,
            "operating_logic": self.operating_logic,
            "total_pop": round(self.total_pop),
            "fertility_rate": round(self.fertility_rate, 3),
            "cognition_index": round(self.cognition_index, 3),
            "age_structure": {k: round(v, 4) for k, v in self.age_structure.items()},
            "class_structure": {k: round(v, 4) for k, v in self.class_structure.items()},
            "events": applied_events[-12:],
            "timeline_applied": len(self.timeline_events),
            "shocks_applied": self.shocks[-5:],
            "recommendations": _recommendations(self),
            "disaster_catalog": DISASTER_TYPES,
            "policy_catalog": POLICY_TYPES,
            "cognition_catalog": COGNITION_TYPES,
        }
        self.last_result = result
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "civilization_key": self.civilization_key,
            "civilization_name": self.civilization_name,
            "scope": self.scope,
            "region_key": self.region_key,
            "region_name": self.region_name,
            "region_pop_share": self.region_pop_share,
            "base_total_pop": self.base_total_pop,
            "operating_logic": self.operating_logic,
            "available_regions": self.available_regions,
            "year": self.year,
            "total_pop": self.total_pop,
            "class_structure": self.class_structure,
            "age_structure": self.age_structure,
            "fertility_rate": self.fertility_rate,
            "mortality_rate": self.mortality_rate,
            "migration_rate": self.migration_rate,
            "cognition_index": self.cognition_index,
            "history": self.history[-64:],
            "shocks": self.shocks[-20:],
            "last_result": self.last_result,
            "disaster_catalog": DISASTER_TYPES,
            "policy_catalog": POLICY_TYPES,
            "cognition_catalog": COGNITION_TYPES,
        }


def _recommendations(lab: PopulationLab) -> list[str]:
    recs = [
        f"推演范围：{lab.region_name}（{lab.scope}）· 占文明人口约 {lab.region_pop_share:.0%}。",
    ]
    if lab.operating_logic:
        recs.append(f"文明运行逻辑：{lab.operating_logic[:80]}…")
    if lab.fertility_rate < 1.2:
        recs.append("生育率偏低：长期将导致劳动力与抚养比恶化。")
    if lab.cognition_index > 0.7:
        recs.append("认知指数较高：生育率可能继续缓慢下行。")
    if lab.shocks:
        recs.append(f"已吸收 {len(lab.shocks)} 次冲击，需关注恢复周期。")
    return recs
