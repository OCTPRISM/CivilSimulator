"use client";

/**
 * WorldAtlas — fixed-page flipbook showing world overview, injection chronicle
 * & stat dashboards.
 *
 * Pages (always 8 — fixed count avoids react-pageflip insertBefore bug):
 *   1. Cover
 *   2. 概况
 *   3. 世情纪事（注入的事件 / 角色）
 *   4. 政治
 *   5. 经济
 *   6. 民生
 *   7. 军事
 *   8. Back cover
 */

import dynamic from "next/dynamic";
import { forwardRef, useMemo } from "react";
import type { Agent, ScheduledInjection, Session, WorldStats } from "@/lib/api";

const HTMLFlipBook: any = dynamic(() => import("react-pageflip"), { ssr: false });

type Props = {
  session: Session;
  stats?: WorldStats;
};

export default function WorldAtlas({ session, stats }: Props) {
  const injections = session.injections || [];
  const agents = session.agents || [];
  const clockTick = session.world?.clock?.tick ?? 0;

  const latestInjection = useMemo(
    () => pickLatestHighlight(injections, agents, clockTick),
    [injections, agents, clockTick],
  );

  return (
    <HTMLFlipBook
      key="atlas-v2"
      width={340}
      height={460}
      size="stretch"
      minWidth={260}
      maxWidth={400}
      minHeight={360}
      maxHeight={540}
      maxShadowOpacity={0.45}
      showCover={true}
      mobileScrollSupport={true}
      usePortrait={false}
      drawShadow={true}
      flippingTime={650}
      useMouseEvents={true}
      className="shadow-2xl"
    >
      <Cover title={session.world?.name || ""} genre={session.world?.genre || ""} />
      <Overview session={session} latest={latestInjection} />
      <Chronicle
        injections={injections}
        agents={agents}
        locations={session.world?.locations || []}
        clockTick={clockTick}
      />
      <StatPage title="政治"
                metric={stats?.politics ?? 60}
                history={(stats?.history || []).map((h) => h.politics)}
                summary={stats?.summary?.politics || "—"}
                tone="indigo" />
      <StatPage title="经济"
                metric={stats?.economy ?? 55}
                history={(stats?.history || []).map((h) => h.economy)}
                summary={stats?.summary?.economy || "—"}
                tone="emerald" />
      <StatPage title="民生"
                metric={stats?.livelihood ?? 60}
                history={(stats?.history || []).map((h) => h.livelihood)}
                summary={stats?.summary?.livelihood || "—"}
                tone="amber" />
      <StatPage title="军事"
                metric={stats?.military ?? 40}
                history={(stats?.history || []).map((h) => h.military)}
                summary={stats?.summary?.military || "—"}
                tone="rose" />
      <BackCover injectionCount={injections.length} />
    </HTMLFlipBook>
  );
}

type Highlight = {
  kind: "event" | "character";
  tick: number;
  title: string;
  body: string;
  status: "pending" | "fired";
};

function pickLatestHighlight(
  injections: ScheduledInjection[],
  agents: Agent[],
  clockTick: number,
): Highlight | null {
  if (!injections.length) return null;
  const sorted = [...injections].sort((a, b) => b.tick - a.tick || Number(b.fired) - Number(a.fired));
  const inj = sorted[0];
  return injectionToHighlight(inj, agents, clockTick);
}

function injectionToHighlight(
  inj: ScheduledInjection,
  agents: Agent[],
  clockTick: number,
): Highlight {
  const p = inj.payload || {};
  const pending = !inj.fired && inj.tick > clockTick;
  if (inj.kind === "character") {
    const ag = agents.find((a) => a.id === p.agent_id);
    const name = String(ag?.name || p.name || "来客");
    return {
      kind: "character",
      tick: inj.tick,
      title: name,
      body: String(ag?.persona || p.persona || "来历不明"),
      status: pending ? "pending" : "fired",
    };
  }
  return {
    kind: "event",
    tick: inj.tick,
    title: "异变",
    body: String(p.summary || "（未记述）"),
    status: pending ? "pending" : "fired",
  };
}

function locName(locations: { id: string; name: string }[], id: unknown): string {
  if (!id || typeof id !== "string") return "";
  return locations.find((l) => l.id === id)?.name || "";
}

