"""Deterministic finance kernel for validation experiments.

Prices, money aggregates and shocks are rule-driven and seedable. LLM may
narrate outcomes but must not invent market numbers for this subsystem.
"""
from __future__ import annotations

import hashlib
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..layer3_agents import Society
    from .world import World


# genre -> goods with base price and which professions supply them
_CATALOGS: dict[str, list[dict[str, Any]]] = {
    "wuxia": [
        {"id": "grain", "name": "粮米", "base": 8.0, "suppliers": ["农", "管事", "厨", "庄"]},
        {"id": "wine", "name": "酒水", "base": 6.0, "suppliers": ["丐", "客栈", "说书", "酒"]},
        {"id": "arms", "name": "兵刃", "base": 40.0, "suppliers": ["剑", "杀手", "铁"]},
        {"id": "ferry", "name": "船资", "base": 3.0, "suppliers": ["渡", "船", "艄"]},
        {"id": "lodging", "name": "客栈", "base": 12.0, "suppliers": ["客栈", "说书", "店"]},
    ],
    "ancient": [
        {"id": "grain", "name": "粮米", "base": 7.0, "suppliers": ["农", "仓", "吏"]},
        {"id": "salt", "name": "盐铁", "base": 15.0, "suppliers": ["商", "铁", "盐"]},
        {"id": "labor", "name": "徭役", "base": 5.0, "suppliers": ["役", "兵", "卫"]},
        {"id": "silk", "name": "绢帛", "base": 20.0, "suppliers": ["商", "织", "贾"]},
        {"id": "tax", "name": "税银", "base": 10.0, "suppliers": ["吏", "税", "衙"]},
    ],
    "scifi": [
        {"id": "energy", "name": "能源", "base": 12.0, "suppliers": ["工", "能", "站"]},
        {"id": "data", "name": "算力", "base": 18.0, "suppliers": ["研", "AI", "码", "数据"]},
        {"id": "hull", "name": "船体件", "base": 55.0, "suppliers": ["工", "造", "航"]},
        {"id": "rations", "name": "合成粮", "base": 9.0, "suppliers": ["生", "农", "厨"]},
        {"id": "credit", "name": "信用点", "base": 1.0, "suppliers": ["银", "贸", "商"]},
    ],
    "xuanhuan": [
        {"id": "spirit", "name": "灵石", "base": 25.0, "suppliers": ["修", "宗", "丹"]},
        {"id": "herb", "name": "灵药", "base": 30.0, "suppliers": ["药", "丹", "医"]},
        {"id": "grain", "name": "凡粮", "base": 6.0, "suppliers": ["农", "凡", "厨"]},
        {"id": "artifact", "name": "法器坯", "base": 80.0, "suppliers": ["器", "炼", "铁"]},
        {"id": "lodging", "name": "客栈", "base": 10.0, "suppliers": ["客", "店"]},
    ],
    "mystery": [
        {"id": "grain", "name": "口粮", "base": 8.0, "suppliers": ["厨", "店", "农"]},
        {"id": "info", "name": "情报", "base": 35.0, "suppliers": ["探", "记", "说"]},
        {"id": "bribe", "name": "贿金", "base": 50.0, "suppliers": ["官", "警", "商"]},
        {"id": "lodging", "name": "旅馆", "base": 14.0, "suppliers": ["店", "馆"]},
        {"id": "fuel", "name": "灯油", "base": 5.0, "suppliers": ["工", "商"]},
    ],
    "modern": [
        {"id": "housing", "name": "住房", "base": 50.0, "suppliers": ["房", "建", "工"]},
        {"id": "energy", "name": "能源", "base": 18.0, "suppliers": ["能", "电", "工"]},
        {"id": "food", "name": "食品", "base": 12.0, "suppliers": ["农", "食", "商"]},
        {"id": "service", "name": "服务", "base": 15.0, "suppliers": ["服", "商"]},
        {"id": "credit", "name": "信贷", "base": 10.0, "suppliers": ["银", "融", "商"]},
    ],
    "enterprise": [
        {"id": "talent", "name": "人才", "base": 40.0, "suppliers": ["管", "研", "销"]},
        {"id": "supply", "name": "供应链", "base": 22.0, "suppliers": ["工", "运", "商"]},
        {"id": "rd", "name": "研发", "base": 55.0, "suppliers": ["研", "工"]},
        {"id": "marketing", "name": "营销", "base": 28.0, "suppliers": ["销", "商"]},
        {"id": "cash", "name": "营运资金", "base": 20.0, "suppliers": ["银", "管", "商"]},
    ],
    "securities": [
        {"id": "equity", "name": "股票", "base": 100.0, "suppliers": ["投", "经", "银"]},
        {"id": "bond", "name": "债券", "base": 80.0, "suppliers": ["银", "融"]},
        {"id": "derivative", "name": "衍生品", "base": 45.0, "suppliers": ["经", "投"]},
        {"id": "liquidity", "name": "流动性", "base": 25.0, "suppliers": ["银", "融", "商"]},
        {"id": "info", "name": "研报", "base": 30.0, "suppliers": ["研", "经"]},
    ],
    "custom": [
        {"id": "grain", "name": "粮米", "base": 8.0, "suppliers": ["农", "商", "工"]},
        {"id": "craft", "name": "手工品", "base": 15.0, "suppliers": ["工", "商"]},
        {"id": "service", "name": "服务", "base": 12.0, "suppliers": ["商", "官"]},
        {"id": "credit", "name": "信用", "base": 10.0, "suppliers": ["银", "商"]},
        {"id": "info", "name": "情报", "base": 25.0, "suppliers": ["官", "商", "学"]},
    ],
    "military": [
        {"id": "ammo", "name": "弹药", "base": 35.0, "suppliers": ["工", "兵"]},
        {"id": "fuel", "name": "油料", "base": 28.0, "suppliers": ["运", "工", "能"]},
        {"id": "ration", "name": "军粮", "base": 14.0, "suppliers": ["粮", "农", "厨"]},
        {"id": "med", "name": "卫勤", "base": 40.0, "suppliers": ["医", "卫"]},
        {"id": "intel", "name": "情报", "base": 60.0, "suppliers": ["情", "侦", "兵"]},
    ],
}


