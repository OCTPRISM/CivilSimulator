"use client";

import { useEffect, useState } from "react";
import {
  OUTFIT_STYLE_OPTIONS,
  type OutfitStyleId,
} from "@/lib/ancientRoleProps";
import { ensureHy3dOutfitReadyLoaded, isHy3dOutfitReady } from "@/lib/gltfCharacters";
import { useI18n } from "@/lib/i18n";

type Props = {
  roleId: string;
  value: OutfitStyleId;
  onChange: (id: OutfitStyleId) => void;
};

/**
 * Radio: 本职装束 / 各服装风格.
 * Selecting a style swaps the whole body mesh — never stacks a second outfit.
 */
export default function OutfitStylePicker({ roleId, value, onChange }: Props) {
  const { t } = useI18n();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let cancelled = false;
    ensureHy3dOutfitReadyLoaded().then(() => {
      if (!cancelled) setTick((n) => n + 1);
    });
    return () => { cancelled = true; };
  }, [roleId]);
  void tick;

  return (
    <div className="rounded-xl border border-stone-700 bg-stone-900/50 p-3">
      <div className="text-[10px] uppercase tracking-widest opacity-50 mb-1">
        {t("outfit.title")}
      </div>
      <p className="text-[11px] opacity-45 mb-2">
        {t("outfit.hint")}
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
        {OUTFIT_STYLE_OPTIONS.map((opt) => {
          const ready = opt.id === "default" || isHy3dOutfitReady(roleId, opt.id);
          const selected = value === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              disabled={!ready}
              onClick={() => onChange(opt.id)}
              className={`rounded-lg border px-2.5 py-2 text-left text-sm transition
                ${selected
                  ? "border-amber-400 bg-amber-500/15 ring-1 ring-amber-500/40"
                  : "border-stone-700 bg-stone-950/40 hover:border-amber-500/40"}
                ${!ready ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              <div className="text-amber-100/90 font-serif">{opt.label}</div>
              <div className="text-[10px] opacity-40 mt-0.5">
                {opt.id === "default" ? t("outfit.body") : ready ? t("outfit.swap") : t("outfit.rendering")}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