const Cover = forwardRef<HTMLDivElement, { title: string; genre: string }>(
  function Cover({ title, genre }, ref) {
    return (
      <div ref={ref} className="page p-6 flex flex-col items-center justify-center">
        <div className="text-[10px] uppercase tracking-[0.3em] opacity-60">
          World Atlas
        </div>
        <div className="font-serif text-2xl mt-3 text-center">《{title}》</div>
        <div className="ink-rule w-2/3 my-4" />
        <div className="text-xs opacity-70 uppercase tracking-widest">{genre}</div>
        <div className="mt-auto text-[11px] opacity-60">— 翻 页 阅 览 —</div>
      </div>
    );
  });

const Overview = forwardRef<HTMLDivElement, {
  session: Session;
  latest: Highlight | null;
}>(function Overview({ session, latest }, ref) {
  const w = session.world || {};
  const pending = (session.injections || []).filter((i) => !i.fired).length;
  return (
    <div ref={ref} className="page p-5 text-sm leading-relaxed">
      <h3 className="font-serif text-lg mb-2">世界概况</h3>
      <div className="ink-rule mb-3" />
      <p className="text-[12px] opacity-85">{w.premise}</p>
      <div className="mt-3 text-[11px] opacity-70 space-y-1">
        <div>纪年：{w.clock?.era} · 第 {w.clock?.tick} 时</div>
        <div>地点：{(w.locations || []).map((l: { name: string }) => l.name).join(" · ")}</div>
        <div>势力：{(w.factions || []).map((f: { name: string }) => f.name).join(" · ") || "（散漫无主）"}</div>
        {pending > 0 && (
          <div className="text-amber-300/90 pt-1">
            书册纪事：{pending} 条待触发（见下一页）
          </div>
        )}
      </div>
      {latest && (
        <div className="mt-4 p-2.5 rounded border border-stone-700/80 bg-stone-950/40">
          <div className="text-[10px] uppercase tracking-widest opacity-50 mb-1">
            最新纪事
          </div>
          <div className="text-[11px] text-amber-200/90">
            {latest.status === "pending" ? "待触发" : "已载入"} · 第 {latest.tick} 时
            {latest.kind === "character" ? " · 人物" : " · 事件"}
          </div>
          <div className="font-serif text-sm mt-0.5">{latest.title}</div>
          <p className="text-[11px] opacity-75 mt-1 line-clamp-3">{latest.body}</p>
        </div>
      )}
    </div>
  );
});

const Chronicle = forwardRef<HTMLDivElement, {
  injections: ScheduledInjection[];
  agents: Agent[];
  locations: { id: string; name: string }[];
  clockTick: number;
}>(function Chronicle({ injections, agents, locations, clockTick }, ref) {
  const sorted = useMemo(() => {
    return [...injections].sort((a, b) => {
      // pending first (soonest tick), then fired (newest first)
      const ap = !a.fired ? 0 : 1;
      const bp = !b.fired ? 0 : 1;
      if (ap !== bp) return ap - bp;
      return a.fired === b.fired ? a.tick - b.tick : b.tick - a.tick;
    });
  }, [injections]);

  return (
    <div ref={ref} className="page p-4 text-sm leading-relaxed flex flex-col">
      <h3 className="font-serif text-lg mb-1">世情纪事</h3>
      <div className="text-[10px] opacity-50 mb-2">注入的事件与人物</div>
      <div className="ink-rule mb-2" />
      {sorted.length === 0 ? (
        <p className="text-[12px] opacity-50 mt-4 text-center">
          此书册尚无自定义纪事。<br />
          在左侧注入事件或角色后，将同步誊录于此。
        </p>
      ) : (
        <ul className="flex-1 overflow-y-auto space-y-2.5 pr-1 text-[11px]">
          {sorted.map((inj) => (
            <ChronicleEntry
              key={inj.id}
              inj={inj}
              agents={agents}
              locations={locations}
              clockTick={clockTick}
            />
          ))}
        </ul>
      )}
    </div>
  );
});

