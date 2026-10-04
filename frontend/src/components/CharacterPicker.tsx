"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CharacterCategory, CharacterVariant } from "@/lib/api";
import CharacterFigurePreview, { CharacterFigureThumb } from "@/components/CharacterFigurePreview";
import {
  ROLE_SKIN_IDS, getFigure, withSkinVariant, type RoleSkinId,
} from "@/lib/characterFigures";
import { ROLE_SKIN_LABELS } from "@/lib/gltfCharacters";

type Props = {
  categories: CharacterCategory[];
  seedKey: string;
  seedName: string;
  loading?: boolean;
  onConfirm: (categoryKey: string, variant: CharacterVariant, skin: RoleSkinId) => void;
};

export default function CharacterPicker({
  categories, seedKey, seedName, loading, onConfirm,
}: Props) {
  const [catIdx, setCatIdx] = useState(0);
  const [varIdx, setVarIdx] = useState(0);
  const [skin, setSkin] = useState<RoleSkinId>("fair");
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
    if (basePreset) setSkin(basePreset.skinVariant);
  }, [basePreset?.id]);

  const activePreset = basePreset ? withSkinVariant(basePreset, skin) : null;

  const scrollToVariant = useCallback((idx: number) => {
    setVarIdx(idx);
    const el = scrollerRef.current;
    if (!el) return;
    const card = el.children[idx] as HTMLElement | undefined;
    if (card) card.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, []);

  if (!categories.length) {
    return <p className="opacity-60 text-sm">暂无角色数据。</p>;
  }

  return (
    <div className="w-full max-w-3xl">
      <div className="text-center mb-6">
        <h2 className="font-serif text-2xl">选择你的角色</h2>
        <p className="text-sm opacity-60 mt-1">进入《{seedName}》之前，先择一类身份与形象</p>
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
            <div className="text-[10px] opacity-40 mt-1">{c.variants.length} 种形象</div>
          </button>
        ))}
      </div>

      {category && variant && activePreset && (
        <>
          <CharacterFigurePreview
            key={`${category.key}-${variant.key}-${skin}`}
            preset={activePreset}
            height={340}
            active
          />

          <div className="mt-4 rounded-xl border border-stone-700 bg-stone-900/50 p-3">
            <div className="text-[10px] uppercase tracking-widest opacity-50 mb-2">
              皮肤色调（本角色专属贴图 · 4 选 1）
            </div>
            <div className="grid grid-cols-4 gap-2">
              {ROLE_SKIN_IDS.map((id) => {
                const swatch = withSkinVariant(activePreset, id).skin;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setSkin(id)}
                    className={`rounded-lg border px-2 py-2 text-center transition
                      ${skin === id
                        ? "border-amber-400 bg-amber-500/15 ring-1 ring-amber-500/40"
                        : "border-stone-700 hover:border-amber-500/40"}`}
                  >
                    <div
                      className="mx-auto mb-1.5 h-8 w-8 rounded-full border border-stone-600"
                      style={{ background: `linear-gradient(145deg, ${swatch}, ${swatch}aa)` }}
                    />
                    <div className="text-[11px] text-amber-100/90">{ROLE_SKIN_LABELS[id]}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-between mt-4 mb-2 px-1">
            <div className="text-sm opacity-70">
              {category.name} · 选择形象（{varIdx + 1}/{variants.length}）
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

          <div className="mt-4 rounded-xl border border-stone-700 bg-stone-900/50 p-4">
            <div className="text-[10px] uppercase tracking-widest opacity-50 mb-2">
              配套装备
            </div>
            {variant.equipment && Object.keys(variant.equipment).length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(variant.equipment).map(([slot, item]) => (
                  <div key={slot}
                       className="rounded-md border border-stone-700 bg-stone-950/60 px-2.5 py-2">
                    <div className="text-[10px] opacity-50">{slot}</div>
                    <div className="text-sm text-amber-100/90">{item}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[12px] opacity-50">轻装上路，无特别装备。</p>
            )}
          </div>

          <button
            type="button"
            disabled={loading}
            onClick={() => onConfirm(category.key, variant, skin)}
            className="mt-6 w-full py-3 rounded-md bg-amber-500/90 text-stone-900
                       font-semibold disabled:opacity-40 hover:bg-amber-400"
          >
            {loading ? "正在进入世界…" : `以「${variant.name}」的身份进入`}
          </button>
        </>
      )}
    </div>
  );
}
