"use client";

import { useState } from "react";
import type { GameTask, Session } from "@/lib/api";
import { completeTask, createSelfTask } from "@/lib/api";

type Props = {
  sid: string;
  session: Session;
  onUpdate: (s: Session) => void;
};

export default function TaskPanel({ sid, session, onUpdate }: Props) {
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const tasks = session.tasks || [];
  const open = tasks.filter((t) => t.status === "open");

  async function addSelf() {
    if (!title.trim()) return;
    setBusy(true);
    try {
      const j = await createSelfTask(sid, title.trim(), title.trim(), { gold: 20 });
      if (j.session) onUpdate(j.session);
      setTitle("");
    } finally {
      setBusy(false);
    }
  }

  async function complete(taskId: string) {
    setBusy(true);
    try {
      const j = await completeTask(sid, taskId);
      if (j.session) onUpdate(j.session);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-stone-800 bg-stone-900/50 p-3">
      <div className="text-[11px] uppercase tracking-widest opacity-60 mb-2">
        任务 · Tasks（{open.length} 进行中）
      </div>
      {open.length === 0 ? (
        <div className="text-[12px] opacity-50 mb-2">暂无进行中的任务。</div>
      ) : (
        <ul className="space-y-2 mb-3 max-h-40 overflow-y-auto">
          {open.map((t) => (
            <li key={t.id} className="text-[12px] border border-stone-800 rounded-lg p-2">
              <div className="flex justify-between gap-2">
                <span className="font-serif text-amber-200">{t.title}</span>
                <span className="text-[10px] opacity-50 shrink-0">{_src(t.source)}</span>
              </div>
              <p className="opacity-70 mt-0.5 line-clamp-2">{t.description}</p>
              {_rewards(t) && (
                <p className="text-[10px] text-emerald-400/80 mt-1">{_rewards(t)}</p>
              )}
              <button disabled={busy} onClick={() => complete(t.id)}
                className="mt-1.5 text-[11px] px-2 py-0.5 rounded border border-emerald-600/50
                           text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-40">
                领取完成
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input value={title} onChange={(e) => setTitle(e.target.value)}
          placeholder="自定目标，如：去客栈打听血染洛阳…"
          className="flex-1 text-[12px] rounded-md bg-stone-950 border border-stone-700 px-2 py-1.5" />
        <button disabled={busy || !title.trim()} onClick={addSelf}
          className="px-3 py-1.5 rounded-md bg-amber-500/80 text-stone-900 text-[12px] font-semibold disabled:opacity-40">
          自定
        </button>
      </div>
      <p className="text-[10px] opacity-45 mt-2">
        工作类任务在行动输入含「工作/劳作」时自动结算薪酬；剧情类由世界事件自动生成。
      </p>
    </div>
  );
}

function _src(s: string) {
  return s === "work" ? "工作" : s === "story" ? "剧情" : "自定";
}

function _rewards(t: GameTask) {
  const r = t.rewards;
  if (!r) return "";
  const parts: string[] = [];
  if (r.gold) parts.push(`💰 ${r.gold}`);
  if (r.food?.length) parts.push(`🍚 ${r.food.join("、")}`);
  if (r.equipment?.length) parts.push(`⚔ ${r.equipment.join("、")}`);
  return parts.join(" · ");
}
