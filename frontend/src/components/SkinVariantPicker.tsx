"use client";

import { useEffect, useState } from "react";
import { ROLE_SKIN_IDS, type RoleSkinId } from "@/lib/characterFigures";
import {
  ensureHy3dSkinReadyLoaded, isHy3dNpcReady, isHy3dSkinReady,
} from "@/lib/gltfCharacters";
import { useI18n } from "@/lib/i18n";

type Props = {
  roleId: string;
  value: RoleSkinId;
  onChange: (id: RoleSkinId) => void;
};

const SWATCH: Record<RoleSkinId, string> = {
  fair: "#f3d7c4",
  tan: "#c48a62",
  warm: "#e0b089",
  pale: "#ead9d0",
};

export default function SkinVariantPicker({ roleId, value, onChange }: Props) {
  const { t } = useI18n();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let cancelled = false;
    ensureHy3dSkinReadyLoaded().then(() => {
      if (!cancelled) setTick((n) => n + 1);
    });
    return () => { cancelled = true; };
  }, [roleId]);
  void tick;

  const hy = isHy3dNpcReady(roleId);

  return (
    <div className="rounded-xl border border-stone-700 bg-stone-900/50 p-3">
      <div className="text-[10px] uppercase tracking-widest opacity-50 mb-1">
        {t("skin.title")}
      </div>
      <p className="text-[11px] opacity-45 mb-2">
        {t("skin.hint")}
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
        {ROLE_SKIN_IDS.map((id) => {
          const ready = !hy || isHy3dSkinReady(roleId, id);
          const selected = value === id;
          return (
            <button
              key={id}
              type="button"
              disabled={!ready}
              onClick={() => onChange(id)}
              className={`rounded-lg border px-2.5 py-2 text-left text-sm transition
                ${selected
                  ? "border-amber-400 bg-amber-500/15 ring-1 ring-amber-500/40"
                  : "border-stone-700 bg-stone-950/40 hover:border-amber-500/40"}
                ${!ready ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-4 rounded-full border border-stone-600 shrink-0"
                  style={{ background: SWATCH[id] }}
                />
                <span className="text-amber-100/90 font-serif">{t(`skin.${id}`)}</span>
              </div>
              <div className="text-[10px] opacity-40 mt-0.5">
                {ready ? t("skin.ready") : t("outfit.rendering")}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
