"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import {
  createSession, getPlayerCatalog, listSeeds,
  type PlayerCatalog, type Seed, type CharacterVariant,
} from "@/lib/api";
import type { RoleSkinId } from "@/lib/characterFigures";
import { setBoundPlayerId } from "@/lib/playIdentity";
import CharacterPicker from "@/components/CharacterPicker";
import CivilizationDashboard from "@/components/CivilizationDashboard";
import WorldMapPreview from "@/components/WorldMapPreview";

export default function CreateCharacterPage({ params }: { params: { seedKey: string } }) {
  const seedKey = params.seedKey;
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [seed, setSeed] = useState<Seed | null>(null);
  const [catalog, setCatalog] = useState<PlayerCatalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace(`/login?next=/create/${seedKey}`);
    }
  }, [authLoading, user, router, seedKey]);

  useEffect(() => {
    Promise.all([listSeeds(), getPlayerCatalog(seedKey)])
      .then(([seeds, cat]) => {
        setSeed(seeds.find((s) => s.key === seedKey) || null);
        setCatalog(cat);
      })
      .catch((e) => setErr(String(e)));
  }, [seedKey]);

  async function onConfirm(categoryKey: string, variant: CharacterVariant, skin: RoleSkinId) {
    setLoading(true);
    setErr(null);
    try {
      const { session } = await createSession(seedKey, {
        category_key: categoryKey,
        variant_key: variant.key,
        skin,
      });
      if (session.player_id) setBoundPlayerId(session.id, session.player_id);
      sessionStorage.setItem(`sess_${session.id}`, JSON.stringify(session));
      router.push(`/play/${session.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "进入失败");
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
    <main className="min-h-screen flex flex-col items-center px-4 py-8">
      <div className="w-full max-w-3xl flex items-center justify-between mb-6">
        <Link href="/" className="text-sm opacity-60 hover:opacity-100">← 返回文明选择</Link>
        <div className="text-[11px] opacity-50">{user.display_name || user.username}</div>
      </div>
      <p className="w-full max-w-3xl text-[11px] text-amber-200/65 mb-4 leading-relaxed">
        Tech Preview：创建后会写入快照；重启服务后可在「我的世界」续玩同一房间（方案 B 预览）。
      </p>

      {seed && (
        <>
          <div className="w-full max-w-3xl mb-3 rounded-lg border border-stone-800
                          overflow-hidden relative aspect-[21/6]">
            <img
              src={`/maps/${seed.is_custom ? (seed.genre || "ancient") : seed.key}.png`}
              alt=""
              className="absolute inset-0 w-full h-full object-cover opacity-60"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
            />
            <div className="absolute inset-0 bg-gradient-to-r from-stone-950/90 to-transparent
                            flex items-center px-6">
              <div>
                <div className="font-serif text-xl">{seed.is_custom ? `★ ${seed.name}` : seed.name}</div>
                <div className="text-[11px] opacity-60 uppercase">{seed.genre}</div>
              </div>
            </div>
          </div>
          <div className="w-full max-w-3xl mb-4">
            <WorldMapPreview genre={seed.genre} height={240} />
          </div>
        </>
      )}

      <div className="w-full max-w-3xl mb-6">
        <CivilizationDashboard seedKey={seedKey} compact />
      </div>

      {catalog ? (
        <CharacterPicker
          categories={catalog.categories}
          seedKey={seedKey}
          seedName={seed?.name || seedKey}
          loading={loading}
          onConfirm={onConfirm}
        />
      ) : (
        <p className="opacity-60">正在载入角色库…</p>
      )}

      {err && <p className="text-rose-400 text-sm mt-4 max-w-3xl">{err}</p>}
    </main>
  );
}
