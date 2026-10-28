"use client";

import { Suspense } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

const GlbViewer = dynamic(() => import("@/components/generator/GlbViewer"), { ssr: false });

/** Public static preview of the latest Hunyuan3D character demo (no auth). */
export default function DemoCharacterPage() {
  const { t } = useI18n();
  return (
    <main className="min-h-screen px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <Link href="/" className="text-[11px] opacity-50 hover:opacity-80">{t("demo.back")}</Link>
        <h1 className="font-serif text-2xl tracking-widest mt-3">{t("demo.title")}</h1>
        <p className="text-sm opacity-55 mt-1 mb-6">
          {t("demo.lead")}
        </p>
        <div className="rounded-2xl border border-stone-700 overflow-hidden min-h-[480px] bg-stone-950">
          <Suspense fallback={<div className="p-8 opacity-50">{t("demo.loading")}</div>}>
            {/* Public path — no Authorization header needed */}
            <GlbViewer url="/generated/demo/character.glb?v=2" />
          </Suspense>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <div>
            <p className="text-[11px] opacity-45 mb-2">{t("demo.ref")}</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/generated/demo/dit-ref.png"
              alt="DiT reference"
              className="w-full rounded-xl border border-stone-800 bg-white"
            />
          </div>
          <div>
            <p className="text-[11px] opacity-45 mb-2">{t("demo.note")}</p>
            <p className="text-sm opacity-60 leading-relaxed">
              {t("demo.noteBody")}
            </p>
          </div>
        </div>
        <p className="text-[11px] opacity-40 mt-4">
          {t("demo.path")}
        </p>
      </div>
    </main>
  );
}
