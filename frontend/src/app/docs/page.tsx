"use client";

import Link from "next/link";
import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";
import { useI18n } from "@/lib/i18n";

export default function DocsPage() {
  const { t } = useI18n();
  const docs = [
    { title: t("docs.d1.title"), desc: t("docs.d1.desc") },
    {
      href: "https://github.com/Tencent-Hunyuan/Hunyuan3D-2",
      title: t("docs.d2.title"),
      desc: t("docs.d2.desc"),
      external: true,
    },
    { title: t("docs.d3.title"), desc: t("docs.d3.desc") },
    { title: t("docs.d4.title"), desc: t("docs.d4.desc") },
    { title: t("docs.d5.title"), desc: t("docs.d5.desc") },
  ];

  return (
    <main className="min-h-screen px-4 sm:px-6 py-8">
      <div className="max-w-3xl mx-auto">
        <SiteLogo href="/" compact />
        <h1 className="font-serif text-3xl tracking-widest mt-6 mb-2">{t("docs.title")}</h1>
        <p className="text-sm opacity-55 mb-10">{t("docs.lead")}</p>
        <ul className="space-y-4">
          {docs.map((d) => (
            <li key={d.title} className="rounded-xl border border-stone-800 bg-stone-950/40 p-4">
              {"href" in d && d.href ? (
                d.external ? (
                  <a href={d.href} target="_blank" rel="noreferrer"
                     className="font-serif text-lg hover:text-cyan-200/90 transition">{d.title} ↗</a>
                ) : (
                  <Link href={d.href} className="font-serif text-lg hover:text-cyan-200/90 transition">
                    {d.title}
                  </Link>
                )
              ) : (
                <div className="font-serif text-lg">{d.title}</div>
              )}
              <p className="text-[12px] opacity-55 mt-1">{d.desc}</p>
            </li>
          ))}
        </ul>
        <p className="text-[11px] opacity-40 mt-8">
          {t("docs.more")}
        </p>
        <SiteFooter />
      </div>
    </main>
  );
}
