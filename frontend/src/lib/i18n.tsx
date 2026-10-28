"use client";

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import { en, zh, type Dict } from "@/locales/messages";

export type Locale = "zh" | "en";

const STORAGE_KEY = "civsim_locale";

type I18nCtx = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  tf: (key: string, fallback: string, vars?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nCtx | null>(null);

const TABLES: Record<Locale, Dict> = { zh, en };

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return "zh";
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "zh" || saved === "en") return saved;
  } catch {
    /* ignore */
  }
  return "zh";
}

function interpolate(template: string, vars?: Record<string, string | number>) {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => (
    vars[name] === undefined ? `{${name}}` : String(vars[name])
  ));
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readStoredLocale);

  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback((key: string, vars?: Record<string, string | number>) => {
    const table = TABLES[locale];
    const fallback = TABLES.zh;
    return interpolate(table[key] ?? fallback[key] ?? key, vars);
  }, [locale]);

  const tf = useCallback((key: string, fallback: string, vars?: Record<string, string | number>) => {
    const table = TABLES[locale];
    const raw = table[key] ?? TABLES.zh[key];
    return interpolate(raw ?? fallback, vars);
  }, [locale]);

  const value = useMemo(() => ({ locale, setLocale, t, tf }), [locale, setLocale, t, tf]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
