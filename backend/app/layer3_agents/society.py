from __future__ import annotations

import random
from .agent import Agent


def _slot_for_hour(schedule: list[dict], hour: int) -> dict | None:
    """Find the schedule slot covering `hour`. Slots may use to>24 to wrap past midnight."""
    if not schedule:
        return None
    for slot in schedule:
        f, t = int(slot.get("from", 0)), int(slot.get("to", 0))
        if t <= f:                        # malformed; skip
            continue
        # normal slot fully within day
        if t <= 24:
            if f <= hour < t:
                return slot
        else:
            # wraps past midnight: covers [f,24) ∪ [0, t-24)
            if hour >= f or hour < (t - 24):
                return slot
    return None


class Society:
    """Container for all agents in a world + simple social-graph utilities."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def add(self, agent: Agent) -> Agent:
        self._agents[agent.id] = agent
        return agent

    def get(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def all(self) -> list[Agent]:
        return list(self._agents.values())

    def npcs(self) -> list[Agent]:
        from .agent import AgentKind
        return [a for a in self._agents.values() if a.kind == AgentKind.NPC]

    def players(self) -> list[Agent]:
        from .agent import AgentKind
        return [a for a in self._agents.values() if a.kind == AgentKind.PLAYER]

    def at(self, location_id: str) -> list[Agent]:
        return [a for a in self._agents.values() if a.location_id == location_id]

    def adjust_relation(self, a: str, b: str, delta: float) -> None:
        ag = self._agents.get(a)
        if not ag:
            return
        ag.relations[b] = max(-1.0, min(1.0, ag.relations.get(b, 0.0) + delta))

    # ---- Phase 6b: drive NPC location & economy from schedule ----
    def advance_schedules(self, world) -> list[dict]:  # noqa: ANN001
        """For each NPC: place them per current hour's schedule slot, advance economy.
        Returns a list of {agent_id, location_id, activity, income_delta} for events.
        Player agents are not auto-moved.
        """
        from .agent import AgentKind
        events: list[dict] = []
        hour = world.clock.hour_of_day
        day  = world.clock.day
        loc_by_name = {l.name: l.id for l in world.locations.values()}

        for a in self._agents.values():
            # Proxy players act like NPCs while the user is offline.
            if a.kind == AgentKind.PLAYER:
                if not a.is_proxy():
                    if a.location_id:
                        slot = _slot_for_hour(a.schedule, hour) if a.schedule else None
                        self._update_agent_motion(a, world, slot, loc_by_name)
                    continue
                # ensure a wander schedule exists
                if not a.schedule:
                    from .offline_choice import default_wander_schedule
                    a.schedule = default_wander_schedule(world, a)

            elif a.kind != AgentKind.NPC:
                continue
            else:
                # NPCs continue as before
                pass

            # Daily settlement (NPCs + proxy players with economy)
            if a._last_day_settled != day and a.economy:
                if a._last_day_settled >= 0:    # not first activation
                    expenses = float(a.economy.get("daily_expenses", 0))
                    a.savings += a.today_income - expenses
                    base_tier = a.economy.get("meal_tier", "中")
                    # downgrade if savings can't cover one day of expenses
                    if a.savings < 0:
                        a.last_meal_tier = "无"
                    elif a.savings < expenses:
                        a.last_meal_tier = "差"
                    else:
                        a.last_meal_tier = base_tier
                a.today_income = 0.0
                a.today_customers = 0
                a._last_day_settled = day

            # Place by schedule
            slot = _slot_for_hour(a.schedule, hour)
            if slot:
                loc_name = slot.get("location") or ""
                lid = loc_by_name.get(loc_name)
                if lid and lid != a.location_id:
                    a.location_id = lid
                a.current_activity = slot.get("activity", "")

                # Income tick: if this slot is a working slot (has economy unit)
                # and the NPC is below daily capacity, accrue income probabilistically
                if a.economy and a.economy.get("daily_capacity"):
                    cap = int(a.economy["daily_capacity"])
                    work_hours = sum(
                        max(0, int(s.get("to", 0)) - int(s.get("from", 0)))
                        for s in a.schedule
                        if "income" in (s.get("activity") or "") or s.get("working")
                    )
                    # Heuristic: if this slot's activity hints at work (摆渡/接客/巡夜/etc.),
                    # treat as working hour.
                    is_work = any(
                        kw in (slot.get("activity") or "")
                        for kw in ("摆渡", "巡", "守", "看店", "卖", "炼", "采", "教书",
                                   "驯", "诊", "修", "唱", "斗", "试药", "缝补", "走货",
                                   "扫", "造册", "祈祷", "记账", "授课", "煮", "熬", "炒")
                    )
                    if is_work and a.today_customers < cap:
                        # spread cap over assumed ~6 working hours; per-tick prob
                        p = min(1.0, cap / 6.0 / max(1, len([s for s in a.schedule if s is slot])))
                        if random.random() < p:
                            unit_price = float(a.economy.get("income_per_unit", 0))
                            a.today_income += unit_price
                            a.today_customers += 1
                            events.append({
                                "agent_id": a.id,
                                "income_delta": unit_price,
                                "today_customers": a.today_customers,
                            })

            self._update_agent_motion(a, world, slot, loc_by_name)
        return events

    def _update_agent_motion(
        self, a: Agent, world, slot: dict | None, loc_by_name: dict,
    ) -> None:
        from .agent import AgentKind
        from ..layer2_civilization.map_meta import loc_id_coords, loc_coords, snap_norm_to_road

        genre = world.genre
        activity = (slot.get("activity") if slot else "") or a.current_activity or ""
        a.behavior = _behavior_from_activity(activity)

        # Target = current location centroid + activity offset
        tx, tz = loc_id_coords(genre, world, a.location_id)
        if slot and slot.get("location"):
            lc = loc_coords(genre, slot["location"])
            if lc:
                tx, tz = lc

        seed = sum(ord(c) for c in a.id) % 997
        ox = ((seed % 11) - 5) * 0.015
        oz = ((seed % 7) - 3) * 0.015
        tx += ox
        tz += oz

        if a.behavior == "walk":
            # Walk along nearest road centerline (lane ±2.5 map px)
            t = world.clock.tick * 0.08 + seed * 0.01
            along = 18.0 * (1 if int(t) % 2 else -1)
            side = 2.5 if (seed % 2 == 0) else -2.5
            tx, tz = snap_norm_to_road(genre, tx, tz, along=along, side=side)
        elif a.behavior == "drink":
            tz += 0.02
        elif a.behavior == "farm":
            tx += 0.04 * (seed % 3 - 1)
        else:
            # Idle near location still snaps onto curb so NPCs aren't in the void
            tx, tz = snap_norm_to_road(genre, tx, tz, along=(seed % 9) - 4, side=3.0)

        a.target_x, a.target_z = tx, tz
        # lerp toward target
        a.world_x += (tx - a.world_x) * 0.35
        a.world_z += (tz - a.world_z) * 0.35

        if a.kind == AgentKind.PLAYER and a.world_x == 0 and a.world_z == 0:
            a.world_x, a.world_z = tx, tz


def _behavior_from_activity(activity: str) -> str:
    if any(k in activity for k in ("酒", "喝", "灌", "饮")):
        return "drink"
    if any(k in activity for k in ("耕", "种", "田", "采", "锄")):
        return "farm"
    if any(k in activity for k in ("爬", "树", "枝")):
        return "climb"
    if any(k in activity for k in ("潜", "泳", "江心", "船在江")):
        return "swim"
    if any(k in activity for k in ("走", "行", "逛", "踱", "过", "摆渡", "巡")):
        return "walk"
    if any(k in activity for k in (
        "摆渡", "巡", "守", "看店", "卖", "炼", "教书", "诊", "修",
        "接客", "说书", "对账", "操练", "练",
    )):
        return "work"
    return "idle"
