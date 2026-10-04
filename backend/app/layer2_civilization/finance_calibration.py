"""Calibrate MacroParams (ρ, κ, β) from reference macro series via MLE.

Uses genre-specific stylized quarterly proxies aligned with each civilization era.
Not live market data — reproducible reference panels for sandbox consistency.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .finance_sim_core import MacroParams

# Quarterly proxies: output_gap (%/100), inflation (%), policy_rate (%)
# Sources stylized from public macro patterns (OECD/World Bank shapes, scaled).
_REFERENCE: dict[str, dict[str, list[float]]] = {
    "modern": {
        "output_gap": [-0.02, -0.01, 0.0, 0.01, 0.02, 0.015, 0.01, -0.005, -0.02, -0.03, -0.015, 0.0,
                       0.01, 0.02, 0.025, 0.02, 0.015, 0.01, 0.005, 0.0, -0.01, -0.02, -0.015, -0.01],
        "inflation": [1.8, 2.0, 2.1, 2.3, 2.5, 2.4, 2.2, 2.0, 1.5, 1.2, 1.0, 1.5, 2.0, 2.5, 3.0, 3.2,
                      3.0, 2.8, 2.5, 2.3, 2.0, 1.8, 1.6, 1.9],
        "policy_rate": [2.5, 2.5, 2.75, 3.0, 3.25, 3.5, 3.5, 3.25, 2.5, 1.75, 1.0, 0.5, 0.25, 0.5,
                        1.0, 1.5, 2.0, 2.5, 3.0, 3.25, 3.5, 3.25, 3.0, 2.75],
    },
    "ancient": {
        "output_gap": [0.01, 0.02, 0.015, 0.0, -0.01, -0.02, -0.03, -0.02, 0.0, 0.01, 0.02, 0.01,
                       0.0, -0.01, -0.015, -0.02, -0.025, -0.02, -0.01, 0.0, 0.005, 0.01, 0.015, 0.01],
        "inflation": [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0, 4.0, 3.0, 2.0, 1.5, 1.0, 0.8, 1.0,
                      1.5, 2.0, 2.5, 2.0, 1.5, 1.0, 0.8, 0.6],
        "policy_rate": [3.0, 3.0, 3.0, 3.5, 4.0, 4.5, 5.0, 5.0, 4.5, 4.0, 3.5, 3.0, 3.0, 3.5, 4.0,
                        4.5, 5.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0, 3.0],
    },
    "wuxia": {
        "output_gap": [0.0, 0.01, 0.015, 0.01, 0.0, -0.01, -0.02, -0.015, -0.01, 0.0, 0.01, 0.02,
                       0.015, 0.01, 0.0, -0.005, -0.01, -0.015, -0.01, 0.0, 0.005, 0.01, 0.015, 0.01],
        "inflation": [1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 2.5, 2.0, 1.5, 1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5,
                      3.0, 2.8, 2.5, 2.0, 1.8, 1.5, 1.2, 1.0],
        "policy_rate": [4.0, 4.0, 4.5, 5.0, 5.5, 6.0, 5.5, 5.0, 4.5, 4.0, 4.0, 4.5, 5.0, 5.5, 6.0,
                        5.5, 5.0, 4.5, 4.0, 4.0, 4.5, 5.0, 4.5, 4.0],
    },
    "scifi": {
        "output_gap": [0.02, 0.025, 0.03, 0.025, 0.02, 0.015, 0.01, 0.005, 0.0, -0.005, 0.0, 0.01,
                       0.015, 0.02, 0.025, 0.02, 0.015, 0.01, 0.005, 0.0, 0.005, 0.01, 0.015, 0.02],
        "inflation": [2.0, 2.2, 2.5, 2.8, 3.0, 3.2, 3.0, 2.8, 2.5, 2.2, 2.0, 2.1, 2.3, 2.5, 2.8, 3.0,
                      3.2, 3.0, 2.8, 2.5, 2.3, 2.1, 2.0, 2.1],
        "policy_rate": [1.5, 1.5, 1.75, 2.0, 2.25, 2.5, 2.5, 2.25, 2.0, 1.75, 1.5, 1.5, 1.75, 2.0,
                        2.25, 2.5, 2.75, 3.0, 2.75, 2.5, 2.25, 2.0, 1.75, 1.5],
    },
    "mystery": {
        "output_gap": [-0.03, -0.04, -0.05, -0.04, -0.03, -0.02, -0.01, 0.0, 0.005, 0.0, -0.01, -0.02,
                       -0.03, -0.035, -0.04, -0.03, -0.02, -0.01, 0.0, 0.005, 0.0, -0.005, -0.01, -0.015],
        "inflation": [0.5, 0.0, -0.5, -1.0, -1.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 1.5,
                      1.0, 0.5, 0.0, -0.5, 0.0, 0.5, 1.0, 0.5, 0.0],
        "policy_rate": [5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.75, 0.5, 0.5, 0.75, 1.0, 1.25,
                        1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5],
    },
    "xuanhuan": {
        "output_gap": [0.01, 0.015, 0.02, 0.015, 0.01, 0.005, 0.0, -0.005, 0.0, 0.005, 0.01, 0.015,
                       0.02, 0.015, 0.01, 0.005, 0.0, -0.005, -0.01, -0.005, 0.0, 0.005, 0.01, 0.015],
        "inflation": [1.5, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.8, 1.5, 1.8, 2.0, 2.5,
                      3.0, 2.8, 2.5, 2.0, 1.8, 1.5, 1.2, 1.0],
        "policy_rate": [3.5, 3.5, 4.0, 4.5, 5.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.5, 4.0, 4.5, 5.0, 5.5,
                        5.0, 4.5, 4.0, 3.5, 3.5, 4.0, 4.5, 4.0, 3.5],
    },
    "enterprise": {
        "output_gap": [0.02, 0.025, 0.03, 0.025, 0.02, 0.015, 0.01, 0.005, 0.0, -0.01, -0.02, -0.015,
                       -0.01, 0.0, 0.01, 0.015, 0.02, 0.015, 0.01, 0.005, 0.0, -0.005, -0.01, -0.005],
        "inflation": [2.0, 2.2, 2.5, 2.8, 3.0, 2.8, 2.5, 2.2, 2.0, 1.8, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8,
                      3.0, 2.8, 2.5, 2.2, 2.0, 1.8, 1.6, 1.8],
        "policy_rate": [2.0, 2.0, 2.25, 2.5, 2.75, 3.0, 3.0, 2.75, 2.5, 2.0, 1.5, 1.0, 0.75, 1.0, 1.5,
                        2.0, 2.5, 3.0, 3.25, 3.5, 3.25, 3.0, 2.75, 2.5],
    },
    "securities": {
        "output_gap": [0.01, 0.015, 0.02, 0.015, 0.01, 0.0, -0.005, -0.01, -0.015, -0.01, -0.005, 0.0,
                       0.005, 0.01, 0.015, 0.02, 0.015, 0.01, 0.005, 0.0, -0.005, -0.01, -0.005, 0.0],
        "inflation": [1.5, 1.8, 2.0, 2.2, 2.5, 2.3, 2.0, 1.8, 1.5, 1.2, 1.0, 1.2, 1.5, 1.8, 2.0, 2.2,
                      2.5, 2.3, 2.0, 1.8, 1.5, 1.3, 1.2, 1.4],
        "policy_rate": [2.5, 2.5, 2.75, 3.0, 3.25, 3.5, 3.25, 3.0, 2.75, 2.5, 2.25, 2.0, 2.25, 2.5,
                        2.75, 3.0, 3.25, 3.0, 2.75, 2.5, 2.25, 2.0, 2.25, 2.5],
    },
    "military": {
        "output_gap": [0.0, 0.005, 0.01, 0.015, 0.02, 0.015, 0.01, 0.005, 0.0, -0.005, -0.01, -0.015,
                       -0.02, -0.015, -0.01, -0.005, 0.0, 0.005, 0.01, 0.015, 0.02, 0.015, 0.01, 0.005],
        "inflation": [2.0, 2.2, 2.5, 2.8, 3.0, 3.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.8, 2.0, 2.5, 3.0, 3.5,
                      4.0, 3.5, 3.0, 2.5, 2.0, 1.8, 1.6, 1.8],
        "policy_rate": [2.0, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.25, 3.0, 2.75, 2.5, 2.5, 2.75,
                        3.0, 3.25, 3.5, 3.25, 3.0, 2.75, 2.5, 2.25, 2.0, 2.0],
    },
}


def _ar1_mle(series: list[float]) -> tuple[float, float]:
    """MLE for AR(1): x_t = rho * x_{t-1} + eps. Returns (rho, sigma)."""
    if len(series) < 3:
        return 0.78, 0.01
    x = series[:-1]
    y = series[1:]
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den = sum((xi - mx) ** 2 for xi in x) or 1e-9
    rho = max(-0.5, min(0.98, num / den))
    resid = [yi - rho * xi for xi, yi in zip(x, y)]
    sigma = math.sqrt(sum(r * r for r in resid) / len(resid)) if resid else 0.01
    return rho, max(1e-4, sigma)


def _phillips_kappa(y: list[float], pi: list[float]) -> float:
    """OLS slope: Δπ ≈ κ · y_{t-1}."""
    if len(y) < 3 or len(pi) < 3:
        return 0.22
    dpi = [pi[i] - pi[i - 1] for i in range(1, len(pi))]
    ylag = y[:-1]
    n = min(len(dpi), len(ylag))
    if n < 2:
        return 0.22
    num = sum(dpi[i] * ylag[i] for i in range(n))
    den = sum(ylag[i] ** 2 for i in range(n)) or 1e-9
    return max(0.05, min(0.45, num / den))


def _is_beta(y: list[float], r: list[float], pi: list[float], r_star: float = 2.5) -> float:
    """OLS: y_t ≈ -β · (real_rate - r*)."""
    if len(y) < 3:
        return 0.35
    real = [r[i] - pi[i] for i in range(len(y))]
    neutral = r_star - pi[0]
    spread = [real[i] - neutral for i in range(len(y))]
    num = sum(-y[i] * spread[i] for i in range(len(y)))
    den = sum(spread[i] ** 2 for i in range(len(y))) or 1e-9
    return max(0.1, min(0.6, num / den))


@dataclass
class CalibrationResult:
    params: MacroParams
    genre: str
    method: str
    diagnostics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        p = self.params
        return {
            "genre": self.genre,
            "method": self.method,
            "rho_y": round(p.rho_y, 4),
            "kappa_pi": round(p.kappa_pi, 4),
            "beta_r": round(p.beta_r, 4),
            "phi_taylor": round(p.phi_taylor, 4),
            "r_star": round(p.r_star, 3),
            "pi_star": round(p.pi_star, 3),
            "diagnostics": self.diagnostics,
        }


def calibrate_macro_params(genre: str, gdp_index: float | None = None) -> CalibrationResult:
    """MLE / OLS calibration from reference panel for genre."""
    ref = _REFERENCE.get(genre) or _REFERENCE["modern"]
    y = list(ref["output_gap"])
    pi = list(ref["inflation"])
    r = list(ref["policy_rate"])

    rho_y, sigma_y = _ar1_mle(y)
    kappa = _phillips_kappa(y, pi)
    r_star = sum(r) / len(r)
    pi_star = sum(pi) / len(pi)
    beta = _is_beta(y, r, pi, r_star=r_star - pi_star)

    # Bayesian shrinkage toward defaults (pseudo-prior weight 0.25)
    prior = MacroParams()
    w = 0.75
    params = MacroParams(
        rho_y=w * rho_y + (1 - w) * prior.rho_y,
        kappa_pi=w * kappa + (1 - w) * prior.kappa_pi,
        beta_r=w * beta + (1 - w) * prior.beta_r,
        r_star=r_star,
        pi_star=pi_star,
        sigma_y=w * sigma_y + (1 - w) * prior.sigma_y,
        sigma_pi=prior.sigma_pi,
        sigma_idx=prior.sigma_idx,
    )

    if gdp_index is not None and gdp_index > 0:
        scale = gdp_index / 100.0
        params.sigma_y *= max(0.85, min(1.15, scale))

    return CalibrationResult(
        params=params,
        genre=genre,
        method="mle_ols_bayesian_shrink",
        diagnostics={
            "n_obs": len(y),
            "raw_rho": round(rho_y, 4),
            "raw_kappa": round(kappa, 4),
            "raw_beta": round(beta, 4),
            "reference": "genre_stylized_quarterly_panel",
        },
    )


def macro_state_from_market(
    *,
    price_index: float,
    inflation: float,
    gini: float,
    velocity: float,
    money_supply: float,
) -> dict[str, float]:
    """Micro → macro closure: map MarketState aggregates to macro initial conditions."""
    og = _clamp((price_index / 100.0 - 1.0) * 0.85, -0.12, 0.10)
    risk = _clamp(0.22 + gini * 0.45 + max(0, inflation) * 0.02, 0.05, 0.92)
    liq = _clamp(0.35 + velocity * 0.15 + min(1.0, money_supply / 5000.0) * 0.2, 0.08, 0.92)
    return {
        "output_gap": og,
        "inflation": inflation if abs(inflation) < 20 else inflation / 12.0,
        "risk_premium": risk,
        "liquidity": liq,
        "index": price_index,
    }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
