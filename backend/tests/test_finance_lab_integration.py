"""Async integration tests for finance lab workspace API."""
from __future__ import annotations

import pytest

from app.layer2_civilization.finance_institutions import get_finance_institutions
from app.labs.workspace import create_or_get_lab, lab_add_manual_events, lab_finance_simulate


@pytest.mark.asyncio
async def test_ancient_global_simulate_full_pipeline():
    ws = create_or_get_lab(user_id="pytest-int", lab_key="finance", civilization_key="ancient")
    await lab_add_manual_events(
        ws,
        [{"time": "T+6", "title": "边关战事", "kind": "war", "magnitude": -0.3}],
        use_llm_ner=False,
    )
    out = await lab_finance_simulate(ws, mode="global", horizon=12, skip_llm=True)
    sim = out["simulation"]
    report = out["report"]

    inst_names = " ".join(i["name"] for i in get_finance_institutions("ancient"))
    assert "山西票号" not in inst_names
    assert "柜坊" in inst_names

    assert sim.get("fusion_strategy", {}).get("label") == "ancient_slow_cycle"
    assert sim.get("longrun_fusion") is True
    assert sim.get("audit_trail")
    assert sim["audit_trail"][0].get("fusion")

    assert report.get("conclusion")
    assert len(report.get("charts") or []) >= 5
    assert any(t.get("title") == "逐步推演数值表" for t in report.get("tables") or [])
    assert out.get("pdf_base64")


@pytest.mark.asyncio
async def test_all_genres_fusion_strategy_labels():
    from app.layer2_civilization.finance_fusion_config import GENRES, get_fusion_strategy

    for genre in GENRES:
        ws = create_or_get_lab(user_id=f"pytest-{genre}", lab_key="finance", civilization_key=genre)
        out = await lab_finance_simulate(ws, mode="global", horizon=8, skip_llm=True)
        sim = out["simulation"]
        expected = get_fusion_strategy(genre, "global").label
        assert sim.get("fusion_strategy", {}).get("label") == expected, genre


@pytest.mark.asyncio
async def test_corporate_inherits_macro_fusion():
    ws = create_or_get_lab(user_id="pytest-corp", lab_key="finance", civilization_key="modern")
    out = await lab_finance_simulate(ws, mode="corporate", horizon=10, skip_llm=True)
    sim = out["simulation"]
    assert sim.get("forecast")
    assert sim.get("fusion_strategy", {}).get("label", "").endswith("corporate")
