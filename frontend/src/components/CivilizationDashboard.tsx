"use client";

import { useEffect, useState } from "react";
import { getCivilizationDashboard, type CivilizationDashboard as DashboardData } from "@/lib/api";

type Props = {
  seedKey: string;
  compact?: boolean;
};

export default function CivilizationDashboard({ seedKey, compact }: Props) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!seedKey) return;
    getCivilizationDashboard(seedKey)
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, [seedKey]);

  if (err) {
    return <div className="text-sm text-red-400/80">{err}</div>;
  }
  if (!data) {
    return <div className="text-sm opacity-50">载入文明概览…</div>;
  }

  return (
    <div className={`rounded-xl border border-amber-800/30 bg-stone-900/40 p-4 space-y-4 ${compact ? "" : "max-w-3xl"}`}>
      <div>
        <div className="text-[11px] uppercase tracking-widest text-amber-300/80">文明 Dashboard</div>
        <h2 className="font-serif text-xl mt-1">{data.name}</h2>
        <p className="text-[12px] opacity-60 mt-1 leading-relaxed">{data.premise}</p>
        {data.era_label && (
          <span className="inline-block mt-2 text-[10px] px-2 py-0.5 rounded border border-stone-700 opacity-70">
            {data.era_label}
          </span>
        )}
      </div>

      {data.population_explanation && (
        <p className="text-[11px] opacity-70 leading-relaxed border-l-2 border-amber-700/50 pl-3">
          {data.population_explanation}
        </p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {data.metrics.map((m) => (
          <div key={m.key} className="rounded-lg border border-stone-800 px-2 py-1.5">
            <div className="text-[10px] opacity-50">{m.label}</div>
            <div className="font-serif text-sm text-amber-100">{m.display}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[12px]">
        <div className="space-y-2">
          <div className="text-[10px] uppercase tracking-widest opacity-50">当前状态</div>
          <div className="rounded-lg border border-stone-800 p-2 space-y-1">
            <div><span className="opacity-50">阶段</span> · {data.current_state.stage}</div>
            {data.current_state.government && (
              <div><span className="opacity-50">政体</span> · {data.current_state.government}</div>
            )}
            {data.current_state.operating_logic && (
              <div className="opacity-80 leading-relaxed">{data.current_state.operating_logic}</div>
            )}
          </div>
        </div>

        {!!data.factions.length && (
          <div className="space-y-2">
            <div className="text-[10px] uppercase tracking-widest opacity-50">主要势力</div>
            <ul className="space-y-1">
              {data.factions.slice(0, 5).map((f, i) => (
                <li key={i} className="rounded border border-stone-800 px-2 py-1">
                  <span className="text-amber-200">{f.name}</span>
                  {f.ideology && <span className="opacity-50 text-[11px]"> · {f.ideology}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {!!data.historical_events.length && (
        <div className="space-y-2">
          <div className="text-[10px] uppercase tracking-widest opacity-50">重大历史事件</div>
          <ul className="space-y-1.5">
            {data.historical_events.map((ev, i) => (
              <li key={i} className="rounded border border-stone-800 px-2 py-1.5 text-[11px]">
                {ev.era && <span className="text-amber-200/80">{ev.era} · </span>}
                <span className="font-medium">{ev.title}</span>
                {ev.description && <div className="opacity-60 mt-0.5">{ev.description}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
