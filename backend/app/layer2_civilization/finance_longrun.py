"""Long-range history parameter estimation and step-level fusion.

Each forecast step N:
1. Short-term: Markov递推 from state_{N-1} (macro_step)
2. Long-range: per-parameter estimate at step N from full history window
3. Fusion: blend short + long estimates → corrected state_N

Strategy is selected from finance_fusion_config (genre × mode).
"""
from __future__ import annotations

import math
from typing import Any

from .finance_fusion_config import FusionStrategy, get_fusion_strategy
from .finance_sim_core import MacroParams, MacroState, _clamp


_PARAM_SPECS: list[tuple[str, str, str]] = [
    ("output_gap", "output_gap", "ar1_mean_revert"),
    ("inflation", "inflation", "ar1_mean_revert"),
    ("policy_rate", "policy_rate", "ewma"),
    ("risk", "risk_premium", "ewma"),
    ("liquidity", "liquidity", "ewma"),
    ("index", "index", "log_trend"),
]


def _series(history: list[dict[str, Any]], key: str, window: int) -> list[float]:
    rows = history[-window:] if window > 0 else history
    out: list[float] = []
    for row in rows:
        v = row.get(key)
        if isinstance(v, (int, float)) and not math.isnan(float(v)):
            out.append(float(v))
    return out


def _ar1_rho(series: list[float], mle_rho: float | None = None) -> float:
    if mle_rho is not None:
        return _clamp(mle_rho, 0.05, 0.98)
    if len(series) < 3:
        return 0.78
    x, y = series[:-1], series[1:]
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den = sum((xi - mx) ** 2 for xi in x) or 1e-9
    return _clamp(num / den, 0.05, 0.98)


def _ar1_forecast(
    series: list[float],
    steps_ahead: int,
    *,
    target: float | None = None,
    mle_rho: float | None = None,
) -> float:
    if not series:
        return target or 0.0
    if len(series) == 1:
        return series[0]
    rho = _ar1_rho(series, mle_rho)
    mu = sum(series) / len(series)
    last = series[-1]
    tgt = mu if target is None else target
    h = max(1, steps_ahead)
    return tgt + (rho ** h) * (last - tgt)


def _ewma_forecast(series: list[float], steps_ahead: int, alpha: float = 0.12) -> float:
    if not series:
        return 0.0
    level = series[0]
    trend = 0.0
    for v in series[1:]:
        prev = level
        level = alpha * v + (1 - alpha) * level
        trend = 0.3 * (level - prev) + 0.7 * trend
    return level + trend * max(1, steps_ahead)


def _log_trend_forecast(series: list[float], steps_ahead: int) -> float:
    if len(series) < 2:
        return series[-1] if series else 100.0
    logs = [math.log(max(1e-6, v)) for v in series]
    n = len(logs)
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(logs) / n
    num = sum((xs[i] - mx) * (logs[i] - my) for i in range(n))
    den = sum((x - mx) ** 2 for x in xs) or 1e-9
    slope = num / den
    intercept = my - slope * mx
    log_f = intercept + slope * (n - 1 + max(1, steps_ahead))
    return max(10.0, math.exp(log_f))


def _reference_anchor(genre: str, state_key: str, step: int) -> float | None:
    from .finance_calibration import _REFERENCE

    ref = _REFERENCE.get(genre) or _REFERENCE.get("modern")
    if not ref:
        return None
    if state_key == "output_gap":
        series = ref.get("output_gap") or []
    elif state_key == "inflation":
        series = ref.get("inflation") or []
    elif state_key == "policy_rate":
        series = ref.get("policy_rate") or []
    else:
        return None
    if not series:
        return None
    return float(series[step % len(series)])


def _risk_score_to_premium(risk_score: float) -> float:
    return _clamp((risk_score - 0.25) / 0.55, 0.05, 0.95)