def _catalog(genre: str) -> list[dict[str, Any]]:
    return list(_CATALOGS.get(genre) or _CATALOGS["ancient"])


def _seed_int(seed: str) -> int:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


@dataclass
class GoodState:
    id: str
    name: str
    base: float
    price: float
    inventory: float = 100.0
    supply_tick: float = 0.0
    demand_tick: float = 0.0
    suppliers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "base": round(self.base, 3),
            "price": round(self.price, 3),
            "inventory": round(self.inventory, 2),
            "supply_tick": round(self.supply_tick, 3),
            "demand_tick": round(self.demand_tick, 3),
            "change_pct": round((self.price / self.base - 1.0) * 100.0, 2),
        }


@dataclass
class FinanceShock:
    id: str
    kind: str          # supply | demand | price
    good_id: str       # specific good or "*" for all
    magnitude: float   # e.g. 0.3 = +30% demand / -30% supply / +30% price jump
    remaining: int
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "good_id": self.good_id,
            "magnitude": self.magnitude,
            "remaining": self.remaining,
            "note": self.note,
        }


@dataclass
class MarketState:
    """Session-scoped market for validation experiments."""
    seed: str = "default"
    tick: int = 0
    goods: dict[str, GoodState] = field(default_factory=dict)
    shocks: list[FinanceShock] = field(default_factory=list)
    history: deque = field(default_factory=lambda: deque(maxlen=256))
    last_events: list[dict[str, Any]] = field(default_factory=list)
    money_supply: float = 0.0
    price_index: float = 100.0
    inflation: float = 0.0
    velocity: float = 0.0
    gini: float = 0.0
    volume: float = 0.0
    _rng_state: Any = None

    @classmethod
    def create(cls, *, genre: str, seed: str, society: "Society | None" = None) -> "MarketState":
        m = cls(seed=seed)
        for g in _catalog(genre):
            m.goods[g["id"]] = GoodState(
                id=g["id"],
                name=g["name"],
                base=float(g["base"]),
                price=float(g["base"]),
                inventory=80.0,
                suppliers=list(g.get("suppliers") or []),
            )
        m._rng_state = random.Random(_seed_int(seed)).getstate()
        if society is not None:
            m.money_supply = sum(float(a.savings or 0) for a in society.all())
        m.price_index = m._compute_index()
        m._push_history()
        return m

    def rng(self) -> random.Random:
        r = random.Random()
        if self._rng_state is not None:
            r.setstate(self._rng_state)
        else:
            r.seed(_seed_int(self.seed))
        return r

    def _save_rng(self, r: random.Random) -> None:
        self._rng_state = r.getstate()

    def _compute_index(self) -> float:
        if not self.goods:
            return 100.0
        ratios = [g.price / g.base for g in self.goods.values() if g.base > 0]
        if not ratios:
            return 100.0
        return 100.0 * (sum(ratios) / len(ratios))

    @staticmethod
    def _gini(values: list[float]) -> float:
        xs = sorted(max(0.0, v) for v in values)
        n = len(xs)
        if n == 0:
            return 0.0
        total = sum(xs)
        if total <= 1e-9:
            return 0.0
        acc = 0.0
        for i, v in enumerate(xs, start=1):
            acc += i * v
        return max(0.0, min(1.0, (2 * acc) / (n * total) - (n + 1) / n))

    def _profession_matches(self, profession: str, keywords: list[str]) -> bool:
        p = profession or ""
        return any(k in p for k in keywords)

    def schedule_shock(
        self,
        *,
        kind: str,
        good_id: str,
        magnitude: float,
        duration: int,
        note: str = "",
    ) -> FinanceShock:
        kind = kind if kind in ("supply", "demand", "price") else "demand"
        magnitude = max(-0.9, min(3.0, float(magnitude)))
        duration = max(1, min(120, int(duration)))
        if good_id != "*" and good_id not in self.goods:
            raise ValueError(f"unknown good: {good_id}")
        shock = FinanceShock(
            id=f"shock_{self.tick}_{len(self.shocks)}_{kind}",
            kind=kind,
            good_id=good_id,
            magnitude=magnitude,
            remaining=duration,
            note=note[:200],
        )
        if kind == "price":
            targets = self.goods.values() if good_id == "*" else [self.goods[good_id]]
            for g in targets:
                g.price = max(0.1, g.price * (1.0 + magnitude))
        self.shocks.append(shock)
        return shock

    def advance(self, world: "World", society: "Society") -> list[dict[str, Any]]:
        """One finance hour. Deterministic given seed + agent state."""
        r = self.rng()
        events: list[dict[str, Any]] = []
        agents = [a for a in society.all() if not a.is_dormant()]

        # Reset flow meters
        for g in self.goods.values():
            g.supply_tick = 0.0
            g.demand_tick = 0.0

        # Active shock multipliers
        supply_mul: dict[str, float] = {gid: 1.0 for gid in self.goods}
        demand_mul: dict[str, float] = {gid: 1.0 for gid in self.goods}
        still: list[FinanceShock] = []
        for s in self.shocks:
            if s.remaining <= 0:
                continue
            keys = list(self.goods) if s.good_id == "*" else [s.good_id]
            for gid in keys:
                if gid not in self.goods:
                    continue
                if s.kind == "supply":
                    supply_mul[gid] *= max(0.05, 1.0 + s.magnitude)
                elif s.kind == "demand":
                    demand_mul[gid] *= max(0.05, 1.0 + s.magnitude)
                    # Scarcity pressure: demand shocks also drain buffer stock.
                    self.goods[gid].inventory = max(
                        5.0, self.goods[gid].inventory * (1.0 - 0.04 * abs(s.magnitude))
                    )
            s.remaining -= 1
            if s.remaining > 0:
                still.append(s)
            else:
                events.append({
                    "kind": "shock_expired",
                    "summary": f"冲击结束：{s.kind}/{s.good_id}",
                    "importance": 0.35,
                })
        self.shocks = still

        # Production from working agents
        hour = world.clock.hour_of_day
        for a in agents:
            prof = a.profession or ""
            econ = a.economy or {}
            capacity = float(econ.get("daily_capacity") or 1)
            act = a.current_activity or ""
            working = bool(act) and not act.startswith("沉睡")
            if not working and 8 <= hour < 18:
                working = True
            if not working:
                continue
            produced = False
            for g in self.goods.values():
                if self._profession_matches(prof, g.suppliers):
                    # Keep hourly output modest so prices stay near base without shocks.
                    qty = max(0.05, min(1.2, capacity / 18.0) * (0.75 + 0.25 * r.random()))
                    qty *= supply_mul[g.id]
                    g.supply_tick += qty
                    g.inventory += qty
                    pay = qty * g.price * 0.55
                    a.savings += pay
                    a.today_income += pay
                    produced = True
                    break  # one primary good per profession per hour
            if not produced:
                g = next(iter(self.goods.values()))
                qty = 0.15 * supply_mul[g.id]
                g.supply_tick += qty
                g.inventory += qty
                pay = qty * g.price * 0.4
                a.savings += pay
                a.today_income += pay

        # Consumption / demand from expenses & wealth
        traded = 0.0
        for a in agents:
            econ = a.economy or {}
            daily_exp = float(econ.get("daily_expenses") or 8)
            budget = (daily_exp / 18.0)  # concentrate spending in active hours
            if not (6 <= hour < 22):
                budget *= 0.35
            wealth_factor = 1.0 + min(1.5, max(0.0, a.savings) / 800.0)
            for g in self.goods.values():
                share = 1.0 / max(1, len(self.goods))
                want = (budget * share * wealth_factor / max(0.5, g.price)) * demand_mul[g.id]
                want *= 0.9 + 0.2 * r.random()
                got = min(want, max(0.0, g.inventory))
                g.demand_tick += want
                g.inventory -= got
                cost = got * g.price
                a.savings -= cost
                traded += cost
            if a.savings < -50:
                a.savings = -50.0

        # Price discovery: inventory pressure + flow imbalance
        for g in self.goods.values():
            inv_target = 80.0
            inv_pressure = (inv_target - g.inventory) / inv_target
            flow = g.demand_tick - g.supply_tick
            flow_pressure = flow / max(1.0, (g.supply_tick + g.demand_tick) / 2.0 + 1.0)
            # Stronger reaction under active shocks
            boost = 1.0
            if demand_mul[g.id] != 1.0 or supply_mul[g.id] != 1.0:
                boost = 1.8
            delta = (0.06 * inv_pressure + 0.16 * flow_pressure) * boost
            delta = max(-0.1, min(0.15, delta))
            g.price = max(0.25 * g.base, g.price * (1.0 + delta))
            g.price += (g.base - g.price) * 0.008
            g.inventory = max(5.0, min(250.0, g.inventory))

        prev_index = self.price_index
        self.tick += 1
        self.money_supply = sum(float(a.savings or 0) for a in society.all())
        self.price_index = self._compute_index()
        if prev_index > 1e-6:
            # per-tick inflation annualized lightly for UI (not literal YoY)
            self.inflation = (self.price_index / prev_index - 1.0) * 100.0
        else:
            self.inflation = 0.0
        self.volume = traded
        self.velocity = traded / max(1.0, abs(self.money_supply))
        self.gini = self._gini([float(a.savings or 0) for a in society.all()])

        # Notable events for validation log
        if abs(self.inflation) >= 1.5:
            events.append({
                "kind": "inflation",
                "summary": f"价格指数至 {self.price_index:.1f}（时序通胀 {self.inflation:+.2f}%）",
                "importance": 0.55,
            })
        hottest = max(self.goods.values(), key=lambda g: abs(g.price / g.base - 1.0))
        if abs(hottest.price / hottest.base - 1.0) >= 0.25:
            events.append({
                "kind": "price_move",
                "summary": f"{hottest.name}现价 {hottest.price:.2f}（相对基价 {((hottest.price/hottest.base)-1)*100:+.1f}%）",
                "importance": 0.45,
            })

        self._push_history()
        self.last_events = events
        self._save_rng(r)
        return events

    def _push_history(self) -> None:
        self.history.append({
            "tick": self.tick,
            "price_index": round(self.price_index, 3),
            "inflation": round(self.inflation, 4),
            "money_supply": round(self.money_supply, 2),
            "velocity": round(self.velocity, 4),
            "gini": round(self.gini, 4),
            "volume": round(self.volume, 2),
            "prices": {gid: round(g.price, 3) for gid, g in self.goods.items()},
        })

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "tick": self.tick,
            "price_index": round(self.price_index, 3),
            "inflation": round(self.inflation, 4),
            "money_supply": round(self.money_supply, 2),
            "velocity": round(self.velocity, 4),
            "gini": round(self.gini, 4),
            "volume": round(self.volume, 2),
            "goods": [g.as_dict() for g in self.goods.values()],
            "shocks": [s.as_dict() for s in self.shocks],
            "history": list(self.history),
            "last_events": list(self.last_events),
            "reproducible": True,
            "engine": "deterministic_market_v1",
        }

    def export_csv(self) -> str:
        cols = ["tick", "price_index", "inflation", "money_supply", "velocity", "gini", "volume"]
        good_ids = list(self.goods.keys())
        header = cols + [f"price_{gid}" for gid in good_ids]
        lines = [",".join(header)]
        for row in self.history:
            vals = [str(row.get(c, "")) for c in cols]
            prices = row.get("prices") or {}
            vals.extend(str(prices.get(gid, "")) for gid in good_ids)
            lines.append(",".join(vals))
        return "\n".join(lines) + "\n"
