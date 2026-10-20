/** In-tab transcript for player↔player (and overlay) chats. Survives close/reopen. */

export type TalkLine = {
  id?: string;
  who: "me" | "them";
  text: string;
};

const threads = new Map<string, TalkLine[]>();
const seenIds = new Set<string>();

function key(sid: string, peerId: string): string {
  return `${sid}:${peerId}`;
}

export function getTalkLines(sid: string, peerId: string): TalkLine[] {
  return threads.get(key(sid, peerId)) || [];
}

export function appendTalkLine(sid: string, peerId: string, line: TalkLine): boolean {
  if (line.id) {
    const idKey = `${sid}:${line.id}`;
    if (seenIds.has(idKey)) return false;
    seenIds.add(idKey);
  }
  const k = key(sid, peerId);
  const prev = threads.get(k) || [];
  threads.set(k, [...prev, line]);
  return true;
}

export function ensureTalkGreeting(sid: string, peerId: string, text: string): TalkLine[] {
  const existing = getTalkLines(sid, peerId);
  if (existing.length) return existing;
  const greeting: TalkLine = { who: "them", text };
  threads.set(key(sid, peerId), [greeting]);
  return [greeting];
}

export type TalkInboxItem = {
  message_id?: string;
  from_id?: string;
  from_name?: string;
  to_id?: string;
  to_name?: string;
  text?: string;
};

/** Replay server inbox into local threads. Returns peer id of newest unseen incoming. */
export function hydrateTalkInbox(
  sid: string,
  selfId: string | null | undefined,
  items: TalkInboxItem[] | undefined | null,
): string | null {
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
    if (added && toId === selfId && fromId !== selfId) {
      newestIncoming = fromId;
    }
  }
  return newestIncoming;
}
