/** Dramatic per-role gear overlays — heads, hair, coats that change silhouette at a glance. */
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { FigurePreset, WeaponKind } from "@/lib/characterFigures";

function Mat({
  color, metalness = 0.05, roughness = 0.75, emissive, emissiveIntensity = 0, opacity = 1,
}: {
  color: string; metalness?: number; roughness?: number;
  emissive?: string; emissiveIntensity?: number; opacity?: number;
}) {
  return (
    <meshStandardMaterial
      color={color}
      metalness={metalness}
      roughness={roughness}
      emissive={emissive || color}
      emissiveIntensity={emissiveIntensity}
      transparent={opacity < 1}
      opacity={opacity}
    />
  );
}

function AccWeapon({ kind, accent }: { kind: WeaponKind; accent: string }) {
  if (kind === "none") return null;
  if (kind === "sword" || kind === "blade") {
    const thick = kind === "blade" ? 0.09 : 0.055;
    return (
      <group position={[0.4, 0.95, 0.1]} rotation={[0.12, 0.25, kind === "blade" ? -0.55 : -0.42]}>
        <mesh castShadow position={[0, 0.38, 0]}>
          <boxGeometry args={[kind === "blade" ? 0.035 : 0.018, kind === "blade" ? 0.62 : 0.78, thick]} />
          <Mat color="#e8eef6" metalness={0.9} roughness={0.18} />
        </mesh>
        <mesh castShadow position={[0, 0, 0]}>
          <boxGeometry args={[0.18, 0.035, 0.055]} />
          <Mat color={accent} metalness={0.75} roughness={0.28} />
        </mesh>
        <mesh castShadow position={[0, -0.16, 0]}>
          <cylinderGeometry args={[0.025, 0.03, 0.26, 8]} />
          <Mat color="#2a1810" roughness={0.9} />
        </mesh>
      </group>
    );
  }
  if (kind === "staff" || kind === "spear") {
    return (
      <group position={[0.38, 0.55, 0]} rotation={[0.04, 0, -0.05]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.02, 0.028, kind === "spear" ? 1.35 : 1.2, 8]} />
          <Mat color="#5a3a1c" roughness={0.88} />
        </mesh>
        {kind === "spear" && (
          <mesh castShadow position={[0, 0.72, 0]}>
            <coneGeometry args={[0.045, 0.18, 8]} />
            <Mat color={accent} metalness={0.85} roughness={0.22} />
          </mesh>
        )}
        {kind === "staff" && (
          <mesh castShadow position={[0, 0.58, 0]}>
            <sphereGeometry args={[0.05, 10, 10]} />
            <Mat color={accent} metalness={0.4} roughness={0.35} emissive={accent} emissiveIntensity={0.35} />
          </mesh>
        )}
      </group>
    );
  }
  if (kind === "bow") {
    return (
      <group position={[-0.32, 1.05, -0.08]} rotation={[0, 0.35, 0.08]}>
        <mesh castShadow rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.3, 0.015, 6, 28, Math.PI * 1.2]} />
          <Mat color="#6b3f1f" roughness={0.82} />
        </mesh>
        <mesh position={[0.02, 0, 0.02]}>
          <boxGeometry args={[0.004, 0.55, 0.004]} />
          <Mat color="#d6d3d1" roughness={0.5} />
        </mesh>
      </group>
    );
  }
  if (kind === "fan") {
    return (
      <group position={[0.34, 1.08, 0.12]} rotation={[0.35, -0.25, 0.15]}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <mesh key={i} castShadow rotation={[0, 0, (i - 2.5) * 0.14]} position={[0, 0.1, 0]}>
            <boxGeometry args={[0.03, 0.32, 0.006]} />
            <Mat color={i % 2 ? accent : "#fef3c7"} roughness={0.45} />
          </mesh>
        ))}
      </group>
    );
  }
  if (kind === "pistol" || kind === "rifle" || kind === "scanner") {
    const long = kind === "rifle";
    return (
      <group position={[0.34, 0.98, 0.14]} rotation={[0.05, -0.5, 0]}>
        <mesh castShadow>
          <boxGeometry args={[long ? 0.55 : 0.22, 0.055, 0.08]} />
          <Mat color="#111827" metalness={0.75} roughness={0.32} />
        </mesh>
        {kind === "scanner" && (
          <mesh position={[0.02, 0.04, 0.05]}>
            <planeGeometry args={[0.12, 0.16]} />
            <Mat color={accent} emissive={accent} emissiveIntensity={0.85} metalness={0.2} roughness={0.4} />
          </mesh>
        )}
        {kind === "rifle" && (
          <mesh position={[0.28, 0.02, 0]}>
            <cylinderGeometry args={[0.018, 0.022, 0.2, 8]} />
            <Mat color="#1f2937" metalness={0.8} roughness={0.3} />
          </mesh>
        )}
      </group>
    );
  }
  return null;
}

