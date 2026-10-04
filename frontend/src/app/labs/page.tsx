"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listLabs, type LabMeta } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LabsIndexPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [labs, setLabs] = useState<LabMeta[]>([]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    listLabs().then(setLabs).catch(() => setLabs([]));
  }, []);

  if (authLoading || !user) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">载入中…</main>;
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8 flex items-center justify-between gap-3">
          <div>
            <Link href="/" className="text-[11px] opacity-50 hover:opacity-80">← 首页</Link>
            <h1 className="font-serif text-3xl tracking-wider mt-2">实验平台</h1>
            <p className="text-sm opacity-60 mt-1">选择实验室进入独立沙盘</p>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          {labs.map((lab) => (
            <Link
              key={lab.key}
              href={`/labs/${lab.key}`}
              className="rounded-lg border border-stone-700 p-5 hover:border-cyan-500/45
                         transition bg-stone-950/40"
            >
              <div className="flex justify-between gap-2">
                <div className="font-serif text-xl">{lab.name}</div>
                <span className="text-[10px] opacity-60">
                  {lab.status === "ready" ? "可用" : "建设中"}
                </span>
              </div>
              <p className="text-[13px] opacity-70 mt-2 leading-relaxed">{lab.blurb}</p>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
