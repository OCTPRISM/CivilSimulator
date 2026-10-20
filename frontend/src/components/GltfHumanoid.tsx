"use client";

/**
 * Unique per-role GLTF humanoid + selectable body-owned skin PBR (4 packs).
 * Clothing silhouette is baked into each role's body.glb — no Mixamo overlay / gear kit.
 * Hy3d (shape-only) bodies get role-specific vertex outfit bands + simple face cues + catalog props.
 */
import { useMemo, useRef } from "react";
import { useFrame, useLoader } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { clone as cloneSkinned } from "three/examples/jsm/utils/SkeletonUtils.js";
import type { FigurePreset, RoleSkinId } from "@/lib/characterFigures";
import {
  classifyMaterialSlot, clothPackUrls, metalPackUrls, roleBodyDef, roleSkinUrls,
} from "@/lib/gltfCharacters";
import AncientRoleProps from "@/components/AncientRoleProps";

type Props = {
  preset: FigurePreset;
  behavior?: string;
  dormant?: boolean;
  highlight?: boolean;
  scale?: number;
  showcase?: boolean;
};

type SlotTex = {
  map: THREE.Texture;
  roughnessMap: THREE.Texture;
  normalMap: THREE.Texture;
  metalnessMap: THREE.Texture;
};

function useLookTextures(preset: FigurePreset) {
  const skinId = (preset.skinVariant || "fair") as RoleSkinId;
  const bodyId = preset.bodyId || preset.id;
  const urls = useMemo(() => {
    const s = roleSkinUrls(bodyId, skinId);
    const c = clothPackUrls(preset.clothPack);
    const m = metalPackUrls(preset.metalPack);
    return [
      s.map, s.roughnessMap, s.normalMap, s.metalnessMap,
      c.map, c.roughnessMap, c.normalMap, c.metalnessMap,
      m.map, m.roughnessMap, m.normalMap, m.metalnessMap,
    ];
  }, [bodyId, skinId, preset.clothPack, preset.metalPack]);

  const tex = useLoader(THREE.TextureLoader, urls);

  return useMemo(() => {
    const assign = (slice: THREE.Texture[]): SlotTex => {
      const [map, roughnessMap, normalMap, metalnessMap] = slice;
      map.colorSpace = THREE.SRGBColorSpace;
      for (const t of slice) {
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
        t.anisotropy = 8;
        t.needsUpdate = true;
      }
      return { map, roughnessMap, normalMap, metalnessMap };
    };
    return {
      skin: assign(tex.slice(0, 4) as THREE.Texture[]),
      cloth: assign(tex.slice(4, 8) as THREE.Texture[]),
      metal: assign(tex.slice(8, 12) as THREE.Texture[]),
    };
  }, [tex]);
}

