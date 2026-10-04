"use client";

/**
 * Hero tier — 散修剑客 (wuxia_wanderer)
 * R3F cinematic mesh + PBR. Iteration target: replace with compiled GLB when quality gate passes.
 * v0.1 — wuxia lean silhouette, readable face, layered 劲装/披风, NOT box GLB.
 */
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { FigurePreset } from "@/lib/characterFigures";
import {
  ClothPhysical, LeatherPhysical, MetalPhysical, SkinPhysical,
  useClothMaps, useMetalMaps, useSkinMaps,
} from "@/lib/figureMaterials";

type Props = {
  preset: FigurePreset;
  behavior?: string;
  dormant?: boolean;
  highlight?: boolean;
  scale?: number;
  showcase?: boolean;
};

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

function CapsuleSeg({
  pos, rot, r, len, color, opacity, skin, skinMaps, clothMaps,
}: {
  pos: [number, number, number]; rot?: [number, number, number];
  r: number; len: number; color: string; opacity: number; skin?: boolean;
  skinMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
  clothMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
}) {
  return (
    <mesh position={pos} rotation={rot} castShadow receiveShadow>
      <capsuleGeometry args={[r, Math.max(0.02, len), 8, 16]} />
      {skin
        ? <SkinPhysical color={color} opacity={opacity} maps={skinMaps} />
        : <ClothPhysical color={color} opacity={opacity} maps={clothMaps} />}
    </mesh>
  );
}

/** Layered back cape — multi-panel sway reads as cloth, not a flat box */
function WandererCape({
  accent, torso, opacity, clothMaps, capeRef,
}: {
  accent: string; torso: string; opacity: number;
  clothMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
  capeRef: React.RefObject<THREE.Group>;
}) {
  const inner = mix(torso, "#1a2030", 0.35);
  const outer = mix(accent, torso, 0.55);
  return (
    <group ref={capeRef} position={[0, 1.08, -0.14]}>
      {[
        { x: 0, ry: 0.18, w: 0.52, h: 1.05, z: 0, col: outer },
        { x: -0.08, ry: 0.28, w: 0.38, h: 0.92, z: -0.02, col: inner },
        { x: 0.08, ry: 0.12, w: 0.36, h: 0.88, z: -0.03, col: inner },
      ].map((p, i) => (
        <mesh key={i} position={[p.x, -0.12, p.z]} rotation={[0.24 + i * 0.04, p.ry, 0]} castShadow receiveShadow>
          <planeGeometry args={[p.w, p.h, 1, 8]} />
          <meshPhysicalMaterial color={p.col} transparent opacity={opacity}
            roughness={0.82} metalness={0.04} side={THREE.DoubleSide}
            map={clothMaps?.albedo} roughnessMap={clothMaps?.roughness} />
        </mesh>
      ))}
      <mesh position={[0, 0.08, 0.04]} castShadow>
        <boxGeometry args={[0.14, 0.06, 0.04]} />
        <MetalPhysical color={accent} opacity={opacity} roughness={0.25} />
      </mesh>
    </group>
  );
}

function BackSword({ accent, opacity, metalMaps }: {
  accent: string; opacity: number;
  metalMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
}) {
  return (
    <group position={[-0.12, 1.05, -0.22]} rotation={[0.15, 0.35, -0.12]}>
      <mesh castShadow position={[0, 0, 0]}>
        <boxGeometry args={[0.06, 0.72, 0.1]} />
        <LeatherPhysical color="#2a1810" opacity={opacity} />
      </mesh>
      <mesh castShadow position={[0, 0.42, 0.02]}>
        <boxGeometry args={[0.014, 0.82, 0.055]} />
        <MetalPhysical color="#dce4ee" opacity={opacity} maps={metalMaps} roughness={0.12} />
      </mesh>
      <mesh castShadow position={[0, -0.02, 0]}>
        <boxGeometry args={[0.18, 0.028, 0.05]} />
        <MetalPhysical color={accent} opacity={opacity} maps={metalMaps} />
      </mesh>
      <mesh castShadow position={[0, -0.18, 0]}>
        <cylinderGeometry args={[0.022, 0.028, 0.22, 12]} />
        <LeatherPhysical color="#1a1008" opacity={opacity} />
      </mesh>
    </group>
  );
}

