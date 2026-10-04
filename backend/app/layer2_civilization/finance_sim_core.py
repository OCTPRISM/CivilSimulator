"""Structured macro-finance simulation core (v2).

Replaces naive random walks with an explainable macro pipeline:

1. Events → transmission channels (policy / IS / Phillips / risk)
2. Impulse persistence (exponential decay, half-life ~4 steps)
3. Monte Carlo scenario bands (p10 / p50 / p90)
4. Per-step audit trail (inputs, equations, event attribution)

Conceptual alignment (not econometrically calibrated on real data):
- IS curve + Taylor-style policy reaction (Galí, *Monetary Policy*, 2015)
- Phillips-type inflation dynamics
- Policy uncertainty → risk premium (Baker–Bloom–Davis EPU framework)
- Market clearing with heterogeneous agents → ``MarketState`` (market mode only)

This module is deterministic given seed; LLM never touches these numbers.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Any


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# Event kind → macro channel impacts (signed, unitless shock weights)
# Each entry documents *why* the channel moves (see channel_labels).
TRANSMISSION: dict[str, dict[str, float]] = {
    "rate": {
        "policy_rate": 0.40,
        "liquidity": -0.28,
        "risk_premium": 0.06,
    },
    "policy": {
        "output_gap": 0.24,
        "liquidity": 0.20,
        "inflation_shock": 0.06,
    },
    "political": {
        "risk_premium": 0.30,
        "output_gap": -0.12,
        "liquidity": -0.10,
    },
    "war": {
        "supply_shock": 0.35,
        "risk_premium": 0.28,
        "output_gap": -0.22,
    },
    "plague": {
        "supply_shock": 0.25,
        "output_gap": -0.18,
        "risk_premium": 0.15,
    },
    "earthquake": {
        "supply_shock": 0.30,
        "output_gap": -0.20,
        "liquidity": -0.08,
    },
    "price": {
        "inflation_shock": 0.25,
        "liquidity": -0.12,
    },
    "property": {
        "liquidity": 0.18,
        "output_gap": 0.08,
        "policy_rate": 0.05,
    },
    "earnings": {
        "output_gap": 0.15,
        "risk_premium": -0.08,
    },
    "product": {
        "output_gap": 0.12,
        "supply_shock": -0.08,
    },
    "scandal": {
        "risk_premium": 0.22,
        "liquidity": -0.10,
    },
    "custom": {
        "output_gap": 0.10,
        "risk_premium": 0.08,
    },
}

CHANNEL_LABELS: dict[str, str] = {
    "output_gap": "产出缺口（需求/景气）",
    "inflation_shock": "通胀冲击项",
    "policy_rate": "政策利率水平",
    "risk_premium": "风险溢价（EPU/地缘）",
    "liquidity": "流动性/信贷条件",
    "supply_shock": "供给侧扰动",
}

METHODOLOGY = {
    "engine": "structured_macro_v2",
    "paradigm": "hybrid",
    "macro_modes": "IS-Phillips-Taylor lite + long-run fusion + Monte Carlo bands",
    "market_mode": "agent_based_market_v1 (MarketState + Society agents)",
    "references": [
        "Galí (2015) — NK Phillips curve & monetary policy transmission",
        "Baker, Bloom, Davis (2016) — policy uncertainty & risk premium",
        "Heterogeneous-agent market clearing — internal MarketState kernel",
    ],
    "disclaimer": "文明沙盘参数，非计量校准；用于情景一致性与可解释推演，非实盘预测。",
}


@dataclass
class MacroParams:
    """Structural parameters (perturbed per MC path)."""
    rho_y: float = 0.78          # output gap persistence
    kappa_pi: float = 0.22       # Phillips slope
    beta_r: float = 0.35         # IS sensitivity to real rate
    phi_taylor: float = 0.45     # Taylor rule on inflation gap
    r_star: float = 2.5          # neutral rate (%)
    pi_star: float = 2.0         # inflation target (%)
    impulse_decay: float = 0.82  # ~4-step half-life
    sigma_y: float = 0.004
    sigma_pi: float = 0.035
    sigma_idx: float = 0.003


@dataclass
class MacroState:
    output_gap: float = 0.0
    inflation: float = 2.0
    policy_rate: float = 2.5
    risk_premium: float = 0.32
    liquidity: float = 0.55
    supply_shock: float = 0.0
    inflation_shock: float = 0.0
    index: float = 100.0

    def growth_pct(self) -> float:
        return round(self.output_gap * 100.0, 3)

    def risk_score(self) -> float:
        return round(_clamp(0.25 + self.risk_premium * 0.55 + max(0, -self.output_gap) * 0.3, 0.05, 0.95), 3)


@dataclass
class Impulses:
    output_gap: float = 0.0
    inflation_shock: float = 0.0
    policy_rate: float = 0.0
    risk_premium: float = 0.0
    liquidity: float = 0.0
    supply_shock: float = 0.0

    def decay(self, rate: float) -> None:
        self.output_gap *= rate
        self.inflation_shock *= rate
        self.policy_rate *= rate
        self.risk_premium *= rate
        self.liquidity *= rate
        self.supply_shock *= rate


def _event_dict(ev: Any) -> dict[str, Any]:
    if hasattr(ev, "as_dict"):
        return ev.as_dict()
    return dict(ev) if isinstance(ev, dict) else {}


def apply_events_to_impulses(
    events: list[Any],
    step: int,
    impulses: Impulses,
    *,
    genre: str = "modern",
    institution_scale: float = 1.0,
    institutions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Map timeline events at ``step`` into channel impulses; return attribution."""
    from .finance_institutions import institution_modifiers
    from .finance_institution_dynamics import institution_modifiers_from_state

    attributions: list[dict[str, Any]] = []
    for raw in events:
        ev = _event_dict(raw)
        at = ev.get("at_step")
        if at is None:
            at = -1
        if int(at) != step:
            continue
        kind = str(ev.get("kind") or "custom")
        mag = _clamp(float(ev.get("magnitude") or 0.0), -1.0, 1.0)
        if institutions:
            mods = institution_modifiers_from_state(institutions, kind)
        else:
            mods = institution_modifiers(genre, kind)
        event_scale = float(mods.get(kind, 1.0))
        channels = dict(TRANSMISSION.get(kind) or TRANSMISSION["custom"])
        # LLM NER may supply explicit channel weights
        preview = ev.get("channel_preview")
        if isinstance(preview, dict) and preview:
            for ch, v in preview.items():
                if ch in channels:
                    channels[ch] = float(v) / max(1e-6, abs(mag)) if abs(mag) > 1e-6 else float(v)
        hits: dict[str, float] = {}
        for ch, coef in channels.items():
            scale = event_scale * institution_scale
            delta = mag * coef * scale
            hits[ch] = round(delta, 4)
            if hasattr(impulses, ch):
                setattr(impulses, ch, getattr(impulses, ch) + delta)
        attributions.append({
            "step": step,
            "title": str(ev.get("title") or ""),
            "kind": kind,
            "magnitude": mag,
            "channels": hits,
            "rationale": ev.get("rationale") or _event_rationale(kind, hits),
            "source": ev.get("source", "manual"),
        })
    return attributions


