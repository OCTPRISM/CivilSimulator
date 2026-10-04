"use client";

/**
 * Higher-fidelity roads + architecture for World3D.
 * Roads: continuous Catmull-Rom extrusions that hug terrain.
 * Buildings: genre kits (Chinese traditional / modern curtain / noir / sci-fi)
 * instead of plain stacked boxes.
 */
import { Suspense, useEffect, useMemo } from "react";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { resolveBuildingModel, resolveStallModel, type BuildingRole } from "@/lib/buildingKits";
import KitBuildingMesh, { KitErrorBoundary } from "@/components/world/KitBuildingMesh";
import HumanoidFigure from "@/components/HumanoidFigure";
import { getFigure, type RoleSkinId } from "@/lib/characterFigures";
import LandmarkBuilding from "@/components/world/LandmarkBuildings";

export type ArchBuildingType =
  | "commercial" | "residential" | "temple" | "dock" | "palace"
  | "tower" | "shop" | "office" | "ship_port" | "stall" | "farmhouse";

export type ArchBuilding = {
  name: string; x: number; y: number; w: number; h: number;
  enterable?: boolean; floors?: number; type?: ArchBuildingType;
  sign?: string; banner?: boolean;
  /** Yaw in radians — face the street */
  rot?: number;
  /** v1.4 map landmark tier */
  landmark?: "primary" | "secondary";
  /** Explicit hero GLB key (landmark_tavern / landmark_palace / landmark_temple) */
  modelKey?: string;
  zone?: "urban" | "rural" | "sacred" | string;
  city?: string;
  /** Stall goods kind: 果摊 / 布摊 / 书摊 / … */
  stallKind?: string;
};

export type ArchRoad = {
  from: [number, number]; to: [number, number];
  /** cobble = 青石板城内路；dirt = 泥土乡道；paved/neon = 现代 */
  kind?: "dirt" | "cobble" | "paved" | "neon";
};

