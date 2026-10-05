"use client";

import type { Agent, Page, Session, WakeBriefing, WorldStats } from "@/lib/api";
import WorldAtlas from "@/components/WorldAtlas";
import WorldDrawer from "@/components/WorldDrawer";
import NpcPanel from "@/components/NpcPanel";
import SkillPanel from "@/components/SkillPanel";
import ChoicePanel, { normalizeChoices } from "@/components/ChoicePanel";
import CharacterFigurePreview from "@/components/CharacterFigurePreview";
import { resolveFigure } from "@/lib/characterFigures";
import type { PlayQuality } from "@/lib/playSettings";
import type { OverlayKey } from "@/lib/playState";

type StatBarsProps = { stats: WorldStats };

function StatBars({ stats }: StatBarsProps) {
  const items: { key: keyof Pick<WorldStats, "politics"|"economy"|"livelihood"|"military"|"environment">;
                 label: string; tone: string }[] = [
    { key: "politics", label: "政治", tone: "bg-indigo-400" },
    { key: "economy", label: "经济", tone: "bg-emerald-400" },
    { key: "livelihood", label: "民生", tone: "bg-amber-400" },
    { key: "military", label: "军事", tone: "bg-rose-400" },
    { key: "environment", label: "环境", tone: "bg-cyan-400" },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      {items.map((it) => {
        const v = Number(stats[it.key] ?? 0);
        return (
          <div key={it.key} className="rounded-lg border border-stone-700/60 bg-stone-950/50 p-2">
            <div className="flex justify-between text-[11px] opacity-80">
              <span>{it.label}</span>
              <span>{v.toFixed(0)}</span>
            </div>
            <div className="mt-1 h-1.5 bg-stone-800 rounded overflow-hidden">
              <div className={`${it.tone} h-full transition-[width] duration-700`}
                   style={{ width: `${Math.max(2, v)}%` }} />
            </div>
            <div className="mt-1 text-[10px] opacity-60 line-clamp-2">{stats.summary[it.key]}</div>
          </div>
        );
      })}
    </div>
  );
}