def _event_rationale(kind: str, hits: dict[str, float]) -> str:
    parts = [f"{CHANNEL_LABELS.get(ch, ch)}{'↑' if v > 0 else '↓'}" for ch, v in hits.items() if abs(v) > 1e-4]
    prefix = {
        "rate": "货币政策传导",
        "policy": "财政/产业政策",
        "political": "政治不确定性",
        "war": "地缘冲突与供给中断",
        "earnings": "盈利预期",
        "scandal": "声誉与融资风险",
    }.get(kind, "综合冲击")
    return f"{prefix}：" + "、".join(parts[:4]) if parts else prefix


def macro_step(
    state: MacroState,
    impulses: Impulses,
    params: MacroParams,
    rng: random.Random,
    *,
    step: int,
    forecast: bool,
    genre: str = "modern",
    institution_scale: float = 1.0,
) -> tuple[MacroState, dict[str, Any]]:
    """One macro period. Returns new state + audit row."""
    prev = MacroState(**state.__dict__)

    eff_y = impulses.output_gap + impulses.supply_shock * -0.35
    eff_pi = impulses.inflation_shock + impulses.supply_shock * 0.40

    # Taylor-style endogenous policy adjustment toward inflation target
    pi_gap = state.inflation - params.pi_star
    policy_target = params.r_star + params.phi_taylor * pi_gap + impulses.policy_rate * 0.5
    policy_rate = _clamp(
        0.85 * state.policy_rate + 0.15 * policy_target,
        0.0, 12.0,
    )

    real_rate = policy_rate - state.inflation
    output_gap = (
        params.rho_y * state.output_gap
        + eff_y
        + 0.18 * impulses.liquidity
        - params.beta_r * (real_rate - (params.r_star - params.pi_star))
        + rng.gauss(0, params.sigma_y)
    )
    output_gap = _clamp(output_gap, -0.12, 0.10)

    inflation = (
        state.inflation
        + params.kappa_pi * output_gap
        + eff_pi
        + rng.gauss(0, params.sigma_pi)
    )
    inflation = _clamp(inflation, -1.0, 12.0)

    risk_premium = _clamp(
        0.75 * state.risk_premium + 0.25 * (0.32 + impulses.risk_premium),
        0.05, 0.95,
    )
    liquidity = _clamp(0.8 * state.liquidity + 0.2 * (0.55 + impulses.liquidity), 0.08, 0.92)

    # Index: attenuated macro pass-through (period = 1 scenario step ≈ 1 month)
    idx_ret = (
        0.14 * output_gap
        + 0.06 * (inflation - params.pi_star) / 100.0
        - 0.18 * risk_premium / 100.0
        + rng.gauss(0, params.sigma_idx)
    )
    idx_ret = _clamp(idx_ret, -0.06, 0.06)
    index = max(10.0, state.index * (1.0 + idx_ret))

    new_state = MacroState(
        output_gap=output_gap,
        inflation=round(inflation, 3),
        policy_rate=round(policy_rate, 3),
        risk_premium=round(risk_premium, 3),
        liquidity=round(liquidity, 3),
        supply_shock=round(impulses.supply_shock, 4),
        inflation_shock=round(impulses.inflation_shock, 4),
        index=round(index, 3),
    )

    audit = {
        "step": step,
        "forecast": forecast,
        "equations": [
            "output_gap = ρ·y + impulse_y − β·(real_rate − r*) + ε_y",
            "inflation = π + κ·y + impulse_π + ε_π",
            "policy_rate → Taylor(π − π*)",
            "index_return = clamp(0.14·y + 0.06·(π−π*) − 0.18·risk + ε, ±6%)",
        ],
        "inputs": {
            "prev_output_gap": round(prev.output_gap, 4),
            "prev_inflation": round(prev.inflation, 4),
            "real_rate": round(real_rate, 4),
            "impulses": {k: round(v, 4) for k, v in impulses.__dict__.items()},
        },
        "outputs": {
            "index": new_state.index,
            "growth": new_state.growth_pct(),
            "risk": new_state.risk_score(),
            "inflation": new_state.inflation,
            "policy_rate": new_state.policy_rate,
            "liquidity": new_state.liquidity,
        },
    }
    return new_state, audit