/** Procedural seamless road albedo (canvas → CanvasTexture). */
function makeRoadAlbedo(kind: "cobble" | "dirt" | "paved" | "neon", seed = 1): THREE.CanvasTexture {
  const size = 256;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d")!;
  if (kind === "cobble") {
    // Mortar base — 青石灰缝
    ctx.fillStyle = "#9ca3af";
    ctx.fillRect(0, 0, size, size);
    const cols = 6;
    const rows = 6;
    const bw = size / cols;
    const bh = size / rows;
    for (let row = 0; row < rows; row++) {
      const ox = (row % 2) * (bw * 0.5);
      for (let col = -1; col <= cols; col++) {
        const x = col * bw + ox;
        const y = row * bh;
        const n = ((row * 17 + col * 31 + seed * 13) % 50);
        const g = 120 + n;
        const b = 135 + Math.floor(n * 0.7);
        ctx.fillStyle = `rgb(${g - 18},${g},${b})`;
        ctx.strokeStyle = "#6b7280";
        ctx.lineWidth = 3;
        const inset = 3;
        ctx.fillRect(x + inset, y + inset, bw - inset * 2, bh - inset * 2);
        ctx.strokeRect(x + inset, y + inset, bw - inset * 2, bh - inset * 2);
        ctx.fillStyle = "rgba(255,255,255,0.12)";
        ctx.fillRect(x + inset + 2, y + inset + 2, (bw - inset * 2) * 0.45, 3);
      }
    }
  } else if (kind === "dirt") {
    ctx.fillStyle = "#9a7040";
    ctx.fillRect(0, 0, size, size);
    for (let i = 0; i < 2800; i++) {
      const x = (i * 47 + seed * 19) % size;
      const y = (i * 91 + seed * 7) % size;
      const v = 70 + ((i * 13) % 60);
      ctx.fillStyle = `rgba(${v + 40},${v},${v - 30},${0.2 + (i % 5) * 0.06})`;
      ctx.fillRect(x, y, 2 + (i % 4), 2 + (i % 3));
    }
    // wheel ruts
    ctx.strokeStyle = "rgba(50,30,12,0.45)";
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.moveTo(size * 0.32, 0);
    ctx.lineTo(size * 0.36, size);
    ctx.moveTo(size * 0.66, 0);
    ctx.lineTo(size * 0.60, size);
    ctx.stroke();
  } else {
    ctx.fillStyle = kind === "neon" ? "#1e293b" : "#52525b";
    ctx.fillRect(0, 0, size, size);
    for (let i = 0; i < 400; i++) {
      const x = (i * 53) % size;
      const y = (i * 97) % size;
      ctx.fillStyle = `rgba(255,255,255,${0.02 + (i % 4) * 0.01})`;
      ctx.fillRect(x, y, 3, 3);
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  tex.needsUpdate = true;
  return tex;
}

type HeightFn = (x: number, z: number) => number;
type Px2World = (x: number, y: number) => [number, number];

const CLASSIC = new Set(["ancient", "wuxia", "xuanhuan"]);

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

type RoadKind = "dirt" | "cobble" | "paved" | "neon";

function roadHalfW(kind: RoadKind): number {
  // Cobble slightly narrower — wide elevated strips read as 长城
  return kind === "neon" ? 1.55 : kind === "paved" ? 1.45 : kind === "cobble" ? 2.85 : 3.5;
}
function roadLift(kind: RoadKind): number {
  return kind === "dirt" ? 0.22 : kind === "cobble" ? 0.2 : 0.28;
}
function roadTint(kind: RoadKind): THREE.Color {
  if (kind === "neon") return new THREE.Color("#1e293b");
  if (kind === "paved") return new THREE.Color("#d4d4d8");
  if (kind === "cobble") return new THREE.Color("#c4cdd8");
  return new THREE.Color("#d2b48c");
}

function nodeKeyPx(p: [number, number]): string {
  return `${Math.round(p[0] * 2) / 2},${Math.round(p[1] * 2) / 2}`;
}

function resolveRoadKind(r: ArchRoad, genre: string): RoadKind {
  return (r.kind as RoadKind)
    || (genre === "scifi" ? "neon"
      : genre === "modern" || genre === "mystery" || genre === "enterprise" || genre === "securities"
        ? "paved"
        : "dirt");
}

type JunctionArm = {
  dx: number; dz: number; // unit, outward from node in world XZ
  halfW: number;
  kind: RoadKind;
  angle: number;
};

export type RoadEndBlend = {
  /** Foreign style at this end (null = same style or no neighbor). */
  start: RoadKind | null;
  end: RoadKind | null;
  startJunction: boolean;
  endJunction: boolean;
  /** World-meters to cut this ribbon short of the node (miter room for junction poly). */
  insetStart: number;
  insetEnd: number;
};

type NodeInfo = {
  x: number; y: number; // map px
  arms: { ux: number; uy: number; kind: RoadKind; halfW: number; roadIdx: number; atStart: boolean }[];
};

function buildRoadNodes(roads: ArchRoad[], genre: string, scale: number): Map<string, NodeInfo> {
  const nodes = new Map<string, NodeInfo>();
  roads.forEach((r, roadIdx) => {
    const kind = resolveRoadKind(r, genre);
    const halfW = roadHalfW(kind);
    const ends: [ [number, number], boolean ][] = [[r.from, true], [r.to, false]];
    for (const [p, atStart] of ends) {
      const key = nodeKeyPx(p);
      const other = atStart ? r.to : r.from;
      const len = Math.hypot(other[0] - p[0], other[1] - p[1]) || 1;
      // Outward in map px (y → world z)
      const ux = (other[0] - p[0]) / len;
      const uy = (other[1] - p[1]) / len;
      const n = nodes.get(key) || { x: p[0], y: p[1], arms: [] };
      n.arms.push({ ux, uy, kind, halfW, roadIdx, atStart });
      nodes.set(key, n);
    }
  });
  void scale;
  return nodes;
}

/** Per-endpoint blend + miter inset for every road. */
export function roadEndBlendKinds(
  roads: ArchRoad[],
  genre: string,
  scale = 0.38,
): RoadEndBlend[] {
  const nodes = buildRoadNodes(roads, genre, scale);
  return roads.map((r, roadIdx) => {
    const mine = resolveRoadKind(r, genre);
    const endInfo = (p: [number, number], atStart: boolean) => {
      const node = nodes.get(nodeKeyPx(p));
      if (!node || node.arms.length < 2) {
        return { foreign: null as RoadKind | null, junction: false, inset: 0 };
      }
      const foreign = node.arms.map((a) => a.kind).find((k) => k !== mine) || null;
      const myArm = node.arms.find((a) => a.roadIdx === roadIdx && a.atStart === atStart);
      const myU = myArm ? { x: myArm.ux, y: myArm.uy } : { x: 0, y: 0 };
      const myHw = roadHalfW(mine);
      // Dirt mountain paths: no inset — insets were leaving visible gaps on slopes
      if (mine === "dirt") {
        return { foreign, junction: true, inset: 0 };
      }
      let insetM = myHw * 0.85;
      for (const a of node.arms) {
        if (a.roadIdx === roadIdx) continue;
        const dot = Math.abs(a.ux * myU.x + a.uy * myU.y);
        if (dot > 0.92) {
          if (a.kind !== mine) insetM = Math.max(insetM, Math.max(myHw, a.halfW) * 0.5);
          continue;
        }
        insetM = Math.max(insetM, a.halfW * 0.9, myHw * 0.85);
      }
      return { foreign, junction: true, inset: insetM };
    };
    const s = endInfo(r.from, true);
    const e = endInfo(r.to, false);
    return {
      start: s.foreign,
      end: e.foreign,
      startJunction: s.junction,
      endJunction: e.junction,
      insetStart: s.inset,
      insetEnd: e.inset,
    };
  });
}

/** Monotone chain convex hull in XZ (y ignored). */
function convexHullXZ(pts: { x: number; z: number }[]): { x: number; z: number }[] {
  const p = [...pts].sort((a, b) => a.x - b.x || a.z - b.z);
  if (p.length <= 2) return p;
  const cross = (o: { x: number; z: number }, a: { x: number; z: number }, b: { x: number; z: number }) =>
    (a.x - o.x) * (b.z - o.z) - (a.z - o.z) * (b.x - o.x);
  const lower: { x: number; z: number }[] = [];
  for (const pt of p) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 0) lower.pop();
    lower.push(pt);
  }
  const upper: { x: number; z: number }[] = [];
  for (let i = p.length - 1; i >= 0; i--) {
    const pt = p[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 0) upper.pop();
    upper.push(pt);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}

/**
 * Polygonal junction fills from road-corridor corners (never circles).
 * Cross → rectangle/octagon; T → rect; collinear style-join → short splice rect.
 * Roads are inset so their square-cut ends abut this polygon.
 */
export function RoadJunctionFills({
  roads, genre, mapWidth, mapHeight, heightAt, scale = 0.38,
}: {
  roads: ArchRoad[];
  genre: string;
  mapWidth: number;
  mapHeight: number;
  heightAt: HeightFn;
  scale?: number;
}) {
  const meshes = useMemo(() => {
    const nodes = buildRoadNodes(roads, genre, scale);
    const out: { geom: THREE.BufferGeometry; color: string }[] = [];

    for (const node of nodes.values()) {
      if (node.arms.length < 2) continue;
      const cx = (node.x - mapWidth / 2) * scale;
      const cz = (node.y - mapHeight / 2) * scale;

      const arms: JunctionArm[] = node.arms.map((a) => ({
        dx: a.ux, dz: a.uy, halfW: a.halfW, kind: a.kind,
        angle: Math.atan2(a.ux, a.uy),
      }));
      arms.sort((a, b) => a.angle - b.angle);
      const uniq: JunctionArm[] = [];
      for (const a of arms) {
        const prev = uniq[uniq.length - 1];
        if (prev && Math.abs(a.angle - prev.angle) < 0.12) {
          if (a.halfW > prev.halfW) uniq[uniq.length - 1] = a;
        } else uniq.push(a);
      }
      if (uniq.length >= 2) {
        const first = uniq[0];
        const last = uniq[uniq.length - 1];
        const wrap = Math.abs(first.angle + Math.PI * 2 - last.angle) < 0.12;
        if (wrap) {
          if (first.halfW >= last.halfW) uniq.pop();
          else uniq.shift();
        }
      }
      if (uniq.length < 2) continue;

      // Sample each arm's left/right curb at node and at abutment (= halfW out)
      const edgePts: { x: number; z: number }[] = [];
      for (const a of uniq) {
        const px = -a.dz;
        const pz = a.dx;
        const ext = a.halfW; // matches ribbon inset for crossing arms
        for (const s of [-1, 1] as const) {
          edgePts.push({ x: cx + px * a.halfW * s, z: cz + pz * a.halfW * s });
          edgePts.push({
            x: cx + a.dx * ext + px * a.halfW * s,
            z: cz + a.dz * ext + pz * a.halfW * s,
          });
        }
      }
      const corners = convexHullXZ(edgePts);
      if (corners.length < 3) continue;

      const kinds = [...new Set(uniq.map((a) => a.kind))];
      const col = roadTint(kinds[0]).clone();
      if (kinds.length > 1) col.lerp(roadTint(kinds[1]), 0.5);
      const lift = Math.max(...uniq.map((a) => roadLift(a.kind))) + 0.02;
      // Drape on terrain (per-vertex Y) — flat slabs float on mountain grades
      const ys = corners.map((c) => heightAt(c.x, c.z));
      const ySpan = Math.max(...ys) - Math.min(...ys);
      if (ySpan > 2.8) continue; // too steep for a fill patch; ribbons meet alone

      const yC = heightAt(cx, cz) + lift;
      const positions: number[] = [cx, yC, cz];
      const colors: number[] = [col.r, col.g, col.b];
      for (let ci = 0; ci < corners.length; ci++) {
        const c = corners[ci];
        positions.push(c.x, ys[ci] + lift, c.z);
        colors.push(col.r, col.g, col.b);
      }
      const indices: number[] = [];
      for (let i = 0; i < corners.length; i++) {
        indices.push(0, i + 1, ((i + 1) % corners.length) + 1);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
      g.setIndex(indices);
      g.computeVertexNormals();
      out.push({ geom: g, color: `#${col.getHexString()}` });
    }
    return out;
  }, [roads, genre, mapWidth, mapHeight, scale, heightAt]);

  return (
    <group>
      {meshes.map((m, i) => (
        <mesh key={i} geometry={m.geom} receiveShadow>
          <meshStandardMaterial
            color={m.color}
            vertexColors
            roughness={0.9}
            metalness={0.04}
            side={THREE.DoubleSide}
            polygonOffset
            polygonOffsetFactor={-5}
            polygonOffsetUnits={-5}
          />
        </mesh>
      ))}
    </group>
  );
}

/** Continuous road ribbon — ends inset + style blend; joins via polygonal fills. */
export function SmoothRoad({
  road, genre, mapWidth, mapHeight, heightAt, scale = 0.38,
  blendStart = null, blendEnd = null,
  startJunction = false, endJunction = false,
  insetStart = 0, insetEnd = 0,
}: {
  road: ArchRoad;
  genre: string;
  mapWidth: number;
  mapHeight: number;
  heightAt: HeightFn;
  scale?: number;
  blendStart?: RoadKind | null;
  blendEnd?: RoadKind | null;
  startJunction?: boolean;
  endJunction?: boolean;
  insetStart?: number;
  insetEnd?: number;
}) {
  const kind: RoadKind =
    (road.kind as RoadKind)
    || (genre === "scifi" ? "neon"
      : genre === "modern" || genre === "mystery" || genre === "enterprise" || genre === "securities"
        ? "paved"
        : "dirt");

  const texKind: "cobble" | "dirt" | "paved" | "neon" =
    kind === "cobble" ? "cobble"
      : kind === "dirt" ? "dirt"
        : kind === "neon" ? "neon"
          : "paved";

  const albedo = useMemo(
    () => makeRoadAlbedo(texKind, Math.abs((road.from[0] * 13 + road.to[1] * 7) | 0)),
    [texKind, road.from[0], road.to[1]],
  );

  const { roadGeom, bedGeom, lineGeom, uvRepeat, useVertexColor } = useMemo(() => {
    let ax = (road.from[0] - mapWidth / 2) * scale;
    let az = (road.from[1] - mapHeight / 2) * scale;
    let bx = (road.to[0] - mapWidth / 2) * scale;
    let bz = (road.to[1] - mapHeight / 2) * scale;
    const fullLen = Math.hypot(bx - ax, bz - az);
    const empty = new THREE.BufferGeometry();
    if (fullLen < 0.2) {
      return {
        roadGeom: empty, bedGeom: empty,
        lineGeom: null as THREE.BufferGeometry | null,
        uvRepeat: 1, useVertexColor: false,
      };
    }
    const ux = (bx - ax) / fullLen;
    const uz = (bz - az) / fullLen;
    // Cut ribbon short of junction so polygonal fill owns the intersection
    // Never erase short mountain/approach segments — cap inset hard
    const i0 = Math.min(insetStart, fullLen * 0.22);
    const i1 = Math.min(insetEnd, fullLen * 0.22);
    if (i0 + i1 >= fullLen - 0.8) {
      // Keep a stub ribbon instead of deleting the road (avoids mountain disconnects)
      const keep = Math.max(0.5, fullLen * 0.35);
      const skip = (fullLen - keep) * 0.5;
      ax += ux * skip; az += uz * skip;
      bx -= ux * skip; bz -= uz * skip;
    } else {
      ax += ux * i0; az += uz * i0;
      bx -= ux * i1; bz -= uz * i1;
    }
    const len = Math.hypot(bx - ax, bz - az);
    if (len < 0.25) {
      return {
        roadGeom: empty, bedGeom: empty,
        lineGeom: null as THREE.BufferGeometry | null,
        uvRepeat: 1, useVertexColor: false,
      };
    }
    // Dense samples on steep grades so the ribbon doesn't chord through the air
    const hProbe0 = heightAt(ax, az);
    const hProbe1 = heightAt(bx, bz);
    const slope = Math.abs(hProbe1 - hProbe0) / Math.max(len, 0.01);
    const samples = Math.max(56, Math.ceil(len * (slope > 0.12 ? 28 : slope > 0.06 ? 18 : 12)));
    const nx = -uz;
    const nz = ux;
    const halfW0 = roadHalfW(kind);
    const lift0 = roadLift(kind);
    const styleBlend = Math.min(len * 0.4, 12);
    const colStart = blendStart ? roadTint(blendStart) : roadTint(kind);
    const colEnd = blendEnd ? roadTint(blendEnd) : roadTint(kind);
    // Match width to junction poly at abutments
    const hwStart = (blendStart || startJunction) ? halfW0 : halfW0;
    const hwEnd = (blendEnd || endJunction) ? halfW0 : halfW0;
    const useVertexColor = !!(blendStart || blendEnd);
    const smooth = (u: number) => u * u * (3 - 2 * u);

    const left: THREE.Vector3[] = [];
    const right: THREE.Vector3[] = [];
    const mid: THREE.Vector3[] = [];
    const uvs: number[] = [];
    const colors: number[] = [];
    const bed = 0.1;

    for (let i = 0; i <= samples; i++) {
      const t = i / samples;
      const distStart = t * len;
      const distEnd = (1 - t) * len;
      let halfW = halfW0;
      let lift = lift0;
      const c = new THREE.Color(1, 1, 1);

      // Square cut at abutment (constant width) — no tapered "bubble"
      if (startJunction && distStart < 0.8) halfW = hwStart;
      if (endJunction && distEnd < 0.8) halfW = hwEnd;

      if (blendStart && distStart < styleBlend) {
        const s = smooth(1 - distStart / styleBlend);
        c.lerp(colStart.clone().multiplyScalar(1.12), s * 0.7);
      }
      if (blendEnd && distEnd < styleBlend) {
        const s = smooth(1 - distEnd / styleBlend);
        c.lerp(colEnd.clone().multiplyScalar(1.12), s * 0.7);
      }

      const x = ax + (bx - ax) * t;
      const z = az + (bz - az) * t;
      let yMax = heightAt(x, z);
      for (const f of [-1, -0.5, 0.5, 1]) {
        yMax = Math.max(yMax, heightAt(x + nx * halfW * f, z + nz * halfW * f));
      }
      const y = yMax + lift;
      left.push(new THREE.Vector3(x + nx * halfW, y, z + nz * halfW));
      right.push(new THREE.Vector3(x - nx * halfW, y, z - nz * halfW));
      mid.push(new THREE.Vector3(x, y + 0.02, z));
      const v = t * (len / (halfW * 2));
      uvs.push(0, v, 1, v);
      colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
    }

    const buildStrip = (a: THREE.Vector3[], b: THREE.Vector3[], withUv: boolean, withColor: boolean) => {
      const positions: number[] = [];
      const indices: number[] = [];
      for (let i = 0; i < a.length; i++) {
        positions.push(a[i].x, a[i].y, a[i].z);
        positions.push(b[i].x, b[i].y, b[i].z);
      }
      for (let i = 0; i < a.length - 1; i++) {
        const i0 = i * 2;
        indices.push(i0, i0 + 1, i0 + 2, i0 + 1, i0 + 3, i0 + 2);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      if (withUv) g.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
      if (withColor) g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
      g.setIndex(indices);
      g.computeVertexNormals();
      return g;
    };

    const roadGeom = buildStrip(left, right, true, useVertexColor);
    const bedL = left.map((p) => new THREE.Vector3(p.x, p.y - bed, p.z));
    const bedR = right.map((p) => new THREE.Vector3(p.x, p.y - bed, p.z));
    const bedGeom = buildStrip(bedL, bedR, false, false);
    let lineGeom: THREE.BufferGeometry | null = null;
    if (kind === "paved" || kind === "neon") {
      const lw = kind === "neon" ? 0.08 : 0.06;
      const lA: THREE.Vector3[] = [];
      const lB: THREE.Vector3[] = [];
      for (const p of mid) {
        lA.push(new THREE.Vector3(p.x + nx * lw, p.y + 0.01, p.z + nz * lw));
        lB.push(new THREE.Vector3(p.x - nx * lw, p.y + 0.01, p.z - nz * lw));
      }
      lineGeom = buildStrip(lA, lB, false, false);
    }
    return { roadGeom, bedGeom, lineGeom, uvRepeat: Math.max(1, len / 6), useVertexColor };
  }, [
    road.from[0], road.from[1], road.to[0], road.to[1], road.kind, kind,
    mapWidth, mapHeight, scale, heightAt, blendStart, blendEnd,
    startJunction, endJunction, insetStart, insetEnd,
  ]);

  useEffect(() => {
    albedo.repeat.set(1, uvRepeat);
    albedo.needsUpdate = true;
  }, [albedo, uvRepeat]);

  const matProps =
    kind === "neon"
      ? { color: "#ffffff", roughness: 0.4, metalness: 0.35, emissive: "#0e7490", emissiveIntensity: 0.28 }
      : kind === "cobble"
        ? { color: "#c4cdd8", roughness: 0.88, metalness: 0.06, emissive: "#000000", emissiveIntensity: 0 }
        : kind === "paved"
          ? { color: "#d4d4d8", roughness: 0.82, metalness: 0.08, emissive: "#000000", emissiveIntensity: 0 }
          : { color: "#d2b48c", roughness: 0.96, metalness: 0.02, emissive: "#000000", emissiveIntensity: 0 };

  const lineColor =
    kind === "neon" ? "#22d3ee"
      : genre === "mystery" ? "#d6d3d1"
        : genre === "securities" ? "#eab308"
          : genre === "enterprise" ? "#5eead4"
            : "#facc15";

  return (
    <group>
      <mesh geometry={bedGeom} receiveShadow>
        <meshStandardMaterial
          color={kind === "dirt" ? "#5c4030" : "#3f4650"}
          roughness={1}
          side={THREE.DoubleSide}
          depthWrite
        />
      </mesh>
      <mesh geometry={roadGeom} receiveShadow>
        <meshStandardMaterial
          {...matProps}
          map={albedo}
          vertexColors={useVertexColor}
          side={THREE.DoubleSide}
          polygonOffset
          polygonOffsetFactor={-4}
          polygonOffsetUnits={-4}
          depthWrite
        />
      </mesh>
      {lineGeom && (
        <mesh geometry={lineGeom} receiveShadow>
          <meshStandardMaterial
            color={lineColor}
            roughness={0.35}
            metalness={kind === "neon" ? 0.5 : 0.1}
            emissive={kind === "neon" ? lineColor : "#000000"}
            emissiveIntensity={kind === "neon" ? 0.95 : 0}
            side={THREE.DoubleSide}
            polygonOffset
            polygonOffsetFactor={-5}
            polygonOffsetUnits={-5}
          />
        </mesh>
      )}
    </group>
  );
}

/** Hip / 庑殿 roof from four sloping faces + ridge. */
function HipRoof({
  w, d, h = 0.85, color = "#7f1d1d", accent = "#44403c", ornate = false,
}: {
  w: number; d: number; h?: number; color?: string; accent?: string; ornate?: boolean;
}) {
  const geom = useMemo(() => {
    const hw = w / 2;
    const hd = d / 2;
    const rw = w * 0.12;
    const A = [-hw, 0, hd];
    const B = [hw, 0, hd];
    const C = [hw, 0, -hd];
    const D = [-hw, 0, -hd];
    const R0 = [-rw, h, 0];
    const R1 = [rw, h, 0];
    const tris: number[] = [];
    const tri = (p: number[], q: number[], r: number[]) => tris.push(...p, ...q, ...r);
    tri(A, B, R1); tri(A, R1, R0);
    tri(B, C, R1);
    tri(C, D, R0); tri(C, R0, R1);
    tri(D, A, R0);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(tris, 3));
    g.computeVertexNormals();
    return g;
  }, [w, d, h]);

  return (
    <group>
      <mesh geometry={geom} castShadow receiveShadow>
        <meshStandardMaterial color={color} roughness={0.72} metalness={0.08} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, 0.04, 0]} castShadow>
        <boxGeometry args={[w * 1.08, 0.07, d * 1.08]} />
        <meshStandardMaterial color={accent} roughness={0.8} />
      </mesh>
      <mesh position={[0, h + 0.04, 0]} castShadow>
        <boxGeometry args={[w * 0.28, 0.1, 0.12]} />
        <meshStandardMaterial color={accent} roughness={0.65} />
      </mesh>
      {ornate && (
        <>
          {/* ridge tiles */}
          <mesh position={[0, h + 0.08, 0]} castShadow>
            <boxGeometry args={[w * 0.22, 0.08, 0.16]} />
            <meshStandardMaterial color="#78350f" roughness={0.55} metalness={0.2} />
          </mesh>
          {/* chiwen / ridge finials */}
          {([-1, 1] as const).map((sx) => (
            <mesh key={`rf${sx}`} position={[sx * w * 0.42, h * 0.35, 0]} castShadow>
              <coneGeometry args={[0.1, 0.35, 6]} />
              <meshStandardMaterial color="#ca8a04" metalness={0.55} roughness={0.32} />
            </mesh>
          ))}
          <mesh position={[0, h + 0.32, 0]} castShadow>
            <sphereGeometry args={[0.14, 12, 10]} />
            <meshStandardMaterial color="#eab308" metalness={0.65} roughness={0.28} />
          </mesh>
          {([[-1, -1], [-1, 1], [1, -1], [1, 1]] as const).map(([sx, sz], i) => (
            <mesh
              key={i}
              position={[sx * w * 0.5, 0.12, sz * d * 0.5]}
              rotation={[0, 0, -sx * 0.55]}
              castShadow
            >
              <boxGeometry args={[0.55, 0.07, 0.1]} />
              <meshStandardMaterial color={color} roughness={0.65} />
            </mesh>
          ))}
        </>
      )}
    </group>
  );
}

