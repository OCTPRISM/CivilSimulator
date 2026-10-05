/** M2: bind each browser tab to its own player agent inside a shared room. */

const PID_KEY = (sid: string) => `civsim_pid_${sid}`;

export function getBoundPlayerId(sid: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("pid");
    if (fromUrl) return fromUrl;
  } catch { /* ignore */ }
  try {
    return sessionStorage.getItem(PID_KEY(sid));
  } catch {
    return null;
  }
}

export function setBoundPlayerId(sid: string, playerId: string): void {
  if (typeof window === "undefined" || !playerId) return;
  try {
    sessionStorage.setItem(PID_KEY(sid), playerId);
  } catch { /* ignore */ }
}

export function clearBoundPlayerId(sid: string): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(PID_KEY(sid));
  } catch { /* ignore */ }
}

/** Keep local "me" when a room-wide snapshot arrives with host player_id. */
export function withBoundPlayerId<T extends { player_id?: string | null; player_ids?: string[] }>(
  sid: string,
  session: T,
): T {
  const bound = getBoundPlayerId(sid);
  if (!bound) {
    if (session.player_id) setBoundPlayerId(sid, session.player_id);
    return session;
  }
  if (session.player_ids && !session.player_ids.includes(bound)) {
    return session;
  }
  if (session.player_id === bound) return session;
  return { ...session, player_id: bound };
}

export function inviteUrl(sid: string): string {
  if (typeof window === "undefined") return `/join/${sid}`;
  return `${window.location.origin}/join/${sid}`;
}
