"use client";

import { useEffect, useState } from "react";
import type { Session } from "@/lib/api";
import { injectCharacter, injectEvent, skipToTick } from "@/lib/api";

type Props = {
  sid: string;
  session: Session;
  onUpdate: (s: Session) => void;
};

export default function InjectPanel({ sid, session, onUpdate }: Props) {
  const clockTick = session.world?.clock?.tick ?? 0;
  const [tab, setTab] = useState<"event" | "char" | "skip">("event");
  const [tick, setTick] = useState<number>(clockTick);
  const [summary, setSummary] = useState("");
  const [charName, setCharName] = useState("");
  const [charPersona, setCharPersona] = useState("");
  const [targetTick, setTargetTick] = useState<number>(clockTick + 24);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Keep inject/skip tick fields aligned with live world clock
  useEffect(() => {
    setTick(clockTick);
    setTargetTick((t) => (t <= clockTick ? clockTick + 24 : t));
  }, [clockTick]);

  const injections = session.injections || [];

  async function submitEvent() {
    if (!summary.trim()) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const j = await injectEvent(sid, tick, summary.trim());
      if (j.session) onUpdate(j.session);
      setSummary("");
      setMsg(`已安排事件于 tick ${tick}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "注入失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitChar() {
    if (!charName.trim()) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const j = await injectCharacter(sid, {
        tick, name: charName.trim(), persona: charPersona.trim() || charName.trim(),
      });
      if (j.session) onUpdate(j.session);
      setCharName("");
      setCharPersona("");
      setMsg(`已安排角色于 tick ${tick}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "注入失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitSkip() {
    const dest = Math.max(clockTick + 1, targetTick);
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const j = await skipToTick(sid, dest);
      if (j.session) onUpdate(j.session);
      setMsg(`已快进 ${j.steps} 时辰 → tick ${j.tick}`);
      setTargetTick(j.tick + 24);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "快进失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-stone-800 bg-stone-900/50 p-3">
      <div className="text-[11px] uppercase tracking-widest opacity-60 mb-2">
        自定义进度 · 时间点注入
      </div>
      <div className="flex gap-1 mb-3">
        {(["event", "char", "skip"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-2 py-1 text-[11px] rounded border ${
              tab === t ? "border-amber-500/60 text-amber-200 bg-amber-500/10"
                : "border-stone-700 text-stone-400"}`}>
            {t === "event" ? "事件" : t === "char" ? "角色" : "快进"}
          </button>
        ))}
      </div>

      {tab !== "skip" && (
        <>
          <label className="text-[10px] opacity-60 block mb-1">
            触发 tick（当前 {clockTick}）
          </label>
          <input type="number" value={tick} onChange={(e) => setTick(+e.target.value)}
            className="w-full mb-2 text-[12px] rounded-md bg-stone-950 border border-stone-700 px-2 py-1" />
        </>
      )}

      {tab === "event" && (
        <>
          <textarea value={summary} onChange={(e) => setSummary(e.target.value)}
            placeholder="例如：第三日午时，血手堂在渡口发动突袭…"
            rows={2}
            className="w-full text-[12px] rounded-md bg-stone-950 border border-stone-700 px-2 py-1.5 mb-2" />
          <button disabled={busy || !summary.trim()} onClick={submitEvent}
            className="w-full py-1.5 rounded-md bg-indigo-500/80 text-white text-[12px] disabled:opacity-40">
            注入事件
          </button>
        </>
      )}

      {tab === "char" && (
        <>
          <input value={charName} onChange={(e) => setCharName(e.target.value)}
            placeholder="角色名"
            className="w-full mb-2 text-[12px] rounded-md bg-stone-950 border border-stone-700 px-2 py-1.5" />
          <input value={charPersona} onChange={(e) => setCharPersona(e.target.value)}
            placeholder="人设简述"
            className="w-full mb-2 text-[12px] rounded-md bg-stone-950 border border-stone-700 px-2 py-1.5" />
          <button disabled={busy || !charName.trim()} onClick={submitChar}
            className="w-full py-1.5 rounded-md bg-indigo-500/80 text-white text-[12px] disabled:opacity-40">
            注入角色
          </button>
        </>
      )}

      {tab === "skip" && (
        <>
          <label className="text-[10px] opacity-60 block mb-1">
            快进到 tick（当前 {clockTick}）
          </label>
          <div className="flex gap-2 mb-2">
            {[6, 24, 72].map((n) => (
              <button key={n} type="button" onClick={() => setTargetTick(clockTick + n)}
                className="flex-1 py-1 rounded border border-stone-700 text-[11px]
                           hover:border-amber-400/50">
                +{n}
              </button>
            ))}
          </div>
          <input type="number" value={targetTick} onChange={(e) => setTargetTick(+e.target.value)}
            className="w-full mb-2 text-[12px] rounded-md bg-stone-950 border border-stone-700 px-2 py-1" />
          <button disabled={busy || targetTick <= clockTick} onClick={submitSkip}
            className="w-full py-1.5 rounded-md bg-rose-500/70 text-white text-[12px] disabled:opacity-40">
            {busy ? "快进中…" : `快进到 tick ${Math.max(clockTick + 1, targetTick)}`}
          </button>
        </>
      )}

      {msg && <p className="mt-2 text-[11px] text-emerald-300/90">{msg}</p>}
      {err && <p className="mt-2 text-[11px] text-rose-300/90">{err}</p>}

      {injections.length > 0 && (
        <ul className="mt-3 text-[11px] opacity-70 space-y-1 max-h-24 overflow-y-auto">
          {injections.slice(-5).map((inj) => (
            <li key={inj.id} className="border-l-2 border-stone-700 pl-2">
              t{inj.tick} · {inj.kind} {inj.fired ? "✓" : "待触发"}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
