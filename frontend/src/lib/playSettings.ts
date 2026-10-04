/** Play session settings persisted locally (v1.4 Esc menu). */

export type PlayQuality = "low" | "medium" | "high";
export type PlaySettings = {
  tts: boolean;
  sfx: boolean;
  quality: PlayQuality;
  reducedMotion: boolean;
  cameraMode: "third" | "first";
};

const KEY = "civsim_play_settings";

const DEFAULTS: PlaySettings = {
  tts: false,
  sfx: true,
  quality: "medium",
  reducedMotion: false,
  cameraMode: "third",
};

export function loadPlaySettings(): PlaySettings {
  if (typeof window === "undefined") return { ...DEFAULTS };
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function savePlaySettings(patch: Partial<PlaySettings>): PlaySettings {
  const next = { ...loadPlaySettings(), ...patch };
  if (typeof window !== "undefined") {
    localStorage.setItem(KEY, JSON.stringify(next));
  }
  return next;
}
