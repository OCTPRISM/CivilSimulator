"use client";

/** Dev map preview — inspect per-genre 3D city layout without a play session. */
import { useEffect, useState } from "react";
import World3D, { type CameraMode } from "@/components/World3D";
import { genreKitUrls, markHy3dReady } from "@/lib/buildingKits";
import { preloadKitUrls } from "@/components/world/KitBuildingMesh";
import { MAP_JSON_REV } from "@/lib/worldMapLoader";

const GENRES: { key: string; label: string }[] = [
  { key: "ancient", label: "古代" },
  { key: "wuxia", label: "武侠" },
  { key: "xuanhuan", label: "玄幻" },
  { key: "mystery", label: "悬疑" },
  { key: "modern", label: "当代" },
  { key: "scifi", label: "科幻" },
  { key: "enterprise", label: "创业" },
  { key: "securities", label: "证券" },
  { key: "military", label: "军事" },
];

const MAP_REV = MAP_JSON_REV;

type MapStats = {
  revision?: string;
  roads: number;
  buildings: number;
  stalls: string[];
  props: number;
  landmarks: string[];
};

export default function DevMapsPage() {
  const [genre, setGenre] = useState("ancient");
  const [hour, setHour] = useState(11);
  const [cameraMode, setCameraMode] = useState<CameraMode>("third");
  const [stats, setStats] = useState<MapStats | null>(null);
  const [hyReady, setHyReady] = useState(0);
  const [hyCounts, setHyCounts] = useState({ buildings: 0, stalls: 0, props: 0 });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/models/hy3d_ready.json?t=${Date.now()}`, { cache: "no-store" });
        if (!r.ok || cancelled) return;
        const d = await r.json();
        markHy3dReady("building", d.buildings || []);
        markHy3dReady("stall", d.stalls || []);
        markHy3dReady("prop", d.props || []);
        if (!cancelled) {
          setHyCounts({
            buildings: (d.buildings || []).length,
            stalls: (d.stalls || []).length,
            props: (d.props || []).length,
          });
          setHyReady((n) => n + 1);
        }
      } catch {
        /* ignore — landmarks hardcoded in buildingKits */
      }
    })();
    return () => { cancelled = true; };
  }, [genre]);

  useEffect(() => {
    preloadKitUrls(genreKitUrls(genre));
  }, [genre, hyReady]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/maps/${genre}.json?v=${MAP_REV}`, { cache: "no-store" });
        if (!r.ok) return;
        const d = await r.json();
        if (cancelled) return;
        const stalls = (d.buildings || [])
          .filter((b: { type?: string }) => b.type === "stall")
          .map((b: { sign?: string; stallKind?: string }) => b.stallKind || b.sign || "摊");
        setStats({
          revision: d.mapBrief?.revision || d.distanceAudit?.revision || "?",
          roads: (d.roads || []).length,
          buildings: (d.buildings || []).length,
          stalls,
          props: (d.props || []).length,
          landmarks: (d.buildings || [])
            .filter((b: { modelKey?: string }) => b.modelKey)
            .map((b: { modelKey: string }) => b.modelKey),
        });
      } catch {
        /* ignore */
      }
    })();
    return () => { cancelled = true; };
  }, [genre]);

  return (
    <main className="min-h-screen bg-stone-950 text-stone-100 flex flex-col">
      <header className="px-4 py-3 border-b border-stone-800 flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-lg text-amber-100">3D 地图预览</h1>
        <div className="flex flex-wrap gap-1.5">
          {GENRES.map((g) => (
            <button
              key={g.key}
              type="button"
              onClick={() => setGenre(g.key)}
              className={`px-2.5 py-1 rounded-md border text-xs transition
                ${genre === g.key
                  ? "border-amber-400 bg-amber-500/15 text-amber-50"
                  : "border-stone-700 text-stone-400 hover:border-amber-500/40"}`}
            >
              {g.label}
            </button>
          ))}
        </div>
        <label className="text-[11px] text-stone-400 flex items-center gap-2 ml-auto">
          时辰 {hour}:00
          <input
            type="range" min={0} max={23} value={hour}
            onChange={(e) => setHour(Number(e.target.value))}
            className="w-28"
          />
        </label>
      </header>

      {stats && (
        <div className="px-4 py-2 border-b border-amber-900/40 bg-amber-950/40 text-[11px] text-amber-100 flex flex-wrap gap-x-4 gap-y-1">
          <span className="font-mono text-amber-300">rev={stats.revision}</span>
          <span className="text-cyan-200">
            引擎=Hunyuan3D · ready 建筑{hyCounts.buildings}/摊{hyCounts.stalls}/道具{hyCounts.props}
          </span>
          <span>路 {stats.roads}</span>
          <span>建筑 {stats.buildings}</span>
          <span>道具 {stats.props}</span>
          <span>地标 {stats.landmarks.join(" · ") || "—"}</span>
          <span className="text-amber-50">
            临街摊：{stats.stalls.length ? stats.stalls.join("、") : "无"}
          </span>
          {!/streetfix|roads\d/.test(stats.revision || "") && genre === "ancient" && (
            <span className="text-rose-300">⚠ 仍是旧地图缓存 — 请硬刷新 Cmd+Shift+R</span>
          )}
        </div>
      )}

      <div className="flex-1 min-h-0">
        <World3D
          key={`${genre}-${MAP_REV}-hy${hyReady}`}
          genre={genre}
          worldLocations={[]}
          agents={[]}
          playerId={null}
          height={typeof window !== "undefined" ? window.innerHeight - 96 : 720}
          cameraMode={cameraMode}
          onCameraModeChange={setCameraMode}
          hour={hour}
        />
      </div>
      <p className="absolute bottom-3 left-3 text-[10px] text-stone-500 pointer-events-none z-10">
        左键拖拽平移 · 右键旋转 · 滚轮缩放 · 单击任意处聚焦 · 硬刷新 Cmd+Shift+R
      </p>
    </main>
  );
}