function LatticeWindow({
  x, y, z, w = 0.55, h = 0.7, lit, litColor = "#fde68a", open = false,
}: {
  x: number; y: number; z: number; w?: number; h?: number; lit?: boolean; litColor?: string; open?: boolean;
}) {
  const frame = 0.05;
  return (
    <group position={[x, y, z]}>
      {/* frame only when open — hollow so interior reads through */}
      <mesh position={[0, h / 2, 0]}>
        <boxGeometry args={[w + frame * 2, frame, 0.06]} />
        <meshStandardMaterial color="#44403c" roughness={0.8} />
      </mesh>
      <mesh position={[0, -h / 2, 0]}>
        <boxGeometry args={[w + frame * 2, frame, 0.06]} />
        <meshStandardMaterial color="#44403c" roughness={0.8} />
      </mesh>
      <mesh position={[-w / 2, 0, 0]}>
        <boxGeometry args={[frame, h, 0.06]} />
        <meshStandardMaterial color="#44403c" roughness={0.8} />
      </mesh>
      <mesh position={[w / 2, 0, 0]}>
        <boxGeometry args={[frame, h, 0.06]} />
        <meshStandardMaterial color="#44403c" roughness={0.8} />
      </mesh>
      {!open && (
        <>
          <mesh>
            <boxGeometry args={[w, h, 0.03]} />
            <meshStandardMaterial
              color={lit ? litColor : "#1c1917"}
              emissive={lit ? litColor : "#000"}
              emissiveIntensity={lit ? 0.55 : 0}
              roughness={0.35}
            />
          </mesh>
          <mesh position={[0, 0, 0.03]}>
            <boxGeometry args={[0.04, h * 0.95, 0.03]} />
            <meshStandardMaterial color="#44403c" roughness={0.8} />
          </mesh>
          <mesh position={[0, 0, 0.03]}>
            <boxGeometry args={[w * 0.95, 0.04, 0.03]} />
            <meshStandardMaterial color="#44403c" roughness={0.8} />
          </mesh>
        </>
      )}
      {open && lit && (
        <pointLight position={[0, 0, -0.4]} intensity={0.35} distance={3.5} color={litColor} />
      )}
    </group>
  );
}

