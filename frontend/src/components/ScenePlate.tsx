"use client";

import { useEffect, useMemo, useState } from "react";

type Props = {
  enabled: boolean;
  genre?: string;
  locationName?: string;
  summary?: string;
  hour?: number;
  tension?: number;
  reducedMotion?: boolean;
};

function sceneArtUrl(p: Omit<Props, "enabled" | "reducedMotion">): string {
  const q = new URLSearchParams({
    genre: p.genre || "ancient",
    location: p.locationName || "",
    summary: (p.summary || "").slice(0, 80),
    hour: String(p.hour ?? 12),
    tension: String(p.tension ?? 0.3),
  });
  return `/api/media/scene-art?${q.toString()}`;
}

/** Soft cinematic plate behind dialogue — M3 scene illustration. */
export default function ScenePlate({
  enabled,
  genre,
  locationName,
  summary,
  hour,
  tension,
  reducedMotion,
}: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [visible, setVisible] = useState(false);
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
      setSrc(url);
      requestAnimationFrame(() => setVisible(true));
    };
    img.onerror = () => {
      if (!cancelled) setSrc(null);
    };
    img.src = url;
    return () => {
      cancelled = true;
    };
  }, [enabled, url]);

  if (!enabled || !src) return null;

  return (
    <div
      className="pointer-events-none absolute inset-0 z-[5] overflow-hidden"
      aria-hidden
    >
      <div
        className="absolute inset-0 bg-cover bg-center"
        style={{
          backgroundImage: `url(${src})`,
          opacity: visible ? 0.42 : 0,
          filter: "saturate(0.9) contrast(1.05)",
          transform: reducedMotion ? undefined : visible ? "scale(1.04)" : "scale(1.08)",
          transition: reducedMotion
            ? "opacity 200ms ease"
            : "opacity 900ms ease, transform 12s ease-out",
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-black/20" />
    </div>
  );
}
