"use client";

/**
 * Immersive world viewport — terrain, stylized architecture, day/night lighting,
 * follow-cam. Keeps the same public Props as before.
 */
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import {
  Html, OrbitControls, PointerLockControls, Sky, Stars, Cloud,
} from "@react-three/drei";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";
import type { Agent } from "@/lib/api";
import HumanoidFigure from "@/components/HumanoidFigure";
import { resolveFigure } from "@/lib/characterFigures";
import { loadWorldMap, type MapData as LoadedMapData } from "@/lib/worldMapLoader";
import {
  WorldPresentationStore, worldNormFromScene,
} from "@/lib/worldPresentationStore";
import { genreKitUrls, markHy3dReady, resolvePropModel } from "@/lib/buildingKits";
import { markHy3dNpcReady } from "@/lib/gltfCharacters";
import KitBuildingMesh, { KitErrorBoundary, preloadKitUrls } from "@/components/world/KitBuildingMesh";
import {
  DetailedBuilding, DetailedDock, DetailedShipPort, SmoothRoad,
  roadEndBlendKinds, RoadJunctionFills,
} from "@/components/world/Architecture";
import { resolveBuildingMove } from "@/lib/buildingCollision";

/**
 * Map px → world meters. Was 0.1 (cities ~9 m radius) while houses are ~4 m —
 * everything overlapped like toys on a table. ~0.38 gives human streets +
 * mountain-scale massifs with buildings nestled on local flats.
 * Per-civ `terrain.worldScale` multiplies this so each civilization feels
 * a different area (xuanhuan huge floating peaks vs compact securities lake).
 */
const SCALE = 0.38;
/** Active unit for the currently mounting Scene — set from map DNA worldScale. */
let ACTIVE_SCALE = SCALE;
const SEG = 160;

type MapLoc = { name: string; x: number; y: number; building?: boolean; enterable?: boolean };
type MapFac = { name: string; x: number; y: number; r: number; color: [number, number, number]; terrain?: string };
type WaterRegion = { x: number; y: number; rx: number; ry: number; depth: number; diveable?: boolean; name?: string };
type RiverRegion = { name?: string; points: [number, number][]; width: number };
type BridgeSeg = { x: number; y: number; angle: number; length: number; name?: string };
type ShoreSpot = { x: number; y: number; kind?: "grass" | "reed" };
type TreeSpot = { x: number; y: number; climbable?: boolean };
type BuildingType =
  | "commercial" | "residential" | "temple" | "dock" | "palace"
  | "tower" | "shop" | "office" | "ship_port" | "stall" | "farmhouse";
type Building = {
  name: string; x: number; y: number; w: number; h: number;
  enterable?: boolean; floors?: number; type?: BuildingType;
  sign?: string; banner?: boolean; rot?: number; city?: string;
  landmark?: "primary" | "secondary";
  modelKey?: string;
  zone?: string;
  stallKind?: string;
};
type MapProp = {
  kind: string; x: number; y: number; rot?: number; scale?: number;
};
type MapLandmark = {
  id: string; name: string; tier: "primary" | "secondary";
  x: number; y: number; building_type?: string; city?: string;
};
type CameraAnchor = {
  id: string; x: number; y: number; yaw?: number; pitch?: number;
  distance?: number; role?: string; look_at?: { x: number; y: number };
};
type RoadSeg = { from: [number, number]; to: [number, number]; kind?: "dirt" | "cobble" | "paved" | "neon" };
type CityWall = { name?: string; x: number; y: number; rx: number; ry: number; hasMoat?: boolean };
type Animal = { name: string; x: number; y: number; species: string; behavior: string };
type FieldPatch = { x: number; y: number; w: number; h: number; kind?: "paddy" | "park" };
type MapData = LoadedMapData & {
  water?: WaterRegion[]; rivers?: RiverRegion[]; bridges?: BridgeSeg[];
  shore_grass?: ShoreSpot[];
  trees?: TreeSpot[]; buildings?: Building[]; animals?: Animal[];
  roads?: RoadSeg[]; walls?: CityWall[]; fields?: FieldPatch[];
  props?: MapProp[];
  cities?: { name: string; x: number; y: number; r: number }[];
  landmarks?: MapLandmark[];
  camera_anchors?: CameraAnchor[];
};

function inferBuildingType(b: Building, genre: string): BuildingType {
  if (b.type === "farmhouse") return "farmhouse";
  if (b.zone === "rural" || /田舍|茅屋|农家|草屋/.test(b.name)) return "farmhouse";
  if (b.type) return b.type;
  const n = b.name;
  if (/飞船港|停靠港|船坞|船港|landing|dock.?alpha|bay/i.test(n)) return "ship_port";
  if (/寺|庙|观|庵|宫观|道观|剑庐|炼丹|问道/.test(n)) return "temple";
  if (/码头|渡口|埠头|渡/.test(n)) return "dock";
  if (/酒肆|酒楼|客栈|构栏|茶楼|茶棚|商|铺|市|行|店|面馆|便利|报亭|酒廊|娱乐|咖啡|仓/.test(n)) {
    return "commercial";
  }
  if (/办公|总部|中枢|ADMIN|DATACORE|BLUESHIELD/i.test(n)) return "office";
  if (/殿|阙|衙|府|厅|署|议会|巡捕|门楼/.test(n)) return "palace";
  if ((genre === "modern" || genre === "scifi" || genre === "securities") && (b.floors || 1) >= 8) return "tower";
  if (genre === "enterprise" && (b.floors || 1) >= 7) return "office";
  if (genre === "military" && /库|仓|车库|弹药/.test(n)) return "commercial";
  if (/居|宅|坊|巷|公寓|栖居|宿舍|厢房/.test(n)) return "residential";
  return "residential";
}

type WorldLoc = { id: string; name: string };

export type CameraMode = "third" | "first";

type Props = {
  genre: string;
  fullscreen?: boolean;
  worldLocations: WorldLoc[];
  agents: Agent[];
  playerId: string | null;
  height?: number;
  cameraMode: CameraMode;
  onCameraModeChange: (m: CameraMode) => void;
  dormant?: boolean;
  onEnterBuilding?: (name: string) => void;
  /** 0–23 world hour for day/night lighting */
  hour?: number;
  /** v1.4 UI-010: WASD exploration + proximity NPC talk */
  explorationEnabled?: boolean;
  presentation?: WorldPresentationStore;
  onMove?: (world_x: number, world_z: number) => void;
  onNearbyNpc?: (npc: Agent | null) => void;
  /** standard | low — from session.world.visual_capabilities.character_lod */
  characterLod?: "standard" | "low";
  /** create/dev compact preview — hide play HUD chrome */
  previewMode?: boolean;
};

function px2world(x: number, y: number, w: number, h: number): [number, number] {
  return [(x - w / 2) * ACTIVE_SCALE, (y - h / 2) * ACTIVE_SCALE];
}

function applyMapScale(map: MapData) {
  const ws = Number(map.terrain?.worldScale);
  ACTIVE_SCALE = SCALE * (Number.isFinite(ws) && ws > 0 ? ws : 1);
}

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function hash2(ix: number, iz: number, seed: number): number {
  let n = (ix * 374761393 + iz * 668265263 + seed * 982451653) | 0;
  n = (n ^ (n >>> 13)) * 1274126177;
  n = n ^ (n >>> 16);
  return (n & 0x7fffffff) / 0x7fffffff;
}

/** Value noise — avoids axis-aligned sin×cos “waffle” grids. */
function valueNoise(x: number, z: number, seed: number): number {
  const x0 = Math.floor(x);
  const z0 = Math.floor(z);
  const fx = x - x0;
  const fz = z - z0;
  const ux = fx * fx * (3 - 2 * fx);
  const uz = fz * fz * (3 - 2 * fz);
  const a = hash2(x0, z0, seed);
  const b = hash2(x0 + 1, z0, seed);
  const c = hash2(x0, z0 + 1, seed);
  const d = hash2(x0 + 1, z0 + 1, seed);
  return a + (b - a) * ux + (c - a) * uz + (a - b - c + d) * ux * uz;
}

/** Domain-warped FBM with rotated octaves — organic ridges, no tic-tac-toe. */
function fbm(x: number, z: number, seed: number): number {
  // Domain warp so contours aren't axis-aligned
  const wx = x + (valueNoise(x * 0.09, z * 0.09, seed + 11) - 0.5) * 18;
  const wz = z + (valueNoise(x * 0.09 + 40, z * 0.09, seed + 29) - 0.5) * 18;
  let amp = 1;
  let freq = 0.035;
  let sum = 0;
  let norm = 0;
  let px = wx;
  let pz = wz;
  for (let o = 0; o < 5; o++) {
    // Rotate sampling axes each octave (~37°)
    const c = Math.cos(o * 0.65);
    const s = Math.sin(o * 0.65);
    const rx = px * c - pz * s;
    const rz = px * s + pz * c;
    sum += amp * (valueNoise(rx * freq * 28, rz * freq * 28, seed + o * 17) * 2 - 1);
    norm += amp;
    amp *= 0.48;
    freq *= 2.05;
    px += 19.1;
    pz += 13.7;
  }
  return sum / (norm || 1);
}

function smoothstep(e0: number, e1: number, x: number): number {
  const t = THREE.MathUtils.clamp((x - e0) / (e1 - e0), 0, 1);
  return t * t * (3 - 2 * t);
}

/**
 * Height field:
 * - soft organic micro-relief (no waffle grid)
 * - huge mountain ridges between cities (peak factions)
 * - city pads flattened so buildings sit like on a plain when close
 */
function peakBoostAt(wx: number, wz: number, map: MapData): number {
  const maxH = map.terrain?.maxHeight ?? 12;
  let boost = 0;
  for (const f of map.factions || []) {
    if (f.terrain !== "peak") continue;
    const [fx, fz] = px2world(f.x, f.y, map.width, map.height);
    const d = Math.hypot(wx - fx, wz - fz);
    const r = Math.max(0.01, f.r * ACTIVE_SCALE);
    if (d > r * 1.35) continue;
    const t = 1 - d / (r * 1.35);
    boost = Math.max(boost, Math.pow(smoothstep(0, 1, t), 1.65) * maxH * 3.6);
  }
  return boost;
}

