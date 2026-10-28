"use client";

import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";
import { useI18n } from "@/lib/i18n";

export default function ContactPage() {
  const { t } = useI18n();
  return (
    <main className="min-h-screen px-4 sm:px-6 py-8">
      <div className="max-w-lg mx-auto">
        <SiteLogo href="/" compact />
        <h1 className="font-serif text-3xl tracking-widest mt-6 mb-2">{t("contact.title")}</h1>
        <p className="text-sm opacity-55 mb-8">{t("contact.lead")}</p>
        <div className="space-y-4 text-[13px] opacity-70 leading-relaxed">
          <p>
            <span className="opacity-50">{t("contact.email")} · </span>
            <a href="mailto:hello@civsim.local" className="hover:opacity-100">hello@civsim.local</a>
          </p>
          <p>
            <span className="opacity-50">{t("contact.feedback")} · </span>
            {t("contact.feedbackBody")}
          </p>
          <p>
            <span className="opacity-50">{t("contact.biz")} · </span>
            {t("contact.bizBody")}
          </p>
        </div>
        <SiteFooter />
      </div>
    </main>
  );
}
