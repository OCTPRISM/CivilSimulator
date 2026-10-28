"use client";

import { useState } from "react";
import type { GameTask, Session } from "@/lib/api";
import { completeTask, createSelfTask } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Props = {
  sid: string;
  session: Session;
  onUpdate: (s: Session) => void;
};

export default function TaskPanel({ sid, session, onUpdate }: Props) {
  const { t } = useI18n();
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
        {t("task.title", { n: open.length })}
      </div>
      {open.length === 0 ? (
        <div className="text-[12px] opacity-50 mb-2">{t("task.empty")}</div>
      ) : (
        <ul className="space-y-2 mb-3 max-h-40 overflow-y-auto">
          {open.map((task) => (
            <li key={task.id} className="text-[12px] border border-stone-800 rounded-lg p-2">
              <div className="flex justify-between gap-2">
                <span className="font-serif text-amber-200">{task.title}</span>
                <span className="text-[10px] opacity-50 shrink-0">{_src(task.source, t)}</span>
              </div>
              <p className="opacity-70 mt-0.5 line-clamp-2">{task.description}</p>
              {_rewards(task) && (
                <p className="text-[10px] text-emerald-400/80 mt-1">{_rewards(task)}</p>
              )}
              <button disabled={busy} onClick={() => complete(task.id)}
                className="mt-1.5 text-[11px] px-2 py-0.5 rounded border border-emerald-600/50
                           text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-40">
                {t("task.claim")}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input value={title} onChange={(e) => setTitle(e.target.value)}
          placeholder={t("task.customPh")}
          className="flex-1 text-[12px] rounded-md bg-stone-950 border border-stone-700 px-2 py-1.5" />
        <button disabled={busy || !title.trim()} onClick={addSelf}
          className="px-3 py-1.5 rounded-md bg-amber-500/80 text-stone-900 text-[12px] font-semibold disabled:opacity-40">
          {t("task.custom")}
        </button>
      </div>
      <p className="text-[10px] opacity-45 mt-2">
        {t("task.hint")}
      </p>
    </div>
  );
}

function _src(s: string, t: (key: string) => string) {
  return s === "work" ? t("task.work") : s === "story" ? t("task.story") : t("task.custom");
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
