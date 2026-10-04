"use client";

export type ConfidenceBand = {
  step?: number;
  label?: string;
  p10: number;
  p50: number;
  p90: number;
};

type Props = {
  bands: ConfidenceBand[];
  history?: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
};

export default function FanChart({
  bands,
  history = [],
  width = 320,
  height = 72,
  stroke = "#38bdf8",
  fill = "rgba(56, 189, 248, 0.18)",
}: Props) {
  if (bands.length < 2) {
    return <div className="text-[10px] opacity-40 py-3">等待置信区间…</div>;
  }

  const all = [
    ...history,
    ...bands.flatMap((b) => [b.p10, b.p50, b.p90]),
  ];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = Math.max(1e-6, max - min);
  const n = bands.length;
  const histOffset = history.length;
  const totalPts = histOffset + n;

  const xAt = (i: number) => (i / Math.max(1, totalPts - 1)) * width;
  const yAt = (v: number) => height - ((v - min) / span) * (height - 6) - 3;

  const fanTop = bands.map((b, i) => `${xAt(histOffset + i).toFixed(1)},${yAt(b.p90).toFixed(1)}`).join(" ");
  const fanBot = [...bands].reverse().map((b, i) => {
    const idx = histOffset + (n - 1 - i);
    return `${xAt(idx).toFixed(1)},${yAt(b.p10).toFixed(1)}`;
  }).join(" ");

  const medianPts = bands.map((b, i) => `${xAt(histOffset + i).toFixed(1)},${yAt(b.p50).toFixed(1)}`).join(" ");

  const histPts = history.length >= 2
    ? history.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ")
    : "";

  return (
    <div className="space-y-1">
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="max-w-full">
        <polygon points={`${fanTop} ${fanBot}`} fill={fill} stroke="none" />
        {histPts && (
          <polyline fill="none" stroke="#64748b" strokeWidth="1.4" strokeDasharray="3 2" points={histPts} />
        )}
        <polyline fill="none" stroke={stroke} strokeWidth="1.8" points={medianPts} />
      </svg>
      <div className="flex flex-wrap gap-3 text-[10px] opacity-50">
        <span>p10–p90 区间</span>
        <span className="text-sky-300/80">— p50 中位</span>
        {history.length >= 2 && <span>· · 历史</span>}
        {bands.length > 0 && (
          <span>
            期末 {bands[bands.length - 1].p10.toFixed(1)}–{bands[bands.length - 1].p90.toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
}
