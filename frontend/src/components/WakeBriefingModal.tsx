"use client";

import type { WakeBriefing } from "@/lib/api";

type Props = {
  briefing: WakeBriefing;
  onClose: () => void;
};

export default function WakeBriefingModal({ briefing, onClose }: Props) {
  const isProxy = briefing.offline_mode === "proxy";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4
                    bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-amber-700/40
                      bg-stone-950 text-stone-100 shadow-2xl overflow-hidden">
        <div className="px-5 pt-5 pb-3 border-b border-stone-800">
          <div className="text-[10px] uppercase tracking-[0.2em] text-amber-500/80">
            {isProxy ? "归位 · 代行回顾" : "苏醒 · 残缺情报"}
          </div>
          <h2 className="font-serif text-xl text-amber-100 mt-1">
            {isProxy ? "你的角色并未停下" : "你错过了一些事情"}
          </h2>
          <p className="text-[12px] opacity-60 mt-1">
            {isProxy ? "自主行动约" : "休眠约"}{" "}
            {briefing.ticks_asleep} 时辰 · {briefing.clock_label}
            （tick {briefing.from_tick}→{briefing.to_tick}）
          </p>
        </div>

        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          <p className="font-serif text-[15px] leading-7 text-stone-200">
            {briefing.narrative}
          </p>

          {briefing.shards.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-widest opacity-50 mb-2">
                {isProxy ? "亲历片段" : "断片感知"}
              </div>
              <ul className="space-y-2">
                {briefing.shards.map((s, i) => (
                  <li key={`${s.tick}-${i}`}
                      className="text-[12px] border-l-2 border-stone-700 pl-2 leading-5">
                    <span className={`text-[10px] mr-1.5 ${
                      s.clarity === "lived" ? "text-emerald-400/80"
                        : s.clarity === "miss" ? "text-stone-500"
                          : s.clarity === "rumour" ? "text-sky-400/80"
                            : "text-amber-400/80"
                    }`}>
                      {s.clarity === "lived" ? "亲历"
                        : s.clarity === "miss" ? "空白"
                          : s.clarity === "rumour" ? "传闻"
                            : "断片"}
                    </span>
                    {s.perceived}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {briefing.npc_shifts.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-widest opacity-50 mb-2">
                人事挪移
              </div>
              <ul className="space-y-1 text-[12px] opacity-80">
                {briefing.npc_shifts.map((n, i) => (
                  <li key={i}>
                    {n.name}：{n.from} → {n.to}
                    {n.activity ? `（${n.activity}）` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {briefing.world_stats_hint && (
            <div className="text-[11px] opacity-55">
              宏观风向：{briefing.world_stats_hint}
            </div>
          )}
        </div>

        <div className="px-5 py-4 border-t border-stone-800 flex justify-end">
          <button onClick={onClose}
                  className="px-4 py-2 rounded-md bg-amber-500/90 text-stone-900
                             font-semibold text-sm hover:bg-amber-400">
            继续旅程
          </button>
        </div>
      </div>
    </div>
  );
}
