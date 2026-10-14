"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";
import BrandAtmosphere from "@/components/BrandAtmosphere";
import OnboardingModal from "@/components/OnboardingModal";

const SECONDARY = [
  { href: "/labs", label: "实验平台" },
  { href: "/worlds", label: "我的世界" },
  { href: "/generator", label: "模型生成" },
  { href: "/civilizations", label: "自定义文明" },
] as const;

export default function Home() {
  const router = useRouter();
  const { user, loading: authLoading, logout } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return (
      <main className="brand-surface min-h-screen flex items-center justify-center text-[var(--brand-ink-muted)]">
        正在载入…
      </main>
    );
  }

  return (
    <main className="brand-surface min-h-screen flex flex-col">
      <BrandAtmosphere />

      <div className="relative z-10 flex flex-col min-h-screen">
        <header className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-8 pt-5 sm:pt-6
                           max-w-[var(--brand-max)] mx-auto w-full">
          <SiteLogo compact />
          <div className="flex items-center gap-3">
            <span className="text-sm text-[var(--brand-ink-muted)] truncate max-w-[10rem]">
              {user.display_name || user.username}
            </span>
            <button
              type="button"
              onClick={logout}
              className="text-[11px] px-2.5 py-1 rounded border border-[var(--brand-line)]
                         text-[var(--brand-ink-muted)] hover:text-[var(--brand-ink)]"
            >
              退出
            </button>
          </div>
        </header>

        <OnboardingModal />

        {/* First viewport: one composition — brand, line, CTA */}
        <section className="flex-1 flex flex-col items-center justify-center px-4 sm:px-8
                            min-h-[calc(100svh-5.5rem)] pb-16">
          <div className="brand-hero-in flex flex-col items-center text-center max-w-xl">
            <SiteLogo href={null} hero />
            <p className="mt-8 sm:mt-10 text-base sm:text-lg text-[var(--brand-ink-muted)] leading-relaxed
                          tracking-wide">
              活在小说里。选择文明，踏入仍在运转的世界。
            </p>
            <div className="mt-8 sm:mt-10 flex flex-col sm:flex-row items-center gap-4">
              <Link href="/simulator" className="brand-cta min-w-[12rem]">
                进入模拟器
              </Link>
            </div>
            <nav className="mt-10 flex flex-wrap justify-center gap-x-5 gap-y-2" aria-label="其它入口">
              {SECONDARY.map((item) => (
                <Link key={item.href} href={item.href} className="brand-link-quiet">
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </section>

        <div className="px-4 sm:px-8 max-w-[var(--brand-max)] mx-auto w-full pb-8">
          <SiteFooter />
        </div>
      </div>
    </main>
  );
}
