"""Tests for finance report enrichment (charts, conclusion, tables)."""
from app.labs.report import build_report, enrich_finance_report
from app.layer2_civilization.finance_sim_core import bootstrap_macro_history, simulate_macro_ensemble


def _sample_sim(genre: str = "ancient"):
    hist, terminal = bootstrap_macro_history(seed="rep1", events=[], n_steps=48, genre=genre)
    return simulate_macro_ensemble(
        seed="rep1", events=[], horizon=12,
        start_state=terminal, start_step=48,
        history_rows=hist, genre=genre, fusion_mode="global",
    )


def test_enrich_adds_conclusion_and_charts():
    sim = _sample_sim()
    hist = sim.get("forecast") or []
    report = build_report(
        lab_key="finance",
        lab_name="金融实验室",
        civilization_name="九州",
        civilization_key="ancient",
        horizon=12,
        dimensions=["index"],
        series={"全局指数": hist},
        events=[],
        metrics_summary={"index": hist[-1]["index"] if hist else 0},
        analysis_sections=[],
    )
    report = enrich_finance_report(report, sim, mode="global", horizon=12)
    assert report.get("conclusion")
    assert any(a.get("heading") == "终结性结论" for a in report.get("analysis") or [])
    chart_types = {c.get("type") for c in report.get("charts") or []}
    assert "line" in chart_types
    assert "histogram" in chart_types or "scatter" in chart_types
    tables = report.get("tables") or []
    assert any(t.get("title") == "逐步推演数值表" for t in tables)


def test_pdf_bytes_non_empty():
    sim = _sample_sim()
    hist = sim.get("forecast") or []
    report = build_report(
        lab_key="finance",
        lab_name="金融",
        civilization_name="九州",
        civilization_key="ancient",
        horizon=12,
        dimensions=["index"],
        series={"全局指数": hist},
        events=[],
        metrics_summary={},
        analysis_sections=[],
    )
    report = enrich_finance_report(report, sim, mode="global", horizon=12)
    report["mode_label"] = "全局走势"
    from app.labs.report_pdf import build_pdf_bytes

    pdf = build_pdf_bytes(report)
    assert len(pdf) > 5000
