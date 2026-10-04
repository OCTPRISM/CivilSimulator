"""Tests for long-range history fusion in macro simulation."""
from app.layer2_civilization.finance_fusion_config import get_fusion_strategy
from app.layer2_civilization.finance_longrun import estimate_params_at_step
from app.layer2_civilization.finance_sim_core import (
    MacroParams,
    bootstrap_macro_history,
    simulate_macro_ensemble,
    simulate_macro_path,
)


def test_longrun_estimates_from_history():
    hist, _ = bootstrap_macro_history(seed="lr1", events=[], n_steps=48, genre="ancient")
    est = estimate_params_at_step(
        hist, target_step=48, steps_ahead=1, params=MacroParams(), genre="ancient",
    )
    assert "index" in est
    assert "inflation" in est
    assert est["index"]["history_len"] == 48


def test_fusion_differs_from_markov_only():
    hist, terminal = bootstrap_macro_history(seed="lr2", events=[], n_steps=48, genre="ancient")
    plain = simulate_macro_path(
        seed="lr2", events=[], horizon=12, start_state=terminal, start_step=48,
        history_rows=None, use_longrun_fusion=False, path_tag="plain",
    )
    fused = simulate_macro_path(
        seed="lr2", events=[], horizon=12, start_state=terminal, start_step=48,
        history_rows=hist, use_longrun_fusion=True, fusion_mode="global",
        genre="ancient", path_tag="plain",
    )
    assert fused.get("longrun_fusion") is True
    assert fused.get("fusion_log")
    assert fused.get("fusion_strategy", {}).get("label") == "ancient_slow_cycle"
    assert (
        any(f.get("corrections") for f in fused["fusion_log"])
        or plain["forecast"][-1]["index"] != fused["forecast"][-1]["index"]
    )


def test_fusion_audit_in_trail():
    hist, terminal = bootstrap_macro_history(seed="lr3", events=[], n_steps=48, genre="ancient")
    sim = simulate_macro_path(
        seed="lr3", events=[], horizon=6, start_state=terminal, start_step=48,
        history_rows=hist, collect_audit=True, genre="ancient", fusion_mode="global",
    )
    assert sim["audit_trail"][0].get("fusion")
    assert sim["audit_trail"][0].get("markov_outputs")
    assert "strategy_label" in sim["audit_trail"][0]["fusion"]


def test_retail_mode_disables_fusion():
    hist, terminal = bootstrap_macro_history(seed="lr4", events=[], n_steps=48, genre="modern")
    sim = simulate_macro_path(
        seed="lr4", events=[], horizon=12, start_state=terminal, start_step=48,
        history_rows=hist, genre="modern", fusion_mode="retail",
    )
    strat = get_fusion_strategy("modern", "retail")
    assert strat.enabled is False
    assert sim.get("longrun_fusion") is False
    assert not sim.get("fusion_log")


def test_ensemble_carries_fusion_strategy():
    hist, terminal = bootstrap_macro_history(seed="lr5", events=[], n_steps=48, genre="military")
    sim = simulate_macro_ensemble(
        seed="lr5", events=[], horizon=8, start_state=terminal, start_step=48,
        history_rows=hist, genre="military", fusion_mode="global",
    )
    assert sim.get("fusion_strategy")
    assert sim["fusion_strategy"]["label"] == "military_regime"
    assert len(sim.get("confidence_bands") or []) == 8