function distToSegment2D(
  px: number, py: number, ax: number, ay: number, bx: number, by: number,
): number {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  if (len2 < 1e-6) return Math.hypot(px - ax, py - ay);
  let t = ((px - ax) * dx + (py - ay) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  const cx = ax + t * dx;
  const cy = ay + t * dy;
  return Math.hypot(px - cx, py - cy);
}

/** Extra Y so characters stand on raised road slabs (not buried to the waist). */
function roadSurfaceLift(wx: number, wz: number, map: MapData): number {
  let best = Infinity;
  let lift = 0;
  for (const r of map.roads || []) {
    const [ax, az] = px2world(r.from[0], r.from[1], map.width, map.height);
    const [bx, bz] = px2world(r.to[0], r.to[1], map.width, map.height);
    const abx = bx - ax;
    const abz = bz - az;
    const len2 = abx * abx + abz * abz || 1;
    let t = ((wx - ax) * abx + (wz - az) * abz) / len2;
    t = Math.max(0, Math.min(1, t));
    const px = ax + abx * t;
    const pz = az + abz * t;
    const d = Math.hypot(wx - px, wz - pz);
    const kind = r.kind || "dirt";
    const halfW = kind === "cobble" ? 3.9 : kind === "dirt" ? 4.2 : kind === "neon" ? 1.8 : 1.7;
    if (d <= halfW + 0.55 && d < best) {
      best = d;
      lift = kind === "dirt" ? 0.31 : 0.35;
    }
  }
  return lift;
}

function standHeight(wx: number, wz: number, map: MapData): number {
  return heightAt(wx, wz, map) + roadSurfaceLift(wx, wz, map);
}

function heightAt(wx: number, wz: number, map: MapData): number {
  const seed = map.terrain?.seed ?? 1;
  const maxH = map.terrain?.maxHeight ?? 12;
  // Tiny ground noise only — mountains come from peaks, not periodic fbm
  let h = fbm(wx, wz, seed) * 0.35;

  // City pads + mountain peaks from factions / cities
  const cities = map.cities || [];
  for (const f of map.factions || []) {
    const [fx, fz] = px2world(f.x, f.y, map.width, map.height);
    const d = Math.hypot(wx - fx, wz - fz);
    const r = Math.max(0.01, f.r * ACTIVE_SCALE);
    if (d > r * 1.35) continue;
    const t = 1 - d / (r * 1.35);
    const kind = f.terrain || "hill";
    if (kind === "peak") {
      // Broad massifs — wide skirts, soft crowns (no needle spikes under houses)
      const ridge = smoothstep(0, 1, t);
      h += Math.pow(ridge, 1.65) * maxH * 3.6;
    } else if (kind === "hill") {
      h += Math.pow(smoothstep(0, 1, t), 1.45) * maxH * 0.7;
    } else if (kind === "valley") {
      h += t * t * 0.25;
    }
  }

  // Flatten inside each city so streets/buildings share a local "ground plane"
  for (const c of cities) {
    const [cx, cz] = px2world(c.x, c.y, map.width, map.height);
    const d = Math.hypot(wx - cx, wz - cz);
    const r = Math.max(8, c.r * ACTIVE_SCALE * 1.15);
    if (d > r * 1.35) continue;
    // Pad sits at the mountain height sampled at city center (nestled), then flattened
    const [pcx, pcz] = [cx, cz];
    let pad = fbm(pcx, pcz, seed) * 0.35;
    for (const f of map.factions || []) {
      if (f.terrain !== "peak") continue;
      const [fx, fz] = px2world(f.x, f.y, map.width, map.height);
      const pd = Math.hypot(pcx - fx, pcz - fz);
      const pr = Math.max(0.01, f.r * ACTIVE_SCALE);
      if (pd > pr * 1.5) continue;
      const pt = 1 - pd / (pr * 1.5);
      pad += Math.pow(smoothstep(0, 1, pt), 1.65) * maxH * 3.6;
    }
    // Soft plateau: full flat in core, wide blend at rim — no spike teeth inside town
    const flatten = 1 - smoothstep(r * 0.7, r * 1.3, d);
    h = THREE.MathUtils.lerp(h, pad + 0.05, flatten);
    h += (valueNoise(wx * 1.4, wz * 1.4, seed + 7) - 0.5) * 0.025 * flatten;
  }

  for (const w of map.water || []) {
    const [wx0, wz0] = px2world(w.x, w.y, map.width, map.height);
    const dx = (wx - wx0) / Math.max(0.01, w.rx * ACTIVE_SCALE);
    const dz = (wz - wz0) / Math.max(0.01, w.ry * ACTIVE_SCALE);
    const d2 = dx * dx + dz * dz;
    if (d2 < 1.2) {
      const shore = Math.max(0, 1 - d2);
      const waterY = (map.terrain?.waterLevel ?? -0.35) - w.depth * 0.025 * shore;
      const peak = peakBoostAt(wx, wz, map);
      // Never punch lake bowls through mountain massifs — that reads as hollow peaks
      if (peak > 2.2 && h > waterY + 0.6) continue;
      h = Math.min(h, waterY + (1 - shore) * 0.35);
    }
  }

  for (const river of map.rivers || []) {
    const pts = river.points || [];
    const halfW = Math.max(0.6, (river.width || 20) * ACTIVE_SCALE * 0.48);
    for (let i = 0; i < pts.length - 1; i++) {
      const [ax, ay] = pts[i];
      const [bx, by] = pts[i + 1];
      const [wax, waz] = px2world(ax, ay, map.width, map.height);
      const [wbx, wbz] = px2world(bx, by, map.width, map.height);
      const d = distToSegment2D(wx, wz, wax, waz, wbx, wbz);
      if (d >= halfW * 1.25) continue;
      const shore = Math.max(0, 1 - d / (halfW * 1.25));
      const waterY = (map.terrain?.waterLevel ?? -0.35) - 0.06 * shore;
      const peak = peakBoostAt(wx, wz, map);
      if (peak > 2.0 && h > waterY + 0.75) continue;
      h = Math.min(h, waterY + (1 - shore) * 0.22);
    }
  }

  // Grade ONLY steep dirt mountain paths — cut highs down to the ramp.
  // Never raise long cobble arterials (that reads as a 长城 embankment to 大明宫).
  {
    let bestD = Infinity;
    let gradeH = h;
    let blend = 0;
    for (const r of map.roads || []) {
      const kind = r.kind || "dirt";
      if (kind !== "dirt") continue;
      const [ax, az] = px2world(r.from[0], r.from[1], map.width, map.height);
      const [bx, bz] = px2world(r.to[0], r.to[1], map.width, map.height);
      const abx = bx - ax;
      const abz = bz - az;
      const len2 = abx * abx + abz * abz || 1;
      const len = Math.sqrt(len2);
      const h0 = heightAtUngraded(ax, az, map);
      const h1 = heightAtUngraded(bx, bz, map);
      if (Math.abs(h1 - h0) / len < 0.08) continue; // flat dirt — leave terrain alone
      let t = ((wx - ax) * abx + (wz - az) * abz) / len2;
      t = Math.max(0, Math.min(1, t));
      const px = ax + abx * t;
      const pz = az + abz * t;
      const d = Math.hypot(wx - px, wz - pz);
      const halfW = 4.4;
      if (d > halfW + 1.8 || d >= bestD) continue;
      bestD = d;
      gradeH = h0 + (h1 - h0) * t;
      blend = 1 - smoothstep(halfW * 0.3, halfW + 1.6, d);
    }
    if (blend > 0.02 && h > gradeH) {
      // Cut only — never build a raised causeway wall
      h = THREE.MathUtils.lerp(h, gradeH, blend * 0.9);
    }
  }
  return h;
}

/** Terrain height without road-grade blend (avoids recursion). */
function heightAtUngraded(wx: number, wz: number, map: MapData): number {
  const seed = map.terrain?.seed ?? 1;
  const maxH = map.terrain?.maxHeight ?? 12;
  let h = fbm(wx, wz, seed) * 0.35;
  for (const f of map.factions || []) {
    const [fx, fz] = px2world(f.x, f.y, map.width, map.height);
    const d = Math.hypot(wx - fx, wz - fz);
    const r = Math.max(0.01, f.r * ACTIVE_SCALE);
    if (d > r * 1.35) continue;
    const t = 1 - d / (r * 1.35);
    const kind = f.terrain || "hill";
    if (kind === "peak") h += Math.pow(smoothstep(0, 1, t), 1.65) * maxH * 3.6;
    else if (kind === "hill") h += Math.pow(smoothstep(0, 1, t), 1.45) * maxH * 0.7;
    else if (kind === "valley") h += t * t * 0.25;
  }
  for (const c of map.cities || []) {
    const [cx, cz] = px2world(c.x, c.y, map.width, map.height);
    const d = Math.hypot(wx - cx, wz - cz);
    const r = Math.max(8, c.r * ACTIVE_SCALE * 1.15);
    if (d > r * 1.35) continue;
    let pad = fbm(cx, cz, seed) * 0.35;
    for (const f of map.factions || []) {
      if (f.terrain !== "peak" && f.terrain !== "hill") continue;
      const [fx, fz] = px2world(f.x, f.y, map.width, map.height);
      const pd = Math.hypot(cx - fx, cz - fz);
      const pr = Math.max(0.01, f.r * ACTIVE_SCALE);
      if (pd > pr * 1.5) continue;
      const pt = 1 - pd / (pr * 1.5);
      const boost = f.terrain === "peak" ? maxH * 3.6 : maxH * 0.55;
      pad += Math.pow(smoothstep(0, 1, pt), 1.65) * boost;
    }
    const flatten = 1 - smoothstep(r * 0.7, r * 1.3, d);
    h = THREE.MathUtils.lerp(h, pad + 0.05, flatten);
  }
  return h;
}

type DayPalette = {
  bg: string;
  fog: string;
  sun: string;
  sunIntensity: number;
  ambient: number;
  hemiSky: string;
  hemiGround: string;
  sunPos: [number, number, number];
  night: boolean;
};

function dayPalette(hour: number): DayPalette {
  const h = ((hour % 24) + 24) % 24;
  if (h >= 5 && h < 8) {
    return {
      bg: "#1a1520", fog: "#2a2030", sun: "#ffb38a", sunIntensity: 1.05,
      ambient: 0.35, hemiSky: "#ffd6b8", hemiGround: "#2a1f18",
      sunPos: [18, 12, 28], night: false,
    };
  }
  if (h >= 8 && h < 17) {
    return {
      bg: "#87a0b8", fog: "#b8c9d8", sun: "#fff4e0", sunIntensity: 2.05,
      ambient: 0.78, hemiSky: "#e8f0ff", hemiGround: "#5a5044",
      sunPos: [38, 55, 22], night: false,
    };
  }
  if (h >= 17 && h < 20) {
    return {
      bg: "#2a1820", fog: "#4a2830", sun: "#ff7a4a", sunIntensity: 1.15,
      ambient: 0.32, hemiSky: "#ffb08a", hemiGround: "#1a1210",
      sunPos: [-22, 10, 18], night: false,
    };
  }
  return {
    bg: "#05060a", fog: "#0a0c14", sun: "#a8c4ff", sunIntensity: 0.55,
    ambient: 0.32, hemiSky: "#1a2238", hemiGround: "#080604",
    sunPos: [-10, 28, -20], night: true,
  };
}

function Terrain({ map, genre }: { map: MapData; genre: string }) {
  const groundUrl =
    genre === "scifi" ? "/textures/ground/neon.png"
      : genre === "modern" || genre === "mystery" || genre === "enterprise" || genre === "securities"
        ? "/textures/ground/asphalt.png"
        : genre === "military" ? "/textures/ground/dirt.png"
        : "/textures/ground/dirt.png";
  const tex = useLoader(THREE.TextureLoader, groundUrl);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(14, 8);

  const geom = useMemo(() => {
    const w = map.width * ACTIVE_SCALE;
    const h = map.height * ACTIVE_SCALE;
    const g = new THREE.PlaneGeometry(w, h, SEG, SEG);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position;
    const colors = new Float32Array(pos.count * 3);
    const terrainTint: Record<string, [string, string, string, string]> = {
      scifi: ["#1e293b", "#334155", "#64748b", "#0e7490"],
      modern: ["#3f4a3a", "#6b6558", "#c4c0b4", "#c2a878"],
      mystery: ["#2a2e32", "#4a4e48", "#8a8578", "#1e4d6b"],
      enterprise: ["#3d5a54", "#6a8f86", "#c5d5cf", "#5aa8b0"],
      securities: ["#2c3640", "#4a5560", "#9aa4ae", "#2563a8"],
      military: ["#4a4638", "#6b6550", "#a89870", "#6b7a55"],
      xuanhuan: ["#2a1840", "#5a3878", "#c4b0e0", "#6b4a9a"],
      wuxia: ["#2d3d30", "#4a6b48", "#9bb88a", "#5a7a6a"],
      ancient: ["#3d4a38", "#6b5a42", "#d6d0c4", "#c2a878"],
    };
    const [low, mid, high, shore] = terrainTint[genre] || terrainTint.ancient;
    const cLow = new THREE.Color(low);
    const cMid = new THREE.Color(mid);
    const cHigh = new THREE.Color(high);
    const cShore = new THREE.Color(shore);
    const tmp = new THREE.Color();
    const waterY = map.terrain?.waterLevel ?? -0.35;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const z = pos.getZ(i);
      const y = heightAt(x, z, map);
      pos.setY(i, y);
      const t = THREE.MathUtils.clamp((y + 0.5) / 4.5, 0, 1);
      if (y < waterY + 0.35) tmp.copy(cShore);
      else if (t < 0.35) tmp.copy(cLow).lerp(cMid, t / 0.35);
      else tmp.copy(cMid).lerp(cHigh, (t - 0.35) / 0.65);
      colors[i * 3] = tmp.r;
      colors[i * 3 + 1] = tmp.g;
      colors[i * 3 + 2] = tmp.b;
    }
    g.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    g.computeVertexNormals();
    return g;
  }, [map, genre]);

  const baseColor: Record<string, string> = {
    scifi: "#7dd3fc",
    modern: "#a8a29e",
    mystery: "#78716c",
    enterprise: "#94a3b8",
    securities: "#64748b",
    military: "#a8a29e",
    xuanhuan: "#c4b0e0",
    wuxia: "#a3b18a",
    ancient: "#c4b59a",
  };
  return (
    <mesh geometry={geom} receiveShadow castShadow>
      <meshStandardMaterial
        map={tex}
        color={baseColor[genre] || "#c4b59a"}
        vertexColors
        side={THREE.DoubleSide}
        roughness={genre === "scifi" ? 0.78 : 0.92}
        metalness={genre === "scifi" ? 0.12 : genre === "securities" ? 0.06 : 0.04}
      />
    </mesh>
  );
}

