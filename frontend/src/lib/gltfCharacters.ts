/**
 * Per-role unique GLTF bodies + 4 selectable separated skin PBR packs.
 * Bodies live under /models/characters/roles/{roleId}/body.glb
 * Skins: fair | tan | warm | pale — each with albedo/roughness/normal/metalness.
 */
import type { ClothPackId, FigurePreset, FigureStyle, MetalPackId, RoleSkinId } from "@/lib/characterFigures";
import { ROLE_SKIN_IDS } from "@/lib/characterFigures";

export type PbrSlotMaps = {
  map: string;
  roughnessMap: string;
  normalMap: string;
  metalnessMap: string;
};

export type RoleBodyDef = {
  id: string;
  url: string;
  scale: number;
  y: number;
  label: string;
};

/**
 * Hunyuan NPC bodies are paper-flat cutouts with near-identical silhouettes.
 * Keep empty so street life uses volumetric ProceduralHumanoid + role clothing.
 */
const HY3D_NPC_BODIES = new Set<string>();
const HY3D_NPC_CACHE = "hyNpc6";

export function markHy3dNpcReady(_ids: string[]) {
  /* intentionally no-op — do not re-enable flat hy3d NPC meshes */
}

export function hy3dNpcReadyIds(): string[] {
  return [...HY3D_NPC_BODIES];
}

/** Unique body mesh for this role — prefer Hunyuan3D when ready. */
export function roleBodyDef(roleId: string): RoleBodyDef {
  const hy = HY3D_NPC_BODIES.has(roleId);
  return {
    id: roleId,
    url: hy
      ? `/models/characters/roles/${roleId}/hy3d/body.glb?v=${HY3D_NPC_CACHE}`
      : `/models/characters/roles/${roleId}/body.glb`,
    scale: hy ? 1.75 : 1,
    y: hy ? 0.05 : 0,
    label: roleId,
  };
}

export function roleBodyUrl(roleId: string): string {
  return roleBodyDef(roleId).url;
}

/** 4 selectable skin packs owned by this role's body. */
export function roleSkinUrls(roleId: string, skin: RoleSkinId): PbrSlotMaps {
  const base = `/models/characters/roles/${roleId}/skins/${skin}`;
  return {
    map: `${base}/albedo.png`,
    roughnessMap: `${base}/roughness.png`,
    normalMap: `${base}/normal.png`,
    metalnessMap: `${base}/metalness.png`,
  };
}

export function isRoleSkinId(id: string | undefined | null): id is RoleSkinId {
  return !!id && (ROLE_SKIN_IDS as readonly string[]).includes(id);
}

function sharedPackUrls(kind: string, id: string): PbrSlotMaps {
  const base = `/models/characters/pbr/${kind}_${id}`;
  return {
    map: `${base}/albedo.png`,
    roughnessMap: `${base}/roughness.png`,
    normalMap: `${base}/normal.png`,
    metalnessMap: `${base}/metalness.png`,
  };
}

export function clothPackUrls(id: ClothPackId): PbrSlotMaps {
  return sharedPackUrls("cloth", id);
}
export function metalPackUrls(id: MetalPackId): PbrSlotMaps {
  return sharedPackUrls("metal", id);
}

export function classifyMaterialSlot(name: string): "skin" | "cloth" | "metal" | "hair" | "eye" {
  const n = name.toLowerCase();
  if (/eye|teeth|tooth|cornea|sclera/.test(n)) return "eye";
  if (/^hair$|hair|beard|topknot/.test(n)) return "hair";
  if (/^metal$|visor|joint|metal|armor|helm|plate|iron|steel/.test(n)) return "metal";
  if (/^skin$|skin|face|limb|flesh|hand|neck|head/.test(n)) return "skin";
  if (/^cloth$|cloth|robe|cape|fabric|shirt|pant|coat|suit/.test(n)) return "cloth";
  return "cloth";
}

export function genreStageMood(genre: FigurePreset["genre"]): {
  bg: string; fog: string; key: string; fill: string; rim: string; exposure: number;
} {
  switch (genre) {
    case "wuxia":
      return { bg: "#0a0908", fog: "#1a1410", key: "#ffb070", fill: "#5a6e8a", rim: "#c9a45a", exposure: 1.05 };
    case "ancient":
      return { bg: "#0c0a08", fog: "#2a2018", key: "#ffd090", fill: "#6a7a90", rim: "#e8c070", exposure: 1.1 };
    case "scifi":
      return { bg: "#050810", fog: "#0a1020", key: "#80d0ff", fill: "#4060a0", rim: "#40f0e0", exposure: 0.95 };
    case "xuanhuan":
      return { bg: "#080610", fog: "#1a1030", key: "#d0a0ff", fill: "#5060a0", rim: "#80ffe0", exposure: 1.0 };
    case "mystery":
      return { bg: "#07060a", fog: "#121018", key: "#ff8a3a", fill: "#4a6080", rim: "#a08060", exposure: 0.92 };
    case "modern":
      return { bg: "#0a0c10", fog: "#141820", key: "#e8eef5", fill: "#5a7088", rim: "#60a5fa", exposure: 1.02 };
    default:
      return { bg: "#07060a", fog: "#0c0a10", key: "#ff9a55", fill: "#6a7e9a", rim: "#c9a45a", exposure: 1.0 };
  }
}

export function idlePreferForStyle(style: FigureStyle): string[] {
  if (style === "rogue") return ["sneak_pose", "idle", "Idle", "headShake", "Standing"];
  if (style === "scholar" || style === "merchant") return ["agree", "idle", "Idle", "Wave", "Yes"];
  if (style === "mage") return ["sad_pose", "SambaDance", "idle", "Idle"];
  if (style === "sci_fi") return ["Idle", "Standing", "ThumbsUp", "Wave"];
  if (style === "detective") return ["idle", "Idle", "Standing"];
  return ["Idle", "idle", "agree", "SambaDance", "Standing"];
}

export const ROLE_SKIN_LABELS: Record<RoleSkinId, string> = {
  fair: "白皙",
  tan: "古铜",
  warm: "暖麦",
  pale: "冷白",
};
