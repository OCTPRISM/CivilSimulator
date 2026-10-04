"""Structured simulation report generator for all labs."""
from __future__ import annotations

from typing import Any


def build_report(
    *,
    lab_key: str,
    lab_name: str,
    civilization_name: str,
    civilization_key: str,
    horizon: int,
    dimensions: list[str],
    series: dict[str, list[dict[str, Any]]],
    events: list[dict[str, Any]],
    metrics_summary: dict[str, Any],
    analysis_sections: list[dict[str, str]],
) -> dict[str, Any]:
    """Build a full report payload with charts/tables for frontend rendering."""
    charts = []
    for dim, points in series.items():
        if not points:
            continue
        x_key = "step" if "step" in points[0] else ("year" if "year" in points[0] else "tick")
        y_keys = [k for k in points[0] if k not in (x_key, "label", "forecast") and isinstance(points[0][k], (int, float))]
        if not y_keys:
            continue
        charts.append({
            "id": dim,
            "title": dim,
            "type": "fan" if dim == "置信区间" else "line",
            "x_key": x_key,
            "series": [{"key": y, "label": y, "values": [p.get(y) for p in points]} for y in y_keys[:3]],
            "labels": [str(p.get("label") or p.get(x_key)) for p in points],
        })

    event_impacts = []
    for ev in events:
        event_impacts.append({
            "time": ev.get("time_label") or f"T+{ev.get('at_step', 0)}",
            "title": ev.get("title", ""),
            "magnitude": ev.get("magnitude", 0),
            "effect": _impact_text(ev),
        })

    tables = [
        {
            "title": "关键指标摘要",
            "columns": ["指标", "数值"],
            "rows": [[k, v] for k, v in metrics_summary.items()],
        },
        {
            "title": "输入事件清单",
            "columns": ["时间", "事件", "冲击"],
            "rows": [
                [e.get("time", ""), e.get("title", ""), f"{e.get('magnitude', 0):+.2f}"]
                for e in event_impacts
            ],
        },
    ]

    predictions = []
    for dim, points in series.items():
        if len(points) < 2:
            continue
        forecast_pts = [p for p in points if p.get("forecast")]
        if not forecast_pts:
            forecast_pts = points[-min(8, len(points)):]
        y_key = next((k for k in forecast_pts[0] if isinstance(forecast_pts[0].get(k), (int, float)) and k not in ("step", "year", "tick")), None)
        if y_key and len(forecast_pts) >= 2:
            start_v = forecast_pts[0][y_key]
            end_v = forecast_pts[-1][y_key]
            predictions.append({
                "dimension": dim,
                "horizon": horizon,
                "from_value": start_v,
                "to_value": end_v,
                "change_pct": round((end_v / start_v - 1) * 100, 2) if start_v else 0,
                "trend": "上行" if end_v > start_v else "下行" if end_v < start_v else "持平",
            })

    return {
        "title": f"{civilization_name} · {lab_name} 推演报告",
        "lab_key": lab_key,
        "civilization_key": civilization_key,
        "civilization_name": civilization_name,
        "horizon": horizon,
        "dimensions": dimensions,
        "charts": charts,
        "tables": tables,
        "event_impacts": event_impacts,
        "predictions": predictions,
        "analysis": analysis_sections,
        "disclaimer": "本报告由确定性沙盘内核生成，供情景分析参考，不构成投资或政策决策唯一依据。",
    }


def _impact_text(ev: dict[str, Any]) -> str:
    mag = float(ev.get("magnitude") or 0)
    if mag > 0.2:
        return "显著正向冲击，推升相关维度"
    if mag > 0:
        return "温和正向影响"
    if mag < -0.2:
        return "显著负向冲击，加剧下行压力"
    if mag < 0:
        return "温和负向拖累"
    return "中性事件"


