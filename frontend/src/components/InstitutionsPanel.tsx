"use client";

export type FinanceInstitution = {
  key?: string;
  name: string;
  institution_type?: string;
  era_label?: string;
  roles?: string[];
  description?: string;
  influence?: number;
  health?: number;
  capacity?: number;
  throughput?: number;
  assets_index?: number;
  last_delta?: Record<string, unknown>;
  transmission?: Record<string, number>;
  base_transmission?: Record<string, number>;
};

type Props = {
  institutions?: FinanceInstitution[];
};

const TYPE_LABEL: Record<string, string> = {
  fiscal_regulator: "财政监管",
  central_bank: "中央银行",
  exchange: "交易所",
  guild: "行会/商帮",
  clearing: "清算",
  credit: "信贷",
  monopoly: "专卖",
  regulator: "监管",
};

export default function InstitutionsPanel({ institutions = [] }: Props) {
  if (!institutions.length) return null;

  return (
    <div className="rounded-lg border border-violet-800/30 bg-violet-950/10 p-3 space-y-2">
      <div className="text-[10px] uppercase tracking-widest text-violet-300/70">
        时代金融机构 · 动态演化
      </div>
      <p className="text-[10px] opacity-45 leading-relaxed">
        影响力、健康度与传导系数随人口、工农发展、企业营收、宏观周期与事件冲击逐步调整。
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {institutions.map((inst) => {
          const inf = inst.influence;
          const hlth = inst.health;
          const cap = inst.capacity;
          const delta = inst.last_delta as Record<string, number> | undefined;
          return (
          <div key={inst.key || inst.name} className="rounded border border-stone-800/80 px-2 py-1.5 text-[11px]">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-serif text-violet-100">{inst.name}</span>
              {inst.era_label && <span className="text-[10px] opacity-45">{inst.era_label}</span>}
            </div>
            {inst.institution_type && (
              <div className="text-[10px] text-violet-300/60 mt-0.5">
                {TYPE_LABEL[inst.institution_type] || inst.institution_type}
              </div>
            )}
            {(inf != null || hlth != null || cap != null) && (
              <div className="flex flex-wrap gap-2 mt-1 text-[10px]">
                {inf != null && (
                  <span className="text-cyan-200/80">影响力 {(inf * 100).toFixed(0)}%</span>
                )}
                {hlth != null && (
                  <span className="text-emerald-300/70">健康 {(hlth * 100).toFixed(0)}%</span>
                )}
                {cap != null && (
                  <span className="text-amber-200/70">容量 {(cap * 100).toFixed(0)}%</span>
                )}
                {inst.throughput != null && (
                  <span className="opacity-45">吞吐 {inst.throughput}</span>
                )}
              </div>
            )}
            {delta && (delta.influence || delta.health || delta.capacity) ? (
              <div className="text-[9px] opacity-50 mt-0.5 font-mono">
                Δ inf {delta.influence >= 0 ? "+" : ""}{delta.influence?.toFixed?.(3) ?? delta.influence}
                {" · "}hlth {delta.health >= 0 ? "+" : ""}{delta.health?.toFixed?.(3) ?? delta.health}
              </div>
            ) : null}
            {inst.description && <p className="opacity-65 mt-1 leading-relaxed">{inst.description}</p>}
            {!!inst.roles?.length && (
              <div className="flex flex-wrap gap-1 mt-1">
                {inst.roles.map((r) => (
                  <span key={r} className="text-[9px] px-1 py-0.5 rounded bg-stone-900/80 opacity-55">{r}</span>
                ))}
              </div>
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
}