function FieldMesh({ field, map, genre }: { field: FieldPatch; map: MapData; genre: string }) {
  const [x, z] = px2world(field.x, field.y, map.width, map.height);
  const y = heightAt(x, z, map) + 0.04;
  // Approximate local slope so paddies don't float as flat cards
  const yx = heightAt(x + 1.5, z, map);
  const yz = heightAt(x, z + 1.5, map);
  const rotX = Math.atan2(y - yz, 1.5);
  const rotZ = Math.atan2(yx - y, 1.5);
  const isPaddy = field.kind === "paddy" || genre === "ancient" || genre === "wuxia";
  const isSpirit = genre === "xuanhuan";
  const isLawn = genre === "enterprise" || genre === "securities" || genre === "modern";
  const color = isSpirit ? "#5b21b6" : isPaddy ? "#4a7c59" : isLawn ? "#65a30d" : genre === "military" ? "#78716c" : genre === "scifi" ? "#0f766e" : "#3f6212";
  const metal = genre === "scifi" ? 0.15 : 0.02;
  return (
    <mesh
      position={[x, y, z]}
      rotation={[rotX - Math.PI / 2, 0, rotZ]}
      receiveShadow
    >
      <planeGeometry args={[field.w * ACTIVE_SCALE * 0.85, field.h * ACTIVE_SCALE * 0.85]} />
      <meshStandardMaterial color={color} roughness={0.96} metalness={metal} transparent opacity={0.88} />
    </mesh>
  );
}

function PostFX({ night, genre }: { night: boolean; genre: string }) {
  /**
   * Black-screen root cause (diagnosed):
   * @react-three/postprocessing defaults EffectComposer to HalfFloatType FBOs.
   * Headless Chromium / some GPU drivers fail the half-float blit → cleared black frame.
   * Fix: UnsignedByteType + no mipmapBlur + antialias off on the Canvas gl context.
   * Keep bloom mild — strong bloom + dark albedo reads as a black frame even when FBO works.
   */
  return (
    <EffectComposer
      multisampling={0}
      frameBufferType={THREE.UnsignedByteType}
    >
      <Bloom
        luminanceThreshold={night ? 0.55 : genre === "scifi" ? 0.78 : 0.94}
        luminanceSmoothing={0.45}
        intensity={night ? 0.35 : genre === "scifi" ? 0.22 : 0.1}
        mipmapBlur={false}
      />
      <Vignette offset={0.32} darkness={night ? 0.4 : 0.28} />
    </EffectComposer>
  );
}

function WaterBody({ w, map }: { w: WaterRegion; map: MapData }) {
  const ref = useRef<THREE.Mesh>(null);
  const [x, z] = px2world(w.x, w.y, map.width, map.height);
  const y = (map.terrain?.waterLevel ?? -0.35) + 0.02;
  const base = useMemo(() => {
    const g = new THREE.PlaneGeometry(w.rx * ACTIVE_SCALE * 2, w.ry * ACTIVE_SCALE * 2, 36, 20);
    // store rest positions in userData
    const pos = g.attributes.position;
    const rest = new Float32Array(pos.count);
    for (let i = 0; i < pos.count; i++) rest[i] = pos.getZ(i);
    (g as any).__restZ = rest;
    return g;
  }, [w.rx, w.ry]);

  useFrame((state) => {
    if (!ref.current) return;
    const g = ref.current.geometry as THREE.PlaneGeometry;
    const pos = g.attributes.position;
    const rest: Float32Array = (g as any).__restZ;
    const t = state.clock.elapsedTime;
    for (let i = 0; i < pos.count; i++) {
      const px = pos.getX(i);
      const py = pos.getY(i);
      const wave =
        Math.sin(px * 1.4 + t * 1.1) * 0.045
        + Math.cos(py * 1.1 + t * 0.85) * 0.03
        + Math.sin((px + py) * 0.55 + t * 0.4) * 0.02;
      pos.setZ(i, (rest?.[i] ?? 0) + wave);
    }
    pos.needsUpdate = true;
    g.computeVertexNormals();
  });

  return (
    <group position={[x, y, z]}>
      <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} geometry={base} receiveShadow>
        <meshPhysicalMaterial
          color="#1a5f78"
          transparent
          opacity={0.78}
          roughness={0.12}
          metalness={0.35}
          transmission={0.15}
          thickness={0.4}
          emissive="#0b3a4a"
          emissiveIntensity={0.12}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.04, 0]}>
        <ringGeometry args={[Math.min(w.rx, w.ry) * ACTIVE_SCALE * 0.92, Math.max(w.rx, w.ry) * ACTIVE_SCALE * 1.05, 64]} />
        <meshStandardMaterial color="#c4a574" transparent opacity={0.35} roughness={1} />
      </mesh>
      {w.diveable && (
        <Html center position={[0, 0.45, 0]} distanceFactor={30}>
          <div className="text-[9px] text-sky-100/85 bg-stone-950/50 px-1.5 py-0.5 rounded pointer-events-none backdrop-blur-sm">
            可下潜 · {w.name || "水域"}
          </div>
        </Html>
      )}
    </group>
  );
}

