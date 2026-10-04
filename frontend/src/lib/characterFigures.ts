/** Per-scene / per-role figures — unique GLTF body each + 4 selectable skins. */
export type WeaponKind =
  | "sword" | "blade" | "staff" | "bow" | "spear" | "fan"
  | "pistol" | "rifle" | "scanner" | "none";

export type FigureStyle =
  | "warrior" | "rogue" | "scholar" | "mage" | "ranger"
  | "sci_fi" | "detective" | "merchant";

export type SceneGenre = "wuxia" | "ancient" | "scifi" | "xuanhuan" | "mystery" | "modern";

/** Four selectable separated PBR skins per unique role body. */
export const ROLE_SKIN_IDS = ["fair", "tan", "warm", "pale"] as const;
export type RoleSkinId = (typeof ROLE_SKIN_IDS)[number];

export type ClothPackId =
  | "hemp" | "silk" | "leather" | "tech" | "wool" | "linen" | "noir"
  | "robe_indigo" | "robe_crimson" | "armor_lacquer" | "coat_tweed"
  | "suit_charcoal" | "neon_mesh" | "silk_jade" | "burlap";
export type MetalPackId =
  | "iron" | "bronze" | "gold" | "jade" | "chrome" | "copper"
  | "obsidian" | "rust" | "spirit_silver" | "blood_iron" | "neon" | "verdigris";
export type Silhouette = "armored" | "robed" | "lean" | "stocky" | "cloaked" | "civilian";

/** @deprecated shared Mixamo ids — role bodies supersede these */
export type GltfModelId = "soldier" | "xbot" | "michelle" | "rpm" | "robot";
/** @deprecated use RoleSkinId */
export type SkinPackId = RoleSkinId | "weathered" | "ash" | "porcelain" | "olive" | "bronze_skin" | "cold";

export type FigureBuild = {
  height: number;
  bulk: number;
};

export type FigurePreset = {
  id: string;
  label: string;
  genre: SceneGenre;
  skin: string;
  hair: string;
  torso: string;
  legs: string;
  accent: string;
  weapon: WeaponKind;
  style: FigureStyle;
  /** Default of the 4 body-owned skin packs */
  skinVariant: RoleSkinId;
  clothPack: ClothPackId;
  metalPack: MetalPackId;
  silhouette: Silhouette;
  build: FigureBuild;
  /** Unique GLTF body id (= role id); never a shared sci-fi base */
  bodyId: string;
  cape?: boolean;
  hood?: boolean;
  pauldrons?: boolean;
  tall?: boolean;
  glow?: number;
  /** CSS thumb hints only — not runtime geometric overlays */
  hairStyle?: string;
  head?: string;
  coat?: string;
  /** @deprecated alias of skinVariant */
  skinPack?: SkinPackId;
  /** @deprecated unused — kept for older gallery strings */
  model?: GltfModelId;
};

const B = (height: number, bulk: number): FigureBuild => ({ height, bulk });

const SKIN_HEX: Record<RoleSkinId, string> = {
  fair: "#e8c9a8",
  tan: "#c49464",
  warm: "#c9925e",
  pale: "#f0dcc8",
};

function P(
  partial: Omit<FigurePreset, "bodyId" | "skin"> & { skinVariant: RoleSkinId; skin?: string },
): FigurePreset {
  return {
    ...partial,
    bodyId: partial.id,
    skin: partial.skin || SKIN_HEX[partial.skinVariant],
    skinPack: partial.skinVariant,
  };
}

