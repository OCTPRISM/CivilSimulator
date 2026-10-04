"use client";

/**
 * Load a kit GLB and fit it to the building footprint.
 * Meshes are declared as R3F <mesh> elements (not <primitive>) so they
 * reliably survive Suspense remounts and auto-dispose.
 */
import { useMemo, Component, type ReactNode } from "react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import type { KitModel } from "@/lib/buildingKits";

type Props = {
  model: KitModel;
  targetW: number;
  targetD: number;
  floors?: number;
  night?: boolean;
};

type Part = {
  key: string;
  geometry: THREE.BufferGeometry;
  material: THREE.Material | THREE.Material[];
  position: THREE.Vector3;
  quaternion: THREE.Quaternion;
  scale: THREE.Vector3;
};

/** Height-band Tang palette for untextured Hunyuan meshes (no materials / grey only). */
function paintAncientUntextured(geo: THREE.BufferGeometry, yMin: number, yMax: number, tint?: string) {
  const pos = geo.getAttribute("position");
  if (!pos) return null;
  if (!geo.getAttribute("normal")) geo.computeVertexNormals();
  const nor = geo.getAttribute("normal");
  const colors = new Float32Array(pos.count * 3);
  const span = Math.max(0.01, yMax - yMin);
  const roof = new THREE.Color(tint || "#9f1239");
  const wall = new THREE.Color("#e8dcc8");
  const wood = new THREE.Color("#5c4033");
  const stone = new THREE.Color("#a8a29e");
  const tmp = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const y = pos.getY(i);
    const t = (y - yMin) / span;
    const ny = nor ? Math.abs(nor.getY(i)) : 0;
    if (t < 0.12) tmp.copy(stone);
    else if (t > 0.72 || ny > 0.72) tmp.copy(roof);
    else if (ny < 0.35 && t > 0.2 && t < 0.65) tmp.copy(wood).lerp(wall, 0.35);
    else tmp.copy(wall);
    colors[i * 3] = tmp.r;
    colors[i * 3 + 1] = tmp.g;
    colors[i * 3 + 2] = tmp.b;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  return new THREE.MeshStandardMaterial({
    vertexColors: true,
    roughness: 0.78,
    metalness: 0.05,
    side: THREE.DoubleSide,
    emissive: new THREE.Color("#3f2a1f"),
    emissiveIntensity: 0.12,
  });
}

