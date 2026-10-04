"""Civilization dashboard — background, metrics, events, current state."""
from __future__ import annotations

from typing import Any

from .civilization_demographics import get_demographics
from .civilization_resolver import civilization_context, load_seed_any


def build_dashboard(seed_key: str, user_id: str | None = None) -> dict[str, Any]:
    ctx = civilization_context(seed_key, user_id=user_id)
    demo = get_demographics(ctx)
    seed = load_seed_any(seed_key, user_id=user_id)

    historical = []
    if seed_key.startswith("custom_"):
        for ev in ctx.get("historical_events") or []:
            historical.append({
                "era": ev.get("era", ""),
                "title": ev.get("title", ""),
                "description": ev.get("description", ""),
            })
    else:
        for i, rule in enumerate(seed.rules[:4]):
            if "史事" in rule or len(rule) > 20:
                historical.append({"era": demo.get("era_label", ""), "title": f"背景{i+1}", "description": rule})

    metrics = [
        {"key": "population", "label": "总人口", "value": demo["total_pop"], "unit": "人", "display": f"{demo['total_pop']:,}"},
        {"key": "urbanization", "label": "城镇化率", "value": demo["urban_pop_pct"], "unit": "%", "display": f"{demo['urban_pop_pct']*100:.1f}%"},
        {"key": "fertility", "label": "总和生育率", "value": demo["fertility_rate"], "unit": "", "display": str(demo["fertility_rate"])},
        {"key": "literacy", "label": "识字率", "value": demo["literacy_pct"], "unit": "%", "display": f"{demo['literacy_pct']*100:.1f}%"},
        {"key": "life_exp", "label": "预期寿命", "value": demo["life_expectancy"], "unit": "岁", "display": f"{demo['life_expectancy']}岁"},
        {"key": "gdp_index", "label": "经济指数", "value": demo["gdp_index"], "unit": "基准100", "display": str(demo["gdp_index"])},
    ]

    factions = [{"name": f.get("name", ""), "ideology": f.get("ideology", "")} for f in (seed.factions or [])]
    if not factions and seed_key.startswith("custom_"):
        for cls, ratio in (ctx.get("class_structure") or {}).items():
            if ratio >= 0.08:
                factions.append({"name": cls, "ideology": f"人口占比约 {ratio*100:.0f}%"})

    return {
        "seed_key": seed_key,
        "name": seed.name,
        "genre": seed.genre,
        "premise": seed.premise,
        "rules": seed.rules[:6],
        "era_label": demo.get("era_label", ""),
        "population_explanation": demo.get("explanation", ""),
        "demographics": demo,
        "metrics": metrics,
        "historical_events": historical,
        "factions": factions,
        "locations": [{"name": loc.get("name", ""), "description": loc.get("description", "")[:120]} for loc in seed.locations[:5]],
        "current_state": {
            "stage": ctx.get("current_stage") or demo.get("era_label", "进行中"),
            "government": ctx.get("government_form") or (seed.rules[1] if len(seed.rules) > 1 else ""),
            "operating_logic": ctx.get("operating_logic") or seed.rules[0] if seed.rules else "",
            "summary": seed.premise[:300],
        },
    }