export const FIGURE_PRESETS: Record<string, FigurePreset> = {
  // —— 武侠 · 射雕/仙剑轮廓（独立 GLB）——
  wuxia_wanderer: P({
    id: "wuxia_wanderer", label: "散修剑客", genre: "wuxia",
    hair: "#1a1520", torso: "#3d4554", legs: "#1e2430",
    accent: "#a8b8c8", weapon: "sword", style: "warrior",
    skinVariant: "warm", clothPack: "armor_lacquer", metalPack: "iron", silhouette: "armored",
    build: B(1.02, 1.05), hairStyle: "topknot", head: "none", coat: "cape", cape: true,
  }),
  wuxia_sect_disciple: P({
    id: "wuxia_sect_disciple", label: "名门弟子", genre: "wuxia",
    hair: "#0f0e12", torso: "#f4f6f8", legs: "#d8dde6",
    accent: "#5eb8e8", weapon: "sword", style: "warrior",
    skinVariant: "fair", clothPack: "silk", metalPack: "spirit_silver", silhouette: "armored",
    build: B(1.04, 0.98), pauldrons: true, hairStyle: "ponytail", head: "helm", coat: "armor",
  }),
  wuxia_blade_rogue: P({
    id: "wuxia_blade_rogue", label: "浪迹刀客", genre: "wuxia",
    hair: "#0a0c10", torso: "#3a2410", legs: "#1a1210",
    accent: "#c46a2a", weapon: "blade", style: "rogue",
    skinVariant: "warm", clothPack: "leather", metalPack: "rust", silhouette: "cloaked",
    build: B(0.98, 1.02), hairStyle: "long", head: "hood", coat: "cloak", hood: true,
  }),
  wuxia_thief: P({
    id: "wuxia_thief", label: "妙手神偷", genre: "wuxia",
    hair: "#111827", torso: "#1e293b", legs: "#0f172a",
    accent: "#22d3ee", weapon: "none", style: "rogue",
    skinVariant: "tan", clothPack: "noir", metalPack: "obsidian", silhouette: "lean",
    build: B(0.96, 0.9), hairStyle: "short", head: "mask", coat: "cloak", hood: true,
  }),
  wuxia_beggar: P({
    id: "wuxia_beggar", label: "丐帮弟子", genre: "wuxia",
    hair: "#292524", torso: "#57534e", legs: "#44403c",
    accent: "#a8a29e", weapon: "staff", style: "rogue",
    skinVariant: "tan", clothPack: "burlap", metalPack: "iron", silhouette: "stocky",
    build: B(0.97, 1.12), hairStyle: "buzz", head: "bamboo_hat", coat: "vest",
  }),
  wuxia_storyteller: P({
    id: "wuxia_storyteller", label: "说书客", genre: "wuxia",
    hair: "#374151", torso: "#713f12", legs: "#292524",
    accent: "#fbbf24", weapon: "fan", style: "scholar",
    skinVariant: "tan", clothPack: "robe_crimson", metalPack: "bronze", silhouette: "robed",
    build: B(0.99, 1.0), hairStyle: "topknot", head: "bamboo_hat", coat: "robe",
  }),
  wuxia_physician: P({
    id: "wuxia_physician", label: "江湖郎中", genre: "wuxia",
    hair: "#1f2937", torso: "#ecfdf5", legs: "#d1fae5",
    accent: "#10b981", weapon: "none", style: "scholar",
    skinVariant: "fair", clothPack: "linen", metalPack: "verdigris", silhouette: "civilian",
    build: B(1.0, 0.95), hairStyle: "bun", head: "none", coat: "apron",
  }),
  // —— 古代 · 汉唐明古装 ——
  ancient_student: P({
    id: "ancient_student", label: "寒门书生", genre: "ancient",
    hair: "#111827", torso: "#dbeafe", legs: "#1e3a5f",
    accent: "#2563eb", weapon: "fan", style: "scholar",
    skinVariant: "pale", clothPack: "linen", metalPack: "bronze", silhouette: "lean",
    build: B(1.08, 0.82), tall: true, hairStyle: "topknot", head: "none", coat: "robe",
  }),
  ancient_clerk: P({
    id: "ancient_clerk", label: "衙门小吏", genre: "ancient",
    hair: "#1f2937", torso: "#1e3a5f", legs: "#0f172a",
    accent: "#f59e0b", weapon: "none", style: "scholar",
    skinVariant: "tan", clothPack: "wool", metalPack: "gold", silhouette: "civilian",
    build: B(0.96, 1.02), hairStyle: "short", head: "futou", coat: "sash",
  }),
  ancient_guard: P({
    id: "ancient_guard", label: "镖局趟子手", genre: "ancient",
    hair: "#1c1917", torso: "#78350f", legs: "#292524",
    accent: "#fcd34d", weapon: "blade", style: "warrior",
    skinVariant: "warm", clothPack: "armor_lacquer", metalPack: "bronze", silhouette: "stocky",
    build: B(1.12, 1.28), pauldrons: true, hairStyle: "buzz", head: "helm", coat: "armor",
  }),
  ancient_archer: P({
    id: "ancient_archer", label: "边军斥候", genre: "ancient",
    hair: "#292524", torso: "#365314", legs: "#1a2e05",
    accent: "#84cc16", weapon: "bow", style: "ranger",
    skinVariant: "tan", clothPack: "hemp", metalPack: "iron", silhouette: "lean",
    build: B(1.06, 0.88), hairStyle: "ponytail", head: "hood", coat: "cloak", hood: true,
  }),
  ancient_trader: P({
    id: "ancient_trader", label: "西市行商", genre: "ancient",
    hair: "#1f2937", torso: "#b45309", legs: "#451a03",
    accent: "#fbbf24", weapon: "none", style: "merchant",
    skinVariant: "tan", clothPack: "coat_tweed", metalPack: "gold", silhouette: "stocky",
    build: B(0.94, 1.22), hairStyle: "short", head: "bamboo_hat", coat: "vest",
  }),
  ancient_farmer: P({
    id: "ancient_farmer", label: "田舍农夫", genre: "ancient",
    hair: "#292524", torso: "#a3a3a3", legs: "#57534e",
    accent: "#78716c", weapon: "none", style: "merchant",
    skinVariant: "warm", clothPack: "burlap", metalPack: "rust", silhouette: "stocky",
    build: B(0.88, 1.18), hairStyle: "messy", head: "bamboo_hat", coat: "apron",
  }),
  ancient_porter: P({
    id: "ancient_porter", label: "脚夫挑夫", genre: "ancient",
    hair: "#1c1917", torso: "#78716c", legs: "#292524",
    accent: "#a8a29e", weapon: "staff", style: "ranger",
    skinVariant: "tan", clothPack: "hemp", metalPack: "iron", silhouette: "lean",
    build: B(1.14, 0.95), tall: true, hairStyle: "buzz", head: "bamboo_hat", coat: "vest",
  }),
  ancient_artisan: P({
    id: "ancient_artisan", label: "匠作铁匠", genre: "ancient",
    hair: "#44403c", torso: "#1c1917", legs: "#292524",
    accent: "#ea580c", weapon: "none", style: "warrior",
    skinVariant: "warm", clothPack: "leather", metalPack: "copper", silhouette: "stocky",
    build: B(0.92, 1.32), pauldrons: true, hairStyle: "short", head: "none", coat: "apron",
  }),
  // —— 科幻 · 机械/制服/特战/宇航 ——
  scifi_comms: P({
    id: "scifi_comms", label: "通讯官", genre: "scifi",
    hair: "#0ea5e9", torso: "#1e3a5f", legs: "#0f172a",
    accent: "#38bdf8", weapon: "scanner", style: "sci_fi",
    skinVariant: "pale", clothPack: "neon_mesh", metalPack: "neon", silhouette: "civilian",
    build: B(1.0, 0.95), glow: 0.25, hairStyle: "short", head: "visor", coat: "exosuit",
  }),
  scifi_engineer: P({
    id: "scifi_engineer", label: "维修工", genre: "scifi",
    hair: "#f97316", torso: "#44403c", legs: "#292524",
    accent: "#fb923c", weapon: "none", style: "sci_fi",
    skinVariant: "warm", clothPack: "tech", metalPack: "copper", silhouette: "stocky",
    build: B(1.0, 1.14), pauldrons: true, glow: 0.15, hairStyle: "none", head: "visor", coat: "exosuit",
  }),
  scifi_scout: P({
    id: "scifi_scout", label: "外勤侦察", genre: "scifi",
    hair: "#1e293b", torso: "#334155", legs: "#0f172a",
    accent: "#22d3ee", weapon: "rifle", style: "sci_fi",
    skinVariant: "tan", clothPack: "tech", metalPack: "chrome", silhouette: "lean",
    build: B(1.08, 0.92), tall: true, glow: 0.2, hairStyle: "buzz", head: "visor", coat: "vest",
  }),
  scifi_xeno: P({
    id: "scifi_xeno", label: "语言学家", genre: "scifi",
    hair: "#7c3aed", torso: "#312e81", legs: "#1e1b4b",
    accent: "#a78bfa", weapon: "scanner", style: "sci_fi",
    skinVariant: "pale", clothPack: "robe_indigo", metalPack: "spirit_silver", silhouette: "robed",
    build: B(1.02, 0.9), glow: 0.35, hairStyle: "none", head: "none", coat: "robe",
  }),
  // —— 玄幻 · 西游记 ——
  xuanhuan_outer: P({
    id: "xuanhuan_outer", label: "外门弟子", genre: "xuanhuan",
    hair: "#111827", torso: "#e0e7ff", legs: "#312e81",
    accent: "#818cf8", weapon: "sword", style: "mage",
    skinVariant: "pale", clothPack: "silk_jade", metalPack: "jade", silhouette: "robed",
    build: B(1.03, 0.95), cape: true, glow: 0.3, hairStyle: "long", head: "none", coat: "robe",
  }),
  xuanhuan_rogue: P({
    id: "xuanhuan_rogue", label: "散修", genre: "xuanhuan",
    hair: "#1f2937", torso: "#1e1b4b", legs: "#0f172a",
    accent: "#c084fc", weapon: "staff", style: "mage",
    skinVariant: "warm", clothPack: "robe_indigo", metalPack: "spirit_silver", silhouette: "cloaked",
    build: B(1.0, 1.0), hood: true, glow: 0.4, hairStyle: "long", head: "hood", coat: "cloak",
  }),
  xuanhuan_alchemist: P({
    id: "xuanhuan_alchemist", label: "炼丹学徒", genre: "xuanhuan",
    hair: "#374151", torso: "#14532d", legs: "#052e16",
    accent: "#4ade80", weapon: "none", style: "scholar",
    skinVariant: "tan", clothPack: "silk_jade", metalPack: "verdigris", silhouette: "civilian",
    build: B(0.97, 1.05), glow: 0.2, hairStyle: "bun", head: "none", coat: "apron",
  }),
  // —— 悬疑 · 福尔摩斯 ——
  mystery_detective: P({
    id: "mystery_detective", label: "私家侦探", genre: "mystery",
    hair: "#1f2937", torso: "#1c1917", legs: "#0c0a09",
    accent: "#a8a29e", weapon: "pistol", style: "detective",
    skinVariant: "tan", clothPack: "suit_charcoal", metalPack: "obsidian", silhouette: "cloaked",
    build: B(1.06, 0.98), tall: true, hairStyle: "short", head: "fedora", coat: "trench",
  }),
  mystery_reporter: P({
    id: "mystery_reporter", label: "记者", genre: "mystery",
    hair: "#78350f", torso: "#fef3c7", legs: "#44403c",
    accent: "#f59e0b", weapon: "none", style: "scholar",
    skinVariant: "fair", clothPack: "coat_tweed", metalPack: "bronze", silhouette: "civilian",
    build: B(0.98, 0.95), hairStyle: "bob", head: "fedora", coat: "trench",
  }),
  mystery_doctor: P({
    id: "mystery_doctor", label: "港口医师", genre: "mystery",
    hair: "#374151", torso: "#f8fafc", legs: "#cbd5e1",
    accent: "#0ea5e9", weapon: "none", style: "scholar",
    skinVariant: "pale", clothPack: "linen", metalPack: "chrome", silhouette: "civilian",
    build: B(1.0, 0.96), hairStyle: "short", head: "none", coat: "apron",
  }),
  // —— 当代 ——
  modern_civilian: P({
    id: "modern_civilian", label: "都市行人", genre: "modern",
    hair: "#374151", torso: "#64748b", legs: "#334155",
    accent: "#94a3b8", weapon: "none", style: "merchant",
    skinVariant: "tan", clothPack: "wool", metalPack: "chrome", silhouette: "civilian",
    build: B(1.0, 0.98), hairStyle: "short", head: "none", coat: "hoodie",
  }),
  modern_office: P({
    id: "modern_office", label: "白领职员", genre: "modern",
    hair: "#1f2937", torso: "#1e293b", legs: "#0f172a",
    accent: "#64748b", weapon: "none", style: "scholar",
    skinVariant: "fair", clothPack: "suit_charcoal", metalPack: "chrome", silhouette: "lean",
    build: B(1.02, 0.94), hairStyle: "short", head: "none", coat: "blazer",
  }),
  modern_courier: P({
    id: "modern_courier", label: "快递骑手", genre: "modern",
    hair: "#111827", torso: "#ea580c", legs: "#292524",
    accent: "#38bdf8", weapon: "none", style: "sci_fi",
    skinVariant: "warm", clothPack: "neon_mesh", metalPack: "chrome", silhouette: "lean",
    build: B(0.98, 1.0), hairStyle: "cap", head: "cap", coat: "vest",
  }),
  // —— NPC ——
  npc_swordsman: P({
    id: "npc_swordsman", label: "剑客", genre: "wuxia",
    hair: "#111827", torso: "#f1f5f9", legs: "#334155",
    accent: "#38bdf8", weapon: "sword", style: "warrior",
    skinVariant: "fair", clothPack: "silk", metalPack: "spirit_silver", silhouette: "armored",
    build: B(1.05, 1.08), pauldrons: true, hairStyle: "topknot", head: "helm", coat: "armor",
  }),
  npc_rogue_mask: P({
    id: "npc_rogue_mask", label: "面具客", genre: "wuxia",
    hair: "#18181b", torso: "#18181b", legs: "#09090b",
    accent: "#ef4444", weapon: "blade", style: "rogue",
    skinVariant: "pale", clothPack: "noir", metalPack: "blood_iron", silhouette: "cloaked",
    build: B(1.02, 1.0), hood: true, glow: 0.15, hairStyle: "none", head: "mask", coat: "cloak",
  }),
  npc_drunkard: P({
    id: "npc_drunkard", label: "酒客", genre: "wuxia",
    hair: "#292524", torso: "#9a3412", legs: "#44403c",
    accent: "#fbbf24", weapon: "staff", style: "rogue",
    skinVariant: "warm", clothPack: "burlap", metalPack: "bronze", silhouette: "stocky",
    build: B(0.9, 1.35), hairStyle: "messy", head: "bamboo_hat", coat: "vest",
  }),
  npc_boatman: P({
    id: "npc_boatman", label: "船工", genre: "wuxia",
    hair: "#1c1917", torso: "#0e7490", legs: "#164e63",
    accent: "#67e8f9", weapon: "spear", style: "merchant",
    skinVariant: "tan", clothPack: "hemp", metalPack: "rust", silhouette: "stocky",
    build: B(1.1, 1.2), hairStyle: "buzz", head: "bamboo_hat", coat: "vest",
  }),
  npc_storyteller: P({
    id: "npc_storyteller", label: "说书人", genre: "wuxia",
    hair: "#44403c", torso: "#7c2d12", legs: "#292524",
    accent: "#fdba74", weapon: "fan", style: "scholar",
    skinVariant: "tan", clothPack: "robe_crimson", metalPack: "bronze", silhouette: "robed",
    build: B(0.98, 1.02), hairStyle: "topknot", head: "bamboo_hat", coat: "robe",
  }),
  npc_default: P({
    id: "npc_default", label: "路人", genre: "wuxia",
    hair: "#374151", torso: "#64748b", legs: "#334155",
    accent: "#94a3b8", weapon: "none", style: "merchant",
    skinVariant: "tan", clothPack: "wool", metalPack: "iron", silhouette: "civilian",
    build: B(1.0, 1.0), hairStyle: "short", head: "none", coat: "sash",
  }),
};

