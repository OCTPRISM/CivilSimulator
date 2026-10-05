"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { getSession, joinSession } from "@/lib/api";
import { setBoundPlayerId } from "@/lib/playIdentity";

export default function JoinRoomPage({ params }: { params: { sid: string } }) {
  const sid = params.sid;
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [worldName, setWorldName] = useState<string>("");
  const [description, setDescription] = useState("一位路过的旅人，想见识这座城的风土人情。");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [roster, setRoster] = useState(0);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace(`/login?next=/join/${sid}`);
    }
  }, [authLoading, user, router, sid]);

  useEffect(() => {
    getSession(sid)
      .then((j) => {
        setWorldName(j.session?.world?.name || sid);
        setRoster(j.session?.player_ids?.length || 1);
      })
      .catch(() => setErr("房间不存在或已结束"));
  }, [sid]);

  async function onJoin() {
    setLoading(true);
    setErr(null);
    try {
      const { session, player_id } = await joinSession(sid, { description });
      setBoundPlayerId(session.id, player_id);
      sessionStorage.setItem(`sess_${session.id}`, JSON.stringify(session));
      router.push(`/play/${session.id}?pid=${encodeURIComponent(player_id)}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加入失败");
      setLoading(false);
    }
  }

  if (authLoading || !user) {
    return (
      <main className="min-h-screen flex items-center justify-center opacity-60">
        正在验证登录…
      </main>
    );
  }

  return (
    <main className="min-h-screen flex flex-col items-center px-4 py-10 bg-stone-950 text-stone-100">
      <div className="w-full max-w-lg">
        <Link href="/" className="text-sm opacity-60 hover:opacity-100">← 返回</Link>
        <h1 className="mt-6 font-serif text-2xl text-amber-50">加入世界</h1>
        <p className="mt-2 text-sm opacity-70">
          《{worldName || "…"}》 · 当前 {roster} 人在场
        </p>

        <label className="block mt-8 text-xs uppercase tracking-widest opacity-60">
          你是谁
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          className="mt-2 w-full rounded-lg border border-stone-700 bg-stone-900/80 px-3 py-2 text-sm
                     focus:outline-none focus:border-amber-500/60"
          placeholder="描述你的身份、来历与气质…"
        />

        {err && <p className="mt-3 text-sm text-rose-300">{err}</p>}

        <button
          type="button"
          disabled={loading || !description.trim()}
          onClick={onJoin}
          className="mt-6 w-full rounded-lg border border-amber-600/70 bg-amber-500/10 py-2.5
                     text-amber-100 hover:bg-amber-500/20 disabled:opacity-40"
        >
          {loading ? "正在进入…" : "进入房间"}
        </button>
      </div>
    </main>
  );
}