def _perturb_params(base: MacroParams, rng: random.Random) -> MacroParams:
    return MacroParams(
        rho_y=base.rho_y + rng.uniform(-0.04, 0.04),
        kappa_pi=base.kappa_pi + rng.uniform(-0.03, 0.03),
        beta_r=base.beta_r + rng.uniform(-0.04, 0.04),
        phi_taylor=base.phi_taylor + rng.uniform(-0.05, 0.05),
        r_star=base.r_star,
        pi_star=base.pi_star,
        impulse_decay=base.impulse_decay,
        sigma_y=base.sigma_y * rng.uniform(0.85, 1.15),
        sigma_pi=base.sigma_pi * rng.uniform(0.85, 1.15),
        sigma_idx=base.sigma_idx * rng.uniform(0.85, 1.15),
    )


def simulate_macro_path(
    *,
    seed: str,
    events: list[Any],
    horizon: int,
    start_state: MacroState | None = None,
    start_step: int = 0,
    params: MacroParams | None = None,
    collect_audit: bool = True,
    path_tag: str = "base",
    genre: str = "modern",
    institutions: list[dict[str, Any]] | None = None,
    institution_context_kwargs: dict[str, Any] | None = None,
    history_rows: list[dict[str, Any]] | None = None,
    use_longrun_fusion: bool = True,
    fusion_mode: str = "global",
) -> dict[str, Any]:
    """Forward macro path for ``horizon`` steps from ``start_state``.

    Fusion strategy is selected from ``finance_fusion_config`` using ``genre``
    and ``fusion_mode`` (global / city / corporate / retail).
    """
    from .finance_fusion_config import get_fusion_strategy
    from .finance_institution_dynamics import (
        build_institution_context,
        evolve_institutions_step,
        _events_at_step,
    )
    from .finance_longrun import estimate_params_at_step, fuse_macro_step, _step_has_war

    params = params or MacroParams()
    strategy = get_fusion_strategy(genre, fusion_mode)
    fusion_enabled = use_longrun_fusion and strategy.enabled
    rng = random.Random(_seed_int(seed, path_tag, str(horizon), str(len(events))))
    state = start_state or MacroState()
    impulses = Impulses()
    forecast: list[dict[str, Any]] = []
    audit_trail: list[dict[str, Any]] = []
    event_log: list[dict[str, Any]] = []
    fusion_log: list[dict[str, Any]] = []
    ctx_kwargs = dict(institution_context_kwargs or {})
    baseline_pop = ctx_kwargs.get("baseline_population")
    accumulated: list[dict[str, Any]] = list(history_rows or [])

    for i in range(horizon):
        step = start_step + i
        step_events = _events_at_step(events, step)
        if institutions is not None:
            ctx = build_institution_context(
                step=step,
                genre=genre,
                macro_state=state,
                events_at_step=step_events,
                baseline_population=baseline_pop,
                **{k: v for k, v in ctx_kwargs.items() if k != "baseline_population"},
            )
            inst_delta = evolve_institutions_step(institutions, ctx, step_events)

        attrs = apply_events_to_impulses(
            events, step, impulses, genre=genre, institutions=institutions,
        )
        if attrs:
            event_log.extend(attrs)

        markov_state, audit = macro_step(state, impulses, params, rng, step=step, forecast=True, genre=genre)
        state = markov_state

        if fusion_enabled and len(accumulated) >= strategy.min_history:
            war_active = _step_has_war(step_events)
            longrun = estimate_params_at_step(
                accumulated,
                target_step=step,
                steps_ahead=1,
                params=params,
                genre=genre,
                strategy=strategy,
            )
            state, fusion_audit = fuse_macro_step(
                markov_state,
                longrun,
                history_len=len(accumulated),
                steps_ahead=i + 1,
                strategy=strategy,
                war_active=war_active,
            )
            audit["markov_outputs"] = dict(audit.get("outputs") or {})
            audit["outputs"] = {
                "index": state.index,
                "growth": state.growth_pct(),
                "risk": state.risk_score(),
                "inflation": state.inflation,
                "policy_rate": state.policy_rate,
                "liquidity": state.liquidity,
            }
            audit["fusion"] = fusion_audit
            audit["longrun_estimates"] = longrun
            fusion_log.append({"step": step, **fusion_audit})

        impulses.decay(params.impulse_decay)

        row = {
            "step": step,
            "index": state.index,
            "growth": state.growth_pct(),
            "risk": state.risk_score(),
            "inflation": state.inflation,
            "policy_rate": state.policy_rate,
            "liquidity": state.liquidity,
            "output_gap": round(state.output_gap, 4),
            "label": f"F+{i + 1}",
            "forecast": True,
        }
        forecast.append(row)
        accumulated.append(row)
        if collect_audit:
            audit["events"] = attrs
            if institutions is not None:
                audit["institutions"] = inst_delta
                audit["context"] = {
                    "population_norm": ctx.population_norm,
                    "agriculture_index": ctx.agriculture_index,
                    "industry_index": ctx.industry_index,
                    "enterprise_revenue_index": ctx.enterprise_revenue_index,
                    "event_pressure": ctx.event_pressure,
                }
            audit_trail.append(audit)

    return {
        "forecast": forecast,
        "audit_trail": audit_trail,
        "event_log": event_log,
        "terminal_state": state,
        "institutions": institutions,
        "fusion_log": fusion_log,
        "longrun_fusion": fusion_enabled and len(history_rows or []) >= strategy.min_history,
        "fusion_strategy": strategy.as_dict(),
    }