function HairMesh({ preset }: { preset: FigurePreset }) {
  const style = preset.hairStyle || "short";
  const c = preset.hair;
  if (style === "none") return null;
  if (style === "topknot") {
    return (
      <group position={[0, 1.72, -0.02]}>
        <mesh castShadow position={[0, 0.02, 0]}>
          <sphereGeometry args={[0.11, 14, 12]} />
          <Mat color={c} roughness={0.9} />
        </mesh>
        <mesh castShadow position={[0, 0.14, 0]}>
          <sphereGeometry args={[0.07, 12, 10]} />
          <Mat color={c} roughness={0.9} />
        </mesh>
      </group>
    );
  }
  if (style === "long") {
    return (
      <group>
        <mesh castShadow position={[0, 1.68, -0.02]}>
          <sphereGeometry args={[0.13, 14, 12]} />
          <Mat color={c} roughness={0.88} />
        </mesh>
        <mesh castShadow position={[0, 1.35, -0.1]} rotation={[0.2, 0, 0]}>
          <boxGeometry args={[0.22, 0.55, 0.08]} />
          <Mat color={c} roughness={0.9} />
        </mesh>
      </group>
    );
  }
  if (style === "ponytail") {
    return (
      <group>
        <mesh castShadow position={[0, 1.68, 0]}>
          <sphereGeometry args={[0.115, 14, 12]} />
          <Mat color={c} roughness={0.88} />
        </mesh>
        <mesh castShadow position={[0, 1.45, -0.16]} rotation={[0.55, 0, 0]}>
          <cylinderGeometry args={[0.035, 0.05, 0.42, 8]} />
          <Mat color={c} roughness={0.9} />
        </mesh>
      </group>
    );
  }
  if (style === "bun") {
    return (
      <group position={[0, 1.72, -0.04]}>
        <mesh castShadow>
          <torusGeometry args={[0.07, 0.045, 8, 16]} />
          <Mat color={c} roughness={0.88} />
        </mesh>
      </group>
    );
  }
  if (style === "neon") {
    return (
      <group position={[0, 1.68, 0]}>
        <mesh castShadow>
          <sphereGeometry args={[0.12, 14, 12]} />
          <Mat color={c} roughness={0.45} emissive={preset.accent} emissiveIntensity={0.45} />
        </mesh>
        <mesh position={[0.1, 0.02, 0.08]} rotation={[0.4, 0.5, 0]}>
          <boxGeometry args={[0.04, 0.12, 0.02]} />
          <Mat color={preset.accent} emissive={preset.accent} emissiveIntensity={0.7} />
        </mesh>
      </group>
    );
  }
  if (style === "messy") {
    return (
      <group position={[0, 1.66, 0]}>
        <mesh castShadow>
          <sphereGeometry args={[0.125, 10, 8]} />
          <Mat color={c} roughness={0.95} />
        </mesh>
        {[-0.08, 0, 0.08].map((x, i) => (
          <mesh key={i} castShadow position={[x, 0.08, -0.02]} rotation={[0.3, 0, x * 2]}>
            <boxGeometry args={[0.05, 0.1, 0.04]} />
            <Mat color={c} roughness={0.95} />
          </mesh>
        ))}
      </group>
    );
  }
  if (style === "bob") {
    return (
      <group position={[0, 1.64, 0]}>
        <mesh castShadow>
          <sphereGeometry args={[0.125, 14, 12]} />
          <Mat color={c} roughness={0.88} />
        </mesh>
        <mesh castShadow position={[0, -0.02, -0.02]} scale={[1.15, 0.85, 1.05]}>
          <sphereGeometry args={[0.13, 14, 10, 0, Math.PI * 2, 0, Math.PI * 0.65]} />
          <Mat color={c} roughness={0.9} />
        </mesh>
      </group>
    );
  }
  // short / buzz
  return (
    <mesh castShadow position={[0, 1.66, -0.01]}>
      <sphereGeometry args={[style === "buzz" ? 0.105 : 0.12, 14, 12]} />
      <Mat color={c} roughness={0.9} />
    </mesh>
  );
}

