"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { listSeeds, type Seed } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";

export default function SimulatorHubPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [seeds, setSeeds] = useState<Seed[]>([]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    listSeeds().then(setSeeds).catch(() => {});
  }, []);

  if (authLoading || !user) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">正在载入…</main>;
  }

  return (
    <main className="brand-surface min-h-screen px-4 sm:px-6 py-8">
      <div className="max-w-[var(--brand-max)] mx-auto">
        <header className="mb-10 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <SiteLogo href="/" compact />
            <h1 className="font-serif text-3xl tracking-[0.18em] mt-5 text-[var(--brand-ink)]">
              文明模拟器
            </h1>
            <p className="text-sm text-[var(--brand-ink-muted)] mt-2">
              选择文明种子，创建角色，进入叙事世界。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/worlds"
              className="text-[12px] text-[var(--brand-ink-muted)] hover:text-[var(--brand-ink)]
                         border border-[var(--brand-line)] rounded-lg px-3 py-2"
            >
              我的世界 →
            </Link>
            <Link
              href="/civilizations"
              className="text-[12px] text-[var(--brand-ink-muted)] hover:text-[var(--brand-ink)]
                         border border-[var(--brand-line)] rounded-lg px-3 py-2"
            >
              我的自定义文明 →
            </Link>
          </div>
        </header>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <Link
            href="/civilizations/new"
            className="rounded-xl border-2 border-dashed border-amber-700/45 p-6
                       hover:border-amber-400/50 transition bg-amber-950/15 text-center"
          >
            <span className="text-3xl opacity-70">✦</span>
            <div className="font-serif text-lg mt-2">自定义文明</div>
            <p className="text-[11px] opacity-50 mt-1">规则 · 地点 · 势力 · 人口</p>
          </Link>
          {seeds.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => router.push(`/create/${s.key}`)}
              className="text-left rounded-xl border border-stone-700 overflow-hidden
                         hover:border-amber-500/40 transition"
            >
              <div className="relative aspect-[16/10] bg-stone-900">
                <img
                  src={`/maps/${s.key}.png`}
                  alt=""
                  className="absolute inset-0 w-full h-full object-cover opacity-80"
                  draggable={false}
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-transparent to-transparent" />
                <div className="absolute bottom-3 left-3 right-3">
                  <div className="font-serif text-lg">{s.name}</div>
                  <div className="text-[10px] opacity-60 uppercase">{s.genre}</div>
                </div>
              </div>
              <p className="p-3 text-[12px] opacity-70 line-clamp-2">{s.premise}</p>
            </button>
          ))}
        </div>
        <SiteFooter />
      </div>
    </main>
  );
}