function RiverBody({ river, map, genre }: { river: RiverRegion; map: MapData; genre: string }) {
  const ref = useRef<THREE.Mesh>(null);
  const waterY = (map.terrain?.waterLevel ?? -0.35) + 0.03;
  const { geom, center } = useMemo(() => {
    const pts = river.points || [];
    if (pts.length < 2) {
      return { geom: new THREE.BufferGeometry(), center: [0, 0] as [number, number] };
    }
    const worldPts = pts.map(([px, py]) => px2world(px, py, map.width, map.height));
    const halfW = Math.max(0.8, (river.width || 20) * ACTIVE_SCALE * 0.5);
    const left: THREE.Vector3[] = [];
    const right: THREE.Vector3[] = [];
    for (let i = 0; i < worldPts.length - 1; i++) {
      const [ax, az] = worldPts[i];
      const [bx, bz] = worldPts[i + 1];
      const len = Math.hypot(bx - ax, bz - az);
      if (len < 0.1) continue;
      const nx = -(bz - az) / len;
      const nz = (bx - ax) / len;
      const samples = Math.max(8, Math.ceil(len * 3));
      for (let s = 0; s <= samples; s++) {
        const t = s / samples;
        const x = ax + (bx - ax) * t;
        const z = az + (bz - az) * t;
        const y = heightAt(x, z, map);
        left.push(new THREE.Vector3(x - nx * halfW, y + 0.02, z - nz * halfW));
        right.push(new THREE.Vector3(x + nx * halfW, y + 0.02, z + nz * halfW));
      }
    }
    if (left.length < 2) {
      return { geom: new THREE.BufferGeometry(), center: worldPts[0] as [number, number] };
    }
    const positions: number[] = [];
    for (let i = 0; i < left.length - 1; i++) {
      const a = left[i]; const b = right[i]; const c = left[i + 1]; const d = right[i + 1];
      positions.push(a.x, waterY, a.z, b.x, waterY, b.z, c.x, waterY, c.z);
      positions.push(b.x, waterY, b.z, d.x, waterY, d.z, c.x, waterY, c.z);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    g.computeVertexNormals();
    const cx = worldPts.reduce((s, p) => s + p[0], 0) / worldPts.length;
    const cz = worldPts.reduce((s, p) => s + p[1], 0) / worldPts.length;
    return { geom: g, center: [cx, cz] as [number, number] };
  }, [river, map]);

  useFrame((state) => {
    if (!ref.current) return;
    const mat = ref.current.material as THREE.MeshPhysicalMaterial;
    mat.emissiveIntensity = 0.1 + Math.sin(state.clock.elapsedTime * 0.8) * 0.03;
  });

  if (!river.points || river.points.length < 2) return null;
  const tint = genre === "scifi" ? "#0ea5e9" : genre === "mystery" ? "#1e4d6b" : "#1a6b88";
  return (
    <group>
      <mesh ref={ref} geometry={geom} receiveShadow>
        <meshPhysicalMaterial
          color={tint}
          transparent
          opacity={0.82}
          roughness={0.1}
          metalness={0.3}
          transmission={0.12}
          emissive="#0a3a4a"
          emissiveIntensity={0.12}
          side={THREE.DoubleSide}
        />
      </mesh>
      {river.name && (
        <Html center position={[center[0], waterY + 0.8, center[1]]} distanceFactor={42}>
          <div className="text-[9px] text-sky-100/80 bg-stone-950/45 px-1.5 py-0.5 rounded pointer-events-none">
            {river.name}
          </div>
        </Html>
      )}
    </group>
  );
}

/** Stone arch bridge — clearly not a wooden dock. */
function BridgeMesh({ bridge, map, genre }: { bridge: BridgeSeg; map: MapData; genre: string }) {
  const [x, z] = px2world(bridge.x, bridge.y, map.width, map.height);
  const waterY = map.terrain?.waterLevel ?? -0.35;
  // Sample banks along span so deck clears water even when center is a river bowl
  const ang = bridge.angle || 0;
  const halfLen = ((bridge.length || 40) * ACTIVE_SCALE) * 0.45;
  const y0 = heightAt(x, z, map);
  const y1 = heightAt(x + Math.sin(ang) * halfLen, z + Math.cos(ang) * halfLen, map);
  const y2 = heightAt(x - Math.sin(ang) * halfLen, z - Math.cos(ang) * halfLen, map);
  const bankY = Math.max(y0, y1, y2);
  const deckY = Math.max(bankY + 0.45, waterY + 1.55);
  const len = (bridge.length || 40) * ACTIVE_SCALE;
  const deckW = genre === "scifi" ? 2.6 : genre === "modern" ? 2.5 : 2.8;
  const stone = genre === "scifi" ? "#64748b" : genre === "modern" ? "#78716c" : "#a8a29e";
  const stoneDark = genre === "scifi" ? "#475569" : "#78716c";
  const rail = genre === "scifi" ? "#94a3b8" : "#57534e";
  const arches = Math.max(2, Math.min(5, Math.floor(len / 4.2)));

  return (
    <group position={[x, 0, z]} rotation={[0, bridge.angle || 0, 0]}>
      {/* Main stone deck */}
      <mesh castShadow receiveShadow position={[0, deckY, 0]}>
        <boxGeometry args={[deckW, 0.38, len]} />
        <meshStandardMaterial color={stone} roughness={0.92} metalness={0.04} />
      </mesh>
      {/* Cobble wearing strip */}
      <mesh receiveShadow position={[0, deckY + 0.2, 0]}>
        <boxGeometry args={[deckW * 0.55, 0.06, len * 0.96]} />
        <meshStandardMaterial color="#d6d3d1" roughness={0.95} />
      </mesh>
      {/* Parapet walls */}
      {([-1, 1] as const).map((side) => (
        <group key={side}>
          <mesh castShadow position={[side * deckW * 0.48, deckY + 0.55, 0]}>
            <boxGeometry args={[0.22, 0.85, len * 0.98]} />
            <meshStandardMaterial color={stoneDark} roughness={0.9} />
          </mesh>
          {Array.from({ length: Math.max(4, Math.floor(len / 1.8)) }, (_, i) => {
            const t = (i + 0.5) / Math.max(4, Math.floor(len / 1.8)) - 0.5;
            return (
              <mesh key={i} castShadow position={[side * deckW * 0.48, deckY + 1.05, t * len * 0.92]}>
                <boxGeometry args={[0.28, 0.28, 0.28]} />
                <meshStandardMaterial color={stone} roughness={0.88} />
              </mesh>
            );
          })}
        </group>
      ))}
      {/* Stone piers + arch rings spanning water */}
      {Array.from({ length: arches }, (_, i) => {
        const t = (i + 0.5) / arches - 0.5;
        const pz = t * len * 0.78;
        const pierH = deckY - waterY - 0.15;
        return (
          <group key={`arch${i}`} position={[0, 0, pz]}>
            {([-1, 1] as const).map((sx) => (
              <mesh key={sx} castShadow position={[sx * deckW * 0.28, waterY + pierH * 0.45, 0]}>
                <boxGeometry args={[deckW * 0.22, pierH * 0.9, 0.85]} />
                <meshStandardMaterial color={stoneDark} roughness={0.94} />
              </mesh>
            ))}
            {/* Arch soffit (half-torus look via scaled cylinder segment) */}
            <mesh
              castShadow
              position={[0, waterY + pierH * 0.55, 0]}
              rotation={[0, 0, Math.PI / 2]}
            >
              <torusGeometry args={[deckW * 0.38, 0.16, 8, 16, Math.PI]} />
              <meshStandardMaterial color={stone} roughness={0.9} side={THREE.DoubleSide} />
            </mesh>
          </group>
        );
      })}
      {/* Short ramps — stay inside deck footprint so they never cover building doors */}
      {([-1, 1] as const).map((end) => (
        <mesh
          key={`ramp${end}`}
          castShadow
          receiveShadow
          position={[0, deckY - 0.12, end * (len * 0.42)]}
          rotation={[end * 0.18, 0, 0]}
        >
          <boxGeometry args={[deckW * 0.9, 0.22, Math.min(1.6, len * 0.18)]} />
          <meshStandardMaterial color={stone} roughness={0.93} />
        </mesh>
      ))}
      {bridge.name && (
        <Html center position={[0, deckY + 2.2, 0]} distanceFactor={28}>
          <div className="text-[9px] px-1.5 py-0.5 rounded bg-stone-900/80 text-stone-100
                          border border-stone-500/50 pointer-events-none tracking-wider">
            {bridge.name}
          </div>
        </Html>
      )}
    </group>
  );
}

function ShoreGrass({ spots, map, genre }: { spots: ShoreSpot[]; map: MapData; genre: string }) {
  const color = genre === "scifi" ? "#4ade80" : genre === "mystery" ? "#65a30d" : "#84cc16";
  const reedColor = genre === "mystery" ? "#a3e635" : "#9acd32";
  return (
    <>
      {spots.map((s, i) => {
        const [x, z] = px2world(s.x, s.y, map.width, map.height);
        const y = heightAt(x, z, map);
        const isReed = s.kind === "reed";
        const h = isReed ? 0.55 + (i % 3) * 0.12 : 0.25 + (i % 4) * 0.06;
        return (
          <group key={i} position={[x, y, z]} rotation={[0, (i * 0.7) % (Math.PI * 2), 0]}>
            {isReed ? (
              <>
                <mesh position={[0, h * 0.5, 0]}>
                  <cylinderGeometry args={[0.02, 0.03, h, 4]} />
                  <meshStandardMaterial color={reedColor} roughness={0.95} />
                </mesh>
                <mesh position={[0.06, h * 0.45, 0.04]}>
                  <cylinderGeometry args={[0.015, 0.025, h * 0.85, 4]} />
                  <meshStandardMaterial color={reedColor} roughness={0.95} />
                </mesh>
              </>
            ) : (
              <>
                <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
                  <circleGeometry args={[0.18 + (i % 3) * 0.04, 6]} />
                  <meshStandardMaterial color={color} transparent opacity={0.75} roughness={1} side={THREE.DoubleSide} />
                </mesh>
                <mesh rotation={[-Math.PI / 2, 0.4, 0]} position={[0.08, 0.03, 0]}>
                  <planeGeometry args={[0.22, 0.14]} />
                  <meshStandardMaterial color={color} transparent opacity={0.65} roughness={1} side={THREE.DoubleSide} />
                </mesh>
              </>
            )}
          </group>
        );
      })}
    </>
  );
}

function Tree({ t, map, genre }: { t: TreeSpot; map: MapData; genre: string }) {
  const [x, z] = px2world(t.x, t.y, map.width, map.height);
  const y = heightAt(x, z, map);
  const seed = hashStr(`${t.x}:${t.y}`);
  const lean = ((seed % 11) - 5) * 0.02;
  const scale = 1.15 + (seed % 5) * 0.18;
  const classic = genre === "ancient" || genre === "wuxia" || genre === "xuanhuan" || genre === "military";
  const canopyByGenre: Record<string, [string, string, string]> = {
    ancient: ["#3f6212", "#4d7c0f", "#5c4033"],
    wuxia: ["#166534", "#15803d", "#4a3728"],
    xuanhuan: ["#4c1d95", "#6b21a8", "#3b0764"],
    mystery: ["#3f4f3a", "#52525b", "#292524"],
    modern: ["#166534", "#4d7c0f", "#57534e"],
    scifi: ["#0f766e", "#14532d", "#334155"],
    enterprise: ["#15803d", "#86efac", "#78716c"],
    securities: ["#4d7c0f", "#a3a3a3", "#44403c"],
    military: ["#3f6212", "#713f12", "#44403c"],
  };
  const [canopy, canopy2, trunk] = canopyByGenre[genre] || canopyByGenre.ancient;

  return (
    <group position={[x, y, z]} rotation={[0, lean * 4, lean]} scale={scale * (genre === "xuanhuan" ? 1.35 : genre === "enterprise" ? 0.85 : 1)}>
      <mesh position={[0, 0.7, 0]} castShadow>
        <cylinderGeometry args={[0.08, 0.14, 1.4, 8]} />
        <meshStandardMaterial color={trunk} roughness={0.95} />
      </mesh>
      {classic ? (
        <>
          <mesh position={[0, 1.55, 0]} castShadow>
            <coneGeometry args={[0.55, 1.35, 8]} />
            <meshStandardMaterial color={canopy} roughness={0.88} />
          </mesh>
          <mesh position={[0, 2.15, 0]} castShadow>
            <coneGeometry args={[0.38, 0.95, 7]} />
            <meshStandardMaterial color={canopy2} roughness={0.88} />
          </mesh>
          <mesh position={[0, 2.6, 0]} castShadow>
            <coneGeometry args={[0.22, 0.55, 6]} />
            <meshStandardMaterial color={canopy} roughness={0.9} />
          </mesh>
        </>
      ) : (
        <>
          <mesh position={[0, 1.55, 0]} castShadow>
            <sphereGeometry args={[0.62, 12, 10]} />
            <meshStandardMaterial color={canopy} roughness={0.85} />
          </mesh>
          <mesh position={[0.22, 1.75, -0.12]} castShadow>
            <sphereGeometry args={[0.42, 10, 8]} />
            <meshStandardMaterial color={canopy2} roughness={0.85} />
          </mesh>
          <mesh position={[-0.24, 1.7, 0.14]} castShadow>
            <sphereGeometry args={[0.36, 10, 8]} />
            <meshStandardMaterial color={canopy} roughness={0.9} />
          </mesh>
        </>
      )}
    </group>
  );
}

function RoadMesh({
  road, map, genre, blendStart, blendEnd, startJunction, endJunction,
  insetStart, insetEnd,
}: {
  road: RoadSeg; map: MapData; genre: string;
  blendStart?: "dirt" | "cobble" | "paved" | "neon" | null;
  blendEnd?: "dirt" | "cobble" | "paved" | "neon" | null;
  startJunction?: boolean;
  endJunction?: boolean;
  insetStart?: number;
  insetEnd?: number;
}) {
  const hAt = useMemo(() => (x: number, z: number) => heightAt(x, z, map), [map]);
  return (
    <SmoothRoad
      road={road}
      genre={genre}
      mapWidth={map.width}
      mapHeight={map.height}
      heightAt={hAt}
      scale={ACTIVE_SCALE}
      blendStart={blendStart ?? null}
      blendEnd={blendEnd ?? null}
      startJunction={!!startJunction}
      endJunction={!!endJunction}
      insetStart={insetStart ?? 0}
      insetEnd={insetEnd ?? 0}
    />
  );
}

function CityWallMesh({ wall, map }: { wall: CityWall; map: MapData }) {
  const geom = useMemo(() => {
    const [cx, cz] = px2world(wall.x, wall.y, map.width, map.height);
    const rx = wall.rx * ACTIVE_SCALE;
    const ry = wall.ry * ACTIVE_SCALE;
    const n = 64;
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= n; i++) {
      const a = (i / n) * Math.PI * 2;
      const x = cx + Math.cos(a) * rx;
      const z = cz + Math.sin(a) * ry;
      pts.push(new THREE.Vector3(x, heightAt(x, z, map) + 0.9, z));
    }
    const curve = new THREE.CatmullRomCurve3(pts, true, "catmullrom", 0.2);
    const shape = new THREE.Shape();
    shape.moveTo(-0.35, -0.95);
    shape.lineTo(0.35, -0.95);
    shape.lineTo(0.4, 0.85);
    shape.lineTo(0.2, 1.05);
    shape.lineTo(-0.2, 1.05);
    shape.lineTo(-0.4, 0.85);
    shape.closePath();
    const g = new THREE.ExtrudeGeometry(shape, {
      steps: n,
      bevelEnabled: false,
      extrudePath: curve,
    });
    g.computeVertexNormals();
    return g;
  }, [wall, map]);

  const [cx, cz] = px2world(wall.x, wall.y, map.width, map.height);
  const r = Math.max(wall.rx, wall.ry) * ACTIVE_SCALE;

  return (
    <group>
      {wall.hasMoat && (
        <mesh position={[cx, (map.terrain?.waterLevel ?? -0.35) + 0.02, cz]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[r * 1.08, r * 1.32, 64]} />
          <meshStandardMaterial color="#1e3a5f" transparent opacity={0.72} roughness={0.35} metalness={0.15} />
        </mesh>
      )}
      <mesh geometry={geom} castShadow receiveShadow>
        <meshStandardMaterial color="#78716c" roughness={0.92} />
      </mesh>
    </group>
  );
}