function GltfBody({
  preset, behavior, dormant, highlight, scale, showcase,
}: Props) {
  const bodyId = preset.bodyId || preset.id;
  const def = roleBodyDef(bodyId, preset.skinVariant, preset.outfitStyle);
  const group = useRef<THREE.Group>(null);
  const { scene } = useGLTF(def.url);
  const pbr = useLookTextures(preset);

  const cloned = useMemo(() => {
    const root = cloneSkinned(scene) as THREE.Group;
    const glow = preset.glow ?? 0;
    const isHy3d = def.url.includes("/hy3d/");

    if (isHy3d) {
      root.updateMatrixWorld(true);
      let box = new THREE.Box3().setFromObject(root);
      // Ground feet to y=0 so showcase/Play show full legs (meshes often centered).
      root.position.y -= box.min.y;
      root.updateMatrixWorld(true);
      box = new THREE.Box3().setFromObject(root);

      // Textured Paint GLBs: keep baked albedo (skin/face/cloth) — do not vertex-tint.
      let hasMaps = false;
      root.traverse((obj: THREE.Object3D) => {
        const mesh = obj as THREE.Mesh;
        if (!mesh.isMesh) return;
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const mat of mats) {
          if (mat && "map" in mat && (mat as THREE.MeshStandardMaterial).map) hasMaps = true;
        }
      });
      if (hasMaps) {
        root.traverse((obj: THREE.Object3D) => {
          const mesh = obj as THREE.Mesh;
          if (!mesh.isMesh) return;
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          const next = mats.map((mat) => {
            if (!(mat instanceof THREE.MeshStandardMaterial) && !(mat instanceof THREE.MeshPhysicalMaterial)) {
              return mat;
            }
            const m = mat.clone();
            m.side = THREE.DoubleSide;
            m.envMapIntensity = 1.15;
            m.roughness = Math.min(0.88, Math.max(0.4, m.roughness ?? 0.65));
            // Sharpen baked Paint albedo: mipmaps + high anisotropy.
            for (const slot of [m.map, m.normalMap, m.roughnessMap, m.metalnessMap] as (THREE.Texture | null)[]) {
              if (!slot) continue;
              slot.colorSpace = slot === m.map ? THREE.SRGBColorSpace : THREE.NoColorSpace;
              slot.anisotropy = 16;
              slot.generateMipmaps = true;
              slot.minFilter = THREE.LinearMipmapLinearFilter;
              slot.magFilter = THREE.LinearFilter;
              slot.needsUpdate = true;
            }
            m.needsUpdate = true;
            return m;
          });
          mesh.material = next.length === 1 ? next[0] : next;
        });
        return root;
      }

      // Shape-only fallback — role outfit bands (not flat skin tint).
      const y0 = box.min.y;
      const span = Math.max(0.01, box.max.y - box.min.y);
      const x0 = box.min.x;
      const xSpan = Math.max(0.01, box.max.x - x0);
      const z0 = box.min.z;
      const zSpan = Math.max(0.01, box.max.z - z0);
      const skinC = new THREE.Color(preset.skin);
      const clothC = new THREE.Color(preset.torso);
      const hairC = new THREE.Color(preset.hair);
      const shoeC = new THREE.Color(preset.legs);
      const accentC = new THREE.Color(preset.accent);
      const sleeveC = clothC.clone().offsetHSL(0, -0.05, -0.12);
      const sashC = accentC.clone().lerp(clothC, 0.25);
      const coat = preset.coat || "robe";
      const bands =
        coat === "armor" ? { shoe: 0.1, hem: 0.28, sash: 0.48, collar: 0.72, face: 0.84 } :
        coat === "cloak" ? { shoe: 0.1, hem: 0.22, sash: 0.42, collar: 0.7, face: 0.83 } :
        coat === "apron" ? { shoe: 0.12, hem: 0.35, sash: 0.55, collar: 0.74, face: 0.85 } :
        coat === "vest" ? { shoe: 0.1, hem: 0.32, sash: 0.5, collar: 0.72, face: 0.84 } :
        { shoe: 0.1, hem: 0.3, sash: 0.48, collar: 0.7, face: 0.83 };

      root.traverse((obj: THREE.Object3D) => {
        const mesh = obj as THREE.Mesh;
        if (!mesh.isMesh || !mesh.geometry) return;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        const geo = mesh.geometry.clone();
        if (!geo.getAttribute("normal")) geo.computeVertexNormals();
        const pos = geo.getAttribute("position");
        const colors = new Float32Array(pos.count * 3);
        const tmp = new THREE.Color();
        for (let i = 0; i < pos.count; i++) {
          const t = (pos.getY(i) - y0) / span;
          const nx = (pos.getX(i) - x0) / xSpan;
          const nz = (pos.getZ(i) - z0) / zSpan;
          const front = nz > 0.55;
          if (t > bands.face) {
            tmp.copy(hairC);
          } else if (t > bands.collar) {
            tmp.copy(skinC);
            const eyeY = t > 0.88 && t < 0.94;
            const eyeX = (nx > 0.28 && nx < 0.42) || (nx > 0.58 && nx < 0.72);
            const mouth = t > 0.84 && t < 0.87 && nx > 0.4 && nx < 0.6;
            if (front && eyeY && eyeX) tmp.set("#1a1520");
            else if (front && mouth) tmp.copy(skinC).offsetHSL(0, 0.05, -0.22);
            else if (t > 0.92) tmp.copy(hairC).lerp(skinC, 0.35);
          } else if (t > bands.sash - 0.04 && t < bands.sash + 0.06) {
            tmp.copy(sashC);
          } else if (t < bands.shoe) {
            tmp.copy(shoeC);
          } else if (t < bands.hem) {
            tmp.copy(sleeveC).lerp(shoeC, 0.15);
          } else {
            const sleeve = nx < 0.18 || nx > 0.82;
            tmp.copy(sleeve ? sleeveC : clothC);
            if (coat === "armor" && t > 0.55 && t < 0.7) tmp.lerp(accentC, 0.25);
            if (coat === "cloak" && nz < 0.35) tmp.lerp(shoeC, 0.35);
          }
          colors[i * 3] = tmp.r;
          colors[i * 3 + 1] = tmp.g;
          colors[i * 3 + 2] = tmp.b;
        }
        geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
        mesh.geometry = geo;
        mesh.material = new THREE.MeshStandardMaterial({
          vertexColors: true,
          roughness: coat === "armor" ? 0.55 : 0.7,
          metalness: coat === "armor" ? 0.22 : 0.04,
          side: THREE.DoubleSide,
        });
      });
      return root;
    }

    root.traverse((obj: THREE.Object3D) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const next = mats.map((mat) => {
        if (!(mat instanceof THREE.MeshStandardMaterial) && !(mat instanceof THREE.MeshPhysicalMaterial)) {
          return mat;
        }
        const slot = classifyMaterialSlot(`${mat.name}|${mesh.name}`);
        const m = mat.clone() as THREE.MeshStandardMaterial;

        if (slot === "eye") {
          m.color = new THREE.Color("#1a2840");
          m.map = null;
          m.roughnessMap = null;
          m.normalMap = null;
          m.metalnessMap = null;
          m.roughness = 0.12;
          m.metalness = 0.08;
          m.emissive = new THREE.Color("#3060a0");
          m.emissiveIntensity = 0.35;
          m.envMapIntensity = 1.4;
          m.needsUpdate = true;
          return m;
        }

        if (slot === "hair") {
          m.color = new THREE.Color(preset.hair);
          m.map = null;
          m.roughnessMap = null;
          m.normalMap = null;
          m.metalnessMap = null;
          m.roughness = 0.72;
          m.metalness = 0.02;
          m.envMapIntensity = 0.35;
          m.needsUpdate = true;
          return m;
        }

        if (slot === "skin") {
          const src = pbr.skin;
          m.color = new THREE.Color("#ffffff");
          m.map = src.map;
          m.roughnessMap = src.roughnessMap;
          m.normalMap = src.normalMap;
          m.metalnessMap = src.metalnessMap;
          m.roughness = 0.55;
          m.metalness = 0.02;
          m.envMapIntensity = 0.55;
        } else if (slot === "metal") {
          const src = pbr.metal;
          m.color = new THREE.Color(preset.accent);
          m.map = src.map;
          m.roughnessMap = src.roughnessMap;
          m.normalMap = src.normalMap;
          m.metalnessMap = src.metalnessMap;
          m.roughness = /chrome|neon|spirit_silver/.test(preset.metalPack) ? 0.22 : 0.4;
          m.metalness = 0.88;
          m.envMapIntensity = 1.15;
          if (highlight || glow > 0) {
            m.emissive = new THREE.Color(preset.accent);
            m.emissiveIntensity = highlight ? 0.12 : glow * 0.35;
          }
        } else {
          const src = pbr.cloth;
          m.color = new THREE.Color(preset.torso);
          m.map = src.map;
          m.roughnessMap = src.roughnessMap;
          m.normalMap = src.normalMap;
          m.metalnessMap = src.metalnessMap;
          const silky = /silk|robe/.test(preset.clothPack);
          const techy = /tech|neon/.test(preset.clothPack);
          m.roughness = silky ? 0.5 : techy ? 0.42 : 0.75;
          m.metalness = techy ? 0.28 : 0.06;
          m.envMapIntensity = 0.5;
          if (highlight || glow > 0) {
            m.emissive = new THREE.Color(preset.accent);
            m.emissiveIntensity = highlight ? 0.06 : glow * 0.2;
          }
        }
        m.needsUpdate = true;
        return m;
      });
      mesh.material = next.length === 1 ? next[0] : next;
    });
    return root;
  }, [scene, pbr, preset, highlight, def.url]);

  useFrame((state) => {
    if (!group.current || dormant) return;
    const t = state.clock.elapsedTime;
    if (showcase) group.current.rotation.y = Math.sin(t * 0.25) * 0.2;
    const wantWalk = behavior === "walk" || behavior === "swim";
    group.current.position.y = def.y + (wantWalk
      ? Math.abs(Math.sin(t * 6)) * 0.04
      : Math.sin(t * 1.4) * 0.008);
    if (wantWalk && !showcase) group.current.rotation.y = Math.sin(t * 0.5) * 0.06;
  });

  const h = preset.build.height * (preset.tall ? 1.04 : 1);
  const b = preset.build.bulk;
  const s = def.scale * (scale ?? 1) * (showcase ? 1.02 : 1);

  // Props only — clothing styles swap `def.url`, never overlay a second body.
  const equipped = (preset.equippedProps || []).filter((slug) => {
    // Inline: clothing slugs must not attach even if stale state still lists them.
    return !["青衫", "麻短褐", "短褐背心", "皮围裙", "皮护腕"].includes(slug);
  });

  return (
    <group ref={group} position={[0, def.y, 0]} scale={[s * b, s * h, s * b]}>
      <primitive object={cloned} />
      {equipped.length > 0 && (preset.genre === "ancient" || bodyId.startsWith("ancient_")) ? (
        <AncientRoleProps slugs={equipped} />
      ) : null}
    </group>
  );
}

export default function GltfHumanoid(props: Props) {
  const bodyId = props.preset.bodyId || props.preset.id;
  const lookKey = [
    bodyId,
    props.preset.outfitStyle || "default",
    props.preset.skinVariant,
    props.preset.clothPack,
    props.preset.metalPack,
    (props.preset.equippedProps || []).join(","),
  ].join("|");
  return <GltfBody key={lookKey} {...props} />;
}
