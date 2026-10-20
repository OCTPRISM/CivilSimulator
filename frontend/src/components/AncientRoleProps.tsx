"use client";

import { Suspense, useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import { clone as cloneSkinned } from "three/examples/jsm/utils/SkeletonUtils.js";
import * as THREE from "three";
import {
  ancientPropUrl,
  attachesForSlugs,
  isAncientPropReady,
  type RolePropAttach,
} from "@/lib/ancientRoleProps";

function PropMesh({ attach }: { attach: RolePropAttach }) {
  const url = ancientPropUrl(attach.slug);
  const { scene } = useGLTF(url);
  const obj = useMemo(() => {
    const root = cloneSkinned(scene) as THREE.Group;
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      m.castShadow = true;
      m.receiveShadow = true;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      const next = mats.map((mat) => {
        if (!(mat instanceof THREE.MeshStandardMaterial) && !(mat instanceof THREE.MeshPhysicalMaterial)) {
          return new THREE.MeshStandardMaterial({
            color: "#c4a574",
            roughness: 0.65,
            metalness: 0.15,
          });
        }
        const c = mat.clone();
        c.side = THREE.DoubleSide;
        c.roughness = Math.min(0.85, c.roughness ?? 0.6);
        if (c.map) {
          c.map.anisotropy = 16;
          c.map.colorSpace = THREE.SRGBColorSpace;
          c.map.needsUpdate = true;
        }
        return c;
      });
      m.material = next.length === 1 ? next[0] : next;
    });

    // Fit longest axis, then seat by align (grip=handle/top at origin, bottom=planted).
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    const size = new THREE.Vector3();
    box.getSize(size);
    const longest = Math.max(size.x, size.y, size.z, 0.01);
    const target = attach.fitSize ?? (attach.kind === "clothing" ? 1.4 : 0.45);
    const fit = target / longest;
    root.scale.setScalar(fit);
    root.updateMatrixWorld(true);
    const box2 = new THREE.Box3().setFromObject(root);
    const center = box2.getCenter(new THREE.Vector3());
    const align = attach.align || "center";
    if (align === "bottom") {
      root.position.set(-center.x, -box2.min.y, -center.z);
    } else if (align === "grip") {
      // Seat so the upper end (handle / strap) sits near the socket.
      root.position.set(-center.x, -box2.max.y, -center.z);
    } else {
      root.position.set(-center.x, -center.y, -center.z);
    }
    return root;
  }, [scene, attach.kind, attach.fitSize, attach.align]);

  const rot = attach.rotation || [0, 0, 0];
  return (
    <group position={attach.position} rotation={rot} scale={attach.scale ?? 1}>
      <primitive object={obj} />
    </group>
  );
}

type Props = {
  /** Only user-checked / outfit-selected slugs — never auto-fills role defaults. */
  slugs?: string[];
};

export default function AncientRoleProps({ slugs }: Props) {
  const list = useMemo(
    () => attachesForSlugs(slugs || []).filter((a) => isAncientPropReady(a.slug)),
    [slugs],
  );
  if (!list.length) return null;
  return (
    <Suspense fallback={null}>
      {list.map((a) => (
        <PropMesh key={a.slug} attach={a} />
      ))}
    </Suspense>
  );
}

export function preloadAncientRoleProps(slugs: string[]) {
  for (const a of attachesForSlugs(slugs)) {
    useGLTF.preload(ancientPropUrl(a.slug));
  }
}