function HeroFace({
  preset, opacity, skinMaps, clothMaps, headScale, showcase,
}: {
  preset: FigurePreset; opacity: number; headScale: number; showcase: boolean;
  skinMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
  clothMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
}) {
  const skinDeep = useMemo(() => shade(preset.skin, 0.82), [preset.skin]);
  const skinLight = useMemo(() => mix(preset.skin, "#fff0e4", 0.2), [preset.skin]);
  const cheek = useMemo(() => mix(preset.skin, "#c06050", 0.28), [preset.skin]);
  const lip = useMemo(() => mix(preset.skin, "#a04840", 0.5), [preset.skin]);
  const iris = useMemo(() => mix("#2a1808", "#4a6030", 0.35), []);

  return (
    <group position={[0, 1.58, 0.025]} scale={[headScale, headScale, headScale]}>
      {/* skull */}
      <mesh castShadow scale={[0.94, 1.08, 0.92]}>
        <sphereGeometry args={[0.155, 32, 28]} />
        <SkinPhysical color={preset.skin} opacity={opacity} maps={skinMaps} />
      </mesh>
      {/* jaw — lean wanderer, not demon */}
      <mesh position={[0, -0.09, 0.02]} castShadow scale={[0.88, 0.62, 0.78]}>
        <sphereGeometry args={[0.12, 20, 16]} />
        <SkinPhysical color={skinDeep} opacity={opacity} maps={skinMaps} />
      </mesh>
      {/* cheekbones */}
      <mesh position={[-0.08, 0.01, 0.1]} castShadow>
        <sphereGeometry args={[0.045, 12, 10]} />
        <meshPhysicalMaterial color={cheek} transparent opacity={opacity * 0.32}
          roughness={0.55} sheen={0.35} sheenColor={cheek} depthWrite={false} />
      </mesh>
      <mesh position={[0.08, 0.01, 0.1]} castShadow>
        <sphereGeometry args={[0.045, 12, 10]} />
        <meshPhysicalMaterial color={cheek} transparent opacity={opacity * 0.32}
          roughness={0.55} sheen={0.35} sheenColor={cheek} depthWrite={false} />
      </mesh>
      {/* nose */}
      <mesh position={[0, -0.01, 0.148]} castShadow rotation={[0.32, 0, 0]}>
        <capsuleGeometry args={[0.012, 0.055, 6, 10]} />
        <SkinPhysical color={skinDeep} opacity={opacity} maps={skinMaps} />
      </mesh>
      {/* ears */}
      {([-1, 1] as const).map((s) => (
        <mesh key={s} position={[s * 0.145, -0.01, 0]} rotation={[0, 0, s * 0.25]}
              castShadow scale={[0.32, 0.55, 0.28]}>
          <sphereGeometry args={[0.08, 12, 10]} />
          <SkinPhysical color={preset.skin} opacity={opacity} maps={skinMaps} />
        </mesh>
      ))}
      {/* eyes */}
      {([-1, 1] as const).map((side) => (
        <group key={side} position={[side * 0.052, 0.032, 0.12]}>
          <mesh position={[0, 0, -0.008]}>
            <sphereGeometry args={[0.032, 14, 12]} />
            <meshStandardMaterial color="#0a0806" transparent opacity={opacity * 0.5} depthWrite={false} />
          </mesh>
          <mesh scale={[1.15, 1.02, 0.62]}>
            <sphereGeometry args={[0.028, 18, 16]} />
            <meshPhysicalMaterial color="#f2ece4" roughness={0.12} clearcoat={0.65} clearcoatRoughness={0.18} />
          </mesh>
          <mesh position={[0, -0.002, 0.014]}>
            <sphereGeometry args={[0.015, 16, 14]} />
            <meshPhysicalMaterial color={iris} roughness={0.18} metalness={0.06} clearcoat={0.45} />
          </mesh>
          <mesh position={[0, -0.002, 0.022]}>
            <sphereGeometry args={[0.007, 10, 10]} />
            <meshStandardMaterial color="#040302" roughness={0.08} />
          </mesh>
          <mesh position={[side * 0.006, 0.006, 0.028]}>
            <sphereGeometry args={[0.004, 8, 8]} />
            <meshStandardMaterial color="#fff6ec" emissive="#ffd0a0" emissiveIntensity={showcase ? 1.0 : 0.7} />
          </mesh>
        </group>
      ))}
      {/* brows — sharp martial */}
      <mesh position={[-0.052, 0.068, 0.118]} rotation={[0.06, 0, 0.28]} castShadow>
        <capsuleGeometry args={[0.008, 0.055, 4, 8]} />
        <ClothPhysical color={preset.hair} opacity={opacity} maps={clothMaps} />
      </mesh>
      <mesh position={[0.052, 0.068, 0.118]} rotation={[0.06, 0, -0.28]} castShadow>
        <capsuleGeometry args={[0.008, 0.055, 4, 8]} />
        <ClothPhysical color={preset.hair} opacity={opacity} maps={clothMaps} />
      </mesh>
      {/* lips */}
      <mesh position={[0, -0.065, 0.128]} castShadow scale={[1.2, 0.32, 0.48]}>
        <sphereGeometry args={[0.03, 14, 10]} />
        <meshPhysicalMaterial color={lip} roughness={0.38} clearcoat={0.12} sheen={0.25} sheenColor={lip} />
      </mesh>
    </group>
  );
}

