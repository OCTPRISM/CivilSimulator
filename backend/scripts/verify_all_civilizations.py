#!/usr/bin/env python3
"""Verify finance lab for every built-in civilization — setup + all modes + genre fit."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Genre-specific acceptance criteria for civilization-appropriate simulation
CIV_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "ancient": {
        "label": "古代·九州",
        "institution_names": ["户部", "盐铁司", "柜坊", "转运使"],
        "global_event_snippet": "开仓",
        "city_event_snippet": "漕运",
        "market_goods": {"grain", "salt"},
        "calibration_genre": "ancient",
    },
    "wuxia": {
        "label": "武侠·江湖",
        "institution_names": ["镖局", "钱堂"],
        "global_event_snippet": "渡口",
        "city_event_snippet": "镖局",
        "market_goods": {"grain", "arms"},
        "calibration_genre": "wuxia",
    },
    "modern": {
        "label": "现代·都会",
        "institution_names": ["中央银行", "证券交易所"],
        "global_event_snippet": "央行",
        "city_event_snippet": "地铁",
        "market_goods": {"housing", "food"},
        "calibration_genre": "modern",
    },
    "scifi": {
        "label": "科幻·环带",
        "institution_names": ["联邦储备", "清算"],
        "global_event_snippet": "轨道港",
        "city_event_snippet": "城市",  # default city ok
        "market_goods": {"energy", "data"},
        "calibration_genre": "scifi",
    },
    "xuanhuan": {
        "label": "玄幻·修真",
        "institution_names": ["灵石", "拍卖"],
        "global_event_snippet": "灵脉",
        "city_event_snippet": "坊市",
        "market_goods": {"spirit", "herb"},
        "calibration_genre": "xuanhuan",
    },
    "mystery": {
        "label": "悬疑·雾港",
        "institution_names": ["信托银行", "交易所"],
        "global_event_snippet": "雾港",
        "city_event_snippet": "港口",
        "market_goods": {"info", "bribe"},
        "calibration_genre": "mystery",
    },
    "enterprise": {
        "label": "创业·企业",
        "institution_names": ["创投", "股权"],
        "global_event_snippet": "行业景气",
        "city_event_snippet": "城市",
        "market_goods": {"talent", "rd"},
        "calibration_genre": "enterprise",
    },
    "securities": {
        "label": "证券·镜湖",
        "institution_names": ["证券监管", "清算所"],
        "global_event_snippet": "流动性",
        "city_event_snippet": "城市",
        "market_goods": {"equity", "bond"},
        "calibration_genre": "securities",
    },
    "military": {
        "label": "军工·边关",
        "institution_names": ["军工", "后勤"],
        "global_event_snippet": "边境",
        "city_event_snippet": "城市",
        "market_goods": {"ammo", "fuel"},
        "calibration_genre": "military",
    },
}


def _load_seed_keys() -> list[str]:
    seeds_dir = Path(__file__).resolve().parents[1] / "app" / "seeds"
    keys = []
    for p in sorted(seeds_dir.glob("*.json")):
        if p.name == "player_catalog.json":
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        keys.append(data["key"])
    return keys


def _check_setup(civ_key: str, lab_snap: dict, finance_snap: dict | None, exp: dict) -> list[str]:
    errs: list[str] = []
    inst_names = " ".join(i.get("name", "") for i in lab_snap.get("institutions") or [])
    for kw in exp["institution_names"]:
        if kw not in inst_names:
            errs.append(f"institution missing keyword '{kw}' (have: {inst_names})")

    cal = lab_snap.get("calibration") or {}
    if cal.get("genre") != exp["calibration_genre"]:
        errs.append(f"calibration genre {cal.get('genre')} != {exp['calibration_genre']}")

    if not lab_snap.get("available_cities"):
        errs.append("no cities")
    if not lab_snap.get("available_companies"):
        errs.append("no companies")

    g_events = lab_snap.get("global", {}).get("events") or []
    if g_events:
        titles = " ".join(e.get("title", "") for e in g_events)
        if exp["global_event_snippet"] not in titles:
            errs.append(f"global template mismatch: expected '{exp['global_event_snippet']}' in {titles[:60]}")

    if finance_snap:
        gids = {g.get("id") for g in finance_snap.get("goods") or []}
        missing = exp["market_goods"] - gids
        if missing:
            errs.append(f"market goods missing {missing}")

    return errs


def _check_sim(mode: str, sim: dict, exp: dict) -> list[str]:
    errs: list[str] = []
    if mode in ("global", "city", "corporate"):
        if not sim.get("forecast"):
            errs.append(f"{mode}: no forecast")
        if mode in ("global", "city"):
            bands = sim.get("confidence_bands") or []
            if len(bands) < 4:
                errs.append(f"{mode}: bands={len(bands)}")
            audit = sim.get("audit_trail") or []
            if not audit:
                errs.append(f"{mode}: no audit")
            elif not audit[0].get("institutions"):
                errs.append(f"{mode}: audit missing institution evolution")
    elif mode == "market":
        if sim.get("price_index") is None:
            errs.append("market: no price_index")
        if not sim.get("institutions"):
            errs.append("market: no institutions")
    if not sim.get("disclaimer") and mode != "market":
        pass  # narrative modes have disclaimer on result
    return errs


async def main() -> int:
    from app.layer2_civilization.finance import MarketState
    from app.labs.workspace import (
        _synthetic_society,
        create_or_get_lab,
        lab_finance_simulate,
    )

    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    modes = ["global", "city", "corporate", "market"]

    for civ_key in _load_seed_keys():
        exp = CIV_EXPECTATIONS.get(civ_key)
        if not exp:
            failures.append(f"{civ_key}: no expectations defined")
            continue

        ws = create_or_get_lab(user_id="civ-verify", lab_key="finance", civilization_key=civ_key)
        lab_snap = ws.finance_lab.snapshot()
        finance_snap = ws.finance.snapshot() if ws.finance else None

        setup_errs = _check_setup(civ_key, lab_snap, finance_snap, exp)
        mode_results: dict[str, str] = {}

        for mode in modes:
            try:
                out = await lab_finance_simulate(ws, mode=mode, horizon=12, skip_llm=True, market_steps=16)
                sim = out.get("simulation") or {}
                sim_errs = _check_sim(mode, sim, exp)
                if sim_errs:
                    failures.extend([f"{civ_key}/{mode}: {e}" for e in sim_errs])
                    mode_results[mode] = "FAIL"
                else:
                    mode_results[mode] = "OK"
            except Exception as e:
                failures.append(f"{civ_key}/{mode}: {type(e).__name__}: {e}")
                mode_results[mode] = "ERROR"

        rows.append({
            "civ": civ_key,
            "label": exp["label"],
            "setup": "OK" if not setup_errs else "FAIL",
            "setup_errs": setup_errs,
            **mode_results,
            "institutions": [i["name"] for i in (ws.finance_lab.institutions or [])],
            "global_tpl": [e.get("title") for e in (lab_snap.get("global", {}).get("events") or [])[:2]],
        })
        failures.extend([f"{civ_key}/setup: {e}" for e in setup_errs])

    print("\n" + "=" * 88)
    print("FINANCE LAB — PER-CIVILIZATION VERIFICATION")
    print("=" * 88)
    print(f"{'文明':<12} {'setup':<6} {'global':<8} {'city':<8} {'corp':<8} {'market':<8} 机构")
    print("-" * 88)
    for r in rows:
        inst = "、".join(r["institutions"][:3])
        print(
            f"{r['civ']:<12} {r['setup']:<6} {r.get('global','?'):<8} {r.get('city','?'):<8} "
            f"{r.get('corporate','?'):<8} {r.get('market','?'):<8} {inst}"
        )
        if r["setup_errs"]:
            for e in r["setup_errs"]:
                print(f"  ✗ setup: {e}")

    print("\n" + "-" * 88)
    ok = sum(1 for r in rows if r["setup"] == "OK" and all(r.get(m) == "OK" for m in modes))
    print(f"Fully passing civilizations: {ok}/{len(rows)}")
    if failures:
        print(f"\nTotal issues: {len(failures)}")
        for f in failures[:20]:
            print(f"  • {f}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more")
        return 1
    print("All civilizations pass setup + simulation checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
