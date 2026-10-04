"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";

const PORTALS = [
  {
    key: "labs",
    href: "/labs",
    title: "实验平台",
    tagline: "可控沙盘 · 数值复现",
    icon: "⚗",
    accent: "border-cyan-800/55 hover:border-cyan-400/50",
    glow: "from-cyan-500/20 via-cyan-500/5",
    ring: "group-hover:shadow-[0_0_48px_rgba(34,211,238,0.12)]",
  },
  {
    key: "simulator",
    href: "/simulator",
    title: "文明模拟器",
    tagline: "选文明 · 选角色 · 活在故事里",
    icon: "🏛",
    accent: "border-amber-800/50 hover:border-amber-400/45",
    glow: "from-amber-500/18 via-amber-500/5",
    ring: "group-hover:shadow-[0_0_48px_rgba(251,191,36,0.1)]",
  },
  {
    key: "generator",
    href: "/generator",
    title: "3D 模型生成器",
    tagline: "文本生成人物 · 道具 · 地图",
    icon: "◈",
    accent: "border-violet-800/50 hover:border-violet-400/45",
    glow: "from-violet-500/18 via-violet-500/5",
    ring: "group-hover:shadow-[0_0_48px_rgba(167,139,250,0.1)]",
  },
] as const;

const INTROS = [
  {
    key: "labs",
    title: "实验平台",
    accent: "text-cyan-300/90",
    body: "脱离叙事对局的独立沙盘环境。可在金融、气象、舆情、政令、人口、军事等实验室中注入变量、对照路径、导出报告，以确定性数值引擎复现推演结果，为文明模拟提供可验证的底层参数。",
  },
  {
    key: "simulator",
    title: "文明模拟器",
    accent: "text-amber-300/90",
    body: "以 Agent 社会驱动的沉浸式叙事引擎。选择古代、武侠、科幻等文明种子或自定义文明配置，挑选角色形象进入 3D 世界，与 NPC 对话、推进剧情、完成任务，体验「活在小说里」的连续模拟。",
  },
  {
    key: "generator",
    title: "3D 模型生成器",
    accent: "text-violet-300/90",
    body: "基于 Hunyuan3D-2mini-Turbo 的本地资产生成管线。支持文本描述生成 3D 人物与道具模型（GLB），以及文本驱动的程序化 3D 地图沙盘，为文明世界快速注入独有角色、器物与场景。",
  },
] as const;

export default function Home() {
  const router = useRouter();
  const { user, loading: authLoading, logout } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return (
      <main className="min-h-screen flex items-center justify-center opacity-60">
        正在载入…
      </main>
    );
  }

  return (
    <main className="min-h-screen flex flex-col px-4 sm:px-8 py-6 sm:py-10">
      <div className="max-w-6xl mx-auto w-full flex-1">
        <header className="flex flex-wrap items-center justify-between gap-4 mb-12 sm:mb-16">
          <SiteLogo />
          <div className="flex items-center gap-3">
            <span className="text-sm opacity-55">{user.display_name || user.username}</span>
            <button
              type="button"
              onClick={logout}
              className="text-[11px] px-2.5 py-1 rounded border border-stone-700 opacity-55 hover:opacity-100"
            >
              退出
            </button>
          </div>
        </header>

        {/* Three portal cards only */}
        <div className="grid md:grid-cols-3 gap-5 sm:gap-6 mb-16 sm:mb-20">
          {PORTALS.map((p) => (
            <Link
              key={p.key}
              href={p.href}
              className={`group relative block rounded-2xl border ${p.accent} ${p.ring}
                          bg-stone-950/60 backdrop-blur-sm overflow-hidden
                          transition-all duration-300 hover:scale-[1.02]`}
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${p.glow} to-transparent opacity-80`} />
              <div className="relative flex flex-col items-center justify-center text-center
                              min-h-[220px] sm:min-h-[260px] px-6 py-10">
                <span className="text-4xl sm:text-5xl mb-4 opacity-90">{p.icon}</span>
                <h2 className="font-serif text-2xl sm:text-[1.65rem] tracking-wider">{p.title}</h2>
                <p className="text-[11px] sm:text-xs opacity-50 mt-2 tracking-wide">{p.tagline}</p>
                <span className="mt-6 text-[11px] opacity-40 group-hover:opacity-70 transition tracking-widest">
                  进入 →
                </span>
              </div>
            </Link>
          ))}
        </div>

        {/* Feature overviews below cards */}
        <section className="space-y-10 sm:space-y-12">
          <h2 className="font-serif text-lg tracking-[0.25em] text-center opacity-45">
            功能概览
          </h2>
          <div className="grid md:grid-cols-3 gap-8 sm:gap-10">
            {INTROS.map((item) => (
              <article key={item.key} className="space-y-3">
                <h3 className={`font-serif text-lg tracking-wider ${item.accent}`}>
                  {item.title}
                </h3>
                <p className="text-[13px] leading-relaxed opacity-60">
                  {item.body}
                </p>
              </article>
            ))}
          </div>
        </section>

        <SiteFooter />
      </div>
    </main>
  );
}
