"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";
import {
  generateMap3D,
  generateModelFromImage,
  generateModelFromText,
  getGeneratorStatus,
  listCharacterOutfits,
  listGeneratorCivilizations,
  type CharacterGenerateResult,
  type CharacterOutfit,
  type GeneratorCivilization,
  type GeneratorStatus,
  type MapGenerateResult,
} from "@/lib/api";

const GlbViewer = dynamic(() => import("@/components/generator/GlbViewer"), { ssr: false });
const WorldMapPreview = dynamic(() => import("@/components/WorldMapPreview"), { ssr: false });

type Tab = "model" | "map";
type ModelKind = "character" | "prop";
type InputMode = "text" | "image";

export default function GeneratorPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<Tab>("model");
  const [status, setStatus] = useState<GeneratorStatus | null>(null);
  const [modelKind, setModelKind] = useState<ModelKind>("character");
  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [modelPrompt, setModelPrompt] = useState("青年男子，剑眉星目，清瘦英气");
  const [civs, setCivs] = useState<GeneratorCivilization[]>([]);
  const [civId, setCivId] = useState<string>("wuxia");
  const [outfits, setOutfits] = useState<CharacterOutfit[]>([]);
  const [outfitId, setOutfitId] = useState<string | null>(null);
  const [mapPrompt, setMapPrompt] = useState("武侠江湖，青云门与落霞镇，山河纵横");
  const [mapGenre, setMapGenre] = useState("");
  const [mapResult, setMapResult] = useState<MapGenerateResult | null>(null);
  const [modelResult, setModelResult] = useState<CharacterGenerateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    const poll = () => getGeneratorStatus().then(setStatus).catch(() => setStatus(null));
    poll();
    const id = setInterval(poll, 15000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    listGeneratorCivilizations()
      .then((list) => {
        setCivs(list);
        if (list.length && !list.find((c) => c.id === civId)) {
          setCivId(list[0].id);
        }
      })
      .catch(async () => {
        // Static fallback when API offline
        try {
          const r = await fetch("/models/characters/civilizations/index.json");
          const j = await r.json();
          const list = (j.civilizations || []).map((c: {
            id: string; name: string; era?: string; outfit_count?: number; catalog_url?: string; character_url?: string;
          }) => ({
            id: c.id,
            name: c.name,
            genre: c.id,
            era: c.era || "",
            outfit_count: c.outfit_count || 4,
            character_url: c.character_url,
            catalog_url: c.catalog_url,
          }));
          setCivs(list);
        } catch {
          setCivs([]);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!civId) return;
    listCharacterOutfits(civId)
      .then((list) => {
        setOutfits(list);
        setOutfitId(list[0]?.id ?? null);
      })
      .catch(async () => {
        try {
          const r = await fetch(`/models/characters/civilizations/${civId}/catalog.json`);
          const j = await r.json();
          const list = (j.outfits || []).map((o: CharacterOutfit) => ({
            ...o,
            civilization: civId,
            era: j.era || "",
            civilization_name: j.name || civId,
          }));
          setOutfits(list);
          setOutfitId(list[0]?.id ?? null);
        } catch {
          setOutfits([]);
          setOutfitId(null);
        }
      });
  }, [civId]);

  const selectedOutfit = outfits.find((o) => o.id === outfitId) ?? null;
  const selectedCiv = civs.find((c) => c.id === civId) ?? null;

  const onMapGenerate = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const civ = mapGenre || civId || undefined;
      setMapResult(await generateMap3D(mapPrompt, civ, civ));
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [mapPrompt, mapGenre, civId]);

  const onModelGenerate = useCallback(async () => {
    setErr(null);
    setProgress(null);
    setLoading(true);
    setModelResult(null);
    try {
      const st = await getGeneratorStatus().catch(() => null);
      setStatus(st);
      if (!st?.online) {
        throw new Error(
          "Hunyuan3D 服务未启动。请在终端运行：./backend/scripts/hunyuan3d/start_server.sh"
        );
      }
      if (modelKind === "character" && !outfitId) {
        throw new Error("请选择一套服饰风格");
      }
      setProgress(
        modelKind === "character"
          ? "已提交：服饰风格 + 文生图 → 3D（CPU 可能需较长时间）…"
          : "已提交任务，正在生成…"
      );
      if (inputMode === "text") {
        if (!modelPrompt.trim()) throw new Error("请输入文本描述");
        setModelResult(await generateModelFromText(modelPrompt, modelKind, outfitId, civId));
      } else {
        const file = fileRef.current?.files?.[0];
        if (!file) throw new Error("请上传参考图");
        setModelResult(await generateModelFromImage(file, modelKind, modelPrompt, outfitId, civId));
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
      setProgress(null);
    }
  }, [inputMode, modelPrompt, modelKind, outfitId, civId]);

  const onFilePick = (f: File | null) => {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(f ? URL.createObjectURL(f) : null);
  };

  if (authLoading || !user) {
    return (
      <main className="min-h-screen flex items-center justify-center opacity-60">正在载入…</main>
    );
  }

  const glbUrl = modelResult?.glb_url ?? null;
  const curatedUrl = selectedCiv?.character_url ?? null;
  const previewUrl = glbUrl || (modelKind === "character" ? curatedUrl : null);

  return (
    <main className="min-h-screen px-4 sm:px-6 py-8 flex flex-col">
      <div className="max-w-6xl mx-auto w-full flex-1">
        <header className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div>
            <SiteLogo href="/" compact />
            <h1 className="font-serif text-2xl sm:text-3xl tracking-widest mt-4">3D 模型生成器</h1>
            <p className="text-sm opacity-55 mt-1">文本 / 参考图 → 3D 人物 · 道具 · 地图</p>
          </div>
          <div className={`text-[11px] px-3 py-1.5 rounded-full border shrink-0
            ${status?.online
              ? "border-emerald-600/50 text-emerald-300/90 bg-emerald-950/30"
              : "border-stone-600 text-stone-400"}`}>
            Hunyuan3D {status?.online ? "在线" : "离线"}
          </div>
        </header>

        <div className="flex flex-wrap gap-2 mb-6">
          {([
            ["model", "3D 模型（人物 / 道具）"],
            ["map", "3D 地图"],
          ] as [Tab, string][]).map(([t, label]) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm border transition
                ${tab === t
                  ? "border-violet-500/60 bg-violet-950/40"
                  : "border-stone-700 text-stone-400 hover:border-stone-500"}`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "model" && (
          <div className="grid lg:grid-cols-2 gap-6">
            <section className="rounded-2xl border border-stone-700/80 bg-stone-950/50 p-6 space-y-4">
              <div className="flex gap-2">
                {(["character", "prop"] as ModelKind[]).map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setModelKind(k)}
                    className={`text-[11px] px-3 py-1 rounded border transition
                      ${modelKind === k
                        ? "border-violet-500/50 bg-violet-950/30"
                        : "border-stone-700 opacity-60"}`}
                  >
                    {k === "character" ? "3D 人物" : "3D 道具"}
                  </button>
                ))}
              </div>

              <div className="flex gap-2">
                {(["text", "image"] as InputMode[]).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setInputMode(m)}
                    className={`text-[11px] px-3 py-1 rounded border transition
                      ${inputMode === m
                        ? "border-stone-500 bg-stone-900/80"
                        : "border-stone-800 opacity-50"}`}
                  >
                    {m === "text" ? "文本生成" : "参考图生成"}
                  </button>
                ))}
              </div>

              {modelKind === "character" && (
                <div className="space-y-3">
                  <div>
                    <p className="text-[11px] tracking-wide opacity-55 mb-2">文明世界</p>
                    <div className="flex flex-wrap gap-1.5">
                      {civs.map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => setCivId(c.id)}
                          className={`text-[11px] px-2.5 py-1 rounded border transition
                            ${civId === c.id
                              ? "border-amber-600/55 bg-amber-950/30"
                              : "border-stone-800 opacity-60 hover:opacity-90"}`}
                        >
                          {c.name}
                        </button>
                      ))}
                    </div>
                    {selectedCiv && (
                      <p className="text-[10px] opacity-40 mt-1.5">{selectedCiv.era}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-[11px] tracking-wide opacity-55">服饰套装（职业 × 道具）</p>
                      <p className="text-[10px] opacity-40">每文明 4 套</p>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {outfits.map((o) => {
                        const active = outfitId === o.id;
                        return (
                          <button
                            key={o.id}
                            type="button"
                            onClick={() => setOutfitId(o.id)}
                            className={`text-left rounded-xl border px-3 py-2.5 transition
                              ${active
                                ? "border-amber-600/55 bg-amber-950/25"
                                : "border-stone-800 hover:border-stone-600 bg-stone-950/40"}`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">{o.label}</span>
                              <span className="text-[10px] opacity-45">{o.occupation}</span>
                            </div>
                            <p className="text-[11px] opacity-55 mt-0.5">{o.blurb}</p>
                            <p className="text-[10px] opacity-40 mt-1.5 leading-relaxed">
                              衣：{o.clothing.slice(0, 3).join("、")}
                            </p>
                            <p className="text-[10px] opacity-40 leading-relaxed">
                              器：{o.props.join("、")}
                            </p>
                          </button>
                        );
                      })}
                    </div>
                    {selectedOutfit && (
                      <p className="text-[10px] opacity-45">
                        已选「{selectedCiv?.name ?? civId} · {selectedOutfit.label}」
                      </p>
                    )}
                  </div>
                </div>
              )}

              <textarea
                value={modelPrompt}
                onChange={(e) => setModelPrompt(e.target.value)}
                rows={4}
                className="w-full rounded-lg bg-stone-900/80 border border-stone-700 px-3 py-2
                           text-sm resize-none outline-none focus:border-violet-600/50"
                placeholder={modelKind === "character"
                  ? "描述人物外貌、气质、姿态（服饰由上方套装提供）…"
                  : "描述道具形状、材质、用途…"}
              />

              {inputMode === "image" && (
                <>
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => onFilePick(e.target.files?.[0] ?? null)}
                  />
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    className="w-full aspect-video rounded-xl border border-dashed border-stone-600
                               relative overflow-hidden hover:border-violet-500/40 transition"
                  >
                    {preview ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={preview} alt="" className="absolute inset-0 w-full h-full object-cover" />
                    ) : (
                      <span className="absolute inset-0 flex items-center justify-center text-sm opacity-45">
                        点击上传参考图（可选增强文本）
                      </span>
                    )}
                  </button>
                </>
              )}

              <button
                type="button"
                disabled={loading || (inputMode === "image" && !status?.online)}
                onClick={onModelGenerate}
                className="w-full py-2.5 rounded-lg bg-violet-600/80 hover:bg-violet-500/90
                           disabled:opacity-40 font-medium text-sm transition"
              >
                {loading
                  ? (progress || "生成中…")
                  : `生成 3D ${modelKind === "character" ? "人物" : "道具"}`}
              </button>
              {modelResult?.source && (
                <p className="text-[10px] opacity-45">
                  管线：{modelResult.source}
                  {modelResult.outfit?.label ? ` · 服饰：${modelResult.outfit.label}` : ""}
                </p>
              )}
            </section>

            <section className="rounded-2xl border border-stone-700/80 bg-stone-950/50 overflow-hidden min-h-[360px]">
              {previewUrl ? (
                <Suspense fallback={<div className="p-8 opacity-50">加载预览…</div>}>
                  <GlbViewer url={previewUrl} />
                </Suspense>
              ) : (
                <div className="min-h-[360px] flex items-center justify-center text-sm opacity-40 px-6 text-center">
                  GLB 预览区
                </div>
              )}
              {modelKind === "character" && selectedCiv && !glbUrl && (
                <p className="text-[10px] opacity-40 px-4 py-2 border-t border-stone-800">
                  预览：{selectedCiv.name} 默认人物（生成完成后替换为新模型）
                </p>
              )}
            </section>
          </div>
        )}

        {tab === "map" && (
          <div className="grid lg:grid-cols-2 gap-6">
            <section className="rounded-2xl border border-stone-700/80 bg-stone-950/50 p-6">
              <h2 className="font-serif text-xl mb-4">文本 → 3D 地图</h2>
              <textarea
                value={mapPrompt}
                onChange={(e) => setMapPrompt(e.target.value)}
                rows={5}
                className="w-full rounded-lg bg-stone-900/80 border border-stone-700 px-3 py-2
                           text-sm resize-none outline-none focus:border-emerald-600/50"
              />
              <div className="flex flex-wrap gap-2 mt-3 mb-4">
                {["ancient", "wuxia", "xuanhuan", "mystery", "modern", "scifi", "enterprise", "securities", "military"].map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setMapGenre(mapGenre === g ? "" : g)}
                    className={`text-[11px] px-2.5 py-1 rounded border transition
                      ${mapGenre === g ? "border-emerald-500/60 bg-emerald-950/40" : "border-stone-700 opacity-70"}`}
                  >
                    {g}
                  </button>
                ))}
              </div>
              <button
                type="button"
                disabled={loading}
                onClick={onMapGenerate}
                className="w-full py-2.5 rounded-lg bg-emerald-700/80 hover:bg-emerald-600/90
                           disabled:opacity-40 font-medium text-sm"
              >
                {loading ? "生成中…" : "生成 3D 地图"}
              </button>
            </section>
            <section className="space-y-4">
              {mapResult?.png_url && (
                <div className="rounded-2xl border border-stone-700/80 overflow-hidden">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={mapResult.png_url} alt="地图" className="w-full object-cover" />
                </div>
              )}
              {mapResult?.genre && (
                <div className="rounded-2xl border border-stone-700/80 overflow-hidden" style={{ height: 240 }}>
                  <Suspense fallback={null}>
                    <WorldMapPreview genre={mapResult.genre} height={240} />
                  </Suspense>
                </div>
              )}
            </section>
          </div>
        )}

        {err && (
          <p className="mt-6 text-red-400/90 text-sm rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-3">
            {err}
          </p>
        )}

        <SiteFooter />
      </div>
    </main>
  );
}
