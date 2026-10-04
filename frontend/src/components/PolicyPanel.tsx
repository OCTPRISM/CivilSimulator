"use client";

import { useEffect, useMemo, useState } from "react";
import {
  labWsAddManualEvents, labWsPolicySimulate, labWsUploadDataset,
  type LabReport, type TimelineEvent,
} from "@/lib/api";
import LabReportView from "@/components/LabReportView";

type Props = {
  labId: string;
  civilizationKey?: string;
  policy?: any;
  timelineEvents?: TimelineEvent[];
  lastReport?: LabReport | null;
  onUpdate: (p: any) => void;
  onLabUpdate?: (patch: { policy?: any; timeline_events?: TimelineEvent[]; last_report?: LabReport | null }) => void;
};

export default function PolicyPanel({
  labId, civilizationKey, policy, timelineEvents = [], lastReport, onUpdate, onLabUpdate,
}: Props) {
  const activeCivKey = civilizationKey || policy?.civilization_key || "";
  const agencies = useMemo(() => (policy?.agencies ?? []) as any[], [activeCivKey, policy?.agencies]);
  const [agencyKey, setAgencyKey] = useState(policy?.agency_key || agencies[0]?.key || "fiscal");
  const agency = agencies.find((a) => a.key === agencyKey) || agencies[0];
  const instruments = agency?.instruments || [];
  const [instrumentKey, setInstrumentKey] = useState(policy?.instrument_key || instruments[0]?.key || "");
  const [steps, setSteps] = useState(24);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<LabReport | null>(lastReport ?? null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState("policy_report.pdf");
  const [evTitle, setEvTitle] = useState("");
  const [evStep, setEvStep] = useState(6);
  const [evMag, setEvMag] = useState(0.15);

  useEffect(() => {
    const first = agencies[0]?.key || "fiscal";
    setAgencyKey(policy?.agency_key || first);
    setInstrumentKey(policy?.instrument_key || agencies[0]?.instruments?.[0]?.key || "");
    setReport(lastReport ?? null);
    setPdfBase64(null);
  }, [activeCivKey, agencies, policy?.agency_key, lastReport]);

  useEffect(() => {
    const insts = agency?.instruments || [];
    if (insts.length && !insts.some((i: any) => i.key === instrumentKey)) {
      setInstrumentKey(insts[0].key);
    }
  }, [agencyKey, agency, instrumentKey]);

  async function wrap(fn: () => Promise<void>) {
    setBusy(true); setErr(null); setMsg(null);
    try { await fn(); } catch (e) { setErr(e instanceof Error ? e.message : "操作失败"); }
    finally { setBusy(false); }
  }

  return (
    <div className="rounded-xl border border-amber-800/40 bg-stone-900/50 p-4 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-widest text-amber-300/80">政令推演实验室</div>
        <p className="text-[10px] opacity-50 mt-1">按政府机关职能与关注点，推演政令执行时滞、合规与社会响应。</p>
      </div>
      <div className="grid sm:grid-cols-2 gap-3 text-[11px]">
        <label className="space-y-1">
          主政部门
          <select value={agencyKey} onChange={(e) => setAgencyKey(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            {agencies.map((a: any) => (
              <option key={a.key} value={a.key}>{a.name}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          政令工具
          <select value={instrumentKey} onChange={(e) => setInstrumentKey(e.target.value)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            {instruments.map((i: any) => (
              <option key={i.key} value={i.key}>{i.name}</option>
            ))}
          </select>
        </label>
      </div>
      {agency?.focus && <p className="text-[10px] opacity-55">关注点：{agency.focus}</p>}

      <EventBar labId={labId} busy={busy} timelineEvents={timelineEvents} evTitle={evTitle} setEvTitle={setEvTitle}
                evStep={evStep} setEvStep={setEvStep} evMag={evMag} setEvMag={setEvMag}
                onLabUpdate={onLabUpdate} wrap={wrap} setMsg={setMsg} kinds={[
        { v: "policy", l: "政令" }, { v: "protest", l: "民变" }, { v: "decree", l: "诏令" },
      ]} />

      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-[11px] flex items-center gap-2">
          推演周期
          <input type="number" min={4} max={120} value={steps} onChange={(e) => setSteps(Number(e.target.value) || 24)}
                 className="w-16 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
        </label>
        <button type="button" disabled={busy} onClick={() => wrap(async () => {
          const j = await labWsPolicySimulate(labId, { steps, agency_key: agencyKey, instrument_key: instrumentKey });
          if (j.policy) onUpdate(j.policy);
          if (j.lab) onLabUpdate?.({ policy: j.lab.policy, timeline_events: j.lab.timeline_events, last_report: j.lab.last_report });
          if (j.report) { setReport(j.report); onLabUpdate?.({ last_report: j.report, policy: j.policy }); }
          if (j.pdf_base64) {
            setPdfBase64(j.pdf_base64);
            setPdfFilename(j.pdf_filename || "policy_report.pdf");
          }
          setMsg("政令推演完成，可下载 PDF 报告");
        })}
                className="flex-1 min-w-[200px] py-2.5 rounded bg-amber-500/90 text-stone-950 text-[13px] font-bold disabled:opacity-40">
          开始推演 · 生成 PDF 报告
        </button>
      </div>
      {report && <LabReportView report={report} pdfBase64={pdfBase64} pdfFilename={pdfFilename} />}
      {(msg || err) && <div className={`text-[11px] ${err ? "text-rose-300" : "text-emerald-300/90"}`}>{err || msg}</div>}
    </div>
  );
}

function EventBar({ labId, busy, timelineEvents, evTitle, setEvTitle, evStep, setEvStep, evMag, setEvMag,
  onLabUpdate, wrap, setMsg, kinds }: any) {
  return (
    <div className="rounded-lg border border-violet-800/30 bg-stone-950/40 p-3 space-y-2">
      <div className="text-[10px] uppercase tracking-widest text-violet-300/70">事件输入（可选）</div>
      <div className="flex flex-wrap gap-2 items-center text-[11px]">
        <label className="cursor-pointer">
          <input type="file" accept=".csv,.xlsx,.xls,.md,.markdown,.txt,.zip" className="hidden" disabled={busy}
                 onChange={(e) => {
                   const f = e.target.files?.[0]; if (!f) return;
                   wrap(async () => {
                     const j = await labWsUploadDataset(labId, f);
                     onLabUpdate?.({ timeline_events: j.lab?.timeline_events });
                     setMsg(`已导入 ${j.imported ?? 0} 条事件`); e.target.value = "";
                   });
                 }} />
          <span className="px-2 py-1 rounded border border-stone-600">上传数据集</span>
        </label>
        <input value={evTitle} onChange={(e) => setEvTitle(e.target.value)} placeholder="事件标题" disabled={busy}
               className="flex-1 min-w-[100px] bg-stone-950 border border-stone-700 rounded px-2 py-1" />
        <input type="number" min={0} max={120} value={evStep} onChange={(e) => setEvStep(Number(e.target.value) || 0)}
               className="w-14 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
        <select className="bg-stone-950 border border-stone-700 rounded px-1 py-1" defaultValue={kinds[0]?.v}>
          {kinds.map((k: any) => <option key={k.v} value={k.v}>{k.l}</option>)}
        </select>
        <input type="number" step={0.05} value={evMag} onChange={(e) => setEvMag(Number(e.target.value) || 0)}
               className="w-14 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
        <button type="button" disabled={busy || !evTitle.trim()} className="px-2 py-1 rounded border border-stone-600 disabled:opacity-40"
                onClick={() => wrap(async () => {
                  const j = await labWsAddManualEvents(labId, [{ time: `T+${evStep}`, title: evTitle.trim(), magnitude: evMag, kind: kinds[0].v }]);
                  onLabUpdate?.({ timeline_events: j.timeline_events }); setEvTitle("");
                  setMsg(`已添加事件（共 ${j.timeline_events?.length ?? 0} 条）`);
                })}>添加</button>
      </div>
      {timelineEvents.length > 0 && (
        <ul className="text-[10px] opacity-60 max-h-20 overflow-y-auto">
          {timelineEvents.slice(-5).map((ev: TimelineEvent, i: number) => (
            <li key={i}>T+{ev.at_step} · {ev.title}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
