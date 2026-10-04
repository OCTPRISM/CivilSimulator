"use client";

/**
 * Loads Blender hero GLB v0.9 — body/cloth/weapon only, no env/fx duplicates.
 * Falls back to null if load fails — caller should use HeroWuxiaWanderer.
 */
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import type { FigurePreset } from "@/lib/characterFigures";

const GLB_URL = "/models/characters/hero/wuxia_wanderer/ronin_character_v0.9.glb";

type Props = {
  preset: FigurePreset;
  behavior?: string;
  dormant?: boolean;
  highlight?: boolean;
  scale?: number;
  showcase?: boolean;
};

export default function HeroBlenderRonin({
  behavior, dormant, highlight, scale = 1, showcase,
}: Props) {
  const group = useRef<THREE.Group>(null);
  const { scene } = useGLTF(GLB_URL);

  const cloned = useMemo(() => {
    const root = scene.clone(true);
    const box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    // Normalize to ~1.75m tall humanoid for WebGL world
    const targetH = 1.75;
    const sy = size.y > 0.01 ? targetH / size.y : 1;
    root.scale.setScalar(sy);
    root.position.set(-center.x * sy, -box.min.y * sy, -center.z * sy);
    root.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      if (highlight && mesh.material instanceof THREE.MeshStandardMaterial) {
        const m = mesh.material.clone();
        m.emissive = new THREE.Color("#fbbf24");
        m.emissiveIntensity = 0.08;
        mesh.material = m;
      }
    });
    return root;
  }, [scene, highlight]);

  useFrame((state) => {
    if (!group.current || dormant) return;
    const t = state.clock.elapsedTime;
    const bob = behavior === "walk"
      ? Math.abs(Math.sin(t * 6)) * 0.03
      : showcase
        ? Math.sin(t * 0.8) * 0.008
        : Math.sin(t * 1.3) * 0.005;
    group.current.position.y = bob;
    if (showcase) group.current.rotation.y = Math.sin(t * 0.2) * 0.08;
  });

  return (
    <group ref={group} scale={scale} position={[0, 0, 0]}>
      <primitive object={cloned} />
    </group>
  );
}

useGLTF.preload(GLB_URL);
