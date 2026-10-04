"""Generate PDF bytes from structured lab report."""
from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _ensure_font() -> str:
    name = "STSong-Light"
    try:
        pdfmetrics.getFont(name)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


def build_pdf_bytes(report: dict[str, Any]) -> bytes:
    font = _ensure_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    base = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCN", parent=base["Title"], fontName=font, fontSize=16, leading=22)
    h_style = ParagraphStyle("HCN", parent=base["Heading2"], fontName=font, fontSize=12, leading=16,
                             spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle("BodyCN", parent=base["Normal"], fontName=font, fontSize=10, leading=14)
    small_style = ParagraphStyle("SmallCN", parent=body_style, fontSize=8, textColor=colors.grey)
    conclusion_style = ParagraphStyle(
        "ConclusionCN", parent=body_style, fontName=font, fontSize=11, leading=16,
        backColor=colors.HexColor("#1e293b"), borderPadding=8, spaceBefore=8, spaceAfter=8,
    )

    story: list[Any] = []
    story.append(Paragraph(_esc(report.get("title", "推演报告")), title_style))
    meta = (
        f"文明：{report.get('civilization_name', '')} · "
        f"维度：{report.get('mode_label', '')} · "
        f"周期：{report.get('horizon', '')} 步"
    )
    story.append(Paragraph(_esc(meta), body_style))
    story.append(Spacer(1, 0.4 * cm))

    dash = report.get("dashboard") or {}
    if dash:
        story.append(Paragraph("文明背景与当前状态", h_style))
        for line in [
            f"时代：{dash.get('era_label', '')}",
            f"人口说明：{dash.get('population_explanation', '')}",
            f"当前阶段：{(dash.get('current_state') or {}).get('stage', '')}",
        ]:
            if line.strip("："):
                story.append(Paragraph(_esc(line), body_style))
        story.append(Spacer(1, 0.25 * cm))

    conclusion = report.get("conclusion") or ""
    if conclusion:
        story.append(Paragraph("终结性结论", h_style))
        story.append(Paragraph(_esc(conclusion), conclusion_style))
        story.append(Spacer(1, 0.3 * cm))

    charts = report.get("charts") or []
    if charts:
        story.append(Paragraph("结果图表", h_style))
        from .report_charts import render_chart_png

        for ch in charts[:12]:
            png = render_chart_png(ch)
            if png:
                img = Image(io.BytesIO(png), width=16 * cm, height=6.5 * cm)
                story.append(img)
                analysis = ch.get("analysis") or ""
                if analysis:
                    story.append(Paragraph(_esc(f"图释：{analysis}"), small_style))
                story.append(Spacer(1, 0.2 * cm))

    tables = report.get("tables") or []
    for tb in tables:
        story.append(Paragraph(_esc(tb.get("title", "表格")), h_style))
        cols = tb.get("columns") or []
        rows = tb.get("rows") or []
        if not cols or not rows:
            continue
        data = [cols] + [[str(c) for c in row] for row in rows[:40]]
        col_w = min(16 * cm / max(1, len(cols)), 4 * cm)
        tbl = Table(data, colWidths=[col_w] * len(cols))
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), font, 7),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.25 * cm))

    preds = report.get("predictions") or []
    if preds:
        story.append(Paragraph("多维度预测", h_style))
        for p in preds[:8]:
            story.append(Paragraph(
                _esc(f"{p.get('dimension', '')}：{p.get('trend', '')} "
                     f"({p.get('change_pct', 0):+.1f}%)"),
                body_style,
            ))

    impacts = report.get("event_impacts") or []
    if impacts:
        story.append(Paragraph("事件影响", h_style))
        rows = [["时间", "事件", "影响"]] + [
            [str(e.get("time", "")), str(e.get("title", "")), str(e.get("effect", ""))]
            for e in impacts[:20]
        ]
        tbl = Table(rows, colWidths=[2.5 * cm, 5 * cm, 8.5 * cm])
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), font, 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.3 * cm))

    for sec in report.get("analysis") or []:
        if sec.get("heading") == "终结性结论" and conclusion:
            continue
        story.append(Paragraph(_esc(sec.get("heading", "")), h_style))
        story.append(Paragraph(_esc(sec.get("body", "")), body_style))

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(_esc(report.get("disclaimer", "")), small_style))

    doc.build(story)
    return buf.getvalue()


def _esc(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
