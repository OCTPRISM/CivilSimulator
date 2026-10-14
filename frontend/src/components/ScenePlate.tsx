"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Props = {
  enabled: boolean;
  genre?: string;
  locationName?: string;
  summary?: string;
  hour?: number;
  tension?: number;
  reducedMotion?: boolean;
  /** Bumps cross-fade when a new page arrives. */
  pageKey?: string | number;
};

function sceneArtUrl(p: Omit<Props, "enabled" | "reducedMotion" | "pageKey">): string {
  const q = new URLSearchParams({
    genre: p.genre || "ancient",
    location: p.locationName || "",
    summary: (p.summary || "").slice(0, 80),
    hour: String(p.hour ?? 12),
    tension: String(p.tension ?? 0.3),
  });
  return `/api/media/scene-art?${q.toString()}`;
}

/** Lower-band cinematic veil behind the dialogue dock — keeps upper 3D readable. */
export default function ScenePlate({
  enabled,
  genre,
  locationName,
  summary,
  hour,
  tension,
  reducedMotion,
  pageKey,
}: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [prevSrc, setPrevSrc] = useState<string | null>(null);
  const [visible, setVisible] = useState(false);
  const srcRef = useRef<string | null>(null);
  const url = useMemo(
    () => sceneArtUrl({ genre, locationName, summary, hour, tension }),
    [genre, locationName, summary, hour, tension],
  );

  useEffect(() => {
    if (!enabled) {
      setVisible(false);
      return;
    }
    let cancelled = false;
    setVisible(false);
    const img = new Image();
    img.onload = () => {
      if (cancelled) return;
      const prev = srcRef.current;
      if (prev && prev !== url) setPrevSrc(prev);
      srcRef.current = url;
      setSrc(url);
      requestAnimationFrame(() => setVisible(true));
    };
    img.onerror = () => {
      if (!cancelled) {
        srcRef.current = null;
        setSrc(null);
      }
    };
    img.src = url;
    return () => {
      cancelled = true;
    };
  }, [enabled, url, pageKey]);

  useEffect(() => {
    if (!prevSrc || !visible) return;
    const t = window.setTimeout(() => setPrevSrc(null), reducedMotion ? 220 : 900);
    return () => window.clearTimeout(t);
  }, [prevSrc, visible, reducedMotion]);

  if (!enabled || (!src && !prevSrc)) return null;

  const bandMask =
    "linear-gradient(to top, black 0%, black 42%, rgba(0,0,0,0.55) 62%, transparent 88%)";

  return (
    <div
      className="pointer-events-none absolute inset-0 z-[5] overflow-hidden"
      aria-hidden
    >
      {prevSrc && (
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: `url(${prevSrc})`,
            opacity: visible ? 0 : 0.32,
            WebkitMaskImage: bandMask,
            maskImage: bandMask,
            filter: "saturate(0.85) contrast(1.04)",
            transition: reducedMotion
              ? "opacity 180ms ease"
              : "opacity 800ms ease",
          }}
        />
      )}
      {src && (
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: `url(${src})`,
            opacity: visible ? 0.34 : 0,
            WebkitMaskImage: bandMask,
            maskImage: bandMask,
            filter: "saturate(0.88) contrast(1.05)",
            transform: reducedMotion ? undefined : visible ? "scale(1.03)" : "scale(1.06)",
            transition: reducedMotion
              ? "opacity 200ms ease"
              : "opacity 900ms ease, transform 14s ease-out",
          }}
        />
      )}
      <div
        className="absolute inset-x-0 bottom-0 h-[55%]"
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.72) 0%, rgba(0,0,0,0.35) 45%, transparent 100%)",
        }}
      />
    </div>
  );
}