function BuildingMesh({
  b, map, genre, onEnter, night,
}: {
  b: Building; map: MapData; genre: string; night?: boolean; onEnter?: (n: string) => void;
}) {
  const kind = inferBuildingType(b, genre);
  const p2w = (x: number, y: number) => px2world(x, y, map.width, map.height);
  const hAt = (x: number, z: number) => heightAt(x, z, map);
  if (kind === "dock") {
    return (
      <DetailedDock
        b={{ ...b, type: kind }}
        px2world={p2w}
        waterY={map.terrain?.waterLevel ?? -0.35}
        genre={genre}
      />
    );
  }
  if (kind === "ship_port") {
    return (
      <DetailedShipPort
        b={{ ...b, type: kind }}
        night={night}
        onEnter={onEnter}
        px2world={p2w}
        heightAt={hAt}
        genre={genre}
      />
    );
  }
  return (
    <DetailedBuilding
      b={{ ...b, type: kind }}
      genre={genre}
      night={night}
      onEnter={onEnter}
      px2world={p2w}
      heightAt={hAt}
      mapW={map.width}
      mapH={map.height}
    />
  );
}

function StreetPropMesh({
  prop, map, genre, night,
}: {
  prop: MapProp; map: MapData; genre: string; night?: boolean;
}) {
  const [x, z] = px2world(prop.x, prop.y, map.width, map.height);
  const y = heightAt(x, z, map) + 0.02;
  const yaw = prop.rot ?? 0;
  const s = prop.scale ?? 1;
  const kind = prop.kind;
  const hy = resolvePropModel(genre, kind);
  // Prefer Hunyuan3D GLB for named props when available
  if (hy && ["lantern", "banner", "wine_jar", "stone_lion", "well"].includes(kind)) {
    return (
      <group position={[x, y, z]} rotation={[0, yaw, 0]} scale={[s, s, s]}>
        <KitErrorBoundary fallback={
          <mesh position={[0, 0.4, 0]} castShadow>
            <boxGeometry args={[0.35, 0.8, 0.35]} />
            <meshStandardMaterial color="#6b5b4a" />
          </mesh>
        }>
          <Suspense fallback={null}>
            <KitBuildingMesh model={hy} targetW={1.4} targetD={1.4} floors={1} night={night} />
          </Suspense>
        </KitErrorBoundary>
      </group>
    );
  }
  return (
    <group position={[x, y, z]} rotation={[0, yaw, 0]} scale={[s, s, s]}>
      {kind === "lantern" && (
        <>
          <mesh position={[0, 1.05, 0]} castShadow>
            <cylinderGeometry args={[0.04, 0.05, 2.1, 8]} />
            <meshStandardMaterial color="#3f2a1f" roughness={0.85} />
          </mesh>
          <mesh position={[0, 2.2, 0]} castShadow>
            <sphereGeometry args={[0.22, 12, 12]} />
            <meshStandardMaterial
              color="#fde68a"
              emissive="#fbbf24"
              emissiveIntensity={night ? 1.2 : 0.45}
              roughness={0.4}
            />
          </mesh>
        </>
      )}
      {kind === "banner" && (
        <>
          <mesh position={[0, 1.3, 0]} castShadow>
            <cylinderGeometry args={[0.04, 0.05, 2.6, 8]} />
            <meshStandardMaterial color="#3f2a1f" />
          </mesh>
          <mesh position={[0.32, 1.7, 0]} castShadow>
            <boxGeometry args={[0.55, 1.2, 0.04]} />
            <meshStandardMaterial color="#b91c1c" roughness={0.7} />
          </mesh>
        </>
      )}
      {kind === "wine_jar" && (
        <mesh position={[0, 0.35, 0]} castShadow>
          <cylinderGeometry args={[0.28, 0.34, 0.7, 14]} />
          <meshStandardMaterial color="#92400e" roughness={0.75} />
        </mesh>
      )}
      {kind === "stone_lion" && (
        <mesh position={[0, 0.5, 0]} castShadow>
          <boxGeometry args={[0.55, 1.0, 0.55]} />
          <meshStandardMaterial color="#d6d3d1" roughness={0.88} />
        </mesh>
      )}
      {kind === "well" && (
        <mesh position={[0, 0.4, 0]} castShadow>
          <cylinderGeometry args={[0.65, 0.72, 0.8, 16]} />
          <meshStandardMaterial color="#78716c" roughness={0.95} />
        </mesh>
      )}
      {!["lantern", "banner", "wine_jar", "stone_lion", "well"].includes(kind) && (
        <mesh position={[0, 0.3, 0]} castShadow>
          <boxGeometry args={[0.4, 0.6, 0.4]} />
          <meshStandardMaterial color="#6b5b4a" />
        </mesh>
      )}
    </group>
  );
}

function LandmarkMarkers({ map, night }: { map: MapData; night?: boolean }) {
  const landmarks = map.landmarks || [];
  if (!landmarks.length) return null;
  return (
    <group>
      {landmarks.map((lm) => {
        const [x, z] = px2world(lm.x, lm.y, map.width, map.height);
        const y = heightAt(x, z, map);
        const primary = lm.tier === "primary";
        return (
          <group key={lm.id} position={[x, y, z]}>
            {primary && (
              <>
                <mesh position={[0, 10, 0]} castShadow>
                  <cylinderGeometry args={[0.06, 0.2, 18, 10]} />
                  <meshStandardMaterial
                    color="#fbbf24"
                    emissive="#f59e0b"
                    emissiveIntensity={night ? 1.1 : 0.55}
                    transparent
                    opacity={0.42}
                  />
                </mesh>
                <pointLight position={[0, 14, 0]} intensity={night ? 2.2 : 1.1} distance={32} color="#fcd34d" />
              </>
            )}
            {primary && (
              <Html position={[0, 16, 0]} center distanceFactor={38}>
                <div className="font-serif text-[11px] px-2 py-0.5 rounded
                                bg-amber-950/80 border border-amber-500/50 text-amber-100
                                pointer-events-none whitespace-nowrap shadow-lg">
                  ★ {lm.name}
                </div>
              </Html>
            )}
          </group>
        );
      })}
    </group>
  );
}

function StreetPedestrians({ map, genre }: { map: MapData; genre: string }) {
  const roads = map.roads || [];
  const people = useMemo(() => {
    const out: { id: number; ax: number; az: number; bx: number; bz: number; speed: number; phase: number; side: number; profession: string }[] = [];
    let id = 0;
    const professions = genre === "ancient"
      ? ["行商", "书生", "镖师", "小吏", "农人", "船工", "酒客", "脚夫", "铁匠", "说书"]
      : ["行人", "路人"];
    // Prefer market / short urban segments so walkers read on the cross streets
    const ranked = [...roads].sort((a, b) => {
      const la = Math.hypot(a.to[0] - a.from[0], a.to[1] - a.from[1]);
      const lb = Math.hypot(b.to[0] - b.from[0], b.to[1] - b.from[1]);
      return la - lb;
    });
    for (const road of ranked.slice(0, 12)) {
      const [ax, az] = px2world(road.from[0], road.from[1], map.width, map.height);
      const [bx, bz] = px2world(road.to[0], road.to[1], map.width, map.height);
      const len = Math.hypot(bx - ax, bz - az);
      if (len < 6) continue;
      const n = len > 22 ? 3 : 2;
      for (let i = 0; i < n; i++) {
        const h = hashStr(`${road.from}${road.to}${i}`);
        out.push({
          id: id++,
          ax, az, bx, bz,
          speed: 0.07 + (h % 5) * 0.01,
          phase: (h % 100) / 100,
          side: i % 2 === 0 ? 1 : -1,
          profession: professions[h % professions.length],
        });
      }
      if (out.length > 28) break;
    }
    return out;
  }, [map, roads, genre]);

  const popPresets = useMemo(() => people.map((p) => ({
    ...p,
    preset: resolveFigure(
      { id: `ped-${p.id}`, name: `${p.profession}${p.id}`, profession: p.profession } as Agent,
      genre,
    ),
  })), [people, genre]);

  return (
    <group>
      {popPresets.map(({ preset, ...p }) => (
        <StreetWalkerGltf key={p.id} p={p} map={map} preset={preset} />
      ))}
    </group>
  );
}

function StreetWalkerGltf({
  p, map, preset,
}: {
  p: { id: number; ax: number; az: number; bx: number; bz: number; speed: number; phase: number; side: number };
  map: MapData;
  preset: ReturnType<typeof resolveFigure>;
}) {
  const ref = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!ref.current) return;
    const t = (state.clock.elapsedTime * p.speed + p.phase) % 1;
    const ping = t < 0.5 ? t * 2 : 2 - t * 2;
    const x = p.ax + (p.bx - p.ax) * ping;
    const z = p.az + (p.bz - p.az) * ping;
    const dx = p.bx - p.ax;
    const dz = p.bz - p.az;
    const len = Math.hypot(dx, dz) || 1;
    // Stay on carriageway (dirt halfW ≈ 3.9); dual lanes inside the strip
    const lane = 1.15;
    const ox = (-dz / len) * lane * p.side;
    const oz = (dx / len) * lane * p.side;
    const wx = x + ox;
    const wz = z + oz;
    ref.current.position.set(wx, standHeight(wx, wz, map), wz);
    ref.current.rotation.y = Math.atan2(dx, dz) + (t < 0.5 ? 0 : Math.PI);
  });
  return (
    <group ref={ref}>
      <HumanoidFigure preset={preset} scale={0.82} behavior="walk" />
    </group>
  );
}

