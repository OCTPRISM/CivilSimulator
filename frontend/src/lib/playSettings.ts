/** Play session settings persisted locally (v1.4 Esc menu + M3 multimodal). */

export type PlayQuality = "low" | "medium" | "high";
export type PlaySettings = {
  tts: boolean;
  sfx: boolean;
  bgm: boolean;
  /** Speech rate 0.7–1.3 */
  ttsRate: number;
  /** Also read NPC dialogue lines */
  ttsReadSpeech: boolean;
  /** Soft cinematic scene plate behind dialogue */
  sceneArt: boolean;
  quality: PlayQuality;
  reducedMotion: boolean;
  cameraMode: "third" | "first";
  /** Mobile narrative: optional World3D preview (off by default). */
  worldPreview: boolean;
};

const KEY = "civsim_play_settings";

const DEFAULTS: PlaySettings = {
  tts: false,
  sfx: true,
  bgm: true,
  ttsRate: 0.95,
  ttsReadSpeech: false,
  sceneArt: true,
  quality: "medium",
  reducedMotion: false,
  cameraMode: "third",
  worldPreview: false,
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
