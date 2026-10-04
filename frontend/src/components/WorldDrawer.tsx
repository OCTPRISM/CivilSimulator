"use client";

import { useMemo } from "react";
import type { Agent, Session } from "@/lib/api";
import CivilizationDashboard from "@/components/CivilizationDashboard";

type Props = {
  open: boolean;
  onClose: () => void;
  session: Session;
  tensionCurve?: number[];
};

/** Side drawer: world overview + agent relation graph + tension curve. */
export default function WorldDrawer({ open, onClose, session, tensionCurve = [] }: Props) {
  const { nodes, links } = useMemo(() => buildGraph(session.agents), [session.agents]);

  return (
    <>
      {/* backdrop */}
      <div
        onClick={onClose}
        className={`fixed inset-0 bg-black/60 z-40 transition-opacity ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />
      <aside
        className={`fixed top-0 right-0 h-full w-[420px] max-w-[90vw] z-50
                    bg-stone-950/95 border-l border-stone-700
                    shadow-2xl transition-transform duration-300
                    ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="flex items-center justify-between p-4 border-b border-stone-800">
          <div>
            <div className="font-serif text-lg">{session.world.name}</div>
            <div className="text-xs opacity-60 uppercase tracking-widest">
              {session.world.genre} · tick {session.world.clock?.tick ?? 0}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-amber-300 text-2xl leading-none"
            aria-label="关闭"
          >
            ×
          </button>
        </div>

        <div className="overflow-y-auto h-[calc(100%-64px)] p-4 space-y-6 text-sm">
          {session.seed_key && (
            <CivilizationDashboard seedKey={session.seed_key} compact />
          )}

          {/* premise */}
          <Section title="世界设定">
            <p className="opacity-85 leading-relaxed">{session.world.premise}</p>
          </Section>

          {/* tension curve */}
          {tensionCurve.length > 0 && (
            <Section title="剧情张力曲线">
              <Sparkline values={tensionCurve} />
            </Section>
          )}

          {/* relation graph */}
          <Section title="关系图">
            <RelationGraph nodes={nodes} links={links} agents={session.agents} />
          </Section>

          {/* agents */}
          <Section title="在场角色">
            <ul className="space-y-2">
              {session.agents.map((a) => (
                <li
                  key={a.id}
                  className={`p-2 rounded border ${
                    a.id === session.player_id
                      ? "border-amber-500/70 bg-amber-500/5"
                      : "border-stone-800"
                  }`}
                >
                  <div className="flex justify-between">
                    <span className="font-serif">{a.name}</span>
                    <span className="opacity-60 text-xs">
                      {a.kind === "player" ? "玩家" : "NPC"}
                    </span>
                  </div>
                  <div className="opacity-70 text-xs mt-1 leading-relaxed">
                    {a.persona}
                  </div>
                  {a.traits?.length ? (
                    <div className="opacity-50 text-[11px] mt-1">
                      {a.traits.join(" · ")}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </Section>

          {/* locations & factions */}
          <Section title="世界结构">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <div className="opacity-60 mb-1">地点</div>
                <ul className="space-y-1">
                  {session.world.locations?.map((l: any) => (
                    <li key={l.id} className="opacity-90">· {l.name}</li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="opacity-60 mb-1">派系</div>
                <ul className="space-y-1">
                  {session.world.factions?.map((f: any) => (
                    <li key={f.id} className="opacity-90">· {f.name}</li>
                  ))}
                </ul>
              </div>
            </div>
          </Section>
        </div>
      </aside>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-xs uppercase tracking-widest opacity-60 mb-2">{title}</h3>
      {children}
    </section>
  );
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const w = 360, h = 60, pad = 4;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = pad + (i * (w - 2 * pad)) / Math.max(1, values.length - 1);
    const y = h - pad - ((v - min) / range) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg width={w} height={h} className="w-full">
      <polyline
        fill="none"
        stroke="rgba(245,158,11,0.9)"
        strokeWidth={2}
        points={pts.join(" ")}
      />
      <line x1={0} y1={h - pad} x2={w} y2={h - pad}
            stroke="rgba(255,255,255,0.1)" />
    </svg>
  );
}

type Node = { id: string; name: string; isPlayer: boolean; x: number; y: number };
type Link = { from: string; to: string; weight: number };

function buildGraph(agents: Agent[]): { nodes: Node[]; links: Link[] } {
  // simple circular layout
  const r = 110;
  const cx = 180, cy = 130;
  const nodes: Node[] = agents.map((a, i) => {
    const t = (i / Math.max(1, agents.length)) * Math.PI * 2;
    return {
      id: a.id,
      name: a.name,
      isPlayer: a.kind === "player",
      x: cx + Math.cos(t) * r,
      y: cy + Math.sin(t) * r,
    };
  });
  const links: Link[] = [];
  for (const a of agents) {
    for (const [other, w] of Object.entries(a.relations || {})) {
      if (Math.abs(w as number) < 0.05) continue;
      links.push({ from: a.id, to: other, weight: w as number });
    }
  }
  return { nodes, links };
}

function RelationGraph({ nodes, links, agents }:
  { nodes: Node[]; links: Link[]; agents: Agent[] }) {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  return (
    <svg width={360} height={260} className="w-full">
      {links.map((l, i) => {
        const a = byId[l.from], b = byId[l.to];
        if (!a || !b) return null;
        const color = l.weight >= 0
          ? `rgba(16,185,129,${Math.min(1, 0.3 + Math.abs(l.weight))})`
          : `rgba(244,63,94,${Math.min(1, 0.3 + Math.abs(l.weight))})`;
        return (
          <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={color} strokeWidth={1 + Math.abs(l.weight) * 2} />
        );
      })}
      {nodes.map((n) => (
        <g key={n.id}>
          <circle cx={n.x} cy={n.y} r={n.isPlayer ? 9 : 6}
                  fill={n.isPlayer ? "#f59e0b" : "#a78bfa"}
                  stroke="rgba(255,255,255,0.3)" />
          <text x={n.x} y={n.y - 12} textAnchor="middle"
                className="fill-stone-200" fontSize="11">
            {n.name}
          </text>
        </g>
      ))}
      {nodes.length === 0 && (
        <text x={180} y={130} textAnchor="middle" className="fill-stone-500" fontSize="12">
          （暂无关系数据）
        </text>
      )}
    </svg>
  );
}
