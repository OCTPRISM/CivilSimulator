"use client";

import { useEffect, useMemo, useState } from "react";
import type { Session } from "@/lib/api";
import {
  advanceFinance, financeShock,
  labCorporateEvent, labCorporateForecast,
  labGlobalEvent, labGlobalForecast,
  labCityEvent, labCityForecast,
  labRetailRun,
  labWsAdvanceFinance, labWsCorporateEvent, labWsCorporateForecast,
  labWsFinanceShock, labWsGlobalEvent, labWsGlobalForecast,
  labWsCityEvent, labWsCityForecast, labWsRetailRun,
  labWsUploadDataset, labWsAddManualEvents, labWsFinanceSimulate,
  type LabReport, type TimelineEvent,
} from "@/lib/api";
import LabReportView from "@/components/LabReportView";
import FanChart from "@/components/charts/FanChart";
import AuditTrailPanel from "@/components/AuditTrailPanel";
import InstitutionsPanel from "@/components/InstitutionsPanel";

type FinanceGood = {
  id: string; name: string; base: number; price: number;
  inventory: number; supply_tick: number; demand_tick: number; change_pct: number;
};

type FinanceSnap = {
  seed: string; tick: number; price_index: number; inflation: number;
  money_supply: number; velocity: number; gini: number; volume: number;
  goods: FinanceGood[];
  shocks: { id: string; kind: string; good_id: string; magnitude: number; remaining: number; note: string }[];
  history: {
    tick: number; price_index: number; inflation: number; money_supply: number;
    velocity: number; gini: number; volume: number; prices: Record<string, number>;
  }[];
  engine?: string;
};

type Tab = "market" | "global" | "city" | "corporate" | "retail";

type LabPatch = {
  finance?: FinanceSnap | null;
  finance_lab?: any;
  timeline_events?: TimelineEvent[];
  last_report?: LabReport | null;
};

type Props = {
  /** Session-bound mode (legacy / play page). */
  sid?: string;
  session?: Session | null;
  onUpdate?: (s: Session) => void;
  /** Standalone experiment platform mode. */
  labId?: string;
  civilizationKey?: string;
  finance?: FinanceSnap | null;
  financeLab?: any;
  timelineEvents?: TimelineEvent[];
  lastReport?: LabReport | null;
  onLabUpdate?: (patch: LabPatch) => void;
  compact?: boolean;
};

function Sparkline({
  values, width = 260, height = 52, stroke = "#22d3ee",
}: { values: number[]; width?: number; height?: number; stroke?: string }) {
  if (values.length < 2) {
    return <div className="text-[10px] opacity-40 py-3">等待序列…</div>;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-6, max - min);
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / span) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="max-w-full">
      <polyline fill="none" stroke={stroke} strokeWidth="1.6" points={pts} />
    </svg>
  );
}

function ForecastViz({
  result, valueKey, stroke,
}: {
  result: any; valueKey: string; stroke: string;
}) {
  const history = (result.history || []).map((h: any) => h[valueKey] ?? h.index ?? h.price);
  const forecast = (result.forecast || []).map((h: any) => h[valueKey] ?? h.index ?? h.price);
  const bands = result.confidence_bands || [];
  if (bands.length >= 2) {
    return <FanChart bands={bands} history={history} stroke={stroke} />;
  }
  return <Sparkline values={[...history, ...forecast]} stroke={stroke} />;
}

function activeTabResult(tab: Tab, global: any, city: any, corp: any, retail: any, market: any) {
  if (tab === "global") return global;
  if (tab === "city") return city;
  if (tab === "corporate") return corp;
  if (tab === "retail") return retail;
  if (tab === "market") return market;
  return null;
}

