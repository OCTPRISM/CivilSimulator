/**
 * 九州 wardrobe — hy3d prop/clothing meshes.
 * Nothing is auto-attached; UI checkboxes / outfit radio equip items onto the figure.
 *
 * Socket space: hy3d body feet at y=0, standing height ≈ 1.9–2.1.
 */
export type WardrobeKind = "prop" | "clothing";

/** How to seat the mesh after unit-fit. */
export type PropAlign = "center" | "bottom" | "grip";

export type RolePropAttach = {
  slug: string;
  kind: WardrobeKind;
  label: string;
  /** Local offset relative to character root (meters). */
  position: [number, number, number];
  rotation?: [number, number, number];
  /** Extra uniform scale after fitSize normalization. */
  scale?: number;
  /** Longest-axis target size after fit (meters). */
  fitSize?: number;
  align?: PropAlign;
};

const PROP_BASE = "/models/characters/civilizations/ancient/props";
const PROP_CACHE = "hyprop4";

export function ancientPropUrl(slug: string): string {
  return `${PROP_BASE}/${slug}/prop.glb?v=${PROP_CACHE}`;
}

/**
 * Landmarks (feet y=0): hip≈0.95 · waist≈1.05 · hand≈0.85 · shoulder≈1.45 · head≈1.9
 * Weapons hang at hip; flags plant at ground; pouches at belt.
 */
export const ANCIENT_WARDROBE: RolePropAttach[] = [
  // —— clothing (torso overlays) ——
  {
    slug: "青衫", kind: "clothing", label: "青衫",
    position: [0, 1.0, 0.02], fitSize: 1.55, align: "center", scale: 1,
  },
  {
    slug: "皮护腕", kind: "clothing", label: "皮护腕",
    position: [0.38, 0.95, 0.06], rotation: [0.1, 0.2, 0.35], fitSize: 0.28, align: "center", scale: 1,
  },
  {
    slug: "皮围裙", kind: "clothing", label: "皮围裙",
    position: [0, 0.85, 0.1], fitSize: 0.95, align: "center", scale: 1,
  },
  {
    slug: "短褐背心", kind: "clothing", label: "短褐背心",
    position: [0, 1.15, 0.03], fitSize: 0.85, align: "center", scale: 1,
  },
  {
    slug: "麻短褐", kind: "clothing", label: "麻短褐",
    position: [0, 1.0, 0.02], fitSize: 1.35, align: "center", scale: 1,
  },
  // —— hand / belt props ——
  {
    slug: "笔墨纸砚", kind: "prop", label: "笔墨纸砚",
    // left hand carry
    position: [-0.32, 0.82, 0.12], rotation: [0.15, 0.5, 0.05], fitSize: 0.32, align: "center", scale: 1,
  },
  {
    slug: "案卷袋", kind: "prop", label: "案卷袋",
    // left hip satchel
    position: [-0.28, 0.92, 0.08], rotation: [0.1, 0.9, 0.15], fitSize: 0.38, align: "grip", scale: 1,
  },
  {
    slug: "县衙腰牌", kind: "prop", label: "县衙腰牌",
    // right belt plaque hanging
    position: [0.18, 0.98, 0.14], rotation: [0.15, 0.1, 0.05], fitSize: 0.16, align: "grip", scale: 1,
  },
  {
    slug: "朴刀", kind: "prop", label: "朴刀",
    // right hip, blade down along leg
    position: [0.3, 0.98, -0.02], rotation: [0.05, 0.15, -1.35], fitSize: 1.05, align: "grip", scale: 1,
  },
  {
    slug: "铁胎弓", kind: "prop", label: "铁胎弓",
    // left back / shoulder unstrung bow
    position: [-0.22, 1.2, -0.12], rotation: [0.2, 0.9, 0.55], fitSize: 0.95, align: "center", scale: 1,
  },
  {
    slug: "狼牙箭_12", kind: "prop", label: "狼牙箭",
    // right back quiver
    position: [0.22, 1.15, -0.14], rotation: [0.25, -0.35, 0.1], fitSize: 0.55, align: "grip", scale: 1,
  },
  {
    slug: "袖中账", kind: "prop", label: "袖中账",
    // tucked at right sleeve / chest
    position: [0.22, 1.15, 0.14], rotation: [0.5, 0.3, 0.1], fitSize: 0.14, align: "center", scale: 1,
  },
  {
    slug: "通行路引", kind: "prop", label: "通行路引",
    // left hand scroll
    position: [-0.3, 0.88, 0.1], rotation: [0.2, 0.6, 0.1], fitSize: 0.28, align: "center", scale: 1,
  },
  {
    slug: "钱袋", kind: "prop", label: "钱袋",
    // belt pouch front-right
    position: [0.16, 0.92, 0.12], rotation: [0.1, 0.2, 0.15], fitSize: 0.18, align: "grip", scale: 1,
  },
  {
    slug: "线装书", kind: "prop", label: "线装书",
    // left hand book
    position: [-0.28, 0.9, 0.1], rotation: [0.35, -0.2, 0.1], fitSize: 0.22, align: "center", scale: 1,
  },
  {
    slug: "镖旗", kind: "prop", label: "镖旗",
    // planted at left foot, pole vertical
    position: [-0.42, 0.02, -0.05], rotation: [0.05, 0.35, 0.02], fitSize: 1.55, align: "bottom", scale: 1,
  },
];

