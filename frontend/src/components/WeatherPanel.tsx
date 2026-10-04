"use client";

import { useEffect, useMemo, useState } from "react";
import {
  labWsAddManualEvents, labWsWeatherSimulate, labWsUploadDataset,
  type LabReport, type TimelineEvent,
} from "@/lib/api";
import LabReportView from "@/components/LabReportView";

const ROLES = [
  { key: "farmer", name: "农户", desc: "作物收成、灌溉、霜冻与病虫害" },
  { key: "herder", name: "牧民", desc: "草场载畜、转场、雪灾与饲草" },
  { key: "government", name: "政府", desc: "赈济、粮储、迁移与财政压力" },
  { key: "transport", name: "运输", desc: "路网中断、运费、时效与货损" },
];

type Props = {
  labId: string;
  civilizationKey?: string;
  weather?: any;
  timelineEvents?: TimelineEvent[];
  lastReport?: LabReport | null;
  onUpdate: (w: any) => void;
  onLabUpdate?: (patch: { weather?: any; timeline_events?: TimelineEvent[]; last_report?: LabReport | null }) => void;
};

export default function WeatherPanel({
  labId, civilizationKey, weather, timelineEvents = [], lastReport, onUpdate, onLabUpdate,
}: Props) {
  const activeCivKey = civilizationKey || weather?.civilization_key || "";
  const patterns = useMemo(() => (weather?.patterns ?? []) as any[], [activeCivKey, weather?.patterns]);
  const [roleKey, setRoleKey] = useState(weather?.role_key || "farmer");
  const [patternKey, setPatternKey] = useState(weather?.pattern_key || patterns[0]?.key || "normal_var");
  const [steps, setSteps] = useState(24);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<LabReport | null>(lastReport ?? null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState("weather_report.pdf");
  const [evTitle, setEvTitle] = useState("");
  const [evStep, setEvStep] = useState(8);

  const role = ROLES.find((r) => r.key === roleKey) || ROLES[0];

  useEffect(() => {
    setRoleKey(weather?.role_key || "farmer");
    setPatternKey(weather?.pattern_key || patterns[0]?.key || "normal_var");
    setReport(lastReport ?? null);
    setPdfBase64(null);
  }, [activeCivKey, patterns, weather?.role_key, lastReport]);

  async function wrap(fn: () => Promise<void>) {
    setBusy(true); setErr(null); setMsg(null);
    try { await fn(); } catch (e) { setErr(e instanceof Error ? e.message : "操作失败"); }
    finally { setBusy(false); }
  }

  return (
    <div className="rounded-xl border border-sky-800/40 bg-stone-900/50 p-4 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-widest text-sky-300/80">气象演化实验室</div>
        <p className="text-[10px] opacity-50 mt-1">按角色关注点分别生成推演报告：农户、牧民、政府、运输。</p>
      </div>
      <div className="grid sm:grid-cols-2 gap-3 text-[11px]">
        <label className="space-y-1">
          推演视角
          <select value={roleKey} onChange={(e) => setRoleKey(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            {ROLES.map((r) => (
              <option key={r.key} value={r.key}>{r.name}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          气候模式
          <select value={patternKey} onChange={(e) => setPatternKey(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            {patterns.map((p: any) => (
              <option key={p.key} value={p.key}>{p.name}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="text-[10px] opacity-55">{role.name}关注：{role.desc}</p>

      <div className="rounded-lg border border-violet-800/30 bg-stone-950/40 p-3 space-y-2 text-[11px]">
        <div className="text-[10px] uppercase tracking-widest text-violet-300/70">极端事件（可选）</div>
        <div className="flex flex-wrap gap-2">
          <input value={evTitle} onChange={(e) => setEvTitle(e.target.value)} placeholder="如：连续暴雨"
                 className="flex-1 bg-stone-950 border border-stone-700 rounded px-2 py-1" />
          <button type="button" disabled={busy || !evTitle.trim()}
                  onClick={() => wrap(async () => {
                    const j = await labWsAddManualEvents(labId, [{
                      time: `T+${evStep}`, title: evTitle.trim(), magnitude: 0.25, kind: "flood",
                    }]);
                    onLabUpdate?.({ timeline_events: j.timeline_events }); setEvTitle("");
                  })}
                  className="px-2 py-1 rounded border border-stone-600 disabled:opacity-40">添加</button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-[11px] flex items-center gap-2">
          推演周期
          <input type="number" min={4} max={120} value={steps} onChange={(e) => setSteps(Number(e.target.value) || 24)}
                 className="w-16 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
        </label>
        <button type="button" disabled={busy} onClick={() => wrap(async () => {
          const j = await labWsWeatherSimulate(labId, { steps, role_key: roleKey, pattern_key: patternKey });
          if (j.weather) onUpdate(j.weather);
          if (j.lab) onLabUpdate?.({ weather: j.lab.weather, timeline_events: j.lab.timeline_events, last_report: j.lab.last_report });
          if (j.report) { setReport(j.report); onLabUpdate?.({ last_report: j.report, weather: j.weather }); }
          if (j.pdf_base64) {
            setPdfBase64(j.pdf_base64);
            setPdfFilename(j.pdf_filename || "weather_report.pdf");
          }
          setMsg(`${role.name}视角气象推演完成，可下载 PDF`);
        })}
                className="flex-1 min-w-[200px] py-2.5 rounded bg-sky-500/90 text-stone-950 text-[13px] font-bold disabled:opacity-40">
          开始推演 · 生成 {role.name} PDF 报告
        </button>
      </div>
      {report && <LabReportView report={report} pdfBase64={pdfBase64} pdfFilename={pdfFilename} />}
      {(msg || err) && <div className={`text-[11px] ${err ? "text-rose-300" : "text-emerald-300/90"}`}>{err || msg}</div>}
    </div>
  );
}
