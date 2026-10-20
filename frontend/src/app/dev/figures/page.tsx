"use client";

/** Gallery: hy3d bodies + outfit style + optional props. */
import { useMemo, useState } from "react";
import CharacterFigurePreview, { CharacterFigureThumb } from "@/components/CharacterFigurePreview";
import OutfitStylePicker from "@/components/OutfitStylePicker";
import WardrobeChecklist from "@/components/WardrobeChecklist";
import {
  FIGURE_PRESETS, presetsForGenre, withEquippedProps, withOutfitStyle,
  type SceneGenre,
} from "@/lib/characterFigures";
import {
  mergeEquipped,
  type OutfitStyleId,
} from "@/lib/ancientRoleProps";

const GENRES: { key: SceneGenre; label: string }[] = [
  { key: "wuxia", label: "武侠" },
  { key: "ancient", label: "古代" },
  { key: "scifi", label: "科幻" },
  { key: "xuanhuan", label: "玄幻" },
  { key: "mystery", label: "悬疑" },
];

export default function DevFiguresPage() {
  const [genre, setGenre] = useState<SceneGenre>("ancient");
  const [outfitStyle, setOutfitStyle] = useState<OutfitStyleId>("default");
  const [propSlugs, setPropSlugs] = useState<string[]>([]);
  const list = useMemo(() => {
    const g = presetsForGenre(genre);
    const npcs = Object.values(FIGURE_PRESETS).filter(
      (p) => p.id.startsWith("npc_") && (genre === "wuxia" || p.genre === genre),
    );
    const ids = new Set(g.map((p) => p.id));
    if (genre === "wuxia") {
      for (const n of npcs) if (!ids.has(n.id)) g.push(n);
    }
    return g;
  }, [genre]);
  const [sel, setSel] = useState(list[0]?.id || "ancient_student");
  const activeId = list.some((p) => p.id === sel) ? sel : list[0]?.id;
  const base = activeId ? FIGURE_PRESETS[activeId] : FIGURE_PRESETS.ancient_student;
  const equipped = useMemo(
    () => mergeEquipped(outfitStyle, propSlugs),
    [outfitStyle, propSlugs],
  );
  const main = withEquippedProps(withOutfitStyle(base, outfitStyle), equipped);
  const showWardrobe = genre === "ancient" || main.id.startsWith("ancient_");

  return (
    <main className="min-h-screen bg-stone-950 text-stone-100 p-6">
      <h1 className="font-serif text-xl text-amber-100 mb-2">角色形象核对</h1>
      <p className="text-xs text-stone-500 mb-4">
        服装风格单选 · 道具勾选后才挂载 · 预览框内日光照明
      </p>

      <div className="flex flex-wrap gap-2 mb-5">
        {GENRES.map((g) => (
          <button
            key={g.key}
            type="button"
            onClick={() => {
              setGenre(g.key);
              const next = presetsForGenre(g.key)[0];
              if (next) {
                setSel(next.id);
                setOutfitStyle("default");
                setPropSlugs([]);
              }
            }}
            className={`px-3 py-1.5 rounded-lg border text-sm font-serif transition
              ${genre === g.key
                ? "border-amber-400 bg-amber-500/15 text-amber-50"
                : "border-stone-700 text-stone-400 hover:border-amber-500/40"}`}
          >
            {g.label}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] max-w-6xl">
        <div className="space-y-4">
          <CharacterFigurePreview
            key={`${main.id}-${equipped.join(",")}`}
            preset={main}
            height={440}
            active
          />
          {showWardrobe && (
            <>
              <OutfitStylePicker
                roleId={main.id}
                value={outfitStyle}
                onChange={setOutfitStyle}
              />
              <WardrobeChecklist
                roleId={main.id}
                equipped={propSlugs}
                onChange={setPropSlugs}
              />
            </>
          )}
        </div>
        <div className="flex flex-wrap gap-3 content-start max-h-[720px] overflow-y-auto pr-1">
          {list.map((p) => (
            <CharacterFigureThumb
              key={p.id}
              preset={p}
              name={p.label}
              profession={`body:${p.bodyId}`}
              selected={p.id === main.id}
              onClick={() => {
                setSel(p.id);
                setOutfitStyle("default");
                setPropSlugs([]);
              }}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
