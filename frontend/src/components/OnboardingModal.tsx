"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

const KEY = "civsim_onboarded";

export default function OnboardingModal() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(KEY)) setOpen(true);
    } catch {
      /* ignore */
    }
  }, []);

  function dismiss() {
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      /* ignore */
    }
    setOpen(false);
  }

  if (!open) return null;

  const steps = [
    { title: t("onboard.s1.title"), body: t("onboard.s1.body") },
    { title: t("onboard.s2.title"), body: t("onboard.s2.body") },
    { title: t("onboard.s3.title"), body: t("onboard.s3.body") },
  ];

  return (
    <>
      <div className="fixed inset-0 z-[80] bg-black/70" onClick={dismiss} />
      <div
        className="fixed left-1/2 top-1/2 z-[90] w-[min(420px,92vw)] -translate-x-1/2 -translate-y-1/2
                   rounded-2xl border border-amber-900/40 bg-stone-950 p-6 shadow-2xl space-y-4"
        role="dialog"
        aria-labelledby="onboard-title"
      >
        <h2 id="onboard-title" className="font-serif text-xl text-amber-100 tracking-wider">
          {t("onboard.title")}
        </h2>
        <p className="text-[12px] text-amber-200/70 leading-relaxed">
          {t("onboard.lead")}
        </p>
        <ol className="space-y-3">
          {steps.map((s, i) => (
            <li key={s.title} className="flex gap-3">
              <span className="shrink-0 w-6 h-6 rounded-full border border-amber-700/50
                               text-[11px] flex items-center justify-center text-amber-200/80">
                {i + 1}
              </span>
              <div>
                <div className="text-sm text-amber-50/95">{s.title}</div>
                <p className="text-[12px] opacity-60 mt-0.5 leading-relaxed">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
        <button
          type="button"
          onClick={dismiss}
          className="w-full py-2.5 rounded-lg bg-amber-500/90 text-stone-900 font-semibold
                     hover:bg-amber-400 text-sm"
        >
          {t("onboard.start")}
        </button>
      </div>
    </>
  );
}