export function figureIdForVariant(seedKey: string, _categoryKey: string, variantKey: string): string {
  return `${seedKey}_${variantKey}`.replace(/-/g, "_");
}

const FIGURE_ALIASES: Record<string, string> = {
  xuanhuan_rogue_cult: "xuanhuan_rogue",
};

export function resolveFigureId(id: string | undefined | null): string | null {
  if (!id) return null;
  if (FIGURE_PRESETS[id]) return id;
  const aliased = FIGURE_ALIASES[id];
  if (aliased && FIGURE_PRESETS[aliased]) return aliased;
  return null;
}

export function withSkinVariant(preset: FigurePreset, skin: RoleSkinId | string | undefined | null): FigurePreset {
  const id = (ROLE_SKIN_IDS as readonly string[]).includes(skin || "")
    ? (skin as RoleSkinId)
    : preset.skinVariant;
  if (id === preset.skinVariant && preset.skin === SKIN_HEX[id]) return preset;
  return {
    ...preset,
    skinVariant: id,
    skinPack: id,
    skin: SKIN_HEX[id],
  };
}

export function resolveFigure(agent: {
  appearance?: { figure?: string; skin?: string };
  avatar?: string;
  profession?: string;
  traits?: string[];
  name?: string;
}, genre?: string): FigurePreset {
  const resolved = resolveFigureId(agent.appearance?.figure);
  if (resolved) return withSkinVariant(FIGURE_PRESETS[resolved], agent.appearance?.skin);
  const p = (agent.profession || "").toLowerCase();
  if (p.includes("行商") || p.includes("商") || p.includes("贩") || p.includes("摊")) {
    return withSkinVariant(FIGURE_PRESETS.ancient_trader, agent.appearance?.skin);
  }
  if (p.includes("书生") || p.includes("学")) {
    return withSkinVariant(FIGURE_PRESETS.ancient_student, agent.appearance?.skin);
  }
  if (p.includes("镖") || p.includes("卫") || p.includes("兵")) {
    return withSkinVariant(FIGURE_PRESETS.ancient_guard, agent.appearance?.skin);
  }
  if (p.includes("吏") || p.includes("衙")) {
    return withSkinVariant(FIGURE_PRESETS.ancient_clerk, agent.appearance?.skin);
  }
  if (p.includes("农") || p.includes("田") || p.includes("农夫")) {
    return withSkinVariant(FIGURE_PRESETS.ancient_farmer, agent.appearance?.skin);
  }
  if (p.includes("脚夫") || p.includes("挑夫") || p.includes("力夫")) {
    return withSkinVariant(FIGURE_PRESETS.ancient_porter, agent.appearance?.skin);
  }
  if (p.includes("铁匠") || p.includes("匠")) {
    return withSkinVariant(FIGURE_PRESETS.ancient_artisan, agent.appearance?.skin);
  }
  if (p.includes("酒客") || p.includes("醉")) {
    return withSkinVariant(FIGURE_PRESETS.npc_drunkard, agent.appearance?.skin);
  }
  if (p.includes("船工")) {
    return withSkinVariant(FIGURE_PRESETS.npc_boatman, agent.appearance?.skin);
  }
  if (p.includes("杀手") || p.includes("堂") || p.includes("鬼")) {
    return withSkinVariant(FIGURE_PRESETS.npc_rogue_mask, agent.appearance?.skin);
  }
  if (p.includes("剑") || p.includes("庄") || p.includes("首座")) {
    return withSkinVariant(FIGURE_PRESETS.npc_swordsman, agent.appearance?.skin);
  }
  if (p.includes("丐") || p.includes("长老") || p.includes("醉")) {
    return withSkinVariant(FIGURE_PRESETS.npc_drunkard, agent.appearance?.skin);
  }
  if (p.includes("船") || p.includes("摆渡")) {
    return withSkinVariant(FIGURE_PRESETS.npc_boatman, agent.appearance?.skin);
  }
  if (p.includes("说书")) {
    return withSkinVariant(FIGURE_PRESETS.npc_storyteller, agent.appearance?.skin);
  }
  if (p.includes("医") || p.includes("郎中")) {
    const g = (genre || "wuxia") as SceneGenre;
    if (g === "mystery") return withSkinVariant(FIGURE_PRESETS.mystery_doctor, agent.appearance?.skin);
    if (g === "xuanhuan") return withSkinVariant(FIGURE_PRESETS.xuanhuan_alchemist, agent.appearance?.skin);
    return withSkinVariant(FIGURE_PRESETS.wuxia_physician, agent.appearance?.skin);
  }
  if (agent.traits?.includes("动物")) {
    return withSkinVariant({ ...FIGURE_PRESETS.npc_default, weapon: "none", style: "rogue" }, agent.appearance?.skin);
  }
  const g = (genre || "wuxia") as SceneGenre;
  const pool = presetsForGenre(g).filter((x) => !x.id.startsWith("npc_"));
  if (pool.length) {
    const seed = `${agent.name || ""}|${agent.profession || ""}`;
    let h = 0;
    for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
    return withSkinVariant(pool[h % pool.length], agent.appearance?.skin);
  }
  const byGenre: Partial<Record<SceneGenre, FigurePreset>> = {
    mystery: FIGURE_PRESETS.mystery_reporter,
    scifi: FIGURE_PRESETS.scifi_comms,
    xuanhuan: FIGURE_PRESETS.xuanhuan_alchemist,
    ancient: FIGURE_PRESETS.ancient_clerk,
    wuxia: FIGURE_PRESETS.npc_default,
    modern: FIGURE_PRESETS.modern_civilian,
  };
  return withSkinVariant(byGenre[g] || FIGURE_PRESETS.npc_default, agent.appearance?.skin);
}

export function getFigure(id: string, skin?: RoleSkinId | string | null): FigurePreset {
  const resolved = resolveFigureId(id);
  return withSkinVariant((resolved && FIGURE_PRESETS[resolved]) || FIGURE_PRESETS.npc_default, skin);
}

export function presetsForGenre(genre: SceneGenre): FigurePreset[] {
  return Object.values(FIGURE_PRESETS).filter((p) => p.genre === genre);
}
