"use client";

/**
 * NpcChat — slide-up dialog window for talking with a single NPC.
 * Maintains a local message history (not persisted across sessions yet);
 * each turn POSTs /api/sessions/{sid}/talk and appends both player & NPC lines.
 */
import { useEffect, useRef, useState } from "react";
import { talkToNpc, type Agent } from "@/lib/api";

type Line = { who: "me" | "npc"; text: string };

type Props = {
  sid: string;
  npc: Agent;
  onClose: () => void;
};

export default function NpcChat({ sid, npc, onClose }: Props) {
  const [lines, setLines] = useState<Line[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Open with an in-character greeting placeholder.
  useEffect(() => {
    setLines([{
      who: "npc",
      text: `（${npc.name}抬眼看你）……`,
    }]);
  }, [npc.id, npc.name]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight, behavior: "smooth",
    });
  }, [lines.length]);

  async function send() {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    setLines((ls) => [...ls, { who: "me", text: t }]);
    setText("");
    try {
      const r = await talkToNpc(sid, npc.id, t);
      setLines((ls) => [...ls, { who: "npc", text: r.reply }]);
    } catch (e) {
      setLines((ls) => [...ls, {
        who: "npc",
        text: "（对方似乎走神了——稍候再试。）",
      }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end sm:items-center
                    justify-center bg-stone-950/70 backdrop-blur-sm
                    p-2 sm:p-6"
         onClick={onClose}>
      <div className="w-full sm:max-w-lg bg-stone-900 border border-stone-700
                      rounded-2xl shadow-2xl flex flex-col max-h-[90vh]"
           onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center gap-3 p-3 border-b border-stone-800">
          <div className="w-12 h-12 rounded-full
                          bg-gradient-to-br from-amber-700/50 to-stone-800
                          flex items-center justify-center text-2xl
                          border border-stone-700">
            {npc.avatar || "👤"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-serif text-base text-amber-200">
              {npc.name}
            </div>
            <div className="text-[11px] opacity-70 line-clamp-1">
              {npc.persona}
            </div>
          </div>
          <button onClick={onClose}
                  className="px-2.5 py-1 text-xs rounded-md border
                             border-stone-700 hover:border-amber-400
                             text-stone-300">
            关
          </button>
        </div>

        {/* Goals/traits hint */}
        <div className="px-3 pt-2 pb-1 text-[11px] opacity-60 flex flex-wrap gap-2">
          {npc.profession && <span className="text-amber-300/80">职业：{npc.profession}</span>}
          {npc.goals.length > 0 && (
            <span>目标：{npc.goals.join(" / ")}</span>
          )}
          {npc.traits.length > 0 && (
            <span>·  {npc.traits.join(" · ")}</span>
          )}
        </div>

        {/* Live status: activity + economy */}
        {(npc.current_activity || npc.economy?.income_label) && (
          <div className="mx-3 mb-2 rounded-md border border-stone-800
                          bg-stone-950/60 px-2.5 py-1.5
                          text-[11px] grid grid-cols-2 gap-x-3 gap-y-0.5">
            {npc.current_activity && (
              <div className="col-span-2 text-emerald-300/90">
                🕒 此刻：{npc.current_activity}
              </div>
            )}
            {npc.economy?.income_label && (
              <div className="text-amber-200/90">
                💰 今日 {npc.today_income ?? 0}
                <span className="opacity-60">
                  （{npc.today_customers ?? 0}/
                  {npc.economy.daily_capacity ?? "?"}{npc.economy.unit ?? ""}）
                </span>
              </div>
            )}
            {typeof npc.savings === "number" && (
              <div className="text-stone-300">
                🪙 积蓄 {npc.savings}
              </div>
            )}
            {npc.last_meal_tier && (
              <div className="text-stone-400">
                🍚 餐食 {npc.last_meal_tier}
              </div>
            )}
            {npc.economy?.income_per_unit !== undefined && (
              <div className="text-stone-500 col-span-2">
                单价 {npc.economy.income_per_unit}/{npc.economy.unit ?? "笔"}
                {npc.economy.daily_expenses !== undefined &&
                  ` · 日支 ${npc.economy.daily_expenses}`}
              </div>
            )}
          </div>
        )}

        {/* Scrollable history */}
        <div ref={scrollRef}
             className="flex-1 overflow-y-auto px-3 py-3 space-y-2.5
                        text-[13px] leading-relaxed">
          {lines.map((l, i) => (
            <div key={i}
                 className={`flex ${l.who === "me" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] px-3 py-2 rounded-2xl
                  ${l.who === "me"
                    ? "bg-amber-500/85 text-stone-950 rounded-br-sm"
                    : "bg-stone-800 text-stone-100 rounded-bl-sm"}`}>
                {l.text}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex justify-start">
              <div className="bg-stone-800 text-stone-400 px-3 py-2
                              rounded-2xl rounded-bl-sm text-[12px]">
                {npc.name}正在斟酌……
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-2.5 border-t border-stone-800 flex gap-2">
          <input
            value={text}
            disabled={busy}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={`对${npc.name}说……`}
            className="flex-1 rounded-md bg-stone-950/70
                       border border-stone-700 focus:border-amber-400
                       outline-none px-3 py-2 text-sm" />
          <button onClick={send}
                  disabled={busy || !text.trim()}
                  className="px-4 py-2 rounded-md bg-amber-500/90
                             text-stone-900 font-semibold text-sm
                             disabled:opacity-40 hover:bg-amber-400">
            说
          </button>
        </div>
      </div>
    </div>
  );
}
