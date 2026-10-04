"use client";

import { useEffect, useMemo, useState } from "react";
import {
  labWsAddManualEvents, labWsMilitarySimulate, labWsUploadDataset,
  type LabReport, type TimelineEvent,
} from "@/lib/api";
import LabReportView from "@/components/LabReportView";

type LabPatch = {
  military?: any;
  timeline_events?: TimelineEvent[];
  last_report?: LabReport | null;
};

type Props = {
  labId: string;
  civilizationKey?: string;
  military?: any;
  timelineEvents?: TimelineEvent[];
  lastReport?: LabReport | null;
  onUpdate: (m: any) => void;
  onLabUpdate?: (patch: LabPatch) => void;
};

export default function MilitaryPanel({
  labId, civilizationKey, military, timelineEvents = [], lastReport, onUpdate, onLabUpdate,
}: Props) {
  const activeCivKey = civilizationKey || military?.civilization_key || "";
  const scenarios = useMemo(
    () => (military?.scenario_catalog ?? []) as {
      key: string; name: string; era: string; type?: string; type_label?: string;
    }[],
    [activeCivKey, military?.scenario_catalog],
  );
  const battlefields = military?.battlefield_catalog || [];

  const [scenario, setScenario] = useState(military?.scenario_key || scenarios[0]?.key || "");
  const [battlefield, setBattlefield] = useState(military?.battlefield_key || "rural");
  const [steps, setSteps] = useState(12);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<any>(military?.last_result || null);
  const [report, setReport] = useState<LabReport | null>(lastReport ?? null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState("military_report.pdf");

  const [evTitle, setEvTitle] = useState("");
  const [evStep, setEvStep] = useState(4);
  const [evMag, setEvMag] = useState(-0.2);
  const [evKind, setEvKind] = useState("war");

  useEffect(() => {
    const first = scenarios[0]?.key || "";
    setScenario(military?.scenario_key || first);
    setBattlefield(military?.battlefield_key || "rural");
    setResult(military?.last_result || null);
    setReport(lastReport ?? null);
    setPdfBase64(null);
  }, [activeCivKey, scenarios, military?.scenario_key, military?.battlefield_key, lastReport]);

  async function wrap(fn: () => Promise<void>) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function runSimulate() {
    await wrap(async () => {
      const j = await labWsMilitarySimulate(labId, {
        steps,
        scenario_key: scenario,
        battlefield_key: battlefield,
      });
      if (j.military) onUpdate(j.military);
      if (j.lab) onLabUpdate?.({ military: j.lab.military, timeline_events: j.lab.timeline_events, last_report: j.lab.last_report });
      setResult(j.result || j.simulation);
      if (j.report) {
        setReport(j.report);
        onLabUpdate?.({ last_report: j.report, military: j.military });
      }
      if (j.pdf_base64) {
        setPdfBase64(j.pdf_base64);
        setPdfFilename(j.pdf_filename || "military_report.pdf");
      }
      setMsg("军事推演完成，可下载 PDF 报告");
    });
  }

  const selectedScenario = scenarios.find((s) => s.key === scenario);

  return (
    <div className="rounded-xl border border-rose-800/40 bg-stone-900/50 p-4 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-widest text-rose-300/80">军事推演 · 红蓝对抗</div>
        <p className="text-[10px] opacity-50 mt-1">
          选定本文明战役与地形；事件（可选）与文明背景、当前状态共同作用于推演，完成后自动生成 PDF 报告。
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-3 text-[11px]">
        <label className="space-y-1">
          战役场景
          <select value={scenario || scenarios[0]?.key || ""} onChange={(e) => setScenario(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            {scenarios.map((s) => (
              <option key={s.key} value={s.key}>
                {s.type_label ? `[${s.type_label}] ` : ""}{s.name} ({s.era})
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          战场地形
          <select value={battlefield} onChange={(e) => setBattlefield(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            {battlefields.map((b: any) => (
              <option key={b.key} value={b.key}>{b.name}</option>
            ))}
          </select>
        </label>
      </div>

      {selectedScenario && (
        <p className="text-[10px] opacity-50">
          红方 {military?.red_name} vs 蓝方 {military?.blue_name}
          {selectedScenario.type_label ? ` · ${selectedScenario.type_label}` : ""}
        </p>
      )}

      <div className="rounded-lg border border-violet-800/30 bg-stone-950/40 p-3 space-y-2">
        <div className="text-[10px] uppercase tracking-widest text-violet-300/70">
          事件输入（可选 · 综合背景与选中战役）
        </div>
        <div className="flex flex-wrap gap-2 items-center text-[11px]">
          <label className="cursor-pointer">
            <input type="file" accept=".csv,.xlsx,.xls,.md,.markdown,.txt,.zip" className="hidden"
                   disabled={busy}
                   onChange={(e) => {
                     const f = e.target.files?.[0];
                     if (!f) return;
                     wrap(async () => {
                       const j = await labWsUploadDataset(labId, f);
                       onLabUpdate?.({
                         timeline_events: j.lab?.timeline_events,
                         military: j.lab?.military,
                       });
                       setMsg(`已导入 ${j.imported ?? 0} 条事件`);
                       e.target.value = "";
                     });
                   }} />
            <span className="px-2 py-1 rounded border border-stone-600 hover:border-violet-500">
              上传数据集
            </span>
          </label>
          <span className="opacity-40">|</span>
          <input value={evTitle} onChange={(e) => setEvTitle(e.target.value)}
                 placeholder="事件标题" disabled={busy}
                 className="flex-1 min-w-[120px] bg-stone-950 border border-stone-700 rounded px-2 py-1" />
          <input type="number" min={0} max={60} value={evStep}
                 onChange={(e) => setEvStep(Number(e.target.value) || 0)}
                 className="w-16 bg-stone-950 border border-stone-700 rounded px-1 py-1" title="回合" />
          <select value={evKind} onChange={(e) => setEvKind(e.target.value)}
                  className="bg-stone-950 border border-stone-700 rounded px-1 py-1">
            <option value="war">战争</option>
            <option value="military">军事</option>
            <option value="policy">政策</option>
            <option value="custom">自定义</option>
          </select>
          <input type="number" step={0.05} value={evMag}
                 onChange={(e) => setEvMag(Number(e.target.value) || 0)}
                 className="w-16 bg-stone-950 border border-stone-700 rounded px-1 py-1" title="强度" />
          <button type="button" disabled={busy || !evTitle.trim()}
                  onClick={() => wrap(async () => {
                    const j = await labWsAddManualEvents(labId, [{
                      time: `T+${evStep}`,
                      title: evTitle.trim(),
                      magnitude: evMag,
                      kind: evKind,
                    }]);
                    onLabUpdate?.({ timeline_events: j.timeline_events });
                    setEvTitle("");
                    setMsg(`已添加事件（共 ${j.timeline_events?.length ?? 0} 条）`);
                  })}
                  className="px-2 py-1 rounded border border-stone-600 disabled:opacity-40">
            添加
          </button>
        </div>
        {timelineEvents.length > 0 && (
          <ul className="text-[10px] opacity-60 space-y-0.5 max-h-24 overflow-y-auto">
            {timelineEvents.slice(-6).map((ev, i) => (
              <li key={i}>T+{ev.at_step} · {ev.title} ({ev.kind}, {ev.magnitude})</li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap gap-2 items-end">
        <label className="flex items-center gap-2 text-[11px]">
          推演回合
          <input type="number" min={1} max={60} value={steps}
                 onChange={(e) => setSteps(Number(e.target.value) || 12)}
                 className="w-16 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
        </label>
        <button type="button" disabled={busy}
                onClick={runSimulate}
                className="flex-1 min-w-[200px] py-2.5 rounded bg-rose-500/90 text-stone-950 text-[13px]
                           font-bold disabled:opacity-40 hover:bg-rose-400 transition">
          开始推演 · 生成 PDF 报告
        </button>
      </div>

      {military && (
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div className="rounded border border-rose-900/50 p-2">
            <div className="text-rose-200">红方 · {military.red_name}</div>
            <div>兵力 {Math.round(military.red_strength)} · 士气 {(military.red_morale * 100).toFixed(0)}%</div>
          </div>
          <div className="rounded border border-blue-900/50 p-2">
            <div className="text-blue-200">蓝方 · {military.blue_name}</div>
            <div>兵力 {Math.round(military.blue_strength)} · 士气 {(military.blue_morale * 100).toFixed(0)}%</div>
          </div>
        </div>
      )}

      {result && (
        <div className="text-[12px] space-y-2 border-t border-stone-800 pt-3">
          <div>
            推演结果：
            {result.winner === "red" ? "红方优势" : result.winner === "blue" ? "蓝方优势" : "僵持"}
          </div>
          <ul className="list-disc pl-4 opacity-80 text-[11px]">
            {(result.recommendations || []).map((r: string, i: number) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {report && <LabReportView report={report} pdfBase64={pdfBase64} pdfFilename={pdfFilename} />}

      {(msg || err) && (
        <div className={`text-[11px] ${err ? "text-rose-300" : "text-emerald-300/90"}`}>
          {err || msg}
        </div>
      )}
    </div>
  );
}
