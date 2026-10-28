"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function SiteFooter() {
  const { t } = useI18n();
  return (
    <footer className="mt-16 pt-8 border-t border-stone-800/80">
      <div className="grid sm:grid-cols-3 gap-8 text-[12px]">
        <div>
          <div className="font-serif text-sm tracking-wider mb-2 opacity-80">{t("footer.platform")}</div>
          <ul className="space-y-1.5 opacity-55">
            <li><Link href="/labs" className="hover:opacity-100 transition">{t("nav.labs")}</Link></li>
            <li><Link href="/simulator" className="hover:opacity-100 transition">{t("nav.simulator")}</Link></li>
            <li><Link href="/worlds" className="hover:opacity-100 transition">{t("nav.worlds")}</Link></li>
            <li><Link href="/generator" className="hover:opacity-100 transition">{t("nav.generator")}</Link></li>
          </ul>
        </div>
        <div>
          <div className="font-serif text-sm tracking-wider mb-2 opacity-80">{t("footer.docs")}</div>
          <ul className="space-y-1.5 opacity-55">
            <li><Link href="/docs" className="hover:opacity-100 transition">{t("nav.docs")}</Link></li>
            <li>
              <a href="https://github.com/Tencent-Hunyuan/Hunyuan3D-2" target="_blank" rel="noreferrer"
                 className="hover:opacity-100 transition">
                {t("footer.hunyuan")}
              </a>
            </li>
          </ul>
        </div>
        <div>
          <div className="font-serif text-sm tracking-wider mb-2 opacity-80">{t("footer.contact")}</div>
          <ul className="space-y-1.5 opacity-55">
            <li><Link href="/contact" className="hover:opacity-100 transition">{t("nav.contact")}</Link></li>
            <li><a href="mailto:hello@civsim.local" className="hover:opacity-100 transition">hello@civsim.local</a></li>
          </ul>
        </div>
      </div>
      <p className="text-[10px] opacity-30 text-center mt-10 tracking-widest">
        {t("footer.copy", { year: new Date().getFullYear() })}
      </p>
    </footer>
  );
}