/** Open doorway — no door leaf so room furniture is visible from street. */
function OpenDoorway({
  x, y, z, w = 0.9, h = 1.55, wood = "#4a3428",
}: {
  x: number; y: number; z: number; w?: number; h?: number; wood?: string;
}) {
  const t = 0.07;
  return (
    <group position={[x, y, z]}>
      <mesh position={[0, h / 2, 0]}>
        <boxGeometry args={[w + t * 2, t, 0.1]} />
        <meshStandardMaterial color={wood} roughness={0.75} />
      </mesh>
      <mesh position={[-w / 2 - t / 2, 0, 0]}>
        <boxGeometry args={[t, h, 0.1]} />
        <meshStandardMaterial color={wood} roughness={0.75} />
      </mesh>
      <mesh position={[w / 2 + t / 2, 0, 0]}>
        <boxGeometry args={[t, h, 0.1]} />
        <meshStandardMaterial color={wood} roughness={0.75} />
      </mesh>
      {/* threshold */}
      <mesh position={[0, -h / 2, 0.02]}>
        <boxGeometry args={[w + t * 2, 0.06, 0.14]} />
        <meshStandardMaterial color="#78716c" roughness={0.9} />
      </mesh>
    </group>
  );
}

function StallGoods({ kind, bw, bd }: { kind: string; bw: number; bd: number }) {
  const k = kind || "";
  if (/果/.test(k)) {
    const colors = ["#dc2626", "#ea580c", "#ca8a04", "#16a34a", "#d97706", "#ef4444"];
    return (
      <group>
        {[-0.7, 0, 0.7].map((x, i) => (
          <mesh key={`b${i}`} position={[x, 0.62, 0.08]} castShadow>
            <cylinderGeometry args={[0.38, 0.34, 0.28, 14]} />
            <meshStandardMaterial color="#a16207" roughness={0.9} />
          </mesh>
        ))}
        {Array.from({ length: 14 }).map((_, i) => (
          <mesh
            key={i}
            position={[((i % 7) - 3) * 0.26, 0.88 + Math.floor(i / 7) * 0.2, 0.05 + (i % 2) * 0.12]}
            castShadow
          >
            <sphereGeometry args={[0.14 + (i % 3) * 0.03, 12, 12]} />
            <meshStandardMaterial color={colors[i % colors.length]} roughness={0.5} emissive={colors[i % colors.length]} emissiveIntensity={0.08} />
          </mesh>
        ))}
      </group>
    );
  }
  if (/布|绸|锦/.test(k)) {
    const bolts = ["#b91c1c", "#1d4ed8", "#ca8a04", "#065f46", "#7c3aed"];
    return (
      <group>
        {bolts.map((c, i) => (
          <group key={i} position={[(i - 2) * 0.32, 0.78, -0.05]}>
            <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
              <cylinderGeometry args={[0.1, 0.1, 0.85, 10]} />
              <meshStandardMaterial color={c} roughness={0.65} />
            </mesh>
            <mesh position={[0, 0.12, 0.2]} rotation={[0.4, 0.2, 0]} castShadow>
              <boxGeometry args={[0.55, 0.02, 0.35]} />
              <meshStandardMaterial color={c} roughness={0.7} side={THREE.DoubleSide} />
            </mesh>
          </group>
        ))}
      </group>
    );
  }
  if (/书|卷/.test(k)) {
    return (
      <group>
        {Array.from({ length: 8 }).map((_, i) => (
          <mesh
            key={i}
            position={[((i % 4) - 1.5) * 0.3, 0.72 + Math.floor(i / 4) * 0.12, -0.08]}
            castShadow
          >
            <boxGeometry args={[0.22, 0.08, 0.32]} />
            <meshStandardMaterial
              color={i % 2 ? "#78350f" : "#44403c"}
              roughness={0.85}
            />
          </mesh>
        ))}
        {/* scroll */}
        <mesh position={[0.7, 0.85, 0.1]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.06, 0.06, 0.5, 8]} />
          <meshStandardMaterial color="#fef3c7" roughness={0.8} />
        </mesh>
      </group>
    );
  }
  if (/饼|胡饼|面/.test(k)) {
    return (
      <group>
        {Array.from({ length: 6 }).map((_, i) => (
          <mesh key={i} position={[(i - 2.5) * 0.28, 0.74, (i % 2) * 0.15]} rotation={[-Math.PI / 2, 0, 0]} castShadow>
            <cylinderGeometry args={[0.14, 0.14, 0.05, 16]} />
            <meshStandardMaterial color="#d97706" roughness={0.75} />
          </mesh>
        ))}
        <mesh position={[0, 0.7, -0.25]} castShadow>
          <boxGeometry args={[bw * 0.5, 0.08, 0.25]} />
          <meshStandardMaterial color="#78716c" roughness={0.9} />
        </mesh>
      </group>
    );
  }
  if (/酒/.test(k)) {
    return (
      <group>
        {[-0.45, 0, 0.45].map((x, i) => (
          <group key={i} position={[x, 0.7, 0]}>
            <mesh castShadow>
              <cylinderGeometry args={[0.16, 0.2, 0.45, 12]} />
              <meshStandardMaterial color="#92400e" roughness={0.7} />
            </mesh>
            <mesh position={[0, 0.28, 0]} castShadow>
              <cylinderGeometry args={[0.08, 0.1, 0.12, 10]} />
              <meshStandardMaterial color="#78350f" roughness={0.65} />
            </mesh>
          </group>
        ))}
        <mesh position={[0.7, 0.95, 0.15]} castShadow>
          <boxGeometry args={[0.08, 0.7, 0.08]} />
          <meshStandardMaterial color="#44403c" />
        </mesh>
        <mesh position={[0.85, 1.1, 0.15]} castShadow>
          <boxGeometry args={[0.35, 0.55, 0.04]} />
          <meshStandardMaterial color="#b91c1c" roughness={0.7} />
        </mesh>
      </group>
    );
  }
  if (/香|料/.test(k)) {
    const jars = ["#a16207", "#78716c", "#b45309", "#57534e"];
    return (
      <group>
        {jars.map((c, i) => (
          <mesh key={i} position={[(i - 1.5) * 0.32, 0.78, 0]} castShadow>
            <cylinderGeometry args={[0.12, 0.14, 0.35, 10]} />
            <meshStandardMaterial color={c} roughness={0.8} />
          </mesh>
        ))}
        {/* spice mounds */}
        {["#ea580c", "#ca8a04", "#9a3412"].map((c, i) => (
          <mesh key={`m${i}`} position={[(i - 1) * 0.35, 0.72, 0.28]} castShadow>
            <sphereGeometry args={[0.14, 8, 8]} />
            <meshStandardMaterial color={c} roughness={0.95} />
          </mesh>
        ))}
      </group>
    );
  }
  // default crates
  return (
    <group>
      {Array.from({ length: 3 }).map((_, i) => (
        <mesh key={i} position={[(i - 1) * 0.4, 0.72, 0]} castShadow>
          <boxGeometry args={[0.32, 0.28, 0.32]} />
          <meshStandardMaterial color="#92400e" roughness={0.85} />
        </mesh>
      ))}
    </group>
  );
}