function SimulationProgress({ phase }: { phase: string }) {
  return (
    <div className="rounded-lg border border-cyan-700/40 bg-cyan-950/25 p-3 space-y-2">
      <div className="flex justify-between text-[11px]">
        <span className="text-cyan-200">{phase}</span>
        <span className="opacity-50 animate-pulse">推演中…</span>
      </div>
      <div className="h-1.5 rounded-full bg-stone-800 overflow-hidden">
        <div className="h-full w-1/3 bg-cyan-400 animate-[pulse_1.2s_ease-in-out_infinite]" />
      </div>
      <p className="text-[10px] opacity-45">按步计算中，完成后可下载 PDF 报告。</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-stone-800 px-2 py-1.5">
      <div className="text-[10px] opacity-50">{label}</div>
      <div className="font-serif text-sm text-cyan-100">{value}</div>
    </div>
  );
}

export default function FinancePanel({
  sid, session, onUpdate, labId, civilizationKey, finance: financeProp, financeLab,
  timelineEvents = [], lastReport, onLabUpdate, compact,
}: Props) {
  const standalone = Boolean(labId);
  const [localFinance, setLocalFinance] = useState<FinanceSnap | null>(
    (financeProp as FinanceSnap | null) ?? (session?.finance as FinanceSnap | null) ?? null,
  );
  const finance = standalone
    ? ((financeProp as FinanceSnap | null) ?? localFinance)
    : ((session?.finance as FinanceSnap | null) ?? localFinance);

  const [tab, setTab] = useState<Tab>("global");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // market
  const [steps, setSteps] = useState(24);
  const [goodId, setGoodId] = useState("*");
  const [kind, setKind] = useState<"demand" | "supply" | "price">("demand");
  const [magnitude, setMagnitude] = useState(0.4);

  // global / corporate event form
  const [evTitle, setEvTitle] = useState("");
  const [evStep, setEvStep] = useState(40);
  const [evMag, setEvMag] = useState(0.25);
  const [evKind, setEvKind] = useState("political");
  const [horizon, setHorizon] = useState(24);
  const [skipLlm, setSkipLlm] = useState(false);
  const [useLlmNer, setUseLlmNer] = useState(true);
  const [timeInput, setTimeInput] = useState("T+8");
  const [report, setReport] = useState<LabReport | null>(lastReport ?? null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState("finance_report.pdf");
  const [simPhase, setSimPhase] = useState<string | null>(null);
  const [reportAnimate, setReportAnimate] = useState(false);

  // corporate — optional manual override
  const [company, setCompany] = useState("");
  const [sector, setSector] = useState("");

  // retail
  const [risk, setRisk] = useState<"conservative" | "balanced" | "aggressive">("balanced");
  const [retailHorizon, setRetailHorizon] = useState<"auto" | "short" | "long">("auto");
  const [capital, setCapital] = useState(100000);

  const labSnap = financeLab || session?.finance_lab;
  const activeCivKey = civilizationKey || labSnap?.civilization_key || "";
  const calibration = labSnap?.calibration as Record<string, unknown> | undefined;

  const cities = useMemo(
    () => (labSnap?.available_cities ?? []) as { key: string; name: string; description?: string }[],
    [activeCivKey, labSnap?.available_cities],
  );
  const companies = useMemo(
    () => (labSnap?.available_companies ?? []) as {
      key: string; name: string; sector?: string; description?: string;
      entity_type?: string; entity_type_label?: string;
    }[],
    [activeCivKey, labSnap?.available_companies],
  );
  const enterpriseOptions = useMemo(
    () => companies.filter((c) => !c.entity_type || c.entity_type === "enterprise"),
    [companies],
  );
  const unitOptions = useMemo(
    () => companies.filter((c) => c.entity_type === "unit"),
    [companies],
  );

  const [globalResult, setGlobalResult] = useState<any>(
    labSnap?.global?.last_forecast || null,
  );
  const [cityResult, setCityResult] = useState<any>(
    labSnap?.city?.last_forecast || null,
  );
  const [cityKey, setCityKey] = useState<string>(labSnap?.city?.city_key || "");
  const cityName = useMemo(() => {
    const c = cities.find((x) => x.key === cityKey) || cities[0];
    return labSnap?.city?.city_name || c?.name || "本城";
  }, [cities, cityKey, labSnap?.city?.city_name]);

  const [corpResult, setCorpResult] = useState<any>(
    labSnap?.corporate?.last_forecast || null,
  );
  const [companyKey, setCompanyKey] = useState<string>(labSnap?.corporate?.company?.key || "");
  const selectedCompany = useMemo(() => {
    return companies.find((c) => c.key === companyKey) || companies[0];
  }, [companies, companyKey]);

  useEffect(() => {
    if (!activeCivKey) return;
    setCityKey(labSnap?.city?.city_key || cities[0]?.key || "");
    setCompanyKey(labSnap?.corporate?.company?.key || companies[0]?.key || "");
    setGlobalResult(labSnap?.global?.last_forecast || null);
    setCityResult(labSnap?.city?.last_forecast || null);
    setCorpResult(labSnap?.corporate?.last_forecast || null);
    setRetailResult(labSnap?.retail?.last_result || null);
    setReport(lastReport ?? null);
    setPdfBase64(null);
    setCompany("");
    setSector("");
  }, [activeCivKey, cities, companies, labSnap?.city?.city_key, labSnap?.corporate?.company?.key, lastReport]);
  const [retailResult, setRetailResult] = useState<any>(
    labSnap?.retail?.last_result || null,
  );

  const indexSeries = useMemo(
    () => (finance?.history || []).map((h) => h.price_index),
    [finance?.history],
  );

  const institutions = useMemo(() => {
    const sim = activeTabResult(tab, globalResult, cityResult, corpResult, retailResult, finance);
    return (sim?.institutions ?? labSnap?.institutions ?? []) as import("@/components/InstitutionsPanel").FinanceInstitution[];
  }, [tab, globalResult, cityResult, corpResult, retailResult, finance, labSnap?.institutions]);

  function applyResponse(j: any) {
    if (j.session && onUpdate) onUpdate(j.session);
    const patch: LabPatch = {};
    if (j.finance !== undefined) {
      patch.finance = j.finance;
      setLocalFinance(j.finance);
    }
    if (j.finance_lab !== undefined) patch.finance_lab = j.finance_lab;
    if (Object.keys(patch).length && onLabUpdate) onLabUpdate(patch);
  }

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

  const tabs: { id: Tab; label: string }[] = [
    { id: "global", label: "全局走势" },
    { id: "city", label: "城市金融" },
    { id: "corporate", label: "企业评估" },
    { id: "retail", label: "量化交易" },
    { id: "market", label: "市场清算" },
  ];

  const tabModeLabel = tabs.find((t) => t.id === tab)?.label || "推演";

  async function runUnifiedSimulate() {
    if (!standalone || !labId) return;
    setSimPhase("正在推演…");
    setReportAnimate(false);
    try {
      await wrap(async () => {
        const j = await labWsFinanceSimulate(labId, {
          mode: tab,
          horizon,
          city_key: tab === "city" ? cityKey : undefined,
          company_key: tab === "corporate" ? companyKey : undefined,
          company_name: company || undefined,
          sector: sector || undefined,
          risk,
          retail_horizon: retailHorizon,
          capital,
          market_steps: tab === "market" ? steps : undefined,
          skip_llm: skipLlm,
        });
        applyResponse(j);
        const sim = j.simulation;
        if (j.finance_lab?.institutions) {
          onLabUpdate?.({ finance_lab: j.finance_lab });
        }
        if (j.lab) {
          onLabUpdate?.({
            finance: j.lab.finance,
            finance_lab: j.lab.finance_lab,
            timeline_events: j.lab.timeline_events,
            last_report: j.lab.last_report,
          });
        }
        if (tab === "global") setGlobalResult(sim);
        else if (tab === "city") setCityResult(sim);
        else if (tab === "corporate") setCorpResult(sim);
        else if (tab === "retail") setRetailResult(sim);
        if (j.report) {
          setReport(j.report);
          setReportAnimate(true);
          onLabUpdate?.({ last_report: j.report });
        }
        if (j.pdf_base64) {
          setPdfBase64(j.pdf_base64);
          setPdfFilename(j.pdf_filename || "finance_report.pdf");
        }
        setMsg(`${tabModeLabel}推演完成 · 共 ${horizon} 步 · 报告已生成，可下载 PDF`);
        window.setTimeout(() => setSimPhase(null), 1200);
      });
    } catch {
      setSimPhase(null);
    }
  }

  return (
    <div className={`rounded-xl border border-cyan-800/40 bg-stone-900/50 p-3 space-y-3 ${compact ? "" : "max-w-3xl"}`}>
      <div>
        <div className="text-[11px] uppercase tracking-widest text-cyan-300/80">
          金融验证实验室
        </div>
        <p className="text-[10px] opacity-50 mt-0.5">
          情景沙盘推演 · 数值可复现 · 文案可由 Ollama 润色 · 非实盘投资建议
        </p>
      </div>

      {!!institutions.length && (
        <InstitutionsPanel institutions={institutions} />
      )}

      <div className="flex flex-wrap gap-1">
        {tabs.map((t) => (
          <button key={t.id} type="button" onClick={() => setTab(t.id)}
                  className={`px-2.5 py-1 rounded text-[11px] border transition
                    ${tab === t.id
                      ? "border-cyan-400 bg-cyan-500/15 text-cyan-100"
                      : "border-stone-700 text-stone-400 hover:border-stone-500"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {standalone && labId && (
        <div className="rounded-lg border border-violet-800/30 bg-stone-950/40 p-3 space-y-2">
          <div className="text-[10px] uppercase tracking-widest text-violet-300/70">
            事件输入（作用于当前文明背景下的各维度推演）
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
                         onLabUpdate?.({ timeline_events: j.lab?.timeline_events, ...j.lab });
                         setMsg(`已导入 ${j.imported ?? 0} 条事件`);
                         e.target.value = "";
                       });
                     }} />
              <span className="inline-block px-2 py-1 rounded border border-violet-600/40 text-violet-100">
                上传数据集
              </span>
            </label>
            <input value={timeInput} onChange={(e) => setTimeInput(e.target.value)}
                   placeholder="时间"
                   className="w-24 bg-stone-950 border border-stone-700 rounded px-2 py-1" />
            <select value={evKind} onChange={(e) => setEvKind(e.target.value)}
                    className="bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[11px]">
              <option value="political">政治</option>
              <option value="policy">政策</option>
              <option value="rate">利率</option>
              <option value="price">物价</option>
              <option value="property">地产</option>
              <option value="war">战争</option>
              <option value="plague">瘟疫</option>
              <option value="earthquake">灾害</option>
              <option value="earnings">财报</option>
              <option value="product">产品</option>
              <option value="scandal">舆情</option>
              <option value="custom">自定义</option>
            </select>
            <input value={evTitle} onChange={(e) => setEvTitle(e.target.value)}
                   placeholder="事件标题"
                   className="flex-1 min-w-[120px] bg-stone-950 border border-stone-700 rounded px-2 py-1" />
            <input type="number" step={0.05} value={evMag}
                   onChange={(e) => setEvMag(Number(e.target.value) || 0)}
                   className="w-14 bg-stone-950 border border-stone-700 rounded px-1 py-1" />
            <button type="button" disabled={busy || !evTitle.trim()}
                    onClick={() => wrap(async () => {
                      const j = await labWsAddManualEvents(labId, [{
                        time: timeInput.trim(),
                        title: evTitle.trim(),
                        magnitude: evMag,
                        kind: evKind,
                      }], useLlmNer);
                      onLabUpdate?.({ timeline_events: j.timeline_events ?? j.lab?.timeline_events });
                      setEvTitle("");
                      setMsg(useLlmNer ? "已添加事件（LLM 结构化通道）" : "已添加事件");
                    })}
                    className="px-2 py-1 rounded border border-violet-600/50 disabled:opacity-40">
              添加
            </button>
            <label className="flex items-center gap-1.5 text-[10px] opacity-60">
              <input type="checkbox" checked={useLlmNer}
                     onChange={(e) => setUseLlmNer(e.target.checked)}
                     className="rounded border-stone-600" />
              LLM 结构化（仅 NER→通道，不生成数值）
            </label>
          </div>
          {!!timelineEvents.length && (
            <div className="text-[10px] opacity-50 max-h-20 overflow-y-auto space-y-0.5">
              已录入 {timelineEvents.length} 条 · {timelineEvents.slice(-4).map((e) =>
                `${e.time_label || `T+${e.at_step}`} ${e.title}`).join(" · ")}
              {timelineEvents.slice(-2).map((e, i) => e.rationale ? (
                <div key={i} className="opacity-70 italic">{e.rationale}</div>
              ) : null)}
            </div>
          )}
        </div>
      )}

      {tab === "global" && (
        <div className="space-y-3">
          <p className="text-[12px] opacity-70 leading-relaxed">
            基于文明宏观背景与输入事件，推演全局指数、风险及政策调整时间点。
          </p>

          {globalResult && (
            <div className="space-y-2 text-[12px]">
              <div className="grid grid-cols-2 gap-2">
                <Metric label="展望" value={globalResult.narrative?.outlook || "—"} />
                <Metric label="期末指数"
                        value={String(globalResult.forecast?.at(-1)?.index?.toFixed?.(1)
                          ?? globalResult.forecast?.[globalResult.forecast.length - 1]?.index
                          ?? "—")} />
              </div>
              <ForecastViz result={globalResult} valueKey="index" stroke="#38bdf8" />
              <p className="opacity-80 leading-relaxed">{globalResult.narrative?.summary}</p>
              {!!globalResult.policy_calendar?.length && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest opacity-50 mb-1">
                    政策调整时间点
                  </div>
                  <ul className="space-y-1.5">
                    {globalResult.policy_calendar.map((c: any, i: number) => (
                      <li key={i} className="rounded border border-stone-800 px-2 py-1.5">
                        <span className="text-amber-200">{c.when}</span>
                        <span className="opacity-50"> · {c.urgency}</span>
                        <div className="text-cyan-100/90">{c.action}</div>
                        <div className="text-[10px] opacity-50">{c.reason}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {!!globalResult.narrative?.policy_notes?.length && (
                <ul className="list-disc pl-4 opacity-80 space-y-0.5">
                  {globalResult.narrative.policy_notes.map((n: string, i: number) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              )}
              <p className="text-[10px] opacity-40">{globalResult.disclaimer}</p>
            </div>
          )}
        </div>
      )}

      {tab === "city" && (
        <div className="space-y-3">
          <p className="text-[12px] opacity-70 leading-relaxed">
            基于 {cityName} 本地信贷、地产、就业与流动性，推演城市金融周期与政策响应点。
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <label className="text-[11px] opacity-80 space-y-1">
              选择城市
              <select value={cityKey || cities[0]?.key || ""} onChange={(e) => setCityKey(e.target.value)}
                      className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
                {cities.map((c) => (
                  <option key={c.key} value={c.key}>{c.name}</option>
                ))}
              </select>
            </label>
          </div>
          {cities.find((c) => c.key === cityKey)?.description && (
            <p className="text-[10px] opacity-50">{cities.find((c) => c.key === cityKey)?.description}</p>
          )}

          {cityResult && (
            <div className="space-y-2 text-[12px]">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <Metric label="展望" value={cityResult.narrative?.outlook || "—"} />
                <Metric label="城市指数"
                        value={String(cityResult.forecast?.at(-1)?.city_index?.toFixed?.(1) ?? "—")} />
                <Metric label="地产指数"
                        value={String(cityResult.forecast?.at(-1)?.property_index?.toFixed?.(1) ?? "—")} />
                <Metric label="就业率"
                        value={cityResult.forecast?.at(-1)?.employment != null
                          ? `${(cityResult.forecast.at(-1).employment * 100).toFixed(0)}%` : "—"} />
              </div>
              <ForecastViz result={cityResult} valueKey="city_index" stroke="#c084fc" />
              <p className="opacity-80 leading-relaxed">{cityResult.narrative?.summary}</p>
              {!!cityResult.narrative?.policy_notes?.length && (
                <ul className="list-disc pl-4 opacity-80 space-y-0.5">
                  {cityResult.narrative.policy_notes.map((n: string, i: number) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              )}
              <p className="text-[10px] opacity-40">{cityResult.disclaimer}</p>
            </div>
          )}
        </div>
      )}

      {tab === "corporate" && (
        <div className="space-y-3">
          <p className="text-[12px] opacity-70 leading-relaxed">
            选择文明典型企业与单位（不含自然人），在关键节点插入事件，推演股价并给出融资建议。
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
            <label className="space-y-1 opacity-80">
              评估对象
              <select value={companyKey || companies[0]?.key || ""} onChange={(e) => setCompanyKey(e.target.value)}
                      className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
                {enterpriseOptions.length > 0 && (
                  <optgroup label="企业">
                    {enterpriseOptions.map((c) => (
                      <option key={c.key} value={c.key}>
                        {c.name}{c.sector ? ` · ${c.sector}` : ""}
                      </option>
                    ))}
                  </optgroup>
                )}
                {unitOptions.length > 0 && (
                  <optgroup label="单位">
                    {unitOptions.map((c) => (
                      <option key={c.key} value={c.key}>
                        {c.name}{c.sector ? ` · ${c.sector}` : ""}
                      </option>
                    ))}
                  </optgroup>
                )}
                {enterpriseOptions.length === 0 && unitOptions.length === 0 && companies.map((c) => (
                  <option key={c.key} value={c.key}>
                    {c.name}{c.sector ? ` · ${c.sector}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <input value={company} onChange={(e) => setCompany(e.target.value)}
                   placeholder="自定义名称（可选）"
                   className="bg-stone-950 border border-stone-700 rounded px-2 py-1" />
            <input value={sector} onChange={(e) => setSector(e.target.value)}
                   placeholder={`行业（默认 ${selectedCompany?.sector || "—"}）`}
                   className="bg-stone-950 border border-stone-700 rounded px-2 py-1" />
          </div>
          {selectedCompany?.description && (
            <p className="text-[10px] opacity-50">{selectedCompany.description}</p>
          )}

          {corpResult && (
            <div className="space-y-2 text-[12px]">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                <Metric label="企业" value={corpResult.company?.name || "—"} />
                <Metric label="预期收益%"
                        value={`${(corpResult.expected_return_pct ?? 0) >= 0 ? "+" : ""}${corpResult.expected_return_pct ?? "—"}`} />
                <Metric label="期末价"
                        value={String(corpResult.forecast?.at?.(-1)?.price
                          ?? corpResult.forecast?.[corpResult.forecast.length - 1]?.price
                          ?? "—")} />
              </div>
              <ForecastViz result={corpResult} valueKey="price" stroke="#a3e635" />
              <p className="opacity-80">{corpResult.narrative?.summary}</p>
              <div className="text-[10px] uppercase tracking-widest opacity-50">融资建议</div>
              <ul className="list-disc pl-4 space-y-0.5 opacity-85">
                {(corpResult.narrative?.financing || []).map((x: string, i: number) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
              <p className="text-[10px] opacity-40">{corpResult.disclaimer}</p>
            </div>
          )}
        </div>
      )}

      {tab === "retail" && (
        <div className="space-y-3">
          <p className="text-[12px] opacity-70 leading-relaxed">
            普通企业与个人量化沙盘：比较短/长期持仓，给出适合期限与预估收益（合成路径）。
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
            <label className="space-y-1">
              风险偏好
              <select value={risk} onChange={(e) => setRisk(e.target.value as typeof risk)}
                      className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
                <option value="conservative">稳健</option>
                <option value="balanced">均衡</option>
                <option value="aggressive">进取</option>
              </select>
            </label>
            <label className="space-y-1">
              期限偏好
              <select value={retailHorizon}
                      onChange={(e) => setRetailHorizon(e.target.value as typeof retailHorizon)}
                      className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
                <option value="auto">自动推荐</option>
                <option value="short">强制短期</option>
                <option value="long">强制长期</option>
              </select>
            </label>
            <label className="space-y-1">
              本金
              <input type="number" min={1000} value={capital}
                     onChange={(e) => setCapital(Number(e.target.value) || 1000)}
                     className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1" />
            </label>
          </div>

          {retailResult && (
            <div className="space-y-2 text-[12px]">
              <div className="rounded-lg border border-emerald-800/40 bg-emerald-950/20 p-2">
                <div className="text-emerald-200 font-serif">
                  建议：{retailResult.recommendation?.horizon_label}
                </div>
                <div className="opacity-80 mt-1">{retailResult.recommendation?.rationale}</div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <Metric label="预估收益%"
                        value={`${retailResult.recommendation?.expected_return_pct ?? "—"}`} />
                <Metric label="期末资产"
                        value={`${retailResult.recommendation?.expected_end_value ?? "—"}`} />
                <Metric label="最大回撤%"
                        value={`${retailResult.recommendation?.max_drawdown_pct ?? "—"}`} />
                <Metric label="波动%"
                        value={`${retailResult.recommendation?.vol_pct ?? "—"}`} />
              </div>
              <Sparkline
                values={retailResult.recommendation?.horizon === "short"
                  ? (retailResult.paths?.short || [])
                  : (retailResult.paths?.long || [])}
                stroke="#fbbf24"
              />
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead className="opacity-50 text-left">
                    <tr>
                      <th className="py-1">策略</th>
                      <th>短期收益</th>
                      <th>长期收益</th>
                      <th>短期回撤</th>
                      <th>长期回撤</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(retailResult.comparison || {}).map(([k, v]: [string, any]) => (
                      <tr key={k} className="border-t border-stone-800/80">
                        <td className="py-1.5">{v.label}</td>
                        <td>{v.short_return_pct}%</td>
                        <td>{v.long_return_pct}%</td>
                        <td>{v.short_mdd_pct}%</td>
                        <td>{v.long_mdd_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[10px] opacity-40">{retailResult.disclaimer}</p>
            </div>
          )}
        </div>
      )}

      {tab === "market" && finance && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
            <Metric label="物价指数" value={finance.price_index.toFixed(1)} />
            <Metric label="时序通胀%" value={`${finance.inflation >= 0 ? "+" : ""}${finance.inflation.toFixed(2)}`} />
            <Metric label="货币存量" value={finance.money_supply.toFixed(0)} />
            <Metric label="基尼" value={finance.gini.toFixed(3)} />
          </div>
          <Sparkline values={indexSeries} />
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead className="opacity-50 text-left">
                <tr>
                  <th className="py-1">商品</th><th>现价</th><th>相对基价</th><th>库存</th>
                </tr>
              </thead>
              <tbody>
                {finance.goods.map((g) => (
                  <tr key={g.id} className="border-t border-stone-800/80">
                    <td className="py-1.5 text-cyan-100">{g.name}</td>
                    <td>{g.price.toFixed(2)}</td>
                    <td className={g.change_pct >= 0 ? "text-rose-300" : "text-emerald-300"}>
                      {g.change_pct >= 0 ? "+" : ""}{g.change_pct.toFixed(1)}%
                    </td>
                    <td>{g.inventory.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rounded-lg border border-stone-800 p-2 space-y-2 text-[11px]">
            <div className="text-[10px] opacity-50">市场清算参数</div>
            <label className="flex items-center gap-2">
              快进时数
              <input type="number" min={1} max={168} value={steps}
                     onChange={(e) => setSteps(Number(e.target.value) || 1)}
                     className="w-20 bg-stone-950 border border-stone-700 rounded px-2 py-1" />
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
              <label className="space-y-1">
                冲击类型
                <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}
                        className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
                  <option value="demand">需求</option>
                  <option value="supply">供给</option>
                  <option value="price">价格</option>
                </select>
              </label>
              <label className="space-y-1">
                商品
                <select value={goodId} onChange={(e) => setGoodId(e.target.value)}
                        className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1">
                  <option value="*">全部</option>
                  {finance.goods.map((g) => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                强度
                <input type="number" step={0.05} min={0.05} max={1.5} value={magnitude}
                       onChange={(e) => setMagnitude(Number(e.target.value) || 0.4)}
                       className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1" />
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              {standalone && labId ? (
                <>
                  <button type="button" disabled={busy}
                          onClick={() => wrap(async () => {
                            const j = await labWsFinanceShock(labId, {
                              kind, good_id: goodId, magnitude,
                            });
                            applyResponse(j);
                            setMsg("已注入市场冲击");
                          })}
                          className="px-2 py-1 rounded border border-amber-600/50 disabled:opacity-40">
                    注入冲击
                  </button>
                  <button type="button" disabled={busy}
                          onClick={() => wrap(async () => {
                            const j = await labWsAdvanceFinance(labId, steps);
                            applyResponse(j);
                            setMsg(`市场快进 ${steps} 步`);
                          })}
                          className="px-2 py-1 rounded border border-cyan-600/50 disabled:opacity-40">
                    快进 {steps} 步
                  </button>
                </>
              ) : sid ? (
                <>
                  <button type="button" disabled={busy}
                          onClick={() => wrap(async () => {
                            const j = await financeShock(sid, { kind, good_id: goodId, magnitude });
                            applyResponse(j);
                            setMsg("已注入市场冲击");
                          })}
                          className="px-2 py-1 rounded border border-amber-600/50 disabled:opacity-40">
                    注入冲击
                  </button>
                  <button type="button" disabled={busy}
                          onClick={() => wrap(async () => {
                            const j = await advanceFinance(sid, steps);
                            applyResponse(j);
                            setMsg(`市场快进 ${steps} 步`);
                          })}
                          className="px-2 py-1 rounded border border-cyan-600/50 disabled:opacity-40">
                    快进 {steps} 步
                  </button>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {tab === "market" && !finance && (
        <p className="text-[12px] opacity-50">请新建会话以初始化市场清算引擎。</p>
      )}

      {(() => {
        const sim = activeTabResult(tab, globalResult, cityResult, corpResult, retailResult, finance);
        const audit = sim?.audit_trail || sim?.event_log;
        if (!audit?.length && !sim?.methodology) return null;
        if (tab === "retail" && !audit?.length) return null;
        return (
          <AuditTrailPanel
            auditTrail={sim?.audit_trail}
            eventLog={sim?.event_log}
            methodology={sim?.methodology}
            calibration={(sim?.calibration as Record<string, unknown>) || calibration}
            compact={compact}
          />
        );
      })()}

      {standalone && labId && (
        <div className="rounded-lg border border-cyan-700/40 bg-cyan-950/20 p-3 space-y-2">
          <div className="flex flex-wrap gap-3 items-end">
            <label className="text-[11px] opacity-80 space-y-1">
              推演步数
              <input type="number" min={4} max={120} value={horizon}
                     onChange={(e) => setHorizon(Number(e.target.value) || 24)}
                     className="block w-24 bg-stone-950 border border-stone-700 rounded px-2 py-1" />
            </label>
            <label className="flex items-center gap-2 text-[11px] opacity-75 pb-1">
              <input type="checkbox" checked={skipLlm}
                     onChange={(e) => setSkipLlm(e.target.checked)}
                     className="rounded border-stone-600" />
              快速推演（跳过 LLM 润色）
            </label>
            <button type="button" disabled={busy}
                    onClick={runUnifiedSimulate}
                    className="flex-1 min-w-[200px] py-2.5 rounded bg-cyan-500 text-stone-950 text-[13px]
                               font-bold disabled:opacity-40 hover:bg-cyan-400 transition">
              开始推演 · 生成完整报告（{tabModeLabel}）
            </button>
          </div>
          {simPhase && <SimulationProgress phase={simPhase} />}
          <p className="text-[10px] opacity-45">
            上传或手动输入的事件将综合文明背景逐步推演，完成后展示曲线、表格、分布图与终结结论，并可下载 PDF。
          </p>
        </div>
      )}

      {report && standalone && (
        <LabReportView
          report={report}
          animate={reportAnimate}
          pdfBase64={pdfBase64}
          pdfFilename={pdfFilename}
        />
      )}

      {(msg || err) && (
        <div className={`text-[11px] ${err ? "text-rose-300" : "text-emerald-300/90"}`}>
          {err || msg}
        </div>
      )}
    </div>
  );
}
