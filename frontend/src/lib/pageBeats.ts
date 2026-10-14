import type { Beat, Page } from "@/lib/api";

export type ReadableBeat = {
  kind: "narration" | "speech";
  speaker: string | null;
  content: string;
};

/** Narration + speech beats with non-empty content (stage + TTS). */
export function readableBeats(page: Page | null | undefined): ReadableBeat[] {
  if (!page?.beats?.length) return [];
  const out: ReadableBeat[] = [];
  for (const b of page.beats) {
    if ((b.kind !== "narration" && b.kind !== "speech") || !b.content?.trim()) continue;
    out.push({
      kind: b.kind,
      speaker: b.speaker,
      content: b.content.trim(),
    });
  }
  return out;
}

/** Join beats into a TTS string; speech only when explicitly enabled. */
export function beatsToSpeechText(
  beats: ReadableBeat[],
  opts: { readSpeech?: boolean } = {},
): string {
  const readSpeech = Boolean(opts.readSpeech);
  const parts: string[] = [];
  for (const b of beats) {
    if (b.kind === "narration") parts.push(b.content);
    else if (readSpeech) {
      parts.push(b.speaker ? `${b.speaker}：${b.content}` : b.content);
    }
  }
  return parts.join("。");
}

export function latestReadableBeats(pages: Page[]): ReadableBeat[] {
  if (!pages.length) return [];
  return readableBeats(pages[pages.length - 1]);
}

/** Type guard helper for Beat lists from loose JSON. */
export function asBeats(raw: unknown): Beat[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (b): b is Beat =>
      Boolean(b)
      && typeof b === "object"
      && typeof (b as Beat).content === "string"
      && typeof (b as Beat).kind === "string",
  );
}
