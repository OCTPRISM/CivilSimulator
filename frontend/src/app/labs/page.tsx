"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listLabs, type LabMeta } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function LabsIndexPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { t, tf } = useI18n();
  const [labs, setLabs] = useState<LabMeta[]>([]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    listLabs().then(setLabs).catch(() => setLabs([]));
  }, []);

  if (authLoading || !user) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">{t("common.loadingShort")}</main>;
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8 flex items-center justify-between gap-3">
          <div>
            <Link href="/" className="text-[11px] opacity-50 hover:opacity-80">← {t("common.home")}</Link>
            <h1 className="font-serif text-3xl tracking-wider mt-2">{t("labs.title")}</h1>
            <p className="text-sm opacity-60 mt-1">{t("labs.lead")}</p>
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
                <div className="font-serif text-xl">{tf(`lab.${lab.key}`, lab.name)}</div>
                <span className="text-[10px] opacity-60">
                  {lab.status === "ready" ? t("common.ready") : t("common.building")}
                </span>
              </div>
              <p className="text-[13px] opacity-70 mt-2 leading-relaxed">
                {tf(`lab.${lab.key}.blurb`, lab.blurb)}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
