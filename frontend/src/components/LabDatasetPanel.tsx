"use client";

import { useState } from "react";
import {
  labWsAddManualEvents, labWsRunReport, labWsUploadDataset,
  type LabReport, type LabWorkspace, type TimelineEvent,
} from "@/lib/api";

type Props = {
  labId: string;
  labKey: string;
  timelineEvents?: TimelineEvent[];
  lastReport?: LabReport | null;
  onUpdate?: (patch: Partial<LabWorkspace>) => void;
  onReport?: (report: LabReport) => void;
};

export default function LabDatasetPanel({
  labId, labKey, timelineEvents = [], lastReport, onUpdate, onReport,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [timeInput, setTimeInput] = useState("T+8");
  const [titleInput, setTitleInput] = useState("");
  const [magInput, setMagInput] = useState(0.2);
  const [horizon, setHorizon] = useState(24);
  const [mode, setMode] = useState("auto");

  async function wrap(fn: () => Promise<void>) {
    setBusy(true); setErr(null); setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-violet-800/40 bg-stone-900/50 p-4 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-widest text-violet-300/80">
          数据与事件 · 推演报告
        </div>
        <p className="text-[10px] opacity-50 mt-0.5">
          支持 Excel / CSV / Markdown / ZIP；或手动输入「时间 + 事件」。基于文明与事件推演并生成完整报告。
        </p>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <label className="text-[11px] opacity-80 cursor-pointer">
          <input type="file" accept=".csv,.xlsx,.xls,.md,.markdown,.txt,.zip" className="hidden"
                 disabled={busy}
                 onChange={(e) => {
                   const f = e.target.files?.[0];
                   if (!f) return;
                   wrap(async () => {
                     const j = await labWsUploadDataset(labId, f);
                     onUpdate?.({ timeline_events: j.lab?.timeline_events, last_report: j.lab?.last_report });
                     setMsg(`已导入 ${j.imported ?? 0} 条事件`);
                     e.target.value = "";
                   });
                 }} />
          <span className="inline-block px-3 py-1.5 rounded border border-violet-600/50
                           hover:border-violet-400 text-violet-100">
            上传数据集
          </span>
        </label>
        <span className="text-[10px] opacity-40">.csv .xlsx .md .zip</span>
      </div>

      <div className="rounded-lg border border-stone-800 p-3 space-y-2">
        <div className="text-[10px] uppercase tracking-widest opacity-50">手动输入事件</div>
        <div className="flex flex-wrap gap-2 text-[11px]">
          <input value={timeInput} onChange={(e) => setTimeInput(e.target.value)}
                 placeholder="时间 / T+8 / 2024-03"
                 className="w-28 bg-stone-950 border border-stone-700 rounded px-2 py-1" />
          <input value={titleInput} onChange={(e) => setTitleInput(e.target.value)}
                 placeholder="事件标题"
                 className="flex-1 min-w-[140px] bg-stone-950 border border-stone-700 rounded px-2 py-1" />
          <input type="number" step={0.05} value={magInput}
                 onChange={(e) => setMagInput(Number(e.target.value) || 0)}
                 className="w-16 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
          <button type="button" disabled={busy || !titleInput.trim()}
                  onClick={() => wrap(async () => {
                    const j = await labWsAddManualEvents(labId, [{
                      time: timeInput.trim(),
                      title: titleInput.trim(),
                      magnitude: magInput,
                    }]);
                    onUpdate?.({
                      timeline_events: j.timeline_events ?? j.lab?.timeline_events,
                    });
                    setTitleInput("");
                    setMsg("已添加事件");
                  })}
                  className="px-2 py-1 rounded border border-violet-600/60 disabled:opacity-40">
            添加
          </button>
        </div>
      </div>

      {!!timelineEvents.length && (
        <div className="text-[11px] space-y-1 max-h-32 overflow-y-auto">
          <div className="opacity-50">已录入 {timelineEvents.length} 条</div>
          {timelineEvents.slice(-8).map((ev, i) => (
            <div key={ev.id || i} className="opacity-70 truncate">
              {ev.time_label || `T+${ev.at_step}`} · {ev.title}
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-end text-[11px]">
        <label className="space-y-1">
          推演周期
          <input type="number" min={4} max={120} value={horizon}
                 onChange={(e) => setHorizon(Number(e.target.value) || 24)}
                 className="block w-20 bg-stone-950 border border-stone-700 rounded px-2 py-1" />
        </label>
        {labKey === "finance" && (
          <label className="space-y-1">
            维度
            <select value={mode} onChange={(e) => setMode(e.target.value)}
                    className="block bg-stone-950 border border-stone-700 rounded px-2 py-1">
              <option value="auto">自动</option>
              <option value="global">全局走势</option>
              <option value="city">城市金融</option>
            </select>
          </label>
        )}
        <button type="button" disabled={busy}
                onClick={() => wrap(async () => {
                  const j = await labWsRunReport(labId, { horizon, mode });
                  if (j.lab) onUpdate?.({ ...j.lab, last_report: j.report });
                  else onUpdate?.({ last_report: j.report });
                  onReport?.(j.report);
                  setMsg("推演报告已生成");
                })}
                className="px-4 py-1.5 rounded bg-violet-600/80 text-stone-950 font-semibold
                           disabled:opacity-40">
          生成推演报告
        </button>
      </div>

      {msg && <p className="text-[11px] text-emerald-400/90">{msg}</p>}
      {err && <p className="text-[11px] text-red-400">{err}</p>}
      {lastReport && !onReport && (
        <p className="text-[10px] opacity-40">上次报告：{lastReport.title}</p>
      )}
    </div>
  );
}
