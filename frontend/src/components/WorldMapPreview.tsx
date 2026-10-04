"use client";

import dynamic from "next/dynamic";

const World3D = dynamic(() => import("@/components/World3D"), { ssr: false });

type Props = {
  genre: string;
  height?: number;
};

/** Compact 3D map preview for create page (v1.4 UI-004). */
export default function WorldMapPreview({ genre, height = 220 }: Props) {
  return (
    <div className="w-full rounded-lg border border-stone-800 overflow-hidden relative"
         style={{ height }}>
      <World3D
        genre={genre}
        worldLocations={[]}
        agents={[]}
        playerId={null}
        height={height}
        cameraMode="third"
        onCameraModeChange={() => {}}
        hour={10}
        previewMode
      />
      <div className="absolute bottom-2 left-2 text-[10px] uppercase tracking-widest
                      opacity-50 pointer-events-none">
        3D 世界预览
      </div>
    </div>
  );
}