function TopknotHair({
  preset, opacity, clothMaps, hairRef,
}: {
  preset: FigurePreset; opacity: number;
  clothMaps?: { albedo: THREE.Texture; roughness: THREE.Texture };
  hairRef: React.RefObject<THREE.Group>;
}) {
  const ribbon = preset.accent;
  return (
    <group ref={hairRef} position={[0, 1.6, 0.02]}>
      <mesh position={[0, 0.1, -0.03]} castShadow>
        <sphereGeometry args={[0.17, 22, 18, 0, Math.PI * 2, 0, Math.PI * 0.52]} />
        <ClothPhysical color={preset.hair} opacity={opacity} />
      </mesh>
      {/* topknot bun */}
      <mesh position={[0, 0.18, -0.06]} castShadow>
        <sphereGeometry args={[0.065, 16, 14]} />
        <ClothPhysical color={shade(preset.hair, 0.92)} opacity={opacity} />
      </mesh>
      {/* ribbon */}
      <mesh position={[0, 0.14, -0.02]} rotation={[0.4, 0, 0]} castShadow>
        <boxGeometry args={[0.04, 0.22, 0.012]} />
        <ClothPhysical color={ribbon} opacity={opacity} maps={clothMaps} />
      </mesh>
      {/* side locks */}
      {([-1, 1] as const).map((s) => (
        <mesh key={s} position={[s * 0.13, -0.02, 0.04]} rotation={[0.15, s * 0.2, s * 0.35]} castShadow>
          <capsuleGeometry args={[0.028, 0.18, 6, 10]} />
          <ClothPhysical color={preset.hair} opacity={opacity} />
        </mesh>
      ))}
    </group>
  );
}