function AnimalMesh({ a, map }: { a: Animal; map: MapData }) {
  const ref = useRef<THREE.Group>(null);
  const [x, z] = px2world(a.x, a.y, map.width, map.height);
  const baseY = heightAt(x, z, map);
  const seed = hashStr(a.name);

  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.elapsedTime + seed * 0.01;
    if (a.behavior === "swim" || a.species === "fish") {
      ref.current.position.x = x + Math.sin(t * 0.7) * 1.2;
      ref.current.position.z = z + Math.cos(t * 0.55) * 0.8;
      ref.current.position.y = (map.terrain?.waterLevel ?? -0.35) + 0.15;
      ref.current.rotation.y = Math.sin(t * 0.7) * 0.5;
    } else {
      ref.current.position.x = x + Math.sin(t * 0.4) * 0.6;
      ref.current.position.z = z + Math.cos(t * 0.35) * 0.6;
      const gy = heightAt(ref.current.position.x, ref.current.position.z, map);
      ref.current.position.y = gy + 0.15;
    }
  });

  const isFish = a.species === "fish";
  return (
    <group ref={ref} position={[x, baseY + 0.15, z]}>
      <mesh castShadow>
        {isFish ? <capsuleGeometry args={[0.08, 0.25, 4, 8]} /> : <capsuleGeometry args={[0.12, 0.35, 4, 8]} />}
        <meshStandardMaterial color={isFish ? "#f97316" : "#a16207"} roughness={0.55} />
      </mesh>
      {!isFish && (
        <mesh position={[0.22, 0.12, 0]} castShadow>
          <sphereGeometry args={[0.12, 8, 8]} />
          <meshStandardMaterial color="#a16207" />
        </mesh>
      )}
    </group>
  );
}

function DynamicAgent({
  agent, map, coordsByLocId, isPlayer, hideBody, dormant, registerPlayer, genre,
  presentation, localControl, playerRef, characterLod,
}: {
  agent: Agent; map: MapData;
  coordsByLocId: Record<string, [number, number]>;
  isPlayer: boolean; hideBody?: boolean; dormant?: boolean;
  registerPlayer?: (obj: THREE.Object3D | null) => void;
  genre: string;
  presentation?: WorldPresentationStore;
  localControl?: boolean;
  playerRef?: React.MutableRefObject<THREE.Object3D | null>;
  characterLod?: "standard" | "low";
}) {
  const ref = useRef<THREE.Group>(null);
  const [labelVisible, setLabelVisible] = useState(true);
  const pose = presentation?.getInterpolated(agent.id);
  const wx = pose?.x ?? agent.world_x ?? 0;
  const wz = pose?.z ?? agent.world_z ?? 0;
  const fallback = agent.location_id ? coordsByLocId[agent.location_id] : null;
  const baseX = wx !== 0 || wz !== 0 ? wx / 2 * map.width * ACTIVE_SCALE : (fallback?.[0] ?? 0);
  const baseZ = wx !== 0 || wz !== 0 ? wz / 2 * map.height * ACTIVE_SCALE : (fallback?.[1] ?? 0);

  useEffect(() => {
    if (isPlayer) registerPlayer?.(ref.current);
    return () => { if (isPlayer) registerPlayer?.(null); };
  }, [isPlayer, registerPlayer]);

  useFrame(() => {
    if (!ref.current) return;
    if (playerRef?.current && !isPlayer) {
      const dist = ref.current.position.distanceTo(playerRef.current.position);
      const next = dist < (characterLod === "low" ? 28 : 42);
      setLabelVisible((prev) => (prev === next ? prev : next));
    }
    if (isPlayer && localControl) {
      const gy = standHeight(ref.current.position.x, ref.current.position.z, map);
      const targetY = gy + (agent.behavior === "swim" ? -0.35 : 0);
      ref.current.position.y += (targetY - ref.current.position.y) * 0.2;
      registerPlayer?.(ref.current);
      return;
    }
    const ip = presentation?.getInterpolated(agent.id);
    const ix = ip?.x ?? agent.world_x ?? 0;
    const iz = ip?.z ?? agent.world_z ?? 0;
    const tx = ix !== 0 || iz !== 0 ? (ix / 2) * map.width * ACTIVE_SCALE : baseX;
    const tz = ix !== 0 || iz !== 0 ? (iz / 2) * map.height * ACTIVE_SCALE : baseZ;
    const nextX = ref.current.position.x + (tx - ref.current.position.x) * 0.14;
    const nextZ = ref.current.position.z + (tz - ref.current.position.z) * 0.14;
    const [rx, rz] = resolveBuildingMove(
      map, ACTIVE_SCALE,
      ref.current.position.x, ref.current.position.z, nextX, nextZ, 0.35,
    );
    ref.current.position.x = rx;
    ref.current.position.z = rz;
    const gy = standHeight(ref.current.position.x, ref.current.position.z, map);
    const targetY = gy + (agent.behavior === "swim" ? -0.35 : 0);
    ref.current.position.y += (targetY - ref.current.position.y) * 0.2;
    if (isPlayer) registerPlayer?.(ref.current);
  });

  const preset = resolveFigure(agent, genre);
  const showNameplate = isPlayer || labelVisible;

  return (
    <group ref={ref} position={[baseX, standHeight(baseX, baseZ, map), baseZ]}>
      {!hideBody && (
        <>
          <HumanoidFigure
            preset={preset}
            behavior={agent.behavior}
            dormant={dormant && isPlayer}
            highlight={isPlayer}
            scale={isPlayer ? 1.05 : 1}
          />
          {showNameplate && (
            <Html position={[0, 2.2, 0]} center distanceFactor={16}>
              <div className={`px-1.5 py-0.5 text-[10px] rounded whitespace-nowrap pointer-events-none font-serif border shadow
                ${isPlayer
                  ? "bg-amber-400/95 text-stone-900 border-amber-200"
                  : "bg-stone-950/85 text-stone-100 border-stone-600"}`}>
                {agent.name}
                {agent.behavior && agent.behavior !== "idle" && (
                  <span className="opacity-70 ml-1">·{_behaviorLabel(agent.behavior)}</span>
                )}
              </div>
            </Html>
          )}
          {isPlayer && (
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
              <ringGeometry args={[0.35, 0.48, 32]} />
              <meshBasicMaterial color="#fbbf24" transparent opacity={0.55} depthWrite={false} />
            </mesh>
          )}
        </>
      )}
    </group>
  );
}

function _behaviorLabel(b: string): string {
  const m: Record<string, string> = {
    walk: "行走", work: "劳作", drink: "饮酒", farm: "耕作",
    climb: "攀爬", swim: "游水", idle: "静候",
  };
  return m[b] || b;
}

const PROXIMITY_RADIUS = 3.2;
const MOVE_SPEED = 0.11;

function ExplorationController({
  map, agents, playerId, playerRef, presentation, onMove, onNearbyNpc, enabled, dormant,
}: {
  map: MapData;
  agents: Agent[];
  playerId: string | null;
  playerRef: React.MutableRefObject<THREE.Object3D | null>;
  presentation?: WorldPresentationStore;
  onMove?: (world_x: number, world_z: number) => void;
  onNearbyNpc?: (npc: Agent | null) => void;
  enabled?: boolean;
  dormant?: boolean;
}) {
  const keys = useRef({ w: false, a: false, s: false, d: false });
  const lastSend = useRef(0);
  const lastNpc = useRef<Agent | null>(null);

  useEffect(() => {
    if (!enabled || dormant) return;
    const down = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      if (k === "w" || k === "a" || k === "s" || k === "d") keys.current[k] = true;
    };
    const up = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      if (k === "w" || k === "a" || k === "s" || k === "d") keys.current[k] = false;
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [enabled, dormant]);

  useFrame(() => {
    if (!enabled || dormant || !playerId) return;
    const g = playerRef.current;
    if (!g) return;

    let dx = 0;
    let dz = 0;
    if (keys.current.w) dz -= MOVE_SPEED;
    if (keys.current.s) dz += MOVE_SPEED;
    if (keys.current.a) dx -= MOVE_SPEED;
    if (keys.current.d) dx += MOVE_SPEED;
    if (dx || dz) {
      const ox = g.position.x;
      const oz = g.position.z;
      const [nx, nz] = resolveBuildingMove(
        map, ACTIVE_SCALE, ox, oz, ox + dx, oz + dz, 0.4,
      );
      g.position.x = nx;
      g.position.z = nz;
      const [wx, wz] = worldNormFromScene(g.position.x, g.position.z, map.width, map.height, ACTIVE_SCALE);
      presentation?.setLocal(playerId, wx, wz);
      const now = performance.now();
      if (now - lastSend.current > 90) {
        lastSend.current = now;
        onMove?.(wx, wz);
      }
    }

    let best: Agent | null = null;
    let bestD = PROXIMITY_RADIUS;
    for (const a of agents) {
      if (a.kind !== "npc" || a.id === playerId) continue;
      const ip = presentation?.getInterpolated(a.id);
      const ax = ((ip?.x ?? a.world_x ?? 0) / 2) * map.width * ACTIVE_SCALE;
      const az = ((ip?.z ?? a.world_z ?? 0) / 2) * map.height * ACTIVE_SCALE;
      const d = Math.hypot(g.position.x - ax, g.position.z - az);
      if (d < bestD) {
        bestD = d;
        best = a;
      }
    }
    if (best?.id !== lastNpc.current?.id) {
      lastNpc.current = best;
      onNearbyNpc?.(best);
    }
  });

  return null;
}

