"use client";

/**
 * Distinct hero landmarks — 二层酒楼 / 四合院宫殿 / 道观院落.
 * Local +Z is the street front (matches map builder road yaw).
 */
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { useMemo } from "react";

export type LandmarkArch = {
  name: string;
  sign?: string;
  modelKey?: string;
};

function HipRoof({
  w, d, h = 0.85, color = "#7f1d1d", accent = "#44403c", ornate = false,
}: {
  w: number; d: number; h?: number; color?: string; accent?: string; ornate?: boolean;
}) {
  const geom = useMemo(() => {
    const hw = w / 2;
    const hd = d / 2;
    const rw = w * 0.12;
    const A = [-hw, 0, hd];
    const B = [hw, 0, hd];
    const C = [hw, 0, -hd];
    const D = [-hw, 0, -hd];
    const R0 = [-rw, h, 0];
    const R1 = [rw, h, 0];
    const tris: number[] = [];
    const tri = (p: number[], q: number[], r: number[]) => tris.push(...p, ...q, ...r);
    tri(A, B, R1); tri(A, R1, R0);
    tri(B, C, R1);
    tri(C, D, R0); tri(C, R0, R1);
    tri(D, A, R0);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(tris, 3));
    g.computeVertexNormals();
    return g;
  }, [w, d, h]);

  return (
    <group>
      <mesh geometry={geom} castShadow receiveShadow>
        <meshStandardMaterial color={color} roughness={0.7} metalness={0.08} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, 0.04, 0]} castShadow>
        <boxGeometry args={[w * 1.08, 0.07, d * 1.08]} />
        <meshStandardMaterial color={accent} roughness={0.75} />
      </mesh>
      {ornate && (
        <>
          <mesh position={[0, h + 0.28, 0]} castShadow>
            <sphereGeometry args={[0.13, 12, 10]} />
            <meshStandardMaterial color="#eab308" metalness={0.65} roughness={0.28} />
          </mesh>
          {([-1, 1] as const).map((sx) => (
            <mesh key={sx} position={[sx * w * 0.42, h * 0.35, 0]} castShadow>
              <coneGeometry args={[0.1, 0.32, 6]} />
              <meshStandardMaterial color="#ca8a04" metalness={0.5} roughness={0.35} />
            </mesh>
          ))}
        </>
      )}
    </group>
  );
}

function EnterBtn({ name, y, onEnter }: { name: string; y: number; onEnter?: (n: string) => void }) {
  return (
    <Html position={[0, y, 0]} center distanceFactor={20}>
      <button type="button" onClick={() => onEnter?.(name)}
        className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/85 text-amber-50
                   border border-amber-500/50 hover:bg-amber-700/90">
        进入 · {name}
      </button>
    </Html>
  );
}

/** Stone path from door (+Z) out to the street so entry reads clearly. */
function StreetApproach({ bw, bd, length = 4.2 }: { bw: number; bd: number; length?: number }) {
  const steps = 5;
  return (
    <group>
      {/* long walkway toward street */}
      <mesh position={[0, 0.04, bd * 0.55 + length * 0.45]} receiveShadow>
        <boxGeometry args={[bw * 0.38, 0.08, length]} />
        <meshStandardMaterial color="#a8a29e" roughness={0.94} />
      </mesh>
      <mesh position={[0, 0.06, bd * 0.55 + length * 0.45]} receiveShadow>
        <boxGeometry args={[bw * 0.22, 0.06, length * 0.95]} />
        <meshStandardMaterial color="#d6d3d1" roughness={0.96} />
      </mesh>
      {Array.from({ length: steps }).map((_, i) => (
        <mesh
          key={i}
          position={[0, 0.05 + i * 0.07, bd * 0.52 + 0.12 + i * 0.14]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[bw * 0.32 - i * 0.02, 0.08, 0.2]} />
          <meshStandardMaterial color="#78716c" roughness={0.92} />
        </mesh>
      ))}
    </group>
  );
}

