"use client";

/**
 * Cinematic humanoid — Black Myth · Zhong Kui visual language in WebGL:
 * thick robe silhouette, skin SSS, hemp cloth, ritual metal, candle-key readable face.
 */
import { Suspense, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { FigurePreset, WeaponKind } from "@/lib/characterFigures";
import {
  ClothPhysical, LeatherPhysical, MetalPhysical, SkinPhysical,
  useClothMaps, useMetalMaps, useSkinMaps,
} from "@/lib/figureMaterials";
import GltfHumanoid from "@/components/GltfHumanoid";
import HeroCharacter from "@/components/hero/HeroCharacter";
import { isHeroPipelineRole } from "@/lib/heroCharacter";

function shade(hex: string, mul: number) {
  const c = new THREE.Color(hex);
  c.multiplyScalar(mul);
  return `#${c.getHexString()}`;
}
function mix(a: string, b: string, t: number) {
  const ca = new THREE.Color(a);
  const cb = new THREE.Color(b);
  ca.lerp(cb, t);
  return `#${ca.getHexString()}`;
}

function Seg({
  pos, rot, r, len, color, opacity, skin, skinMaps, clothMaps,
}: {
  pos: [number, number, number]; rot?: [number, number, number];
  r: number; len: number; color: string; opacity: number; skin?: boolean;
  skinMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
  clothMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
}) {
  return (
    <mesh position={pos} rotation={rot} castShadow receiveShadow>
      <capsuleGeometry args={[r, Math.max(0.02, len), 6, 12]} />
      {skin
        ? <SkinPhysical color={color} opacity={opacity} maps={skinMaps} />
        : <ClothPhysical color={color} opacity={opacity} maps={clothMaps} />}
    </mesh>
  );
}

function WeaponMesh({
  kind, accent, opacity, metalMaps,
}: {
  kind: WeaponKind; accent: string; opacity: number;
  metalMaps: { albedo: THREE.Texture; roughness: THREE.Texture } | undefined;
}) {
  if (kind === "none") return null;
  if (kind === "sword") {
    return (
      <group position={[0.42, 0.9, 0.05]} rotation={[0.06, 0.15, -0.48]}>
        <mesh castShadow position={[0, 0.42, 0]}>
          <boxGeometry args={[0.018, 0.88, 0.07]} />
          <MetalPhysical color="#d8e0ea" opacity={opacity} maps={metalMaps} roughness={0.14} />
        </mesh>
        <mesh castShadow position={[0, 0.42, 0.012]}>
          <boxGeometry args={[0.004, 0.86, 0.04]} />
          <MetalPhysical color="#f5f7fa" opacity={opacity} roughness={0.08} />
        </mesh>
        <mesh castShadow position={[0, 0.01, 0]}>
          <boxGeometry args={[0.22, 0.032, 0.06]} />
          <MetalPhysical color={accent} opacity={opacity} maps={metalMaps} />
        </mesh>
        <mesh castShadow position={[0, -0.14, 0]}>
          <cylinderGeometry args={[0.026, 0.032, 0.28, 10]} />
          <LeatherPhysical color="#2a1a10" opacity={opacity} />
        </mesh>
        <mesh castShadow position={[0, -0.3, 0]}>
          <sphereGeometry args={[0.042, 12, 12]} />
          <MetalPhysical color={accent} opacity={opacity} maps={metalMaps} emissive={accent} emissiveIntensity={0.15} />
        </mesh>
      </group>
    );
  }
  if (kind === "blade") {
    return (
      <group position={[0.4, 0.88, 0.04]} rotation={[0.05, 0.1, -0.3]}>
        <mesh castShadow position={[0, 0.32, 0]}>
          <boxGeometry args={[0.03, 0.66, 0.12]} />
          <MetalPhysical color="#a8b0bc" opacity={opacity} maps={metalMaps} roughness={0.22} />
        </mesh>
        <mesh castShadow position={[0, -0.06, 0]}>
          <cylinderGeometry args={[0.03, 0.036, 0.2, 8]} />
          <LeatherPhysical color="#1a120e" opacity={opacity} />
        </mesh>
      </group>
    );
  }
  if (kind === "staff") {
    return (
      <group position={[0.38, 0.68, 0]} rotation={[0.03, 0, -0.04]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.028, 0.034, 1.35, 10]} />
          <LeatherPhysical color="#4a3018" opacity={opacity} />
        </mesh>
        <mesh castShadow position={[0, 0.66, 0]}>
          <icosahedronGeometry args={[0.06, 0]} />
          <MetalPhysical color={accent} opacity={opacity} maps={metalMaps} emissive={accent} emissiveIntensity={0.35} />
        </mesh>
      </group>
    );
  }
  if (kind === "bow") {
    return (
      <group position={[-0.32, 1.02, -0.06]} rotation={[0, 0.38, 0.08]}>
        <mesh castShadow rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.3, 0.016, 8, 28, Math.PI * 1.15]} />
          <LeatherPhysical color="#5a3218" opacity={opacity} />
        </mesh>
      </group>
    );
  }
  if (kind === "spear") {
    return (
      <group position={[0.36, 0.72, 0]} rotation={[0.05, 0, -0.03]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.022, 0.026, 1.4, 8]} />
          <LeatherPhysical color="#3a3834" opacity={opacity} />
        </mesh>
        <mesh castShadow position={[0, 0.72, 0]}>
          <coneGeometry args={[0.048, 0.2, 8]} />
          <MetalPhysical color={accent} opacity={opacity} maps={metalMaps} />
        </mesh>
      </group>
    );
  }
  if (kind === "fan") {
    return (
      <group position={[0.38, 1.02, 0.1]} rotation={[0.28, -0.18, 0.1]}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <mesh key={i} castShadow rotation={[0, 0, (i - 2.5) * 0.14]} position={[0, 0.08, 0]}>
            <boxGeometry args={[0.03, 0.32, 0.006]} />
            <ClothPhysical color={i % 2 ? accent : "#f5e6c8"} opacity={opacity} />
          </mesh>
        ))}
      </group>
    );
  }
  if (kind === "pistol" || kind === "rifle") {
    const long = kind === "rifle";
    return (
      <group position={[0.38, 0.96, 0.14]} rotation={[0.04, -0.48, 0]}>
        <mesh castShadow>
          <boxGeometry args={[long ? 0.58 : 0.26, 0.07, 0.09]} />
          <MetalPhysical color="#1a2332" opacity={opacity} maps={metalMaps} roughness={0.4} />
        </mesh>
        <mesh castShadow position={[-0.06, -0.08, 0]}>
          <boxGeometry args={[0.08, 0.12, 0.06]} />
          <LeatherPhysical color="#0c1018" opacity={opacity} />
        </mesh>
      </group>
    );
  }
  if (kind === "scanner") {
    return (
      <group position={[0.38, 0.98, 0.12]} rotation={[0.12, -0.22, 0]}>
        <mesh castShadow>
          <boxGeometry args={[0.16, 0.28, 0.04]} />
          <MetalPhysical color="#0f172a" opacity={opacity} maps={metalMaps} />
        </mesh>
        <mesh castShadow position={[0, 0.02, 0.024]}>
          <planeGeometry args={[0.12, 0.2]} />
          <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={0.65} roughness={0.3} />
        </mesh>
      </group>
    );
  }
  return null;
}