function OrbitFollow({
  target, camDist, focus, freeExplore = false,
}: {
  target: React.MutableRefObject<THREE.Object3D | null>;
  camDist: number;
  /** World-space look-at when no player (map preview). */
  focus?: [number, number, number];
  /** Map browser: pan/zoom/click freely — do NOT lock target to focus every frame. */
  freeExplore?: boolean;
}) {
  const controls = useRef<any>(null);
  const look = useRef(new THREE.Vector3());
  const primed = useRef(false);
  const { camera, gl, scene } = useThree();
  const focusV = useMemo(
    () => new THREE.Vector3(...(focus ?? [0, 0.6, 0])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [focus?.[0], focus?.[1], focus?.[2]],
  );

  useEffect(() => {
    primed.current = false;
  }, [focusV.x, focusV.y, focusV.z, camDist]);

  // Click terrain / buildings to re-center look-at (free explore)
  useEffect(() => {
    if (!freeExplore) return;
    const el = gl.domElement;
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let downX = 0;
    let downY = 0;

    const onDown = (e: PointerEvent) => {
      downX = e.clientX;
      downY = e.clientY;
    };
    const onUp = (e: PointerEvent) => {
      if (!controls.current) return;
      // Ignore drags — only treat as click-to-focus
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) return;
      if (e.button !== 0) return;
      const rect = el.getBoundingClientRect();
      pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(scene.children, true);
      const hit = hits.find((h) => {
        const n = (h.object.name || "") + (h.object.parent?.name || "");
        // Prefer ground-ish hits; skip HTML sprites / lights
        return h.face && h.distance < camDist * 4;
      });
      if (hit) {
        controls.current.target.set(hit.point.x, hit.point.y + 0.4, hit.point.z);
        controls.current.update();
      }
    };
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointerup", onUp);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointerup", onUp);
    };
  }, [freeExplore, camera, gl, scene, camDist]);

  useFrame(({ camera: cam }) => {
    if (!controls.current) return;
    const following = !!target.current && !freeExplore;
    if (following) {
      look.current.set(
        target.current!.position.x,
        target.current!.position.y + 1.15,
        target.current!.position.z,
      );
      controls.current.target.lerp(look.current, primed.current ? 0.18 : 1);
    }
    if (!primed.current) {
      if (following) {
        const dist = Math.min(11, Math.max(6.5, camDist * 0.12));
        cam.position.set(
          look.current.x + dist * 0.55,
          look.current.y + dist * 0.42,
          look.current.z + dist * 0.72,
        );
        controls.current.target.copy(look.current);
      } else {
        // Overview framing — whole district visible, then user pans freely
        const dist = Math.max(45, Math.min(camDist * 0.55, 140));
        controls.current.target.copy(focusV);
        cam.position.set(
          focusV.x + dist * 0.55,
          focusV.y + dist * 0.62,
          focusV.z + dist * 0.7,
        );
      }
      primed.current = true;
    }
    controls.current.update();
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enablePan
      screenSpacePanning
      maxPolarAngle={Math.PI / 2.2}
      minPolarAngle={0.12}
      minDistance={freeExplore ? 8 : 6}
      maxDistance={camDist * (freeExplore ? 4.5 : 3.2)}
      rotateSpeed={0.7}
      zoomSpeed={1.15}
      panSpeed={1.1}
      // Map browser: left-drag pans, right rotates (click still recenters)
      mouseButtons={freeExplore
        ? { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE }
        : { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN }}
    />
  );
}

function InteriorRoom({ name, onExit, night }: { name: string; onExit: () => void; night?: boolean }) {
  const kind = /紫宸|宫|殿/.test(name) ? "palace"
    : /古观|寺|庙|观/.test(name) ? "temple"
      : /醉仙|酒肆|酒楼/.test(name) ? "tavern"
        : "hall";
  const wall = kind === "palace" ? "#7f1d1d" : kind === "temple" ? "#e7e5e4" : "#5c4033";
  const floor = kind === "palace" ? "#9f1239" : kind === "temple" ? "#d6d3d1" : "#292524";
  const light = kind === "temple" ? "#fef3c7" : "#fbbf24";
  return (
    <>
      <color attach="background" args={[night ? "#120f0e" : kind === "temple" ? "#292524" : "#1c1917"]} />
      <fog attach="fog" args={[night ? "#120f0e" : "#1c1917", 4, 14]} />
      <ambientLight intensity={night ? 0.25 : 0.45} />
      <pointLight position={[1.5, 2.4, 1.2]} intensity={night ? 1.4 : 0.9} color={light} castShadow />
      <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[10, 10]} />
        <meshStandardMaterial color={floor} roughness={0.95} />
      </mesh>
      {([[0, 1.6, -3.2, 8, 3.2, 0.2], [0, 1.6, 3.2, 8, 3.2, 0.2],
         [-3.2, 1.6, 0, 0.2, 3.2, 8], [3.2, 1.6, 0, 0.2, 3.2, 8]] as const).map((b, i) => (
        <mesh key={i} position={[b[0], b[1], b[2]]} castShadow receiveShadow>
          <boxGeometry args={[b[3], b[4], b[5]]} />
          <meshStandardMaterial color={wall} roughness={0.9} />
        </mesh>
      ))}
      {kind === "tavern" && (
        <>
          <mesh position={[0, 0.55, -1.2]} castShadow>
            <boxGeometry args={[3.2, 0.9, 0.6]} />
            <meshStandardMaterial color="#78350f" roughness={0.8} />
          </mesh>
          {[-1.2, 0, 1.2].map((x, i) => (
            <mesh key={i} position={[x, 1.15, -1.15]} castShadow>
              <cylinderGeometry args={[0.16, 0.18, 0.45, 10]} />
              <meshStandardMaterial color="#92400e" roughness={0.7} />
            </mesh>
          ))}
          <mesh position={[-1.4, 0.4, 1.2]} castShadow>
            <boxGeometry args={[0.7, 0.7, 0.7]} />
            <meshStandardMaterial color="#44403c" />
          </mesh>
        </>
      )}
      {kind === "palace" && (
        <>
          <mesh position={[0, 0.45, -1.6]} castShadow>
            <boxGeometry args={[2.2, 0.7, 1.2]} />
            <meshStandardMaterial color="#b45309" roughness={0.6} metalness={0.2} />
          </mesh>
          <mesh position={[0, 1.2, -1.6]} castShadow>
            <boxGeometry args={[1.1, 1.0, 0.5]} />
            <meshStandardMaterial color="#ca8a04" roughness={0.4} metalness={0.35} />
          </mesh>
          {[-2.2, 2.2].map((x, i) => (
            <mesh key={i} position={[x, 1.5, -0.5]} castShadow>
              <cylinderGeometry args={[0.12, 0.14, 2.8, 10]} />
              <meshStandardMaterial color="#9f1239" />
            </mesh>
          ))}
        </>
      )}
      {kind === "temple" && (
        <>
          <mesh position={[0, 0.5, -1.4]} castShadow>
            <boxGeometry args={[2.4, 0.8, 0.9]} />
            <meshStandardMaterial color="#78716c" roughness={0.85} />
          </mesh>
          <mesh position={[0, 1.35, -1.4]} castShadow>
            <boxGeometry args={[0.9, 0.9, 0.4]} />
            <meshStandardMaterial color="#fafaf9" roughness={0.7} />
          </mesh>
          <mesh position={[0, 0.3, 1.0]} castShadow>
            <cylinderGeometry args={[0.45, 0.5, 0.35, 16]} />
            <meshStandardMaterial color="#57534e" />
          </mesh>
        </>
      )}
      {kind === "hall" && (
        <>
          <mesh position={[-1.2, 0.45, 0.8]} castShadow>
            <boxGeometry args={[1.4, 0.7, 0.7]} />
            <meshStandardMaterial color="#78350f" roughness={0.8} />
          </mesh>
          <mesh position={[1.1, 0.9, -1.5]} castShadow>
            <boxGeometry args={[0.9, 1.6, 0.4]} />
            <meshStandardMaterial color="#57534e" />
          </mesh>
        </>
      )}
      <Html center position={[0, 2.6, 0]}>
        <div className="text-center">
          <div className="font-serif text-amber-100 text-sm mb-2 drop-shadow">{name} · 室内</div>
          <button type="button" onClick={onExit}
            className="text-[11px] px-3 py-1 rounded bg-stone-800/90 text-stone-100 border border-stone-600">
            离开建筑
          </button>
        </div>
      </Html>
    </>
  );
}

function Atmosphere({ palette, genre }: { palette: DayPalette; genre: string }) {
  const fogNear = palette.night ? 60 : 100;
  const fogFar = palette.night ? 420 : 900;
  return (
    <>
      <color attach="background" args={[palette.bg]} />
      <fog attach="fog" args={[palette.fog, fogNear, fogFar]} />
      {!palette.night && (
        <Sky
          distance={450000}
          sunPosition={palette.sunPos}
          inclination={0.49}
          azimuth={0.25}
          mieCoefficient={0.004}
          rayleigh={palette.sunIntensity > 1.3 ? 2.2 : 1.2}
        />
      )}
      {palette.night && <Stars radius={80} depth={40} count={1600} factor={3.2} saturation={0} fade speed={0.4} />}
      {!palette.night && genre !== "mystery" && (
        <Cloud position={[8, 16, -12]} opacity={0.28} speed={0.15} bounds={[12, 2, 8]} segments={12} />
      )}
    </>
  );
}

