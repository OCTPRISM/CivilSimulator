/** In-tab + sessionStorage transcript for player↔player and player↔NPC chats. */

export type TalkLine = {
  id?: string;
  who: "me" | "them";
  text: string;
};

const threads = new Map<string, TalkLine[]>();
const seenIds = new Set<string>();
const loadedSids = new Set<string>();
const STORAGE_PREFIX = "civsim_talk_v1_";
const THREAD_CAP = 80;

function key(sid: string, peerId: string): string {
  return `${sid}:${peerId}`;
}

function canStore(): boolean {
  return typeof window !== "undefined" && typeof sessionStorage !== "undefined";
}

function persistSid(sid: string) {
  if (!canStore() || !sid) return;
  const dump: Record<string, TalkLine[]> = {};
  const prefix = `${sid}:`;
  threads.forEach((lines, k) => {
    if (k.startsWith(prefix) && lines.length) dump[k] = lines.slice(-THREAD_CAP);
  });
  const seen: string[] = [];
  seenIds.forEach((id) => {
    if (id.startsWith(prefix) || id.startsWith(`${sid}:`)) seen.push(id);
  });
  try {
    sessionStorage.setItem(STORAGE_PREFIX + sid, JSON.stringify({ dump, seen }));
  } catch {
    /* quota / private mode */
  }
}

function loadSid(sid: string) {
  if (!sid || loadedSids.has(sid)) return;
  loadedSids.add(sid);
  if (!canStore()) return;
  try {
    const raw = sessionStorage.getItem(STORAGE_PREFIX + sid);
    if (!raw) return;
    const parsed = JSON.parse(raw) as { dump?: Record<string, TalkLine[]>; seen?: string[] };
    if (parsed.dump) {
      Object.entries(parsed.dump).forEach(([k, lines]) => {
        if (!Array.isArray(lines) || threads.has(k)) return;
        threads.set(k, lines.filter((l) => l && l.text && (l.who === "me" || l.who === "them")));
      });
    }
    (parsed.seen || []).forEach((id) => {
      if (id) seenIds.add(id);
    });
  } catch {
    /* ignore corrupt cache */
  }
}

export function getTalkLines(sid: string, peerId: string): TalkLine[] {
  loadSid(sid);
  return threads.get(key(sid, peerId)) || [];
}

export function appendTalkLine(sid: string, peerId: string, line: TalkLine): boolean {
  loadSid(sid);
  if (line.id) {
    const idKey = `${sid}:${line.id}`;
    if (seenIds.has(idKey)) return false;
    seenIds.add(idKey);
  }
  const k = key(sid, peerId);
  const prev = threads.get(k) || [];
  const next = [...prev, line];
  threads.set(k, next.length > THREAD_CAP ? next.slice(-THREAD_CAP) : next);
  persistSid(sid);
  return true;
}

/** Prevent inbox replay from duplicating a line we already showed (local send). */
export function rememberTalkMessageIds(sid: string, ids: Array<string | undefined | null>) {
  loadSid(sid);
  let changed = false;
  for (const id of ids) {
    const mid = (id || "").trim();
    if (!mid) continue;
    const idKey = `${sid}:${mid}`;
    if (!seenIds.has(idKey)) {
      seenIds.add(idKey);
      changed = true;
    }
  }
  if (changed) persistSid(sid);
}

export function ensureTalkGreeting(sid: string, peerId: string, text: string): TalkLine[] {
  loadSid(sid);
  const existing = getTalkLines(sid, peerId);
  if (existing.length) return existing;
  const greeting: TalkLine = { who: "them", text };
  threads.set(key(sid, peerId), [greeting]);
  persistSid(sid);
  return [greeting];
}

export type TalkInboxItem = {
  message_id?: string;
  from_id?: string;
  from_name?: string;
  to_id?: string;
  to_name?: string;
  from_kind?: string;
  text?: string;
};

/** Replay server inbox into local threads. Returns peer id of newest unseen P2P incoming. */
export function hydrateTalkInbox(
  sid: string,
  selfId: string | null | undefined,
  items: TalkInboxItem[] | undefined | null,
): string | null {
  loadSid(sid);
  if (!selfId || !items?.length) return null;
  let newestIncoming: string | null = null;
  for (const m of items) {
    const text = (m.text || "").trim();
    const fromId = m.from_id || "";
    const toId = m.to_id || "";
    if (!text || !fromId || !toId) continue;
    const peerId: string = fromId === selfId ? toId : fromId;
    if (!peerId || peerId === selfId) continue;
    const added = appendTalkLine(sid, peerId, {
      id: m.message_id,
      who: fromId === selfId ? "me" : "them",
      text,
    });
    if (
      added &&
      toId === selfId &&
      fromId !== selfId &&
      m.from_kind !== "npc"
    ) {
      newestIncoming = fromId;
    }
  }
  persistSid(sid);
  return newestIncoming;
}
