"use client";

import type { StoryChoice } from "@/lib/api";

/** Normalize legacy string choices from older sessions. */
export function normalizeChoices(raw: unknown[] | undefined): StoryChoice[] {
  if (!raw?.length) return [];
  return raw.map((item) => {
    if (typeof item === "string") {
      const legacy: Record<string, StoryChoice> = {
        "上前一步": {
          label: "走近对峙",
          hint: "靠近眼前之人或事发中心",
          action: "我上前一步，逼近眼前之人。",
        },
        "按住腰间": {
          label: "戒备观察",
          hint: "手按兵器，提防四周",
          action: "我按住腰间兵刃，戒备地打量四周。",
        },
        "转身离去": {
          label: "暂时离开",
          hint: "不与当下风波纠缠，先离开",
          action: "我转身离去，暂避锋芒。",
        },
      };
      return legacy[item] ?? { label: item, hint: item, action: item };
    }
    const o = item as Partial<StoryChoice>;
    const label = o.label || o.action || "行动";
    return {
      label,
      hint: o.hint || label,
      action: o.action || label,
    };
  });
}

type Props = {
  choices: StoryChoice[];
  loading?: boolean;
  onPick: (choice: StoryChoice) => void;
};

export default function ChoicePanel({ choices, loading, onPick }: Props) {
  if (!choices.length) return null;

  return (
    <div className="grid gap-2 sm:grid-cols-1 mb-3">
      {choices.map((c, i) => (
        <button
          key={`${c.label}-${i}`}
          type="button"
          disabled={loading}
          onClick={() => onPick(c)}
          className="group text-left rounded-lg border border-amber-600/50
                     bg-stone-950/50 px-3 py-2.5 hover:bg-amber-500/10
                     hover:border-amber-400/70 disabled:opacity-40 transition"
        >
          <div className="font-medium text-amber-100 text-sm">{c.label}</div>
          <div className="text-[12px] text-stone-400 mt-0.5 leading-snug">
            {c.hint}
          </div>
        </button>
      ))}
    </div>
  );
}
