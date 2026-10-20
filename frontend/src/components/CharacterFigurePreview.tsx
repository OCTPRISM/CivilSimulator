"use client";

import { Component, Suspense, useEffect, useState, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { Environment, OrbitControls, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import HumanoidFigure from "@/components/HumanoidFigure";
import type { FigurePreset } from "@/lib/characterFigures";
import { ensureAncientPropsReadyLoaded } from "@/lib/ancientRoleProps";
import {
  ensureHy3dNpcReadyLoaded, ensureHy3dOutfitReadyLoaded, ensureHy3dSkinReadyLoaded,
  roleBodyDef,
} from "@/lib/gltfCharacters";

/** Daylight mood scoped to the preview canvas only — page chrome stays system-dark. */
const DAYLIGHT = {
  bg: "#c5e2f6",
  fog: "#e4f1fb",
  exposure: 1.4,
} as const;

type Props = {
  preset: FigurePreset;
  height?: number;
  active?: boolean;
  /** Manual drag-to-rotate (Play character overlay UI-009). */
  interactive?: boolean;
};

class CanvasErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  render() {
    if (this.state.error) return this.props.fallback;
    return this.props.children;
  }
}

function SoftLoading({ height }: { height: number }) {
  return (
    <div
      className="w-full flex items-center justify-center text-[12px] text-amber-900/50 font-serif"
      style={{
        height,
        background: "radial-gradient(ellipse at 50% 30%, #fff6e0 0%, #c5e2f6 55%, #9ec4e0 100%)",
      }}
    >
      形象载入中…
    </div>
  );
}

function Stage({
  preset, active, interactive, assetsReady,
}: {
  preset: FigurePreset;
  active?: boolean;
  interactive?: boolean;
  assetsReady: boolean;
}) {
  return (
    <>
      <color attach="background" args={[DAYLIGHT.bg]} />
      <fog attach="fog" args={[DAYLIGHT.fog, 14, 28]} />

      <ambientLight intensity={0.72} color="#fff8ee" />
      <hemisphereLight args={["#e8f4ff", "#d8c8a8", 0.85]} />

      {/* Key sun */}
      <directionalLight
        position={[3.2, 5.5, 2.4]}
        intensity={active ? 2.1 : 1.7}
        color="#fff4d8"
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />
      {/* Soft fill sky */}
      <directionalLight position={[-2.8, 3.2, -1.2]} intensity={0.75} color="#b8d8f8" />
      {/* Warm rim */}
      <directionalLight position={[-1.2, 2.2, -2.8]} intensity={0.55} color="#ffe0a0" />
      <pointLight position={[0.4, 1.6, 1.6]} intensity={0.45} color="#fff6e8" distance={8} decay={2} />

      <Suspense fallback={null}>
        <Environment preset="park" environmentIntensity={0.55} />
      </Suspense>

      {/* Light ground — sunny plaza, not a dark dais */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <circleGeometry args={[2.2, 64]} />
        <meshStandardMaterial color="#e8dcc4" roughness={0.92} metalness={0.02} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
        <ringGeometry args={[0.55, 0.78, 64]} />
        <meshStandardMaterial color="#f0e6d0" roughness={0.7} metalness={0.08} />
      </mesh>

      <group position={[0, 0.02, 0]}>
        {assetsReady ? (
          <HumanoidFigure preset={preset} highlight={!!active} scale={0.96} showcase />
        ) : null}
      </group>

      <OrbitControls
        enableZoom={false}
        enablePan={false}
        enableRotate
        minPolarAngle={interactive ? Math.PI / 3.4 : Math.PI / 2.55}
        maxPolarAngle={interactive ? Math.PI / 1.65 : Math.PI / 2.05}
        target={[0, 0.95, 0]}
        autoRotate={!interactive}
        autoRotateSpeed={active ? 0.45 : 0.25}
      />
    </>
  );
}

/** Single WebGL canvas character showcase — mount only one at a time. */
export default function CharacterFigurePreview({
  preset, height = 320, active = true, interactive = false,
}: Props) {
  const soft = <SoftLoading height={height} />;
  const [assetsReady, setAssetsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      ensureHy3dNpcReadyLoaded(),
      ensureHy3dSkinReadyLoaded(),
      ensureHy3dOutfitReadyLoaded(),
      ensureAncientPropsReadyLoaded(),
    ]).then(() => {
      if (cancelled) return;
      // Prefetch body GLB so Suspense rarely stalls on empty frame.
      try {
        const def = roleBodyDef(
          preset.bodyId || preset.id,
          preset.skinVariant,
          preset.outfitStyle,
        );
        useGLTF.preload(def.url);
      } catch { /* ignore */ }
      setAssetsReady(true);
    });
    return () => { cancelled = true; };
  }, [preset.bodyId, preset.id, preset.skinVariant, preset.outfitStyle]);

  const outfitNote = preset.outfitStyle && preset.outfitStyle !== "default"
    ? preset.outfitStyle
    : "本职装束";
  const propNote = (preset.equippedProps || []).length
    ? ` · 道具${preset.equippedProps!.length}`
    : "";

  return (
    <div
      className={`relative rounded-xl border overflow-hidden
        ${active
          ? "border-amber-400/90 ring-1 ring-amber-500/40 shadow-[0_8px_40px_rgba(0,0,0,0.4)]"
          : "border-stone-700"}`}
      style={{ height, background: "#0c0a09" }}
    >
      <CanvasErrorBoundary fallback={soft}>
        <Canvas
          key={`fig-${preset.id}-${preset.skinVariant}-${preset.outfitStyle || "default"}-${(preset.equippedProps || []).join(",")}-${preset.clothPack}`}
          shadows
          dpr={[1, 1.75]}
          gl={{
            antialias: true,
            alpha: false,
            powerPreference: "high-performance",
            toneMapping: THREE.ACESFilmicToneMapping,
            toneMappingExposure: DAYLIGHT.exposure,
            failIfMajorPerformanceCaveat: false,
          }}
          camera={{ position: [1.35, 0.95, 4.6], fov: 32, near: 0.1, far: 40 }}
          onCreated={({ gl }) => {
            gl.setClearColor(DAYLIGHT.bg);
            gl.outputColorSpace = THREE.SRGBColorSpace;
          }}
        >
          <Stage
            preset={preset}
            active={active}
            interactive={interactive}
            assetsReady={assetsReady}
          />
        </Canvas>
      </CanvasErrorBoundary>
      {!assetsReady && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none
                        text-[12px] font-serif text-amber-100/50 bg-stone-950/40">
          形象载入中…
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 pointer-events-none
                      bg-gradient-to-t from-black/80 via-black/25 to-transparent pt-12 pb-2.5">
        <div className="text-center text-[13px] font-serif tracking-wide text-amber-50">
          {preset.label}
        </div>
        <div className="text-center text-[9px] uppercase tracking-[0.18em] text-stone-400/80 mt-0.5">
          {preset.genre} · {outfitNote}{propNote}
        </div>
      </div>
    </div>
  );
}

