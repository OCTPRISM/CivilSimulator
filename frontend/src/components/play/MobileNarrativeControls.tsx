"use client";

import type { Agent } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Props = {
  locationName: string;
  clockLabel?: string;
  summary?: string;
  npcs: Agent[];
  sid: string;
  loading?: boolean;
  worldPreview: boolean;
  onToggleWorldPreview: () => void;
  onAdvance: () => void;
  onOpenMap: () => void;
  onOpenWorld: () => void;
};

/** Touch-first location + NPC + primary actions (architecture §9.7). */
export default function MobileNarrativeControls({
  locationName,
  clockLabel,
  summary,
  npcs,
  sid,
  loading,
  worldPreview,
  onToggleWorldPreview,
  onAdvance,
  onOpenMap,
  onOpenWorld,
}: Props) {
  const { t } = useI18n();
  return (
    <div className="w-full max-w-[var(--play-dock-max)] mx-auto space-y-2">
      <div className="play-panel px-3 py-2.5 shadow-lg">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-serif text-base text-[var(--play-ink)] truncate">{locationName}</p>
            {clockLabel && (
              <p className="text-[10px] uppercase tracking-widest text-[var(--play-ink-muted)] mt-0.5">
                {clockLabel}
              </p>
            )}
            {summary && (
              <p className="text-[12px] text-[var(--play-ink-muted)] mt-1 line-clamp-2 leading-relaxed">
                {summary}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onToggleWorldPreview}
            className="play-btn-ghost !min-h-[36px] shrink-0 text-[11px] !px-2.5 !py-1.5"
          >
            {worldPreview ? t("play.hide3d") : t("play.show3d")}
          </button>
        </div>

        {npcs.length > 0 && (
          <div className="mt-2.5 pt-2 border-t border-[var(--play-line)]/50">
            <p className="text-[10px] text-[var(--play-ink-muted)] mb-1.5">{t("play.talkHere")}</p>
            <div className="flex flex-wrap gap-1.5">
              {npcs.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  disabled={loading}
                  className="px-3 py-1.5 rounded-md text-[12px] border border-[var(--play-line)]
                             bg-[var(--play-deep)]/70 text-[var(--play-ink)]
                             active:border-[var(--play-amber)]
                             disabled:opacity-40 min-h-[36px]"
                  onClick={() => {
                    window.dispatchEvent(
                      new CustomEvent("civsim:npc-talk", { detail: { sid, npcId: n.id } }),
                    );
                  }}
                >
                  {n.kind === "player" ? t("play.playerTag", { name: n.name }) : n.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        <button
          type="button"
          disabled={loading}
          onClick={onAdvance}
          className="play-cta w-full text-sm"
        >
          {t("play.forward")}
        </button>
        <button
          type="button"
          onClick={onOpenMap}
          className="play-btn-ghost w-full text-sm"
        >
          {t("play.mapShort")}
        </button>
        <button
          type="button"
          onClick={onOpenWorld}
          className="play-btn-ghost w-full text-sm"
        >
          {t("play.worldShort")}
        </button>
      </div>
    </div>
  );
}