function Plaque({ label, y, z, wood = "#7c2d12", accent = "#ca8a04" }: {
  label: string; y: number; z: number; wood?: string; accent?: string;
}) {
  return (
    <group position={[0, y, z]}>
      <mesh castShadow>
        <boxGeometry args={[Math.min(2.4, label.length * 0.35 + 0.8), 0.42, 0.08]} />
        <meshStandardMaterial color={wood} roughness={0.5} metalness={0.12} />
      </mesh>
      <mesh position={[0, 0, 0.05]}>
        <boxGeometry args={[Math.min(2.1, label.length * 0.32 + 0.6), 0.3, 0.03]} />
        <meshStandardMaterial color={accent} metalness={0.35} roughness={0.4} />
      </mesh>
      <Html position={[0, 0, 0.12]} center distanceFactor={14}>
        <div className="font-serif text-[13px] tracking-[0.3em] text-amber-50 pointer-events-none
                        drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)]">
          {label}
        </div>
      </Html>
    </group>
  );
}

/** 醉仙楼 — clear two-storey street tavern with balcony. */
function TavernTwoStorey({
  b, night, onEnter, bw, bd,
}: {
  b: LandmarkArch; night?: boolean; onEnter?: (n: string) => void; bw: number; bd: number;
}) {
  const label = b.sign || b.name;
  const gH = 2.35;
  const uH = 2.1;
  const wood = "#6b3f2a";
  const wall = "#f3e7d3";
  const roof = "#991b1b";
  const front = bd * 0.48;

  return (
    <group>
      {/* plinth + steps / path to street (+Z) */}
      <mesh position={[0, 0.08, 0]} receiveShadow>
        <boxGeometry args={[bw * 1.08, 0.16, bd * 1.05]} />
        <meshStandardMaterial color="#a8a29e" roughness={0.92} />
      </mesh>
      <StreetApproach bw={bw} bd={bd} length={5.2} />

      {/* —— ground floor shop —— */}
      <mesh position={[0, gH / 2 + 0.16, 0]} castShadow receiveShadow>
        <boxGeometry args={[bw * 0.92, gH, bd * 0.88]} />
        <meshStandardMaterial color={wall} roughness={0.86} />
      </mesh>
      {([[-1, -1], [-1, 1], [1, -1], [1, 1]] as const).map(([sx, sz], i) => (
        <mesh key={i} position={[sx * bw * 0.42, gH / 2 + 0.16, sz * bd * 0.4]} castShadow>
          <cylinderGeometry args={[0.1, 0.12, gH, 10]} />
          <meshStandardMaterial color={wood} roughness={0.65} />
        </mesh>
      ))}
      {/* open shop front */}
      <mesh position={[0, 1.05, front - 0.02]}>
        <boxGeometry args={[bw * 0.55, 1.7, 0.06]} />
        <meshStandardMaterial color="#1c1917" roughness={1} />
      </mesh>
      <mesh position={[0, 0.55, front * 0.35]} castShadow>
        <boxGeometry args={[bw * 0.7, 0.7, 0.45]} />
        <meshStandardMaterial color="#78350f" roughness={0.8} />
      </mesh>
      {[-0.5, 0, 0.5].map((x, i) => (
        <mesh key={i} position={[x, 1.05, front * 0.35]} castShadow>
          <cylinderGeometry args={[0.12, 0.14, 0.4, 10]} />
          <meshStandardMaterial color="#92400e" roughness={0.7} />
        </mesh>
      ))}

      {/* floor plate between storeys */}
      <mesh position={[0, gH + 0.2, 0]} castShadow>
        <boxGeometry args={[bw * 1.0, 0.16, bd * 0.95]} />
        <meshStandardMaterial color={wood} roughness={0.6} />
      </mesh>

      {/* —— upper floor —— */}
      <mesh position={[0, gH + 0.28 + uH / 2, -bd * 0.04]} castShadow receiveShadow>
        <boxGeometry args={[bw * 0.82, uH, bd * 0.72]} />
        <meshStandardMaterial color="#efe2cc" roughness={0.85} />
      </mesh>
      {/* balcony deck + rail */}
      <mesh position={[0, gH + 0.32, front * 0.55]} castShadow>
        <boxGeometry args={[bw * 0.75, 0.08, 0.55]} />
        <meshStandardMaterial color={wood} roughness={0.7} />
      </mesh>
      {[-0.35, 0, 0.35].map((x, i) => (
        <mesh key={i} position={[x * bw, gH + 0.7, front * 0.72]} castShadow>
          <boxGeometry args={[0.05, 0.7, 0.05]} />
          <meshStandardMaterial color={wood} />
        </mesh>
      ))}
      <mesh position={[0, gH + 1.05, front * 0.72]} castShadow>
        <boxGeometry args={[bw * 0.72, 0.05, 0.05]} />
        <meshStandardMaterial color={wood} />
      </mesh>
      {/* upper windows */}
      {[-0.22, 0.22].map((x, i) => (
        <mesh key={i} position={[x * bw, gH + 0.28 + uH * 0.55, front * 0.28]}>
          <boxGeometry args={[0.55, 0.7, 0.05]} />
          <meshStandardMaterial
            color="#fde68a"
            emissive="#fbbf24"
            emissiveIntensity={night ? 0.55 : 0.2}
          />
        </mesh>
      ))}

      <group position={[0, gH + 0.28 + uH + 0.15, -bd * 0.04]}>
        <HipRoof w={bw * 1.05} d={bd * 0.95} h={0.85} color={roof} accent={wood} ornate />
      </group>
      {/* ground eave */}
      <group position={[0, gH + 0.35, 0]}>
        <HipRoof w={bw * 1.15} d={bd * 1.05} h={0.45} color={roof} accent={wood} />
      </group>

      {/* banners */}
      {([-1, 1] as const).map((sx) => (
        <group key={sx} position={[sx * bw * 0.55, 1.9, front]}>
          <mesh>
            <cylinderGeometry args={[0.035, 0.04, 2.4, 8]} />
            <meshStandardMaterial color="#3f2a1f" />
          </mesh>
          <mesh position={[sx * 0.25, 0.15, 0]} castShadow>
            <boxGeometry args={[0.4, 1.4, 0.05]} />
            <meshStandardMaterial color="#b91c1c" roughness={0.7} />
          </mesh>
        </group>
      ))}
      {[-0.4, 0, 0.4].map((x, i) => (
        <mesh key={i} position={[x, gH + 0.1, front * 0.85]} castShadow>
          <sphereGeometry args={[0.14, 12, 12]} />
          <meshStandardMaterial color="#fbbf24" emissive="#f59e0b" emissiveIntensity={night ? 1 : 0.4} />
        </mesh>
      ))}

      <Plaque label={label} y={gH * 0.75} z={front + 0.08} />
      <pointLight position={[0, gH + 1, front]} intensity={night ? 1 : 0.4} distance={9} color="#fbbf24" />
      <EnterBtn name={b.name} y={gH + uH + 2.2} onEnter={onEnter} />
    </group>
  );
}

