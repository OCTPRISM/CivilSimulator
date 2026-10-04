/**
 * Runtime building footprints for walk collision (player + street NPCs).
 * Matches DetailedBuilding: map AABB center → world XZ, yaw = b.rot.
 */

export type ColliderBuilding = {
  x: number;
  y: number;
  w: number;
  h: number;
  rot?: number;
  type?: string;
  landmark?: string;
  name?: string;
};

export type CollisionMap = {
  width: number;
  height: number;
  buildings?: ColliderBuilding[];
};

type WorldBox = {
  cx: number;
  cz: number;
  hw: number;
  hd: number;
  cos: number;
  sin: number;
  /** Walkable porch depth on local +Z (street front) */
  frontGap: number;
};

function buildBoxes(map: CollisionMap, scale: number): WorldBox[] {
  const out: WorldBox[] = [];
  for (const b of map.buildings || []) {
    if (b.type === "dock") continue;
    const w = Math.max(2, b.w || 8);
    const h = Math.max(2, b.h || 8);
    const cx = (b.x + w * 0.5 - map.width / 2) * scale;
    const cz = (b.y + h * 0.5 - map.height / 2) * scale;
    // Slightly inset so curb/stall edges aren't overly sticky
    const hw = (w * scale * 0.5) * 0.92;
    const hd = (h * scale * 0.5) * 0.92;
    const rot = b.rot ?? 0;
    // Primary landmarks: shrink front (+Z) half so the street approach stays walkable
    const frontGap =
      b.landmark === "primary" || /醉仙|紫宸|古观/.test(b.name || "")
        ? Math.min(hd * 0.42, 2.4)
        : 0;
    out.push({
      cx, cz, hw, hd,
      cos: Math.cos(rot),
      sin: Math.sin(rot),
      frontGap,
    });
  }
  return out;
}

function overlaps(box: WorldBox, x: number, z: number, r: number): boolean {
  const dx = x - box.cx;
  const dz = z - box.cz;
  // World → local (inverse of Three.js Y-yaw)
  const lx = dx * box.cos - dz * box.sin;
  const lz = dx * box.sin + dz * box.cos;
  // Hollow front porch: allow walk-up on +Z face of landmarks
  const hdFront = box.frontGap > 0 && lz > 0 ? Math.max(0.2, box.hd - box.frontGap) : box.hd;
  const ax = Math.abs(lx) - box.hw;
  const az = Math.abs(lz) - hdFront;
  if (ax <= 0 && az <= 0) return true;
  if (ax > 0 && az > 0) return ax * ax + az * az < r * r;
  if (ax > 0) return ax < r;
  return az < r;
}

/** Resolve a world XZ move against building footprints (slide on axes). */
export function resolveBuildingMove(
  map: CollisionMap,
  scale: number,
  x: number,
  z: number,
  nx: number,
  nz: number,
  radius = 0.38,
): [number, number] {
  const boxes = buildBoxes(map, scale);
  if (!boxes.length) return [nx, nz];

  const blocked = (px: number, pz: number) =>
    boxes.some((b) => overlaps(b, px, pz, radius));

  if (!blocked(nx, nz)) return [nx, nz];
  // Axis slide
  if (!blocked(nx, z)) return [nx, z];
  if (!blocked(x, nz)) return [x, nz];
  return [x, z];
}
