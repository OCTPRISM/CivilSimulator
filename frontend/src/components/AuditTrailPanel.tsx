"use client";

import { useState } from "react";

export type AuditStep = {
  step?: number;
  forecast?: boolean;
  equations?: string[];
  fusion?: {
    engine?: string;
    history_len?: number;
    corrections?: Record<string, {
      markov?: number;
      longrun?: number;
      fused?: number;
      weight_longrun?: number;
      delta?: number;
    }>;
    rationale?: string;
  };
  markov_outputs?: Record<string, unknown>;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, number>;
  events?: {
    title?: string;
    kind?: string;
    magnitude?: number;
    rationale?: string;
    channel_preview?: Record<string, number>;
  }[];
  institutions?: { name?: string; influence?: number; health?: number; capacity?: number }[];
  context?: {
    population_norm?: number;
    agriculture_index?: number;
    industry_index?: number;
    enterprise_revenue_index?: number;
    event_pressure?: number;
  };
  rationale?: string;
};

type Props = {
  auditTrail?: AuditStep[];
  eventLog?: AuditStep[];
  methodology?: Record<string, unknown>;
  calibration?: Record<string, unknown>;
  compact?: boolean;
};

function fmtObj(obj: Record<string, unknown> | undefined): string {
  if (!obj) return "—";
  return Object.entries(obj)
    .map(([k, v]) => {
      if (typeof v === "number") return `${k}=${v.toFixed?.(3) ?? v}`;
      if (typeof v === "object" && v) {
        const inner = Object.entries(v as Record<string, number>)
          .map(([ik, iv]) => `${ik}:${typeof iv === "number" ? iv.toFixed(3) : iv}`)
          .join(", ");
        return `${k}{${inner}}`;
      }
      return `${k}=${String(v)}`;
    })
    .join(" · ");
}

export default function AuditTrailPanel({
  auditTrail = [],
  eventLog = [],
  methodology,
  calibration,
  compact,
}: Props) {
  const [openStep, setOpenStep] = useState<number | null>(null);
  const rows = auditTrail.length ? auditTrail : eventLog;

  if (!rows.length && !methodology && !calibration) return null;

  const visible = compact ? rows.slice(-6) : rows;

  return (
    <div className="rounded-lg border border-stone-800 bg-stone-950/50 p-3 space-y-3">
      <div className="text-[10px] uppercase tracking-widest text-amber-300/70">
        推演审计链
      </div>

      {!!methodology && (
        <div className="text-[11px] opacity-75 leading-relaxed">
          <span className="opacity-50">引擎 </span>
          {String(methodology.engine || methodology.paradigm || "structured")}
          {methodology.disclaimer ? (
            <span className="block text-[10px] opacity-45 mt-0.5">{String(methodology.disclaimer)}</span>
          ) : null}
        </div>
      )}

      {!!calibration && Object.keys(calibration).length > 0 && (
        <div className="text-[10px] opacity-60 rounded border border-stone-800/80 px-2 py-1.5">
          <span className="text-violet-300/80">参数校准 </span>
          ρ={String((calibration as any).rho ?? "—")}
          {" · "}κ={String((calibration as any).kappa ?? "—")}
          {" · "}β={String((calibration as any).beta ?? "—")}
          {(calibration as any).method ? ` · ${(calibration as any).method}` : ""}
        </div>
      )}

      {!!visible.length && (
        <ul className="space-y-1 max-h-64 overflow-y-auto text-[11px]">
          {visible.map((row, i) => {
            const step = row.step ?? i;
            const isOpen = openStep === step;
            const out = row.outputs || {};
            return (
              <li key={`${step}-${i}`} className="rounded border border-stone-800/80">
                <button
                  type="button"
                  className="w-full text-left px-2 py-1.5 flex flex-wrap gap-x-2 gap-y-0.5 hover:bg-stone-900/60"
                  onClick={() => setOpenStep(isOpen ? null : step)}
                >
                  <span className="text-amber-200/90">T+{step}</span>
                  {out.index != null && <span>指数 {out.index.toFixed?.(1) ?? out.index}</span>}
                  {out.inflation != null && <span className="opacity-60">π {out.inflation}%</span>}
                  {out.risk != null && <span className="opacity-60">风险 {out.risk}</span>}
                  {!!row.events?.length && (
                    <span className="text-violet-300/70">{row.events.length} 事件</span>
                  )}
                </button>
                {isOpen && (
                  <div className="px-2 pb-2 space-y-1.5 border-t border-stone-800/60 pt-1.5 text-[10px] opacity-80">
                    {!!row.equations?.length && (
                      <div>
                        <div className="opacity-45 mb-0.5">方程</div>
                        <ul className="list-disc pl-4 space-y-0.5 font-mono text-[9px]">
                          {row.equations.map((eq, ei) => (
                            <li key={ei}>{eq}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {row.inputs && (
                      <div><span className="opacity-45">输入 </span>{fmtObj(row.inputs as Record<string, unknown>)}</div>
                    )}
                    {row.outputs && (
                      <div><span className="opacity-45">输出 </span>{fmtObj(row.outputs as Record<string, unknown>)}</div>
                    )}
                    {row.fusion?.corrections && Object.keys(row.fusion.corrections).length > 0 && (
                      <div className="space-y-0.5">
                        <div className="opacity-45">长程融合校正（Markov → 融合）</div>
                        {Object.entries(row.fusion.corrections).map(([k, c]) => (
                          <div key={k} className="font-mono text-[9px] opacity-70">
                            {k}: {c.markov} + {c.weight_longrun}×长程({c.longrun}) → {c.fused}
                          </div>
                        ))}
                        {row.fusion.rationale && (
                          <div className="opacity-50 text-[9px]">{row.fusion.rationale}</div>
                        )}
                      </div>
                    )}
                    {!!row.institutions?.length && (
                      <div className="space-y-0.5">
                        <div className="opacity-45">机构演化</div>
                        {row.institutions.slice(0, 3).map((inst, ei) => (
                          <div key={ei} className="font-mono text-[9px] opacity-60">
                            {inst.name}: inf Δ{inst.influence ?? "—"} hlth Δ{inst.health ?? "—"}
                          </div>
                        ))}
                      </div>
                    )}
                    {row.context && (
                      <div className="text-[9px] opacity-50 font-mono">
                        人口×{row.context.population_norm ?? "—"}
                        {" · "}农 {row.context.agriculture_index ?? "—"}
                        {" · "}工 {row.context.industry_index ?? "—"}
                        {" · "}企收 {row.context.enterprise_revenue_index ?? "—"}
                      </div>
                    )}
                    {!!row.events?.length && (
                      <div className="space-y-1">
                        <div className="opacity-45">事件通道</div>
                        {row.events.map((ev, ei) => (
                          <div key={ei} className="rounded bg-stone-900/50 px-1.5 py-1">
                            <span className="text-cyan-100/90">{ev.title || ev.kind}</span>
                            {ev.magnitude != null && <span className="opacity-50"> · mag {ev.magnitude}</span>}
                            {ev.rationale && <div className="opacity-60 mt-0.5">{ev.rationale}</div>}
                            {ev.channel_preview && (
                              <div className="opacity-50 font-mono text-[9px] mt-0.5">
                                {Object.entries(ev.channel_preview).map(([k, v]) => `${k}:${v}`).join(" ")}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
