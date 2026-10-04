"use client";

import { useEffect, useMemo, useState } from "react";
import {
  labWsAddManualEvents, labWsPopulationSimulate, labWsUploadDataset,
  type LabReport, type TimelineEvent,
} from "@/lib/api";
import LabReportView from "@/components/LabReportView";

type Region = {
  key: string; name: string; scope: string; description?: string; pop_share?: number;
};

type Props = {
  labId: string;
  civilizationKey?: string;
  population?: any;
  timelineEvents?: TimelineEvent[];
  lastReport?: LabReport | null;
  onUpdate: (p: any) => void;
  onLabUpdate?: (patch: {
    population?: any;
    timeline_events?: TimelineEvent[];
    last_report?: LabReport | null;
  }) => void;
};

export default function PopulationPanel({
  labId, civilizationKey, population, timelineEvents = [], lastReport, onUpdate, onLabUpdate,
}: Props) {
  const activeCivKey = civilizationKey || population?.civilization_key || "";
  const regions = useMemo(
    () => (population?.available_regions ?? []) as Region[],
    [activeCivKey, population?.available_regions],
  );
  const globalRegion = regions.find((r) => r.key === "global") || regions[0];
  const cityRegions = regions.filter((r) => r.scope === "city");
  const areaRegions = regions.filter((r) => r.scope === "region");

  const [scope, setScope] = useState<"global" | "city" | "region">(
    population?.scope || "global",
  );
  const [regionKey, setRegionKey] = useState(population?.region_key || "global");
  const [years, setYears] = useState(10);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<LabReport | null>(lastReport ?? null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState("population_report.pdf");
  const [result, setResult] = useState<any>(population?.last_result || null);

  const [evTitle, setEvTitle] = useState("");
  const [evStep, setEvStep] = useState(3);
  const [evMag, setEvMag] = useState(1.0);
  const [evKind, setEvKind] = useState("war");

  useEffect(() => {
    setScope(population?.scope || "global");
    setRegionKey(population?.region_key || globalRegion?.key || "global");
    setResult(population?.last_result || null);
    setReport(lastReport ?? null);
    setPdfBase64(null);
  }, [activeCivKey, regions, population?.region_key, globalRegion?.key, lastReport]);

  useEffect(() => {
    if (scope === "global") {
      setRegionKey("global");
    } else if (scope === "city" && cityRegions.length && !cityRegions.some((r) => r.key === regionKey)) {
      setRegionKey(cityRegions[0].key);
    } else if (scope === "region" && areaRegions.length && !areaRegions.some((r) => r.key === regionKey)) {
      setRegionKey(areaRegions[0].key);
    }
  }, [scope, cityRegions, areaRegions, regionKey]);

  const selected = regions.find((r) => r.key === regionKey);

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
      const j = await labWsPopulationSimulate(labId, {
        years,
        scope,
        region_key: regionKey,
        city_key: scope === "city" ? regionKey : undefined,
      });
      if (j.population) onUpdate(j.population);
      if (j.lab) onLabUpdate?.({ population: j.lab.population, timeline_events: j.lab.timeline_events, last_report: j.lab.last_report });
      setResult(j.result || j.simulation);
      if (j.report) {
        setReport(j.report);
        onLabUpdate?.({ last_report: j.report, population: j.population });
      }
      if (j.pdf_base64) {
        setPdfBase64(j.pdf_base64);
        setPdfFilename(j.pdf_filename || "population_report.pdf");
      }
      setMsg("人口推演完成，可下载 PDF 报告");
    });
  }

  return (
    <div className="rounded-xl border border-emerald-800/40 bg-stone-900/50 p-4 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-widest text-emerald-300/80">人口发展实验室</div>
        <p className="text-[10px] opacity-50 mt-1">
          事件（可选）与文明背景、政策、运行逻辑共同作用于全局或选定城市/地区的人口结构与数量；推演后自动生成 PDF。
        </p>
      </div>

      {population && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
          <div className="rounded border border-stone-800 p-2">
            <div className="opacity-50">文明总人口</div>
            <div>{Math.round(population.base_total_pop || population.total_pop).toLocaleString()}</div>
          </div>
          <div className="rounded border border-stone-800 p-2">
            <div className="opacity-50">当前范围人口</div>
            <div>{Math.round(population.total_pop).toLocaleString()}</div>
          </div>
          <div className="rounded border border-stone-800 p-2">
            <div className="opacity-50">生育率</div>
            <div>{population.fertility_rate?.toFixed(2)}</div>
          </div>
          <div className="rounded border border-stone-800 p-2">
            <div className="opacity-50">认知指数</div>
            <div>{(population.cognition_index * 100).toFixed(0)}%</div>
          </div>
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-3 text-[11px]">
        <label className="space-y-1">
          推演范围
          <select value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}
                  className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
            <option value="global">全局人口</option>
            <option value="city">城市</option>
            <option value="region">地区</option>
          </select>
        </label>
        {scope !== "global" && (
          <label className="space-y-1">
            {scope === "city" ? "选择城市" : "选择地区"}
            <select value={regionKey} onChange={(e) => setRegionKey(e.target.value)}
                    className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
              {(scope === "city" ? cityRegions : areaRegions).map((r) => (
                <option key={r.key} value={r.key}>{r.name}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      {selected?.description && (
        <p className="text-[10px] opacity-55">{selected.description}</p>
      )}
      {population?.operating_logic && (
        <p className="text-[10px] opacity-45 border-l-2 border-emerald-800/50 pl-2">
          {population.operating_logic.slice(0, 120)}
        </p>
      )}

      <div className="rounded-lg border border-violet-800/30 bg-stone-950/40 p-3 space-y-2">
        <div className="text-[10px] uppercase tracking-widest text-violet-300/70">
          事件输入（可选 · 作用于人口结构）
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
                       onLabUpdate?.({ timeline_events: j.lab?.timeline_events });
                       setMsg(`已导入 ${j.imported ?? 0} 条事件`);
                       e.target.value = "";
                     });
                   }} />
            <span className="px-2 py-1 rounded border border-stone-600">上传数据集</span>
          </label>
          <input value={evTitle} onChange={(e) => setEvTitle(e.target.value)} placeholder="事件标题"
                 disabled={busy}
                 className="flex-1 min-w-[100px] bg-stone-950 border border-stone-700 rounded px-2 py-1" />
          <input type="number" min={1} max={100} value={evStep} title="第几年"
                 onChange={(e) => setEvStep(Number(e.target.value) || 1)}
                 className="w-14 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
          <select value={evKind} onChange={(e) => setEvKind(e.target.value)}
                  className="bg-stone-950 border border-stone-700 rounded px-1 py-1">
            <option value="war">战争</option>
            <option value="plague">瘟疫</option>
            <option value="flood">洪涝</option>
            <option value="pro_natal">鼓励生育</option>
            <option value="healthcare">公共卫生</option>
            <option value="literacy">识字提升</option>
            <option value="policy">政策</option>
          </select>
          <input type="number" step={0.1} value={evMag} onChange={(e) => setEvMag(Number(e.target.value) || 1)}
                 className="w-14 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
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
          <ul className="text-[10px] opacity-60 max-h-20 overflow-y-auto">
            {timelineEvents.slice(-5).map((ev, i) => (
              <li key={i}>第{ev.at_step}年 · {ev.title} ({ev.kind})</li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-[11px] flex items-center gap-2">
          推演年数
          <input type="number" min={1} max={100} value={years}
                 onChange={(e) => setYears(Number(e.target.value) || 10)}
                 className="w-16 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
        </label>
        <button type="button" disabled={busy} onClick={runSimulate}
                className="flex-1 min-w-[200px] py-2.5 rounded bg-emerald-500/90 text-stone-950 text-[13px]
                           font-bold disabled:opacity-40 hover:bg-emerald-400 transition">
          开始推演 · 生成 PDF 报告
        </button>
      </div>

      {result && (
        <div className="text-[11px] opacity-80 border-t border-stone-800 pt-3">
          {years} 年后「{result.region_name || selected?.name || "全局"}」人口约{" "}
          <strong>{result.total_pop?.toLocaleString()}</strong>，
          生育率 {result.fertility_rate}，认知指数 {(result.cognition_index * 100).toFixed(0)}%
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
