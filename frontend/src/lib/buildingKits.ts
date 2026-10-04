/**
 * Per-civilization building model kits (authored Eastern / modern / sci-fi GLBs).
 * Paths under /models/buildings/{genre}/
 */
export type BuildingRole =
  | "commercial" | "residential" | "temple" | "dock" | "palace"
  | "tower" | "shop" | "office" | "ship_port" | "stall" | "farmhouse";

export type KitModel = {
  url: string;
  scale?: number;
  y?: number;
  tint?: string;
  emissive?: string;
  emissiveIntensity?: number;
};

const CACHE = "hy3d8";
/**
 * Only route to /hy3d/ when the Hunyuan GLB is volumetric + on disk.
 * Flat relief stalls/lanterns/banners (depth ratio < ~0.2) are excluded —
 * those render as grey ribbons; use procedural StreetStall / StreetProp instead.
 */
const HY3D_BUILDINGS = new Set([
  "landmark_tavern.glb",
  "landmark_palace.glb",
  "landmark_temple.glb",
]);
/** Stalls: all current hy3d outputs are flat plaques — keep empty until textured volumetric meshes exist. */
const HY3D_STALLS = new Set<string>([]);
const HY3D_PROPS = new Set<string>([
  "wine_jar.glb",
  "stone_lion.glb",
  "well.glb",
]);

/** Prefer Hunyuan3D …/hy3d/ when ready; otherwise authored kit path. */
const b = (genre: string, file: string) =>
  genre === "ancient" && HY3D_BUILDINGS.has(file)
    ? `/models/buildings/${genre}/hy3d/${file}?v=${CACHE}`
    : `/models/buildings/${genre}/${file}?v=${CACHE}`;
const p = (genre: string, file: string) =>
  genre === "ancient" && HY3D_PROPS.has(file)
    ? `/models/props/${genre}/hy3d/${file}?v=${CACHE}`
    : `/models/props/${genre}/${file}?v=${CACHE}`;
const s = (genre: string, file: string) =>
  HY3D_STALLS.has(file)
    ? `/models/stalls/ancient/hy3d/${file}?v=${CACHE}`
    : "";

function variants(genre: string, files: string[], extra: Partial<KitModel> = {}): KitModel[] {
  return files.map((f) => ({ url: b(genre, f), scale: 1, ...extra }));
}

export type GenreKit = Partial<Record<BuildingRole, KitModel[]>>;

/** Explicit hero landmarks — Hunyuan3D. */
const ANCIENT_LANDMARKS: Record<string, KitModel> = {
  landmark_tavern: { url: b("ancient", "landmark_tavern.glb"), scale: 1.15 },
  landmark_palace: { url: b("ancient", "landmark_palace.glb"), scale: 1.2 },
  landmark_temple: { url: b("ancient", "landmark_temple.glb"), scale: 1.12 },
};

const ANCIENT_KIT: GenreKit = {
  palace: variants("ancient", ["landmark_palace.glb"], { scale: 1.0 }),
  temple: variants("ancient", ["landmark_temple.glb"]),
  commercial: variants("ancient", ["commercial_a.glb", "landmark_tavern.glb"]),
  shop: variants("ancient", ["shop.glb"]),
  residential: variants("ancient", [
    "residential_a.glb", "residential_b.glb", "residential_c.glb", "residential_d.glb",
  ]),
  farmhouse: variants("ancient", ["farmhouse_a.glb", "farmhouse_b.glb"]),
  tower: variants("ancient", ["tower_a.glb"]),
  dock: variants("ancient", ["dock.glb"], { scale: 1.1 }),
  office: variants("ancient", ["landmark_palace.glb"], { scale: 0.75 }),
  ship_port: variants("ancient", ["dock.glb"], { scale: 1.2 }),
};

/** Named stall → Hunyuan filename (resolved only when hy3d file is ready). */
const STALL_FILES: Record<string, string> = {
  果摊: "stall_fruit.glb",
  布摊: "stall_cloth.glb",
  书摊: "stall_book.glb",
  胡饼: "stall_bing.glb",
  酒摊: "stall_wine.glb",
  香料: "stall_spice.glb",
};

/** @deprecated use resolveStallModel — kept for preload enumeration */
export const ANCIENT_STALLS: Record<string, KitModel> = {};

