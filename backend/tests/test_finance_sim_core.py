"""Tests for structured macro finance core."""
from app.layer2_civilization.finance_sim_core import (
    Impulses,
    apply_events_to_impulses,
    bootstrap_macro_history,
    simulate_macro_ensemble,
    simulate_macro_path,
)


def _ev(step: int, kind: str, mag: float, title: str = "test"):
    return {"at_step": step, "kind": kind, "title": title, "magnitude": mag}


def test_deterministic_replay():
    events = [_ev(4, "rate", -0.3, "加息")]
    a = simulate_macro_path(seed="t1", events=events, horizon=12, path_tag="a")
    b = simulate_macro_path(seed="t1", events=events, horizon=12, path_tag="a")
    assert a["forecast"] == b["forecast"]


def test_event_transmission_changes_path():
    base = simulate_macro_path(seed="t2", events=[], horizon=12, path_tag="x")
    shocked = simulate_macro_path(seed="t2", events=[_ev(2, "war", -0.4)], horizon=12, path_tag="x")
    assert base["forecast"][-1]["index"] != shocked["forecast"][-1]["index"]


def test_audit_trail_has_equations():
    sim = simulate_macro_path(
        seed="t3", events=[_ev(1, "policy", 0.2)], horizon=6, collect_audit=True,
    )
    assert sim["audit_trail"]
    assert "equations" in sim["audit_trail"][0]


def test_monte_carlo_bands_ordered():
    sim = simulate_macro_ensemble(seed="t4", events=[], horizon=10, n_paths=24)
    bands = sim["confidence_bands"]
    assert len(bands) == 10
    for b in bands:
        assert b["p10"] <= b["p50"] <= b["p90"]


def test_impulse_attribution():
    impulses = Impulses()
    attrs = apply_events_to_impulses([_ev(0, "rate", 0.5)], 0, impulses)
    assert attrs[0]["channels"]["policy_rate"] > 0
    assert "货币政策" in attrs[0]["rationale"]


def test_bootstrap_history_length():
    hist, terminal = bootstrap_macro_history(seed="t5", events=[], n_steps=48)
    assert len(hist) == 48
    assert terminal.index > 0