/** Outfit styles shown as radio (服装风格) — not skin tone. */
export type OutfitStyleId = "default" | string;

export const OUTFIT_STYLE_OPTIONS: { id: OutfitStyleId; label: string; slug?: string }[] = [
  { id: "default", label: "本职装束" },
  { id: "青衫", label: "青衫", slug: "青衫" },
  { id: "麻短褐", label: "麻短褐", slug: "麻短褐" },
  { id: "短褐背心", label: "短褐背心", slug: "短褐背心" },
  { id: "皮围裙", label: "皮围裙", slug: "皮围裙" },
  { id: "皮护腕", label: "皮护腕", slug: "皮护腕" },
];

const BY_SLUG = new Map(ANCIENT_WARDROBE.map((a) => [a.slug, a]));

export function wardrobeItem(slug: string): RolePropAttach | undefined {
  return BY_SLUG.get(slug);
}

export function wardrobeByKind(kind: WardrobeKind): RolePropAttach[] {
  return ANCIENT_WARDROBE.filter((a) => a.kind === kind);
}

/** Suggested prop slugs for a role (shown first) — never auto-equipped. */
export const ANCIENT_ROLE_SUGGESTED: Record<string, string[]> = {
  ancient_student: ["笔墨纸砚"],
  ancient_clerk: ["案卷袋", "县衙腰牌"],
  ancient_guard: ["朴刀"],
  ancient_archer: ["铁胎弓", "狼牙箭_12"],
  ancient_trader: ["袖中账", "通行路引", "钱袋"],
  ancient_farmer: ["钱袋", "线装书"],
  ancient_porter: ["镖旗", "钱袋"],
  ancient_artisan: ["朴刀", "钱袋"],
};

/** Suggested clothing style id for a role (radio default = 本职装束). */
export const ANCIENT_ROLE_OUTFIT_STYLE: Record<string, OutfitStyleId> = {
  ancient_student: "default",
  ancient_clerk: "default",
  ancient_guard: "default",
  ancient_archer: "default",
  ancient_trader: "default",
  ancient_farmer: "default",
  ancient_porter: "default",
  ancient_artisan: "default",
};

/** @deprecated */
export const ANCIENT_ROLE_PROPS: Record<string, RolePropAttach[]> = Object.fromEntries(
  Object.entries(ANCIENT_ROLE_SUGGESTED).map(([role, slugs]) => [
    role,
    slugs.map((s) => BY_SLUG.get(s)).filter((x): x is RolePropAttach => !!x),
  ]),
);

export function propsForAncientRole(roleId: string): RolePropAttach[] {
  return ANCIENT_ROLE_PROPS[roleId] || [];
}

export function suggestedSlugsForRole(roleId: string): string[] {
  return ANCIENT_ROLE_SUGGESTED[roleId] || [];
}

export function attachesForSlugs(slugs: string[]): RolePropAttach[] {
  const out: RolePropAttach[] = [];
  const seen = new Set<string>();
  for (const s of slugs) {
    if (seen.has(s)) continue;
    const a = BY_SLUG.get(s);
    if (a) {
      seen.add(s);
      out.push(a);
    }
  }
  return out;
}

/**
 * Equipped list is props only.
 * Clothing styles swap the whole body mesh — never layered as overlays.
 */
export function mergeEquipped(_outfitStyle: OutfitStyleId, propSlugs: string[]): string[] {
  return propSlugs.filter((s) => BY_SLUG.get(s)?.kind === "prop");
}

/** Full-garment styles that require a dedicated painted body (mesh swap). */
export const OUTFIT_BODY_STYLES = ["青衫", "麻短褐", "短褐背心", "皮围裙", "皮护腕"] as const;

let _propsReady: Set<string> | null = null;
let _propsReadyLoaded = false;
let _propsReadyFetch: Promise<string[]> | null = null;

export function markAncientPropsReady(slugs: string[]) {
  _propsReady = new Set(slugs.filter(Boolean));
  _propsReadyLoaded = true;
}

export function isAncientPropReady(slug: string): boolean {
  if (!_propsReadyLoaded) return true;
  return _propsReady?.has(slug) ?? false;
}

export function ancientPropsReadyLoaded(): boolean {
  return _propsReadyLoaded;
}

export function ensureAncientPropsReadyLoaded(): Promise<string[]> {
  if (!_propsReadyFetch) {
    _propsReadyFetch = fetch(
      `/models/characters/civilizations/ancient/hy3d_props_ready.json?t=${Date.now()}`,
      { cache: "no-store" },
    )
      .then(async (r) => {
        if (!r.ok) return [] as string[];
        const nd = await r.json();
        const painted: string[] = Array.isArray(nd?.painted)
          ? nd.painted
          : Array.isArray(nd?.props)
            ? nd.props
            : [];
        markAncientPropsReady(painted);
        return painted;
      })
      .catch(() => [] as string[]);
  }
  return _propsReadyFetch;
}