function HeadGear({ preset }: { preset: FigurePreset }) {
  const h = preset.head || "none";
  const accent = preset.accent;
  const hair = preset.hair;

  if (h === "bamboo_hat") {
    return (
      <group position={[0, 1.78, 0]}>
        <mesh castShadow rotation={[0, 0, 0]}>
          <coneGeometry args={[0.42, 0.18, 16]} />
          <Mat color="#a16207" roughness={0.85} />
        </mesh>
        <mesh castShadow position={[0, -0.02, 0]}>
          <cylinderGeometry args={[0.12, 0.14, 0.08, 12]} />
          <Mat color="#78350f" roughness={0.8} />
        </mesh>
      </group>
    );
  }
  if (h === "futou") {
    return (
      <group position={[0, 1.72, 0]}>
        <mesh castShadow>
          <boxGeometry args={[0.28, 0.1, 0.22]} />
          <Mat color="#1e293b" roughness={0.7} />
        </mesh>
        <mesh castShadow position={[-0.2, 0.02, 0]}>
          <boxGeometry args={[0.12, 0.08, 0.04]} />
          <Mat color="#0f172a" roughness={0.7} />
        </mesh>
        <mesh castShadow position={[0.2, 0.02, 0]}>
          <boxGeometry args={[0.12, 0.08, 0.04]} />
          <Mat color="#0f172a" roughness={0.7} />
        </mesh>
      </group>
    );
  }
  if (h === "hood") {
    return (
      <mesh castShadow position={[0, 1.62, -0.02]}>
        <sphereGeometry args={[0.2, 16, 12, 0, Math.PI * 2, 0, Math.PI * 0.62]} />
        <Mat color={hair} roughness={0.88} />
      </mesh>
    );
  }
  if (h === "helm") {
    return (
      <group position={[0, 1.68, 0]}>
        <mesh castShadow>
          <sphereGeometry args={[0.15, 16, 12, 0, Math.PI * 2, 0, Math.PI * 0.72]} />
          <Mat color={accent} metalness={0.85} roughness={0.25} />
        </mesh>
        <mesh castShadow position={[0, -0.02, 0.12]}>
          <boxGeometry args={[0.22, 0.08, 0.06]} />
          <Mat color={accent} metalness={0.8} roughness={0.28} />
        </mesh>
      </group>
    );
  }
  if (h === "visor") {
    return (
      <group position={[0, 1.68, 0.08]}>
        <mesh castShadow>
          <boxGeometry args={[0.24, 0.1, 0.12]} />
          <Mat color="#0f172a" metalness={0.7} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0, 0.06]}>
          <planeGeometry args={[0.2, 0.06]} />
          <Mat color={accent} emissive={accent} emissiveIntensity={0.9} metalness={0.3} roughness={0.25} />
        </mesh>
      </group>
    );
  }
  if (h === "fedora") {
    return (
      <group position={[0, 1.74, 0]}>
        <mesh castShadow rotation={[-0.08, 0.15, 0]}>
          <cylinderGeometry args={[0.14, 0.15, 0.1, 16]} />
          <Mat color="#1c1917" roughness={0.75} />
        </mesh>
        <mesh castShadow position={[0, -0.04, 0]} rotation={[-0.08, 0.15, 0]}>
          <cylinderGeometry args={[0.26, 0.26, 0.02, 20]} />
          <Mat color="#292524" roughness={0.8} />
        </mesh>
      </group>
    );
  }
  if (h === "mask") {
    return (
      <group position={[0, 1.55, 0.1]}>
        <mesh castShadow>
          <boxGeometry args={[0.16, 0.12, 0.04]} />
          <Mat color="#111827" roughness={0.55} metalness={0.2} />
        </mesh>
        <mesh position={[-0.04, 0.02, 0.022]}>
          <circleGeometry args={[0.025, 10]} />
          <Mat color={accent} emissive={accent} emissiveIntensity={0.7} />
        </mesh>
        <mesh position={[0.04, 0.02, 0.022]}>
          <circleGeometry args={[0.025, 10]} />
          <Mat color={accent} emissive={accent} emissiveIntensity={0.7} />
        </mesh>
      </group>
    );
  }
  if (h === "fox_ears") {
    return (
      <group position={[0, 1.72, 0]}>
        <mesh castShadow position={[-0.1, 0.08, 0]} rotation={[0, 0, 0.35]}>
          <coneGeometry args={[0.06, 0.14, 6]} />
          <Mat color="#ea580c" roughness={0.7} />
        </mesh>
        <mesh castShadow position={[0.1, 0.08, 0]} rotation={[0, 0, -0.35]}>
          <coneGeometry args={[0.06, 0.14, 6]} />
          <Mat color="#ea580c" roughness={0.7} />
        </mesh>
      </group>
    );
  }
  if (h === "goggles") {
    return (
      <group position={[0, 1.58, 0.12]}>
        <mesh castShadow position={[-0.05, 0, 0]}>
          <torusGeometry args={[0.04, 0.012, 8, 16]} />
          <Mat color={accent} metalness={0.8} roughness={0.25} />
        </mesh>
        <mesh castShadow position={[0.05, 0, 0]}>
          <torusGeometry args={[0.04, 0.012, 8, 16]} />
          <Mat color={accent} metalness={0.8} roughness={0.25} />
        </mesh>
        <mesh position={[0, 0, 0]}>
          <boxGeometry args={[0.04, 0.015, 0.015]} />
          <Mat color="#334155" metalness={0.6} roughness={0.4} />
        </mesh>
      </group>
    );
  }
  if (h === "nurse_cap") {
    return (
      <mesh castShadow position={[0, 1.74, 0.02]}>
        <boxGeometry args={[0.18, 0.05, 0.14]} />
        <Mat color="#f8fafc" roughness={0.55} />
      </mesh>
    );
  }
  if (h === "crown") {
    return (
      <group position={[0, 1.74, 0]}>
        <mesh castShadow>
          <torusGeometry args={[0.12, 0.025, 8, 20]} />
          <Mat color={accent} metalness={0.9} roughness={0.2} emissive={accent} emissiveIntensity={0.35} />
        </mesh>
        {[0, 1, 2, 3, 4].map((i) => (
          <mesh key={i} castShadow position={[Math.sin((i / 5) * Math.PI * 2) * 0.12, 0.06, Math.cos((i / 5) * Math.PI * 2) * 0.12]}>
            <coneGeometry args={[0.02, 0.07, 5]} />
            <Mat color={accent} metalness={0.85} roughness={0.22} emissive={accent} emissiveIntensity={0.4} />
          </mesh>
        ))}
      </group>
    );
  }
  return null;
}

