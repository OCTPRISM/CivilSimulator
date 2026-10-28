"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ANCIENT_WARDROBE,
  ensureAncientPropsReadyLoaded,
  isAncientPropReady,
  suggestedSlugsForRole,
} from "@/lib/ancientRoleProps";
import { useI18n } from "@/lib/i18n";

type Props = {
  roleId: string;
  /** Prop slugs only (clothing is chosen via outfit-style radio). */
  equipped: string[];
  onChange: (slugs: string[]) => void;
};

/** Free multi-select for hy3d props — nothing equipped until checked. */
export default function WardrobeChecklist({ roleId, equipped, onChange }: Props) {
  const { t } = useI18n();
  const [readyTick, setReadyTick] = useState(0);
  useEffect(() => {
    let cancelled = false;
    ensureAncientPropsReadyLoaded().then(() => {
      if (!cancelled) setReadyTick((n) => n + 1);
    });
    return () => { cancelled = true; };
  }, []);

  const suggested = useMemo(() => new Set(suggestedSlugsForRole(roleId)), [roleId]);
  const props = useMemo(() => {
    void readyTick;
    return [...ANCIENT_WARDROBE.filter((a) => a.kind === "prop")].sort(
      (a, b) => Number(suggested.has(b.slug)) - Number(suggested.has(a.slug)),
    );
  }, [suggested, readyTick]);

  const equippedSet = useMemo(() => new Set(equipped), [equipped]);

  const toggle = (slug: string) => {
    if (equippedSet.has(slug)) onChange(equipped.filter((s) => s !== slug));
    else onChange([...equipped, slug]);
  };

  return (
    <div className="rounded-xl border border-stone-700 bg-stone-900/50 p-3 space-y-2">
      <div className="text-[10px] uppercase tracking-widest opacity-50">
        {t("wardrobe.title")}
      </div>
      <p className="text-[11px] opacity-45">{t("wardrobe.hint")}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        {props.map((a) => {
          const ready = isAncientPropReady(a.slug);
          const checked = equippedSet.has(a.slug);
          return (
            <label
              key={a.slug}
              className={`flex items-center gap-2 rounded-md border px-2.5 py-2 text-sm cursor-pointer transition
                ${checked
                  ? "border-amber-400 bg-amber-500/15"
                  : "border-stone-700 bg-stone-950/40 hover:border-amber-500/40"}
                ${ready ? "" : "opacity-40 pointer-events-none"}`}
            >
              <input
                type="checkbox"
                className="accent-amber-500"
                checked={checked}
                disabled={!ready}
                onChange={() => toggle(a.slug)}
              />
              <span className="text-amber-50/90 flex-1">{a.label}</span>
              <span className="text-[10px] uppercase tracking-wider opacity-40">
                {ready ? t("wardrobe.prop") : t("outfit.rendering")}
              </span>
            </label>
          );
        })}
      </div>
      {equipped.length > 0 && (
        <button
          type="button"
          className="text-[11px] opacity-50 hover:opacity-90 underline"
          onClick={() => onChange([])}
        >
          {t("wardrobe.clear")}
        </button>
      )}
    </div>
  );
}