function SceneInner(props: {
  map: MapData; genre: string; agents: Agent[]; playerId: string | null;
  coordsByLocId: Record<string, [number, number]>; camDist: number;
  cameraMode: CameraMode; dormant?: boolean; hour: number;
  interior: string | null;
  onEnterBuilding: (name: string) => void;
  onExitBuilding: () => void;
  explorationEnabled?: boolean;
  presentation?: WorldPresentationStore;
  onMove?: (world_x: number, world_z: number) => void;
  onNearbyNpc?: (npc: Agent | null) => void;
  characterLod?: "standard" | "low";
}) {
  const {
    map, genre, agents, playerId, coordsByLocId, camDist, cameraMode, dormant,
    hour, interior, onEnterBuilding, onExitBuilding,
    explorationEnabled, presentation, onMove, onNearbyNpc, characterLod,
  } = props;
  applyMapScale(map);
  const playerRef = useRef<THREE.Object3D | null>(null);
  const palette = useMemo(() => dayPalette(hour), [hour]);
  const registerPlayer = (obj: THREE.Object3D | null) => { playerRef.current = obj; };
  const roadBlends = useMemo(
    () => roadEndBlendKinds(map.roads || [], genre, ACTIVE_SCALE),
    [map.roads, genre],
  );

  const mapFocus = useMemo((): [number, number, number] => {
    const anchors = map.camera_anchors || [];
    const spawn = anchors.find((a) => a.role === "spawn") || anchors[0];
    if (spawn) {
      const [x, z] = px2world(spawn.x, spawn.y, map.width, map.height);
      return [x, heightAt(x, z, map) + 1.6, z];
    }
    // Frame the densest non-stall buildings of the first city (not empty geometric center)
    const cities = map.cities || [];
    const list = map.buildings || [];
    if (cities.length) {
      const c = cities[0];
      const inCity = list.filter((b) => {
        if (b.type === "stall" || b.type === "dock") return false;
        return Math.hypot(b.x - c.x, b.y - c.y) <= c.r * 1.05;
      });
      const pool = inCity.length ? inCity : list.filter((b) => b.type !== "stall");
      if (pool.length) {
        const cx = pool.reduce((s, b) => s + b.x, 0) / pool.length;
        const cy = pool.reduce((s, b) => s + b.y, 0) / pool.length;
        const [x, z] = px2world(cx, cy, map.width, map.height);
        return [x, heightAt(x, z, map) + 1.5, z];
      }
      const [x, z] = px2world(c.x, c.y, map.width, map.height);
      return [x, heightAt(x, z, map) + 1.4, z];
    }
    if (!list.length) return [0, 1.2, 0];
    const hubs = list.filter((b) =>
      ["palace", "temple", "tower", "commercial", "ship_port", "office"].includes(b.type || ""),
    );
    const pool = hubs.length >= 2 ? hubs : list;
    let best = pool[0];
    let bestN = -1;
    for (const b of pool) {
      let n = 0;
      for (const o of list) {
        if (Math.hypot(o.x - b.x, o.y - b.y) < 90) n++;
      }
      if (n > bestN) {
        bestN = n;
        best = b;
      }
    }
    const [x, z] = px2world(best.x, best.y, map.width, map.height);
    return [x, heightAt(x, z, map) + 1.5, z];
  }, [map]);

  if (interior) {
    return <InteriorRoom name={interior} onExit={onExitBuilding} night={palette.night} />;
  }

  return (
    <>
      <Atmosphere palette={palette} genre={genre} />
      <ambientLight intensity={palette.ambient * (genre === "scifi" ? 1.35 : 1.2)} />
      <hemisphereLight args={[palette.hemiSky, palette.hemiGround, genre === "scifi" ? 0.95 : 0.78]} />
      <directionalLight
        position={palette.sunPos}
        intensity={palette.sunIntensity * (genre === "scifi" ? 1.05 : 0.9)}
        color={palette.sun}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-far={280}
        shadow-camera-left={-90}
        shadow-camera-right={90}
        shadow-camera-top={90}
        shadow-camera-bottom={-90}
        shadow-bias={-0.0002}
      />
      {/* fill light softens pitch-black lee sides */}
      <directionalLight
        position={[-palette.sunPos[0] * 0.6, 28, -palette.sunPos[2] * 0.5]}
        intensity={genre === "scifi" ? 0.55 : 0.42}
        color="#dbeafe"
      />
      {palette.night && (
        <>
          <directionalLight position={[6, 20, -8]} intensity={0.4} color="#64748b" />
          <pointLight position={[mapFocus[0], 6, mapFocus[2]]} intensity={1.2} color="#f59e0b" distance={40} />
        </>
      )}

      <Suspense fallback={null}>
        <Terrain map={map} genre={genre} />
        {(map.fields || []).filter((_, i) => i % 2 === 0).map((f, i) => (
          <FieldMesh key={`fd${i}`} field={f} map={map} genre={genre} />
        ))}
        {(map.water || []).map((w, i) => <WaterBody key={i} w={w} map={map} />)}
        {(map.rivers || []).map((r, i) => <RiverBody key={`rv${i}`} river={r} map={map} genre={genre} />)}
        {(map.shore_grass?.length ?? 0) > 0 && (
          <ShoreGrass spots={map.shore_grass!} map={map} genre={genre} />
        )}
        {(map.bridges || []).map((b, i) => <BridgeMesh key={`br${i}`} bridge={b} map={map} genre={genre} />)}
        {(map.roads || []).map((r, i) => (
          <RoadMesh
            key={`rd${i}`}
            road={r}
            map={map}
            genre={genre}
            blendStart={roadBlends[i]?.start}
            blendEnd={roadBlends[i]?.end}
            startJunction={roadBlends[i]?.startJunction}
            endJunction={roadBlends[i]?.endJunction}
            insetStart={roadBlends[i]?.insetStart}
            insetEnd={roadBlends[i]?.insetEnd}
          />
        ))}
        <RoadJunctionFills
          roads={map.roads || []}
          genre={genre}
          mapWidth={map.width}
          mapHeight={map.height}
          heightAt={(x, z) => heightAt(x, z, map)}
          scale={ACTIVE_SCALE}
        />
        {/* City walls disabled — ExtrudeGeometry rings were reading as giant slabs */}
        {/* {(map.walls || []).map((w, i) => <CityWallMesh key={`wl${i}`} wall={w} map={map} />)} */}
        {(map.trees || []).map((t, i) => <Tree key={i} t={t} map={map} genre={genre} />)}
        {(map.buildings || []).map((b, i) => (
          <BuildingMesh key={i} b={b} map={map} genre={genre} night={palette.night}
            onEnter={onEnterBuilding} />
        ))}
        {(map.props || []).map((p, i) => (
          <StreetPropMesh key={`pr${i}`} prop={p} map={map} genre={genre} night={palette.night} />
        ))}
        <LandmarkMarkers map={map} night={palette.night} />
        {(map.animals || []).map((a, i) => <AnimalMesh key={i} a={a} map={map} />)}
        <StreetPedestrians map={map} genre={genre} />
        {agents.map((a) => (
          <DynamicAgent
            key={a.id}
            agent={a}
            map={map}
            coordsByLocId={coordsByLocId}
            isPlayer={a.id === playerId}
            hideBody={cameraMode === "first" && a.id === playerId}
            dormant={dormant}
            genre={genre}
            registerPlayer={a.id === playerId ? registerPlayer : undefined}
            presentation={presentation}
            localControl={explorationEnabled && a.id === playerId && !dormant}
            playerRef={playerRef}
            characterLod={characterLod}
          />
        ))}
      </Suspense>

      {explorationEnabled && playerId && !dormant && (
        <ExplorationController
          map={map}
          agents={agents}
          playerId={playerId}
          playerRef={playerRef}
          presentation={presentation}
          onMove={onMove}
          onNearbyNpc={onNearbyNpc}
          enabled={explorationEnabled}
          dormant={dormant}
        />
      )}

      <PostFX night={palette.night} genre={genre} />

      {cameraMode === "third" ? (
        <OrbitFollow
          target={playerRef}
          camDist={camDist}
          focus={mapFocus}
          freeExplore={!playerId || !explorationEnabled}
        />
      ) : (
        <PointerLockControls />
      )}
    </>
  );
}

export default function World3D({
  genre, worldLocations, agents, playerId, height = 520, fullscreen = false,
  cameraMode, onCameraModeChange, dormant = false, onEnterBuilding, hour = 10,
  explorationEnabled = false, presentation, onMove, onNearbyNpc, characterLod = "standard",
  previewMode = false,
}: Props) {
  const [map, setMap] = useState<MapData | null>(null);
  const [mapLoading, setMapLoading] = useState(true);
  const [interior, setInterior] = useState<string | null>(null);
  const palette = dayPalette(hour);

  useEffect(() => {
    let cancelled = false;
    setMapLoading(true);
    (async () => {
      try {
        const r = await fetch(`/models/hy3d_ready.json?t=${Date.now()}`, { cache: "no-store" });
        if (r.ok && !cancelled) {
          const d = await r.json();
          markHy3dReady("building", d.buildings || []);
          markHy3dReady("stall", d.stalls || []);
          markHy3dReady("prop", d.props || []);
        }
        const nr = await fetch(`/models/characters/hy3d_npc_ready.json?t=${Date.now()}`, { cache: "no-store" });
        if (nr.ok && !cancelled) {
          const nd = await nr.json();
          markHy3dNpcReady(nd.npcs || []);
        }
      } catch {
        /* kits already seed known hy3d files */
      }
      if (cancelled) return;
      preloadKitUrls(genreKitUrls(genre));
      const data = await loadWorldMap(genre, worldLocations);
      if (!cancelled) {
        const m = data as MapData;
        applyMapScale(m);
        setMap(m);
        setMapLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [genre, worldLocations]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "v" || e.key === "V") onCameraModeChange(cameraMode === "third" ? "first" : "third");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cameraMode, onCameraModeChange]);

  const locByName = useMemo(() => {
    if (!map) return {};
    const out: Record<string, [number, number]> = {};
    for (const l of map.locations) out[l.name] = px2world(l.x, l.y, map.width, map.height);
    return out;
  }, [map]);

  const coordsByLocId = useMemo(() => {
    const out: Record<string, [number, number]> = {};
    for (const l of worldLocations) {
      const c = locByName[l.name];
      if (c) out[l.id] = c;
    }
    return out;
  }, [worldLocations, locByName]);

  if (!map) {
    return (
      <div className={`${fullscreen ? "h-full w-full" : "rounded-xl border border-stone-800"}
                      bg-stone-900/50 p-6 text-center text-[12px] opacity-60 flex items-center justify-center`}
           style={fullscreen ? undefined : { height }}>
        {mapLoading ? "正在生成 3D 地形…" : "正在加载世界…"}
      </div>
    );
  }

  const camDist = Math.max(map.width, map.height) * ACTIVE_SCALE * 0.85;
  const period =
    hour >= 5 && hour < 8 ? "清晨"
      : hour >= 8 && hour < 17 ? "白昼"
        : hour >= 17 && hour < 20 ? "黄昏"
          : "深夜";

  return (
    <div
      className={`${fullscreen ? "h-full w-full" : "rounded-xl border border-stone-700/80 shadow-inner"}
                  overflow-hidden relative`}
      style={{
        height: fullscreen ? "100%" : height,
        background: `radial-gradient(ellipse at 50% 0%, ${palette.fog}55, #030201 70%)`,
      }}
    >
      {!previewMode && (
        <div className="absolute top-2 left-3 z-10 text-[11px] tracking-wide opacity-80 pointer-events-none">
          <span className="uppercase tracking-widest opacity-70">3D · {map.name}</span>
          <span className="ml-2 text-amber-200/90">{period}</span>
          {interior ? <span className="ml-2">· {interior}</span> : null}
          {dormant ? <span className="ml-2 text-sky-300">· 休眠</span> : null}
        </div>
      )}
      {!previewMode && (
        <div className="absolute top-2 right-3 z-10 flex gap-2">
          <button type="button" onClick={() => onCameraModeChange(cameraMode === "third" ? "first" : "third")}
            className="px-2.5 py-1 rounded-md text-[11px] border border-amber-600/50 bg-stone-950/75 text-amber-100 backdrop-blur-sm">
            {cameraMode === "third" ? "跟拍 · 第三视角" : "漫游 · 第一人称"} · V
          </button>
        </div>
      )}
      {!previewMode && (
        <div className="absolute bottom-2 left-3 z-10 text-[10px] opacity-55 pointer-events-none max-w-[70%]">
          {interior
            ? "室内场景 · 点击离开建筑"
            : explorationEnabled
              ? "WASD 移动 · 靠近 NPC 按 F 交谈 · 跟拍相机 · 日夜随世界时辰变化"
              : "左键拖拽平移 · 右键旋转 · 滚轮缩放 · 单击地面聚焦查看"}
        </div>
      )}
      <Canvas
        shadows
        dpr={[1, 1.5]}
        gl={{
          // antialias must be false when EffectComposer owns the present path
          antialias: false,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: palette.night ? 0.95 : 1.08,
          powerPreference: "high-performance",
        }}
        camera={{
          position: [camDist * 0.14, camDist * 0.09, camDist * 0.13],
          fov: cameraMode === "first" ? 68 : 45,
          near: 0.2,
          far: 2500,
        }}
      >
        <SceneInner
          map={map}
          genre={genre}
          agents={agents}
          playerId={playerId}
          coordsByLocId={coordsByLocId}
          camDist={camDist}
          cameraMode={cameraMode}
          dormant={dormant}
          hour={hour}
          interior={interior}
          onEnterBuilding={(name) => {
            setInterior(name);
            onEnterBuilding?.(name);
          }}
          onExitBuilding={() => setInterior(null)}
          explorationEnabled={explorationEnabled}
          presentation={presentation}
          onMove={onMove}
          onNearbyNpc={onNearbyNpc}
          characterLod={characterLod}
        />
      </Canvas>
    </div>
  );
}