function vendorPresetForStall(sign: string, name: string) {
  const skins: RoleSkinId[] = ["fair", "warm", "tan", "pale"];
  const h = hashStr(name);
  const skin = skins[h % skins.length];
  if (/书/.test(sign)) return getFigure("ancient_student", skin);
  if (/布|绸/.test(sign)) return getFigure("ancient_trader", skin);
  if (/酒/.test(sign)) return getFigure("npc_drunkard", skin);
  if (/香|药/.test(sign)) return getFigure("ancient_clerk", skin);
  if (/果|饼|胡饼|面/.test(sign)) return getFigure("ancient_farmer", skin);
  if (/铁/.test(sign)) return getFigure("ancient_artisan", skin);
  return getFigure("ancient_porter", skin);
}

function StreetStall({
  b, genre, night, bw, bd,
}: {
  b: ArchBuilding; genre: string; night?: boolean; bw: number; bd: number;
}) {
  const kind = b.stallKind || b.sign || "摊";
  const wood = "#5c4033";
  const cloth =
    /果/.test(kind) ? "#15803d"
      : /布/.test(kind) ? "#1d4ed8"
        : /书/.test(kind) ? "#78350f"
          : /酒/.test(kind) ? "#b91c1c"
            : /香/.test(kind) ? "#a16207"
              : "#b45309";
  const vendor = useMemo(() => vendorPresetForStall(kind, b.name), [kind, b.name]);
  const hyStall = resolveStallModel(genre, kind);

  const procedural = (
    <group>
      <mesh position={[0, 0.42, 0.05]} castShadow receiveShadow>
        <boxGeometry args={[bw * 0.95, 0.12, bd * 0.75]} />
        <meshStandardMaterial color={wood} roughness={0.88} />
      </mesh>
      {([[-1, -1], [-1, 1], [1, -1], [1, 1]] as const).map(([sx, sz], i) => (
        <mesh key={i} position={[sx * bw * 0.38, 0.2, sz * bd * 0.28]} castShadow>
          <boxGeometry args={[0.08, 0.4, 0.08]} />
          <meshStandardMaterial color="#3f2a1f" roughness={0.9} />
        </mesh>
      ))}
      <mesh position={[-bw * 0.42, 1.05, -bd * 0.15]} castShadow>
        <cylinderGeometry args={[0.035, 0.04, 1.35, 8]} />
        <meshStandardMaterial color={wood} />
      </mesh>
      <mesh position={[bw * 0.42, 1.05, -bd * 0.15]} castShadow>
        <cylinderGeometry args={[0.035, 0.04, 1.35, 8]} />
        <meshStandardMaterial color={wood} />
      </mesh>
      <mesh position={[0, 1.55, 0.05]} rotation={[0.22, 0, 0]} castShadow>
        <boxGeometry args={[bw * 1.08, 0.04, bd * 1.05]} />
        <meshStandardMaterial
          color={cloth}
          roughness={0.72}
          emissive={night ? cloth : "#000"}
          emissiveIntensity={night ? 0.2 : 0}
        />
      </mesh>
      <StallGoods kind={kind} bw={bw} bd={bd} />
    </group>
  );

  return (
    <group>
      {hyStall ? (
        <KitErrorBoundary fallback={procedural}>
          <Suspense fallback={procedural}>
            <group>
              <KitBuildingMesh model={hyStall} targetW={bw} targetD={bd} floors={1} night={night} />
              {/* Always layer readable goods — hy3d stalls have no texture/skin */}
              <StallGoods kind={kind} bw={bw} bd={bd} />
            </group>
          </Suspense>
        </KitErrorBoundary>
      ) : (
        procedural
      )}

      {/* Vendor — real humanoid behind counter */}
      <group position={[0, 0, -bd * 0.35]}>
        <Suspense fallback={null}>
          <HumanoidFigure preset={vendor} scale={0.72} behavior="idle" />
        </Suspense>
      </group>

      <Html position={[0, 2.35, 0]} center distanceFactor={14}>
        <div className="text-[9px] px-1.5 py-0.5 rounded bg-stone-900/80 text-amber-50 pointer-events-none border border-amber-700/50 font-serif">
          {kind}
        </div>
      </Html>
    </group>
  );
}

