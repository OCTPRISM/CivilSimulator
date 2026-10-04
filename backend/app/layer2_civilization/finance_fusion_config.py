"""Per-genre × per-mode long-run fusion strategy table (9 civilizations × 4 macro modes).

Modes:
  global    — full macro ensemble + fusion
  city      — macro layer mapped to city indicators
  corporate — macro factor for sector-beta equity path
  retail    — vol calibration only (fusion disabled)

Each strategy controls how Markov one-step states blend with long-history estimates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MACRO_MODES = ("global", "city", "corporate", "retail")
GENRES = (
    "ancient", "wuxia", "modern", "scifi", "mystery",
    "enterprise", "securities", "military", "xuanhuan",
)


@dataclass(frozen=True)
class FusionStrategy:
    enabled: bool = True
    min_history: int = 8
    history_window: int = 48
    weight_scale: float = 1.0
    use_mle_rho: bool = True
    use_reference_anchor: bool = False
    reference_blend: float = 0.20
    ewma_alpha: float = 0.12
    war_regime_multiplier: float = 0.50
    max_weight: float = 0.52
    horizon_boost: float = 0.008
    param_weights: dict[str, float] = field(default_factory=lambda: {
        "output_gap": 0.22,
        "inflation": 0.28,
        "policy_rate": 0.18,
        "risk_premium": 0.20,
        "liquidity": 0.16,
        "index": 0.24,
    })
    label: str = ""
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "min_history": self.min_history,
            "history_window": self.history_window,
            "weight_scale": self.weight_scale,
            "use_mle_rho": self.use_mle_rho,
            "use_reference_anchor": self.use_reference_anchor,
            "reference_blend": self.reference_blend,
            "ewma_alpha": self.ewma_alpha,
            "war_regime_multiplier": self.war_regime_multiplier,
            "max_weight": self.max_weight,
            "horizon_boost": self.horizon_boost,
            "param_weights": dict(self.param_weights),
            "label": self.label,
            "notes": self.notes,
        }


def _pw(**kwargs: float) -> dict[str, float]:
    base = {
        "output_gap": 0.22,
        "inflation": 0.28,
        "policy_rate": 0.18,
        "risk_premium": 0.20,
        "liquidity": 0.16,
        "index": 0.24,
    }
    base.update(kwargs)
    return base


def _retail_disabled(notes: str) -> FusionStrategy:
    return FusionStrategy(
        enabled=False,
        weight_scale=0.0,
        label="retail_vol_only",
        notes=notes,
    )


# ---------- genre base profiles (global-mode anchor) ----------
_GENRE_GLOBAL: dict[str, FusionStrategy] = {
    "ancient": FusionStrategy(
        weight_scale=1.18,
        use_mle_rho=True,
        use_reference_anchor=False,
        war_regime_multiplier=0.42,
        history_window=48,
        max_weight=0.50,
        param_weights=_pw(output_gap=0.26, inflation=0.32, index=0.22, policy_rate=0.16),
        label="ancient_slow_cycle",
        notes="唐古代：强均值回归、农政周期，战争时降低长程锚定。",
    ),
    "wuxia": FusionStrategy(
        weight_scale=1.12,
        use_mle_rho=True,
        war_regime_multiplier=0.48,
        history_window=48,
        param_weights=_pw(output_gap=0.24, inflation=0.28, risk_premium=0.24, index=0.22),
        label="wuxia_jianghu",
        notes="江湖：风险与流动性权重偏高，镖局/钱堂冲击短促。",
    ),
    "modern": FusionStrategy(
        weight_scale=0.92,
        use_mle_rho=True,
        ewma_alpha=0.15,
        history_window=36,
        max_weight=0.46,
        param_weights=_pw(inflation=0.24, index=0.28, risk_premium=0.22, liquidity=0.20),
        label="modern_financial",
        notes="当代都会：指数/风险 EWMA 权重较高，短窗 36 步。",
    ),
    "scifi": FusionStrategy(
        weight_scale=1.05,
        use_mle_rho=True,
        use_reference_anchor=True,
        reference_blend=0.28,
        history_window=48,
        param_weights=_pw(output_gap=0.22, inflation=0.26, index=0.26, liquidity=0.20),
        label="scifi_reference",
        notes="环带科幻：参考面板作长程锚，能源/信用点均衡路径。",
    ),
    "mystery": FusionStrategy(
        weight_scale=1.08,
        use_mle_rho=True,
        use_reference_anchor=True,
        reference_blend=0.32,
        history_window=48,
        max_weight=0.48,
        param_weights=_pw(output_gap=0.28, inflation=0.30, risk_premium=0.22, index=0.20),
        label="mystery_depression",
        notes="雾港1930s：大萧条形态参考面板权重高。",
    ),
    "enterprise": FusionStrategy(
        weight_scale=0.95,
        use_mle_rho=True,
        ewma_alpha=0.14,
        history_window=36,
        param_weights=_pw(output_gap=0.26, index=0.30, risk_premium=0.18, liquidity=0.18),
        label="enterprise_vc",
        notes="创业纪：景气与估值指数权重高，政策利率偏低。",
    ),
    "securities": FusionStrategy(
        weight_scale=0.88,
        use_mle_rho=True,
        ewma_alpha=0.16,
        history_window=32,
        max_weight=0.44,
        param_weights=_pw(index=0.32, risk_premium=0.26, liquidity=0.22, inflation=0.20),
        label="securities_market",
        notes="镜湖证券：短窗、高波动，指数/风险/流动性主导。",
    ),
    "military": FusionStrategy(
        weight_scale=0.82,
        use_mle_rho=True,
        war_regime_multiplier=0.32,
        history_window=40,
        param_weights=_pw(output_gap=0.20, risk_premium=0.28, inflation=0.24, index=0.18),
        label="military_regime",
        notes="边关军工：战争事件时大幅削弱长程（结构突变）。",
    ),
    "xuanhuan": FusionStrategy(
        weight_scale=1.02,
        use_mle_rho=True,
        use_reference_anchor=True,
        reference_blend=0.22,
        history_window=48,
        param_weights=_pw(inflation=0.26, liquidity=0.24, index=0.26, output_gap=0.20),
        label="xuanhuan_spirit",
        notes="修真：灵石/丹药供给冲击，流动性与指数并重。",
    ),
}

# ---------- mode adjustments relative to global ----------
_MODE_ADJ: dict[str, dict[str, Any]] = {
    "global": {
        "label_suffix": "",
        "weight_scale_mult": 1.0,
        "enabled": True,
    },
    "city": {
        "label_suffix": "_city",
        "weight_scale_mult": 0.94,
        "history_window_delta": 0,
        "notes_suffix": " 城市层继承 macro 融合后映射。",
        "param_weights_mult": {"employment_proxy": 1.0},  # unused; macro keys unchanged
    },
    "corporate": {
        "label_suffix": "_corporate",
        "weight_scale_mult": 0.62,
        "max_weight_cap": 0.38,
        "notes_suffix": " 企业模式：macro 因子层轻融合，股价由 β 模型主导。",
    },
    "retail": {
        "enabled": False,
        "weight_scale_mult": 0.0,
        "label_suffix": "_retail",
        "notes_suffix": " 量化模式：仅用 macro 路径校准 GBM 波动率，不做逐步融合。",
    },
}


def _apply_mode(base: FusionStrategy, mode: str) -> FusionStrategy:
    if mode == "retail":
        return _retail_disabled(base.notes + _MODE_ADJ["retail"]["notes_suffix"])

    adj = _MODE_ADJ[mode]
    ws = round(base.weight_scale * adj.get("weight_scale_mult", 1.0), 4)
    mw = min(base.max_weight, adj.get("max_weight_cap", base.max_weight))
    hw = base.history_window + adj.get("history_window_delta", 0)

    pw = dict(base.param_weights)
    if mode == "corporate":
        pw["index"] = round(pw.get("index", 0.24) * 0.85, 4)
        pw["output_gap"] = round(pw.get("output_gap", 0.22) * 0.75, 4)

    return FusionStrategy(
        enabled=adj.get("enabled", True),
        min_history=base.min_history,
        history_window=hw,
        weight_scale=ws,
        use_mle_rho=base.use_mle_rho,
        use_reference_anchor=base.use_reference_anchor,
        reference_blend=base.reference_blend,
        ewma_alpha=base.ewma_alpha,
        war_regime_multiplier=base.war_regime_multiplier,
        max_weight=mw,
        horizon_boost=base.horizon_boost,
        param_weights=pw,
        label=(base.label + adj.get("label_suffix", "")),
        notes=(base.notes + adj.get("notes_suffix", "")),
    )


def _build_table() -> dict[str, dict[str, FusionStrategy]]:
    table: dict[str, dict[str, FusionStrategy]] = {}
    for genre in GENRES:
        base = _GENRE_GLOBAL.get(genre) or _GENRE_GLOBAL["modern"]
        table[genre] = {mode: _apply_mode(base, mode) for mode in MACRO_MODES}
    return table


FUSION_TABLE: dict[str, dict[str, FusionStrategy]] = _build_table()

_DEFAULT = FusionStrategy(label="default_modern")


def get_fusion_strategy(genre: str, mode: str = "global") -> FusionStrategy:
    g = FUSION_TABLE.get(genre) or FUSION_TABLE.get("modern", {})
    m = mode if mode in MACRO_MODES else "global"
    return g.get(m) or _apply_mode(_DEFAULT, m)


def fusion_table_summary() -> list[dict[str, Any]]:
    """Flat summary for docs / API."""
    rows: list[dict[str, Any]] = []
    for genre in GENRES:
        for mode in MACRO_MODES:
            s = get_fusion_strategy(genre, mode)
            rows.append({
                "genre": genre,
                "mode": mode,
                "enabled": s.enabled,
                "label": s.label,
                "weight_scale": s.weight_scale,
                "max_weight": s.max_weight,
                "use_reference_anchor": s.use_reference_anchor,
                "war_regime_multiplier": s.war_regime_multiplier,
                "notes": s.notes,
            })
    return rows
