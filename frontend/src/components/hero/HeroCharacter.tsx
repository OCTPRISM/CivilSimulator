"use client";

import { Suspense } from "react";
import HeroBlenderRonin from "@/components/hero/HeroBlenderRonin";
import HeroWuxiaWanderer from "@/components/hero/HeroWuxiaWanderer";
import type { HeroRendererProps } from "@/lib/heroCharacter";

/** Hero pipeline: Blender MCP GLB first, R3F fallback while loading / on error. */
export default function HeroCharacter(props: HeroRendererProps) {
  const id = props.preset.bodyId || props.preset.id;
  if (id === "wuxia_wanderer") {
    return (
      <Suspense fallback={<HeroWuxiaWanderer {...props} showcase={props.showcase ?? true} />}>
        <HeroBlenderRonin {...props} showcase={props.showcase ?? true} />
      </Suspense>
    );
  }
  return null;
}