function TraditionalHouse({
  b, genre, night, onEnter, bw, bd, floors, kind,
}: {
  b: ArchBuilding; genre: string; night?: boolean; onEnter?: (n: string) => void;
  bw: number; bd: number; floors: number; kind: ArchBuildingType;
}) {
  const bodyH = Math.max(2.1, floors * 1.55);
  const isTemple = kind === "temple" || kind === "palace";
  const wall =
    genre === "xuanhuan"
      ? (isTemple ? "#f5f3ff" : "#e9d5ff")
      : isTemple ? "#fafaf9" : kind === "commercial" ? "#f0e0c4" : "#e8dcc8";
  const wood = genre === "xuanhuan" ? "#5b21b6" : "#4a3428";
  const roof = genre === "xuanhuan" ? "#6d28d9" : "#9f1239";
  const layers = isTemple ? 3 : (kind === "commercial" ? 2 : 1);
  const label = b.sign || b.name;
  const seed = hashStr(b.name);
  const yaw = ((seed % 9) - 4) * 0.035;
  const openFront = !!b.enterable;

  return (
    <group rotation={[0, yaw, 0]}>
      {/* front steps only — no plaza tray / exposed plinth */}
      <mesh position={[0, 0.04, bd * 0.48]} castShadow receiveShadow>
        <boxGeometry args={[bw * 0.28, 0.08, 0.22]} />
        <meshStandardMaterial color="#a8a29e" roughness={0.92} />
      </mesh>

      {/* timber frame columns */}
      {([[-1, -1], [-1, 1], [1, -1], [1, 1]] as const).map(([sx, sz], i) => (
        <mesh key={i} position={[sx * bw * 0.42, bodyH / 2, sz * bd * 0.42]} castShadow>
          <cylinderGeometry args={[0.09, 0.11, bodyH, 8]} />
          <meshStandardMaterial color={wood} roughness={0.78} />
        </mesh>
      ))}

      {/* wall panels (inset between columns) */}
      <mesh position={[0, bodyH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[bw * 0.78, bodyH, bd * 0.78]} />
        <meshStandardMaterial color={wall} roughness={0.88} />
      </mesh>

      {/* beam under eaves */}
      <mesh position={[0, bodyH + 0.05, 0]} castShadow>
        <boxGeometry args={[bw * 0.95, 0.12, bd * 0.95]} />
        <meshStandardMaterial color={wood} roughness={0.7} />
      </mesh>

      {/* doors — open when enterable so interior can be suggested */}
      {openFront ? (
        <OpenDoorway x={0} y={0.85} z={bd * 0.4} w={0.75} h={1.4} wood={wood} />
      ) : (
        <>
          <mesh position={[0, 0.55, bd * 0.4]} castShadow>
            <boxGeometry args={[0.55, 1.15, 0.08]} />
            <meshStandardMaterial color="#292524" roughness={0.85} />
          </mesh>
          <mesh position={[0, 0.55, bd * 0.45]}>
            <boxGeometry args={[0.08, 1.05, 0.04]} />
            <meshStandardMaterial color="#a16207" metalness={0.3} />
          </mesh>
        </>
      )}

      {/* lattice windows per floor */}
      {Array.from({ length: floors }).map((_, i) => (
        <group key={i}>
          <LatticeWindow
            x={-bw * 0.22} y={1.15 + i * 1.2} z={bd * 0.4}
            open={openFront && i === 0}
            lit={night} litColor={genre === "xuanhuan" ? "#c4b5fd" : "#fde68a"}
          />
          <LatticeWindow
            x={bw * 0.22} y={1.15 + i * 1.2} z={bd * 0.4}
            open={openFront && i === 0}
            lit={night} litColor={genre === "xuanhuan" ? "#c4b5fd" : "#fde68a"}
          />
        </group>
      ))}

      {/* stacked roofs with stronger eaves overhang */}
      {Array.from({ length: layers }).map((_, i) => {
        const scale = 1.12 + (layers - i) * 0.18;
        return (
          <group key={i} position={[0, 0.35 + bodyH + 0.18 + i * 0.85, 0]}>
            <HipRoof
              w={bw * scale}
              d={bd * scale}
              h={0.62 + (isTemple ? 0.28 : 0.08)}
              color={roof}
              accent={wood}
              ornate={isTemple || i === layers - 1}
            />
          </group>
        );
      })}

      {/* shop plaque + banner */}
      {(kind === "commercial" || kind === "shop") && (
        <>
          <mesh position={[0, bodyH * 0.55, bd * 0.42]} castShadow>
            <boxGeometry args={[Math.min(bw * 0.9, 1.7), 0.34, 0.06]} />
            <meshStandardMaterial color={genre === "xuanhuan" ? "#4c1d95" : "#7c2d12"} roughness={0.65} />
          </mesh>
          {b.enterable && (
            <Html position={[0, bodyH * 0.55, bd * 0.48]} center distanceFactor={16}>
              <div className={`font-serif text-[11px] tracking-widest px-1.5 py-0.5 rounded-sm border pointer-events-none
                ${genre === "xuanhuan"
                  ? "text-violet-50 bg-violet-950/85 border-violet-400/50"
                  : "text-amber-50 bg-amber-950/85 border-amber-600/50"}`}>
                {label}
              </div>
            </Html>
          )}
          {b.banner !== false && (
            <group position={[bw * 0.55, 1.5, bd * 0.4]}>
              <mesh position={[0, 0.4, 0]}>
                <cylinderGeometry args={[0.03, 0.03, 1.5, 6]} />
                <meshStandardMaterial color="#44403c" />
              </mesh>
              <mesh position={[0.2, 0.55, 0]} castShadow>
                <boxGeometry args={[0.3, 0.9, 0.04]} />
                <meshStandardMaterial
                  color={genre === "xuanhuan" ? "#7c3aed" : "#b91c1c"}
                  roughness={0.8}
                  emissive={genre === "xuanhuan" ? "#5b21b6" : "#000"}
                  emissiveIntensity={genre === "xuanhuan" ? 0.3 : 0}
                />
              </mesh>
              {b.enterable && (
                <Html position={[0.2, 0.55, 0.05]} center distanceFactor={15}>
                  <div className="text-[9px] text-amber-50 font-serif pointer-events-none [writing-mode:vertical-rl]">
                    {label.slice(0, 4)}
                  </div>
                </Html>
              )}
            </group>
          )}
        </>
      )}

      {night && (
        <pointLight
          position={[0, bodyH * 0.7, bd * 0.5]}
          intensity={0.55}
          distance={7}
          color={genre === "xuanhuan" ? "#c4b5fd" : "#fbbf24"}
        />
      )}
      {b.enterable && (
        <Html position={[0, bodyH + layers * 0.85 + 1.2, 0]} center distanceFactor={22}>
          <button type="button" onClick={() => onEnter?.(b.name)}
            className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/85 text-amber-50
                       border border-amber-500/50 hover:bg-amber-700/90">
            进入 · {b.name}
          </button>
        </Html>
      )}
    </group>
  );
}

function ModernHouse({
  b, genre, night, onEnter, bw, bd, floors, kind,
}: {
  b: ArchBuilding; genre: string; night?: boolean; onEnter?: (n: string) => void;
  bw: number; bd: number; floors: number; kind: ArchBuildingType;
}) {
  const story = 0.88;
  const bodyH = 0.4 + floors * story;
  const isSci = genre === "scifi";
  const isNoir = genre === "mystery";
  const isCampus = genre === "enterprise";
  const isFinance = genre === "securities";
  const isMil = genre === "military";
  const tall = (kind === "tower" || kind === "office" || floors >= 8) && !isMil;
  const wall =
    isSci
      ? (kind === "residential" ? "#64748b" : "#475569")
      : isNoir
        ? "#57534e"
        : isCampus
          ? (kind === "office" ? "#99f6e4" : "#a7f3d0")
          : isFinance
            ? (kind === "tower" ? "#64748b" : "#94a3b8")
            : isMil
              ? (kind === "commercial" ? "#78716c" : "#a8a29e")
              : kind === "commercial" ? "#cbd5e1" : "#94a3b8";
  const accent =
    isSci ? "#22d3ee"
      : isNoir ? "#9f1239"
        : isCampus ? "#0f766e"
          : isFinance ? "#ca8a04"
            : isMil ? "#3f6212"
              : "#475569";
  const label = b.sign || b.name;

  return (
    <group>
      {/* main volume — no exposed podium tray */}
      <mesh position={[0, bodyH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[bw, bodyH, bd]} />
        <meshStandardMaterial
          color={wall}
          roughness={isSci ? 0.42 : 0.45}
          metalness={isSci ? 0.28 : 0.22}
        />
      </mesh>
      {/* vertical corner fins for silhouette */}
      {([[-1, -1], [-1, 1], [1, -1], [1, 1]] as const).map(([sx, sz], i) => (
        <mesh key={i} position={[sx * bw * 0.52, bodyH / 2, sz * bd * 0.52]} castShadow>
          <boxGeometry args={[0.12, bodyH * 1.02, 0.12]} />
          <meshStandardMaterial color={accent} metalness={0.55} roughness={0.35} />
        </mesh>
      ))}
      {tall && floors > 10 && (
        <mesh position={[0, bodyH * 0.72, 0]} castShadow>
          <boxGeometry args={[bw * 0.82, bodyH * 0.45, bd * 0.82]} />
          <meshStandardMaterial
            color={isSci ? "#334155" : "#64748b"}
            roughness={0.3}
            metalness={0.5}
          />
        </mesh>
      )}

      {/* curtain-wall window grid on four façades */}
      {Array.from({ length: Math.min(floors, 22) }).map((_, fi) => {
        const wy = 0.55 + fi * story;
        if (wy > bodyH - 0.15) return null;
        const cols = Math.max(2, Math.min(4, Math.round(bw / 0.9)));
        const lit = night || isSci;
        const c = isSci ? "#67e8f9"
          : isNoir && night ? "#fb7185"
            : isCampus ? "#5eead4"
              : isFinance ? "#93c5fd"
                : isMil ? "#a3e635"
                  : night ? "#fde68a" : "#7dd3fc";
        const faces: [number, number, number, number][] = [
          [0, 0, bd / 2 + 0.03, 0],
          [0, 0, -bd / 2 - 0.03, Math.PI],
          [bw / 2 + 0.03, 0, 0, Math.PI / 2],
          [-bw / 2 - 0.03, 0, 0, -Math.PI / 2],
        ];
        return (
          <group key={fi}>
            {faces.map(([fx, , fz, rot], faceI) => (
              <group key={faceI} position={[fx, wy, fz]} rotation={[0, rot, 0]}>
                {Array.from({ length: cols }).map((_, ci) => {
                  const span = faceI < 2 ? bw : bd;
                  const wx = -span * 0.32 + ci * (span * 0.64 / Math.max(cols - 1, 1));
                  return (
                    <mesh key={ci} position={[wx, 0, 0]}>
                      <boxGeometry args={[span * 0.18, story * 0.58, 0.05]} />
                      <meshStandardMaterial
                        color={c}
                        emissive={lit ? c : "#038"}
                        emissiveIntensity={lit ? (isSci ? 0.55 : 0.25) : 0.08}
                        roughness={0.18}
                        metalness={0.4}
                      />
                    </mesh>
                  );
                })}
              </group>
            ))}
          </group>
        );
      })}

      {/* entrance canopy */}
      <mesh position={[0, 1.35, bd / 2 + 0.25]} castShadow>
        <boxGeometry args={[bw * 0.55, 0.08, 0.55]} />
        <meshStandardMaterial color="#1e293b" metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.7, bd / 2 + 0.02]} castShadow>
        <boxGeometry args={[0.7, 1.25, 0.08]} />
        <meshStandardMaterial color="#0f172a" roughness={0.5} />
      </mesh>

      {/* roof parapet / mechanical */}
      <mesh position={[0, bodyH + 0.28, 0]} castShadow>
        <boxGeometry args={[bw * 1.02, 0.2, bd * 1.02]} />
        <meshStandardMaterial color="#0f172a" metalness={0.35} roughness={0.5} />
      </mesh>
      {tall && (
        <mesh position={[bw * 0.15, bodyH + 0.9, 0]} castShadow>
          <boxGeometry args={[0.35, 1.0, 0.35]} />
          <meshStandardMaterial
            color="#334155"
            metalness={0.7}
            emissive={isSci ? "#22d3ee" : "#000"}
            emissiveIntensity={isSci ? 0.35 : 0}
          />
        </mesh>
      )}

      {/* sci-fi vertical fins */}
      {isSci && (
        <>
          <mesh position={[-bw / 2 - 0.05, bodyH / 2 + 0.2, 0]} castShadow>
            <boxGeometry args={[0.08, bodyH * 0.9, bd * 0.7]} />
            <meshStandardMaterial color="#22d3ee" emissive="#0891b2" emissiveIntensity={0.35} metalness={0.6} />
          </mesh>
          <mesh position={[bw / 2 + 0.05, bodyH / 2 + 0.2, 0]} castShadow>
            <boxGeometry args={[0.08, bodyH * 0.9, bd * 0.7]} />
            <meshStandardMaterial color="#22d3ee" emissive="#0891b2" emissiveIntensity={0.35} metalness={0.6} />
          </mesh>
        </>
      )}

      {/* lintel / neon sign */}
      {(kind === "commercial" || kind === "shop" || kind === "office") && (
        <>
          <mesh position={[0, 1.55, bd / 2 + 0.08]} castShadow>
            <boxGeometry args={[Math.min(bw * 0.98, 2.6), 0.4, 0.1]} />
            <meshStandardMaterial
              color="#020617"
              emissive={
                isSci ? "#0891b2"
                  : isNoir ? "#9f1239"
                    : isCampus ? "#0f766e"
                      : isFinance ? "#a16207"
                        : isMil ? "#3f6212"
                          : "#1e293b"
              }
              emissiveIntensity={isSci || isNoir || isCampus || isFinance ? 0.55 : 0.15}
              metalness={0.4}
              roughness={0.35}
            />
          </mesh>
          {b.enterable && (
            <Html position={[0, 1.55, bd / 2 + 0.16]} center distanceFactor={15}>
              <div className={`text-[11px] tracking-wide px-2 py-0.5 pointer-events-none border shadow
                ${isSci
                  ? "font-mono text-cyan-100 bg-cyan-950/90 border-cyan-400/60"
                  : isNoir
                    ? "font-mono text-rose-100 bg-rose-950/90 border-rose-400/50"
                    : isCampus
                      ? "font-semibold text-teal-50 bg-teal-950/90 border-teal-400/50"
                      : isFinance
                        ? "font-mono text-amber-50 bg-slate-900/90 border-amber-500/50"
                        : isMil
                          ? "font-semibold text-lime-50 bg-stone-900/90 border-lime-700/50"
                          : "font-semibold text-white bg-slate-900/90 border-slate-500/50"}`}>
                {label}
              </div>
            </Html>
          )}
        </>
      )}

      {night && (
        <pointLight
          position={[0, Math.min(bodyH * 0.6, 12), bd * 0.4]}
          intensity={tall ? 1.1 : 0.5}
          distance={tall ? 18 : 7}
          color={isSci ? "#67e8f9" : isNoir ? "#fb7185" : isCampus ? "#5eead4" : isFinance ? "#fbbf24" : isMil ? "#a3e635" : "#fbbf24"}
        />
      )}
      {b.enterable && (
        <Html position={[0, bodyH + 1.3, 0]} center distanceFactor={22}>
          <button type="button" onClick={() => onEnter?.(b.name)}
            className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/85 text-amber-50
                       border border-amber-500/50 hover:bg-amber-700/90">
            进入 · {b.name}
          </button>
        </Html>
      )}
    </group>
  );
}

