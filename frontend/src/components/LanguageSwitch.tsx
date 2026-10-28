"use client";

import { useI18n, type Locale } from "@/lib/i18n";

type Props = {
  /** Fixed corner control, visible on every page. */
  dock?: boolean;
  className?: string;
};

export default function LanguageSwitch({ dock = false, className = "" }: Props) {
  const { locale, setLocale, t } = useI18n();

  function pick(next: Locale) {
    if (next !== locale) setLocale(next);
  }

  return (
    <div
      role="group"
      aria-label={t("lang.switch")}
      className={`${dock
        ? "fixed z-[85] left-3 bottom-3 sm:left-4 sm:bottom-4"
        : ""} ${className}`}
    >
      <div className="flex items-center rounded-full border border-amber-800/50 bg-stone-950/90
                      backdrop-blur-sm shadow-lg overflow-hidden text-[11px] tracking-wide">
        <button
          type="button"
          aria-pressed={locale === "zh"}
          onClick={() => pick("zh")}
          className={`px-2.5 py-1.5 min-w-[2.1rem] transition
            ${locale === "zh"
              ? "bg-amber-500/90 text-stone-900 font-semibold"
              : "text-amber-100/70 hover:text-amber-50"}`}
        >
          中
        </button>
        <button
          type="button"
          aria-pressed={locale === "en"}
          onClick={() => pick("en")}
          className={`px-2.5 py-1.5 min-w-[2.1rem] transition
            ${locale === "en"
              ? "bg-amber-500/90 text-stone-900 font-semibold"
              : "text-amber-100/70 hover:text-amber-50"}`}
        >
          EN
        </button>
      </div>
    </div>
  );
}
