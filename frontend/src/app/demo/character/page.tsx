"use client";

import { Suspense } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";

const GlbViewer = dynamic(() => import("@/components/generator/GlbViewer"), { ssr: false });

/** Public static preview of the latest Hunyuan3D character demo (no auth). */
export default function DemoCharacterPage() {
  return (
    <main className="min-h-screen px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <Link href="/" className="text-[11px] opacity-50 hover:opacity-80">← 首页</Link>
        <h1 className="font-serif text-2xl tracking-widest mt-3">3D 人物生成预览</h1>
        <p className="text-sm opacity-55 mt-1 mb-6">
          HunyuanDiT 文生图 → Hunyuan3D-2mini 图生 3D ·「青袍剑客」· CPU（文生图 ~10 分钟 + mesh ~18 分钟）
        </p>
        <div className="rounded-2xl border border-stone-700 overflow-hidden min-h-[480px] bg-stone-950">
          <Suspense fallback={<div className="p-8 opacity-50">加载预览…</div>}>
            {/* Public path — no Authorization header needed */}
            <GlbViewer url="/generated/demo/character.glb?v=2" />
          </Suspense>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <div>
            <p className="text-[11px] opacity-45 mb-2">DiT 参考图</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/generated/demo/dit-ref.png"
              alt="DiT reference"
              className="w-full rounded-xl border border-stone-800 bg-white"
            />
          </div>
          <div>
            <p className="text-[11px] opacity-45 mb-2">说明</p>
            <p className="text-sm opacity-60 leading-relaxed">
              参考图为 1024² HunyuanDiT；mesh 为无纹理 shape-only GLB（约 1.8 MB）。
              可在 <Link href="/generator" className="underline opacity-80">3D 生成器</Link> 继续试。
            </p>
          </div>
        </div>
        <p className="text-[11px] opacity-40 mt-4">
          模型路径：/generated/demo/character.glb · 约 1.8 MB
        </p>
      </div>
    </main>
  );
}