export function DetailedBuilding({
  b, genre, night, onEnter, px2world, heightAt, mapW, mapH,
}: {
  b: ArchBuilding;
  genre: string;
  night?: boolean;
  onEnter?: (n: string) => void;
  px2world: Px2World;
  heightAt: HeightFn;
  mapW: number;
  mapH: number;
}) {
  const kind = (b.type || "residential") as BuildingRole;
  // Place at footprint CENTER — corner placement made meshes stick into neighbors
  const [x0, z0] = px2world(b.x, b.y);
  const [x1, z1] = px2world(b.x + (b.w || 8), b.y + (b.h || 8));
  const x = (x0 + x1) * 0.5;
  const z = (z0 + z1) * 0.5;
  const mapBw = Math.abs(x1 - x0);
  const mapBd = Math.abs(z1 - z0);
  // Average local samples so a single downhill probe can't bury the whole house
  const samples = [
    heightAt(x, z),
    heightAt(x + 1.4, z),
    heightAt(x - 1.4, z),
    heightAt(x, z + 1.4),
    heightAt(x, z - 1.4),
  ];
  const y = samples.reduce((s, v) => s + v, 0) / samples.length + 0.02;
  const floors = b.floors || (
    genre === "military" ? (kind === "tower" ? 3 : 2)
      : genre === "enterprise" ? (kind === "tower" ? 8 : kind === "office" ? 5 : 3)
        : genre === "securities" ? (kind === "tower" || kind === "office" ? 12 : 4)
          : (kind === "tower" || kind === "office" ? 12 : 1)
  );
  const classic = CLASSIC.has(genre);

  // Prefer map-reserved footprint (world meters) so stalls/houses never visually overlap
  const footMin: Record<string, [number, number]> = {
    residential: [3.6, 3.2],
    farmhouse: [3.2, 2.8],
    commercial: [4.0, 3.4],
    shop: [3.2, 2.8],
    temple: [5.0, 4.4],
    palace: [5.5, 4.8],
    tower: [4.0, 4.0],
    office: [4.0, 3.6],
    dock: [3.0, 1.4],
    ship_port: [5.0, 4.0],
    stall: [2.6, 2.0],
  };
  const [minW, minD] = footMin[kind] || footMin.residential;
  const isPrimaryLandmark =
    classic && (b.landmark === "primary" || !!b.modelKey || /醉仙|紫宸|古观/.test(b.name));
  const lmBoost = isPrimaryLandmark ? 1.0 : b.landmark === "secondary" ? 1.06 : 1;
  // Landmarks fill their reserved footprint so they sit flush with street lots;
  // ordinary houses keep a small visual gap.
  const fill = isPrimaryLandmark ? 0.96 : 0.86;
  const bw = Math.max(minW, mapBw * fill) * lmBoost;
  const bd = Math.max(minD, mapBd * fill) * lmBoost;
  const landmarkFloorFloor =
    classic ? 3
      : genre === "military" ? 3
        : genre === "enterprise" ? 6
          : genre === "securities" ? 12
            : 10;
  const effFloors = b.landmark === "primary" ? Math.max(floors, landmarkFloorFloor) : floors;

  // Primary landmarks: 二层酒楼 / 四合院 / 道观院落 (not grey hy3d clay).
  const USE_GLB_KITS = true;
  const wantKit =
    kind !== "stall" &&
    USE_GLB_KITS &&
    !isPrimaryLandmark &&
    !(genre === "ancient" && !b.modelKey && b.landmark !== "primary");
  const kit = wantKit
    ? resolveBuildingModel(genre, kind, b.name, {
        modelKey: b.modelKey,
        landmark: b.landmark,
        zone: b.zone,
      })
    : null;
  const label = b.sign || b.name;
  const labelH = Math.max(bw, bd) * (isPrimaryLandmark ? 0.85 : 0.55) + (classic ? 3.2 : floors * 0.12);
  const showLabels = !!b.enterable && !isPrimaryLandmark;
  const yaw = b.rot ?? 0;

  const procedural = kind === "stall" ? (
    <StreetStall b={b} genre={genre} night={night} bw={bw} bd={bd} />
  ) : isPrimaryLandmark ? (
    <LandmarkBuilding
      b={b} genre={genre} night={night} onEnter={onEnter}
      bw={bw} bd={bd} floors={Math.max(effFloors, 2)}
    />
  ) : classic ? (
    <TraditionalHouse
      b={b} genre={genre} night={night} onEnter={onEnter}
      bw={bw} bd={bd} floors={Math.min(floors, 3)} kind={kind}
    />
  ) : (
    <ModernHouse
      b={b} genre={genre} night={night} onEnter={onEnter}
      bw={bw} bd={bd} floors={floors} kind={kind}
    />
  );

  return (
    <group position={[x, y, z]} rotation={[0, yaw, 0]}>
      {kit ? (
        <KitErrorBoundary fallback={procedural}>
          <Suspense fallback={procedural}>
            <KitBuildingMesh model={kit} targetW={bw} targetD={bd} floors={effFloors} night={night} />
          </Suspense>
        </KitErrorBoundary>
      ) : (
        procedural
      )}
      {(kind === "commercial" || kind === "shop" || kind === "office") && showLabels && (
        <Html position={[0, Math.min(labelH, 4.2), bd * 0.55]} center distanceFactor={14}>
          <div className={`text-[11px] px-2 py-0.5 pointer-events-none border shadow tracking-wide
            ${genre === "scifi"
              ? "font-mono text-cyan-100 bg-cyan-950/90 border-cyan-400/60"
              : genre === "mystery"
                ? "font-mono text-rose-100 bg-rose-950/90 border-rose-400/50"
                : classic
                  ? "font-serif text-amber-50 bg-amber-950/85 border-amber-600/50"
                  : "font-semibold text-white bg-slate-900/90 border-slate-500/50"}`}>
            {label}
          </div>
        </Html>
      )}
      {showLabels && (
        <Html position={[0, labelH + 1.2, 0]} center distanceFactor={18}>
          <button type="button" onClick={() => onEnter?.(b.name)}
            className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/85 text-amber-50
                       border border-amber-500/50 hover:bg-amber-700/90">
            进入 · {b.name}
          </button>
        </Html>
      )}
    </group>
  );
}