type Props = {
  preset: FigurePreset;
  behavior?: string;
  dormant?: boolean;
  highlight?: boolean;
  scale?: number;
  showcase?: boolean;
  /** Skip async maps — safe as Suspense fallback */
  solidOnly?: boolean;
};

export function ProceduralHumanoid({
  preset, behavior, dormant, highlight, scale = 1, showcase = false, solidOnly = false,
}: Props) {
  const root = useRef<THREE.Group>(null);
  const capeRef = useRef<THREE.Group>(null);
  const hairRef = useRef<THREE.Group>(null);

  const s = (preset.tall ? 1.04 : 1) * scale * (showcase ? 1.04 : 1)
    * (preset.build?.height ?? 1);
  const bulk = preset.build?.bulk ?? 1;
  const headScale = showcase ? 1.1 : 1;
  const op = dormant ? 0.42 : 1;

  // Zhong Kui palette pressure: red / gold / ash on accents for warrior+cape looks
  const ritual = preset.style === "warrior" || preset.style === "mage" || !!preset.cape;
  const robeWide = ritual || preset.style === "scholar";

  const skinMapsAll = useSkinMaps(preset.skin);
  const clothMapsAll = useClothMaps(preset.torso);
  const legMapsAll = useClothMaps(preset.legs);
  const metalMapsAll = useMetalMaps(preset.accent);
  const skinMaps = solidOnly ? undefined : skinMapsAll;
  const clothMaps = solidOnly ? undefined : clothMapsAll;
  const legMaps = solidOnly ? undefined : legMapsAll;
  const metalMaps = solidOnly ? undefined : metalMapsAll;

  const skinDeep = useMemo(() => shade(preset.skin, 0.82), [preset.skin]);
  const skinLight = useMemo(() => mix(preset.skin, "#fff0e4", 0.18), [preset.skin]);
  const cheek = useMemo(() => mix(preset.skin, "#b05040", 0.32), [preset.skin]);
  const lip = useMemo(() => mix(preset.skin, ritual ? "#8a2030" : "#a04840", 0.55), [preset.skin, ritual]);
  const clothDark = useMemo(() => shade(preset.torso, 0.62), [preset.torso]);
  const clothMid = useMemo(() => shade(preset.torso, 0.88), [preset.torso]);
  const legDark = useMemo(() => shade(preset.legs, 0.72), [preset.legs]);
  const gold = useMemo(() => mix(preset.accent, "#c9a227", 0.45), [preset.accent]);
  const iris = useMemo(() => mix("#1a0e08", "#3a2010", 0.4), []);

  useFrame((state) => {
    if (!root.current || dormant) return;
    const t = state.clock.elapsedTime;
    if (showcase) {
      root.current.position.y = Math.sin(t * 0.9) * 0.008;
      root.current.rotation.y = Math.sin(t * 0.22) * 0.025;
      if (capeRef.current) capeRef.current.rotation.x = 0.06 + Math.sin(t * 1.2) * 0.012;
      if (hairRef.current) hairRef.current.rotation.z = Math.sin(t * 0.9) * 0.012;
      return;
    }
    const bob = behavior === "walk" ? Math.abs(Math.sin(t * 6)) * 0.04
      : behavior === "swim" ? Math.sin(t * 3) * 0.06
      : Math.sin(t * 1.5) * 0.008;
    root.current.position.y = bob;
    if (behavior === "walk") root.current.rotation.y = Math.sin(t * 0.5) * 0.06;
    if (capeRef.current) capeRef.current.rotation.x = 0.06 + Math.sin(t * 1.8) * 0.01;
  });

  const armL: [number, number, number] = showcase ? [0.32, 0.1, 0.18] : [0.14, 0.04, 0.12];
  const armR: [number, number, number] = showcase ? [0.24, -0.06, -0.2] : [0.14, -0.02, -0.1];

  return (
    <group ref={root} scale={[s * bulk, s, s * bulk]}>
      {/* Boots — heavy ritual leather */}
      <mesh position={[-0.11, 0.045, 0.06]} castShadow>
        <boxGeometry args={[0.13, 0.09, 0.26]} />
        <LeatherPhysical color="#140f0c" opacity={op} />
      </mesh>
      <mesh position={[0.11, 0.045, 0.06]} castShadow>
        <boxGeometry args={[0.13, 0.09, 0.26]} />
        <LeatherPhysical color="#140f0c" opacity={op} />
      </mesh>

      {/* Legs */}
      <Seg pos={[-0.11, 0.22, 0]} r={0.06} len={0.22} color={preset.legs} opacity={op} clothMaps={legMaps} />
      <Seg pos={[0.11, 0.22, 0]} r={0.06} len={0.22} color={preset.legs} opacity={op} clothMaps={legMaps} />
      <Seg pos={[-0.11, 0.5, 0]} r={0.07} len={0.28} color={legDark} opacity={op} clothMaps={legMaps} />
      <Seg pos={[0.11, 0.5, 0]} r={0.07} len={0.28} color={legDark} opacity={op} clothMaps={legMaps} />

      {/* Hips / sash — thick official belt mass */}
      <mesh position={[0, 0.74, 0]} castShadow scale={[robeWide ? 1.35 : 1.15, 0.75, 0.9]}>
        <sphereGeometry args={[0.18, 16, 12]} />
        <ClothPhysical color={clothDark} opacity={op} maps={clothMaps} />
      </mesh>
      <mesh position={[0, 0.84, 0]} castShadow>
        <cylinderGeometry args={[robeWide ? 0.2 : 0.16, robeWide ? 0.22 : 0.18, 0.14, 16]} />
        <ClothPhysical color={preset.torso} opacity={op} maps={clothMaps} />
      </mesh>
      <mesh position={[0, 0.84, 0]} castShadow>
        <torusGeometry args={[robeWide ? 0.21 : 0.17, 0.028, 8, 24]} />
        <LeatherPhysical color="#1a120c" opacity={op} />
      </mesh>
      {/* ritual plaque */}
      <mesh position={[0, 0.84, robeWide ? 0.2 : 0.16]} castShadow>
        <boxGeometry args={[0.1, 0.07, 0.03]} />
        <MetalPhysical color={gold} opacity={op} maps={metalMaps}
          emissive={highlight ? gold : undefined}
          emissiveIntensity={highlight ? 0.25 : 0.05} />
      </mesh>

      {/* Thick robe torso — Zhong Kui “wall” silhouette */}
      <mesh position={[0, 1.1, 0]} castShadow receiveShadow
            scale={[robeWide ? 1.25 : 1.05, 1.3, robeWide ? 0.78 : 0.7]}>
        <sphereGeometry args={[0.22, 22, 18]} />
        <ClothPhysical
          color={preset.torso}
          opacity={op}
          maps={clothMaps}
          emissive={highlight ? preset.accent : undefined}
          emissiveIntensity={highlight ? 0.06 : 0}
          sheenColor={ritual ? "#6a4030" : "#8a7a68"}
        />
      </mesh>
      {/* layered robe panels */}
      <mesh position={[0, 1.0, 0.12]} castShadow scale={[robeWide ? 1.1 : 0.95, 1.1, 0.35]}>
        <sphereGeometry args={[0.16, 14, 12]} />
        <ClothPhysical color={clothMid} opacity={op} maps={clothMaps} />
      </mesh>
      {robeWide && (
        <>
          <mesh position={[-0.12, 0.92, 0.1]} rotation={[0.15, 0.35, 0.08]} castShadow>
            <boxGeometry args={[0.2, 0.55, 0.04]} />
            <ClothPhysical color={clothDark} opacity={op} maps={clothMaps} />
          </mesh>
          <mesh position={[0.12, 0.92, 0.1]} rotation={[0.15, -0.35, -0.08]} castShadow>
            <boxGeometry args={[0.2, 0.55, 0.04]} />
            <ClothPhysical color={clothDark} opacity={op} maps={clothMaps} />
          </mesh>
          {/* lower hem — keep above boots so feet stay visible */}
          <mesh position={[0, 0.72, 0.05]} castShadow scale={[1.25, 0.28, 0.85]}>
            <sphereGeometry args={[0.18, 14, 10]} />
            <ClothPhysical color={shade(preset.torso, 0.55)} opacity={op} maps={clothMaps} />
          </mesh>
        </>
      )}
      {/* collar — red/gold ritual rim */}
      <mesh position={[0, 1.32, 0.02]} castShadow>
        <torusGeometry args={[0.1, 0.028, 8, 18]} />
        <ClothPhysical color={ritual ? mix(preset.accent, "#8b1a1a", 0.35) : preset.accent}
          opacity={op} maps={clothMaps} />
      </mesh>

      {/* Shoulders / pauldrons */}
      {preset.pauldrons || ritual ? (
        <>
          <mesh position={[-(robeWide ? 0.28 : 0.24), 1.32, 0]} castShadow>
            <sphereGeometry args={[0.11, 14, 12]} />
            <MetalPhysical color={gold} opacity={op} maps={metalMaps} roughness={0.32} />
          </mesh>
          <mesh position={[robeWide ? 0.28 : 0.24, 1.32, 0]} castShadow>
            <sphereGeometry args={[0.11, 14, 12]} />
            <MetalPhysical color={gold} opacity={op} maps={metalMaps} roughness={0.32} />
          </mesh>
          <mesh position={[-(robeWide ? 0.3 : 0.26), 1.26, 0.05]} castShadow>
            <boxGeometry args={[0.08, 0.12, 0.06]} />
            <MetalPhysical color={shade(gold, 0.7)} opacity={op} maps={metalMaps} />
          </mesh>
          <mesh position={[robeWide ? 0.3 : 0.26, 1.26, 0.05]} castShadow>
            <boxGeometry args={[0.08, 0.12, 0.06]} />
            <MetalPhysical color={shade(gold, 0.7)} opacity={op} maps={metalMaps} />
          </mesh>
        </>
      ) : (
        <>
          <mesh position={[-0.22, 1.3, 0]} castShadow>
            <sphereGeometry args={[0.085, 12, 10]} />
            <ClothPhysical color={clothDark} opacity={op} maps={clothMaps} />
          </mesh>
          <mesh position={[0.22, 1.3, 0]} castShadow>
            <sphereGeometry args={[0.085, 12, 10]} />
            <ClothPhysical color={clothDark} opacity={op} maps={clothMaps} />
          </mesh>
        </>
      )}

      {/* Arms */}
      <group position={[-(robeWide ? 0.3 : 0.27), 1.28, 0]} rotation={armL}>
        <Seg pos={[0, -0.16, 0]} r={0.058} len={0.22} color={preset.torso} opacity={op} clothMaps={clothMaps} />
        <mesh position={[0, -0.32, 0]} castShadow>
          <sphereGeometry args={[0.052, 10, 10]} />
          <ClothPhysical color={clothDark} opacity={op} maps={clothMaps} />
        </mesh>
        <Seg pos={[0, -0.48, 0.01]} r={0.05} len={0.2} color={preset.skin} opacity={op} skin skinMaps={skinMaps} />
        <mesh position={[0, -0.64, 0.02]} castShadow>
          <boxGeometry args={[0.08, 0.1, 0.055]} />
          <SkinPhysical color={skinDeep} opacity={op} maps={skinMaps} />
        </mesh>
      </group>
      <group position={[robeWide ? 0.3 : 0.27, 1.28, 0]} rotation={armR}>
        <Seg pos={[0, -0.16, 0]} r={0.058} len={0.22} color={preset.torso} opacity={op} clothMaps={clothMaps} />
        <mesh position={[0, -0.32, 0]} castShadow>
          <sphereGeometry args={[0.052, 10, 10]} />
          <ClothPhysical color={clothDark} opacity={op} maps={clothMaps} />
        </mesh>
        <Seg pos={[0, -0.48, 0.01]} r={0.05} len={0.2} color={preset.skin} opacity={op} skin skinMaps={skinMaps} />
        <mesh position={[0, -0.64, 0.02]} castShadow>
          <boxGeometry args={[0.08, 0.1, 0.055]} />
          <SkinPhysical color={skinDeep} opacity={op} maps={skinMaps} />
        </mesh>
      </group>

      {/* Neck */}
      <mesh position={[0, 1.38, 0]} castShadow>
        <cylinderGeometry args={[0.058, 0.07, 0.12, 14]} />
        <SkinPhysical color={preset.skin} opacity={op} maps={skinMaps} />
      </mesh>

      {/* ===== FACE — candle-readable, denser features ===== */}
      <group position={[0, 1.58, 0.02]} scale={[headScale, headScale, headScale]}>
        <mesh castShadow scale={[0.96, 1.1, 0.94]}>
          <sphereGeometry args={[0.16, 28, 24]} />
          <SkinPhysical color={preset.skin} opacity={op} maps={skinMaps} />
        </mesh>
        {/* brow ridge — Zhong Kui “凶面” weight */}
        <mesh position={[0, 0.07, 0.1]} castShadow scale={[1.05, 0.35, 0.4]}>
          <sphereGeometry args={[0.1, 14, 10]} />
          <SkinPhysical color={skinDeep} opacity={op} maps={skinMaps} />
        </mesh>
        <mesh position={[0, -0.085, 0.03]} castShadow scale={[0.85, 0.55, 0.75]}>
          <sphereGeometry args={[0.12, 14, 12]} />
          <SkinPhysical color={skinDeep} opacity={op} maps={skinMaps} />
        </mesh>
        <mesh position={[0, 0.02, 0.11]} castShadow scale={[0.9, 0.95, 0.3]}>
          <sphereGeometry args={[0.12, 16, 12]} />
          <SkinPhysical color={skinLight} opacity={op} maps={skinMaps} />
        </mesh>
        {/* cheeks */}
        <mesh position={[-0.085, -0.02, 0.09]} castShadow>
          <sphereGeometry args={[0.05, 10, 10]} />
          <meshPhysicalMaterial color={cheek} transparent opacity={op * 0.35} roughness={0.6}
            sheen={0.3} sheenColor={cheek} depthWrite={false} />
        </mesh>
        <mesh position={[0.085, -0.02, 0.09]} castShadow>
          <sphereGeometry args={[0.05, 10, 10]} />
          <meshPhysicalMaterial color={cheek} transparent opacity={op * 0.35} roughness={0.6}
            sheen={0.3} sheenColor={cheek} depthWrite={false} />
        </mesh>
        {/* nose bridge */}
        <mesh position={[0, 0.0, 0.155]} castShadow rotation={[0.35, 0, 0]}>
          <boxGeometry args={[0.032, 0.07, 0.045]} />
          <SkinPhysical color={skinDeep} opacity={op} maps={skinMaps} />
        </mesh>
        <mesh position={[0, -0.03, 0.165]} castShadow>
          <sphereGeometry args={[0.022, 10, 8]} />
          <SkinPhysical color={skinDeep} opacity={op} maps={skinMaps} />
        </mesh>
        {/* ears */}
        <mesh position={[-0.15, 0, 0]} castShadow rotation={[0, 0, 0.2]} scale={[0.35, 0.58, 0.3]}>
          <sphereGeometry args={[0.08, 10, 10]} />
          <SkinPhysical color={preset.skin} opacity={op} maps={skinMaps} />
        </mesh>
        <mesh position={[0.15, 0, 0]} castShadow rotation={[0, 0, -0.2]} scale={[0.35, 0.58, 0.3]}>
          <sphereGeometry args={[0.08, 10, 10]} />
          <SkinPhysical color={preset.skin} opacity={op} maps={skinMaps} />
        </mesh>

        {/* eyes — wet cornea catch candle light */}
        {([-1, 1] as const).map((side) => (
          <group key={side} position={[side * 0.055, 0.035, 0.125]}>
            <mesh position={[0, 0, -0.01]}>
              <sphereGeometry args={[0.034, 12, 10]} />
              <meshStandardMaterial color="#120a08" transparent opacity={op * 0.45} depthWrite={false} />
            </mesh>
            <mesh scale={[1.2, 1.05, 0.65]}>
              <sphereGeometry args={[0.03, 16, 14]} />
              <meshPhysicalMaterial color="#f4efe6" roughness={0.15} clearcoat={0.6} clearcoatRoughness={0.2} />
            </mesh>
            <mesh position={[0, -0.002, 0.016]}>
              <sphereGeometry args={[0.017, 14, 12]} />
              <meshPhysicalMaterial color={iris} roughness={0.2} metalness={0.08} clearcoat={0.4} />
            </mesh>
            <mesh position={[0, -0.002, 0.026]}>
              <sphereGeometry args={[0.008, 10, 10]} />
              <meshStandardMaterial color="#050302" roughness={0.1} />
            </mesh>
            <mesh position={[0.007, 0.007, 0.032]}>
              <sphereGeometry args={[0.0045, 8, 8]} />
              <meshStandardMaterial color="#fff8f0" emissive="#ffc8a0" emissiveIntensity={0.85} />
            </mesh>
          </group>
        ))}

        {/* heavy brows */}
        <mesh position={[-0.055, 0.075, 0.12]} rotation={[0.08, 0, 0.22]} castShadow>
          <boxGeometry args={[0.07, 0.016, 0.022]} />
          <ClothPhysical color={preset.hair} opacity={op} />
        </mesh>
        <mesh position={[0.055, 0.075, 0.12]} rotation={[0.08, 0, -0.22]} castShadow>
          <boxGeometry args={[0.07, 0.016, 0.022]} />
          <ClothPhysical color={preset.hair} opacity={op} />
        </mesh>

        {/* mouth */}
        <mesh position={[0, -0.07, 0.132]} castShadow scale={[1.25, 0.35, 0.5]}>
          <sphereGeometry args={[0.032, 12, 8]} />
          <meshPhysicalMaterial color={lip} roughness={0.4} clearcoat={0.15} sheen={0.3} sheenColor={lip} />
        </mesh>

        {/* ritual beard for warrior / hooded figures */}
        {(ritual || preset.hood) && (
          <group>
            {[ -0.04, -0.02, 0, 0.02, 0.04 ].map((x, i) => (
              <mesh key={i} position={[x, -0.12 - Math.abs(x) * 0.15, 0.08]}
                    rotation={[0.4, 0, x * 1.2]} castShadow>
                <capsuleGeometry args={[0.018, 0.1 + (i % 2) * 0.04, 4, 8]} />
                <ClothPhysical color={shade(preset.hair, 0.9)} opacity={op} />
              </mesh>
            ))}
          </group>
        )}
      </group>

      {/* Hair / hood */}
      <group ref={hairRef} position={[0, 1.58, 0.02]} scale={[headScale, headScale, headScale]}>
        {preset.hood ? (
          <>
            <mesh position={[0, 0.08, -0.02]} castShadow>
              <sphereGeometry args={[0.19, 18, 14, 0, Math.PI * 2, 0, Math.PI * 0.62]} />
              <ClothPhysical color={preset.hair} opacity={op} maps={clothMaps} />
            </mesh>
            <mesh position={[0, -0.1, -0.14]} castShadow>
              <coneGeometry args={[0.15, 0.32, 12]} />
              <ClothPhysical color={shade(preset.hair, 0.85)} opacity={op} maps={clothMaps} />
            </mesh>
          </>
        ) : (
          <>
            <mesh position={[0, 0.12, -0.02]} castShadow>
              <sphereGeometry args={[0.175, 20, 16, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
              <ClothPhysical color={preset.hair} opacity={op} />
            </mesh>
            {[-0.06, 0, 0.06].map((x, i) => (
              <mesh key={i} position={[x, 0.08, 0.13]} rotation={[0.45, x * 0.5, x * 0.3]} castShadow>
                <capsuleGeometry args={[0.032, 0.08, 4, 8]} />
                <ClothPhysical color={preset.hair} opacity={op} />
              </mesh>
            ))}
            <mesh position={[-0.14, -0.02, 0.02]} castShadow rotation={[0.1, 0, 0.3]}>
              <capsuleGeometry args={[0.038, 0.16, 4, 8]} />
              <ClothPhysical color={preset.hair} opacity={op} />
            </mesh>
            <mesh position={[0.14, -0.02, 0.02]} castShadow rotation={[0.1, 0, -0.3]}>
              <capsuleGeometry args={[0.038, 0.16, 4, 8]} />
              <ClothPhysical color={preset.hair} opacity={op} />
            </mesh>
            <mesh position={[0, -0.02, -0.12]} castShadow scale={[1.15, 1, 0.75]}>
              <sphereGeometry args={[0.13, 14, 12]} />
              <ClothPhysical color={shade(preset.hair, 0.88)} opacity={op} />
            </mesh>
          </>
        )}
      </group>

      {/* Cape / official cloak */}
      {(preset.cape || ritual) && !showcase && (
        <group ref={capeRef} position={[0, 1.15, -0.16]}>
          <mesh position={[0, -0.08, 0]} rotation={[0.22, 0, 0]} castShadow>
            <boxGeometry args={[robeWide ? 0.55 : 0.42, 0.95, 0.045]} />
            <ClothPhysical color={mix(preset.accent, "#4a1010", 0.25)} opacity={op} maps={clothMaps} />
          </mesh>
        </group>
      )}
      {preset.cape && showcase && (
        <group ref={capeRef} position={[0, 1.12, -0.18]}>
          <mesh position={[0, -0.1, 0]} rotation={[0.28, 0, 0]} castShadow>
            <boxGeometry args={[0.48, 0.7, 0.04]} />
            <ClothPhysical color={mix(preset.accent, "#4a1010", 0.2)} opacity={op} maps={clothMaps} />
          </mesh>
        </group>
      )}

      {preset.style === "mage" && (
        <mesh position={[0, 1.12, 0.16]} castShadow>
          <octahedronGeometry args={[0.045, 0]} />
          <MetalPhysical color={gold} opacity={op} maps={metalMaps} emissive={gold} emissiveIntensity={0.45} />
        </mesh>
      )}

      <WeaponMesh kind={preset.weapon} accent={gold} opacity={op} metalMaps={metalMaps} />
    </group>
  );
}

/** Default: Hero pipeline → cinematic R3F; ancient street life → volumetric procedural. */
export default function HumanoidFigure(props: Props) {
  if (isHeroPipelineRole(props.preset)) {
    return <HeroCharacter {...props} />;
  }
  // Ancient / street NPCs must read as distinct 3D people (height, bulk, clothes) —
  // shared hy3d cutouts collapse everyone into the same paper silhouette.
  if (props.preset.genre === "ancient" || props.preset.id.startsWith("npc_")) {
    return <ProceduralHumanoid {...props} />;
  }
  return (
    <Suspense fallback={<ProceduralHumanoid {...props} solidOnly />}>
      <GltfHumanoid {...props} />
    </Suspense>
  );
}