export function PlayHud({
  session, player, isOffline, isProxy, isDormant, degraded, reconnecting,
  onWake, onSleep, onInvite, onExit, onOpenOverlay,
}: {
  session: Session;
  player?: Agent;
  isOffline: boolean;
  isProxy: boolean;
  isDormant: boolean;
  degraded: boolean;
  reconnecting: boolean;
  onWake: () => void;
  onSleep: () => void;
  onInvite?: () => void;
  onExit: () => void;
  onOpenOverlay: (key: OverlayKey) => void;
}) {
  const rosterCount = session.player_ids?.length || session.roster?.length || 1;
  return (
    <div className="absolute top-0 inset-x-0 z-20 pointer-events-none">
      <div className="flex items-start justify-between gap-3 p-3 sm:p-4
                      bg-gradient-to-b from-black/75 via-black/40 to-transparent">
        <div className="min-w-0 pointer-events-auto">
          <div className="font-serif text-lg sm:text-xl text-amber-50 truncate drop-shadow">
            《{session.world.name}》
          </div>
          <div className="text-[10px] opacity-70 uppercase tracking-widest text-stone-300">
            {session.world.genre} · {session.world.clock?.label || `第 ${session.world.clock?.tick ?? 0} 时`}
            <span className="ml-2 text-amber-200/80 normal-case">· {rosterCount} 人同世</span>
            {isDormant && <span className="ml-2 text-sky-300 normal-case">· 休眠</span>}
            {isProxy && <span className="ml-2 text-emerald-300 normal-case">· 代行</span>}
            {degraded && (
              <span className="ml-2 text-amber-300 normal-case">
                · {reconnecting ? "重连中…" : "HTTP 降级同步"}
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 shrink-0 pointer-events-auto">
          {player && (
            <button type="button" onClick={() => onOpenOverlay("character")}
                    className="hidden sm:block text-right text-xs px-2 py-1 rounded border border-stone-700/80
                               bg-stone-950/60 hover:border-amber-500/50">
              <div className="font-serif text-sm text-amber-200">{player.name}</div>
            </button>
          )}
          {onInvite && (
            <button type="button" onClick={onInvite}
                    className="px-2.5 py-1.5 rounded-md border border-amber-700/60 text-xs text-amber-100
                               bg-stone-950/70 hover:border-amber-400/70" title="复制邀请链接">
              邀请
            </button>
          )}
          {isOffline ? (
            <button type="button" onClick={onWake}
                    className="px-3 py-1.5 rounded-md border text-sm border-emerald-500/60 text-emerald-200
                               bg-stone-950/70 hover:bg-emerald-500/10">
              {isProxy ? "收回控制" : "苏醒"}
            </button>
          ) : (
            <button type="button" onClick={onSleep}
                    className="px-3 py-1.5 rounded-md border border-stone-700 text-sm bg-stone-950/70
                               hover:border-sky-400/50">
              离线
            </button>
          )}
          <button type="button" onClick={() => onOpenOverlay("map")}
                  className="px-2.5 py-1.5 rounded-md border border-stone-700 text-xs bg-stone-950/70
                             hover:border-amber-400/50" title="地图 (M)">M 地图</button>
          <button type="button" onClick={() => onOpenOverlay("journal")}
                  className="px-2.5 py-1.5 rounded-md border border-stone-700 text-xs bg-stone-950/70
                             hover:border-amber-400/50" title="日志 (J)">J 日志</button>
          <button type="button" onClick={() => onOpenOverlay("world")}
                  className="px-2.5 py-1.5 rounded-md border border-stone-700 text-xs bg-stone-950/70
                             hover:border-amber-400/50" title="世界状态 (Tab)">Tab 状态</button>
          <button type="button" onClick={() => onOpenOverlay("character")}
                  className="px-2.5 py-1.5 rounded-md border border-stone-700 text-xs bg-stone-950/70
                             hover:border-amber-400/50 sm:hidden" title="角色 (C)">C</button>
          <button type="button" onClick={onExit}
                  className="px-2.5 py-1.5 rounded-md border border-stone-600 text-xs text-stone-300
                             bg-stone-950/70 hover:border-rose-400/70">
            退出
          </button>
        </div>
      </div>
    </div>
  );
}

export function PlayOverlay({
  kind, onClose, session, stats, pages, tensionCurve, sid, player,
  sceneLocId, sceneLoc, loading, isOffline, skills, onUseSkill,
  relationsOpen, onRelationsToggle,
}: {
  kind: OverlayKey;
  onClose: () => void;
  session: Session;
  stats?: WorldStats;
  pages: Page[];
  tensionCurve: number[];
  sid: string;
  player?: Agent;
  sceneLocId: string | null;
  sceneLoc: string;
  loading: boolean;
  isOffline: boolean;
  skills?: Agent["skills"];
  onUseSkill: (id: string) => void;
  relationsOpen: boolean;
  onRelationsToggle: () => void;
}) {
  const titles: Record<OverlayKey, string> = {
    map: "世界地图",
    journal: "旅程日志",
    character: "角色与技能",
    world: "世界状态",
  };

  return (
    <>
      <div className="absolute inset-0 z-30 bg-black/55 backdrop-blur-[2px]"
           onClick={onClose} role="presentation" />
      <div className="absolute inset-x-2 sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2
                      top-14 bottom-4 sm:w-[min(720px,96vw)] z-40
                      rounded-xl border border-stone-700/80 bg-stone-950/95
                      shadow-2xl flex flex-col overflow-hidden">
        <header className="flex items-center justify-between px-4 py-3 border-b border-stone-800">
          <h2 className="font-serif text-lg text-amber-100">{titles[kind]}</h2>
          <button type="button" onClick={onClose}
                  className="text-stone-400 hover:text-amber-200 text-sm px-2 py-1">Esc 关闭</button>
        </header>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {kind === "map" && (
            <div className="h-[min(420px,50vh)] rounded-lg border border-stone-800 bg-stone-900/50
                            flex items-center justify-center p-2">
              <WorldAtlas session={session} stats={stats} />
            </div>
          )}
          {kind === "journal" && (
            <JournalList pages={pages} session={session} sid={sid} onUpdate={() => {}} />
          )}
          {kind === "character" && (
            <>
              {player && (
                <div className="grid sm:grid-cols-[minmax(160px,200px)_1fr] gap-3 items-start">
                  <CharacterFigurePreview
                    preset={resolveFigure(player, session.world.genre)}
                    height={220}
                    active
                    interactive
                  />
                  <div className="rounded-lg border border-stone-800 p-3 space-y-1">
                    <div className="font-serif text-xl text-amber-200">{player.name}</div>
                    <div className="text-xs opacity-60">{player.traits?.join(" · ")}</div>
                    <div className="text-xs opacity-50">{player.persona}</div>
                    {player.profession && (
                      <div className="text-[11px] text-amber-300/80">{player.profession}</div>
                    )}
                    <button type="button" onClick={onRelationsToggle}
                            className="mt-2 text-[11px] text-amber-300/90 underline">
                      查看关系网络 →
                    </button>
                  </div>
                </div>
              )}
              {!isOffline && skills && (
                <SkillPanel skills={skills} loading={loading} disabled={isOffline} onUse={onUseSkill} />
              )}
              <NpcPanel sid={sid} agents={session.agents} playerId={session.player_id}
                        currentLocationId={sceneLocId} currentLocationName={sceneLoc}
                        genre={session.world.genre} />
            </>
          )}
          {kind === "world" && stats && <StatBars stats={stats} />}
        </div>
        <footer className="px-4 py-2 border-t border-stone-800 text-[10px] opacity-45 text-center">
          M 地图 · J 日志 · C 角色 · Tab 状态 · Esc 系统
        </footer>
      </div>
      <WorldDrawer open={relationsOpen} onClose={onRelationsToggle}
                   session={session} tensionCurve={tensionCurve} />
    </>
  );
}

function JournalList({
  pages, session, sid,
}: {
  pages: Page[];
  session: Session;
  sid: string;
  onUpdate: (s: Session) => void;
}) {
  return (
    <div className="space-y-4 text-[12px] leading-6">
      <div>
        <div className="text-[10px] uppercase tracking-widest opacity-60 mb-2">近事 · Recent Events</div>
        {pages.length === 0 ? (
          <div className="opacity-50">尚未起行。</div>
        ) : (
          <ul className="space-y-3">
            {[...pages].slice(-12).reverse().map((p) => {
              const narr = p.beats.find((b) => b.kind === "narration");
              const sys = p.beats.find((b) => b.kind === "system");
              return (
                <li key={p.page_no} className="border-l-2 border-amber-700/40 pl-2">
                  <div className="text-[10px] opacity-50">p.{p.page_no} · {p.scene.location_name}</div>
                  {sys && <div className="text-amber-300/90 text-[11px]">{sys.content}</div>}
                  {narr && <div className="opacity-85">{narr.content}</div>}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {/* TaskPanel embedded in journal */}
      <div className="opacity-80">
        <div className="text-[10px] uppercase tracking-widest opacity-60 mb-2">任务</div>
        {(session.tasks || []).length === 0 ? (
          <p className="opacity-50 text-[11px]">暂无进行中的任务。</p>
        ) : (
          <ul className="space-y-1 text-[11px]">
            {(session.tasks || []).map((t) => (
              <li key={t.id} className="flex justify-between gap-2 border-b border-stone-800/60 py-1">
                <span>{t.title}</span>
                <span className="opacity-50 shrink-0">{t.status}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function PlaySystemMenu({
  open, onClose, ttsOn, sfxOn, quality, reducedMotion,
  onTts, onSfx, onQuality, onReducedMotion, onExit,
}: {
  open: boolean;
  onClose: () => void;
  ttsOn: boolean;
  sfxOn: boolean;
  quality: PlayQuality;
  reducedMotion: boolean;
  onTts: (v: boolean) => void;
  onSfx: (v: boolean) => void;
  onQuality: (q: PlayQuality) => void;
  onReducedMotion: (v: boolean) => void;
  onExit: () => void;
}) {
  if (!open) return null;
  return (
    <>
      <div className="absolute inset-0 z-50 bg-black/60" onClick={onClose} />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50
                      w-[min(360px,92vw)] rounded-xl border border-stone-700 bg-stone-950 p-5 space-y-4">
        <h2 className="font-serif text-xl text-amber-100">系统</h2>
        <label className="flex items-center justify-between text-sm">
          <span>朗读 (TTS)</span>
          <input type="checkbox" checked={ttsOn} onChange={(e) => onTts(e.target.checked)} />
        </label>
        <label className="flex items-center justify-between text-sm">
          <span>音效</span>
          <input type="checkbox" checked={sfxOn} onChange={(e) => onSfx(e.target.checked)} />
        </label>
        <label className="flex items-center justify-between text-sm">
          <span>画面质量</span>
          <select value={quality} onChange={(e) => onQuality(e.target.value as PlayQuality)}
                  className="bg-stone-900 border border-stone-700 rounded px-2 py-1 text-xs">
            <option value="low">低</option>
            <option value="medium">中</option>
            <option value="high">高</option>
          </select>
        </label>
        <label className="flex items-center justify-between text-sm">
          <span>减少动态（晕动）</span>
          <input type="checkbox" checked={reducedMotion}
                 onChange={(e) => onReducedMotion(e.target.checked)} />
        </label>
        <div className="flex gap-2 pt-2">
          <button type="button" onClick={onClose}
                  className="flex-1 py-2 rounded border border-stone-600 text-sm">继续</button>
          <button type="button" onClick={onExit}
                  className="flex-1 py-2 rounded bg-rose-900/80 border border-rose-700 text-sm">
            退出游戏
          </button>
        </div>
      </div>
    </>
  );
}

export function ProximityNpcPrompt({
  npc, onTalk,
}: {
  npc: { id: string; name: string } | null;
  onTalk: () => void;
}) {
  if (!npc) return null;
  return (
    <div className="absolute bottom-24 inset-x-3 sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2
                    z-20 max-w-sm pointer-events-auto">
      <div className="rounded-xl border border-amber-600/50 bg-stone-950/85 backdrop-blur-md px-4 py-2.5
                      flex items-center justify-between gap-3">
        <span className="text-[13px] text-amber-100">{npc.name}</span>
        <button type="button" onClick={onTalk}
                className="px-3 py-1 rounded-full text-[11px] border border-amber-500/60
                           bg-amber-900/50 text-amber-50 hover:bg-amber-800/60">
          F 交谈
        </button>
      </div>
    </div>
  );
}

export function SceneNpcBar({
  sid, agents, playerId, currentLocationId, currentLocationName, genre,
}: {
  sid: string;
  agents: Agent[];
  playerId: string | null;
  currentLocationId: string | null;
  currentLocationName: string;
  genre?: string;
}) {
  const npcs = agents.filter(
    (a) => a.kind === "npc" && a.id !== playerId
      && (currentLocationId ? a.location_id === currentLocationId : true),
  ).slice(0, 6);

  if (npcs.length === 0) return null;

  return (
    <div className="absolute bottom-24 inset-x-3 sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2
                    z-20 max-w-lg pointer-events-auto">
      <div className="rounded-xl border border-stone-700/70 bg-stone-950/80 backdrop-blur-md px-3 py-2">
        <div className="text-[10px] opacity-55 mb-1.5">{currentLocationName} · 可交谈</div>
        <div className="flex flex-wrap gap-1.5">
          {npcs.map((n) => (
            <button key={n.id} type="button"
                    className="px-2.5 py-1 rounded-full text-[11px] border border-amber-700/40
                               bg-amber-950/40 text-amber-100 hover:bg-amber-900/50"
                    onClick={() => {
                      window.dispatchEvent(new CustomEvent("civsim:npc-talk", { detail: { sid, npcId: n.id } }));
                    }}>
              {n.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function PlayDialogueDock({
  visible, isOffline, isProxy, player, storyChoices, loading, input,
  actionError, onPick, onInput, onAdvance, onSubmit, onWake,
}: {
  visible: boolean;
  isOffline: boolean;
  isProxy: boolean;
  player?: Agent;
  storyChoices: ReturnType<typeof normalizeChoices>;
  loading: boolean;
  input: string;
  actionError: string | null;
  onPick: (action: string) => void;
  onInput: (v: string) => void;
  onAdvance: () => void;
  onSubmit: () => void;
  onWake: () => void;
}) {
  if (!visible) return null;

  return (
    <div className={`absolute bottom-0 inset-x-0 z-20 pointer-events-none transition-opacity duration-300
                     ${visible ? "opacity-100" : "opacity-0"}`}>
      <div className="pointer-events-auto mx-2 sm:mx-auto sm:max-w-2xl mb-3 sm:mb-4
                      rounded-xl border border-amber-700/40 bg-stone-950/90 backdrop-blur-md p-3 shadow-xl">
        {isOffline ? (
          <div className="text-[13px] opacity-80 py-2 text-center">
            {isProxy ? (
              <>角色正以 NPC 意志参与世界。{player?.offline_rationale && (
                <p className="mt-1 text-[12px] opacity-60">{player.offline_rationale}</p>
              )}</>
            ) : (
              <>角色休眠中——世界仍在推进。</>
            )}
            <button type="button" onClick={onWake} disabled={loading}
                    className="mt-3 px-4 py-2 rounded-md font-semibold bg-sky-500/80 text-stone-950
                               disabled:opacity-40">
              {isProxy ? "收回控制" : "苏醒"}
            </button>
          </div>
        ) : (
          <>
            {storyChoices.length > 0 && (
              <ChoicePanel choices={storyChoices} loading={loading} onPick={(c) => onPick(c.action)} />
            )}
            <div className="flex gap-2 mt-2">
              <input value={input} onChange={(e) => onInput(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && onSubmit()}
                     placeholder="自由输入行动…"
                     className="flex-1 rounded-md bg-stone-900/70 border border-stone-700
                                focus:border-amber-400 outline-none px-3 py-2 text-sm" />
              <button type="button" disabled={loading} onClick={onAdvance}
                      className="px-3 py-2 rounded-md border border-stone-600 text-sm
                                 hover:border-amber-400 disabled:opacity-40">前行</button>
              <button type="button" disabled={loading || !input.trim()} onClick={onSubmit}
                      className="px-4 py-2 rounded-md bg-amber-500/90 text-stone-900 font-semibold
                                 disabled:opacity-40">行动</button>
            </div>
            {actionError && <p className="mt-2 text-[11px] text-rose-300/90">{actionError}</p>}
          </>
        )}
      </div>
    </div>
  );
}