const WUXIA_KIT: GenreKit = {
  palace: variants("wuxia", ["palace.glb"]),
  temple: variants("wuxia", ["temple_b.glb", "temple_a.glb", "temple_c.glb"]),
  commercial: variants("wuxia", ["commercial_a.glb", "commercial_b.glb", "shop.glb"]),
  shop: variants("wuxia", ["shop.glb"]),
  residential: variants("wuxia", ["residential_a.glb", "residential_b.glb"]),
  farmhouse: variants("ancient", ["farmhouse_a.glb", "farmhouse_b.glb"]),
  tower: variants("wuxia", ["tower_a.glb"]),
  dock: variants("wuxia", ["dock.glb"], { scale: 1.1 }),
  office: variants("wuxia", ["office.glb"]),
  ship_port: variants("wuxia", ["dock.glb"], { scale: 1.2 }),
};

const XUANHUAN_KIT: GenreKit = {
  palace: variants("xuanhuan", ["palace.glb"], { emissive: "#7c3aed", emissiveIntensity: 0.2 }),
  temple: variants("xuanhuan", ["temple_a.glb", "temple_c.glb", "temple_b.glb"], {
    emissive: "#a78bfa", emissiveIntensity: 0.28,
  }),
  commercial: variants("xuanhuan", ["commercial_a.glb", "commercial_b.glb"], {
    emissive: "#6d28d9", emissiveIntensity: 0.12,
  }),
  shop: variants("xuanhuan", ["shop.glb"], { emissive: "#8b5cf6", emissiveIntensity: 0.15 }),
  residential: variants("xuanhuan", ["residential_a.glb", "residential_b.glb"]),
  farmhouse: variants("ancient", ["farmhouse_c.glb", "farmhouse_d.glb"]),
  tower: variants("xuanhuan", ["tower_a.glb"], { emissive: "#c4b5fd", emissiveIntensity: 0.18 }),
  dock: variants("xuanhuan", ["dock.glb"], { scale: 1.1 }),
  office: variants("xuanhuan", ["office.glb"]),
  ship_port: variants("xuanhuan", ["dock.glb"], { scale: 1.2 }),
};

const MODERN_KIT: GenreKit = {
  tower: variants("modern", ["tower_a.glb", "tower_b.glb", "tower_c.glb"]),
  office: variants("modern", ["office_a.glb", "office_b.glb"]),
  commercial: variants("modern", ["commercial_a.glb", "commercial_b.glb", "commercial_c.glb"]),
  shop: variants("modern", ["shop_a.glb", "shop_b.glb"]),
  residential: variants("modern", ["residential_a.glb", "residential_b.glb", "residential_c.glb"]),
  palace: variants("modern", ["palace.glb"]),
  dock: variants("modern", ["dock.glb"], { scale: 1.15 }),
  temple: variants("modern", ["palace.glb"]),
  ship_port: variants("modern", ["dock.glb"], { scale: 1.2 }),
};

const MYSTERY_KIT: GenreKit = {
  residential: variants("mystery", ["residential_a.glb", "residential_b.glb", "residential_c.glb"], {
    tint: "#d4cfc8",
  }),
  commercial: variants("mystery", ["commercial_a.glb", "commercial_b.glb", "commercial_c.glb"]),
  shop: variants("mystery", ["shop_a.glb", "shop_b.glb"], { emissive: "#9f1239", emissiveIntensity: 0.15 }),
  palace: variants("mystery", ["palace.glb"]),
  tower: variants("mystery", ["tower_a.glb", "tower_b.glb", "tower_c.glb"]),
  office: variants("mystery", ["office_a.glb", "office_b.glb"]),
  dock: variants("mystery", ["dock.glb"], { scale: 1.15 }),
  temple: variants("mystery", ["palace.glb"]),
  ship_port: variants("mystery", ["dock.glb"], { scale: 1.2 }),
};

const SCIFI_KIT: GenreKit = {
  tower: variants("scifi", ["tower_a.glb", "tower_b.glb", "tower_c.glb"], {
    emissive: "#22d3ee", emissiveIntensity: 0.28,
  }),
  office: variants("scifi", ["office_a.glb", "office_b.glb"], {
    emissive: "#0891b2", emissiveIntensity: 0.22,
  }),
  commercial: variants("scifi", ["commercial_a.glb", "commercial_b.glb", "commercial_c.glb"], {
    emissive: "#06b6d4", emissiveIntensity: 0.2,
  }),
  residential: variants("scifi", ["residential_a.glb", "residential_b.glb", "residential_c.glb"], {
    emissive: "#164e63", emissiveIntensity: 0.12,
  }),
  palace: variants("scifi", ["palace.glb"], { emissive: "#22d3ee", emissiveIntensity: 0.3 }),
  shop: variants("scifi", ["shop_a.glb", "shop_b.glb"], { emissive: "#67e8f9", emissiveIntensity: 0.3 }),
  ship_port: variants("scifi", ["ship_port_a.glb", "ship_port_b.glb"], { scale: 0.9, y: 0.05 }),
  dock: variants("scifi", ["dock.glb"], { scale: 1.15 }),
  temple: variants("scifi", ["palace.glb"]),
};