export default function HeroWuxiaWanderer({
  preset, behavior, dormant, highlight, scale = 1, showcase = false,
}: Props) {
  const root = useRef<THREE.Group>(null);
  const capeRef = useRef<THREE.Group>(null);
  const hairRef = useRef<THREE.Group>(null);

  const s = scale * (preset.build?.height ?? 1) * (showcase ? 1.05 : 1);
  const bulk = (preset.build?.bulk ?? 1) * 0.96;
  const op = dormant ? 0.42 : 1;
  const headScale = showcase ? 1.12 : 1.06;

  const skinMaps = useSkinMaps(preset.skin);
  const clothMaps = useClothMaps(preset.torso);
  const legMaps = useClothMaps(preset.legs);
  const metalMaps = useMetalMaps(preset.accent);

  const torsoDark = useMemo(() => shade(preset.torso, 0.65), [preset.torso]);
  const torsoLight = useMemo(() => mix(preset.torso, preset.accent, 0.15), [preset.torso, preset.accent]);
  const legBind = useMemo(() => shade(preset.legs, 0.78), [preset.legs]);

  useFrame((state) => {
    if (!root.current || dormant) return;
    const t = state.clock.elapsedTime;
    const bob = behavior === "walk"
      ? Math.abs(Math.sin(t * 6.2)) * 0.035
      : showcase
        ? Math.sin(t * 0.85) * 0.01
        : Math.sin(t * 1.4) * 0.006;
    root.current.position.y = bob;
    if (behavior === "walk") root.current.rotation.y = Math.sin(t * 0.55) * 0.05;
    if (capeRef.current) {
      capeRef.current.rotation.x = 0.08 + Math.sin(t * 1.6) * 0.018;
      capeRef.current.rotation.z = Math.sin(t * 1.1) * 0.012;
    }
    if (hairRef.current) hairRef.current.rotation.z = Math.sin(t * 0.95) * 0.01;
  });

  return (
    <group ref={root} scale={[s * bulk, s, s * bulk]}>
      {/* 布鞋 */}
      {([-0.1, 0.1] as const).map((x) => (
        <mesh key={x} position={[x, 0.04, 0.05]} castShadow>
          <boxGeometry args={[0.11, 0.06, 0.24]} />
          <ClothPhysical color="#2a2420" opacity={op} />
        </mesh>
      ))}

      {/* 绑腿 + 劲装裤 */}
      {([-0.1, 0.1] as const).map((x) => (
        <group key={x}>
          <CapsuleSeg pos={[x, 0.24, 0]} r={0.055} len={0.2} color={preset.legs} opacity={op} clothMaps={legMaps} />
          <CapsuleSeg pos={[x, 0.48, 0]} r={0.062} len={0.26} color={legBind} opacity={op} clothMaps={legMaps} />
          {[0.32, 0.42, 0.52].map((y, i) => (
            <mesh key={i} position={[x, y, 0.02]} castShadow>
              <torusGeometry args={[0.058, 0.012, 6, 14]} />
              <ClothPhysical color={torsoDark} opacity={op} maps={clothMaps} />
            </mesh>
          ))}
        </group>
      ))}

      {/* 腰带 */}
      <mesh position={[0, 0.76, 0]} castShadow scale={[1.05, 0.7, 0.85]}>
        <sphereGeometry args={[0.17, 18, 14]} />
        <ClothPhysical color={torsoDark} opacity={op} maps={clothMaps} />
      </mesh>
      <mesh position={[0, 0.8, 0.1]} castShadow>
        <boxGeometry args={[0.08, 0.06, 0.03]} />
        <MetalPhysical color={preset.accent} opacity={op} maps={metalMaps}
          emissive={highlight ? preset.accent : undefined} emissiveIntensity={highlight ? 0.2 : 0.04} />
      </mesh>

      {/* 交领劲装 — layered torso */}
      <mesh position={[0, 1.06, 0.02]} castShadow scale={[0.92, 1.15, 0.68]}>
        <sphereGeometry args={[0.21, 24, 20]} />
        <ClothPhysical color={preset.torso} opacity={op} maps={clothMaps}
          sheenColor="#4a5060" emissive={highlight ? preset.accent : undefined}
          emissiveIntensity={highlight ? 0.05 : 0} />
      </mesh>
      {/* cross collar V */}
      <mesh position={[-0.04, 1.18, 0.12]} rotation={[0.1, 0.35, 0.15]} castShadow>
        <planeGeometry args={[0.14, 0.38]} />
        <meshPhysicalMaterial color={torsoLight} transparent opacity={op}
          roughness={0.75} metalness={0.05} side={THREE.DoubleSide}
          map={clothMaps?.albedo} roughnessMap={clothMaps?.roughness} />
      </mesh>
      <mesh position={[0.04, 1.18, 0.12]} rotation={[0.1, -0.35, -0.15]} castShadow>
        <planeGeometry args={[0.14, 0.38]} />
        <meshPhysicalMaterial color={torsoLight} transparent opacity={op}
          roughness={0.75} metalness={0.05} side={THREE.DoubleSide}
          map={clothMaps?.albedo} roughnessMap={clothMaps?.roughness} />
      </mesh>
      {/* wide sleeves taper */}
      {([-1, 1] as const).map((side) => (
        <group key={side} position={[side * 0.28, 1.22, 0.02]} rotation={[0.08, side * 0.12, side * 0.08]}>
          <CapsuleSeg pos={[0, -0.14, 0]} r={0.065} len={0.24} color={preset.torso} opacity={op} clothMaps={clothMaps} />
          <CapsuleSeg pos={[0, -0.36, 0.01]} r={0.048} len={0.2} color={torsoDark} opacity={op} clothMaps={clothMaps} />
          <CapsuleSeg pos={[0, -0.52, 0.02]} r={0.042} len={0.16} color={preset.skin} opacity={op} skin skinMaps={skinMaps} />
          <mesh position={[0, -0.64, 0.03]} castShadow>
            <boxGeometry args={[0.075, 0.09, 0.05]} />
            <SkinPhysical color={shade(preset.skin, 0.85)} opacity={op} maps={skinMaps} />
          </mesh>
        </group>
      ))}

      {/* neck */}
      <mesh position={[0, 1.4, 0]} castShadow>
        <cylinderGeometry args={[0.055, 0.065, 0.11, 16]} />
        <SkinPhysical color={preset.skin} opacity={op} maps={skinMaps} />
      </mesh>

      <HeroFace preset={preset} opacity={op} skinMaps={skinMaps} clothMaps={clothMaps}
        headScale={headScale} showcase={!!showcase} />
      <TopknotHair preset={preset} opacity={op} clothMaps={clothMaps} hairRef={hairRef} />
      <WandererCape accent={preset.accent} torso={preset.torso} opacity={op}
        clothMaps={clothMaps} capeRef={capeRef} />
      <BackSword accent={preset.accent} opacity={op} metalMaps={metalMaps} />
    </group>
  );
}
