"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  deleteCustomCivilization,
  listCustomCivilizations,
  type Seed,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function MyCivilizationsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<(Seed & { id: string })[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/civilizations");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    listCustomCivilizations()
      .then(setItems)
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, [user]);

  async function onDelete(id: string, name: string) {
    if (!window.confirm(`确定删除「${name}」？此操作不可恢复。`)) return;
    setBusyId(id);
    try {
      await deleteCustomCivilization(id);
      setItems((xs) => xs.filter((x) => x.id !== id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    } finally {
      setBusyId(null);
    }
  }

  if (authLoading || !user) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">载入中…</main>;
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <Link href="/simulator" className="text-[11px] opacity-50 hover:opacity-80">← 文明模拟器</Link>
            <h1 className="font-serif text-3xl tracking-wider mt-2">我的文明</h1>
            <p className="text-sm opacity-60 mt-1">管理你创建的自定义文明种子</p>
          </div>
          <Link
            href="/civilizations/new"
            className="shrink-0 px-4 py-2 rounded-lg bg-amber-500/90 text-stone-950 text-sm font-semibold"
          >
            新建
          </Link>
        </div>

        {err && <p className="text-red-400 text-sm">{err}</p>}

        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-stone-700 p-10 text-center opacity-70">
            <p className="text-sm">还没有自定义文明</p>
            <Link href="/civilizations/new" className="text-amber-300/90 text-sm mt-2 inline-block">
              去创建 →
            </Link>
          </div>
        ) : (
          <ul className="space-y-3">
            {items.map((c) => (
              <li
                key={c.id}
                className="rounded-xl border border-stone-700 bg-stone-950/60 p-4 flex flex-col sm:flex-row
                           sm:items-center gap-3 justify-between"
              >
                <div className="min-w-0">
                  <div className="font-serif text-lg truncate">★ {c.name}</div>
                  <div className="text-[11px] opacity-50 uppercase mt-0.5">{c.genre}</div>
                  <p className="text-[12px] opacity-70 mt-1 line-clamp-2">{c.premise}</p>
                </div>
                <div className="flex flex-wrap gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => router.push(`/create/${c.key}`)}
                    className="px-3 py-1.5 rounded border border-amber-700/50 text-[12px] hover:border-amber-400/60"
                  >
                    进入
                  </button>
                  <button
                    type="button"
                    onClick={() => router.push(`/civilizations/${c.id}/edit`)}
                    className="px-3 py-1.5 rounded border border-stone-600 text-[12px] hover:border-stone-400"
                  >
                    编辑规则
                  </button>
                  <button
                    type="button"
                    disabled={busyId === c.id}
                    onClick={() => onDelete(c.id, c.name)}
                    className="px-3 py-1.5 rounded border border-red-900/60 text-[12px] text-red-300/90
                               hover:border-red-500/50 disabled:opacity-40"
                  >
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