def analysis_from_simulation(
    lab_key: str,
    events: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    extra: str = "",
    mode: str = "global",
    simulation: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    mode_notes = {
        "global": "宏观指数、增长与风险三维联动，政策日历反映潜在干预窗口。",
        "city": "城市指数与地产、就业、流动性共振，本地事件时滞通常短于全局。",
        "corporate": "企业估值对财报、产品与舆情事件敏感，融资建议随现金流路径调整。",
        "retail": "量化路径为宏观校准 GBM 基准，期限选择取决于波动与回撤权衡。",
        "market": "多主体清算引擎逐步消化供需冲击，物价指数与基尼同步演化。",
    }
    event_body = "；".join(
        f"「{e.get('title', '')}」({e.get('time_label', e.get('at_step', ''))})"
        for e in events[:6]
    ) or "未注入额外事件，路径由文明基线驱动。"
    pred_body = "；".join(
        f"{p['dimension']} {p['trend']} ({p['change_pct']:+.1f}%)"
        for p in predictions[:5]
    ) or "详见图表曲线。"
    sections = [
        {
            "heading": "推演概述",
            "body": extra or f"基于 {len(events)} 个输入事件，在指定周期内完成多维度路径推演。",
        },
        {
            "heading": "事件影响分析",
            "body": event_body,
        },
        {
            "heading": "多维度预测",
            "body": pred_body,
        },
        {
            "heading": "模式解读",
            "body": mode_notes.get(mode, mode_notes["global"]),
        },
    ]
    sim = simulation or {}
    methodology = sim.get("methodology") or {}
    if methodology:
        refs = methodology.get("references") or []
        engine = methodology.get("engine") or methodology.get("macro_modes") or ""
        sections.append({
            "heading": "方法论与引擎",
            "body": f"引擎：{engine}。范式：{methodology.get('paradigm', 'structured')}。"
                    + (f" 参考：{'；'.join(str(r) for r in refs[:3])}" if refs else "")
                    + (f" {methodology.get('disclaimer', '')}" if methodology.get("disclaimer") else ""),
        })
    audit = sim.get("audit_trail") or sim.get("event_log") or []
    if audit:
        sample = audit[:3]
        lines = []
        for row in sample:
            if row.get("rationale"):
                lines.append(str(row["rationale"]))
            elif row.get("events"):
                for ev in row["events"][:2]:
                    lines.append(ev.get("rationale") or ev.get("title", ""))
            elif row.get("equations"):
                out = row.get("outputs") or {}
                lines.append(f"step {row.get('step')}: {out}")
        sections.append({
            "heading": "推演依据（审计摘要）",
            "body": "；".join(lines[:5]) or "逐步方程与事件归因见 simulation.audit_trail。",
        })
    bands = sim.get("confidence_bands") or []
    if bands:
        tail = bands[-1]
        sections.append({
            "heading": "情景区间（Monte Carlo）",
            "body": f"期末指数区间 p10={tail.get('p10')} / p50={tail.get('p50')} / p90={tail.get('p90')}。",
        })
    insts = sim.get("institutions") or []
    if insts:
        sample = insts[0]
        sections.append({
            "heading": "金融机构动态",
            "body": (
                f"共 {len(insts)} 个机构随推演演化。"
                f"示例「{sample.get('name', '')}」影响力 {sample.get('influence', '—')}、"
                f"健康度 {sample.get('health', '—')}、容量 {sample.get('capacity', '—')}。"
                "传导系数随人口、工农指数、企业营收与事件冲击逐步调整。"
            ),
        })
    if sim.get("longrun_fusion"):
        fusion = sim.get("fusion_log") or []
        strat = sim.get("fusion_strategy") or {}
        n_corr = sum(len(f.get("corrections") or {}) for f in fusion)
        sections.append({
            "heading": "长程历史融合校正",
            "body": (
                f"策略「{strat.get('label', '—')}」：每步在 Markov 递推后，"
                f"基于累计历史窗口对各参数做 AR(1)/EWMA/趋势预估并加权融合。"
                f"本路径 {len(fusion)} 步，{n_corr} 项参数被长程锚点调整。"
                + (f" {strat.get('notes', '')}" if strat.get("notes") else "")
            ),
        })
    return sections


def enrich_finance_report(
    report: dict[str, Any],
    simulation: dict[str, Any],
    *,
    mode: str = "global",
    horizon: int = 24,
) -> dict[str, Any]:
    """Add time-series tables, multi-type charts, chart analyses, and conclusion."""
    hist = simulation.get("history") or []
    fcst = simulation.get("forecast") or []
    all_pts = hist + fcst

    # Avoid duplicate line charts — replace generic series charts with labeled ones
    existing_ids = {c.get("id") for c in report.get("charts") or []}
    charts: list[dict[str, Any]] = list(report.get("charts") or [])

    if all_pts:
        step_table = _build_step_table(all_pts, mode)
        if step_table:
            report.setdefault("tables", [])
            report["tables"].insert(0, step_table)

        dim_map = _mode_dim_map(mode)
        for dim_key, dim_label in dim_map:
            vals = [p.get(dim_key) for p in all_pts if isinstance(p.get(dim_key), (int, float))]
            if len(vals) < 2:
                continue
            cid = f"curve_{dim_key}"
            if cid in existing_ids:
                continue
            charts.append({
                "id": cid,
                "title": f"{dim_label}变化曲线",
                "type": "line",
                "x_key": "step",
                "series": [{"key": dim_key, "label": dim_label, "values": vals}],
                "labels": [_point_label(p) for p in all_pts],
                "analysis": _analyze_line(dim_label, vals),
            })

    indices = []
    primary_key = _mode_dim_map(mode)[0][0]
    for p in all_pts:
        v = p.get(primary_key)
        if isinstance(v, (int, float)):
            indices.append(v)
    if len(indices) >= 3:
        returns = [(indices[i] / indices[i - 1] - 1) * 100 for i in range(1, len(indices))]
        bins = _histogram_bins(returns)
        if bins:
            charts.append({
                "id": "hist_returns",
                "title": "逐步指数收益率分布",
                "type": "histogram",
                "bins": bins,
                "analysis": _analyze_histogram(returns),
            })

    scatter_pts = fcst or all_pts
    xs = [p.get("risk") for p in scatter_pts if isinstance(p.get("risk"), (int, float))]
    ys = [p.get(primary_key) for p in scatter_pts if isinstance(p.get(primary_key), (int, float))]
    if len(xs) >= 2 and len(ys) >= 2:
        charts.append({
            "id": "scatter_risk_index",
            "title": f"风险—{_mode_dim_map(mode)[0][1]}散点（预测期）",
            "type": "scatter",
            "points": [
                {"x": p.get("risk"), "y": p.get(primary_key), "label": _point_label(p)}
                for p in scatter_pts
                if isinstance(p.get("risk"), (int, float)) and isinstance(p.get(primary_key), (int, float))
            ],
            "x_label": "风险",
            "y_label": _mode_dim_map(mode)[0][1],
            "analysis": _analyze_scatter(xs, ys),
        })

    tail = (fcst or all_pts)[-1] if all_pts else {}
    radar = _radar_axes(tail, mode)
    if len(radar) >= 3:
        charts.append({
            "id": "radar_terminal",
            "title": "期末多维状态雷达",
            "type": "radar",
            "axes": radar,
            "analysis": _analyze_radar(radar, tail),
        })

    report["charts"] = charts

    chart_analyses = [
        {"chart_id": c["id"], "title": c.get("title", ""), "body": c.get("analysis", "")}
        for c in charts if c.get("analysis")
    ]
    if chart_analyses:
        report["chart_analyses"] = chart_analyses

    conclusion = _build_conclusion(report, simulation, mode, horizon)
    report["conclusion"] = conclusion
    report.setdefault("analysis", [])
    if not any(s.get("heading") == "终结性结论" for s in report["analysis"]):
        report["analysis"].append({"heading": "终结性结论", "body": conclusion})

    return report


def _point_label(p: dict[str, Any]) -> str:
    return str(p.get("label") or f"T+{p.get('step', '')}")


def _mode_dim_map(mode: str) -> list[tuple[str, str]]:
    if mode == "city":
        return [
            ("city_index", "城市指数"), ("property_index", "地产指数"),
            ("employment", "就业"), ("liquidity", "流动性"),
        ]
    if mode == "corporate":
        return [("price", "股价"), ("pe", "市盈率"), ("revenue_growth", "营收增长")]
    if mode == "market":
        return [
            ("price_index", "物价指数"), ("inflation", "通胀"),
            ("money_supply", "货币存量"), ("gini", "基尼"),
        ]
    if mode == "retail":
        return [("value", "资产")]
    return [
        ("index", "指数"), ("growth", "增长"), ("risk", "风险"), ("inflation", "通胀"),
    ]


def _build_step_table(points: list[dict[str, Any]], mode: str) -> dict[str, Any] | None:
    cols_map = _mode_dim_map(mode)
    cols = ["时间"] + [label for _, label in cols_map]
    rows: list[list[Any]] = []
    for p in points:
        row: list[Any] = [_point_label(p)]
        for key, _ in cols_map:
            v = p.get(key)
            if isinstance(v, float):
                row.append(round(v, 3))
            else:
                row.append(v if v is not None else "—")
        rows.append(row)
    if not rows:
        return None
    return {"title": "逐步推演数值表", "columns": cols, "rows": rows}


def _histogram_bins(values: list[float], n_bins: int = 8) -> list[dict[str, Any]]:
    if len(values) < 2:
        return []
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 1e-9:
        return [{"label": f"{lo:.2f}", "count": len(values), "start": lo, "end": hi}]
    width = (hi - lo) / n_bins
    counts = [0] * n_bins
    for v in values:
        idx = min(n_bins - 1, int((v - lo) / width))
        counts[idx] += 1
    bins = []
    for i, c in enumerate(counts):
        start = lo + i * width
        end = start + width
        bins.append({
            "label": f"{start:.1f}~{end:.1f}",
            "count": c,
            "start": round(start, 3),
            "end": round(end, 3),
        })
    return bins


def _radar_axes(tail: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    specs = {
        "global": [
            ("index", "指数", 150), ("growth", "增长", 12), ("risk", "风险", 1.0),
            ("inflation", "通胀", 5.0), ("liquidity", "流动性", 1.0),
        ],
        "city": [
            ("city_index", "城市指数", 150), ("property_index", "地产", 150),
            ("employment", "就业", 1.0), ("liquidity", "流动性", 1.0),
        ],
        "corporate": [("price", "股价", 200), ("pe", "市盈率", 40), ("revenue_growth", "营收", 20)],
        "market": [
            ("price_index", "物价", 200), ("inflation", "通胀", 10),
            ("money_supply", "货币", 5000), ("gini", "基尼", 1.0),
        ],
    }
    axes = []
    for key, label, cap in specs.get(mode, specs["global"]):
        v = tail.get(key)
        if not isinstance(v, (int, float)):
            continue
        if key == "growth":
            norm = min(1.0, max(0.0, (v + cap) / (2 * cap)))
        else:
            norm = min(1.0, max(0.0, abs(v) / cap))
        axes.append({"label": label, "value": round(norm, 3), "raw": v})
    return axes


def _analyze_line(label: str, values: list[float]) -> str:
    start, end = values[0], values[-1]
    change = (end / start - 1) * 100 if start else 0
    peak = max(values)
    trough = min(values)
    trend = "上行" if end > start else "下行" if end < start else "横盘"
    vol = sum(abs(values[i] - values[i - 1]) for i in range(1, len(values))) / max(1, len(values) - 1)
    return (
        f"{label}在推演期内呈{trend}，期末相对期初变动 {change:+.1f}%，"
        f"峰值 {peak:.2f}、谷值 {trough:.2f}，逐步平均波动幅度 {vol:.2f}。"
    )


def _analyze_histogram(returns: list[float]) -> str:
    pos = sum(1 for r in returns if r > 0)
    neg = sum(1 for r in returns if r < 0)
    avg = sum(returns) / len(returns)
    return (
        f"共 {len(returns)} 个逐步收益率样本，正收益 {pos} 步、负收益 {neg} 步，"
        f"均值 {avg:+.2f}%。分布偏{'正' if avg > 0.05 else '负' if avg < -0.05 else '中性'}，"
        "反映路径波动集中度。"
    )


def _analyze_scatter(xs: list[float], ys: list[float]) -> str:
    if len(xs) < 2:
        return "样本不足。"
    corr = _pearson(xs, ys)
    direction = "同向" if corr > 0.2 else "反向" if corr < -0.2 else "弱相关"
    return (
        f"风险与指数相关系数约 {corr:.2f}（{direction}）。"
        "高 risk 区间若对应低 index，说明风险溢价抬升压制估值。"
    )


def _analyze_radar(axes: list[dict[str, Any]], tail: dict[str, Any]) -> str:
    top = max(axes, key=lambda a: a.get("value", 0))
    low = min(axes, key=lambda a: a.get("value", 0))
    return (
        f"期末多维快照中「{top['label']}」相对强度最高（归一 {top['value']:.2f}），"
        f"「{low['label']}」相对最弱（{low['value']:.2f}）。"
        f"综合指数/物价读数：{tail.get('index') or tail.get('city_index') or tail.get('price_index') or '—'}。"
    )


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
    den_y = sum((y - my) ** 2 for y in ys) ** 0.5
    if den_x < 1e-9 or den_y < 1e-9:
        return 0.0
    return num / (den_x * den_y)


def _build_conclusion(
    report: dict[str, Any],
    simulation: dict[str, Any],
    mode: str,
    horizon: int,
) -> str:
    preds = report.get("predictions") or []
    events = report.get("event_impacts") or []
    bands = simulation.get("confidence_bands") or []
    narrative = simulation.get("narrative") or {}
    outlook = ""
    if isinstance(narrative, dict):
        outlook = narrative.get("outlook") or narrative.get("summary") or ""
    if not outlook and preds:
        main = preds[0]
        outlook = f"{main.get('dimension', '主指标')}{main.get('trend', '')} {main.get('change_pct', 0):+.1f}%"

    event_note = f"在 {len(events)} 个输入事件作用下，" if events else "在无额外事件情景下，"
    band_note = ""
    if bands:
        t = bands[-1]
        band_note = f" Monte Carlo 期末指数 p10={t.get('p10')} / p50={t.get('p50')} / p90={t.get('p90')}。"

    policy = simulation.get("policy_calendar") or []
    policy_note = ""
    if policy:
        p0 = policy[0]
        policy_note = f" 政策窗口 {p0.get('step_label', '')} 可能出现「{p0.get('action', '')}」。"

    mode_label = {
        "global": "全局宏观", "city": "城市金融", "corporate": "企业估值",
        "retail": "量化交易", "market": "市场清算",
    }.get(mode, mode)

    return (
        f"【结论】{event_note}经 {horizon} 步 {mode_label} 结构化推演，"
        f"主路径展望：{outlook or '见上表与曲线'}。{band_note}{policy_note}"
        "上述结果基于文明基线参数与确定性方程内核，供情景讨论而非实盘决策依据。"
    )
