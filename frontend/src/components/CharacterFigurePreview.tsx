"use client";

import { Component, Suspense, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { Environment, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import HumanoidFigure from "@/components/HumanoidFigure";
import type { FigurePreset } from "@/lib/characterFigures";
import { genreStageMood } from "@/lib/gltfCharacters";

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

function SilhouetteFallback({ preset, height }: { preset: FigurePreset; height: number }) {
  return (
    <div className="w-full flex flex-col items-center justify-end pb-8"
         style={{ height, background: `radial-gradient(ellipse at 50% 30%, ${preset.accent}22, #0c0a09 70%)` }}>
      <div className="relative" style={{ width: 110, height: 200 }}>
        <div className="absolute left-1/2 -translate-x-1/2 top-1 w-14 h-8 rounded-[50%]" style={{ background: preset.hair }} />
        <div className="absolute left-1/2 -translate-x-1/2 top-4 w-12 h-14 rounded-[48%]"
             style={{ background: `linear-gradient(180deg, ${preset.skin}, ${preset.skin}cc)` }} />
        <div className="absolute left-[40px] top-4 w-3.5 h-4 rounded-b-full" style={{ background: preset.hair }} />
        <div className="absolute left-[52px] top-3.5 w-4 h-5 rounded-b-full" style={{ background: preset.hair }} />
        <div className="absolute left-[64px] top-4 w-3.5 h-4 rounded-b-full" style={{ background: preset.hair }} />
        <div className="absolute left-[44px] top-[34px] w-2.5 h-2 rounded-full bg-[#f8f4ec]">
          <div className="m-[2px] w-1.5 h-1.5 rounded-full bg-stone-900" />
        </div>
        <div className="absolute left-[60px] top-[34px] w-2.5 h-2 rounded-full bg-[#f8f4ec]">
          <div className="m-[2px] w-1.5 h-1.5 rounded-full bg-stone-900" />
        </div>
        <div className="absolute left-1/2 -translate-x-1/2 top-[48px] w-3.5 h-1 rounded-full bg-[#a04840]/70" />
        <div className="absolute left-1/2 -translate-x-1/2 top-[3.9rem] w-3 h-2.5" style={{ background: preset.skin }} />
        <div className="absolute left-1/2 -translate-x-1/2 top-[4.4rem] w-[4.5rem] h-3.5 rounded-t-2xl" style={{ background: preset.torso }} />
        <div className="absolute left-1/2 -translate-x-1/2 top-[5rem] w-12 h-12"
             style={{ background: `linear-gradient(180deg, ${preset.torso}, ${preset.legs})`,
               clipPath: "polygon(10% 0, 90% 0, 75% 100%, 25% 100%)" }} />
        <div className="absolute left-2 top-[4.7rem] w-3 h-14 rounded-full origin-top"
             style={{ background: preset.torso, transform: "rotate(14deg)" }} />
        <div className="absolute right-2 top-[4.7rem] w-3 h-14 rounded-full origin-top"
             style={{ background: preset.torso, transform: "rotate(-14deg)" }} />
        <div className="absolute left-[42px] top-[8rem] w-3.5 h-11 rounded-b-lg" style={{ background: preset.legs }} />
        <div className="absolute left-[58px] top-[8rem] w-3.5 h-11 rounded-b-lg" style={{ background: preset.legs }} />
      </div>
      <div className="text-[12px] font-serif text-amber-100/80 mt-2">{preset.label}</div>
    </div>
  );
}

function Stage({ preset, active, interactive }: { preset: FigurePreset; active?: boolean; interactive?: boolean }) {
  const mood = genreStageMood(preset.genre);
  return (
    <>
      <color attach="background" args={[mood.bg]} />
      <fog attach="fog" args={[mood.fog, 8, 18]} />

      <ambientLight intensity={0.28} color="#3a4250" />
      <hemisphereLight args={[mood.fill, "#120c08", 0.4]} />

      <pointLight
        position={[0.65, 1.85, 1.45]}
        intensity={active ? 1.35 : 1.0}
        color={mood.key}
        distance={7}
        decay={2}
      />
      <pointLight
        position={[-0.4, 1.15, 1.15]}
        intensity={0.35}
        color={mood.key}
        distance={4}
        decay={2}
      />
      <directionalLight position={[-2.4, 1.6, -0.8]} intensity={0.42} color={mood.fill} />
      <directionalLight position={[1.2, 2.5, -2.2]} intensity={0.45} color={mood.rim} />
      <directionalLight position={[1.5, 2.8, 2.2]} intensity={0.85} color="#ffe8d0" />
      <pointLight position={[0, 0.35, 0.8]} intensity={0.25} color="#4a3020" distance={3} />

      <Suspense fallback={null}>
        <Environment
          preset={preset.genre === "scifi" ? "night" : preset.genre === "mystery" ? "night" : "warehouse"}
          environmentIntensity={0.22}
        />
      </Suspense>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <circleGeometry args={[1.5, 64]} />
        <meshPhysicalMaterial color="#121018" roughness={0.92} metalness={0.05} />
      </mesh>
      <mesh position={[0, 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.7, 0.92, 64]} />
        <meshPhysicalMaterial
          color={preset.accent}
          emissive={mixGold(preset.accent)}
          emissiveIntensity={active ? 0.45 : 0.18}
          metalness={0.75}
          roughness={0.28}
          clearcoat={0.4}
        />
      </mesh>
      <mesh position={[0, -0.08, 0]}>
        <cylinderGeometry args={[0.78, 0.88, 0.16, 48]} />
        <meshPhysicalMaterial color="#1a1410" metalness={0.35} roughness={0.55} />
      </mesh>

      <group position={[0, 0.04, 0]}>
        <HumanoidFigure preset={preset} highlight={!!active} scale={0.96} showcase />
      </group>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <circleGeometry args={[0.6, 40]} />
        <meshBasicMaterial color="#000000" transparent opacity={0.55} depthWrite={false} />
      </mesh>

      <OrbitControls
        enableZoom={false}
        enablePan={false}
        enableRotate
        minPolarAngle={interactive ? Math.PI / 4.2 : Math.PI / 2.85}
        maxPolarAngle={interactive ? Math.PI / 1.75 : Math.PI / 2.25}
        target={[0, 0.95, 0]}
        autoRotate={!interactive}
        autoRotateSpeed={active ? 0.45 : 0.25}
      />
    </>
  );
}

function mixGold(accent: string) {
  const a = new THREE.Color(accent);
  a.lerp(new THREE.Color("#c9a227"), 0.4);
  return `#${a.getHexString()}`;
}

/** Single WebGL canvas character showcase — mount only one at a time. */
export default function CharacterFigurePreview({
  preset, height = 320, active = true, interactive = false,
}: Props) {
  const fallback = <SilhouetteFallback preset={preset} height={height} />;
  const mood = genreStageMood(preset.genre);

  return (
    <div
      className={`relative rounded-xl border overflow-hidden
        ${active
          ? "border-amber-400/90 ring-1 ring-amber-500/40 shadow-[0_8px_40px_rgba(0,0,0,0.4)]"
          : "border-stone-700"}`}
      style={{
        height,
        background: `radial-gradient(ellipse at 40% 15%, ${preset.accent}28 0%, ${mood.bg} 40%, #030208 100%)`,
      }}
    >
      <CanvasErrorBoundary fallback={fallback}>
        <Canvas
          key={`fig-${preset.id}-${preset.skinVariant}-${preset.clothPack}`}
          shadows
          dpr={[1, 1.75]}
          gl={{
            antialias: true,
            alpha: false,
            powerPreference: "high-performance",
            toneMapping: THREE.ACESFilmicToneMapping,
            toneMappingExposure: mood.exposure,
            failIfMajorPerformanceCaveat: false,
          }}
          camera={{ position: [0.9, 1.35, 3.2], fov: 30, near: 0.1, far: 40 }}
          onCreated={({ gl }) => {
            gl.setClearColor(mood.bg);
            gl.outputColorSpace = THREE.SRGBColorSpace;
          }}
        >
          <Stage preset={preset} active={active} interactive={interactive} />
        </Canvas>
      </CanvasErrorBoundary>
      <div className="absolute inset-x-0 bottom-0 pointer-events-none
                      bg-gradient-to-t from-black/85 via-black/35 to-transparent pt-12 pb-2.5">
        <div className="text-center text-[13px] font-serif tracking-wide text-amber-50">
          {preset.label}
        </div>
        <div className="text-center text-[9px] uppercase tracking-[0.18em] text-stone-400/80 mt-0.5">
          {preset.genre} · body:{preset.bodyId} · skin:{preset.skinVariant} · {preset.clothPack}/{preset.metalPack}
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
      className={`snap-center shrink-0 w-[148px] rounded-xl border p-2 text-left transition
        ${selected
          ? "border-amber-400 bg-amber-500/15 ring-1 ring-amber-500/40"
          : "border-stone-700 bg-stone-900/50 hover:border-amber-500/40"}`}
    >
      <div
        className="rounded-lg h-[132px] relative overflow-hidden flex items-end justify-center"
        style={{
          background: `radial-gradient(ellipse at 50% 20%, ${preset.accent}40, #1c1917 55%, #0c0a09 100%)`,
        }}
      >
        <div
          className="relative mb-2 origin-bottom"
          style={{ width: 72, height: 118, transform: `scale(${0.92 + (bulk - 1) * 0.55}, ${0.9 + (tall - 1) * 1.2})` }}
        >
          {/* hair mass */}
          <div className="absolute left-1/2 -translate-x-1/2 top-0 w-11 h-7 rounded-[50%_50%_40%_40%]"
               style={{ background: preset.hair }} />
          {/* head oval */}
          <div className="absolute left-1/2 -translate-x-1/2 top-3 w-9 h-10 rounded-[46%]"
               style={{
                 background: `linear-gradient(180deg, ${skinDeep} 0%, ${skinDeep}ee 70%, ${skinDeep}cc)`,
                 boxShadow: "inset 0 -6px 10px rgba(0,0,0,0.12)",
               }} />
          {/* bangs */}
          <div className="absolute left-[22px] top-3 w-3 h-3.5 rounded-b-full" style={{ background: preset.hair }} />
          <div className="absolute left-[32px] top-2.5 w-3.5 h-4 rounded-b-full" style={{ background: preset.hair }} />
          <div className="absolute left-[42px] top-3 w-3 h-3.5 rounded-b-full" style={{ background: preset.hair }} />
          {/* eyes */}
          <div className="absolute left-[28px] top-[26px] w-[7px] h-[6px] rounded-full bg-[#f8f4ec] shadow-sm">
            <div className="absolute left-[1.5px] top-[1px] w-[4px] h-[4px] rounded-full bg-[#2a1810]" />
          </div>
          <div className="absolute left-[42px] top-[26px] w-[7px] h-[6px] rounded-full bg-[#f8f4ec] shadow-sm">
            <div className="absolute left-[1.5px] top-[1px] w-[4px] h-[4px] rounded-full bg-[#2a1810]" />
          </div>
          {/* nose / mouth hints */}
          <div className="absolute left-1/2 -translate-x-1/2 top-[34px] w-1 h-1.5 rounded-sm opacity-50"
               style={{ background: skinDeep, filter: "brightness(0.85)" }} />
          <div className="absolute left-1/2 -translate-x-1/2 top-[40px] w-2.5 h-0.5 rounded-full bg-[#a04840]/60" />
          {/* neck */}
          <div className="absolute left-1/2 -translate-x-1/2 top-[3rem] w-2.5 h-2" style={{ background: skinDeep }} />
          {/* shoulders */}
          <div className="absolute left-1/2 -translate-x-1/2 top-[3.35rem] w-[52px] h-3 rounded-t-xl"
               style={{ background: preset.torso }} />
          {/* torso taper */}
          <div className="absolute left-1/2 -translate-x-1/2 top-[3.7rem] w-10 h-8"
               style={{
                 background: `linear-gradient(180deg, ${preset.torso}, ${preset.legs})`,
                 clipPath: "polygon(8% 0, 92% 0, 78% 100%, 22% 100%)",
               }} />
          {/* arms */}
          <div className="absolute left-[8px] top-[3.55rem] w-2 h-8 rounded-full origin-top"
               style={{ background: `linear-gradient(180deg, ${preset.torso}, ${skinDeep})`, transform: "rotate(16deg)" }} />
          <div className="absolute right-[8px] top-[3.55rem] w-2 h-8 rounded-full origin-top"
               style={{ background: `linear-gradient(180deg, ${preset.torso}, ${skinDeep})`, transform: "rotate(-16deg)" }} />
          {/* legs */}
          <div className="absolute left-[28px] top-[5.7rem] w-2.5 h-7 rounded-b-md" style={{ background: preset.legs }} />
          <div className="absolute left-[40px] top-[5.7rem] w-2.5 h-7 rounded-b-md" style={{ background: preset.legs }} />
          {preset.cape && (
            <div className="absolute left-1/2 -translate-x-1/2 top-[3.4rem] w-14 h-12 -z-10 rounded-b-2xl opacity-50"
                 style={{ background: preset.accent }} />
          )}
          {preset.head === "fedora" && (
            <div className="absolute left-1/2 -translate-x-1/2 top-0.5 w-12 h-2 rounded-full bg-stone-800" />
          )}
          {preset.head === "bamboo_hat" && (
            <div className="absolute left-1/2 -translate-x-1/2 -top-0.5 w-14 h-3 rounded-[50%] bg-amber-700/90" />
          )}
          {preset.head === "futou" && (
            <div className="absolute left-1/2 -translate-x-1/2 top-1 w-10 h-2.5 bg-slate-800" />
          )}
          {preset.head === "visor" && (
            <div className="absolute left-1/2 -translate-x-1/2 top-[22px] w-8 h-2 rounded bg-cyan-400/80" />
          )}
          {preset.head === "mask" && (
            <div className="absolute left-1/2 -translate-x-1/2 top-[28px] w-7 h-3 rounded bg-stone-900" />
          )}
          {preset.coat === "apron" && (
            <div className="absolute left-1/2 -translate-x-1/2 top-[4.2rem] w-9 h-10 bg-stone-100/80"
                 style={{ clipPath: "polygon(10% 0, 90% 0, 85% 100%, 15% 100%)" }} />
          )}
          {preset.weapon !== "none" && (
            <div className="absolute right-0.5 top-12 w-1 h-10 rounded-full"
                 style={{ background: `linear-gradient(180deg, #e2e8f0, ${preset.accent})` }} />
          )}
        </div>
      </div>
      <div className="mt-1.5 px-0.5">
        <div className="font-serif text-[13px] text-amber-100 truncate">{name}</div>
        {profession && (
          <div className="text-[10px] opacity-50 truncate">{profession}</div>
        )}
      </div>
    </button>
  );
}
