/** Play UI state machine (v1.4). */

export type PlayMode =
  | "LOADING"
  | "EXPLORE"
  | "DIALOGUE"
  | "OVERLAY_MAP"
  | "OVERLAY_JOURNAL"
  | "OVERLAY_CHARACTER"
  | "OVERLAY_WORLD_STATE"
  | "SYSTEM_MENU"
  | "RECONNECTING"
  | "WAKE_BRIEFING";

export function derivePlayMode(args: {
  sessionLoaded: boolean;
  hasBriefing: boolean;
  wsReconnecting: boolean;
  overlay: PlayMode | null;
  systemOpen: boolean;
  inDialogue: boolean;
  isOffline: boolean;
}): PlayMode {
  if (!args.sessionLoaded) return "LOADING";
  if (args.wsReconnecting) return "RECONNECTING";
  if (args.hasBriefing) return "WAKE_BRIEFING";
  if (args.systemOpen) return "SYSTEM_MENU";
  if (args.overlay) return args.overlay;
  if (args.inDialogue && !args.isOffline) return "DIALOGUE";
  return "EXPLORE";
}

export type OverlayKey = "map" | "journal" | "character" | "world";

export function overlayFromKey(key: OverlayKey | null): PlayMode | null {
  if (key === "map") return "OVERLAY_MAP";
  if (key === "journal") return "OVERLAY_JOURNAL";
  if (key === "character") return "OVERLAY_CHARACTER";
  if (key === "world") return "OVERLAY_WORLD_STATE";
  return null;
}

export function toggleOverlay(
  current: OverlayKey | null,
  next: OverlayKey,
): OverlayKey | null {
  return current === next ? null : next;
}
