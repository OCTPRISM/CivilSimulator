"use client";

/**
 * NpcChat — slide-up dialog for talking with an NPC or another player.
 * History is stored per session+peer; swipe/scroll up to read earlier lines.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { talkToNpc, type Agent } from "@/lib/api";
import {
  appendTalkLine, ensureTalkGreeting, getTalkLines, type TalkLine,
} from "@/lib/playerTalkStore";

export type PlayerDialogueEvent = {
  message_id?: string;
  from_id: string;
  from_name?: string;
  to_id: string;
  to_name?: string;
  text: string;
};

type Props = {
  sid: string;
  npc: Agent;
  playerId?: string | null;
  onClose: () => void;
};

const NEAR_BOTTOM_PX = 64;

export default function NpcChat({ sid, npc, playerId, onClose }: Props) {
  const isPlayer = npc.kind === "player";
  const greeting = isPlayer
    ? `（${npc.name}就在近前，等你开口。）`
    : `（${npc.name}抬眼看你）……`;
  const [lines, setLines] = useState<TalkLine[]>(() =>
    ensureTalkGreeting(sid, npc.id, greeting),
  );
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottom = useRef(true);
  const selfId = playerId || null;

  const refresh = useCallback(() => {
    setLines(getTalkLines(sid, npc.id));
  }, [sid, npc.id]);

  useEffect(() => {
    setLines(ensureTalkGreeting(sid, npc.id, greeting));
    stickToBottom.current = true;
  }, [sid, npc.id, greeting]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !stickToBottom.current) return;
    el.scrollTop = el.scrollHeight;
  }, [lines.length]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottom.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
  };

  useEffect(() => {
    if (!isPlayer || !selfId) return;
    const onMsg = (ev: Event) => {
      const d = (ev as CustomEvent<PlayerDialogueEvent>).detail;
      if (!d?.text || !d.from_id || !d.to_id) return;
      if (d.from_id !== npc.id || d.to_id !== selfId) return;
      appendTalkLine(sid, npc.id, { id: d.message_id, who: "them", text: d.text });
      refresh();
    };
    window.addEventListener("civsim:player-dialogue", onMsg);
    return () => window.removeEventListener("civsim:player-dialogue", onMsg);
  }, [isPlayer, selfId, npc.id, sid, refresh]);

  async function send() {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    setText("");
    stickToBottom.current = true;
    appendTalkLine(sid, npc.id, { who: "me", text: t });
    refresh();
    try {
      const r = await talkToNpc(sid, npc.id, t, selfId);
      if (!isPlayer && r.reply) {
        appendTalkLine(sid, npc.id, { who: "them", text: r.reply });
        refresh();
      }
    } catch {
      const fail = isPlayer
        ? "（话音未达——对方或许已离线，稍候再试。）"
        : "（对方似乎走神了——稍候再试。）";
      appendTalkLine(sid, npc.id, { who: "them", text: fail });
      refresh();
    } finally {
      setBusy(false);
    }
  }

  const canScrollHistory = lines.length > 4;

  return (
    <div className="fixed inset-0 z-40 flex items-end sm:items-center
                    justify-center bg-stone-950/70 backdrop-blur-sm
                    p-2 sm:p-6"
         onClick={onClose}>
      <div className="w-full sm:max-w-lg h-[min(90vh,720px)] sm:h-[min(82vh,680px)]
                      bg-stone-900 border border-stone-700
                      rounded-2xl shadow-2xl flex flex-col min-h-0"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 p-3 border-b border-stone-800 shrink-0">
          <div className="w-12 h-12 rounded-full
                          bg-gradient-to-br from-amber-700/50 to-stone-800
                          flex items-center justify-center text-2xl
                          border border-stone-700">
            {npc.avatar || "👤"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-serif text-base text-amber-200 flex items-center gap-2">
              <span className="truncate">{npc.name}</span>
              {isPlayer && (
                <span className="text-[10px] px-1.5 py-0.5 rounded border
                                 border-sky-700/50 bg-sky-950/50 text-sky-200/90
                                 font-sans font-normal shrink-0">
                  玩家
                </span>
              )}
            </div>
            <div className="text-[11px] opacity-70 line-clamp-1">
              {npc.persona || (isPlayer ? "同房旅人" : "")}
            </div>
          </div>
          <button onClick={onClose}
                  className="px-2.5 py-1 text-xs rounded-md border
                             border-stone-700 hover:border-amber-400
                             text-stone-300">
            关
          </button>
        </div>

        {!isPlayer && (
          <div className="px-3 pt-2 pb-1 text-[11px] opacity-60 flex flex-wrap gap-2 shrink-0">
            {npc.profession && <span className="text-amber-300/80">职业：{npc.profession}</span>}
            {npc.goals.length > 0 && (
              <span>目标：{npc.goals.join(" / ")}</span>
            )}
            {npc.traits.length > 0 && (
              <span>·  {npc.traits.join(" · ")}</span>
            )}
          </div>
        )}

        {!isPlayer && (npc.current_activity || npc.economy?.income_label) && (
          <div className="mx-3 mb-2 rounded-md border border-stone-800
                          bg-stone-950/60 px-2.5 py-1.5 shrink-0
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
          </div>
        )}

        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-3 py-3 space-y-2.5
                     text-[13px] leading-relaxed overscroll-contain touch-pan-y"
        >
          {canScrollHistory && (
            <div className="text-center text-[10px] opacity-40 pb-1">
              上滑查看更早的对话
            </div>
          )}
          {lines.map((l, i) => (
            <div key={l.id || i}
                 className={`flex ${l.who === "me" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] px-3 py-2 rounded-2xl
                  ${l.who === "me"
                    ? "bg-amber-500/85 text-stone-950 rounded-br-sm"
                    : "bg-stone-800 text-stone-100 rounded-bl-sm"}`}>
                {l.text}
              </div>
            </div>
          ))}
          {busy && !isPlayer && (
            <div className="flex justify-start">
              <div className="bg-stone-800 text-stone-400 px-3 py-2
                              rounded-2xl rounded-bl-sm text-[12px]">
                {npc.name}正在斟酌……
              </div>
            </div>
          )}
        </div>

        <div className="p-2.5 border-t border-stone-800 flex gap-2 shrink-0">
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
