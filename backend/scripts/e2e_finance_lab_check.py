#!/usr/bin/env python3
"""End-to-end finance lab smoke test — institutions, audit, bands, report."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Run from backend/: python scripts/e2e_finance_lab_check.py
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


async def main() -> int:
    from app.labs.workspace import create_or_get_lab, lab_add_manual_events, lab_finance_simulate

    user_id = "e2e-test-user"
    civs = [("ancient", "古代"), ("modern", "现代")]
    modes = ["global", "city", "corporate", "market"]
    results: list[dict[str, Any]] = []
    failures: list[str] = []

    for civ_key, civ_label in civs:
        ws = create_or_get_lab(user_id=user_id, lab_key="finance", civilization_key=civ_key)
        await lab_add_manual_events(
            ws,
            [
                {"time": "T+4", "title": "边关战事升级", "kind": "war", "magnitude": -0.35},
                {"time": "T+12", "title": "开仓平粜/产业补贴", "kind": "policy", "magnitude": 0.28},
            ],
            use_llm_ner=False,
        )
        inst_before = json.loads(json.dumps(ws.finance_lab.institutions))

        for mode in modes:
            label = f"{civ_label}/{mode}"
            try:
                out = await lab_finance_simulate(
                    ws,
                    mode=mode,
                    horizon=16,
                    skip_llm=True,
                    market_steps=20 if mode == "market" else None,
                )
                sim = out.get("simulation") or {}
                report = out.get("report") or {}
                inst_after = out.get("finance_lab", {}).get("institutions") or sim.get("institutions") or []

                check = _validate_run(label, sim, report, inst_before, inst_after)
                check["has_pdf"] = bool(out.get("pdf_base64"))
                if mode == "global" and not out.get("pdf_base64"):
                    check["ok"] = False
                    check["errors"].append("missing pdf_base64")
                results.append(check)
                if not check["ok"]:
                    failures.extend(check["errors"])
            except Exception as e:
                failures.append(f"{label}: {type(e).__name__}: {e}")
                results.append({"label": label, "ok": False, "errors": [str(e)]})

    _print_report(results, failures)
    return 1 if failures else 0


def _inst_changed(before: list, after: list) -> bool:
    if len(before) != len(after):
        return True
    for b, a in zip(before, after):
        for k in ("influence", "health", "capacity", "transmission"):
            if b.get(k) != a.get(k):
                return True
    return False


def _validate_run(
    label: str,
    sim: dict[str, Any],
    report: dict[str, Any],
    inst_before: list,
    inst_after: list,
) -> dict[str, Any]:
    errors: list[str] = []
    mode = sim.get("mode") or report.get("mode") or ""

    # Simulation payload
    if mode in ("global", "city", "corporate"):
        if not sim.get("forecast"):
            errors.append("missing forecast")
        bands = sim.get("confidence_bands") or []
        if mode != "corporate" and len(bands) < 2:
            errors.append(f"confidence_bands too short: {len(bands)}")
        elif bands:
            for b in bands[:3]:
                if not (b["p10"] <= b["p50"] <= b["p90"]):
                    errors.append(f"band order violated: {b}")
        audit = sim.get("audit_trail") or []
        if not audit:
            errors.append("missing audit_trail")
        elif mode == "global":
            if "equations" not in audit[0]:
                errors.append("audit missing equations")
            if not audit[0].get("institutions"):
                errors.append("audit missing institution deltas")
            if not audit[0].get("context"):
                errors.append("audit missing context (pop/ag/ind/enterprise)")
    elif mode == "market":
        if sim.get("price_index") is None:
            errors.append("market missing price_index")
        if not sim.get("institutions"):
            errors.append("market missing evolved institutions")
        if not sim.get("institution_evolution"):
            errors.append("market missing institution_evolution trail")

    if not inst_after:
        errors.append("no institutions in output")
    elif mode in ("global", "city", "market") and not _inst_changed(inst_before, inst_after):
        errors.append("institutions did not evolve")

    # Report completeness
    for key in ("title", "horizon", "charts", "tables", "analysis", "disclaimer"):
        if key not in report:
            errors.append(f"report missing {key}")
    analysis_heads = [a.get("heading") for a in report.get("analysis") or []]
    expected_heads = {"推演概述", "方法论与引擎", "推演依据（审计摘要）"}
    missing_heads = expected_heads - set(analysis_heads)
    if mode in ("global", "city") and missing_heads:
        errors.append(f"report analysis missing: {missing_heads}")
    if mode in ("global", "city") and not report.get("conclusion"):
        errors.append("report missing conclusion")
    if mode == "global" and not sim.get("fusion_strategy"):
        errors.append("simulation missing fusion_strategy")
    if mode == "global" and not sim.get("longrun_fusion"):
        errors.append("global should have longrun_fusion enabled")
    if mode == "global" and sim.get("audit_trail") and not sim["audit_trail"][0].get("fusion"):
        errors.append("audit missing fusion block")
    chart_types = {c.get("type") for c in report.get("charts") or []}
    if mode == "global" and "histogram" not in chart_types and "scatter" not in chart_types:
        errors.append("report missing histogram/scatter chart")
    if report.get("charts") is not None and len(report["charts"]) == 0 and mode == "global":
        errors.append("report has no charts for global")

    fan = next((c for c in report.get("charts") or [] if c.get("type") == "fan"), None)
    has_bands_series = "置信区间" in {c.get("title") for c in report.get("charts") or []}

    sample_inst = inst_after[0] if inst_after else {}
    return {
        "label": label,
        "ok": len(errors) == 0,
        "errors": errors,
        "metrics": {
            "forecast_len": len(sim.get("forecast") or []),
            "bands_len": len(sim.get("confidence_bands") or []),
            "audit_len": len(sim.get("audit_trail") or []),
            "inst_count": len(inst_after),
            "inst_evolved": _inst_changed(inst_before, inst_after),
            "sample_influence": sample_inst.get("influence"),
            "sample_health": sample_inst.get("health"),
            "report_charts": len(report.get("charts") or []),
            "report_analysis_sections": len(report.get("analysis") or []),
            "has_fan_chart": bool(fan or has_bands_series),
            "analysis_headings": analysis_heads,
        },
    }


def _print_report(results: list[dict[str, Any]], failures: list[str]) -> None:
    print("\n" + "=" * 72)
    print("FINANCE LAB E2E CHECK")
    print("=" * 72)
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        print(f"\n[{status}] {r['label']}")
        if r.get("metrics"):
            m = r["metrics"]
            print(
                f"  forecast={m.get('forecast_len')} bands={m.get('bands_len')} "
                f"audit={m.get('audit_len')} inst={m.get('inst_count')} "
                f"evolved={m.get('inst_evolved')}"
            )
            print(
                f"  sample inst: influence={m.get('sample_influence')} health={m.get('sample_health')}"
            )
            print(
                f"  report: charts={m.get('report_charts')} analysis={m.get('report_analysis_sections')} "
                f"fan={m.get('has_fan_chart')}"
            )
            if m.get("analysis_headings"):
                print(f"  analysis: {', '.join(m['analysis_headings'][:6])}")
        if r.get("errors"):
            for e in r["errors"]:
                print(f"  ✗ {e}")

    print("\n" + "-" * 72)
    passed = sum(1 for r in results if r["ok"])
    print(f"Total: {passed}/{len(results)} passed")
    if failures:
        print(f"Failures: {len(failures)}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
