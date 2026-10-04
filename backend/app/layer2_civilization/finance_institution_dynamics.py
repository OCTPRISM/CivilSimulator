"""Dynamic financial institution evolution.

Institutions continuously adapt to time, events (and magnitude), population,
macro economy, enterprise revenue, and agriculture/industry development.
Every simulation mainline feeds the same context into per-step evolution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .finance_institutions import get_finance_institutions

_TX_CLAMP = (0.55, 1.65)

_AG_IDS = frozenset({
    "grain", "food", "herb", "rations", "talent", "spirit", "info", "marketing",
})
_IND_IDS = frozenset({
    "salt", "arms", "energy", "hull", "craft", "housing", "artifact", "rd",
    "supply", "derivative", "equity", "bond", "labor", "silk", "data", "credit",
})


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class InstitutionContext:
    step: int = 0
    genre: str = "modern"
    population_norm: float = 1.0
    population_growth: float = 0.0
    urban_pct: float = 0.5
    gdp_index: float = 100.0
    macro_index: float = 100.0
    inflation: float = 2.0
    output_gap: float = 0.0
    liquidity: float = 0.55
    risk: float = 0.35
    agriculture_index: float = 100.0
    industry_index: float = 100.0
    enterprise_revenue_index: float = 100.0
    market_velocity: float = 0.1
    gini: float = 0.35
    event_pressure: float = 0.0
    event_kinds: list[str] = field(default_factory=list)


def _sector_indices_from_market(snap: dict[str, Any] | None) -> tuple[float, float]:
    if not snap:
        return 100.0, 100.0
    goods = snap.get("goods") or []
    ag_vals: list[float] = []
    ind_vals: list[float] = []
    for g in goods:
        gid = str(g.get("id") or "")
        base = float(g.get("base") or 1.0)
        price = float(g.get("price") or base)
        inv = float(g.get("inventory") or 50.0)
        if base <= 0:
            continue
        # Higher inventory + stable price → sector health; price spike → stress
        health = 100.0 * (inv / 50.0) ** 0.15 / max(0.75, price / base) ** 0.25
        if gid in _AG_IDS:
            ag_vals.append(health)
        elif gid in _IND_IDS:
            ind_vals.append(health)
    ag = sum(ag_vals) / len(ag_vals) if ag_vals else 100.0
    ind = sum(ind_vals) / len(ind_vals) if ind_vals else 100.0
    return round(ag, 2), round(ind, 2)


def _enterprise_revenue_index(
    corporate_history: list[dict[str, Any]] | None,
    macro_index: float,
) -> float:
    if corporate_history and len(corporate_history) >= 2:
        p0 = float(corporate_history[0].get("price") or 100.0)
        p1 = float(corporate_history[-1].get("price") or p0)
        if p0 > 0:
            return round(100.0 * (p1 / p0), 2)
    return round(macro_index, 2)


def build_institution_context(
    *,
    step: int,
    genre: str,
    macro_state: Any | None = None,
    demographics: dict[str, Any] | None = None,
    market_snap: dict[str, Any] | None = None,
    population_snap: dict[str, Any] | None = None,
    corporate_history: list[dict[str, Any]] | None = None,
    events_at_step: list[dict[str, Any]] | None = None,
    baseline_population: float | None = None,
) -> InstitutionContext:
    demo = demographics or {}
    pop_snap = population_snap or {}
    ms = macro_state

    base_pop = float(baseline_population or demo.get("total_pop") or 1_000_000)
    cur_pop = float(pop_snap.get("total_pop") or demo.get("total_pop") or base_pop)
    pop_norm = cur_pop / max(1.0, base_pop)

    fert = float(pop_snap.get("fertility_rate") or demo.get("fertility_rate") or 2.0)
    pop_growth = (fert - 2.0) * 0.008
    if ms is not None:
        pop_growth += float(getattr(ms, "output_gap", 0.0) or 0.0) * 0.15

    ag_idx, ind_idx = _sector_indices_from_market(market_snap)
    macro_index = float(getattr(ms, "index", 100.0) if ms else market_snap.get("price_index") if market_snap else 100.0)
    ent_rev = _enterprise_revenue_index(corporate_history, macro_index)

    evs = events_at_step or []
    pressure = sum(abs(float(e.get("magnitude") or 0.0)) for e in evs)

    return InstitutionContext(
        step=step,
        genre=genre,
        population_norm=round(pop_norm, 4),
        population_growth=round(pop_growth, 4),
        urban_pct=float(demo.get("urban_pop_pct") or 0.5),
        gdp_index=float(demo.get("gdp_index") or 100.0),
        macro_index=round(macro_index, 3),
        inflation=float(getattr(ms, "inflation", 2.0) if ms else 2.0),
        output_gap=float(getattr(ms, "output_gap", 0.0) if ms else 0.0),
        liquidity=float(getattr(ms, "liquidity", 0.55) if ms else 0.55),
        risk=float(ms.risk_score() if ms else 0.35),
        agriculture_index=ag_idx,
        industry_index=ind_idx,
        enterprise_revenue_index=ent_rev,
        market_velocity=float(market_snap.get("velocity") or 0.1) if market_snap else 0.1,
        gini=float(market_snap.get("gini") or 0.35) if market_snap else 0.35,
        event_pressure=round(pressure, 4),
        event_kinds=[str(e.get("kind") or "custom") for e in evs],
    )


def initialize_dynamic_institutions(
    genre: str,
    seed_key: str = "",
    demographics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    demo = demographics or {}
    gdp = float(demo.get("gdp_index") or 100.0)
    out: list[dict[str, Any]] = []
    for inst in get_finance_institutions(genre, seed_key):
        row = dict(inst)
        base_tx = dict(inst.get("transmission") or {})
        row["base_transmission"] = base_tx
        row["transmission"] = dict(base_tx)
        row["influence"] = round(0.92 + min(0.12, gdp / 1200), 3)
        row["health"] = round(_clamp(0.72 + gdp / 500, 0.55, 0.95), 3)
        row["capacity"] = round(_clamp(0.85 + float(demo.get("urban_pop_pct") or 0.5) * 0.25, 0.6, 1.3), 3)
        row["assets_index"] = round(gdp, 2)
        row["throughput"] = round(row["capacity"] * 0.12, 3)
        row["last_delta"] = {}
        row["metrics_history"] = []
        out.append(row)
    return out


def _events_at_step(events: list[Any], step: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in events:
        ev = raw.as_dict() if hasattr(raw, "as_dict") else dict(raw) if isinstance(raw, dict) else {}
        at = ev.get("at_step")
        if at is None:
            at = -1
        if int(at) == step:
            out.append(ev)
    return out


def _evolve_one(
    inst: dict[str, Any],
    ctx: InstitutionContext,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    itype = str(inst.get("institution_type") or "")
    base_tx = inst.get("base_transmission") or inst.get("transmission") or {}
    tx = dict(inst.get("transmission") or base_tx)

    influence = float(inst.get("influence", 1.0))
    health = float(inst.get("health", 0.85))
    capacity = float(inst.get("capacity", 1.0))

    di = dh = dc = 0.0
    dtx: dict[str, float] = {}

    # Macro cycle
    if ctx.output_gap < -0.025:
        stress = abs(ctx.output_gap) * 8
        dh -= 0.012 * stress
        if itype in ("credit", "exchange", "clearing", "guild"):
            dc -= 0.015 * stress
    elif ctx.output_gap > 0.035:
        dh += 0.006
        dc += 0.008

    if ctx.risk > 0.55:
        dh -= (ctx.risk - 0.55) * 0.06
    if ctx.liquidity < 0.42:
        dh -= 0.01

    # Population & urbanization
    pop_pull = (ctx.population_norm - 1.0) * 0.12 + ctx.population_growth * 0.35
    if itype in ("credit", "clearing", "guild"):
        dc += pop_pull * 0.05
        di += pop_pull * 0.025
    if itype == "fiscal_regulator":
        di += (ctx.gini - 0.35) * 0.08

    # Agriculture / industry development
    ag_dev = (ctx.agriculture_index - 100.0) / 100.0
    ind_dev = (ctx.industry_index - 100.0) / 100.0

    if itype == "monopoly":
        dtx["price"] = dtx.get("price", 0.0) - ag_dev * 0.06 + ind_dev * 0.03
        dc += ag_dev * 0.02
    if itype == "fiscal_regulator":
        di += ag_dev * 0.015 + ind_dev * 0.01
        dtx["policy"] = dtx.get("policy", 0.0) + (ctx.gdp_index - 100.0) / 500.0
    if itype == "exchange":
        dtx["earnings"] = dtx.get("earnings", 0.0) + (ctx.enterprise_revenue_index - 100.0) / 100.0 * 0.07
        dc += ind_dev * 0.025
    if itype == "central_bank":
        pi_gap = ctx.inflation - 2.0
        dtx["rate"] = dtx.get("rate", 0.0) + pi_gap * 0.012
        dtx["liquidity"] = dtx.get("liquidity", 0.0) + (0.52 - ctx.liquidity) * 0.05
        di += abs(pi_gap) * 0.008
    if itype == "credit":
        dtx["liquidity"] = dtx.get("liquidity", 0.0) + (ctx.liquidity - 0.5) * 0.04 - ctx.risk * 0.035
        dtx["rate"] = dtx.get("rate", 0.0) + ctx.risk * 0.025 - pop_pull * 0.02
        dc += pop_pull * 0.03
    if itype == "clearing":
        dc += (ctx.market_velocity - 0.1) * 0.25
        dtx["liquidity"] = dtx.get("liquidity", 0.0) + ind_dev * 0.03
    if itype == "guild":
        dtx["custom"] = dtx.get("custom", 0.0) + ind_dev * 0.02
        dc += ctx.market_velocity * 0.15

    # Step events (magnitude-weighted)
    for ev in events:
        kind = str(ev.get("kind") or "custom")
        mag = float(ev.get("magnitude") or 0.0)
        abs_mag = abs(mag)
        if kind in base_tx:
            dtx[kind] = dtx.get(kind, 0.0) + mag * 0.05
        if kind == "war":
            if itype in ("guild", "clearing", "credit", "monopoly"):
                dh -= abs_mag * 0.035
                di += abs_mag * 0.04
            if "war" in base_tx:
                dtx["war"] = dtx.get("war", 0.0) + mag * 0.04
        if kind == "policy" and itype in ("fiscal_regulator", "central_bank"):
            di += mag * 0.045
        if kind in ("earnings", "product") and itype == "exchange":
            dtx["earnings"] = dtx.get("earnings", 0.0) + mag * 0.035
        if kind in ("plague", "earthquake") and itype in ("credit", "clearing"):
            dh -= abs_mag * 0.05
            dc -= abs_mag * 0.04
        if kind == "rate" and itype == "central_bank":
            di += mag * 0.03

    # Time drift (institutional adaptation over horizon)
    time_drift = min(0.03, ctx.step * 0.0004)
    if itype == "exchange":
        dtx["earnings"] = dtx.get("earnings", 0.0) + time_drift * (ctx.enterprise_revenue_index / 100.0 - 1.0)

    influence = _clamp(influence + di, 0.35, 1.65)
    health = _clamp(health + dh, 0.22, 0.98)
    capacity = _clamp(capacity + dc, 0.28, 1.85)

    for k, dv in dtx.items():
        if k not in base_tx:
            continue
        bv = float(base_tx[k])
        nv = bv + dv
        tx[k] = _clamp(nv, _TX_CLAMP[0] * bv, _TX_CLAMP[1] * bv)

    inst["influence"] = round(influence, 4)
    inst["health"] = round(health, 4)
    inst["capacity"] = round(capacity, 4)
    inst["transmission"] = {k: round(float(v), 4) for k, v in tx.items()}
    inst["assets_index"] = round(
        float(inst.get("assets_index") or ctx.gdp_index)
        * (1.0 + ctx.output_gap * 0.35 + (health - 0.8) * 0.015),
        2,
    )
    inst["throughput"] = round(capacity * max(0.05, ctx.market_velocity) * 8.0, 3)

    return {
        "influence": round(di, 4),
        "health": round(dh, 4),
        "capacity": round(dc, 4),
        "transmission": {k: round(v, 4) for k, v in dtx.items()},
    }


def evolve_institutions_step(
    institutions: list[dict[str, Any]],
    ctx: InstitutionContext,
    events_at_step: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Mutate institutions for one simulation step; return audit summaries."""
    evs = events_at_step or []
    summaries: list[dict[str, Any]] = []
    for inst in institutions:
        delta = _evolve_one(inst, ctx, evs)
        inst["last_delta"] = delta
        hist = inst.setdefault("metrics_history", [])
        hist.append({
            "step": ctx.step,
            "influence": inst["influence"],
            "health": inst["health"],
            "capacity": inst["capacity"],
        })
        if len(hist) > 36:
            inst["metrics_history"] = hist[-36:]
        summaries.append({"name": inst.get("name", ""), **delta})
    return summaries


def institution_modifiers_from_state(
    institutions: list[dict[str, Any]],
    event_kind: str,
) -> dict[str, float]:
    """Effective transmission multipliers from live institution state."""
    mult: dict[str, float] = {}
    for inst in institutions:
        eff = (
            float(inst.get("influence", 1.0))
            * float(inst.get("capacity", 1.0))
            * (0.35 + 0.65 * float(inst.get("health", 0.85)))
        )
        tx = inst.get("transmission") or {}
        base = inst.get("base_transmission") or tx
        for ch, m in tx.items():
            if ch == event_kind or event_kind in ("custom", "political", "policy"):
                bm = float(base.get(ch, m))
                adj = 1.0 + (float(m) - bm) * eff + (bm - 1.0) * eff * 0.85
                mult[ch] = mult.get(ch, 1.0) * adj
    return mult


def institutions_audit_summary(institutions: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "name": i.get("name", ""),
            "influence": str(i.get("influence", "")),
            "health": str(i.get("health", "")),
            "capacity": str(i.get("capacity", "")),
            "throughput": str(i.get("throughput", "")),
            "era": i.get("era_label", ""),
        }
        for i in institutions
    ]
