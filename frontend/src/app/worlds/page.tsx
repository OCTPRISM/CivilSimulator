"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { listMyWorlds, restoreSession, type UserWorld } from "@/lib/api";
import { setBoundPlayerId } from "@/lib/playIdentity";
import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";

function formatTime(ts: number) {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return "—";
  }
}

function shortSid(w: UserWorld) {
  if (w.short_id) return w.short_id;
  const id = w.session_id || "";
  return id.length > 8 ? id.slice(-8) : id;
}

export default function MyWorldsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [worlds, setWorlds] = useState<UserWorld[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/worlds");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    listMyWorlds()
      .then(setWorlds)
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [user]);

  async function enter(w: UserWorld) {
    if (w.live) {
      if (w.player_id) setBoundPlayerId(w.session_id, w.player_id);
      router.push(`/play/${w.session_id}`);
      return;
    }
    if (!w.restorable) return;
    setBusyId(w.session_id);
    setErr(null);
    try {
      const { session } = await restoreSession(w.session_id);
      const pid = w.player_id || session.player_id;
      if (pid) setBoundPlayerId(session.id, pid);
      sessionStorage.setItem(`sess_${session.id}`, JSON.stringify(session));
      router.push(`/play/${session.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "续玩失败");
      setBusyId(null);
    }
  }

  if (authLoading || !user) {
    return (
      <main className="min-h-screen flex items-center justify-center opacity-60">
        正在载入…
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 sm:px-6 py-8">
      <div className="max-w-3xl mx-auto">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <SiteLogo href="/" compact />
            <h1 className="font-serif text-3xl tracking-widest mt-4">我的世界</h1>
            <p className="text-sm opacity-55 mt-1">
              Tech Preview：已保存的房间可在重启后端后续玩（方案 B 预览）；极旧或损坏快照可能无法恢复。
            </p>
          </div>
          <Link
            href="/simulator"
            className="text-[12px] border border-amber-700/50 rounded-lg px-3 py-2
                       hover:border-amber-400/50 transition"
          >
            创建新世界 →
          </Link>
        </header>

        {loading && <p className="opacity-50 text-sm">加载中…</p>}
        {err && <p className="text-rose-400 text-sm mb-4">{err}</p>}

        {!loading && worlds.length === 0 && (
          <div className="rounded-xl border border-dashed border-stone-700 p-10 text-center">
            <p className="opacity-60 text-sm">还没有世界记录。</p>
            <Link href="/simulator" className="inline-block mt-4 text-amber-200/90 text-sm">
              去选文明开局 →
            </Link>
          </div>
        )}

        <ul className="space-y-3">
          {worlds.map((w) => {
            const canContinue = w.live || Boolean(w.restorable);
            return (
              <li
                key={w.session_id}
                className="rounded-xl border border-stone-700/80 bg-stone-950/40 p-4
                           flex flex-wrap items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="font-serif text-lg truncate">
                    {w.world_name || w.seed_key || "未命名世界"}
                  </div>
                  <div className="text-[11px] opacity-55 mt-1 space-x-2">
                    <span className="uppercase">{w.genre || w.seed_key || "—"}</span>
                    {w.character_name && <span>· 角色 {w.character_name}</span>}
                    {(w.tick != null || w.snapshot_tick != null) && (
                      <span>· tick {w.live ? w.tick : (w.snapshot_tick ?? w.tick)}</span>
                    )}
                    {w.live && w.players != null && <span>· {w.players} 人</span>}
                    {!w.live && w.restorable && <span>· 已存档</span>}
                    <span>· {formatTime(w.created_at)}</span>
                  </div>
                  <div className="text-[10px] opacity-40 mt-1 font-mono">
                    #{shortSid(w)}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded border ${
                      w.live
                        ? "border-emerald-700/60 text-emerald-300/90"
                        : w.restorable
                          ? "border-sky-700/60 text-sky-300/90"
                          : "border-stone-600 text-stone-500"
                    }`}
                  >
                    {w.live ? "存活" : w.restorable ? "可续玩" : "已结束"}
                  </span>
                  {canContinue ? (
                    <button
                      type="button"
                      disabled={busyId === w.session_id}
                      onClick={() => enter(w)}
                      className="text-sm px-3 py-1.5 rounded-lg bg-amber-500/90 text-stone-900
                                 font-medium hover:bg-amber-400 disabled:opacity-40"
                    >
                      {busyId === w.session_id
                        ? "恢复中…"
                        : w.live
                          ? "继续"
                          : "续玩"}
                    </button>
                  ) : (
                    <span className="text-[11px] opacity-40 max-w-[9rem] text-right leading-snug">
                      无可用快照
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>

        <SiteFooter />
      </div>
    </main>
  );
}
