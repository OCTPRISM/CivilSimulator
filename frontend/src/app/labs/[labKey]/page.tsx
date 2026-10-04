"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import CivilizationDashboard from "@/components/CivilizationDashboard";
import LabDatasetPanel from "@/components/LabDatasetPanel";
import LabReportView from "@/components/LabReportView";
import FinancePanel from "@/components/FinancePanel";
import OpinionPanel from "@/components/OpinionPanel";
import MilitaryPanel from "@/components/MilitaryPanel";
import PolicyPanel from "@/components/PolicyPanel";
import WeatherPanel from "@/components/WeatherPanel";
import EnvironmentPanel from "@/components/EnvironmentPanel";
import PopulationPanel from "@/components/PopulationPanel";
import CivilizationSelector from "@/components/CivilizationSelector";
import {
  getLabWorkspace, listLabs, openLab, rebindLab,
  type LabMeta, type LabReport, type LabWorkspace,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const READY_LABS = new Set(["finance", "weather", "policy", "environment", "opinion", "military", "population"]);

const UNIFIED_SIM_LABS = new Set(["finance", "military", "policy", "weather", "environment", "population"]);

export default function LabDetailPage() {
  const { labKey } = useParams<{ labKey: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [meta, setMeta] = useState<LabMeta | null>(null);
  const [ws, setWs] = useState<LabWorkspace | null>(null);
  const [civKey, setCivKey] = useState("modern");
  const [report, setReport] = useState<LabReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const latestCivRef = useRef(civKey);

  useEffect(() => {
    latestCivRef.current = civKey;
  }, [civKey]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!labKey) return;
    listLabs()
      .then((rows) => setMeta(rows.find((l) => l.key === labKey) || null))
      .catch(() => setMeta(null));
  }, [labKey]);

  useEffect(() => {
    if (!user || !labKey || !READY_LABS.has(labKey)) return;
    let cancelled = false;
    const requested = civKey;
    latestCivRef.current = requested;
    setBusy(true);
    openLab(labKey, requested)
      .then((w) => {
        if (!cancelled && latestCivRef.current === requested) {
          setWs(w);
          setCivKey(w.civilization_key || requested);
          setReport(w.last_report ?? null);
        }
      })
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [user, labKey]); // civKey changes handled by openLab in onCivChange

  async function onCivChange(key: string) {
    if (!labKey || !READY_LABS.has(labKey)) return;
    const current = ws?.civilization_key ?? civKey;
    if (key === current) return;
    latestCivRef.current = key;
    setBusy(true);
    setErr(null);
    try {
      const w = ws?.id
        ? await rebindLab(ws.id, key)
        : await openLab(labKey, key);
      if (latestCivRef.current !== key) return;
      setWs(w);
      setCivKey(w.civilization_key || key);
      setReport(w.last_report ?? null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "切换文明失败");
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">载入中…</main>;
  }

  const name = meta?.name || labKey;
  const ready = meta?.status === "ready" || READY_LABS.has(labKey || "");

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <Link href="/labs" className="text-[11px] opacity-50 hover:opacity-80">← 实验平台</Link>
          <h1 className="font-serif text-3xl tracking-wider mt-2">{name}</h1>
          {meta?.blurb && (
            <p className="text-sm opacity-60 mt-1 max-w-2xl leading-relaxed">{meta.blurb}</p>
          )}
        </div>

        {ready && (
          <CivilizationSelector
            value={ws?.civilization_key ?? civKey}
            onChange={onCivChange}
          />
        )}

        {ready && civKey && ws?.civilization_key === civKey && (
          <CivilizationDashboard seedKey={civKey} compact />
        )}

        {!ready && (
          <div className="rounded-xl border border-stone-700 bg-stone-950/50 p-8 text-center">
            <div className="font-serif text-xl opacity-90">建设中</div>
            <p className="text-sm opacity-60 mt-2">该实验室即将接入。</p>
          </div>
        )}

        {ready && (
          <div className="space-y-3">
            {busy && !ws && <p className="text-sm opacity-50">正在打开沙盘…</p>}
            {err && <p className="text-sm text-red-400">{err}</p>}

            {busy && ws && UNIFIED_SIM_LABS.has(labKey || "") && (
              <p className="text-sm opacity-50">正在切换文明沙盘…</p>
            )}

            {ws && labKey === "finance" && ws.civilization_key === civKey && (
              <FinancePanel
                key={ws.civilization_key}
                labId={ws.id}
                civilizationKey={ws.civilization_key}
                finance={ws.finance}
                financeLab={ws.finance_lab}
                timelineEvents={ws.timeline_events}
                lastReport={ws.last_report ?? report}
                onLabUpdate={(patch) => {
                  setWs((prev) => prev ? { ...prev, ...patch } : prev);
                  if (patch.last_report) setReport(patch.last_report);
                }}
              />
            )}
            {ws && labKey === "policy" && ws.civilization_key === civKey && (
              <PolicyPanel
                key={ws.civilization_key}
                labId={ws.id}
                civilizationKey={ws.civilization_key}
                policy={ws.policy}
                timelineEvents={ws.timeline_events}
                lastReport={ws.last_report ?? report}
                onUpdate={(p) => setWs((prev) => prev ? { ...prev, policy: p } : prev)}
                onLabUpdate={(patch) => {
                  setWs((prev) => prev ? { ...prev, ...patch } : prev);
                  if (patch.last_report) setReport(patch.last_report);
                }}
              />
            )}
            {ws && labKey === "weather" && ws.civilization_key === civKey && (
              <WeatherPanel
                key={ws.civilization_key}
                labId={ws.id}
                civilizationKey={ws.civilization_key}
                weather={ws.weather}
                timelineEvents={ws.timeline_events}
                lastReport={ws.last_report ?? report}
                onUpdate={(w) => setWs((prev) => prev ? { ...prev, weather: w } : prev)}
                onLabUpdate={(patch) => {
                  setWs((prev) => prev ? { ...prev, ...patch } : prev);
                  if (patch.last_report) setReport(patch.last_report);
                }}
              />
            )}
            {ws && labKey === "environment" && ws.civilization_key === civKey && (
              <EnvironmentPanel
                key={ws.civilization_key}
                labId={ws.id}
                civilizationKey={ws.civilization_key}
                environment={ws.environment}
                timelineEvents={ws.timeline_events}
                lastReport={ws.last_report ?? report}
                onUpdate={(e) => setWs((prev) => prev ? { ...prev, environment: e } : prev)}
                onLabUpdate={(patch) => {
                  setWs((prev) => prev ? { ...prev, ...patch } : prev);
                  if (patch.last_report) setReport(patch.last_report);
                }}
              />
            )}
            {ws && labKey === "opinion" && (
              <OpinionPanel labId={ws.id} opinion={ws.opinion}
                onUpdate={(o) => setWs((p) => p ? { ...p, opinion: o } : p)} />
            )}
            {ws && labKey === "military" && ws.civilization_key === civKey && (
              <MilitaryPanel
                key={ws.civilization_key}
                labId={ws.id}
                civilizationKey={ws.civilization_key}
                military={ws.military}
                timelineEvents={ws.timeline_events}
                lastReport={ws.last_report ?? report}
                onUpdate={(m) => setWs((p) => p ? { ...p, military: m } : p)}
                onLabUpdate={(patch) => {
                  setWs((prev) => prev ? { ...prev, ...patch } : prev);
                  if (patch.last_report) setReport(patch.last_report);
                }}
              />
            )}
            {ws && labKey === "population" && ws.civilization_key === civKey && (
              <PopulationPanel
                key={ws.civilization_key}
                labId={ws.id}
                civilizationKey={ws.civilization_key}
                population={ws.population}
                timelineEvents={ws.timeline_events}
                lastReport={ws.last_report ?? report}
                onUpdate={(pop) => setWs((p) => p ? { ...p, population: pop } : p)}
                onLabUpdate={(patch) => {
                  setWs((prev) => prev ? { ...prev, ...patch } : prev);
                  if (patch.last_report) setReport(patch.last_report);
                }}
              />
            )}

            {ws && !UNIFIED_SIM_LABS.has(labKey || "") && (
              <LabDatasetPanel
                labId={ws.id}
                labKey={labKey}
                timelineEvents={ws.timeline_events}
                lastReport={ws.last_report ?? report}
                onUpdate={(patch) => setWs((p) => p ? { ...p, ...patch } : p)}
                onReport={setReport}
              />
            )}

            {!UNIFIED_SIM_LABS.has(labKey || "") && (report || ws?.last_report) && (
              <LabReportView report={report || ws?.last_report || null} />
            )}

            {ws && (
              <button type="button" className="text-[11px] opacity-50 hover:opacity-80"
                      onClick={() => getLabWorkspace(ws.id).then(setWs).catch(() => undefined)}>
                刷新沙盘状态
              </button>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
