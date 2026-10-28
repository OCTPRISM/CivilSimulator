"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CharacterCategory, CharacterVariant } from "@/lib/api";
import CharacterFigurePreview, { CharacterFigureThumb } from "@/components/CharacterFigurePreview";
import OutfitStylePicker from "@/components/OutfitStylePicker";
import SkinVariantPicker from "@/components/SkinVariantPicker";
import WardrobeChecklist from "@/components/WardrobeChecklist";
import {
  getFigure, withEquippedProps, withOutfitStyle, withSkinVariant, type RoleSkinId,
} from "@/lib/characterFigures";
import {
  mergeEquipped,
  type OutfitStyleId,
} from "@/lib/ancientRoleProps";
import { useI18n } from "@/lib/i18n";

type Props = {
  categories: CharacterCategory[];
  seedKey: string;
  seedName: string;
  loading?: boolean;
  onConfirm: (
    categoryKey: string,
    variant: CharacterVariant,
    skin: RoleSkinId,
    equippedProps: string[],
    outfitStyle: OutfitStyleId,
  ) => void;
  /** Confirm button label override (e.g. join flow). */
  confirmLabel?: string;
};

export default function CharacterPicker({
  categories, seedKey, seedName, loading, onConfirm,   confirmLabel,
}: Props) {
  const { t } = useI18n();
  const [catIdx, setCatIdx] = useState(0);
  const [varIdx, setVarIdx] = useState(0);
  const [outfitStyle, setOutfitStyle] = useState<OutfitStyleId>("default");
  const [skin, setSkin] = useState<RoleSkinId>("fair");
  const [propSlugs, setPropSlugs] = useState<string[]>([]);
  const scrollerRef = useRef<HTMLDivElement>(null);

  const category = categories[catIdx];
  const variants = category?.variants || [];
  const variant = variants[varIdx];
  const basePreset = useMemo(
    () => (variant ? getFigure(variant.figure || `${seedKey}_${variant.key}`) : null),
    [variant, seedKey],
  );

  useEffect(() => {
    setVarIdx(0);
    scrollerRef.current?.scrollTo({ left: 0, behavior: "smooth" });
  }, [catIdx]);

  useEffect(() => {
    setOutfitStyle("default");
    setPropSlugs([]);
    setSkin((basePreset?.skinVariant || "fair") as RoleSkinId);
  }, [basePreset?.id, basePreset?.skinVariant]);

  const equipped = useMemo(
    () => mergeEquipped(outfitStyle, propSlugs),
    [outfitStyle, propSlugs],
  );

  const activePreset = basePreset
    ? withEquippedProps(
      withOutfitStyle(withSkinVariant(basePreset, skin), outfitStyle),
      equipped,
    )
    : null;
  const showWardrobe = !!basePreset && (
    basePreset.genre === "ancient" || basePreset.id.startsWith("ancient_")
  );

  const scrollToVariant = useCallback((idx: number) => {
    setVarIdx(idx);
    const el = scrollerRef.current;
    if (!el) return;
    const card = el.children[idx] as HTMLElement | undefined;
    if (card) card.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, []);

  if (!categories.length) {
    return <p className="opacity-60 text-sm">{t("picker.empty")}</p>;
  }

  return (
    <div className="w-full max-w-3xl">
      <div className="text-center mb-6">
        <h2 className="font-serif text-2xl">{t("picker.title")}</h2>
        <p className="text-sm opacity-60 mt-1">{t("picker.lead", { name: seedName })}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-6">
        {categories.map((c, i) => (
          <button
            key={c.key}
            type="button"
            onClick={() => setCatIdx(i)}
            className={`text-left rounded-lg border px-3 py-3 transition
              ${catIdx === i
                ? "border-amber-400 bg-amber-500/15 ring-1 ring-amber-500/40"
                : "border-stone-700 hover:border-amber-500/50 bg-stone-900/40"}`}
          >
            <div className="font-serif text-amber-100">{c.name}</div>
            <div className="text-[11px] opacity-60 mt-0.5 line-clamp-2">{c.description}</div>
            <div className="text-[10px] opacity-40 mt-1">{t("picker.variants", { n: c.variants.length })}</div>
          </button>
        ))}
      </div>

      {category && variant && activePreset && (
        <>
          <CharacterFigurePreview
            key={`${category.key}-${variant.key}-${skin}-${outfitStyle}-${equipped.join(",")}`}
            preset={activePreset}
            height={340}
            active
          />

          <div className="mt-4 space-y-3">
            <SkinVariantPicker
              roleId={activePreset.id}
              value={skin}
              onChange={setSkin}
            />
            {showWardrobe && (
              <>
                <OutfitStylePicker
                  roleId={activePreset.id}
                  value={outfitStyle}
                  onChange={setOutfitStyle}
                />
                <WardrobeChecklist
                  roleId={activePreset.id}
                  equipped={propSlugs}
                  onChange={setPropSlugs}
                />
              </>
            )}
          </div>

          <div className="flex items-center justify-between mt-4 mb-2 px-1">
            <div className="text-sm opacity-70">
              {t("picker.chooseLook", { cat: category.name, i: varIdx + 1, n: variants.length })}
            </div>
            <div className="flex gap-1">
              <button type="button" disabled={varIdx <= 0}
                      onClick={() => scrollToVariant(varIdx - 1)}
                      className="w-8 h-8 rounded border border-stone-600
                                 disabled:opacity-30 hover:border-amber-400">‹</button>
              <button type="button" disabled={varIdx >= variants.length - 1}
                      onClick={() => scrollToVariant(varIdx + 1)}
                      className="w-8 h-8 rounded border border-stone-600
                                 disabled:opacity-30 hover:border-amber-400">›</button>
            </div>
          </div>

          <div
            ref={scrollerRef}
            className="flex gap-2 overflow-x-auto snap-x snap-mandatory pb-2"
            style={{ scrollSnapType: "x mandatory" }}
          >
            {variants.map((v, i) => {
              const preset = getFigure(v.figure || `${seedKey}_${v.key}`);
              return (
                <CharacterFigureThumb
                  key={v.key}
                  preset={preset}
                  name={v.name}
                  profession={v.profession}
                  selected={i === varIdx}
                  onClick={() => scrollToVariant(i)}
                />
              );
            })}
          </div>

          <div className="mt-3 px-1">
            <div className="font-serif text-lg text-amber-100">{variant.name}</div>
            {variant.profession && (
              <div className="text-[12px] opacity-60">{variant.profession}</div>
            )}
            <p className="text-[13px] opacity-75 mt-1 leading-relaxed">{variant.persona}</p>
            {variant.traits?.length ? (
              <div className="flex flex-wrap gap-1 mt-2">
                {variant.traits.map((t) => (
                  <span key={t} className="text-[10px] px-1.5 py-0.5 rounded
                                           bg-stone-800 border border-stone-700">{t}</span>
                ))}
              </div>
            ) : null}
          </div>

          {variant.equipment && Object.keys(variant.equipment).length > 0 ? (
            <div className="mt-4 rounded-xl border border-stone-700 bg-stone-900/50 p-4">
              <div className="text-[10px] uppercase tracking-widest opacity-50 mb-2">
                {t("picker.gear")}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(variant.equipment).map(([slot, item]) => (
                  <div key={slot}
                       className="rounded-md border border-stone-700 bg-stone-950/60 px-2.5 py-2">
                    <div className="text-[10px] opacity-50">{slot}</div>
                    <div className="text-sm text-amber-100/90">{item}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <button
            type="button"
            disabled={loading}
            onClick={() => onConfirm(
              category.key,
              variant,
              skin,
              equipped,
              outfitStyle,
            )}
            className="mt-6 w-full py-3 rounded-md bg-amber-500/90 text-stone-900
                       font-semibold disabled:opacity-40 hover:bg-amber-400"
          >
            {loading
              ? t("picker.entering")
              : (confirmLabel || t("picker.enterAs", { name: variant.name }))}
          </button>
        </>
      )}
    </div>
  );
}