/** Lightweight CSS card — no WebGL (safe for carousels). */
export function CharacterFigureThumb({
  preset, selected, onClick, name, profession,
}: {
  preset: FigurePreset;
  selected?: boolean;
  onClick?: () => void;
  name: string;
  profession?: string;
}) {
  const skinDeep = preset.skin;
  const bulk = preset.build?.bulk ?? 1;
  const tall = (preset.build?.height ?? 1) * (preset.tall ? 1.04 : 1);
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-[148px] shrink-0 snap-center rounded-xl border p-2.5 text-left transition
        ${selected
          ? "border-amber-400 bg-amber-500/15 ring-1 ring-amber-500/40"
          : "border-stone-700 bg-stone-900/40 hover:border-amber-500/40"}`}
    >
      <div
        className="relative mx-auto mb-2 overflow-hidden rounded-lg"
        style={{
          width: 120,
          height: 150,
          background: `radial-gradient(ellipse at 50% 20%, ${preset.accent}28, #0c0a09 70%)`,
        }}
      >
        <div className="absolute left-1/2 -translate-x-1/2 bottom-2"
             style={{ transform: `translateX(-50%) scale(${0.85 * bulk}, ${0.85 * tall})`, transformOrigin: "bottom center" }}>
          <div className="relative" style={{ width: 54, height: 100 }}>
            <div className="absolute left-1/2 -translate-x-1/2 top-0 w-7 h-4 rounded-[50%]" style={{ background: preset.hair }} />
            <div className="absolute left-1/2 -translate-x-1/2 top-2 w-6 h-7 rounded-[48%]"
                 style={{ background: `linear-gradient(180deg, ${skinDeep}, ${skinDeep}cc)` }} />
            <div className="absolute left-1/2 -translate-x-1/2 top-[2.1rem] w-8 h-2 rounded-t-xl" style={{ background: preset.torso }} />
            <div className="absolute left-1/2 -translate-x-1/2 top-[2.5rem] w-6 h-7"
                 style={{ background: `linear-gradient(180deg, ${preset.torso}, ${preset.legs})`,
                   clipPath: "polygon(12% 0, 88% 0, 72% 100%, 28% 100%)" }} />
            <div className="absolute left-[6px] top-[2.4rem] w-1.5 h-7 rounded-full origin-top"
                 style={{ background: preset.torso, transform: "rotate(12deg)" }} />
            <div className="absolute right-[6px] top-[2.4rem] w-1.5 h-7 rounded-full origin-top"
                 style={{ background: preset.torso, transform: "rotate(-12deg)" }} />
            <div className="absolute left-[18px] top-[4.2rem] w-1.5 h-5 rounded-b" style={{ background: preset.legs }} />
            <div className="absolute left-[28px] top-[4.2rem] w-1.5 h-5 rounded-b" style={{ background: preset.legs }} />
          </div>
        </div>
      </div>
      <div className="text-[12px] font-serif text-amber-50 truncate">{name}</div>
      {profession ? (
        <div className="text-[10px] text-stone-500 truncate mt-0.5">{profession}</div>
      ) : null}
    </button>
  );
}
