"use client";

/**
 * NpcPanel — list NPCs present at the player's current location.
 * Click an NPC to open a per-NPC chat dialog (NpcChat).
 */
import { useMemo, useState } from "react";
import { resolveFigure } from "@/lib/characterFigures";
import type { Agent } from "@/lib/api";

function FigureBadge({ agent, genre }: { agent: Agent; genre?: string }) {
  const preset = resolveFigure(agent, genre);
  return (
    <div className="w-10 h-10 rounded-lg shrink-0 border border-stone-700 overflow-hidden
                    flex flex-col items-center justify-end"
         style={{ background: `linear-gradient(180deg, ${preset.torso} 55%, ${preset.legs} 100%)` }}>
      <div className="w-4 h-4 rounded-full mb-0.5 border border-stone-600"
           style={{ background: preset.skin }} />
      <div className="text-[8px] text-stone-300/80 pb-0.5 px-0.5 truncate w-full text-center">
        {preset.weapon !== "none" ? "⚔" : "·"}
      </div>
    </div>
  );
}
import NpcChat from "./NpcChat";

type Props = {
  sid: string;
  agents: Agent[];
  playerId: string | null;
  currentLocationId: string | null;
  currentLocationName: string;
  genre?: string;
};

export default function NpcPanel({
  sid, agents, playerId, currentLocationId, currentLocationName, genre,
}: Props) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const npcs = useMemo(
    () =>
      agents.filter(
        (a) =>
          a.kind === "npc" &&
          (currentLocationId
            ? a.location_id === currentLocationId
            : true) &&
          a.id !== playerId,
      ),
    [agents, currentLocationId, playerId],
  );

  const active = npcs.find((n) => n.id === activeId) || null;

  return (
    <div className="rounded-xl border border-stone-800 bg-stone-900/50 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[11px] uppercase tracking-widest opacity-60">
          在场 · NPC（{npcs.length}）
        </div>
        <div className="text-[11px] opacity-60">
          {currentLocationName}
        </div>
      </div>

      {npcs.length === 0 ? (
        <div className="text-[12px] opacity-50 py-3 text-center">
          此地无人——独行一段路再看。
        </div>
      ) : (
        <ul className="grid gap-2 grid-cols-1 sm:grid-cols-2">
          {npcs.map((n) => (
            <li key={n.id}>
              <button
                onClick={() => setActiveId(n.id)}
                className="w-full flex items-center gap-3 p-2 rounded-lg
                           border border-stone-800 hover:border-amber-500/60
                           bg-stone-950/40 hover:bg-stone-900/60
                           text-left transition"
              >
                <FigureBadge agent={n} genre={genre} />
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <div className="font-serif text-sm text-amber-200 truncate">
                      {n.name}
                    </div>
                    {n.profession && (
                      <div className="text-[10px] opacity-60 truncate">
                        {n.profession}
                      </div>
                    )}
                  </div>
                  {n.current_activity ? (
                    <div className="text-[11px] text-emerald-300/80 line-clamp-1 leading-snug">
                      🕒 {n.current_activity}
                    </div>
                  ) : (
                    <div className="text-[11px] opacity-70 line-clamp-2 leading-snug">
                      {n.persona}
                    </div>
                  )}
                  <div className="mt-0.5 flex flex-wrap gap-1 items-center">
                    {n.economy?.income_label && (
                      <span className="text-[10px] px-1 rounded
                                       bg-amber-900/40 border border-amber-700/40
                                       text-amber-200/90">
                        💰 {n.today_income ?? 0}
                        <span className="opacity-60">
                          /{n.economy.daily_capacity ?? "?"}
                          {n.economy.unit ?? ""}
                        </span>
                      </span>
                    )}
                    {n.last_meal_tier && (
                      <span className="text-[10px] px-1 rounded
                                       bg-stone-800 border border-stone-700
                                       opacity-80">
                        🍚 {n.last_meal_tier}
                      </span>
                    )}
                    {n.traits.slice(0, 2).map((t) => (
                      <span key={t}
                            className="text-[10px] px-1 rounded
                                       bg-stone-800 border border-stone-700
                                       opacity-80">
                        {t}
                      </span>
                    ))}
                    {(n.skills || [])
                      .filter((s) => s.kind === "unique")
                      .slice(0, 2)
                      .map((s) => (
                        <span key={s.id}
                              className="text-[10px] px-1 rounded
                                         bg-violet-950/60 border border-violet-700/40
                                         text-violet-200/90">
                          ✦ {s.name}
                        </span>
                      ))}
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}

      {active && (
        <NpcChat
          sid={sid}
          npc={active}
          onClose={() => setActiveId(null)}
        />
      )}
    </div>
  );
}