def simulate_macro_ensemble(
    *,
    seed: str,
    events: list[Any],
    horizon: int,
    start_state: MacroState | None = None,
    start_step: int = 0,
    n_paths: int = 48,
    params: MacroParams | None = None,
    genre: str = "modern",
    institutions: list[dict[str, Any]] | None = None,
    institution_context_kwargs: dict[str, Any] | None = None,
    history_rows: list[dict[str, Any]] | None = None,
    fusion_mode: str = "global",
) -> dict[str, Any]:
    """Monte Carlo fan: baseline + p10/p50/p90 index bands."""
    params = params or MacroParams()
    n_paths = max(8, min(80, int(n_paths)))

    baseline = simulate_macro_path(
        seed=seed, events=events, horizon=horizon,
        start_state=start_state, start_step=start_step,
        params=params, path_tag="baseline", collect_audit=True, genre=genre,
        institutions=institutions,
        institution_context_kwargs=institution_context_kwargs,
        history_rows=history_rows,
        use_longrun_fusion=True,
        fusion_mode=fusion_mode,
    )

    rng = random.Random(_seed_int(seed, "ensemble", str(n_paths)))
    paths: list[list[float]] = []
    for p in range(n_paths):
        pparams = _perturb_params(params, rng)
        prng_seed = f"{seed}:mc:{p}"
        single = simulate_macro_path(
            seed=prng_seed, events=events, horizon=horizon,
            start_state=start_state, start_step=start_step,
            params=pparams, path_tag=f"mc{p}", collect_audit=False, genre=genre,
            institutions=institutions,
            institution_context_kwargs=institution_context_kwargs,
            history_rows=history_rows,
            use_longrun_fusion=True,
            fusion_mode=fusion_mode,
        )
        idx = [r["index"] for r in single["forecast"]]
        if len(idx) == horizon:
            paths.append(idx)

    bands: list[dict[str, Any]] = []
    if paths:
        for t in range(horizon):
            col = sorted(path[t] for path in paths)
            n = len(col)
            bands.append({
                "step": baseline["forecast"][t]["step"] if t < len(baseline["forecast"]) else t,
                "p10": round(col[max(0, int(n * 0.10))], 3),
                "p50": round(col[int(n * 0.50)], 3),
                "p90": round(col[min(n - 1, int(n * 0.90))], 3),
            })

    vol = _path_vol(baseline["forecast"])
    return {
        **baseline,
        "confidence_bands": bands,
        "methodology": METHODOLOGY,
        "n_paths": n_paths,
        "implied_vol_pct": round(vol * 100, 3),
    }


