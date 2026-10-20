"use client";

/**
 * NpcPanel — list talkable agents at the player's location (NPCs + other players).
 * Click to open NpcChat.
 */
import { useMemo } from "react";
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

type Props = {
  sid: string;
  agents: Agent[];
  playerId: string | null;
  currentLocationId: string | null;
  currentLocationName: string;
  genre?: string;
};

function isTalkable(a: Agent, playerId: string | null, locId: string | null): boolean {
  if (a.id === playerId) return false;
  if (a.kind !== "npc" && a.kind !== "player") return false;
  if (locId && a.location_id !== locId) return false;
  return true;
}

export default function NpcPanel({
  sid, agents, playerId, currentLocationId, currentLocationName, genre,
}: Props) {
  const talkables = useMemo(
    () => agents.filter((a) => isTalkable(a, playerId, currentLocationId)),
    [agents, currentLocationId, playerId],
  );

  const players = talkables.filter((a) => a.kind === "player");
  const npcs = talkables.filter((a) => a.kind === "npc");
  const openTalk = (id: string) => {
    window.dispatchEvent(new CustomEvent("civsim:npc-talk", { detail: { sid, npcId: id } }));
  };

  return (
    <div className="rounded-xl border border-stone-800 bg-stone-900/50 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[11px] uppercase tracking-widest opacity-60">
          在场 · 可交谈（{talkables.length}）
        </div>
        <div className="text-[11px] opacity-60">
          {currentLocationName}
        </div>
      </div>

      {talkables.length === 0 ? (
        <div className="text-[12px] opacity-50 py-3 text-center">
          此地无人——独行一段路再看。
        </div>
      ) : (
        <div className="space-y-3">
          {players.length > 0 && (
            <TalkableList
              title={`同房玩家（${players.length}）`}
              agents={players}
              genre={genre}
              onPick={openTalk}
              playerBadge
            />
          )}
          {npcs.length > 0 && (
            <TalkableList
              title={`NPC（${npcs.length}）`}
              agents={npcs}
              genre={genre}
              onPick={openTalk}
            />
          )}
        </div>
      )}
    </div>
  );
}

function TalkableList({
  title, agents, genre, onPick, playerBadge,
}: {
  title: string;
  agents: Agent[];
  genre?: string;
  onPick: (id: string) => void;
  playerBadge?: boolean;
}) {
  return (
    <div>
      <div className="text-[10px] opacity-50 mb-1.5">{title}</div>
      <ul className="grid gap-2 grid-cols-1 sm:grid-cols-2">
        {agents.map((n) => (
          <li key={n.id}>
            <button
              onClick={() => onPick(n.id)}
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
                  {playerBadge && (
                    <span className="text-[10px] px-1 rounded border border-sky-700/40
                                     bg-sky-950/40 text-sky-200/90 shrink-0">
                      玩家
                    </span>
                  )}
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
                    {n.persona || (playerBadge ? "同房旅人" : "")}
                  </div>
                )}
                {!playerBadge && (
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
                    {n.traits.slice(0, 2).map((t) => (
                      <span key={t}
                            className="text-[10px] px-1 rounded
                                       bg-stone-800 border border-stone-700
                                       opacity-80">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
