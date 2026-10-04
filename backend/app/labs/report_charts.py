"""Render report charts as PNG bytes for PDF embedding."""
from __future__ import annotations

import io
import math
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "STSong", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def _fig_to_png(fig: plt.Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#0f172a")
    plt.close(fig)
    return buf.getvalue()


def render_chart_png(chart: dict[str, Any]) -> bytes | None:
    ctype = chart.get("type", "line")
    if ctype == "line":
        return _line_png(chart)
    if ctype == "fan":
        return _fan_png(chart)
    if ctype == "histogram":
        return _hist_png(chart)
    if ctype == "scatter":
        return _scatter_png(chart)
    if ctype == "radar":
        return _radar_png(chart)
    return None


def _style_ax(ax: plt.Axes, title: str) -> None:
    ax.set_facecolor("#0f172a")
    ax.set_title(title, color="#e2e8f0", fontsize=10)
    ax.tick_params(colors="#94a3b8", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, alpha=0.2, color="#475569")


def _line_png(chart: dict[str, Any]) -> bytes | None:
    series = chart.get("series") or []
    if not series:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    colors = ["#38bdf8", "#a78bfa", "#fbbf24"]
    for i, s in enumerate(series):
        vals = [v for v in (s.get("values") or []) if isinstance(v, (int, float))]
        if len(vals) < 2:
            continue
        ax.plot(range(len(vals)), vals, color=colors[i % len(colors)], linewidth=1.6, label=s.get("label", s.get("key", "")))
    if not ax.lines:
        plt.close(fig)
        return None
    _style_ax(ax, chart.get("title", "曲线"))
    ax.legend(fontsize=7, facecolor="#1e293b", edgecolor="#334155", labelcolor="#e2e8f0")
    return _fig_to_png(fig)


def _fan_png(chart: dict[str, Any]) -> bytes | None:
    series = chart.get("series") or []
    p10 = next((s.get("values") for s in series if s.get("key") == "p10"), None)
    p50 = next((s.get("values") for s in series if s.get("key") == "p50"), None)
    p90 = next((s.get("values") for s in series if s.get("key") == "p90"), None)
    if not p50 or len(p50) < 2:
        return _line_png(chart)
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    xs = list(range(len(p50)))
    if p10 and p90:
        ax.fill_between(xs, p10, p90, color="#38bdf8", alpha=0.25, label="p10–p90")
    ax.plot(xs, p50, color="#38bdf8", linewidth=2, label="p50")
    _style_ax(ax, chart.get("title", "置信区间"))
    ax.legend(fontsize=7, facecolor="#1e293b", edgecolor="#334155", labelcolor="#e2e8f0")
    return _fig_to_png(fig)


def _hist_png(chart: dict[str, Any]) -> bytes | None:
    bins = chart.get("bins") or []
    if not bins:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    labels = [b.get("label", "") for b in bins]
    counts = [b.get("count", 0) for b in bins]
    ax.bar(range(len(counts)), counts, color="#a78bfa", alpha=0.85)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6)
    _style_ax(ax, chart.get("title", "分布"))
    return _fig_to_png(fig)


def _scatter_png(chart: dict[str, Any]) -> bytes | None:
    points = chart.get("points") or []
    xs = [p.get("x") for p in points if isinstance(p.get("x"), (int, float))]
    ys = [p.get("y") for p in points if isinstance(p.get("y"), (int, float))]
    if len(xs) < 2:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    ax.scatter(xs, ys, c="#fbbf24", s=24, alpha=0.85)
    ax.set_xlabel(chart.get("x_label", "x"), color="#94a3b8", fontsize=8)
    ax.set_ylabel(chart.get("y_label", "y"), color="#94a3b8", fontsize=8)
    _style_ax(ax, chart.get("title", "散点"))
    return _fig_to_png(fig)


def _radar_png(chart: dict[str, Any]) -> bytes | None:
    axes = chart.get("axes") or []
    if len(axes) < 3:
        return None
    labels = [a.get("label", "") for a in axes]
    values = [float(a.get("value", 0)) for a in axes]
    angles = np.linspace(0, 2 * math.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(4.5, 4.5), subplot_kw={"polar": True})
    ax.set_facecolor("#0f172a")
    ax.plot(angles, values, color="#38bdf8", linewidth=1.8)
    ax.fill(angles, values, color="#38bdf8", alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color="#94a3b8", fontsize=7)
    ax.set_yticklabels([])
    ax.set_title(chart.get("title", "雷达"), color="#e2e8f0", fontsize=10, pad=16)
    ax.grid(color="#475569", alpha=0.35)
    return _fig_to_png(fig)
