"use client";

/** Temporary public gallery to verify per-role unique GLTF + 4 skins. */
import { useMemo, useState } from "react";
import CharacterFigurePreview, { CharacterFigureThumb } from "@/components/CharacterFigurePreview";
import {
  FIGURE_PRESETS, ROLE_SKIN_IDS, presetsForGenre, withSkinVariant,
  type RoleSkinId, type SceneGenre,
} from "@/lib/characterFigures";
import { ROLE_SKIN_LABELS } from "@/lib/gltfCharacters";

const GENRES: { key: SceneGenre; label: string }[] = [
  { key: "wuxia", label: "武侠" },
  { key: "ancient", label: "古代" },
  { key: "scifi", label: "科幻" },
  { key: "xuanhuan", label: "玄幻" },
  { key: "mystery", label: "悬疑" },
];

export default function DevFiguresPage() {
  const [genre, setGenre] = useState<SceneGenre>("wuxia");
  const [skin, setSkin] = useState<RoleSkinId>("fair");
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
  const [sel, setSel] = useState(list[0]?.id || "wuxia_wanderer");
  const activeId = list.some((p) => p.id === sel) ? sel : list[0]?.id;
  const base = activeId ? FIGURE_PRESETS[activeId] : FIGURE_PRESETS.wuxia_wanderer;
  const main = withSkinVariant(base, skin);

  return (
    <main className="min-h-screen bg-stone-950 text-stone-100 p-6">
      <h1 className="font-serif text-xl text-amber-100 mb-2">角色形象核对</h1>
      <p className="text-xs text-stone-500 mb-4">
        每个角色独立 GLTF 人体；切换下方 4 套分离皮肤 PBR。服饰轮廓烘焙在 body.glb 内，非科幻底模贴皮。
      </p>

      <div className="flex flex-wrap gap-2 mb-3">
        {GENRES.map((g) => (
          <button
            key={g.key}
            type="button"
            onClick={() => {
              setGenre(g.key);
              const next = presetsForGenre(g.key)[0];
              if (next) {
                setSel(next.id);
                setSkin(next.skinVariant);
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

      <div className="flex flex-wrap gap-2 mb-5">
        {ROLE_SKIN_IDS.map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setSkin(id)}
            className={`px-3 py-1.5 rounded-lg border text-xs transition
              ${skin === id
                ? "border-amber-400 bg-amber-500/15 text-amber-50"
                : "border-stone-700 text-stone-400 hover:border-amber-500/40"}`}
          >
            {ROLE_SKIN_LABELS[id]}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] max-w-6xl">
        <CharacterFigurePreview
          key={`${main.id}-${skin}`}
          preset={main}
          height={440}
          active
        />
        <div className="flex flex-wrap gap-3 content-start max-h-[520px] overflow-y-auto pr-1">
          {list.map((p) => (
            <CharacterFigureThumb
              key={p.id}
              preset={withSkinVariant(p, skin)}
              name={p.label}
              profession={`body:${p.bodyId} · ${ROLE_SKIN_LABELS[skin]}`}
              selected={p.id === main.id}
              onClick={() => {
                setSel(p.id);
                setSkin(p.skinVariant);
              }}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