def _path_vol(rows: list[dict[str, Any]]) -> float:
    if len(rows) < 2:
        return 0.01
    rets = [rows[i]["index"] / rows[i - 1]["index"] - 1.0 for i in range(1, len(rows))]
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((x - mean) ** 2 for x in rets) / len(rets))


def bootstrap_macro_history(
    *,
    seed: str,
    events: list[Any],
    n_steps: int = 48,
    params: MacroParams | None = None,
    genre: str = "modern",
) -> tuple[list[dict[str, Any]], MacroState]:
    """Generate consistent history ending at T+{n_steps-1}."""
    params = params or MacroParams()
    rng = random.Random(_seed_int(seed, "hist", str(n_steps)))
    state = MacroState(index=100.0, inflation=params.pi_star, policy_rate=params.r_star)
    impulses = Impulses()
    history: list[dict[str, Any]] = []
    for step in range(n_steps):
        apply_events_to_impulses(events, step, impulses, genre=genre)
        state, _ = macro_step(state, impulses, params, rng, step=step, forecast=False, genre=genre)
        impulses.decay(params.impulse_decay)
        history.append({
            "step": step,
            "index": state.index,
            "growth": state.growth_pct(),
            "risk": state.risk_score(),
            "inflation": state.inflation,
            "policy_rate": state.policy_rate,
            "liquidity": state.liquidity,
            "output_gap": round(state.output_gap, 4),
            "label": f"T+{step}",
        })
    return history, state


