"""In-memory lab workspaces (no civilization session required)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..layer1_foundation import get_llm
from ..layer2_civilization import MarketState, World, WorldClock
from ..layer2_civilization.civilization_resolver import civilization_context
from ..layer2_civilization.finance_lab import FinanceLab
from ..layer3_agents import Agent, AgentKind, Society
from .catalog import get_lab_meta
from .military_lab import MilitaryLab
from .opinion_lab import OpinionLab
from .policy_lab import PolicyLab
from .weather_lab import WeatherLab
from .environment_lab import EnvironmentLab
from .population_lab import PopulationLab
from .lab_store import load_lab_record, save_lab_snapshot
from .datasets import TimelineEvent, parse_manual_events, parse_upload, save_upload
from .report import analysis_from_simulation, build_report, enrich_finance_report

_WORKSPACES: dict[str, "LabWorkspace"] = {}
_BY_USER: dict[str, str] = {}

_SYNTH_PROFESSIONS: dict[str, list[str]] = {
    "modern": ["工", "商", "银", "农", "服", "研"],
    "enterprise": ["工", "商", "研", "销", "管"],
    "securities": ["银", "商", "研", "经", "投"],
    "military": ["工", "兵", "运", "医", "粮"],
    "custom": ["官", "商", "农", "工", "学"],
    "default": ["商", "工", "农", "银", "服"],
}


def _synthetic_society(genre: str) -> Society:
    society = Society()
    tags = _SYNTH_PROFESSIONS.get(genre) or _SYNTH_PROFESSIONS["default"]
    for i, tag in enumerate(tags * 2):
        society.add(Agent(
            id=f"lab_npc_{i}",
            name=f"沙盘商户{i + 1}",
            kind=AgentKind.NPC,
            persona="实验室合成主体",
            profession=tag,
            current_activity="营业",
            savings=80.0 + i * 15.0,
            economy={"daily_capacity": 1.2, "daily_expenses": 8.0},
        ))
    return society


def _stub_world(genre: str, name: str = "实验沙盘") -> World:
    return World(
        id=f"lab_world_{uuid4().hex[:8]}",
        name=name,
        genre=genre,
        premise="实验平台独立沙盘。",
        rules=["数值由确定性内核驱动"],
        clock=WorldClock(era="实验纪元", tick=0, start_hour=8),
    )


@dataclass
class LabWorkspace:
    id: str
    user_id: str
    lab_key: str
    civilization_key: str = "modern"
    genre: str = "modern"
    civilization_name: str = ""
    world: World | None = None
    society: Society | None = None
    finance: MarketState | None = None
    finance_lab: FinanceLab | None = None
    opinion_lab: OpinionLab | None = None
    military_lab: MilitaryLab | None = None
    policy_lab: PolicyLab | None = None
    weather_lab: WeatherLab | None = None
    environment_lab: EnvironmentLab | None = None
    population_lab: PopulationLab | None = None
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    last_report: dict[str, Any] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def llm(self):
        return get_llm()


def _cache_key(user_id: str, lab_key: str, civilization_key: str) -> str:
    return f"{user_id}:{lab_key}:{civilization_key}"


def _init_lab_state(ws: LabWorkspace, civ_ctx: dict[str, Any]) -> None:
    genre = civ_ctx.get("genre", "modern")
    ws.genre = genre
    ws.civilization_name = civ_ctx.get("name", "")
    name = civ_ctx.get("name", "实验沙盘")
    seed_base = f"lab:{ws.user_id}:{ws.lab_key}:{ws.civilization_key}"

    if ws.lab_key == "finance":
        ws.world = _stub_world(genre, name)
        ws.society = _synthetic_society(genre)
        ws.finance = MarketState.create(genre=genre, seed=seed_base, society=ws.society)
        ws.finance_lab = FinanceLab.create(
            seed=f"{seed_base}:desk",
            genre=genre,
            world_name=name,
            civilization_key=ws.civilization_key,
            user_id=ws.user_id,
        )
    elif ws.lab_key == "opinion":
        ws.opinion_lab = OpinionLab.create(seed=seed_base, civ_ctx=civ_ctx)
    elif ws.lab_key == "military":
        ws.military_lab = MilitaryLab.create(
            seed=seed_base, civ_ctx=civ_ctx, user_id=ws.user_id,
        )
    elif ws.lab_key == "policy":
        ws.policy_lab = PolicyLab.create(seed=seed_base, civ_ctx=civ_ctx)
    elif ws.lab_key == "weather":
        ws.weather_lab = WeatherLab.create(seed=seed_base, civ_ctx=civ_ctx)
    elif ws.lab_key == "environment":
        ws.environment_lab = EnvironmentLab.create(seed=seed_base, civ_ctx=civ_ctx)
    elif ws.lab_key == "population":
        ws.population_lab = PopulationLab.create(
            seed=seed_base, civ_ctx=civ_ctx, user_id=ws.user_id,
        )


def _persist(ws: LabWorkspace) -> None:
    try:
        meta = get_lab_meta(ws.lab_key) or {"key": ws.lab_key}
        snap = {
            "id": ws.id,
            "lab_key": ws.lab_key,
            "civilization_key": ws.civilization_key,
            "civilization_name": ws.civilization_name,
            "genre": ws.genre,
            "meta": meta,
            "finance": ws.finance.snapshot() if ws.finance else None,
            "finance_lab": ws.finance_lab.snapshot() if ws.finance_lab else None,
            "opinion": ws.opinion_lab.snapshot() if ws.opinion_lab else None,
            "military": ws.military_lab.snapshot() if ws.military_lab else None,
            "policy": ws.policy_lab.snapshot() if ws.policy_lab else None,
            "weather": ws.weather_lab.snapshot() if ws.weather_lab else None,
            "environment": ws.environment_lab.snapshot() if ws.environment_lab else None,
            "population": ws.population_lab.snapshot() if ws.population_lab else None,
            "timeline_events": ws.timeline_events[-50:],
            "last_report": ws.last_report,
            "status": meta.get("status", "ready"),
        }
        save_lab_snapshot(ws, snap)
    except OSError:
        pass


def create_or_get_lab(
    *,
    user_id: str,
    lab_key: str,
    civilization_key: str = "modern",
) -> LabWorkspace:
    meta = get_lab_meta(lab_key)
    if not meta:
        raise KeyError(f"unknown lab: {lab_key}")
    cache_key = _cache_key(user_id, lab_key, civilization_key)
    existing_id = _BY_USER.get(cache_key)
    if existing_id and existing_id in _WORKSPACES:
        return _WORKSPACES[existing_id]

    civ_ctx = civilization_context(civilization_key, user_id=user_id)
    wid = f"lab_{uuid4().hex[:12]}"
    persisted = load_lab_record(user_id, lab_key, civilization_key)
    if persisted and persisted.get("id"):
        wid = persisted["id"]
    ws = LabWorkspace(
        id=wid, user_id=user_id, lab_key=lab_key,
        civilization_key=civilization_key, genre=civ_ctx.get("genre", "modern"),
    )
    _init_lab_state(ws, civ_ctx)
    if persisted:
        ws.timeline_events = list(persisted.get("timeline_events") or [])
        ws.last_report = persisted.get("last_report")
    _WORKSPACES[wid] = ws
    _BY_USER[cache_key] = wid
    _persist(ws)
    return ws


def rebind_civilization(ws: LabWorkspace, civilization_key: str) -> LabWorkspace:
    """Reinitialize workspace for a civilization (switch civ or refresh in place)."""
    civ_ctx = civilization_context(civilization_key, user_id=ws.user_id)
    caller_cache = _cache_key(ws.user_id, ws.lab_key, ws.civilization_key)
    target_cache = _cache_key(ws.user_id, ws.lab_key, civilization_key)

    target_id = _BY_USER.get(target_cache)
    if target_id and target_id in _WORKSPACES:
        target_ws = _WORKSPACES[target_id]
    else:
        target_ws = ws
        if caller_cache != target_cache:
            _BY_USER.pop(caller_cache, None)

    target_ws.civilization_key = civilization_key
    target_ws.genre = civ_ctx.get("genre", "modern")
    target_ws.civilization_name = civ_ctx.get("name", "")
    target_ws.finance = target_ws.finance_lab = None
    target_ws.opinion_lab = target_ws.military_lab = target_ws.population_lab = None
    target_ws.policy_lab = target_ws.weather_lab = target_ws.environment_lab = None
    target_ws.world = target_ws.society = None
    target_ws.timeline_events = []
    target_ws.last_report = None
    _init_lab_state(target_ws, civ_ctx)
    _BY_USER[target_cache] = target_ws.id
    _persist(target_ws)
    return target_ws


def get_lab(lab_id: str) -> LabWorkspace | None:
    return _WORKSPACES.get(lab_id)


def lab_snapshot(ws: LabWorkspace) -> dict[str, Any]:
    meta = get_lab_meta(ws.lab_key) or {"key": ws.lab_key}
    snap = {
        "id": ws.id,
        "lab_key": ws.lab_key,
        "civilization_key": ws.civilization_key,
        "civilization_name": ws.civilization_name,
        "genre": ws.genre,
        "meta": meta,
        "finance": ws.finance.snapshot() if ws.finance else None,
        "finance_lab": ws.finance_lab.snapshot() if ws.finance_lab else None,
        "opinion": ws.opinion_lab.snapshot() if ws.opinion_lab else None,
        "military": ws.military_lab.snapshot() if ws.military_lab else None,
        "policy": ws.policy_lab.snapshot() if ws.policy_lab else None,
        "weather": ws.weather_lab.snapshot() if ws.weather_lab else None,
        "environment": ws.environment_lab.snapshot() if ws.environment_lab else None,
        "population": ws.population_lab.snapshot() if ws.population_lab else None,
        "timeline_events": ws.timeline_events[-50:],
        "last_report": ws.last_report,
        "status": meta.get("status", "ready"),
    }
    _persist(ws)
    return snap


# ---------- finance ops ----------
async def lab_advance_finance(ws: LabWorkspace, steps: int = 24) -> dict[str, Any]:
    steps = max(1, min(168, int(steps)))
    if not ws.finance or not ws.world or not ws.society:
        raise RuntimeError("finance desk not initialized")
    async with ws.lock:
        events: list[dict] = []
        for _ in range(steps):
            events.extend(ws.finance.advance(ws.world, ws.society))
            ws.world.clock.advance(1)
        return {"steps": steps, "events": events[-20:], "finance": ws.finance.snapshot(),
                "finance_lab": ws.finance_lab.snapshot() if ws.finance_lab else None, "lab": lab_snapshot(ws)}


async def lab_apply_shock(ws: LabWorkspace, *, kind: str, good_id: str = "*",
                          magnitude: float = 0.3, duration: int = 12, note: str = "") -> dict[str, Any]:
    if not ws.finance:
        raise RuntimeError("finance desk not initialized")
    async with ws.lock:
        shock = ws.finance.schedule_shock(kind=kind, good_id=good_id, magnitude=magnitude,
                                          duration=duration, note=note)
        return {"shock": shock.as_dict(), "finance": ws.finance.snapshot(), "lab": lab_snapshot(ws)}


async def lab_global_forecast(ws: LabWorkspace, *, horizon: int = 24) -> dict[str, Any]:
    if not ws.finance_lab:
        raise RuntimeError("finance lab not initialized")
    result = await ws.finance_lab.global_desk.forecast(ws.llm, horizon=horizon)
    return {"result": result, "finance_lab": ws.finance_lab.snapshot(),
            "finance": ws.finance.snapshot() if ws.finance else None, "lab": lab_snapshot(ws)}


async def lab_global_event(ws: LabWorkspace, *, at_step: int, title: str, kind: str = "political",
                           magnitude: float = 0.2, note: str = "") -> dict[str, Any]:
    if not ws.finance_lab:
        raise RuntimeError("finance lab not initialized")
    async with ws.lock:
        ev = ws.finance_lab.global_desk.insert_event(at_step=at_step, title=title,
                                                     kind=kind, magnitude=magnitude, note=note)
        return {"event": ev.as_dict(), "finance_lab": ws.finance_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_corporate_forecast(ws: LabWorkspace, *, horizon: int = 24,
                                 company_name: str | None = None, sector: str | None = None,
                                 company_key: str | None = None) -> dict[str, Any]:
    if not ws.finance_lab:
        raise RuntimeError("finance lab not initialized")
    if company_key:
        if not ws.finance_lab.select_company(company_key):
            raise ValueError(f"unknown company: {company_key}")
    if company_name:
        ws.finance_lab.corporate.company_name = company_name[:40]
    if sector:
        ws.finance_lab.corporate.sector = sector[:24]
    result = await ws.finance_lab.corporate.forecast(ws.llm, horizon=horizon)
    return {"result": result, "finance_lab": ws.finance_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_corporate_event(ws: LabWorkspace, *, at_step: int, title: str, kind: str = "earnings",
                              magnitude: float = 0.2, note: str = "") -> dict[str, Any]:
    if not ws.finance_lab:
        raise RuntimeError("finance lab not initialized")
    async with ws.lock:
        ev = ws.finance_lab.corporate.insert_event(at_step=at_step, title=title,
                                                   kind=kind, magnitude=magnitude, note=note)
        return {"event": ev.as_dict(), "finance_lab": ws.finance_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_retail_run(ws: LabWorkspace, *, risk: str = "balanced", horizon: str = "auto",
                         capital: float | None = None) -> dict[str, Any]:
    if not ws.finance_lab:
        raise RuntimeError("finance lab not initialized")
    async with ws.lock:
        result = ws.finance_lab.retail.run(risk=risk, horizon=horizon, capital=capital)
        return {"result": result, "finance_lab": ws.finance_lab.snapshot(), "lab": lab_snapshot(ws)}


# ---------- opinion ops ----------
async def lab_opinion_simulate(ws: LabWorkspace, steps: int = 24, topic: str = "") -> dict[str, Any]:
    if not ws.opinion_lab:
        raise RuntimeError("opinion lab not initialized")
    async with ws.lock:
        if topic:
            ws.opinion_lab.topic = topic[:200]
        result = ws.opinion_lab.simulate(steps=steps)
        return {"result": result, "opinion": ws.opinion_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_opinion_intervene(ws: LabWorkspace, key: str, note: str = "") -> dict[str, Any]:
    if not ws.opinion_lab:
        raise RuntimeError("opinion lab not initialized")
    async with ws.lock:
        rec = ws.opinion_lab.apply_intervention(key, note=note)
        return {"intervention": rec, "opinion": ws.opinion_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_opinion_node(ws: LabWorkspace, *, at_step: int, title: str,
                           kind: str = "custom", magnitude: float = 0.2) -> dict[str, Any]:
    if not ws.opinion_lab:
        raise RuntimeError("opinion lab not initialized")
    async with ws.lock:
        node = ws.opinion_lab.insert_node(at_step=at_step, title=title, kind=kind, magnitude=magnitude)
        return {"node": node, "opinion": ws.opinion_lab.snapshot(), "lab": lab_snapshot(ws)}


# ---------- military ops ----------
async def lab_military_configure(ws: LabWorkspace, *, scenario_key: str, battlefield_key: str) -> dict[str, Any]:
    if not ws.military_lab:
        raise RuntimeError("military lab not initialized")
    async with ws.lock:
        civ_ctx = civilization_context(ws.civilization_key, user_id=ws.user_id)
        ws.military_lab = MilitaryLab.create(
            seed=f"lab:{ws.user_id}:military:{ws.civilization_key}:{scenario_key}",
            civ_ctx=civ_ctx,
            scenario_key=scenario_key,
            battlefield_key=battlefield_key,
            user_id=ws.user_id,
        )
        return {"military": ws.military_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_military_simulate(
    ws: LabWorkspace,
    *,
    scenario_key: str | None = None,
    battlefield_key: str | None = None,
    steps: int = 12,
) -> dict[str, Any]:
    """Unified military simulation: background + terrain + events + selected 战役 → PDF report."""
    from ..layer2_civilization.civilization_dashboard import build_dashboard
    from .report_pdf import build_pdf_bytes
    import base64

    if not ws.military_lab:
        raise RuntimeError("military lab not initialized")
    steps = max(1, min(60, int(steps)))
    meta = get_lab_meta(ws.lab_key) or {"name": "军事推演实验室", "key": "military"}
    events = list(ws.timeline_events)
    scen_key = scenario_key or ws.military_lab.scenario_key
    bf_key = battlefield_key or ws.military_lab.battlefield_key

    async with ws.lock:
        ws.military_lab.prepare_simulation(
            scenario_key=scen_key,
            battlefield_key=bf_key,
            timeline_events=events,
        )
        result = ws.military_lab.simulate(steps=steps)
        scen = result.get("scenario") or {}
        bf = result.get("battlefield") or {}
        mode_label = f"军事推演 · {scen.get('name', '战役')}"

        dashboard = build_dashboard(ws.civilization_key, user_id=ws.user_id)
        winner = result.get("winner", "stalemate")
        winner_label = {"red": "红方优势", "blue": "蓝方优势", "stalemate": "僵持"}.get(winner, winner)
        metrics_summary = {
            "战役": scen.get("name", ""),
            "类型": scen.get("type_label", scen.get("type", "")),
            "地形": bf.get("name", ""),
            "红方": f"{result['red']['name']} · 兵力 {result['red']['strength']}",
            "蓝方": f"{result['blue']['name']} · 兵力 {result['blue']['strength']}",
            "结果": winner_label,
            "事件数": len(events),
        }

        report = build_report(
            lab_key="military",
            lab_name=meta.get("name", "军事推演实验室"),
            civilization_name=ws.civilization_name or ws.civilization_key,
            civilization_key=ws.civilization_key,
            horizon=steps,
            dimensions=["red_strength", "blue_strength", "red_morale", "blue_morale"],
            series={"红蓝兵力": ws.military_lab.history},
            events=events,
            metrics_summary=metrics_summary,
            analysis_sections=[{"heading": "推演概述", "body": ""}],
        )
        report["mode"] = "military"
        report["mode_label"] = mode_label
        report["dashboard"] = {
            "era_label": dashboard.get("era_label", ""),
            "population_explanation": dashboard.get("population_explanation", ""),
            "current_state": dashboard.get("current_state", {}),
        }
        report["analysis"] = analysis_from_simulation(
            "military",
            events,
            report.get("predictions") or [],
            extra="；".join(result.get("recommendations") or [])[:400],
        )
        report["simulation"] = result
        ws.last_report = report

        pdf_bytes = build_pdf_bytes(report)
        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    return {
        "report": report,
        "result": result,
        "simulation": result,
        "pdf_base64": pdf_b64,
        "pdf_filename": f"{ws.civilization_key}_military_report.pdf",
        "military": ws.military_lab.snapshot(),
        "lab": lab_snapshot(ws),
    }


# ---------- population ops ----------
async def lab_population_simulate(
    ws: LabWorkspace,
    *,
    years: int = 10,
    scope: str = "global",
    region_key: str | None = None,
    city_key: str | None = None,
) -> dict[str, Any]:
    """Unified population simulation: background + scope + events → PDF report."""
    if not ws.population_lab:
        raise RuntimeError("population lab not initialized")
    years = max(1, min(100, int(years)))
    scope = scope if scope in ("global", "city", "region") else "global"
    key = region_key or city_key or ("global" if scope == "global" else None)
    events = list(ws.timeline_events)

    async with ws.lock:
        ws.population_lab.prepare_simulation(
            scope=scope,
            region_key=key,
            timeline_events=events,
        )
        result = ws.population_lab.simulate(years=years)
        scope_label = result.get("scope_label", scope)
        region_name = result.get("region_name", "全局")
        mode_label = f"人口推演 · {scope_label} · {region_name}"
        metrics = {
            "范围": f"{scope_label} · {region_name}",
            "推演年数": years,
            "总人口": f"{result.get('total_pop', 0):,}",
            "生育率": result.get("fertility_rate", ""),
            "认知指数": f"{(result.get('cognition_index', 0) or 0) * 100:.0f}%",
            "事件数": len(events),
        }
        report, pdf_b64 = _finalize_lab_pdf_report(
            ws, lab_key="population", mode_label=mode_label, steps=years,
            dimensions=["total_pop", "fertility_rate", "cognition_index"],
            series={"人口演化": ws.population_lab.history}, events=events,
            metrics_summary=metrics, sim_result=result,
            extra="；".join(result.get("recommendations") or []),
        )

    return {
        "report": report,
        "result": result,
        "simulation": result,
        "pdf_base64": pdf_b64,
        "pdf_filename": f"{ws.civilization_key}_population_{scope}_{region_name}.pdf",
        "population": ws.population_lab.snapshot(),
        "lab": lab_snapshot(ws),
    }


async def lab_population_shock(ws: LabWorkspace, kind: str, magnitude: float = 1.0, note: str = "") -> dict[str, Any]:
    if not ws.population_lab:
        raise RuntimeError("population lab not initialized")
    async with ws.lock:
        rec = ws.population_lab.apply_shock(kind, magnitude=magnitude, note=note)
        return {"shock": rec, "population": ws.population_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_population_policy(ws: LabWorkspace, kind: str, magnitude: float = 1.0) -> dict[str, Any]:
    if not ws.population_lab:
        raise RuntimeError("population lab not initialized")
    async with ws.lock:
        rec = ws.population_lab.apply_policy(kind, magnitude=magnitude)
        return {"policy": rec, "population": ws.population_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_city_forecast(ws: LabWorkspace, *, horizon: int = 24, city_key: str | None = None) -> dict[str, Any]:
    if not ws.finance_lab:
        raise RuntimeError("finance lab not initialized")
    if city_key:
        if not ws.finance_lab.select_city(city_key):
            raise ValueError(f"unknown city: {city_key}")
    result = await ws.finance_lab.city_desk.forecast(ws.llm, horizon=horizon)
    return {"result": result, "finance_lab": ws.finance_lab.snapshot(), "lab": lab_snapshot(ws)}


async def lab_city_event(
    ws: LabWorkspace, *, at_step: int, title: str, kind: str = "policy",
    magnitude: float = 0.2, note: str = "",
) -> dict[str, Any]:
    if not ws.finance_lab:
        raise RuntimeError("finance lab not initialized")
    async with ws.lock:
        ev = ws.finance_lab.city_desk.insert_event(
            at_step=at_step, title=title, kind=kind, magnitude=magnitude, note=note,
        )
        return {"event": ev.as_dict(), "finance_lab": ws.finance_lab.snapshot(), "lab": lab_snapshot(ws)}


def _apply_timeline_to_finance(ws: LabWorkspace, mode: str = "global") -> None:
    if not ws.finance_lab:
        return
    for ev in ws.timeline_events:
        step = int(ev.get("at_step") or 0)
        title = str(ev.get("title") or "事件")
        mag = float(ev.get("magnitude") or 0.15)
        kind = str(ev.get("kind") or "custom")
        if mode in ("global", "market"):
            ws.finance_lab.global_desk.insert_event(at_step=step, title=title, kind=kind, magnitude=mag)
        if mode in ("city", "market"):
            ws.finance_lab.city_desk.insert_event(at_step=step, title=title, kind=kind, magnitude=mag)
        if mode in ("corporate", "market"):
            corp_kind = kind if kind in ("earnings", "product", "scandal", "policy") else "custom"
            ws.finance_lab.corporate.insert_event(at_step=step, title=title, kind=corp_kind, magnitude=mag)


def _run_market_warmup(ws: LabWorkspace, *, steps: int = 12) -> dict[str, Any]:
    """Run agent-based market briefly; return snapshot for macro closure."""
    if not ws.finance or not ws.world or not ws.society:
        return {}
    for _ in range(max(1, min(steps, 48))):
        ws.finance.advance(ws.world, ws.society)
        ws.world.clock.advance(1)
    return ws.finance.snapshot()


def _shock_kind_from_event(kind: str, magnitude: float) -> str:
    if kind in ("war", "plague", "earthquake"):
        return "demand"
    if kind in ("rate", "price", "property"):
        return "price"
    if magnitude < 0:
        return "demand"
    return "supply"


def _apply_market_closure_to_macro(ws: LabWorkspace, snap: dict[str, Any]) -> None:
    if not snap or not ws.finance_lab:
        return
    ws.finance_lab.global_desk.set_initial_from_market(snap)
    if ws.finance_lab.city_desk.history:
        ws.finance_lab.city_desk._terminal_state = ws.finance_lab.global_desk._terminal_state


def _configure_finance_institution_context(ws: LabWorkspace, market_snap: dict[str, Any] | None) -> None:
    """Wire population, market, and corporate signals into institution evolution."""
    if not ws.finance_lab:
        return
    pop_snap = None
    if ws.population_lab:
        try:
            pop_snap = ws.population_lab.snapshot()
        except Exception:
            pop_snap = None
    corp_hist = ws.finance_lab.corporate.history if ws.finance_lab.corporate else None
    ws.finance_lab.configure_institution_context(
        market_snap=market_snap,
        population_snap=pop_snap,
        corporate_history=corp_hist,
    )


_MODE_LABELS = {
    "global": "全局走势",
    "city": "城市金融",
    "corporate": "企业评估",
    "retail": "量化交易",
    "market": "市场清算",
}


async def lab_finance_simulate(
    ws: LabWorkspace,
    *,
    mode: str = "global",
    horizon: int = 24,
    city_key: str | None = None,
    company_key: str | None = None,
    company_name: str | None = None,
    sector: str | None = None,
    risk: str = "balanced",
    retail_horizon: str = "auto",
    capital: float | None = None,
    market_steps: int | None = None,
    skip_llm: bool = False,
) -> dict[str, Any]:
    """Unified finance simulation: apply timeline events, run selected desk, build report + PDF."""
    import asyncio
    import base64

    from ..layer2_civilization.civilization_dashboard import build_dashboard
    from .report_pdf import build_pdf_bytes

    if not ws.finance_lab:
        raise RuntimeError("finance lab not initialized")
    mode = mode if mode in _MODE_LABELS else "global"
    horizon = max(4, min(120, int(horizon)))
    meta = get_lab_meta(ws.lab_key) or {"name": "金融实验室", "key": "finance"}
    events = list(ws.timeline_events)
    series: dict[str, list[dict[str, Any]]] = {}
    sim_result: dict[str, Any] = {}
    dimensions: list[str] = []
    metrics_summary: dict[str, Any] = {}
    mode_label = _MODE_LABELS[mode]
    llm = None if skip_llm else ws.llm

    async with ws.lock:
        ws.finance_lab.prepare_simulation(city_key=city_key, company_key=company_key)
        if company_name:
            ws.finance_lab.corporate.company_name = company_name[:40]
        if sector:
            ws.finance_lab.corporate.sector = sector[:24]
        _apply_timeline_to_finance(ws, mode)

        warmup: dict[str, Any] = {}
        # Micro → macro closure: warm up agent market, seed macro desks
        if mode in ("global", "city", "corporate", "retail"):
            warmup = _run_market_warmup(ws, steps=min(24, horizon))
            if warmup:
                _apply_market_closure_to_macro(ws, warmup)
                _configure_finance_institution_context(ws, warmup)
        elif mode == "market" and ws.finance:
            _configure_finance_institution_context(ws, ws.finance.snapshot())

        if mode == "global":
            sim_result = await ws.finance_lab.global_desk.forecast(llm, horizon=horizon)
            sim_result["institutions"] = ws.finance_lab.institutions
            sim_result["calibration"] = ws.finance_lab.calibration
            sim_result["market_warmup"] = warmup
            series["全局指数"] = (sim_result.get("history") or []) + (sim_result.get("forecast") or [])
            dimensions = ["index", "growth", "risk"]
            tail = (sim_result.get("forecast") or [{}])[-1]
            metrics_summary = {k: tail.get(k, "") for k in ("index", "growth", "risk") if k in tail}
        elif mode == "city":
            sim_result = await ws.finance_lab.city_desk.forecast(llm, horizon=horizon)
            sim_result["institutions"] = ws.finance_lab.institutions
            sim_result["market_warmup"] = warmup
            cname = ws.finance_lab.city_desk.city_name
            mode_label = f"城市金融 · {cname}"
            series["城市指数"] = (sim_result.get("history") or []) + (sim_result.get("forecast") or [])
            dimensions = ["city_index", "property_index", "employment", "liquidity"]
            tail = (sim_result.get("forecast") or [{}])[-1]
            metrics_summary = {
                "城市": cname,
                **{k: tail.get(k, "") for k in ("city_index", "property_index", "employment", "liquidity") if k in tail},
            }
        elif mode == "corporate":
            sim_result = await ws.finance_lab.corporate.forecast(llm, horizon=horizon)
            sim_result["institutions"] = ws.finance_lab.institutions
            cname = ws.finance_lab.corporate.company_name
            mode_label = f"企业评估 · {cname}"
            series["股价"] = (sim_result.get("history") or []) + (sim_result.get("forecast") or [])
            dimensions = ["price"]
            metrics_summary = {
                "企业": cname,
                "行业": ws.finance_lab.corporate.sector,
                "预期收益%": sim_result.get("expected_return_pct", ""),
            }
        elif mode == "retail":
            sim_result = ws.finance_lab.retail.run(
                risk=risk, horizon=retail_horizon, capital=capital,
                events=events,
            )
            rec = sim_result.get("recommendation") or {}
            path = sim_result.get("paths") or {}
            short_path = path.get("short") or []
            long_path = path.get("long") or []
            series["量化路径"] = [
                {"step": i, "value": v} for i, v in enumerate(
                    short_path if rec.get("horizon") == "short" else long_path
                )
            ]
            dimensions = ["return_pct", "drawdown"]
            metrics_summary = {
                "风险偏好": risk,
                "建议期限": rec.get("horizon_label", ""),
                "预估收益%": rec.get("expected_return_pct", ""),
                "期末资产": rec.get("expected_end_value", ""),
            }
        elif mode == "market":
            if not ws.finance or not ws.world or not ws.society:
                raise RuntimeError("market engine not initialized")
            from ..layer2_civilization.finance_institution_dynamics import (
                build_institution_context,
                evolve_institutions_step,
            )
            steps = max(1, min(168, int(market_steps or horizon)))
            seed_base = f"lab:{ws.user_id}:{ws.id}:{ws.civilization_key}"
            ws.finance = MarketState.create(genre=ws.genre, seed=f"{seed_base}:mkt", society=ws.society)
            ws.world.clock.tick = 0
            ws.finance_lab.reset_institutions()
            _configure_finance_institution_context(ws, None)
            inst_audit: list[dict[str, Any]] = []
            for ev in events:
                mag = float(ev.get("magnitude") or 0.15)
                kind = _shock_kind_from_event(str(ev.get("kind") or "custom"), mag)
                ws.finance.schedule_shock(
                    kind=kind, good_id="*", magnitude=abs(mag),
                    duration=max(3, int(abs(mag) * 20)), note=str(ev.get("title") or "")[:80],
                )
            for tick in range(steps):
                ws.finance.advance(ws.world, ws.society)
                ws.world.clock.advance(1)
                snap_tick = ws.finance.snapshot()
                ctx = build_institution_context(
                    step=tick,
                    genre=ws.genre,
                    market_snap=snap_tick,
                    demographics=ws.finance_lab.institution_context_kwargs.get("demographics"),
                    population_snap=ws.population_lab.snapshot() if ws.population_lab else None,
                    corporate_history=ws.finance_lab.corporate.history,
                    baseline_population=ws.finance_lab.baseline_population,
                )
                delta = evolve_institutions_step(ws.finance_lab.institutions, ctx, [])
                if tick % max(1, steps // 12) == 0 or tick == steps - 1:
                    inst_audit.append({"step": tick, "institutions": delta, "context": ctx.__dict__})
            sim_result = ws.finance.snapshot()
            sim_result["institutions"] = ws.finance_lab.institutions
            sim_result["institution_evolution"] = inst_audit
            sim_result["methodology"] = {
                "engine": "agent_based_market_v1",
                "paradigm": "multi_agent",
                "agents": len(ws.society.all()) if ws.society else 0,
                "mechanism": "heterogeneous agents supply/demand → inventory pressure → price discovery",
                "references": ["Heterogeneous-agent market microstructure (ABM-CGE lite)"],
                "disclaimer": "合成社会主体，非真实人口或订单簿数据。",
            }
            sim_result["audit_trail"] = [
                {
                    "step": h.get("tick"),
                    "outputs": {
                        "price_index": h.get("price_index"),
                        "inflation": h.get("inflation"),
                        "gini": h.get("gini"),
                    },
                }
                for h in (sim_result.get("history") or [])[-min(steps, 12):]
            ]
            hist = sim_result.get("history") or []
            series["物价指数"] = hist
            dimensions = ["price_index", "inflation", "money_supply", "gini"]
            metrics_summary = {
                "物价指数": sim_result.get("price_index", ""),
                "通胀%": sim_result.get("inflation", ""),
                "货币存量": sim_result.get("money_supply", ""),
                "基尼系数": sim_result.get("gini", ""),
            }
        else:
            raise ValueError(f"unknown finance mode: {mode}")

    dashboard = build_dashboard(ws.civilization_key, user_id=ws.user_id)
    narrative = sim_result.get("narrative") if isinstance(sim_result.get("narrative"), dict) else {}
    summary_extra = narrative.get("summary") or sim_result.get("summary") or ""

    bands = sim_result.get("confidence_bands") or []
    if bands:
        series["置信区间"] = [
            {"step": b.get("step", i), "p10": b["p10"], "p50": b["p50"], "p90": b["p90"], "label": f"F+{i+1}"}
            for i, b in enumerate(bands)
        ]

    report = build_report(
        lab_key="finance",
        lab_name=meta.get("name", "金融实验室"),
        civilization_name=ws.civilization_name or ws.civilization_key,
        civilization_key=ws.civilization_key,
        horizon=horizon,
        dimensions=dimensions,
        series=series,
        events=events,
        metrics_summary=metrics_summary or {"推演步数": horizon},
        analysis_sections=[{"heading": "推演概述", "body": ""}],
    )
    report["mode"] = mode
    report["mode_label"] = mode_label
    report["dashboard"] = {
        "era_label": dashboard.get("era_label", ""),
        "population_explanation": dashboard.get("population_explanation", ""),
        "current_state": dashboard.get("current_state", {}),
    }
    report["analysis"] = analysis_from_simulation(
        "finance", events, report.get("predictions") or [],
        extra=str(summary_extra)[:400],
        mode=mode,
        simulation=sim_result,
    )
    report = enrich_finance_report(report, sim_result, mode=mode, horizon=horizon)
    report["simulation"] = sim_result
    ws.last_report = report

    pdf_bytes = await asyncio.to_thread(build_pdf_bytes, report)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    return {
        "report": report,
        "simulation": sim_result,
        "mode": mode,
        "pdf_base64": pdf_b64,
        "pdf_filename": f"{ws.civilization_key}_{mode}_report.pdf",
        "finance": ws.finance.snapshot() if ws.finance else None,
        "finance_lab": ws.finance_lab.snapshot(),
        "lab": lab_snapshot(ws),
    }


def _apply_timeline_to_opinion(ws: LabWorkspace) -> None:
    if not ws.opinion_lab:
        return
    for ev in ws.timeline_events:
        ws.opinion_lab.insert_node(
            at_step=int(ev.get("at_step") or 0),
            title=str(ev.get("title") or ""),
            kind=str(ev.get("kind") or "custom"),
            magnitude=float(ev.get("magnitude") or 0.15),
        )


async def lab_upload_dataset(ws: LabWorkspace, filename: str, content: bytes, *, use_llm_ner: bool = True) -> dict[str, Any]:
    from .event_ner import enrich_timeline_event, structure_events_batch

    save_upload(ws.user_id, ws.id, filename, content)
    parsed = parse_upload(filename, content)
    if use_llm_ner and ws.finance_lab:
        items = [{"title": e.title, "time": e.time_label, "description": e.description, "kind": e.kind, "magnitude": e.magnitude} for e in parsed]
        structured = await structure_events_batch(
            ws.llm if use_llm_ner else None,
            items,
            civilization_name=ws.civilization_name,
            genre=ws.genre,
            institutions=ws.finance_lab.institutions,
            use_llm=use_llm_ner,
        )
        parsed = structured or parsed
    for ev in parsed:
        d = enrich_timeline_event(ev.as_dict())
        ws.timeline_events.append(d)
    ws.timeline_events.sort(key=lambda e: e.get("at_step", 0))
    return {"imported": len(parsed), "events": [e if isinstance(e, dict) else e.as_dict() for e in ws.timeline_events[-len(parsed):]], "lab": lab_snapshot(ws)}


async def lab_add_manual_events(ws: LabWorkspace, items: list[dict[str, Any]], *, use_llm_ner: bool = True) -> dict[str, Any]:
    from .event_ner import enrich_timeline_event, structure_events_batch

    if use_llm_ner and ws.finance_lab:
        parsed = await structure_events_batch(
            ws.llm,
            items,
            civilization_name=ws.civilization_name,
            genre=ws.genre,
            institutions=ws.finance_lab.institutions,
            use_llm=use_llm_ner,
        )
    else:
        parsed = parse_manual_events(items)
    for ev in parsed:
        ws.timeline_events.append(enrich_timeline_event(ev.as_dict()))
    ws.timeline_events.sort(key=lambda e: e.get("at_step", 0))
    return {"added": len(parsed), "timeline_events": ws.timeline_events, "lab": lab_snapshot(ws)}


async def lab_run_report(ws: LabWorkspace, *, horizon: int = 24, mode: str = "auto") -> dict[str, Any]:
    """Run simulation with timeline events and generate structured report."""
    horizon = max(4, min(120, int(horizon)))
    meta = get_lab_meta(ws.lab_key) or {"name": ws.lab_key, "key": ws.lab_key}
    lab_name = meta.get("name", ws.lab_key)
    events = list(ws.timeline_events)
    series: dict[str, list[dict[str, Any]]] = {}
    sim_result: dict[str, Any] = {}
    dimensions: list[str] = []
    desk_mode = "global"

    async with ws.lock:
        if ws.lab_key == "finance":
            desk_mode = mode if mode in ("global", "city") else "global"
            _apply_timeline_to_finance(ws, desk_mode)
            if desk_mode == "city":
                sim_result = await ws.finance_lab.city_desk.forecast(ws.llm, horizon=horizon)
                hist = ws.finance_lab.city_desk.history
                fc = sim_result.get("forecast") or []
                series["城市指数"] = hist + fc
                dimensions = ["city_index", "property_index", "employment", "liquidity"]
            else:
                sim_result = await ws.finance_lab.global_desk.forecast(ws.llm, horizon=horizon)
                hist = ws.finance_lab.global_desk.history
                fc = sim_result.get("forecast") or []
                series["全局指数"] = hist + fc
                dimensions = ["index", "growth", "risk"]
        elif ws.lab_key == "opinion":
            _apply_timeline_to_opinion(ws)
            sim_result = ws.opinion_lab.simulate(steps=horizon)
            series["舆情热度"] = ws.opinion_lab.history
            dimensions = ["heat", "sentiment", "polarization"]
        elif ws.lab_key == "military":
            sim_result = ws.military_lab.simulate(steps=min(horizon, 60))
            series["红蓝兵力"] = ws.military_lab.history
            dimensions = ["red_strength", "blue_strength", "red_morale", "blue_morale"]
        elif ws.lab_key == "population":
            for ev in events:
                kind = ev.get("kind") or "war"
                if kind in ("war", "plague", "earthquake", "flood", "pest"):
                    ws.population_lab.apply_shock(kind, magnitude=float(ev.get("magnitude") or 1))
            sim_result = ws.population_lab.simulate(years=min(horizon // 2, 50) or 10)
            series["人口总量"] = ws.population_lab.history
            dimensions = ["total_pop", "fertility_rate", "cognition_index"]
        else:
            raise RuntimeError(f"report not supported for lab: {ws.lab_key}")

    metrics_summary = {}
    if ws.lab_key == "population" and ws.population_lab:
        metrics_summary = {
            "总人口": f"{int(ws.population_lab.total_pop):,}",
            "生育率": ws.population_lab.fertility_rate,
            "认知指数": f"{ws.population_lab.cognition_index*100:.0f}%",
        }
    elif ws.lab_key == "finance" and sim_result.get("forecast"):
        tail = sim_result["forecast"][-1]
        metrics_summary = {k: tail.get(k, "") for k in list(tail.keys())[:6] if k not in ("label", "forecast")}

    preds = []
    report = build_report(
        lab_key=ws.lab_key,
        lab_name=lab_name,
        civilization_name=ws.civilization_name or ws.civilization_key,
        civilization_key=ws.civilization_key,
        horizon=horizon,
        dimensions=dimensions,
        series=series,
        events=events,
        metrics_summary=metrics_summary or {"推演步数": horizon},
        analysis_sections=[{"heading": "推演概述", "body": ""}],
    )
    report["analysis"] = analysis_from_simulation(
        ws.lab_key, events, report.get("predictions") or [],
        extra=(sim_result.get("narrative") or {}).get("summary") if isinstance(sim_result.get("narrative"), dict) else str(sim_result.get("summary", ""))[:300],
        mode=desk_mode if ws.lab_key == "finance" else "global",
    )
    report["predictions"] = report.get("predictions") or []
    report["simulation"] = sim_result
    ws.last_report = report
    return {"report": report, "lab": lab_snapshot(ws)}


async def lab_population_cognition(ws: LabWorkspace, kind: str, magnitude: float = 1.0) -> dict[str, Any]:
    if not ws.population_lab:
        raise RuntimeError("population lab not initialized")
    async with ws.lock:
        rec = ws.population_lab.apply_cognition(kind, magnitude=magnitude)
        return {"cognition": rec, "population": ws.population_lab.snapshot(), "lab": lab_snapshot(ws)}


def _finalize_lab_pdf_report(
    ws: LabWorkspace,
    *,
    lab_key: str,
    mode_label: str,
    steps: int,
    dimensions: list[str],
    series: dict[str, list[dict[str, Any]]],
    events: list[dict[str, Any]],
    metrics_summary: dict[str, Any],
    sim_result: dict[str, Any],
    extra: str = "",
) -> tuple[dict[str, Any], str]:
    from ..layer2_civilization.civilization_dashboard import build_dashboard
    from .report_pdf import build_pdf_bytes
    import base64

    meta = get_lab_meta(lab_key) or {"name": lab_key, "key": lab_key}
    dashboard = build_dashboard(ws.civilization_key, user_id=ws.user_id)
    report = build_report(
        lab_key=lab_key,
        lab_name=meta.get("name", lab_key),
        civilization_name=ws.civilization_name or ws.civilization_key,
        civilization_key=ws.civilization_key,
        horizon=steps,
        dimensions=dimensions,
        series=series,
        events=events,
        metrics_summary=metrics_summary,
        analysis_sections=[{"heading": "推演概述", "body": ""}],
    )
    report["mode"] = lab_key
    report["mode_label"] = mode_label
    report["dashboard"] = {
        "era_label": dashboard.get("era_label", ""),
        "population_explanation": dashboard.get("population_explanation", ""),
        "current_state": dashboard.get("current_state", {}),
    }
    report["analysis"] = analysis_from_simulation(
        lab_key, events, report.get("predictions") or [], extra=extra[:400],
    )
    report["simulation"] = sim_result
    ws.last_report = report
    pdf_b64 = base64.b64encode(build_pdf_bytes(report)).decode("ascii")
    return report, pdf_b64


async def lab_policy_simulate(
    ws: LabWorkspace,
    *,
    agency_key: str | None = None,
    instrument_key: str | None = None,
    steps: int = 24,
) -> dict[str, Any]:
    if not ws.policy_lab:
        raise RuntimeError("policy lab not initialized")
    steps = max(1, min(120, int(steps)))
    events = list(ws.timeline_events)
    async with ws.lock:
        ws.policy_lab.prepare_simulation(
            agency_key=agency_key,
            instrument_key=instrument_key,
            timeline_events=events,
        )
        result = ws.policy_lab.simulate(steps=steps)
        ag = result.get("agency") or {}
        inst = result.get("instrument") or {}
        mode_label = f"政令推演 · {ag.get('name', '')} · {inst.get('name', '')}"
        metrics = {
            "主政部门": ag.get("name", ""),
            "政令": inst.get("name", ""),
            "执行率": f"{result.get('execution', 0):.0%}",
            "合规度": f"{result.get('compliance', 0):.0%}",
            "合法性": f"{result.get('legitimacy', 0):.0%}",
            "社会响应": f"{result.get('social_response', 0):+.2f}",
        }
        report, pdf_b64 = _finalize_lab_pdf_report(
            ws, lab_key="policy", mode_label=mode_label, steps=steps,
            dimensions=["compliance", "legitimacy", "execution", "social_response"],
            series={"政令执行": ws.policy_lab.history}, events=events,
            metrics_summary=metrics, sim_result=result,
            extra="；".join(result.get("recommendations") or []),
        )
    return {
        "report": report, "result": result, "simulation": result,
        "pdf_base64": pdf_b64,
        "pdf_filename": f"{ws.civilization_key}_policy_report.pdf",
        "policy": ws.policy_lab.snapshot(), "lab": lab_snapshot(ws),
    }


async def lab_weather_simulate(
    ws: LabWorkspace,
    *,
    role_key: str | None = None,
    pattern_key: str | None = None,
    steps: int = 24,
) -> dict[str, Any]:
    if not ws.weather_lab:
        raise RuntimeError("weather lab not initialized")
    steps = max(1, min(120, int(steps)))
    events = list(ws.timeline_events)
    async with ws.lock:
        ws.weather_lab.prepare_simulation(
            role_key=role_key, pattern_key=pattern_key, timeline_events=events,
        )
        result = ws.weather_lab.simulate(steps=steps)
        role = result.get("role") or {}
        pat = result.get("pattern") or {}
        metrics_tail = result.get("metrics") or {}
        mode_label = f"气象推演 · {role.get('name', '')} · {pat.get('name', '')}"
        metrics = {"视角": role.get("name", ""), "气候模式": pat.get("name", ""), **{
            k: (f"{v:.0%}" if isinstance(v, float) and v <= 1.5 else f"{v:.2f}")
            for k, v in metrics_tail.items() if k != "tick"
        }}
        report, pdf_b64 = _finalize_lab_pdf_report(
            ws, lab_key="weather", mode_label=mode_label, steps=steps,
            dimensions=list(metrics_tail.keys()),
            series={"气象影响": ws.weather_lab.history}, events=events,
            metrics_summary=metrics, sim_result=result,
            extra=result.get("role_summary", ""),
        )
    return {
        "report": report, "result": result, "simulation": result,
        "pdf_base64": pdf_b64,
        "pdf_filename": f"{ws.civilization_key}_weather_{role.get('key', 'role')}_report.pdf",
        "weather": ws.weather_lab.snapshot(), "lab": lab_snapshot(ws),
    }


async def lab_environment_simulate(
    ws: LabWorkspace,
    *,
    region_key: str | None = None,
    measure_key: str | None = None,
    emission_intensity: float | None = None,
    enterprise_name: str | None = None,
    steps: int = 36,
) -> dict[str, Any]:
    if not ws.environment_lab:
        raise RuntimeError("environment lab not initialized")
    steps = max(1, min(120, int(steps)))
    events = list(ws.timeline_events)
    async with ws.lock:
        ws.environment_lab.prepare_simulation(
            region_key=region_key,
            measure_key=measure_key,
            emission_intensity=emission_intensity,
            enterprise_name=enterprise_name,
            timeline_events=events,
        )
        result = ws.environment_lab.simulate(steps=steps)
        region = result.get("region") or {}
        measure = result.get("measure") or {}
        mode_label = f"环保演化 · {region.get('name', '')} · {result.get('enterprise', '')}"
        metrics = {
            "地区": region.get("name", ""),
            "措施": measure.get("name", ""),
            "排放强度": f"{result.get('emission_intensity', 0):.0%}",
            "污染度": f"{result.get('pollution', 0):.1%}",
            "健康指数": f"{result.get('health_index', 0):.0%}",
            "财产损失": f"{result.get('property_damage', 0):.0f}",
        }
        if result.get("time_to_threshold"):
            metrics["达阈周期"] = result["time_to_threshold"]
        report, pdf_b64 = _finalize_lab_pdf_report(
            ws, lab_key="environment", mode_label=mode_label, steps=steps,
            dimensions=["pollution", "health_index", "property_damage"],
            series={"污染演化": ws.environment_lab.history}, events=events,
            metrics_summary=metrics, sim_result=result,
            extra="；".join(result.get("recommendations") or []),
        )
    return {
        "report": report, "result": result, "simulation": result,
        "pdf_base64": pdf_b64,
        "pdf_filename": f"{ws.civilization_key}_environment_report.pdf",
        "environment": ws.environment_lab.snapshot(), "lab": lab_snapshot(ws),
    }
