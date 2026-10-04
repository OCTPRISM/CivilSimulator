"use client";

import { useState } from "react";
import {
  labWsOpinionIntervene, labWsOpinionSimulate,
} from "@/lib/api";

type Props = { labId: string; opinion?: any; onUpdate: (o: any) => void };

export default function OpinionPanel({ labId, opinion, onUpdate }: Props) {
  const [topic, setTopic] = useState(opinion?.topic || "");
  const [steps, setSteps] = useState(24);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(opinion?.last_result || null);
  const interventions = opinion?.intervention_catalog || [];

  async function wrap(fn: () => Promise<void>) {
    setBusy(true);
    try { await fn(); } finally { setBusy(false); }
  }

  return (
    <div className="rounded-xl border border-violet-800/40 bg-stone-900/50 p-4 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-widest text-violet-300/80">舆情发酵实验室</div>
        <p className="text-[10px] opacity-50 mt-1">模拟议题潜伏期→爆发→峰值→反噬→衰减，并测试干预方式。</p>
      </div>
      <input value={topic} onChange={(e) => setTopic(e.target.value)}
             placeholder="议题名称，如：土地改革草案"
             className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1.5 text-[12px]" />
      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-[11px] space-y-1">
          推演步数
          <input type="number" min={8} max={120} value={steps}
                 onChange={(e) => setSteps(Number(e.target.value) || 24)}
                 className="w-20 bg-stone-950 border border-stone-700 rounded px-2 py-1 block" />
        </label>
        <button type="button" disabled={busy}
                onClick={() => wrap(async () => {
                  const j = await labWsOpinionSimulate(labId, { steps, topic });
                  if (j.opinion) onUpdate(j.opinion);
                  setResult(j.result);
                })}
                className="px-3 py-1.5 rounded bg-violet-500/80 text-stone-950 text-[11px] font-semibold disabled:opacity-40">
          推演舆情周期
        </button>
      </div>
      <div className="text-[10px] opacity-60 uppercase tracking-widest">干预方式</div>
      <div className="flex flex-wrap gap-1">
        {interventions.map((i: any) => (
          <button key={i.key} type="button" disabled={busy}
                  onClick={() => wrap(async () => {
                    const j = await labWsOpinionIntervene(labId, i.key);
                    if (j.opinion) onUpdate(j.opinion);
                  })}
                  className="px-2 py-1 rounded border border-violet-700/50 text-[10px] hover:border-violet-400 disabled:opacity-40">
            {i.name}
          </button>
        ))}
      </div>
      {opinion && (
        <div className="grid grid-cols-3 gap-2 text-[11px]">
          <div className="rounded border border-stone-800 p-2">
            <div className="opacity-50">热度</div>
            <div className="text-violet-100">{(opinion.heat * 100).toFixed(0)}%</div>
          </div>
          <div className="rounded border border-stone-800 p-2">
            <div className="opacity-50">情绪</div>
            <div>{(opinion.sentiment * 100).toFixed(0)}</div>
          </div>
          <div className="rounded border border-stone-800 p-2">
            <div className="opacity-50">极化</div>
            <div>{(opinion.polarization * 100).toFixed(0)}%</div>
          </div>
        </div>
      )}
      {result?.phase && (
        <div className="text-[12px] border-t border-stone-800 pt-3">
          当前阶段：<span className="text-violet-200">{result.phase.name}</span>
          <p className="text-[11px] opacity-70 mt-1">{result.phase.desc}</p>
          {!!result.recommendations?.length && (
            <ul className="list-disc pl-4 mt-2 text-[11px] opacity-80">
              {result.recommendations.map((r: string, i: number) => <li key={i}>{r}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
