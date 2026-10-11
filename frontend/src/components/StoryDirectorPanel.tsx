"use client";

import type { Session } from "@/lib/api";
import InjectPanel from "@/components/InjectPanel";

type Props = {
  sid: string;
  session: Session;
  onUpdate: (s: Session) => void;
};

/** Host-facing story director (wraps inject / skip controls). */
export default function StoryDirectorPanel({ sid, session, onUpdate }: Props) {
  return (
    <div className="rounded-xl border border-amber-800/40 bg-stone-950/85 shadow-xl backdrop-blur-sm">
      <div className="px-3 pt-2 text-[10px] uppercase tracking-widest text-amber-200/70">
        故事导演 · Story Director
      </div>
      <InjectPanel sid={sid} session={session} onUpdate={onUpdate} />
    </div>
  );
}
