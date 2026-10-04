"""Military simulation lab — red vs blue, civilization-scoped scenarios."""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

from .military_scenarios import get_military_scenarios, scenario_by_key

BATTLEFIELDS = [
    {"key": "rainforest", "name": "雨林", "red_mod": -0.06, "blue_mod": 0.04, "supply_mod": -0.12},
    {"key": "mountain", "name": "山区", "red_mod": -0.04, "blue_mod": -0.04, "supply_mod": -0.15},
    {"key": "rural", "name": "农村", "red_mod": 0.02, "blue_mod": 0.0, "supply_mod": 0.05},
    {"key": "urban", "name": "城市", "red_mod": 0.0, "blue_mod": 0.03, "supply_mod": -0.05},
]

_WARLIKE_KINDS = {"war", "military", "battle", "conflict", "attack", "siege"}


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:16], 16)


def _events_by_step(events: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for ev in events:
        step = max(0, int(ev.get("at_step") or 0))
        grouped.setdefault(step, []).append(ev)
    return grouped


@dataclass
class MilitaryLab:
    seed: str
    civilization_key: str = ""
    civilization_name: str = ""
    scenario_key: str = ""
    battlefield_key: str = "rural"
    red_name: str = "红方"
    blue_name: str = "蓝方"
    tick: int = 0
    red_strength: float = 100.0
    blue_strength: float = 100.0
    red_morale: float = 0.7
    blue_morale: float = 0.7
    red_supply: float = 0.8
    blue_supply: float = 0.8
    history: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    last_result: dict[str, Any] | None = None
    scenario_catalog: list[dict[str, Any]] = field(default_factory=list)
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    user_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        seed: str,
        civ_ctx: dict[str, Any] | None = None,
        scenario_key: str = "",
        battlefield_key: str = "rural",
        user_id: str | None = None,
    ) -> "MilitaryLab":
        civ = civ_ctx or {}
        civ_key = civ.get("key", "")
        catalog = get_military_scenarios(civ_key, user_id=user_id)
        if not scenario_key or scenario_key not in {s["key"] for s in catalog}:
            scenario_key = catalog[0]["key"]
        scenario = scenario_by_key(catalog, scenario_key)
        red, blue = scenario["red"], scenario["blue"]
        red_base, blue_base = scenario["red_base"], scenario["blue_base"]
        return cls(
            seed=seed,
            civilization_key=civ_key,
            civilization_name=civ.get("name", ""),
            scenario_key=scenario_key,
            battlefield_key=battlefield_key,
            red_name=red,
            blue_name=blue,
            red_strength=100 * red_base,
            blue_strength=100 * blue_base,
            scenario_catalog=catalog,
            user_id=user_id,
        )

    def _scenario(self) -> dict[str, Any]:
        return scenario_by_key(self.scenario_catalog, self.scenario_key)

    def _battlefield(self) -> dict[str, Any]:
        return next((b for b in BATTLEFIELDS if b["key"] == self.battlefield_key), BATTLEFIELDS[2])

    def _rng(self) -> random.Random:
        return random.Random(_seed_int(self.seed, str(self.tick)))

    def prepare_simulation(
        self,
        *,
        scenario_key: str | None = None,
        battlefield_key: str | None = None,
        timeline_events: list[dict[str, Any]] | None = None,
    ) -> None:
        """Reset state for a fresh run with optional scenario / event overlay."""
        if scenario_key and scenario_key != self.scenario_key:
            if scenario_key in {s["key"] for s in self.scenario_catalog}:
                self.scenario_key = scenario_key
        if battlefield_key:
            self.battlefield_key = battlefield_key
        scen = self._scenario()
        self.red_name = scen["red"]
        self.blue_name = scen["blue"]
        self.red_strength = 100 * float(scen.get("red_base", 0.5))
        self.blue_strength = 100 * float(scen.get("blue_base", 0.5))
        self.red_morale = 0.7
        self.blue_morale = 0.7
        self.red_supply = 0.8
        self.blue_supply = 0.8
        self.tick = 0
        self.history = []
        self.events = []
        self.last_result = None
        self.timeline_events = list(timeline_events or [])

    def _apply_timeline_event(self, ev: dict[str, Any]) -> None:
        mag = float(ev.get("magnitude") or 0.15)
        kind = str(ev.get("kind") or "custom").lower()
        title = str(ev.get("title") or "战场事件")
        if kind in _WARLIKE_KINDS or mag < 0:
            self.red_morale = max(0.05, min(1.0, self.red_morale + mag * 0.35))
            self.blue_morale = max(0.05, min(1.0, self.blue_morale - mag * 0.25))
            self.red_strength = max(0.0, self.red_strength + mag * 8)
            self.blue_strength = max(0.0, self.blue_strength - abs(mag) * 6)
        else:
            self.red_supply = max(0.1, min(1.0, self.red_supply + mag * 0.2))
            self.blue_supply = max(0.1, min(1.0, self.blue_supply + mag * 0.15))
        rec = {
            "tick": self.tick,
            "kind": "timeline",
            "summary": f"事件「{title}」介入战场（{kind}，强度 {mag:+.2f}）",
        }
        self.events.append(rec)

    def simulate(self, steps: int = 12) -> dict[str, Any]:
        steps = max(1, min(60, int(steps)))
        bf = self._battlefield()
        scen = self._scenario()
        battle_events: list[dict[str, Any]] = []
        scheduled = _events_by_step(self.timeline_events)
        for _ in range(steps):
            self.tick += 1
            for ev in scheduled.get(self.tick, []):
                self._apply_timeline_event(ev)
                battle_events.append(self.events[-1])
            r = self._rng()
            red_attack = (0.08 + self.red_morale * 0.06 + bf["red_mod"]) * (0.85 + r.random() * 0.3)
            blue_attack = (0.08 + self.blue_morale * 0.06 + bf["blue_mod"]) * (0.85 + r.random() * 0.3)
            supply_penalty = abs(bf["supply_mod"])
            self.red_supply = max(0.1, self.red_supply - supply_penalty * 0.02 + 0.01)
            self.blue_supply = max(0.1, self.blue_supply - supply_penalty * 0.02 + 0.01)
            red_dmg = blue_attack * self.blue_strength * 0.04 * (2.0 - self.red_supply)
            blue_dmg = red_attack * self.red_strength * 0.04 * (2.0 - self.blue_supply)
            self.red_strength = max(0.0, self.red_strength - red_dmg)
            self.blue_strength = max(0.0, self.blue_strength - blue_dmg)
            self.red_morale = max(0.05, min(1.0, self.red_morale - red_dmg * 0.002 + 0.01))
            self.blue_morale = max(0.05, min(1.0, self.blue_morale - blue_dmg * 0.002 + 0.01))
            if r.random() < 0.15:
                ev = {
                    "tick": self.tick,
                    "kind": "tactical",
                    "summary": f"第{self.tick}回合：{bf['name']}战场发生遭遇战",
                }
                battle_events.append(ev)
                self.events.append(ev)
            self.history.append({
                "tick": self.tick,
                "red_strength": round(self.red_strength, 2),
                "blue_strength": round(self.blue_strength, 2),
                "red_morale": round(self.red_morale, 3),
                "blue_morale": round(self.blue_morale, 3),
            })
            if self.red_strength <= 0 or self.blue_strength <= 0:
                break
        winner = "red" if self.red_strength > self.blue_strength else "blue"
        if abs(self.red_strength - self.blue_strength) < 1:
            winner = "stalemate"
        result = {
            "steps": steps,
            "scenario": scen,
            "battlefield": bf,
            "red": {
                "name": self.red_name,
                "strength": round(self.red_strength, 2),
                "morale": round(self.red_morale, 3),
            },
            "blue": {
                "name": self.blue_name,
                "strength": round(self.blue_strength, 2),
                "morale": round(self.blue_morale, 3),
            },
            "winner": winner,
            "events": battle_events[-12:],
            "timeline_applied": len(self.timeline_events),
            "recommendations": _recommendations(winner, bf, self.red_supply, self.blue_supply, scen),
        }
        self.last_result = result
        return result

    def snapshot(self) -> dict[str, Any]:
        scen = self._scenario()
        return {
            "seed": self.seed,
            "civilization_key": self.civilization_key,
            "civilization_name": self.civilization_name,
            "scenario_key": self.scenario_key,
            "scenario_name": scen.get("name", ""),
            "scenario_type": scen.get("type", ""),
            "scenario_type_label": scen.get("type_label", ""),
            "battlefield_key": self.battlefield_key,
            "red_name": self.red_name,
            "blue_name": self.blue_name,
            "tick": self.tick,
            "red_strength": self.red_strength,
            "blue_strength": self.blue_strength,
            "red_morale": self.red_morale,
            "blue_morale": self.blue_morale,
            "history": self.history[-48:],
            "events": self.events[-16:],
            "last_result": self.last_result,
            "scenario_catalog": self.scenario_catalog,
            "battlefield_catalog": BATTLEFIELDS,
        }


def _recommendations(
    winner: str,
    bf: dict[str, Any],
    red_sup: float,
    blue_sup: float,
    scen: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    stype = scen.get("type_label") or scen.get("type") or "战役"
    recs.append(f"战役类型：{stype} · {scen.get('name', '—')}（{scen.get('era', '—')}）。")
    if bf["supply_mod"] < -0.1:
        recs.append(f"{bf['name']}地形补给压力大，优先保障后勤线。")
    if red_sup < 0.4 or blue_sup < 0.4:
        recs.append("补给告急：考虑战役节奏放缓或开辟新补给通道。")
    if winner == "stalemate":
        recs.append("僵持局面：可尝试侧翼机动或舆论/外交干预打破平衡。")
    elif winner == "red":
        recs.append("红方优势：注意扩大战果时的补给与士气衰减。")
    else:
        recs.append("蓝方优势：警惕反扑窗口，控制战线长度。")
    return recs
