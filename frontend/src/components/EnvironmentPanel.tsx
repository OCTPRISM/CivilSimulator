"use client";

import { useEffect, useMemo, useState } from "react";
import {
  labWsAddManualEvents, labWsEnvironmentSimulate, labWsUploadDataset,
  type LabReport, type TimelineEvent,
} from "@/lib/api";
import LabReportView from "@/components/LabReportView";

type Props = {
  labId: string;
  civilizationKey?: string;
  environment?: any;
  timelineEvents?: TimelineEvent[];
  lastReport?: LabReport | null;
  onUpdate: (e: any) => void;
  onLabUpdate?: (patch: { environment?: any; timeline_events?: TimelineEvent[]; last_report?: LabReport | null }) => void;
};

export default function EnvironmentPanel({
  labId, civilizationKey, environment, timelineEvents = [], lastReport, onUpdate, onLabUpdate,
}: Props) {
  const activeCivKey = civilizationKey || environment?.civilization_key || "";
  const regions = useMemo(() => (environment?.regions ?? []) as any[], [activeCivKey, environment?.regions]);
  const measures = useMemo(() => (environment?.measures ?? []) as any[], [activeCivKey, environment?.measures]);
  const [regionKey, setRegionKey] = useState(environment?.region_key || "river");
  const [measureKey, setMeasureKey] = useState(environment?.measure_key || "none");
  const [emission, setEmission] = useState(environment?.emission_intensity ?? 0.6);
  const [enterprise, setEnterprise] = useState(environment?.enterprise_name || "");
  const [steps, setSteps] = useState(36);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<LabReport | null>(lastReport ?? null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState("environment_report.pdf");

  useEffect(() => {
    setRegionKey(environment?.region_key || regions[0]?.key || "river");
    setMeasureKey(environment?.measure_key || "none");
    setEmission(environment?.emission_intensity ?? 0.6);
    setEnterprise(environment?.enterprise_name || "");
    setReport(lastReport ?? null);
    setPdfBase64(null);
  }, [activeCivKey, regions, environment?.region_key, lastReport]);

  async function wrap(fn: () => Promise<void>) {
    setBusy(true); setErr(null); setMsg(null);
    try { await fn(); } catch (e) { setErr(e instanceof Error ? e.message : "操作失败"); }
    finally { setBusy(false); }
  }

  const region = regions.find((r) => r.key === regionKey);

  return (
    <div className="rounded-xl border border-lime-800/40 bg-stone-900/50 p-4 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-widest text-lime-300/80">环保演化实验室</div>
        <p className="text-[10px] opacity-50 mt-1">推演企业排放在不同地区的污染速度、强度、财产损失及治理措施效果。</p>
      </div>
      <div className="grid sm:grid-cols-2 gap-3 text-[11px]">
        <label className="space-y-1">
          地区类型
          <select value={regionKey} onChange={(e) => setRegionKey(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            {regions.map((r: any) => (
              <option key={r.key} value={r.key}>{r.name}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          治理措施
          <select value={measureKey} onChange={(e) => setMeasureKey(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            {measures.map((m: any) => (
              <option key={m.key} value={m.key}>{m.name}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          排放企业
          <input value={enterprise} onChange={(e) => setEnterprise(e.target.value)}
                 placeholder={environment?.enterprise_name || "企业名称"}
                 className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1" />
        </label>
        <label className="space-y-1">
          排放强度 {(emission * 100).toFixed(0)}%
          <input type="range" min={0.05} max={1} step={0.05} value={emission}
                 onChange={(e) => setEmission(Number(e.target.value))}
                 className="w-full" />
        </label>
      </div>

      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-[11px] flex items-center gap-2">
          推演周期
          <input type="number" min={8} max={120} value={steps} onChange={(e) => setSteps(Number(e.target.value) || 36)}
                 className="w-16 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
        </label>
        <button type="button" disabled={busy} onClick={() => wrap(async () => {
          const j = await labWsEnvironmentSimulate(labId, {
            steps, region_key: regionKey, measure_key: measureKey,
            emission_intensity: emission, enterprise_name: enterprise || undefined,
          });
          if (j.environment) onUpdate(j.environment);
          if (j.lab) onLabUpdate?.({ environment: j.lab.environment, timeline_events: j.lab.timeline_events, last_report: j.lab.last_report });
          if (j.report) { setReport(j.report); onLabUpdate?.({ last_report: j.report, environment: j.environment }); }
          if (j.pdf_base64) {
            setPdfBase64(j.pdf_base64);
            setPdfFilename(j.pdf_filename || "environment_report.pdf");
          }
          setMsg(`${region?.name || "区域"}环保推演完成，可下载 PDF`);
        })}
                className="flex-1 min-w-[200px] py-2.5 rounded bg-lime-500/90 text-stone-950 text-[13px] font-bold disabled:opacity-40">
          开始推演 · 生成 PDF 报告
        </button>
      </div>
      {environment?.last_result && (
        <div className="text-[11px] opacity-70 grid grid-cols-2 gap-2">
          <div>污染度 {(environment.last_result.pollution * 100).toFixed(1)}%</div>
          <div>健康指数 {(environment.last_result.health_index * 100).toFixed(0)}%</div>
        </div>
      )}
      {report && <LabReportView report={report} pdfBase64={pdfBase64} pdfFilename={pdfFilename} />}
      {(msg || err) && <div className={`text-[11px] ${err ? "text-rose-300" : "text-emerald-300/90"}`}>{err || msg}</div>}
    </div>
  );
}