/** Wooden finger pier — clearly a dock, not a stone bridge. */
export function DetailedDock({
  b, px2world, waterY, genre = "ancient",
}: {
  b: ArchBuilding; px2world: Px2World; waterY: number; genre?: string;
}) {
  const [x0, z0] = px2world(b.x, b.y);
  const [x1, z1] = px2world(b.x + (b.w || 8), b.y + (b.h || 4));
  const x = (x0 + x1) * 0.5;
  const z = (z0 + z1) * 0.5;
  const len = Math.max(4.5, Math.abs(x1 - x0) * 1.05); // out into water
  const wid = Math.max(1.6, Math.abs(z1 - z0) * 0.75);
  const yaw = b.rot ?? 0;
  const plankN = Math.max(8, Math.floor(len / 0.55));
  const pileN = Math.max(4, Math.floor(len / 1.4));
  const woodA = "#78350f";
  const woodB = "#92400e";
  const pile = "#451a03";

  return (
    <group position={[x, waterY + 0.22, z]} rotation={[0, yaw, 0]}>
      {/* Shore abutment */}
      <mesh position={[0, 0.05, -wid * 0.15]} castShadow receiveShadow>
        <boxGeometry args={[len * 0.22, 0.45, wid * 1.35]} />
        <meshStandardMaterial color="#78716c" roughness={0.95} />
      </mesh>
      {/* Finger pier planks along +X (into water when rot faces shore→river) */}
      {Array.from({ length: plankN }).map((_, i) => {
        const t = (i + 0.5) / plankN - 0.05;
        return (
          <mesh
            key={`pl${i}`}
            position={[t * len * 0.92, 0.02, 0]}
            receiveShadow
            castShadow
          >
            <boxGeometry args={[len / plankN * 0.92, 0.12, wid]} />
            <meshStandardMaterial color={i % 2 ? woodA : woodB} roughness={0.94} />
          </mesh>
        );
      })}
      {/* Cross beams */}
      {Array.from({ length: 3 }).map((_, i) => (
        <mesh key={`xb${i}`} position={[len * (0.15 + i * 0.28), -0.08, 0]} castShadow>
          <boxGeometry args={[0.14, 0.16, wid * 1.05]} />
          <meshStandardMaterial color={pile} roughness={0.9} />
        </mesh>
      ))}
      {/* Piles into water */}
      {Array.from({ length: pileN }).map((_, i) => {
        const t = (i + 0.4) / pileN;
        return ([-1, 1] as const).map((side) => (
          <mesh
            key={`p${i}${side}`}
            position={[t * len * 0.85, -0.55, side * wid * 0.42]}
            castShadow
          >
            <cylinderGeometry args={[0.09, 0.11, 1.4, 8]} />
            <meshStandardMaterial color={pile} roughness={0.95} />
          </mesh>
        ));
      })}
      {/* Bollards + rope posts at tip */}
      {([-0.35, 0.35] as const).map((sz) => (
        <mesh key={`bol${sz}`} position={[len * 0.78, 0.35, sz * wid]} castShadow>
          <cylinderGeometry args={[0.1, 0.12, 0.55, 10]} />
          <meshStandardMaterial color="#a16207" roughness={0.7} metalness={0.15} />
        </mesh>
      ))}
      {/* Low wooden rail (not stone parapet) */}
      {([-1, 1] as const).map((side) => (
        <mesh key={`rail${side}`} position={[len * 0.4, 0.35, side * wid * 0.48]} castShadow>
          <boxGeometry args={[len * 0.7, 0.08, 0.06]} />
          <meshStandardMaterial color={woodA} roughness={0.9} />
        </mesh>
      ))}
      <Html position={[len * 0.35, 1.5, 0]} center distanceFactor={22}>
        <div className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/85 text-amber-50
                        border border-amber-700/60 pointer-events-none tracking-wider">
          {b.sign || b.name || "码头"}
        </div>
      </Html>
    </group>
  );
}

export function DetailedShipPort({
  b, night, onEnter, px2world, heightAt, genre = "scifi",
}: {
  b: ArchBuilding; night?: boolean; onEnter?: (n: string) => void;
  px2world: Px2World; heightAt: HeightFn; genre?: string;
}) {
  const [x, z] = px2world(b.x, b.y);
  const y = heightAt(x, z);
  const padR = Math.max(3.2, b.w * 0.38 * 0.4);
  const label = b.sign || b.name;
  const kit = resolveBuildingModel(genre, "ship_port", b.name);

  return (
    <group position={[x, y, z]}>
      <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[padR, 64]} />
        <meshStandardMaterial color="#0f172a" roughness={0.3} metalness={0.65} />
      </mesh>
      <mesh position={[0, 0.07, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[padR * 0.35, padR * 0.42, 48]} />
        <meshStandardMaterial
          color="#22d3ee" emissive="#22d3ee" emissiveIntensity={night ? 1.3 : 0.55} roughness={0.25}
        />
      </mesh>
      {kit ? (
        <Suspense fallback={null}>
          <group position={[0, 0.15, 0]}>
            <KitBuildingMesh model={kit} targetW={padR * 1.4} targetD={padR * 0.9} night={night} />
          </group>
        </Suspense>
      ) : null}
      {night && <pointLight position={[0, 4, 0]} intensity={1.4} distance={18} color="#67e8f9" />}
      <Html position={[0, 3.8, 0]} center distanceFactor={26}>
        <div className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950/85 text-cyan-100
                        border border-cyan-400/50 font-mono pointer-events-none">
          ✦ {label}
        </div>
      </Html>
      {b.enterable && (
        <Html position={[0, 4.6, 0]} center distanceFactor={24}>
          <button type="button" onClick={() => onEnter?.(b.name)}
            className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-900/90 text-cyan-50 border border-cyan-400/60">
            进入 · {b.name}
          </button>
        </Html>
      )}
    </group>
  );
}