const ENTERPRISE_KIT: GenreKit = {
  tower: variants("enterprise", ["tower_a.glb", "tower_b.glb", "tower_c.glb"], {
    tint: "#ccfbf1",
  }),
  office: variants("enterprise", ["office_a.glb", "office_b.glb"], {
    tint: "#99f6e4",
  }),
  commercial: variants("enterprise", ["commercial_a.glb", "commercial_b.glb", "commercial_c.glb"]),
  shop: variants("enterprise", ["shop_a.glb", "shop_b.glb"]),
  residential: variants("enterprise", ["residential_a.glb", "residential_b.glb", "residential_c.glb"]),
  palace: variants("enterprise", ["palace.glb"], { tint: "#5eead4" }),
  dock: variants("enterprise", ["dock.glb"], { scale: 1.1 }),
  temple: variants("enterprise", ["palace.glb"]),
  ship_port: variants("enterprise", ["dock.glb"], { scale: 1.15 }),
};

const SECURITIES_KIT: GenreKit = {
  tower: variants("securities", ["tower_a.glb", "tower_b.glb", "tower_c.glb"], {
    tint: "#cbd5e1", emissive: "#d4a017", emissiveIntensity: 0.12,
  }),
  office: variants("securities", ["office_a.glb", "office_b.glb"], {
    tint: "#94a3b8",
  }),
  commercial: variants("securities", ["commercial_a.glb", "commercial_b.glb", "commercial_c.glb"]),
  shop: variants("securities", ["shop_a.glb", "shop_b.glb"], {
    emissive: "#ca8a04", emissiveIntensity: 0.1,
  }),
  residential: variants("securities", ["residential_a.glb", "residential_b.glb", "residential_c.glb"]),
  palace: variants("securities", ["palace.glb"], {
    tint: "#e2e8f0", emissive: "#ca8a04", emissiveIntensity: 0.15,
  }),
  dock: variants("securities", ["dock.glb"], { scale: 1.1 }),
  temple: variants("securities", ["palace.glb"]),
  ship_port: variants("securities", ["dock.glb"], { scale: 1.15 }),
};

const MILITARY_KIT: GenreKit = {
  tower: variants("military", ["tower_a.glb", "tower_b.glb", "tower_c.glb"], {
    tint: "#a3a189",
  }),
  office: variants("military", ["office_a.glb", "office_b.glb"], {
    tint: "#8b8a6e",
  }),
  commercial: variants("military", ["commercial_a.glb", "commercial_b.glb", "commercial_c.glb"], {
    tint: "#78765a",
  }),
  shop: variants("military", ["shop_a.glb", "shop_b.glb"]),
  residential: variants("military", ["residential_a.glb", "residential_b.glb", "residential_c.glb"]),
  palace: variants("military", ["palace.glb"], { tint: "#6b705c" }),
  dock: variants("military", ["dock.glb"], { scale: 1.1 }),
  temple: variants("military", ["palace.glb"]),
  ship_port: variants("military", ["dock.glb"], { scale: 1.15 }),
};

export const BUILDING_KITS: Record<string, GenreKit> = {
  ancient: ANCIENT_KIT,
  wuxia: WUXIA_KIT,
  xuanhuan: XUANHUAN_KIT,
  modern: MODERN_KIT,
  mystery: MYSTERY_KIT,
  scifi: SCIFI_KIT,
  enterprise: ENTERPRISE_KIT,
  securities: SECURITIES_KIT,
  military: MILITARY_KIT,
};

export type PropKind =
  | "lantern" | "banner" | "table" | "stool" | "well"
  | "stone_lion" | "crate" | "wine_jar" | "bench" | "flower_pot" | "cart";

const PROP_FILES: Partial<Record<PropKind, string>> = {
  lantern: "lantern.glb",
  banner: "banner.glb",
  well: "well.glb",
  stone_lion: "stone_lion.glb",
  wine_jar: "wine_jar.glb",
  crate: "wine_jar.glb",
};

