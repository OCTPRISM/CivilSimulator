"use client";

/**
 * Black-Myth / Zhong Kui inspired material kit for WebGL:
 * skin SSS approximation, matte hemp cloth, aged ritual metal.
 * Not UE5 Nanite — but same material *contrast language*.
 */
import { useMemo } from "react";
import * as THREE from "three";

function canvasTex(
  size: number,
  paint: (ctx: CanvasRenderingContext2D, s: number) => void,
  opts?: { anisotropy?: number; colorSpace?: THREE.ColorSpace },
): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d")!;
  paint(ctx, size);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = opts?.anisotropy ?? 4;
  if (opts?.colorSpace) tex.colorSpace = opts.colorSpace;
  tex.needsUpdate = true;
  return tex;
}

/** Fine pore + freckle albedo noise for skin. */
export function useSkinMaps(baseHex: string) {
  return useMemo(() => {
    if (typeof document === "undefined") return undefined;
    const base = new THREE.Color(baseHex);
    const albedo = canvasTex(256, (ctx, s) => {
      ctx.fillStyle = `#${base.getHexString()}`;
      ctx.fillRect(0, 0, s, s);
      for (let i = 0; i < 9000; i++) {
        const x = Math.random() * s;
        const y = Math.random() * s;
        const a = 0.015 + Math.random() * 0.04;
        const shade = Math.random() > 0.55 ? 255 : 40;
        ctx.fillStyle = `rgba(${shade},${shade * 0.85},${shade * 0.7},${a})`;
        ctx.fillRect(x, y, 1 + (Math.random() > 0.85 ? 1 : 0), 1);
      }
      for (let i = 0; i < 40; i++) {
        const x = Math.random() * s;
        const y = Math.random() * s;
        const g = ctx.createRadialGradient(x, y, 0, x, y, 8 + Math.random() * 18);
        g.addColorStop(0, "rgba(180,70,50,0.07)");
        g.addColorStop(1, "rgba(180,70,50,0)");
        ctx.fillStyle = g;
        ctx.fillRect(x - 24, y - 24, 48, 48);
      }
    }, { colorSpace: THREE.SRGBColorSpace });

    const roughness = canvasTex(256, (ctx, s) => {
      ctx.fillStyle = "#8a8a8a";
      ctx.fillRect(0, 0, s, s);
      for (let i = 0; i < 6000; i++) {
        const v = 90 + Math.floor(Math.random() * 80);
        ctx.fillStyle = `rgb(${v},${v},${v})`;
        ctx.fillRect(Math.random() * s, Math.random() * s, 1, 1);
      }
    });

    return { albedo, roughness };
  }, [baseHex]);
}

/** Hemp / cotton weave for robes. */
export function useClothMaps(baseHex: string) {
  return useMemo(() => {
    if (typeof document === "undefined") return undefined;
    const base = new THREE.Color(baseHex);
    const albedo = canvasTex(256, (ctx, s) => {
      ctx.fillStyle = `#${base.getHexString()}`;
      ctx.fillRect(0, 0, s, s);
      for (let y = 0; y < s; y += 2) {
        ctx.fillStyle = `rgba(0,0,0,${0.03 + (y % 4 === 0 ? 0.03 : 0)})`;
        ctx.fillRect(0, y, s, 1);
      }
      for (let x = 0; x < s; x += 3) {
        ctx.fillStyle = "rgba(255,255,255,0.025)";
        ctx.fillRect(x, 0, 1, s);
      }
      for (let i = 0; i < 120; i++) {
        const x = Math.random() * s;
        const y = Math.random() * s;
        ctx.fillStyle = `rgba(30,20,10,${0.04 + Math.random() * 0.08})`;
        ctx.beginPath();
        ctx.ellipse(x, y, 4 + Math.random() * 14, 2 + Math.random() * 6, Math.random(), 0, Math.PI * 2);
        ctx.fill();
      }
    }, { colorSpace: THREE.SRGBColorSpace });

    const roughness = canvasTex(128, (ctx, s) => {
      ctx.fillStyle = "#c8c8c8";
      ctx.fillRect(0, 0, s, s);
      for (let i = 0; i < 2000; i++) {
        const v = 140 + Math.floor(Math.random() * 90);
        ctx.fillStyle = `rgb(${v},${v},${v})`;
        ctx.fillRect(Math.random() * s, Math.random() * s, 2, 1);
      }
    });

    return { albedo, roughness };
  }, [baseHex]);
}