# ---------- City / Corporate adapters ----------

def city_from_macro(row: dict[str, Any], *, scale: float = 1.0) -> dict[str, Any]:
    """Map macro state row → city desk indicators."""
    og = float(row.get("output_gap") or 0.0) * scale
    liq = float(row.get("liquidity") or 0.55)
    employment = _clamp(0.72 + og * 1.8, 0.35, 0.96)
    city_idx = float(row.get("index") or 100.0)
    prop_idx = city_idx * (0.95 + 0.12 * (liq - 0.5))
    return {
        "step": row["step"],
        "city_index": round(city_idx, 3),
        "property_index": round(prop_idx, 3),
        "employment": round(employment, 3),
        "liquidity": round(liq, 3),
        "output_gap": round(og, 4),
        "label": row.get("label", ""),
        "forecast": row.get("forecast", False),
    }


_SECTOR_BETA: dict[str, float] = {
    "贸易": 1.05, "航运": 1.15, "科技": 1.35, "金融": 1.10,
    "制造": 1.20, "消费": 0.85, "能源": 1.25, "公用": 0.65,
    "工商": 1.0, "default": 1.0,
}


def corporate_step_from_macro(
    *,
    price: float,
    macro_row: dict[str, Any],
    prev_macro_row: dict[str, Any] | None,
    sector: str,
    idio_shock: float,
    rng: random.Random,
) -> float:
    """Single-period equity price from macro factor + idiosyncratic shock."""
    beta = _SECTOR_BETA.get(sector) or _SECTOR_BETA["default"]
    if prev_macro_row:
        mkt_ret = macro_row["index"] / prev_macro_row["index"] - 1.0
    else:
        mkt_ret = 0.0
    ret = beta * mkt_ret + idio_shock + rng.gauss(0, 0.008)
    return max(1.0, price * (1.0 + ret))


def retail_regime_from_vol(implied_vol_pct: float) -> dict[str, float]:
    """Adjust GBM sleeve params from macro-implied vol (regime-aware quant)."""
    vol = max(0.004, implied_vol_pct / 100.0)
    return {
        "conservative": {"mu": 0.00020, "sigma": vol * 0.55},
        "balanced": {"mu": 0.00040, "sigma": vol * 0.85},
        "aggressive": {"mu": 0.00065, "sigma": vol * 1.25},
    }