function CoatMesh({ preset }: { preset: FigurePreset }) {
  const coat = preset.coat || "none";
  const bulk = preset.build?.bulk ?? 1;
  const torso = preset.torso;
  const legs = preset.legs;
  const accent = preset.accent;
  const glow = preset.glow ?? 0;

  if (coat === "cape") {
    return (
      <mesh castShadow position={[0, 1.15, -0.18]} rotation={[0.28, 0, 0]}>
        <boxGeometry args={[0.55 * bulk, 0.95, 0.05]} />
        <Mat color={accent} roughness={0.72} opacity={0.95} />
      </mesh>
    );
  }
  if (coat === "robe") {
    return (
      <group>
        <mesh castShadow position={[0, 0.85, 0.02]}>
          <cylinderGeometry args={[0.26 * bulk, 0.42 * bulk, 1.2, 12]} />
          <Mat color={torso} roughness={preset.clothPack === "silk" ? 0.42 : 0.78} opacity={0.96} />
        </mesh>
        <mesh castShadow position={[0, 1.25, 0.05]}>
          <torusGeometry args={[0.2 * bulk, 0.035, 8, 20]} />
          <Mat color={accent} metalness={0.55} roughness={0.35} emissive={accent} emissiveIntensity={glow * 0.4} />
        </mesh>
      </group>
    );
  }
  if (coat === "cloak") {
    return (
      <group>
        <mesh castShadow position={[0, 1.2, -0.12]} rotation={[0.35, 0, 0]}>
          <coneGeometry args={[0.48 * bulk, 1.15, 10]} />
          <Mat color={legs} roughness={0.85} opacity={0.94} />
        </mesh>
        <mesh castShadow position={[0, 1.55, 0]}>
          <sphereGeometry args={[0.22, 12, 10, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
          <Mat color={preset.hair} roughness={0.88} />
        </mesh>
      </group>
    );
  }
  if (coat === "trench") {
    return (
      <group>
        <mesh castShadow position={[0, 1.05, 0.04]}>
          <boxGeometry args={[0.52 * bulk, 0.95, 0.28]} />
          <Mat color={torso} roughness={0.7} />
        </mesh>
        <mesh castShadow position={[0, 0.55, 0.06]} rotation={[0.05, 0, 0]}>
          <boxGeometry args={[0.58 * bulk, 0.55, 0.32]} />
          <Mat color={legs} roughness={0.72} />
        </mesh>
        <mesh castShadow position={[0, 1.35, 0.05]}>
          <boxGeometry args={[0.2, 0.08, 0.06]} />
          <Mat color={accent} metalness={0.3} roughness={0.5} />
        </mesh>
      </group>
    );
  }
  if (coat === "exosuit") {
    return (
      <group>
        <mesh castShadow position={[0, 1.2, 0.08]}>
          <boxGeometry args={[0.42 * bulk, 0.45, 0.28]} />
          <Mat color={torso} metalness={0.55} roughness={0.35} emissive={accent} emissiveIntensity={0.15 + glow * 0.3} />
        </mesh>
        <mesh castShadow position={[0, 1.35, 0.16]}>
          <boxGeometry args={[0.18, 0.12, 0.08]} />
          <Mat color={accent} emissive={accent} emissiveIntensity={0.7} metalness={0.4} roughness={0.3} />
        </mesh>
        <mesh castShadow position={[0, 0.95, -0.18]}>
          <boxGeometry args={[0.35, 0.4, 0.15]} />
          <Mat color="#0f172a" metalness={0.6} roughness={0.4} />
        </mesh>
        {[-1, 1].map((s) => (
          <mesh key={s} castShadow position={[0.28 * s * bulk, 1.35, 0.02]} rotation={[0, 0, -0.4 * s]}>
            <boxGeometry args={[0.14, 0.1, 0.22]} />
            <Mat color={accent} metalness={0.8} roughness={0.25} />
          </mesh>
        ))}
      </group>
    );
  }
  if (coat === "vest") {
    return (
      <mesh castShadow position={[0, 1.15, 0.05]}>
        <boxGeometry args={[0.4 * bulk, 0.5, 0.22]} />
        <Mat color={torso} roughness={0.65} metalness={preset.clothPack === "leather" ? 0.15 : 0.05} />
      </mesh>
    );
  }
  if (coat === "apron") {
    return (
      <group>
        <mesh castShadow position={[0, 0.95, 0.12]}>
          <boxGeometry args={[0.36 * bulk, 0.7, 0.04]} />
          <Mat color="#ecfdf5" roughness={0.6} />
        </mesh>
        <mesh castShadow position={[0, 1.25, 0.1]}>
          <boxGeometry args={[0.12, 0.08, 0.06]} />
          <Mat color={accent} metalness={0.4} roughness={0.4} />
        </mesh>
      </group>
    );
  }
  if (coat === "sash") {
    return (
      <group>
        <mesh castShadow position={[0, 1.05, 0.08]} rotation={[0, 0, 0.15]}>
          <boxGeometry args={[0.5 * bulk, 0.1, 0.08]} />
          <Mat color={accent} roughness={0.55} />
        </mesh>
        <mesh castShadow position={[0.18, 0.85, 0.1]}>
          <boxGeometry args={[0.08, 0.35, 0.05]} />
          <Mat color={accent} roughness={0.55} />
        </mesh>
      </group>
    );
  }
  if (coat === "armor") {
    return (
      <group>
        {[-1, 1].map((s) => (
          <mesh key={s} castShadow position={[0.24 * s * bulk, 1.38, 0.02]} rotation={[0, 0, -0.4 * s]}>
            <boxGeometry args={[0.18, 0.1, 0.24]} />
            <Mat color={accent} metalness={0.85} roughness={0.22} />
          </mesh>
        ))}
        <mesh castShadow position={[0, 1.2, 0.1]}>
          <boxGeometry args={[0.36 * bulk, 0.35, 0.18]} />
          <Mat color={torso} metalness={0.45} roughness={0.4} />
        </mesh>
      </group>
    );
  }
  return null;
}

function FloatingOrb({ accent, glow }: { accent: string; glow: number }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((s) => {
    if (!ref.current) return;
    const t = s.clock.elapsedTime;
    ref.current.position.y = 1.55 + Math.sin(t * 2.2) * 0.08;
    ref.current.position.x = 0.35 + Math.sin(t * 1.1) * 0.04;
  });
  return (
    <mesh ref={ref} castShadow position={[0.35, 1.55, 0.15]}>
      <sphereGeometry args={[0.06, 12, 12]} />
      <Mat color={accent} emissive={accent} emissiveIntensity={0.6 + glow} metalness={0.3} roughness={0.25} />
      <pointLight color={accent} intensity={0.8 + glow} distance={2.2} />
    </mesh>
  );
}

/** Full kit: hair + head + coat + weapon + genre FX */
export default function FigureGearKit({ preset }: { preset: FigurePreset }) {
  const glow = preset.glow ?? 0;
  return (
    <group>
      <HairMesh preset={preset} />
      <HeadGear preset={preset} />
      <CoatMesh preset={preset} />
      <AccWeapon kind={preset.weapon} accent={preset.accent} />
      {(preset.genre === "xuanhuan" || preset.style === "mage") && glow > 0.15 && (
        <FloatingOrb accent={preset.accent} glow={glow} />
      )}
      {glow > 0 && (
        <pointLight
          position={[0, 1.35, 0.25]}
          color={preset.accent}
          intensity={glow * 1.1}
          distance={2.4}
        />
      )}
    </group>
  );
}
