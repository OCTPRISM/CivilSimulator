"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Center, OrbitControls, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { loadGlbBlobUrl } from "@/lib/api";

function Model({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  const cloned = useMemo(() => {
    const root = scene.clone(true);
    const fallback = new THREE.MeshStandardMaterial({
      color: "#e7e5e4",
      roughness: 0.62,
      metalness: 0.08,
      side: THREE.DoubleSide,
    });
    root.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      const geo = mesh.geometry;
      if (geo) {
        if (!geo.getAttribute("normal")) geo.computeVertexNormals();
        geo.computeBoundingSphere();
      }
      mesh.material = fallback;
      mesh.frustumCulled = false;
    });
    const box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    const sy = size.y > 0.01 ? 1.6 / size.y : 1;
    root.scale.setScalar(sy);
    return root;
  }, [scene]);
  return (
    <Center>
      <primitive object={cloned} />
    </Center>
  );
}

function Scene({ blobUrl }: { blobUrl: string }) {
  return (
    <>
      <color attach="background" args={["#1c1917"]} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[3, 5, 2]} intensity={1.35} />
      <directionalLight position={[-2, 2, -3]} intensity={0.45} />
      <Suspense fallback={null}>
        <Model url={blobUrl} />
      </Suspense>
      <OrbitControls enablePan={false} minDistance={1.2} maxDistance={5} />
    </>
  );
}

type Props = { url: string };

export default function GlbViewer({ url }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setErr(null);
    setBlobUrl(null);

    const load = async () => {
      // Public / static assets — no auth. API paths need Authorization.
      if (url.startsWith("/generated/") || url.startsWith("/models/") || url.startsWith("blob:")) {
        return url;
      }
      return loadGlbBlobUrl(url);
    };

    load()
      .then((u) => {
        if (cancelled) {
          if (u.startsWith("blob:")) URL.revokeObjectURL(u);
          return;
        }
        objectUrl = u.startsWith("blob:") ? u : null;
        setBlobUrl(u);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e).replace(/^Error:\s*/i, ""));
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  return (
    <div className="relative w-full h-[480px] lg:h-full min-h-[360px] bg-gradient-to-b from-stone-900 to-stone-950">
      {err && (
        <div className="absolute inset-0 z-10 flex items-center justify-center text-sm text-red-400/80 px-4 text-center">
          {err}
        </div>
      )}
      {!err && !blobUrl && (
        <div className="absolute inset-0 z-10 flex items-center justify-center text-sm opacity-45">
          加载 3D 模型…
        </div>
      )}
      {blobUrl && (
        <Canvas camera={{ position: [0, 1.2, 2.4], fov: 42 }} shadows className="absolute inset-0">
          <Scene blobUrl={blobUrl} />
        </Canvas>
      )}
    </div>
  );
}
