/** Map loading with genre fallback and procedural world when JSON is missing (v1.4 MAP-002). */

export type MapLoc = { name: string; x: number; y: number; building?: boolean; enterable?: boolean };
export type MapFac = { name: string; x: number; y: number; r: number; color: [number, number, number]; terrain?: string };
export type MapData = {
  width: number; height: number; name: string; genre?: string;
  locations: MapLoc[]; factions: MapFac[];
  terrain?: {
    seed?: number;
    maxHeight?: number;
    waterLevel?: number;
    worldScale?: number;
    vegetation?: string;
    shape?: string;
  };
};

const GENRE_FALLBACK: Record<string, string> = {
  // Keep custom → modern only; all 9 built-in civs have dedicated maps now.
  custom: "modern",
};

const PALETTE: [number, number, number][] = [
  [210, 110, 110], [110, 170, 210], [200, 180, 90], [140, 200, 140], [180, 140, 210],
];

function resolveGenreChain(genre: string): string[] {
  const chain = [genre];
  let cur = genre;
  while (GENRE_FALLBACK[cur] && !chain.includes(GENRE_FALLBACK[cur])) {
    cur = GENRE_FALLBACK[cur];
    chain.push(cur);
  }
  if (!chain.includes("modern")) chain.push("modern");
  return chain;
}

export function proceduralFallbackMap(
  genre: string,
  worldLocations: { name: string }[] = [],
): MapData {
  const width = 960;
  const height = 540;
  const names = worldLocations.length
    ? worldLocations.map((l) => l.name)
    : ["起始之地", "聚落", "远郊"];
  const locations: MapLoc[] = names.map((name, i) => ({
    name,
    x: 120 + (i % 3) * 320,
    y: 100 + Math.floor(i / 3) * 180,
    building: true,
    enterable: true,
  }));
  const factions: MapFac[] = locations.map((l, i) => ({
    name: l.name,
    x: l.x,
    y: l.y,
    r: 72 + (i % 3) * 8,
    color: PALETTE[i % PALETTE.length],
    terrain: i % 2 === 0 ? "valley" : "hill",
  }));
  return {
    width,
    height,
    name: `回退世界 · ${genre}`,
    genre,
    locations,
    factions,
    terrain: { seed: genre.length * 997, maxHeight: 18, waterLevel: 0.32 },
    buildings: locations.map((l, i) => ({
      name: l.name,
      x: l.x - 40,
      y: l.y - 30,
      w: 80,
      h: 60,
      enterable: true,
      type: i % 3 === 0 ? "commercial" as const : "residential" as const,
    })),
    roads: locations.slice(1).map((l, i) => ({
      from: [locations[i].x, locations[i].y] as [number, number],
      to: [l.x, l.y] as [number, number],
      kind: "paved" as const,
    })),
    trees: locations.flatMap((l, i) => ([
      { x: l.x + 30, y: l.y + 20, climbable: i % 2 === 0 },
      { x: l.x - 25, y: l.y - 15, climbable: false },
    ])),
  } as MapData & {
    buildings: Array<{ name: string; x: number; y: number; w: number; h: number; enterable?: boolean; type?: string }>;
    roads: Array<{ from: [number, number]; to: [number, number]; kind?: "paved" }>;
    trees: Array<{ x: number; y: number; climbable?: boolean }>;
  };
}

/** Bump when map JSON shape/content changes so browsers never serve a stale layout. */
export const MAP_JSON_REV = "roads8";

async function fetchMapJson(genre: string): Promise<MapData | null> {
  try {
    const r = await fetch(`/maps/${genre}.json?v=${MAP_JSON_REV}&t=${Date.now()}`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as MapData;
  } catch {
    return null;
  }
}

/** Load map JSON with genre chain fallback; procedural map if all fetches fail. */
export async function loadWorldMap(
  genre: string,
  worldLocations: { name: string }[] = [],
): Promise<MapData> {
  for (const g of resolveGenreChain(genre)) {
    const data = await fetchMapJson(g);
    if (data) {
      return { ...data, genre: data.genre || genre };
    }
  }
  return proceduralFallbackMap(genre, worldLocations);
}
