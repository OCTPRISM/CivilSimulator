"use client";

import { useEffect, useState } from "react";
import type { LabReport } from "@/lib/api";
import FanChart from "@/components/charts/FanChart";

function MiniChart({
  series, labels, width = 280, height = 56, reveal = 1,
}: {
  series: { key: string; label: string; values: number[] }[];
  labels: string[];
  width?: number;
  height?: number;
  reveal?: number;
}) {
  const all = series.flatMap((s) => s.values.filter((v) => typeof v === "number"));
  if (all.length < 2) return <div className="text-[10px] opacity-40">无图表数据</div>;
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = Math.max(1e-6, max - min);
  const colors = ["#a78bfa", "#38bdf8", "#fbbf24"];
  const maxLen = Math.max(...series.map((s) => s.values.length));
  const visible = Math.max(2, Math.floor(maxLen * reveal));

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="max-w-full">
      {series.map((s, si) => {
        const slice = s.values.slice(0, visible);
        const pts = slice.map((v, i) => {
          const x = (i / Math.max(1, s.values.length - 1)) * width;
          const y = height - ((v - min) / span) * (height - 4) - 2;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
        return (
          <polyline key={s.key} fill="none" stroke={colors[si % colors.length]}
                    strokeWidth="1.5" points={pts} />
        );
      })}
    </svg>
  );
}

function HistogramChart({ bins }: { bins: { label: string; count: number }[] }) {
  const max = Math.max(1, ...bins.map((b) => b.count));
  return (
    <div className="flex items-end gap-1 h-24">
      {bins.map((b, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-0.5 min-w-0">
          <div className="w-full bg-violet-500/70 rounded-t"
               style={{ height: `${(b.count / max) * 100}%`, minHeight: b.count ? 4 : 0 }} />
          <span className="text-[8px] opacity-45 truncate w-full text-center">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

function ScatterChart({
  points, xLabel, yLabel,
}: {
  points: { x: number; y: number; label?: string }[];
  xLabel?: string;
  yLabel?: string;
}) {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  if (xs.length < 2) return <div className="text-[10px] opacity-40">无散点数据</div>;
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const spanX = Math.max(1e-6, maxX - minX);
  const spanY = Math.max(1e-6, maxY - minY);
  const w = 280, h = 120;

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="max-w-full">
        {points.map((p, i) => {
          const x = ((p.x - minX) / spanX) * (w - 16) + 8;
          const y = h - ((p.y - minY) / spanY) * (h - 16) - 8;
          return <circle key={i} cx={x} cy={y} r={3} fill="#fbbf24" opacity={0.85} />;
        })}
      </svg>
      <div className="flex justify-between text-[9px] opacity-45 mt-1">
        <span>{xLabel || "x"}</span>
        <span>{yLabel || "y"}</span>
      </div>
    </div>
  );
}

function RadarChart({ axes }: { axes: { label: string; value: number }[] }) {
  if (axes.length < 3) return <div className="text-[10px] opacity-40">无雷达数据</div>;
  const n = axes.length;
  const cx = 80, cy = 80, r = 58;
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const pt = (i: number, v: number) => ({
    x: cx + Math.cos(angle(i)) * r * v,
    y: cy + Math.sin(angle(i)) * r * v,
  });
  const poly = axes.map((a, i) => {
    const p = pt(i, Math.min(1, Math.max(0, a.value)));
    return `${p.x},${p.y}`;
  }).join(" ");

  return (
    <svg width="100%" viewBox="0 0 160 160" className="max-w-[200px] mx-auto">
      {[0.25, 0.5, 0.75, 1].map((lv) => (
        <polygon key={lv}
          points={axes.map((_, i) => { const p = pt(i, lv); return `${p.x},${p.y}`; }).join(" ")}
          fill="none" stroke="#334155" strokeWidth="0.5" />
      ))}
      <polygon points={poly} fill="#38bdf8" fillOpacity={0.25} stroke="#38bdf8" strokeWidth={1.5} />
      {axes.map((a, i) => {
        const p = pt(i, 1.12);
        return (
          <text key={a.label} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="middle"
                fill="#94a3b8" fontSize="7">{a.label}</text>
        );
      })}
    </svg>
  );
}

type Props = {
  report: LabReport | null;
  animate?: boolean;
  pdfBase64?: string | null;
  pdfFilename?: string;
};

export default function LabReportView({ report, animate = false, pdfBase64, pdfFilename }: Props) {
  const [reveal, setReveal] = useState(animate ? 0 : 1);

  useEffect(() => {
    if (!animate || !report) {
      setReveal(1);
      return;
    }
    setReveal(0);
    const t0 = setTimeout(() => setReveal(0.2), 200);
    const t1 = setTimeout(() => setReveal(0.5), 700);
    const t2 = setTimeout(() => setReveal(0.8), 1400);
    const t3 = setTimeout(() => setReveal(1), 2200);
    return () => { clearTimeout(t0); clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [animate, report]);

  if (!report) return null;

  const visibleCharts = animate
    ? report.charts.slice(0, Math.max(1, Math.ceil(report.charts.length * reveal)))
    : report.charts;

  function downloadPdf() {
    if (!pdfBase64) return;
    const bin = atob(pdfBase64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const blob = new Blob([arr], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = pdfFilename || "report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rounded-xl border border-emerald-800/40 bg-stone-950/60 p-4 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-[11px] uppercase tracking-widest text-emerald-300/80">推演报告</div>
          <h2 className="font-serif text-xl mt-1">{report.title}</h2>
          <p className="text-[10px] opacity-50 mt-1">
            周期 {report.horizon} 步 · 维度 {report.dimensions.join("、") || "—"}
          </p>
        </div>
        {pdfBase64 && (
          <button type="button" onClick={downloadPdf}
                  className="text-[11px] px-3 py-1.5 rounded bg-emerald-600/80 text-stone-950 font-semibold">
            下载 PDF 报告
          </button>
        )}
      </div>

      {report.conclusion && (
        <div className="rounded-lg border border-emerald-700/50 bg-emerald-950/30 p-3">
          <div className="text-[10px] uppercase tracking-widest text-emerald-300/80 mb-1">终结性结论</div>
          <p className="text-[12px] leading-relaxed text-emerald-50/90">{report.conclusion}</p>
        </div>
      )}

      {!!report.predictions.length && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {report.predictions.map((p, i) => (
            <div key={i} className="rounded-lg border border-stone-800 px-2 py-1.5 text-[11px]">
              <div className="opacity-50">{p.dimension}</div>
              <div className={`font-serif ${p.trend === "上行" ? "text-emerald-300" : p.trend === "下行" ? "text-red-300" : ""}`}>
                {p.trend} {p.change_pct >= 0 ? "+" : ""}{p.change_pct}%
              </div>
            </div>
          ))}
        </div>
      )}

      {!!visibleCharts.length && (
        <div className="space-y-3">
          <div className="text-[10px] uppercase tracking-widest opacity-50">结果图表</div>
          {visibleCharts.map((ch) => (
            <div key={ch.id} className="rounded-lg border border-stone-800 p-3">
              <div className="text-[11px] font-medium mb-2">{ch.title}</div>
              {ch.type === "fan" && (ch.series?.length ?? 0) >= 3 ? (
                <FanChart
                  bands={(ch.labels || []).map((label, i) => ({
                    label,
                    p10: ch.series?.find((s) => s.key === "p10")?.values[i] ?? 0,
                    p50: ch.series?.find((s) => s.key === "p50")?.values[i] ?? 0,
                    p90: ch.series?.find((s) => s.key === "p90")?.values[i] ?? 0,
                  }))}
                />
              ) : ch.type === "histogram" && ch.bins ? (
                <HistogramChart bins={ch.bins} />
              ) : ch.type === "scatter" && ch.points ? (
                <ScatterChart points={ch.points} xLabel={ch.x_label} yLabel={ch.y_label} />
              ) : ch.type === "radar" && ch.axes ? (
                <RadarChart axes={ch.axes} />
              ) : (
                <MiniChart series={ch.series || []} labels={ch.labels || []} reveal={reveal} />
              )}
              {ch.analysis && (
                <p className="text-[10px] opacity-60 mt-2 leading-relaxed">图释：{ch.analysis}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {!!report.tables.length && reveal > 0.4 && (
        <div className="space-y-3">
          {report.tables.map((tb, ti) => (
            <div key={ti}>
              <div className="text-[10px] uppercase tracking-widest opacity-50 mb-1">{tb.title}</div>
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-[11px] border-collapse">
                  <thead>
                    <tr>
                      {tb.columns.map((c) => (
                        <th key={c} className="text-left border-b border-stone-700 py-1 pr-3 opacity-60 sticky top-0 bg-stone-950">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tb.rows.map((row, ri) => (
                      <tr key={ri}>
                        {row.map((cell, ci) => (
                          <td key={ci} className="py-1 pr-3 border-b border-stone-800/50">{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {!!report.event_impacts.length && reveal > 0.6 && (
        <div className="space-y-2">
          <div className="text-[10px] uppercase tracking-widest opacity-50">事件影响</div>
          <ul className="space-y-1.5 text-[11px]">
            {report.event_impacts.map((ev, i) => (
              <li key={i} className="rounded border border-stone-800 px-2 py-1.5">
                <span className="text-amber-200">{ev.time}</span> · {ev.title}
                <div className="opacity-60">{ev.effect}</div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!!report.analysis.length && reveal > 0.8 && (
        <div className="space-y-3">
          <div className="text-[10px] uppercase tracking-widest opacity-50">综合分析</div>
          {report.analysis.filter((s) => s.heading !== "终结性结论").map((sec, i) => (
            <div key={i}>
              <div className="text-[12px] font-medium text-emerald-100/90">{sec.heading}</div>
              <p className="text-[11px] opacity-75 leading-relaxed mt-0.5">{sec.body}</p>
            </div>
          ))}
        </div>
      )}

      <p className="text-[10px] opacity-35">{report.disclaimer}</p>
    </div>
  );
}
