/**
 * Hero Character Pipeline — one role at a time, iterative polish (v1.4 §12 Hero tier).
 * Batch GLB bodies are NOT used for pipeline roles until quality gate passes.
 */
import type { ComponentType } from "react";
import type { FigurePreset } from "@/lib/characterFigures";

/** Roles under active hero refinement — add more ONLY after quality gate. */
export const HERO_PIPELINE_ROLES = ["wuxia_wanderer"] as const;
export type HeroRoleId = (typeof HERO_PIPELINE_ROLES)[number];

export type HeroManifest = {
  character_id: string;
  iteration: number;
  generator_version: string;
  render_path: string;
  status: string;
};

export function isHeroPipelineRole(preset: FigurePreset): preset is FigurePreset & { id: HeroRoleId } {
  const id = preset.bodyId || preset.id;
  return (HERO_PIPELINE_ROLES as readonly string[]).includes(id);
}

export async function loadHeroManifest(roleId: HeroRoleId): Promise<HeroManifest | null> {
  try {
    const res = await fetch(`/models/characters/hero/${roleId}/manifest.json?v=${Date.now()}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** Lazy hero renderers — one file per role under components/hero/ */
export function heroRendererId(preset: FigurePreset): HeroRoleId | null {
  if (!isHeroPipelineRole(preset)) return null;
  return preset.bodyId as HeroRoleId || preset.id as HeroRoleId;
}

export type HeroRendererProps = {
  preset: FigurePreset;
  behavior?: string;
  dormant?: boolean;
  highlight?: boolean;
  scale?: number;
  showcase?: boolean;
};

type HeroRenderer = ComponentType<HeroRendererProps>;

const REGISTRY: Partial<Record<HeroRoleId, () => Promise<{ default: HeroRenderer }>>> = {
  wuxia_wanderer: () => import("@/components/hero/HeroWuxiaWanderer"),
};

export async function loadHeroRenderer(roleId: HeroRoleId): Promise<HeroRenderer | null> {
  const loader = REGISTRY[roleId];
  if (!loader) return null;
  const mod = await loader();
  return mod.default;
}