export default function KitBuildingMesh({ model, targetW, targetD, floors = 2, night }: Props) {
  const gltf = useGLTF(model.url);

  const { parts, fitScale, yLift } = useMemo(() => {
    const tmp = gltf.scene.clone(true);
    tmp.updateMatrixWorld(true);
    const worldBox = new THREE.Box3().setFromObject(tmp);
    const size = worldBox.getSize(new THREE.Vector3());
    if (!Number.isFinite(size.x) || size.x < 0.05 || size.z < 0.05) {
      throw new Error(`empty kit ${model.url}`);
    }
    // Reject only Hunyuan flat reliefs — authored kits (dock etc.) can be thin by design
    if (model.url.includes("/hy3d/")) {
      const dims = [size.x, size.y, size.z].sort((a, b) => a - b);
      if (dims[0] / Math.max(dims[2], 1e-6) < 0.18) {
        throw new Error(`flat hy3d kit ${model.url}`);
      }
    }

    const footprint = Math.max(size.x, size.z);
    const wantFoot = Math.max(targetW, targetD, 2.5);
    const byFoot = wantFoot / footprint;
    const wantH = Math.max(
      wantFoot * (size.y > footprint * 1.8 ? 2.4 : 1.2),
      2.5 + Math.max(1, floors) * (size.y > footprint * 1.8 ? 0.9 : 0.5),
    );
    const byH = size.y > 0.01 ? wantH / size.y : byFoot;
    const fitScale = Math.min(6.5, Math.max(0.25, Math.max(byFoot, byH * 0.9) * (model.scale ?? 1)));
    const center = worldBox.getCenter(new THREE.Vector3());
    const yLift = -worldBox.min.y + 0.04;
    const untextured = model.url.includes("/hy3d/");

    const parts: Part[] = [];
    let i = 0;
    tmp.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh || !mesh.geometry) return;
      const geo = mesh.geometry.clone();
      geo.computeBoundingSphere();
      geo.computeBoundingBox();

      const src = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const hasMaps = src.some((m) => {
        const sm = m as THREE.MeshStandardMaterial;
        return !!(sm?.map || sm?.emissiveMap || sm?.normalMap);
      });
      const greyOnly = src.every((m) => {
        const sm = m as THREE.MeshStandardMaterial;
        if (!sm?.color) return true;
        const hsl = { h: 0, s: 0, l: 0 };
        sm.color.getHSL(hsl);
        return hsl.s < 0.08;
      });

      let mats: THREE.Material | THREE.Material[];
      if (untextured && (!hasMaps || greyOnly)) {
        const bb = geo.boundingBox!;
        const painted = paintAncientUntextured(geo, bb.min.y, bb.max.y, model.tint);
        mats = painted ?? new THREE.MeshStandardMaterial({ color: "#e8dcc8" });
        if (night && mats instanceof THREE.MeshStandardMaterial) {
          mats.emissiveIntensity = 0.22;
        }
      } else {
        mats = src.map((mat) => {
          const base = (mat?.clone?.() ?? new THREE.MeshStandardMaterial({ color: "#d4d4d8" })) as THREE.MeshStandardMaterial;
          base.side = THREE.DoubleSide;
          base.transparent = false;
          base.opacity = 1;
          base.depthWrite = true;
          if (base.color) {
            if (model.tint) base.color.multiply(new THREE.Color(model.tint));
            const hsl = { h: 0, s: 0, l: 0 };
            base.color.getHSL(hsl);
            if (hsl.l < 0.42) base.color.setHSL(hsl.h, Math.min(0.55, hsl.s + 0.05), 0.55);
          }
          if (model.emissive) {
            base.emissive = new THREE.Color(model.emissive);
            base.emissiveIntensity = (model.emissiveIntensity ?? 0.25) * (night ? 1.35 : 0.9);
          } else if (base.color) {
            base.emissive = base.color.clone().multiplyScalar(0.22);
            base.emissiveIntensity = night ? 0.4 : 0.5;
          }
          base.needsUpdate = true;
          return base;
        });
        mats = mats.length === 1 ? mats[0] : mats;
      }

      mesh.updateWorldMatrix(true, false);
      const pos = new THREE.Vector3();
      const quat = new THREE.Quaternion();
      const scl = new THREE.Vector3();
      mesh.matrixWorld.decompose(pos, quat, scl);
      pos.sub(center);
      pos.y += yLift;
      const safeScl = new THREE.Vector3(1, 1, 1);

      parts.push({
        key: `${model.url}-${i++}`,
        geometry: geo,
        material: mats,
        position: pos,
        quaternion: quat,
        scale: safeScl,
      });
    });

    if (!parts.length) throw new Error(`no meshes ${model.url}`);
    return { parts, fitScale, yLift };
  }, [gltf, model, targetW, targetD, floors, night]);

  return (
    <group scale={fitScale} position={[0, model.y ?? 0, 0]}>
      {parts.map((p) => (
        <mesh
          key={p.key}
          geometry={p.geometry}
          material={p.material}
          position={p.position}
          quaternion={p.quaternion}
          scale={p.scale}
          castShadow
          receiveShadow
          frustumCulled={false}
        />
      ))}
    </group>
  );
}

export class KitErrorBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(err: Error) {
    console.warn("[KitBuildingMesh]", err.message);
  }
  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

export function preloadKitUrls(urls: string[]) {
  for (const u of urls) {
    if (!u) continue;
    try {
      const p = useGLTF.preload(u) as unknown;
      // Swallow loader rejections so a missing GLB doesn't trip the Next error overlay.
      Promise.resolve(p).catch(() => undefined);
    } catch {
      /* ignore sync failures */
    }
  }
}
