"use client";

import { Suspense, useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import HeroCharacter from "@/components/hero/HeroCharacter";
import { getFigure, withSkinVariant, ROLE_SKIN_IDS, type RoleSkinId } from "@/lib/characterFigures";
import { ROLE_SKIN_LABELS } from "@/lib/gltfCharacters";
import { loadHeroManifest, type HeroManifest } from "@/lib/heroCharacter";

function Stage({ skin, showcase }: { skin: RoleSkinId; showcase: boolean }) {
  const preset = withSkinVariant(getFigure("wuxia_wanderer"), skin);
  return (
    <>
      <color attach="background" args={["#0a0908"]} />
      <fog attach="fog" args={["#1a1410", 4, 14]} />
      <ambientLight intensity={0.22} color="#3a4250" />
      <hemisphereLight args={["#ffb070", "#120c08", 0.55]} />
      <directionalLight position={[3, 5, 2]} intensity={1.35} color="#ffd090" castShadow
        shadow-mapSize={[2048, 2048]} />
      <directionalLight position={[-2, 3, -1]} intensity={0.45} color="#5a7090" />
      <pointLight position={[0, 2.2, 1.5]} intensity={0.6} color="#fbbf24" distance={8} />
      <HeroCharacter preset={preset} showcase={showcase} highlight />
      <ContactShadows position={[0, 0, 0]} opacity={0.55} scale={8} blur={2.5} far={4} />
      <Environment preset="night" />
      <OrbitControls enablePan={false} minDistance={2.2} maxDistance={5.5}
        minPolarAngle={0.4} maxPolarAngle={Math.PI / 2.05} target={[0, 1.1, 0]} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <circleGeometry args={[2.5, 48]} />
        <meshStandardMaterial color="#1a1510" roughness={0.85} metalness={0.05} />
      </mesh>
    </>
  );
}

export default function DevHeroPage() {
  const [skin, setSkin] = useState<RoleSkinId>("warm");
  const [manifest, setManifest] = useState<HeroManifest | null>(null);
  const [showcase, setShowcase] = useState(true);

  useEffect(() => {
    loadHeroManifest("wuxia_wanderer").then(setManifest);
  }, []);

  return (
    <main className="min-h-screen bg-stone-950 text-stone-100 px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="font-serif text-2xl mb-1">Hero 打磨台 · 散修剑客</h1>
        <p className="text-sm opacity-60 mb-4">
          单角色长期迭代入口 — 不使用 batch GLB；每次改 <code className="text-amber-200/80">HeroWuxiaWanderer.tsx</code> 后在此验收。
        </p>

        {manifest && (
          <div className="mb-4 rounded-lg border border-amber-700/40 bg-amber-950/20 px-4 py-3 text-[12px] space-y-1">
            <div>迭代 #{manifest.iteration} · {manifest.render_path} · {manifest.status}</div>
            <div className="opacity-60">generator {manifest.generator_version}</div>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-4 mb-4">
          <div className="rounded-xl border border-stone-700 overflow-hidden" style={{ height: 420 }}>
            <Canvas shadows dpr={[1, 2]} gl={{ toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.08 }}>
              <Suspense fallback={null}>
                <Stage skin={skin} showcase={showcase} />
              </Suspense>
            </Canvas>
          </div>
          <div className="rounded-xl border border-stone-700 overflow-hidden bg-black/40">
            <img
              src="/models/characters/hero/wuxia_wanderer/preview_face_v0.9.png"
              alt="Blender 面部特写"
              className="w-full h-full object-cover"
              style={{ minHeight: 420 }}
            />
            <div className="text-[10px] opacity-50 px-2 py-1">Blender 面部特写 · v0.9</div>
          </div>
        </div>
        <div className="rounded-xl border border-stone-700 overflow-hidden bg-black/40 mb-4">
          <img
            src="/models/characters/hero/wuxia_wanderer/preview_ronin_v0.9.png"
            alt="Blender 全身渲染"
            className="w-full object-cover max-h-64"
          />
          <div className="text-[10px] opacity-50 px-2 py-1">Blender 全身 · 游侠 + 环首刀 · v0.9</div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
          {ROLE_SKIN_IDS.map((id) => (
            <button key={id} type="button" onClick={() => setSkin(id)}
              className={`rounded-lg border px-3 py-2 text-[12px] transition
                ${skin === id ? "border-amber-400 bg-amber-500/15" : "border-stone-700 hover:border-amber-500/40"}`}>
              {ROLE_SKIN_LABELS[id]}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-[12px] opacity-70 mb-6">
          <input type="checkbox" checked={showcase} onChange={(e) => setShowcase(e.target.checked)} />
          展示模式（慢速旋转 / 略放大头部）
        </label>

        <div className="text-[11px] opacity-50 space-y-1 border-t border-stone-800 pt-4">
          <p>Blender MCP 重建：<code>python3 backend/scripts/hero_compiler/mcp_run_ronin.py</code>（需 Blender 打开且 :9876 已连接）</p>
          <p>离线重建：<code>/Applications/Blender.app/Contents/MacOS/Blender --background --python backend/scripts/hero_compiler/blender_ronin_swordsman.py</code></p>
          <p>质量门禁通过前，其他角色仍使用 GLB / 程序化降级；仅 wuxia_wanderer 走 Hero 专线。</p>
        </div>
      </div>
    </main>
  );
}
