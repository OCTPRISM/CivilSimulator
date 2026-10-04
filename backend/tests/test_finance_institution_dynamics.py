"""Tests for dynamic financial institution evolution."""
from app.layer2_civilization.finance_institution_dynamics import (
    InstitutionContext,
    build_institution_context,
    evolve_institutions_step,
    initialize_dynamic_institutions,
    institution_modifiers_from_state,
)
from app.layer2_civilization.finance_sim_core import MacroState, simulate_macro_ensemble


def test_initialize_has_dynamic_fields():
    insts = initialize_dynamic_institutions("ancient", "ancient", {"gdp_index": 100, "urban_pop_pct": 0.2})
    assert len(insts) >= 3
    for i in insts:
        assert "influence" in i
        assert "health" in i
        assert "base_transmission" in i


def test_evolve_responds_to_war_event():
    insts = initialize_dynamic_institutions("ancient", "ancient", {})
    ctx = InstitutionContext(step=10, genre="ancient", risk=0.7, output_gap=-0.05)
    events = [{"kind": "war", "magnitude": -0.4, "at_step": 10}]
    before = insts[0]["influence"]
    evolve_institutions_step(insts, ctx, events)
    assert insts[0]["last_delta"]
    assert any(i["health"] != 0.85 for i in insts) or insts[0]["influence"] != before


def test_macro_sim_evolve_institutions():
    insts = initialize_dynamic_institutions("modern", "modern", {"total_pop": 1_000_000})
    ctx_kw = {
        "demographics": {"total_pop": 1_000_000, "gdp_index": 120},
        "baseline_population": 1_000_000,
        "market_snap": {"velocity": 0.15, "gini": 0.38, "goods": [
            {"id": "food", "base": 10, "price": 11, "inventory": 40},
            {"id": "energy", "base": 18, "price": 17, "inventory": 55},
        ]},
    }
    sim = simulate_macro_ensemble(
        seed="dyn-test",
        events=[{"at_step": 5, "kind": "policy", "magnitude": 0.3, "title": "补贴"}],
        horizon=8,
        start_state=MacroState(index=100),
        institutions=insts,
        institution_context_kwargs=ctx_kw,
        genre="modern",
    )
    assert sim["audit_trail"]
    assert sim["audit_trail"][0].get("institutions")
    assert sim["institutions"][0]["influence"] != 1.0 or sim["institutions"][0]["health"] != 0.85


def test_modifiers_from_state_differ_from_static():
    insts = initialize_dynamic_institutions("modern", "modern", {})
    insts[0]["transmission"]["rate"] = 1.4
    insts[0]["influence"] = 1.3
    mods = institution_modifiers_from_state(insts, "rate")
    assert mods.get("rate", 1.0) != 1.0