def estimate_params_at_step(
    history: list[dict[str, Any]],
    *,
    target_step: int,
    steps_ahead: int,
    params: MacroParams,
    genre: str = "modern",
    strategy: FusionStrategy | None = None,
) -> dict[str, dict[str, Any]]:
    """Per-parameter long-range estimate for ``target_step``."""
    strat = strategy or get_fusion_strategy(genre, "global")
    estimates: dict[str, dict[str, Any]] = {}
    conf = min(1.0, len(history) / max(8, strat.history_window))
    mle_rho = params.rho_y if strat.use_mle_rho else None

    for hist_key, state_key, method in _PARAM_SPECS:
        series = _series(history, hist_key, strat.history_window)
        if not series:
            continue
        if method == "ar1_mean_revert":
            tgt = params.pi_star if state_key == "inflation" else 0.0
            val = _ar1_forecast(series, steps_ahead, target=tgt, mle_rho=mle_rho)
        elif method == "ewma":
            val = _ewma_forecast(series, steps_ahead, alpha=strat.ewma_alpha)
            if state_key == "risk_premium":
                val = _risk_score_to_premium(val)
        else:
            val = _log_trend_forecast(series, steps_ahead)

        if strat.use_reference_anchor and state_key in ("output_gap", "inflation", "policy_rate"):
            ref_v = _reference_anchor(genre, state_key, target_step)
            if ref_v is not None:
                val = (1 - strat.reference_blend) * val + strat.reference_blend * ref_v

        if state_key == "output_gap":
            val = _clamp(val, -0.12, 0.10)
        elif state_key == "inflation":
            val = _clamp(val, -1.0, 12.0)
        elif state_key == "policy_rate":
            val = _clamp(val, 0.0, 12.0)
        elif state_key == "risk_premium":
            val = _clamp(val, 0.05, 0.95)
        elif state_key == "liquidity":
            val = _clamp(val, 0.08, 0.92)
        elif state_key == "index":
            val = max(10.0, val)

        estimates[state_key] = {
            "value": round(val, 4),
            "method": method,
            "history_len": len(series),
            "confidence": round(conf, 3),
            "target_step": target_step,
            "mle_rho": round(mle_rho, 4) if mle_rho is not None and method == "ar1_mean_revert" else None,
        }
    return estimates


def _fusion_weight(
    state_key: str,
    *,
    strategy: FusionStrategy,
    history_len: int,
    steps_ahead: int,
    war_active: bool,
) -> float:
    base = strategy.param_weights.get(state_key, 0.20) * strategy.weight_scale
    hist_boost = min(0.18, history_len / max(8, strategy.history_window) * 0.18)
    horizon_boost = min(0.10, steps_ahead * strategy.horizon_boost)
    w = base + hist_boost + horizon_boost
    if war_active:
        w *= strategy.war_regime_multiplier
    return min(strategy.max_weight, max(0.0, w))


def _step_has_war(events: list[Any]) -> bool:
    for raw in events:
        if isinstance(raw, dict):
            ev = raw
        elif hasattr(raw, "as_dict"):
            ev = raw.as_dict()
        elif hasattr(raw, "kind"):
            ev = {"kind": raw.kind, "magnitude": getattr(raw, "magnitude", 0)}
        else:
            continue
        kind = str(ev.get("kind") or "")
        if kind in ("war", "plague", "earthquake"):
            return True
    return False


def fuse_macro_step(
    markov: MacroState,
    longrun: dict[str, dict[str, Any]],
    *,
    history_len: int,
    steps_ahead: int,
    strategy: FusionStrategy,
    war_active: bool = False,
) -> tuple[MacroState, dict[str, Any]]:
    """Blend Markov short-step state with long-range parameter estimates."""
    fused = MacroState(**markov.__dict__)
    corrections: dict[str, Any] = {}

    for state_key, est in longrun.items():
        if not hasattr(fused, state_key):
            continue
        markov_val = getattr(markov, state_key)
        long_val = float(est["value"])
        w = _fusion_weight(
            state_key,
            strategy=strategy,
            history_len=history_len,
            steps_ahead=steps_ahead,
            war_active=war_active,
        )
        if w <= 1e-6:
            continue

        if state_key == "index":
            blended = markov_val ** (1 - w) * long_val ** w
        else:
            blended = (1 - w) * markov_val + w * long_val

        blended = max(10.0, blended) if state_key == "index" else blended
        setattr(fused, state_key, round(blended, 4))
        delta = round(blended - markov_val, 4)
        if abs(delta) > 1e-5:
            corrections[state_key] = {
                "markov": round(markov_val, 4),
                "longrun": round(long_val, 4),
                "fused": round(blended, 4),
                "weight_longrun": round(w, 3),
                "method": est.get("method"),
                "delta": delta,
            }

    audit = {
        "engine": "longrun_fusion_v2",
        "strategy_label": strategy.label,
        "history_len": history_len,
        "steps_ahead": steps_ahead,
        "war_active": war_active,
        "corrections": corrections,
        "rationale": (
            f"策略「{strategy.label}」：各参数基于长程历史与 MLE ρ 预估，"
            f"与 Markov 递推加权融合（scale={strategy.weight_scale}）。"
            + (" 战争/灾害窗口：长程权重下调。" if war_active else "")
            if corrections else f"策略「{strategy.label}」：长程与短程一致，未触发校正。"
        ),
    }
    return fused, audit


def longrun_methodology_note(genre: str = "modern", mode: str = "global") -> str:
    s = get_fusion_strategy(genre, mode)
    return f"hybrid_markov_longrun_fusion_v2/{s.label}"