/** 紫宸殿 — 四合院: gatehouse, courtyard, side wings, main hall. */
function PalaceSiheyuan({
  b, night, onEnter, bw, bd,
}: {
  b: LandmarkArch; night?: boolean; onEnter?: (n: string) => void; bw: number; bd: number;
}) {
  const label = b.sign || b.name;
  const wood = "#9f1239";
  const wall = "#fff7ed";
  const roof = "#b45309";
  const stone = "#e7e5e4";
  const wingH = 2.4;
  const hallH = 3.4;
  const gateH = 2.8;
  const courtD = bd * 0.38;
  const wallT = 0.18;

  return (
    <group>
      {/* podium */}
      <mesh position={[0, 0.12, 0]} receiveShadow>
        <boxGeometry args={[bw * 1.2, 0.24, bd * 1.15]} />
        <meshStandardMaterial color={stone} roughness={0.92} />
      </mesh>
      <mesh position={[0, 0.32, 0]} receiveShadow castShadow>
        <boxGeometry args={[bw * 1.08, 0.28, bd * 1.05]} />
        <meshStandardMaterial color={stone} roughness={0.9} />
      </mesh>
      <StreetApproach bw={bw} bd={bd} length={5.8} />

      {/* courtyard floor */}
      <mesh position={[0, 0.48, 0]} receiveShadow>
        <boxGeometry args={[bw * 0.72, 0.06, courtD]} />
        <meshStandardMaterial color="#d6d3d1" roughness={0.95} />
      </mesh>

      {/* enclosing walls (N/S/E/W) with gate gap on +Z */}
      <mesh position={[0, 0.5 + wingH / 2, -bd * 0.48]} castShadow receiveShadow>
        <boxGeometry args={[bw * 0.95, wingH, wallT]} />
        <meshStandardMaterial color={wall} roughness={0.88} />
      </mesh>
      <mesh position={[-bw * 0.48, 0.5 + wingH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[wallT, wingH, bd * 0.95]} />
        <meshStandardMaterial color="#fecaca" roughness={0.88} />
      </mesh>
      <mesh position={[bw * 0.48, 0.5 + wingH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[wallT, wingH, bd * 0.95]} />
        <meshStandardMaterial color="#fecaca" roughness={0.88} />
      </mesh>
      {/* front wall wings around gate */}
      <mesh position={[-bw * 0.32, 0.5 + wingH / 2, bd * 0.48]} castShadow receiveShadow>
        <boxGeometry args={[bw * 0.28, wingH, wallT]} />
        <meshStandardMaterial color={wall} roughness={0.88} />
      </mesh>
      <mesh position={[bw * 0.32, 0.5 + wingH / 2, bd * 0.48]} castShadow receiveShadow>
        <boxGeometry args={[bw * 0.28, wingH, wallT]} />
        <meshStandardMaterial color={wall} roughness={0.88} />
      </mesh>

      {/* gatehouse */}
      <group position={[0, 0.5, bd * 0.48]}>
        {([-1, 1] as const).map((sx) => (
          <mesh key={sx} position={[sx * 0.85, gateH / 2, 0]} castShadow>
            <cylinderGeometry args={[0.14, 0.16, gateH, 12]} />
            <meshStandardMaterial color={wood} roughness={0.55} metalness={0.1} />
          </mesh>
        ))}
        <mesh position={[0, gateH + 0.1, 0]} castShadow>
          <boxGeometry args={[2.4, 0.2, 0.9]} />
          <meshStandardMaterial color={wood} roughness={0.55} />
        </mesh>
        <group position={[0, gateH + 0.35, 0]}>
          <HipRoof w={3.2} d={1.6} h={0.7} color={roof} accent={wood} ornate />
        </group>
        {/* open gate void */}
        <mesh position={[0, 1.1, 0.02]}>
          <boxGeometry args={[1.5, 2.2, 0.2]} />
          <meshStandardMaterial color="#1c1917" roughness={1} />
        </mesh>
      </group>

      {/* east / west side halls */}
      {([-1, 1] as const).map((sx) => (
        <group key={sx} position={[sx * bw * 0.32, 0.5, 0]}>
          <mesh castShadow receiveShadow>
            <boxGeometry args={[bw * 0.22, wingH * 0.9, bd * 0.55]} />
            <meshStandardMaterial color={wall} roughness={0.86} />
          </mesh>
          <group position={[0, wingH * 0.95, 0]}>
            <HipRoof w={bw * 0.32} d={bd * 0.65} h={0.55} color={roof} accent={wood} />
          </group>
          {[-0.15, 0.15].map((z, i) => (
            <mesh key={i} position={[sx * 0.12, wingH * 0.45, z * bd]}>
              <boxGeometry args={[0.05, 0.7, 0.5]} />
              <meshStandardMaterial color="#fde68a" emissive="#fbbf24" emissiveIntensity={night ? 0.4 : 0.12} />
            </mesh>
          ))}
        </group>
      ))}

      {/* main hall (北正殿) raised */}
      <group position={[0, 0.75, -bd * 0.28]}>
        <mesh castShadow receiveShadow>
          <boxGeometry args={[bw * 0.55, hallH, bd * 0.32]} />
          <meshStandardMaterial color={wall} roughness={0.84} />
        </mesh>
        {([-1, 1] as const).map((sx) => (
          <mesh key={sx} position={[sx * bw * 0.22, hallH / 2, bd * 0.14]} castShadow>
            <cylinderGeometry args={[0.15, 0.17, hallH, 12]} />
            <meshStandardMaterial color={wood} roughness={0.5} metalness={0.12} />
          </mesh>
        ))}
        <group position={[0, hallH + 0.1, 0]}>
          <HipRoof w={bw * 0.75} d={bd * 0.48} h={1.0} color={roof} accent={wood} ornate />
        </group>
        <group position={[0, hallH + 1.05, 0]}>
          <HipRoof w={bw * 0.55} d={bd * 0.36} h={0.7} color={roof} accent={wood} ornate />
        </group>
        {/* throne peek */}
        <mesh position={[0, 0.9, -0.15]} castShadow>
          <boxGeometry args={[1.2, 1.0, 0.5]} />
          <meshStandardMaterial color="#ca8a04" metalness={0.35} roughness={0.4} />
        </mesh>
      </group>

      {/* stone lions */}
      {([-1, 1] as const).map((sx) => (
        <mesh key={sx} position={[sx * 1.4, 0.7, bd * 0.62]} castShadow>
          <boxGeometry args={[0.5, 0.55, 0.45]} />
          <meshStandardMaterial color="#a8a29e" roughness={0.75} metalness={0.12} />
        </mesh>
      ))}

      <Plaque label={label} y={gateH + 0.9} z={bd * 0.52} wood={wood} accent="#eab308" />
      <pointLight position={[0, 3, 0]} intensity={night ? 0.9 : 0.35} distance={12} color="#fde68a" />
      <EnterBtn name={b.name} y={hallH + 4.2} onEnter={onEnter} />
    </group>
  );
}

/** 终南古观 — mountain temple courtyard. */
function TempleCourtyard({
  b, night, onEnter, bw, bd,
}: {
  b: LandmarkArch; night?: boolean; onEnter?: (n: string) => void; bw: number; bd: number;
}) {
  const label = b.sign || b.name;
  const wood = "#44403c";
  const wall = "#f5f5f4";
  const roof = "#292524";
  const stone = "#d6d3d1";
  const hallH = 3.0;
  const wingH = 2.2;

  return (
    <group>
      <mesh position={[0, 0.1, 0]} receiveShadow>
        <boxGeometry args={[bw * 1.15, 0.2, bd * 1.12]} />
        <meshStandardMaterial color={stone} roughness={0.94} />
      </mesh>
      <mesh position={[0, 0.28, 0]} receiveShadow>
        <boxGeometry args={[bw * 1.02, 0.22, bd * 1.0]} />
        <meshStandardMaterial color={stone} roughness={0.9} />
      </mesh>
      <StreetApproach bw={bw} bd={bd} length={5.0} />

      {/* court */}
      <mesh position={[0, 0.42, bd * 0.05]} receiveShadow>
        <boxGeometry args={[bw * 0.65, 0.05, bd * 0.4]} />
        <meshStandardMaterial color="#e7e5e4" roughness={0.96} />
      </mesh>

      {/* side corridors */}
      {([-1, 1] as const).map((sx) => (
        <group key={sx} position={[sx * bw * 0.38, 0.4, 0]}>
          <mesh castShadow receiveShadow>
            <boxGeometry args={[bw * 0.18, wingH, bd * 0.7]} />
            <meshStandardMaterial color={wall} roughness={0.88} />
          </mesh>
          <group position={[0, wingH + 0.05, 0]}>
            <HipRoof w={bw * 0.28} d={bd * 0.8} h={0.55} color={roof} accent={wood} />
          </group>
        </group>
      ))}

      {/* main hall back */}
      <group position={[0, 0.55, -bd * 0.25]}>
        <mesh castShadow receiveShadow>
          <boxGeometry args={[bw * 0.55, hallH, bd * 0.35]} />
          <meshStandardMaterial color={wall} roughness={0.86} />
        </mesh>
        {([-1, 1] as const).map((sx) => (
          <mesh key={sx} position={[sx * bw * 0.22, hallH / 2, bd * 0.14]} castShadow>
            <cylinderGeometry args={[0.12, 0.14, hallH, 10]} />
            <meshStandardMaterial color={wood} roughness={0.65} />
          </mesh>
        ))}
        <group position={[0, hallH + 0.08, 0]}>
          <HipRoof w={bw * 0.75} d={bd * 0.5} h={0.95} color={roof} accent={wood} ornate />
        </group>
        <mesh position={[0, 1.0, 0.05]} castShadow>
          <boxGeometry args={[1.4, 1.1, 0.45]} />
          <meshStandardMaterial color="#fafaf9" roughness={0.7} />
        </mesh>
      </group>

      {/* mountain gate */}
      <group position={[0, 0.4, bd * 0.48]}>
        {([-1, 1] as const).map((sx) => (
          <mesh key={sx} position={[sx * 0.9, 1.3, 0]} castShadow>
            <cylinderGeometry args={[0.12, 0.14, 2.6, 10]} />
            <meshStandardMaterial color={wood} />
          </mesh>
        ))}
        <mesh position={[0, 2.7, 0]} castShadow>
          <boxGeometry args={[2.2, 0.18, 0.7]} />
          <meshStandardMaterial color={wood} />
        </mesh>
        <group position={[0, 2.95, 0]}>
          <HipRoof w={2.8} d={1.3} h={0.6} color={roof} accent={wood} ornate />
        </group>
        <mesh position={[0, 1.1, 0.02]}>
          <boxGeometry args={[1.3, 2.0, 0.15]} />
          <meshStandardMaterial color="#1c1917" />
        </mesh>
      </group>

      {/* incense burner in court */}
      <mesh position={[0, 0.7, bd * 0.12]} castShadow>
        <cylinderGeometry args={[0.35, 0.42, 0.5, 16]} />
        <meshStandardMaterial color="#57534e" roughness={0.85} />
      </mesh>
      {[-0.2, 0, 0.2].map((x, i) => (
        <mesh key={i} position={[x, 1.1, bd * 0.12]} castShadow>
          <cylinderGeometry args={[0.03, 0.04, 0.4, 6]} />
          <meshStandardMaterial color="#1c1917" />
        </mesh>
      ))}
      {([-1, 1] as const).map((sx) => (
        <mesh key={sx} position={[sx * bw * 0.22, 0.95, bd * 0.35]} castShadow>
          <cylinderGeometry args={[0.08, 0.12, 1.0, 8]} />
          <meshStandardMaterial color="#78716c" />
        </mesh>
      ))}

      <Plaque label={label} y={3.2} z={bd * 0.52} wood="#292524" accent="#a8a29e" />
      <pointLight position={[0, 2.5, bd * 0.1]} intensity={night ? 0.7 : 0.3} distance={10} color="#fef3c7" />
      <EnterBtn name={b.name} y={hallH + 3.6} onEnter={onEnter} />
    </group>
  );
}

export function landmarkVariant(b: LandmarkArch): "tavern" | "palace" | "temple" {
  if (b.modelKey === "landmark_palace" || /紫宸|宫|殿/.test(b.name + (b.sign || ""))) return "palace";
  if (b.modelKey === "landmark_temple" || /古观|寺|庙|观/.test(b.name + (b.sign || ""))) return "temple";
  return "tavern";
}

export default function LandmarkBuilding({
  b, night, onEnter, bw, bd,
}: {
  b: LandmarkArch;
  genre?: string;
  night?: boolean;
  onEnter?: (n: string) => void;
  bw: number;
  bd: number;
  floors?: number;
}) {
  const v = landmarkVariant(b);
  if (v === "palace") return <PalaceSiheyuan b={b} night={night} onEnter={onEnter} bw={bw} bd={bd} />;
  if (v === "temple") return <TempleCourtyard b={b} night={night} onEnter={onEnter} bw={bw} bd={bd} />;
  return <TavernTwoStorey b={b} night={night} onEnter={onEnter} bw={bw} bd={bd} />;
}
