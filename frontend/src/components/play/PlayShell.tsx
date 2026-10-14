"use client";

import type { Agent, Page, Session, WakeBriefing, WorldStats } from "@/lib/api";
import { AppError } from "@/lib/errors";
import type { ReadableBeat } from "@/lib/pageBeats";
import WorldAtlas from "@/components/WorldAtlas";
import WorldDrawer from "@/components/WorldDrawer";
import NpcPanel from "@/components/NpcPanel";
import SkillPanel from "@/components/SkillPanel";
import ChoicePanel, { normalizeChoices } from "@/components/ChoicePanel";
import CharacterFigurePreview from "@/components/CharacterFigurePreview";
import TaskPanel from "@/components/TaskPanel";
import QuotaNotice from "@/components/play/QuotaNotice";
import DependencyStatus from "@/components/play/DependencyStatus";
import StoryDirectorPanel from "@/components/StoryDirectorPanel";
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
  reconnectFailed, reconnectAttempt, reconnectError, onRetryReconnect,
  serviceError, onDismissServiceError, onRetryServiceError,
  onWake, onSleep, onOpenSystem, onOpenOverlay,
}: {
  session: Session;
  player?: Agent;
  isOffline: boolean;
  isProxy: boolean;
  isDormant: boolean;
  degraded: boolean;
  reconnecting: boolean;
  reconnectFailed?: boolean;
  reconnectAttempt?: number;
  reconnectError?: string | null;
  onRetryReconnect?: () => void;
  serviceError?: AppError | string | null;
  onDismissServiceError?: () => void;
  onRetryServiceError?: () => void;
  onWake: () => void;
  onSleep: () => void;
  onOpenSystem: () => void;
  onOpenOverlay: (key: OverlayKey) => void;
}) {
  const rosterCount = session.player_ids?.length || session.roster?.length || 1;
  const cap = session.max_players || 8;
  const showReconnectBar = Boolean(reconnecting || reconnectFailed || (degraded && reconnectError));
  const appErr = serviceError instanceof AppError ? serviceError : null;
  const plainErr = typeof serviceError === "string" ? serviceError : null;
  const playerInitial = player?.name?.trim()?.slice(0, 1) || "?";
  return (
    <div className="absolute top-0 inset-x-0 z-20 pointer-events-none">
      {appErr?.category === "quota" && (
        <QuotaNotice error={appErr} onDismiss={onDismissServiceError} />
      )}
      {appErr?.category === "dependency" && (
        <DependencyStatus
          error={appErr}
          onRetry={onRetryServiceError}
          onDismiss={onDismissServiceError}
        />
      )}
      {appErr && appErr.category !== "quota" && appErr.category !== "dependency" && (
        <div className="pointer-events-auto mx-3 mt-2 sm:mx-auto sm:max-w-xl
                        rounded-lg border border-rose-700/50 bg-rose-950/90 px-3 py-2
                        text-[12px] text-rose-100 flex gap-2 items-start shadow-lg">
          <p className="flex-1 leading-relaxed">{appErr.displayMessage()}</p>
          {onDismissServiceError && (
            <button type="button" onClick={onDismissServiceError}
                    className="shrink-0 opacity-70 hover:opacity-100 text-[11px]">
              关闭
            </button>
          )}
        </div>
      )}
      {plainErr && (
        <div className="pointer-events-auto mx-3 mt-2 sm:mx-auto sm:max-w-xl
                        rounded-lg border border-rose-700/50 bg-rose-950/90 px-3 py-2
                        text-[12px] text-rose-100 flex gap-2 items-start shadow-lg">
          <p className="flex-1 leading-relaxed">{plainErr}</p>
          {onDismissServiceError && (
            <button type="button" onClick={onDismissServiceError}
                    className="shrink-0 opacity-70 hover:opacity-100 text-[11px]">
              关闭
            </button>
          )}
        </div>
      )}
      {showReconnectBar && (
        <div className="pointer-events-auto mx-3 mt-2 sm:mx-auto sm:max-w-xl
                        rounded-lg border border-amber-700/50 bg-amber-950/90 px-3 py-2
                        text-[12px] text-amber-50 flex gap-2 items-center shadow-lg">
          <p className="flex-1 leading-relaxed">
            {reconnectError
              || (reconnecting
                ? `连接断开，正在重连${reconnectAttempt ? `（${reconnectAttempt}）` : ""}…`
                : "HTTP 降级同步中")}
          </p>
          {reconnectFailed && onRetryReconnect && (
            <button type="button" onClick={onRetryReconnect}
                    className="shrink-0 px-2.5 py-1 rounded border border-amber-500/60
                               bg-amber-900/40 hover:bg-amber-800/50 text-[11px]">
              重连
            </button>
          )}
        </div>
      )}
      <div className="flex items-start justify-between gap-3 p-3 sm:p-4
                      bg-gradient-to-b from-black/75 via-black/40 to-transparent">
        <div className="min-w-0 pointer-events-auto">
          <div className="font-serif text-lg sm:text-xl text-[var(--play-ink)] truncate drop-shadow">
            《{session.world.name}》
          </div>
          <div className="text-[10px] uppercase tracking-widest text-[var(--play-ink-muted)]">
            {session.world.genre} · {session.world.clock?.label || `第 ${session.world.clock?.tick ?? 0} 时`}
            <span className="ml-2 text-[var(--play-amber)] normal-case">· {rosterCount}/{cap} 人</span>
            {isDormant && <span className="ml-2 text-sky-300 normal-case">· 休眠</span>}
            {isProxy && <span className="ml-2 text-emerald-300 normal-case">· 代行</span>}
            {degraded && !showReconnectBar && (
              <span className="ml-2 text-[var(--play-amber-hot)] normal-case">
                · {reconnecting ? "重连中…" : "HTTP 降级同步"}
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 shrink-0 pointer-events-auto">
          {player && (
            <button type="button" onClick={() => onOpenOverlay("character")}
                    className="play-btn-ghost !min-h-0 gap-1.5 text-xs !px-2 !py-1" title={player.name}>
              <span className="w-6 h-6 rounded-full border border-[var(--play-line)]
                               bg-[var(--play-deep)]/80
                               flex items-center justify-center font-serif text-[var(--play-ink)] text-[12px]">
                {playerInitial}
              </span>
              <span className="font-serif text-sm text-[var(--play-amber)] max-w-[7rem] truncate hidden xs:inline sm:inline">
                {player.name}
              </span>
            </button>
          )}
          {isOffline ? (
            <button type="button" onClick={onWake}
                    className="play-btn-ghost !min-h-0 text-sm border-emerald-500/60 text-emerald-200
                               hover:border-emerald-400/70">
              {isProxy ? "收回控制" : "苏醒"}
            </button>
          ) : (
            <button type="button" onClick={onSleep}
                    className="play-btn-ghost !min-h-0 text-sm hover:border-sky-400/50">
              离线
            </button>
          )}
          <button type="button" onClick={onOpenSystem}
                  className="play-btn-ghost !min-h-0 text-xs" title="系统 (Esc)">
            系统
          </button>
        </div>
      </div>
    </div>
  );
}

export function RoomRosterPanel({
  open, onClose, session, isHost, busyId, error, onKick, onTransfer,
}: {
  open: boolean;
  onClose: () => void;
  session: Session;
  isHost: boolean;
  busyId?: string | null;
  error?: string | null;
  onKick: (playerId: string) => void;
  onTransfer: (userId: string) => void;
}) {
  if (!open) return null;
  const roster = session.roster?.length
    ? session.roster
    : (session.player_ids || []).map((pid) => ({
        player_id: pid,
        user_id: null as string | null,
        name: session.agents.find((a) => a.id === pid)?.name || pid,
        presence: session.agents.find((a) => a.id === pid)?.presence || "unknown",
        is_self: pid === session.player_id,
        is_host: false,
      }));
  const cap = session.max_players || 8;

  return (
    <>
      <div className="absolute inset-0 z-40 bg-black/55 backdrop-blur-[1px]"
           onClick={onClose} role="presentation" />
      <div className="absolute inset-x-2 sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2
                      top-16 z-50 w-auto sm:w-[min(420px,94vw)]
                      rounded-xl border border-stone-700/80 bg-stone-950/95 shadow-2xl overflow-hidden">
        <header className="flex items-center justify-between px-4 py-3 border-b border-stone-800">
          <div>
            <h2 className="font-serif text-lg text-amber-100">同世旅人</h2>
            <p className="text-[11px] opacity-55 mt-0.5">{roster.length}/{cap} · 房主可踢人 / 转让</p>
          </div>
          <button type="button" onClick={onClose}
                  className="text-stone-400 hover:text-amber-200 text-sm px-2 py-1">关闭</button>
        </header>
        <ul className="max-h-[50vh] overflow-y-auto divide-y divide-stone-800/80">
          {roster.map((row) => {
            const busy = busyId === row.player_id || (row.user_id && busyId === row.user_id);
            return (
              <li key={row.player_id} className="px-4 py-3 flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-amber-50 truncate">
                    {row.name}
                    {row.is_self && <span className="ml-1.5 text-[10px] opacity-50">你</span>}
                    {row.is_host && <span className="ml-1.5 text-[10px] text-amber-300/80">房主</span>}
                  </div>
                  <div className="text-[10px] opacity-45 mt-0.5">{row.presence}</div>
                </div>
                {isHost && !row.is_self && (
                  <div className="flex gap-1.5 shrink-0">
                    {row.user_id && (
                      <button type="button" disabled={Boolean(busy)}
                              onClick={() => onTransfer(row.user_id!)}
                              className="px-2 py-1 rounded border border-stone-600 text-[11px]
                                         hover:border-amber-400/60 disabled:opacity-40">
                        转让
                      </button>
                    )}
                    <button type="button" disabled={Boolean(busy)}
                            onClick={() => onKick(row.player_id)}
                            className="px-2 py-1 rounded border border-rose-800/70 text-[11px] text-rose-200
                                       hover:border-rose-400/70 disabled:opacity-40">
                      踢出
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
        {error && (
          <p className="px-4 py-2 text-[11px] text-rose-300 border-t border-stone-800">{error}</p>
        )}
        {!isHost && (
          <p className="px-4 py-2 text-[10px] opacity-45 border-t border-stone-800">
            仅房主可踢人与转让房主。
          </p>
        )}
      </div>
    </>
  );
}

export function PlayOverlay({
  kind, onClose, session, stats, pages, tensionCurve, sid, player,
  sceneLocId, sceneLoc, loading, isOffline, skills, onUseSkill,
  relationsOpen, onRelationsToggle, onSessionUpdate, fullscreenSheet,
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
  onSessionUpdate?: (s: Session) => void;
  /** Mobile narrative: edge-to-edge sheet (architecture §9.7). */
  fullscreenSheet?: boolean;
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
      <div
        className={
          fullscreenSheet
            ? `absolute inset-0 z-40 border-0 rounded-none bg-stone-950
               shadow-none flex flex-col overflow-hidden`
            : `absolute inset-x-2 sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2
               top-14 bottom-4 sm:w-[min(720px,96vw)] z-40
               rounded-xl border border-stone-700/80 bg-stone-950/95
               shadow-2xl flex flex-col overflow-hidden`
        }
      >
        <header className="flex items-center justify-between px-4 py-3 border-b border-stone-800
                           pt-[max(0.75rem,env(safe-area-inset-top))]">
          <h2 className="font-serif text-lg text-amber-100">{titles[kind]}</h2>
          <button type="button" onClick={onClose}
                  className="text-stone-400 hover:text-amber-200 text-sm px-3 py-2 min-h-[44px]">
            {fullscreenSheet ? "关闭" : "Esc 关闭"}
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-4 space-y-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          {kind === "map" && (
            <div className={`${fullscreenSheet ? "h-[min(70vh,560px)]" : "h-[min(420px,50vh)]"}
                            rounded-lg border border-stone-800 bg-stone-900/50
                            flex items-center justify-center p-2`}>
              <WorldAtlas session={session} stats={stats} />
            </div>
          )}
          {kind === "journal" && (
            <JournalList
              pages={pages}
              session={session}
              sid={sid}
              onUpdate={onSessionUpdate || (() => {})}
            />
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
  pages, session, sid, onUpdate,
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
      <TaskPanel sid={sid} session={session} onUpdate={onUpdate} />
    </div>
  );
}

export function PlaySystemMenu({
  open, onClose, ttsOn, sfxOn, bgmOn, sceneArtOn, ttsRate, ttsReadSpeech,
  quality, reducedMotion, cameraMode,
  onTts, onSfx, onBgm, onSceneArt, onTtsRate, onTtsReadSpeech,
  onQuality, onReducedMotion, onCameraMode, onExit,
  onInvite, onRoster, onOpenOverlay,
  showStoryDirector, sid, session, onSessionUpdate,
  mobileNarrative, worldPreview, onWorldPreview,
}: {
  open: boolean;
  onClose: () => void;
  ttsOn: boolean;
  sfxOn: boolean;
  bgmOn: boolean;
  sceneArtOn: boolean;
  ttsRate: number;
  ttsReadSpeech: boolean;
  quality: PlayQuality;
  reducedMotion: boolean;
  cameraMode: "third" | "first";
  onTts: (v: boolean) => void;
  onSfx: (v: boolean) => void;
  onBgm: (v: boolean) => void;
  onSceneArt: (v: boolean) => void;
  onTtsRate: (v: number) => void;
  onTtsReadSpeech: (v: boolean) => void;
  onQuality: (q: PlayQuality) => void;
  onReducedMotion: (v: boolean) => void;
  onCameraMode: (m: "third" | "first") => void;
  onExit: () => void;
  onInvite?: () => void;
  onRoster?: () => void;
  onOpenOverlay: (key: OverlayKey) => void;
  showStoryDirector?: boolean;
  sid?: string;
  session?: Session;
  onSessionUpdate?: (s: Session) => void;
  mobileNarrative?: boolean;
  worldPreview?: boolean;
  onWorldPreview?: (v: boolean) => void;
}) {
  if (!open) return null;
  return (
    <>
      <div className="absolute inset-0 z-50 bg-black/60" onClick={onClose} />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50
                      w-[min(400px,92vw)] rounded-xl border border-stone-700 bg-stone-950 p-5 space-y-3 max-h-[85vh] overflow-y-auto">
        <h2 className="font-serif text-xl text-amber-100">系统</h2>
        <p className="text-[11px] text-amber-200/65 leading-relaxed border border-amber-900/40
                      rounded-lg px-3 py-2 bg-amber-950/20">
          Tech Preview：退出前会写入快照；重启服务后可从「我的世界」续玩（方案 B 预览，非 bit-perfect）。
        </p>

        <div className="space-y-1.5">
          <p className="text-[10px] uppercase tracking-widest opacity-50">旅程</p>
          <div className="grid grid-cols-2 gap-1.5">
            <button type="button" onClick={() => { onOpenOverlay("map"); onClose(); }}
                    className="px-2 py-2 rounded border border-stone-700 text-xs hover:border-amber-400/50">
              M 地图
            </button>
            <button type="button" onClick={() => { onOpenOverlay("journal"); onClose(); }}
                    className="px-2 py-2 rounded border border-stone-700 text-xs hover:border-amber-400/50">
              J 日志
            </button>
            <button type="button" onClick={() => { onOpenOverlay("character"); onClose(); }}
                    className="px-2 py-2 rounded border border-stone-700 text-xs hover:border-amber-400/50">
              C 角色
            </button>
            <button type="button" onClick={() => { onOpenOverlay("world"); onClose(); }}
                    className="px-2 py-2 rounded border border-stone-700 text-xs hover:border-amber-400/50">
              Tab 状态
            </button>
            {onRoster && (
              <button type="button" onClick={() => { onRoster(); onClose(); }}
                      className="px-2 py-2 rounded border border-stone-700 text-xs hover:border-amber-400/50">
                同世旅人
              </button>
            )}
            {onInvite && (
              <button type="button" onClick={() => { onInvite(); onClose(); }}
                      className="px-2 py-2 rounded border border-amber-800/50 text-xs text-amber-100
                                 hover:border-amber-400/60">
                邀请链接
              </button>
            )}
          </div>
        </div>

        {mobileNarrative && onWorldPreview && (
          <label className="flex items-center justify-between text-sm">
            <span>3D 世界预览</span>
            <input type="checkbox" checked={Boolean(worldPreview)}
                   onChange={(e) => onWorldPreview(e.target.checked)} />
          </label>
        )}
        {!mobileNarrative && (
          <label className="flex items-center justify-between text-sm">
            <span>相机视角 (V)</span>
            <button type="button"
                    onClick={() => onCameraMode(cameraMode === "third" ? "first" : "third")}
                    className="px-2.5 py-1 rounded border border-amber-700/50 text-[11px] text-amber-100
                               bg-stone-900 hover:border-amber-400/60">
              {cameraMode === "third" ? "跟拍 · 第三视角" : "漫游 · 第一人称"}
            </button>
          </label>
        )}
        <label className="flex items-center justify-between text-sm">
          <span>朗读 (TTS)</span>
          <input type="checkbox" checked={ttsOn} onChange={(e) => onTts(e.target.checked)} />
        </label>
        <label className="flex items-center justify-between text-sm opacity-90">
          <span>朗读语速</span>
          <input
            type="range" min={0.7} max={1.3} step={0.05} value={ttsRate}
            disabled={!ttsOn}
            onChange={(e) => onTtsRate(Number(e.target.value))}
            className="w-28"
          />
        </label>
        <label className="flex items-center justify-between text-sm opacity-90">
          <span>朗读对白</span>
          <input type="checkbox" checked={ttsReadSpeech} disabled={!ttsOn}
                 onChange={(e) => onTtsReadSpeech(e.target.checked)} />
        </label>
        <label className="flex items-center justify-between text-sm">
          <span>背景音乐 (BGM)</span>
          <input type="checkbox" checked={bgmOn} onChange={(e) => onBgm(e.target.checked)} />
        </label>
        <label className="flex items-center justify-between text-sm">
          <span>场景插画</span>
          <input type="checkbox" checked={sceneArtOn} onChange={(e) => onSceneArt(e.target.checked)} />
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

        {showStoryDirector && sid && session && onSessionUpdate && (
          <div className="pt-1 border-t border-stone-800">
            <StoryDirectorPanel sid={sid} session={session} onUpdate={onSessionUpdate} />
          </div>
        )}

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
  npc, onTalk, raised,
}: {
  npc: { id: string; name: string } | null;
  onTalk: () => void;
  /** Lift above dialogue dock when dock is open. */
  raised?: boolean;
}) {
  if (!npc) return null;
  return (
    <div
      className={`absolute inset-x-3 sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2
                  z-20 max-w-sm pointer-events-auto ${raised ? "bottom-[var(--play-dock-clearance)]" : "bottom-6"}`}
    >
      <div className="play-panel px-4 py-2.5 flex items-center justify-between gap-3">
        <span className="text-[13px] text-[var(--play-ink)]">{npc.name}</span>
        <button type="button" onClick={onTalk}
                className="play-cta !min-h-0 !py-1 !px-3 text-[11px]">
          F 交谈
        </button>
      </div>
    </div>
  );
}

export function SceneNpcBar({
  sid, agents, playerId, currentLocationId, currentLocationName, raised,
}: {
  sid: string;
  agents: Agent[];
  playerId: string | null;
  currentLocationId: string | null;
  currentLocationName: string;
  genre?: string;
  raised?: boolean;
}) {
  const npcs = agents.filter(
    (a) => a.kind === "npc" && a.id !== playerId
      && (currentLocationId ? a.location_id === currentLocationId : true),
  ).slice(0, 6);

  if (npcs.length === 0) return null;

  return (
    <div
      className={`absolute inset-x-3 sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2
                  z-20 pointer-events-auto w-full sm:w-[min(100%,var(--play-dock-max))]
                  ${raised ? "bottom-[var(--play-dock-clearance)]" : "bottom-6"}`}
    >
      <div className="play-panel px-3 py-2">
        <div className="text-[10px] text-[var(--play-ink-muted)] mb-1.5">{currentLocationName} · 可交谈</div>
        <LocationNpcChips sid={sid} npcs={npcs} />
      </div>
    </div>
  );
}

function LocationNpcChips({
  sid, npcs,
}: {
  sid: string;
  npcs: Agent[];
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {npcs.map((n) => (
        <button key={n.id} type="button"
                className="px-2.5 py-1 rounded-md text-[11px] border border-[var(--play-line)]
                           bg-[var(--play-deep)]/70 text-[var(--play-ink)]
                           hover:border-[var(--play-amber)]"
                onClick={() => {
                  window.dispatchEvent(new CustomEvent("civsim:npc-talk", { detail: { sid, npcId: n.id } }));
                }}>
          {n.name}
        </button>
      ))}
    </div>
  );
}

export function PlayDialogueDock({
  visible, isOffline, isProxy, player, storyChoices, loading, input,
  actionError, beats, pageKey, reducedMotion, locationNpcs, locationName, sid,
  onPick, onInput, onAdvance, onSubmit, onWake,
  embedded, hideAdvance, onCollapse,
}: {
  visible: boolean;
  isOffline: boolean;
  isProxy: boolean;
  player?: Agent;
  storyChoices: ReturnType<typeof normalizeChoices>;
  loading: boolean;
  input: string;
  actionError: AppError | string | null;
  beats?: ReadableBeat[];
  /** Changes when a new page arrives — drives narration enter animation. */
  pageKey?: string | number;
  reducedMotion?: boolean;
  locationNpcs?: Agent[];
  locationName?: string;
  sid?: string;
  onPick: (action: string) => void;
  onInput: (v: string) => void;
  onAdvance: () => void;
  onSubmit: () => void;
  onWake: () => void;
  /** Parent owns positioning (mobile narrative stack). */
  embedded?: boolean;
  /** Hide 前行 when mobile chrome already provides it. */
  hideAdvance?: boolean;
  /** Desktop: collapse dock to restore clean EXPLORE chrome. */
  onCollapse?: () => void;
}) {
  if (!visible) return null;
  const hasBeats = Boolean(beats?.length);

  const card = (
      <div
        className={`pointer-events-auto w-full play-panel p-3 shadow-xl
                    ${reducedMotion ? "" : "play-dock-enter"}`}
      >
        {onCollapse && !isOffline && (
          <div className="flex justify-end -mt-0.5 mb-1">
            <button type="button" onClick={onCollapse}
                    className="text-[10px] text-[var(--play-ink-muted)] hover:text-[var(--play-ink)] px-1.5 py-0.5">
              收起叙事
            </button>
          </div>
        )}
        {isOffline ? (
          <div className="text-[13px] text-[var(--play-ink-muted)] py-2 text-center">
            {isProxy ? (
              <>角色正以 NPC 意志参与世界。{player?.offline_rationale && (
                <p className="mt-1 text-[12px] opacity-70">{player.offline_rationale}</p>
              )}</>
            ) : (
              <>角色休眠中——世界仍在推进。</>
            )}
            <button type="button" onClick={onWake} disabled={loading}
                    className="play-cta mt-3 !bg-sky-400/90 hover:!bg-sky-300 disabled:opacity-40">
              {isProxy ? "收回控制" : "苏醒"}
            </button>
          </div>
        ) : (
          <>
            {sid && locationNpcs && locationNpcs.length > 0 && (
              <div className="mb-2 pb-2 border-b border-[var(--play-line)]/50">
                <div className="text-[10px] text-[var(--play-ink-muted)] mb-1.5">
                  {locationName || "此地"} · 可交谈
                </div>
                <LocationNpcChips sid={sid} npcs={locationNpcs} />
              </div>
            )}
            {hasBeats && (
              <div
                key={pageKey ?? "beats"}
                className={`mb-2 max-h-[min(28vh,220px)] overflow-y-auto space-y-2 pr-1
                            ${reducedMotion ? "" : "play-narration-enter"}`}
              >
                {beats!.map((b, i) => (
                  <p
                    key={`${b.kind}-${i}-${b.content.slice(0, 12)}`}
                    className="font-serif leading-relaxed text-[var(--play-narration-size)] text-[var(--play-ink)]"
                  >
                    {b.kind === "speech" && b.speaker && (
                      <span className="speaker !bg-[var(--play-deep)]/70 !text-[var(--play-ink)] !border-[var(--play-line)]">
                        {b.speaker}
                      </span>
                    )}
                    {b.content}
                  </p>
                ))}
              </div>
            )}
            {storyChoices.length > 0 && (
              <ChoicePanel choices={storyChoices} loading={loading} onPick={(c) => onPick(c.action)} />
            )}
            <div className="flex gap-2 mt-2">
              <input value={input} onChange={(e) => onInput(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && !loading && onSubmit()}
                     placeholder="自由输入行动…"
                     disabled={loading}
                     className="flex-1 rounded-md bg-[var(--play-deep)]/80
                                border border-[var(--play-line)] text-[var(--play-ink)]
                                focus:border-[var(--play-amber-hot)] outline-none px-3 py-2 text-sm min-h-[44px]
                                placeholder:text-[var(--play-ink-muted)] disabled:opacity-50" />
              {!hideAdvance && (
                <button type="button" disabled={loading} onClick={onAdvance}
                        className="play-btn-ghost text-sm">前行</button>
              )}
              <button type="button" disabled={loading || !input.trim()} onClick={onSubmit}
                      className="play-cta">行动</button>
            </div>
            {actionError && (
              <p className="mt-2 text-[11px] text-rose-300/90">
                {actionError instanceof AppError ? actionError.displayMessage() : actionError}
              </p>
            )}
          </>
        )}
      </div>
  );

  if (embedded) return card;

  return (
    <div className="absolute bottom-0 inset-x-0 z-20 pointer-events-none">
      <div className="mx-2 sm:mx-auto mb-3 sm:mb-4 w-auto sm:w-full sm:max-w-[var(--play-dock-max)]">
        {card}
      </div>
    </div>
  );
}