export const ANCIENT_PROPS: Partial<Record<PropKind, KitModel>> = {};

export function resolveStallModel(genre: string, stallKind?: string | null): KitModel | null {
  if (!stallKind) return null;
  if (genre !== "ancient" && genre !== "wuxia" && genre !== "xuanhuan") return null;
  const file = STALL_FILES[stallKind];
  if (!file || !HY3D_STALLS.has(file)) return null;
  return { url: `/models/stalls/ancient/hy3d/${file}?v=${CACHE}`, scale: 1 };
}

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

/** Resolve hero landmark GLB from explicit modelKey or known landmark names. */
function withHy3dBuildingUrl(model: KitModel): KitModel {
  const m = model.url.match(/\/models\/buildings\/ancient\/(?:hy3d\/)?([^?]+)/);
  if (!m) return model;
  const file = m[1];
  if (!HY3D_BUILDINGS.has(file)) return model;
  const url = `/models/buildings/ancient/hy3d/${file}?v=${CACHE}`;
  return url === model.url ? model : { ...model, url };
}

export function resolveLandmarkModel(
  genre: string,
  name: string,
  modelKey?: string | null,
): KitModel | null {
  if (genre !== "ancient" && genre !== "wuxia" && genre !== "xuanhuan") return null;
  let hit: KitModel | null = null;
  if (modelKey && ANCIENT_LANDMARKS[modelKey]) hit = ANCIENT_LANDMARKS[modelKey];
  else if (/醉仙楼|西市酒肆$/.test(name) || name === "长安·西市酒肆") hit = ANCIENT_LANDMARKS.landmark_tavern;
  else if (/紫宸殿/.test(name)) hit = ANCIENT_LANDMARKS.landmark_palace;
  else if (/终南.*古观$|终南山·古观$/.test(name) || name === "终南山·古观") hit = ANCIENT_LANDMARKS.landmark_temple;
  return hit ? withHy3dBuildingUrl(hit) : null;
}

export function resolveBuildingModel(
  genre: string,
  role: BuildingRole,
  name: string,
  opts?: { modelKey?: string | null; landmark?: string | null; zone?: string | null },
): KitModel | null {
  const landmark = resolveLandmarkModel(genre, name, opts?.modelKey);
  if (landmark && (opts?.landmark === "primary" || opts?.modelKey || /醉仙|紫宸|古观/.test(name))) {
    return landmark;
  }
  const kit = BUILDING_KITS[genre] || BUILDING_KITS.ancient;
  let effective: BuildingRole = role;
  if (
    (role === "residential" || !role) &&
    (opts?.zone === "rural" || /田舍|茅屋|农家|草屋|田野/.test(name))
  ) {
    effective = "farmhouse";
  }
  const list = kit[effective] || kit.residential || kit.commercial;
  if (!list || !list.length) return null;
  return withHy3dBuildingUrl(list[hashStr(name) % list.length]);
}

export function resolvePropModel(genre: string, kind: string): KitModel | null {
  if (genre !== "ancient" && genre !== "wuxia" && genre !== "xuanhuan") return null;
  const file = PROP_FILES[kind as PropKind];
  if (!file || !HY3D_PROPS.has(file)) return null;
  return { url: `/models/props/ancient/hy3d/${file}?v=${CACHE}`, scale: kind === "crate" ? 0.8 : 1 };
}

/** Runtime register newly-generated Hunyuan GLBs (from /models/.../hy3d/manifest). */
export function markHy3dReady(kind: "building" | "stall" | "prop", files: string[]) {
  const set = kind === "building" ? HY3D_BUILDINGS : kind === "stall" ? HY3D_STALLS : HY3D_PROPS;
  for (const f of files) set.add(f);
}

export function genreKitUrls(genre: string): string[] {
  const kit = BUILDING_KITS[genre];
  if (!kit) return [];
  const urls = new Set<string>();
  for (const arr of Object.values(kit)) {
    for (const m of arr || []) urls.add(m.url);
  }
  if (genre === "ancient" || genre === "wuxia" || genre === "xuanhuan") {
    for (const m of Object.values(ANCIENT_LANDMARKS)) urls.add(m.url);
    for (const file of HY3D_STALLS) urls.add(`/models/stalls/ancient/hy3d/${file}?v=${CACHE}`);
    for (const file of HY3D_PROPS) urls.add(`/models/props/ancient/hy3d/${file}?v=${CACHE}`);
  }
  return [...urls];
}