/** Aged ritual bronze / iron. */
export function useMetalMaps(baseHex: string) {
  return useMemo(() => {
    if (typeof document === "undefined") return undefined;
    const base = new THREE.Color(baseHex);
    const albedo = canvasTex(128, (ctx, s) => {
      ctx.fillStyle = `#${base.getHexString()}`;
      ctx.fillRect(0, 0, s, s);
      for (let i = 0; i < 80; i++) {
        ctx.strokeStyle = `rgba(0,0,0,${0.08 + Math.random() * 0.15})`;
        ctx.beginPath();
        ctx.moveTo(Math.random() * s, Math.random() * s);
        ctx.lineTo(Math.random() * s, Math.random() * s);
        ctx.stroke();
      }
      for (let i = 0; i < 40; i++) {
        ctx.fillStyle = "rgba(180,140,60,0.08)";
        ctx.fillRect(Math.random() * s, Math.random() * s, 3, 3);
      }
    }, { colorSpace: THREE.SRGBColorSpace });

    const roughness = canvasTex(128, (ctx, s) => {
      ctx.fillStyle = "#555555";
      ctx.fillRect(0, 0, s, s);
      for (let i = 0; i < 1500; i++) {
        const v = 40 + Math.floor(Math.random() * 160);
        ctx.fillStyle = `rgb(${v},${v},${v})`;
        ctx.fillRect(Math.random() * s, Math.random() * s, 1, 1);
      }
    });

    return { albedo, roughness };
  }, [baseHex]);
}

export function SkinPhysical({
  color, opacity = 1, maps,
}: {
  color: string; opacity?: number;
  maps?: { albedo: THREE.Texture; roughness: THREE.Texture };
}) {
  return (
    <meshPhysicalMaterial
      color={color}
      map={maps?.albedo}
      roughnessMap={maps?.roughness}
      roughness={0.55}
      metalness={0.02}
      clearcoat={0.04}
      clearcoatRoughness={0.7}
      sheen={0.35}
      sheenRoughness={0.7}
      sheenColor="#c47868"
      transmission={0}
      thickness={0}
      transparent={opacity < 1}
      opacity={opacity}
      envMapIntensity={0.35}
    />
  );
}

export function ClothPhysical({
  color, opacity = 1, maps, sheenColor = "#8a7a68",
  emissive, emissiveIntensity = 0,
}: {
  color: string; opacity?: number;
  maps?: { albedo: THREE.Texture; roughness: THREE.Texture };
  sheenColor?: string;
  emissive?: string; emissiveIntensity?: number;
}) {
  return (
    <meshPhysicalMaterial
      color={color}
      map={maps?.albedo}
      roughnessMap={maps?.roughness}
      roughness={0.88}
      metalness={0.03}
      sheen={0.55}
      sheenRoughness={0.82}
      sheenColor={sheenColor}
      transparent={opacity < 1}
      opacity={opacity}
      emissive={emissive || "#000000"}
      emissiveIntensity={emissiveIntensity}
      envMapIntensity={0.35}
    />
  );
}

export function MetalPhysical({
  color, opacity = 1, maps, roughness = 0.28,
  emissive, emissiveIntensity = 0,
}: {
  color: string; opacity?: number;
  maps?: { albedo: THREE.Texture; roughness: THREE.Texture };
  roughness?: number;
  emissive?: string; emissiveIntensity?: number;
}) {
  return (
    <meshPhysicalMaterial
      color={color}
      map={maps?.albedo}
      roughnessMap={maps?.roughness}
      roughness={roughness}
      metalness={0.85}
      clearcoat={0.2}
      clearcoatRoughness={0.4}
      transparent={opacity < 1}
      opacity={opacity}
      emissive={emissive || "#000000"}
      emissiveIntensity={emissiveIntensity}
      envMapIntensity={1.1}
    />
  );
}

export function LeatherPhysical({ color, opacity = 1 }: { color: string; opacity?: number }) {
  return (
    <meshPhysicalMaterial
      color={color}
      roughness={0.78}
      metalness={0.08}
      sheen={0.25}
      sheenRoughness={0.7}
      sheenColor="#5a4030"
      transparent={opacity < 1}
      opacity={opacity}
      envMapIntensity={0.4}
    />
  );
}