function ChronicleEntry({
  inj, agents, locations, clockTick,
}: {
  inj: ScheduledInjection;
  agents: Agent[];
  locations: { id: string; name: string }[];
  clockTick: number;
}) {
  const p = inj.payload || {};
  const isPending = !inj.fired && inj.tick > clockTick;
  const isDue = !inj.fired && inj.tick <= clockTick;
  const status = inj.fired ? "已载入" : isDue ? "待落地" : "待触发";
  const statusTone = inj.fired
    ? "text-emerald-300/90 border-emerald-700/50"
    : isDue
      ? "text-amber-300/90 border-amber-700/50"
      : "text-sky-300/90 border-sky-700/50";

  if (inj.kind === "character") {
    const ag = agents.find((a) => a.id === p.agent_id);
    const name = String(ag?.name || p.name || "来客");
    const persona = String(ag?.persona || p.persona || "");
    const profession = String(ag?.profession || p.profession || "");
    const avatar = String(ag?.avatar || p.avatar || "👤");
    const where = locName(locations, ag?.location_id || p.location_id);

    return (
      <li className={`rounded-md border px-2.5 py-2 bg-stone-950/50 ${statusTone.split(" ")[1]}`}>
        <div className="flex items-start gap-2">
          <div className="text-xl shrink-0">{avatar}</div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[10px] px-1 rounded border ${statusTone}`}>{status}</span>
              <span className="opacity-50">第 {inj.tick} 时 · 人物</span>
            </div>
            <div className="font-serif text-amber-100 text-sm mt-0.5">{name}</div>
            {profession && (
              <div className="text-[10px] opacity-60">{profession}</div>
            )}
            <p className="opacity-80 mt-1 line-clamp-3 leading-snug">{persona}</p>
            {where && (
              <div className="text-[10px] opacity-50 mt-1">现身 · {where}</div>
            )}
          </div>
        </div>
      </li>
    );
  }

  const summary = String(p.summary || "（未记述）");
  const where = locName(locations, p.location_id);

  return (
    <li className={`rounded-md border px-2.5 py-2 bg-stone-950/50 ${statusTone.split(" ")[1]}`}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-[10px] px-1 rounded border ${statusTone}`}>{status}</span>
        <span className="opacity-50">第 {inj.tick} 时 · 事件</span>
      </div>
      <div className="font-serif text-amber-100 text-sm mt-1">📜 异变录</div>
      <p className="opacity-85 mt-1 line-clamp-4 leading-snug">{summary}</p>
      {where && (
        <div className="text-[10px] opacity-50 mt-1">发生于 · {where}</div>
      )}
    </li>
  );
}

const TONE: Record<string, { bar: string; text: string; line: string }> = {
  indigo:  { bar: "bg-indigo-400",  text: "text-indigo-300",  line: "#a5b4fc" },
  emerald: { bar: "bg-emerald-400", text: "text-emerald-300", line: "#6ee7b7" },
  amber:   { bar: "bg-amber-400",   text: "text-amber-300",   line: "#fcd34d" },
  rose:    { bar: "bg-rose-400",    text: "text-rose-300",    line: "#fda4af" },
};

const StatPage = forwardRef<HTMLDivElement, {
  title: string; metric: number; history: number[]; summary: string;
  tone: keyof typeof TONE;
}>(function StatPage({ title, metric, history, summary, tone }, ref) {
  const t = TONE[tone];
  const w = 280, h = 80;
  const pts = (history.length ? history : [metric]).slice(-32);
  const poly = pts
    .map((v, i) => {
      const x = (i / Math.max(1, pts.length - 1)) * w;
      const y = h - (v / 100) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div ref={ref} className="page p-5 text-sm leading-relaxed">
      <h3 className="font-serif text-lg mb-1">{title}</h3>
      <div className="ink-rule mb-3" />
      <div className="flex items-baseline gap-2">
        <div className={`text-3xl font-serif ${t.text}`}>{metric.toFixed(0)}</div>
        <div className="text-xs opacity-60">/ 100</div>
      </div>
      <div className="mt-2 h-2 w-full bg-stone-800 rounded overflow-hidden">
        <div className={`${t.bar} h-full`}
             style={{ width: `${Math.max(2, metric)}%` }} />
      </div>
      <svg className="mt-4" width={w} height={h}>
        <polyline fill="none" stroke={t.line} strokeWidth={2} points={poly} />
      </svg>
      <p className="mt-4 text-[12px] opacity-85">{summary}</p>
    </div>
  );
});

const BackCover = forwardRef<HTMLDivElement, { injectionCount: number }>(
  function BackCover({ injectionCount }, ref) {
    return (
      <div ref={ref} className="page p-6 flex flex-col items-center justify-center gap-2">
        <div className="text-xs opacity-60">未完待续…</div>
        {injectionCount > 0 && (
          <div className="text-[10px] opacity-45">
            纪事 {injectionCount} 条已誊录
          </div>
        )}
      </div>
    );
  });
