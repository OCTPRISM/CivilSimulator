"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { getInvitePreview, joinSession } from "@/lib/api";
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
  const [maxPlayers, setMaxPlayers] = useState<number | null>(null);
  const [previewReady, setPreviewReady] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace(`/login?next=/join/${sid}`);
    }
  }, [authLoading, user, router, sid]);

  useEffect(() => {
    if (!user) return;
    setErr(null);
    getInvitePreview(sid)
      .then((j) => {
        setWorldName(j.world_name || sid);
        setRoster(j.players || 1);
        setMaxPlayers(j.max_players ?? null);
        setPreviewReady(true);
        if (j.already_member) {
          router.replace(`/play/${sid}`);
        }
      })
      .catch((e) => {
        setPreviewReady(false);
        setErr(e instanceof Error ? e.message : "房间不存在或已结束");
      });
  }, [sid, user, router]);

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
          {previewReady
            ? `《${worldName || "…"}》 · 当前 ${roster}${maxPlayers ? `/${maxPlayers}` : ""} 人在场`
            : "正在读取邀请…"}
        </p>
        <p className="mt-2 text-[11px] text-amber-200/65 leading-relaxed">
          Tech Preview：重启后若房间有快照，成员仍可在「我的世界」续玩；极旧邀请链接可能需重新分享。
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
          disabled={loading || !previewReady || Boolean(err)}
          onClick={onJoin}
          className="mt-6 w-full py-2.5 rounded-lg bg-amber-500/90 text-stone-900 font-semibold
                     disabled:opacity-40 hover:bg-amber-400"
        >
          {loading ? "正在加入…" : "进入世界"}
        </button>
      </div>
    </main>
  );
}
