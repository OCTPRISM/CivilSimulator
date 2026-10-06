"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getSession, sendHeartbeat, sleepSession, sleepSessionKeepalive, stepSession, useSkill, wakeSession,
  kickPlayer, transferHost,
  type Page, type Session, type WakeBriefing, type WorldStats, type Agent,
} from "@/lib/api";
import { useTTS, usePageTurnSound, useBgm } from "@/lib/audio";
import { loadPlaySettings, savePlaySettings } from "@/lib/playSettings";
import { derivePlayMode, overlayFromKey, toggleOverlay, type OverlayKey } from "@/lib/playState";
import {
  clearBoundPlayerId, getBoundPlayerId, inviteUrl, setBoundPlayerId, withBoundPlayerId,
} from "@/lib/playIdentity";
import { useSessionWebSocket } from "@/hooks/useSessionWebSocket";
import { useAuth } from "@/lib/auth";
import World3D from "@/components/World3D";
import ScenePlate from "@/components/ScenePlate";
import { WorldPresentationStore } from "@/lib/worldPresentationStore";
import WakeBriefingModal from "@/components/WakeBriefingModal";
import InjectPanel from "@/components/InjectPanel";
import { normalizeChoices } from "@/components/ChoicePanel";
import {
  PlayHud, PlayOverlay, PlaySystemMenu, SceneNpcBar, PlayDialogueDock, ProximityNpcPrompt,
  RoomRosterPanel,
} from "@/components/play/PlayShell";

const WALK_PROMPTS = [
  "继续向前走了一段。",
  "沿路而行，留意四周。",
  "脚步未停，景致更替。",
  "前行片刻，气息陡变。",
];

const TAB_SLEEP_MS = 60_000;
const IS_DEV = process.env.NODE_ENV === "development";

export default function PlayPage({ params }: { params: { sid: string } }) {
  const sid = params.sid;
  const router = useRouter();
  const { user } = useAuth();
  const initialSettings = loadPlaySettings();

  const [session, setSession] = useState<Session | null>(null);
  const [pages, setPages] = useState<Page[]>([]);
  const [stats, setStats] = useState<WorldStats | undefined>();
  const [tensionCurve, setTensionCurve] = useState<number[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<OverlayKey | null>(null);
  const [systemOpen, setSystemOpen] = useState(false);
  const [relationsOpen, setRelationsOpen] = useState(false);
  const [rosterOpen, setRosterOpen] = useState(false);
  const [rosterBusy, setRosterBusy] = useState<string | null>(null);
  const [rosterError, setRosterError] = useState<string | null>(null);
  const [kickedOut, setKickedOut] = useState(false);
  const [ttsOn, setTtsOn] = useState(initialSettings.tts);
  const [sfxOn, setSfxOn] = useState(initialSettings.sfx);
  const [bgmOn, setBgmOn] = useState(initialSettings.bgm);
  const [sceneArtOn, setSceneArtOn] = useState(initialSettings.sceneArt);
  const [ttsRate, setTtsRate] = useState(initialSettings.ttsRate);
  const [ttsReadSpeech, setTtsReadSpeech] = useState(initialSettings.ttsReadSpeech);
  const [quality, setQuality] = useState(initialSettings.quality);
  const [reducedMotion, setReducedMotion] = useState(initialSettings.reducedMotion);
  const [cameraMode, setCameraMode] = useState<"third" | "first">(initialSettings.cameraMode);
  const [briefing, setBriefing] = useState<WakeBriefing | null>(null);
  const [nearbyNpc, setNearbyNpc] = useState<Agent | null>(null);
  const presentationRef = useRef(new WorldPresentationStore());
  const nearbyNpcRef = useRef<Agent | null>(null);
  const talkNearbyNpcRef = useRef<() => void>(() => {});
  const [dialoguePinned, setDialoguePinned] = useState(false);
  const walkRng = useRef(0);
  const sleepTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { speak, stop, setSpeakingListener, readSpeech } = useTTS(ttsOn, {
    rate: ttsRate,
    readSpeech: ttsReadSpeech,
  });
  const { play: playTurn } = usePageTurnSound(sfxOn);
  const { setDucked } = useBgm(bgmOn, session?.world?.genre);

  useEffect(() => {
    setSpeakingListener((speaking) => setDucked(speaking));
    return () => setSpeakingListener(undefined);
  }, [setSpeakingListener, setDucked]);

  const kickedOutRef = useRef(false);

  const applySession = useCallback((s: Session) => {
    // Ignore late WS/HTTP updates after kick (MP-2).
    if (kickedOutRef.current) return;
    const next = withBoundPlayerId(sid, s);
    if (next.player_id) setBoundPlayerId(sid, next.player_id);
    setSession(next);
    presentationRef.current.seedFromAgents(next.agents);
    if (next.pages?.length) setPages(next.pages);
    if (next.stats) setStats(next.stats);
    if (next.tension_curve) setTensionCurve(next.tension_curve);
    sessionStorage.setItem(`sess_${sid}`, JSON.stringify(next));
  }, [sid]);

  const onWsTransform = useCallback((t: { agent_id: string; world_x: number; world_z: number; behavior?: string }) => {
    presentationRef.current.applyTransform(t);
  }, []);

  const onWsTransforms = useCallback((ts: Array<{ agent_id: string; world_x: number; world_z: number; behavior?: string }>) => {
    presentationRef.current.applyBatch(ts);
  }, []);

  const onNearbyNpc = useCallback((npc: Agent | null) => {
    nearbyNpcRef.current = npc;
    setNearbyNpc(npc);
  }, []);

  const onWsPage = useCallback((page: Page, newStats?: WorldStats) => {
    setPages((ps) => {
      if (ps.some((p) => p.page_no === page.page_no)) return ps;
      return [...ps, page];
    });
    if (newStats) setStats(newStats);
    setTensionCurve((c) =>
      page.tension !== undefined ? [...c, page.tension].slice(-32) : c,
    );
  }, []);

  const onWsPresence = useCallback((playerId: string, presence: string) => {
    setSession((prev) => {
      if (!prev) return prev;
      const agents = prev.agents.map((a) =>
        a.id === playerId ? { ...a, presence: presence as Agent["presence"] } : a,
      );
      const next = withBoundPlayerId(sid, { ...prev, agents });
      sessionStorage.setItem(`sess_${sid}`, JSON.stringify(next));
      return next;
    });
  }, [sid]);

  const onPlayerJoined = useCallback((playerId: string, agent?: Agent, room?: Session) => {
    if (room) {
      applySession(room);
      return;
    }
    if (!agent) return;
    setSession((prev) => {
      if (!prev) return prev;
      const agents = prev.agents.some((a) => a.id === agent.id)
        ? prev.agents.map((a) => (a.id === agent.id ? { ...a, ...agent } : a))
        : [...prev.agents, agent];
      const player_ids = prev.player_ids?.includes(playerId)
        ? prev.player_ids
        : [...(prev.player_ids || []), playerId];
      const next = withBoundPlayerId(sid, { ...prev, agents, player_ids });
      sessionStorage.setItem(`sess_${sid}`, JSON.stringify(next));
      return next;
    });
  }, [sid, applySession]);

  const onKicked = useCallback(() => {
    kickedOutRef.current = true;
    clearBoundPlayerId(sid);
    sessionStorage.removeItem(`sess_${sid}`);
    setKickedOut(true);
    setSession(null);
    setRosterOpen(false);
  }, [sid]);

  const boundPlayerId = session?.player_id || getBoundPlayerId(sid);

  const wsConn = useSessionWebSocket({
    sid,
    playerId: boundPlayerId,
    enabled: Boolean(session) && !kickedOut,
    onSession: applySession,
    onPage: onWsPage,
    onPresence: onWsPresence,
    onAgentTransform: onWsTransform,
    onAgentTransforms: onWsTransforms,
    onPlayerJoined,
    onKicked,
  });

  const isHost = Boolean(
    user && session && (
      session.host_user_id === user.id
      || session.roster?.some((r) => r.is_self && r.is_host)
    ),
  );

  const onKick = useCallback(async (playerId: string) => {
    setRosterBusy(playerId);
    setRosterError(null);
    try {
      const j = await kickPlayer(sid, playerId);
      if (j.session) applySession(j.session);
    } catch (e) {
      setRosterError(e instanceof Error ? e.message : "踢人失败");
    } finally {
      setRosterBusy(null);
    }
  }, [sid, applySession]);

  const onTransfer = useCallback(async (toUserId: string) => {
    setRosterBusy(toUserId);
    setRosterError(null);
    try {
      const j = await transferHost(sid, toUserId);
      if (j.session) applySession(j.session);
    } catch (e) {
      setRosterError(e instanceof Error ? e.message : "转让失败");
    } finally {
      setRosterBusy(null);
    }
  }, [sid, applySession]);

  const handleMove = useCallback((world_x: number, world_z: number) => {
    wsConn.send({ type: "move", world_x, world_z, player_id: boundPlayerId });
  }, [wsConn.send, boundPlayerId]);

  const player = session?.agents.find((a) => a.id === session.player_id);
  const isDormant = player?.presence === "dormant";
  const isProxy = player?.presence === "proxy";
  const isOffline = isDormant || isProxy;
  const explorationEnabled = session?.world?.visual_capabilities?.exploration_enabled === true;
  const characterLod = session?.world?.visual_capabilities?.character_lod === "low" ? "low" : "standard";

  useEffect(() => {
    const cached = sessionStorage.getItem(`sess_${sid}`);
    if (cached) {
      try {
        const s: Session = JSON.parse(cached);
        applySession(s);
      } catch { /* ignore */ }
    }
    const pid = getBoundPlayerId(sid);
    setLoadError(null);
    getSession(sid, pid)
      .then((j) => {
        if (j.session) {
          applySession(j.session);
          setLoadError(null);
          const me = j.session.player_id;
          const agent = j.session.agents?.find((a) => a.id === me);
          if (agent?.presence === "dormant" || agent?.presence === "proxy") {
            wakeSession(sid, me).then((w) => {
              if (w.session) applySession(w.session);
              if (w.briefing) setBriefing(w.briefing);
            }).catch(() => {});
          }
        }
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "无法载入世界";
        // Dead / unauthorized rooms: drop stale cache so we don't render a ghost world.
        sessionStorage.removeItem(`sess_${sid}`);
        setSession(null);
        setPages([]);
        if (/401|未登录|登录/.test(msg)) {
          setLoadError("需要登录后才能进入该世界");
        } else if (/403|成员|无权|forbidden/i.test(msg)) {
          setLoadError("你不是该世界的成员");
        } else if (/404|not found|不存在|结束|找不到|快照/i.test(msg)) {
          setLoadError("找不到该世界（无快照或快照不可恢复）");
        } else {
          setLoadError(msg || "无法载入世界");
        }
      });
  }, [sid, applySession]);

  // HTTP fallback poll only when WS degraded (v1.4 NET-010)
  useEffect(() => {
    if (!session || wsConn.connected) return;
    const poll = () => {
      getSession(sid, getBoundPlayerId(sid))
        .then((j) => { if (j.session) applySession(j.session); })
        .catch(() => {});
    };
    poll();
    const iv = setInterval(poll, 4000);
    return () => clearInterval(iv);
  }, [sid, applySession, session, wsConn.connected]);

  useEffect(() => {
    if (!session) return;
    const pid = session.player_id;
    const beat = () => {
      const p = session.agents.find((a) => a.id === pid);
      if (p?.presence === "dormant" || p?.presence === "proxy") return;
      sendHeartbeat(sid, pid).catch(() => {});
    };
    beat();
    const iv = setInterval(beat, 12_000);

    const clearSleepTimer = () => {
      if (sleepTimer.current) {
        clearTimeout(sleepTimer.current);
        sleepTimer.current = null;
      }
    };

    const onVis = () => {
      if (document.visibilityState === "hidden") {
        clearSleepTimer();
        sleepTimer.current = setTimeout(() => {
          sleepSession(sid, "tab_hidden", pid).then((j) => {
            if (j.session) applySession(j.session);
          }).catch(() => {});
        }, TAB_SLEEP_MS);
      } else {
        clearSleepTimer();
        const p = session.agents.find((a) => a.id === pid);
        if (p?.presence === "dormant" || p?.presence === "proxy") {
          wakeSession(sid, pid).then((j) => {
            if (j.session) applySession(j.session);
            if (j.briefing) setBriefing(j.briefing);
          }).catch(() => {});
        }
      }
    };
    const onUnload = () => {
      sleepSessionKeepalive(sid, "unload", pid);
    };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("pagehide", onUnload);
    return () => {
      clearInterval(iv);
      clearSleepTimer();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("pagehide", onUnload);
    };
  }, [sid, session?.id, session?.player_id, applySession, session]);

  useEffect(() => {
    if (pages.length === 0) return;
    playTurn();
    const latest = pages[pages.length - 1];
    const narr = latest?.beats?.find((b) => b.kind === "narration");
    const speech = latest?.beats?.filter((b) => b.kind === "speech") || [];
    const parts: string[] = [];
    if (narr?.content) parts.push(narr.content);
    if (readSpeech) {
      for (const b of speech) {
        if (b.content) parts.push(b.speaker ? `${b.speaker}：${b.content}` : b.content);
      }
    }
    if (parts.length) speak(parts.join("。"));
    else stop();
  }, [pages.length, playTurn, speak, stop, readSpeech]);

  // Keyboard shortcuts (v1.4 UI-003..006)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "Escape") {
        if (overlay) { setOverlay(null); return; }
        setSystemOpen((o) => !o);
        return;
      }
      if (systemOpen) return;
      if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        setOverlay((o) => toggleOverlay(o, "map"));
      } else if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        setOverlay((o) => toggleOverlay(o, "journal"));
      } else if (e.key === "c" || e.key === "C") {
        e.preventDefault();
        setOverlay((o) => toggleOverlay(o, "character"));
      } else if (e.key === "Tab") {
        e.preventDefault();
        setOverlay((o) => toggleOverlay(o, "world"));
      } else if (e.key === "v" || e.key === "V") {
        setCameraMode((m) => {
          const next = m === "third" ? "first" : "third";
          savePlaySettings({ cameraMode: next });
          return next;
        });
      } else if ((e.key === "f" || e.key === "F") && nearbyNpcRef.current) {
        e.preventDefault();
        talkNearbyNpcRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [overlay, systemOpen]);

  useEffect(() => {
    const onNpc = () => setOverlay("character");
    window.addEventListener("civsim:npc-talk", onNpc);
    return () => window.removeEventListener("civsim:npc-talk", onNpc);
  }, []);

  const applyStepResult = useCallback((
    page: Page, newStats?: WorldStats, next?: Session,
  ) => {
    if (next) {
      applySession(next);
      setPages(next.pages?.length ? next.pages : (ps) => [...ps, page]);
    } else {
      setPages((ps) => [...ps, page]);
    }
    if (newStats) setStats(newStats);
    setTensionCurve((c) =>
      page.tension !== undefined ? [...c, page.tension].slice(-32) : c,
    );
  }, [applySession]);

  const submit = useCallback(async (text: string | null) => {
    if (loading || isOffline) return;
    const trimmed = typeof text === "string" ? text.trim() : text;
    if (trimmed === "") return;
    setLoading(true);
    setActionError(null);
    setDialoguePinned(true);
    try {
      const pid = getBoundPlayerId(sid) || session?.player_id;
      const { page, stats: newStats, session: next } = await stepSession(sid, trimmed, pid);
      applyStepResult(page, newStats, next);
      if (trimmed !== null) setInput("");
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "行动失败");
    } finally {
      setLoading(false);
    }
  }, [sid, loading, isOffline, applyStepResult, session?.player_id]);

  const talkNearbyNpc = useCallback(() => {
    const npc = nearbyNpcRef.current;
    if (!npc) return;
    window.dispatchEvent(new CustomEvent("civsim:npc-talk", { detail: { sid, npcId: npc.id } }));
    submit(`与${npc.name}交谈`);
  }, [sid, submit]);
  talkNearbyNpcRef.current = talkNearbyNpc;

  const onUseSkill = useCallback(async (skillId: string) => {
    if (loading || isOffline) return;
    setLoading(true);
    setActionError(null);
    try {
      const pid = getBoundPlayerId(sid) || session?.player_id;
      const { page, stats: newStats, session: next } = await useSkill(sid, skillId, pid || undefined);
      applyStepResult(page, newStats, next);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "技能失败");
    } finally {
      setLoading(false);
    }
  }, [sid, loading, isOffline, applyStepResult, session?.player_id]);

  const onAdvance = useCallback(() => {
    if (loading || isOffline) return;
    submit(WALK_PROMPTS[walkRng.current++ % WALK_PROMPTS.length]);
  }, [submit, loading, isOffline]);

  const onSleep = useCallback(async () => {
    const pid = getBoundPlayerId(sid) || session?.player_id;
    const j = await sleepSession(sid, "manual", pid);
    if (j.session) applySession(j.session);
  }, [sid, applySession, session?.player_id]);

  const onWake = useCallback(async () => {
    setLoading(true);
    try {
      const pid = getBoundPlayerId(sid) || session?.player_id;
      const j = await wakeSession(sid, pid);
      if (j.session) applySession(j.session);
      if (j.briefing) setBriefing(j.briefing);
    } finally {
      setLoading(false);
    }
  }, [sid, applySession, session?.player_id]);

  const onInvite = useCallback(async () => {
    const url = inviteUrl(sid);
    try {
      await navigator.clipboard.writeText(url);
      setActionError(null);
      setSystemOpen(false);
      alert(`邀请链接已复制：\n${url}`);
    } catch {
      prompt("复制邀请链接", url);
    }
  }, [sid]);

  const onExit = useCallback(() => {
    const pid = getBoundPlayerId(sid) || session?.player_id;
    sleepSessionKeepalive(sid, "exit", pid);
    sessionStorage.removeItem(`sess_${sid}`);
    clearBoundPlayerId(sid);
    router.push("/");
  }, [sid, router, session?.player_id]);

  if ((loadError || kickedOut) && !session) {
    return (
      <main className="fixed inset-0 flex flex-col items-center justify-center bg-black gap-4 px-6 text-center">
        <p className="text-rose-300/95 text-sm max-w-md leading-relaxed">
          {kickedOut ? "你已被房主移出此世界" : loadError}
        </p>
        <div className="flex gap-3 text-sm">
          <button
            type="button"
            onClick={() => router.push("/worlds")}
            className="px-3 py-1.5 rounded border border-stone-600 hover:border-amber-400/60"
          >
            我的世界
          </button>
          <button
            type="button"
            onClick={() => router.push("/simulator")}
            className="px-3 py-1.5 rounded bg-amber-500/90 text-stone-900 font-medium"
          >
            创建新世界
          </button>
        </div>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="fixed inset-0 flex items-center justify-center bg-black opacity-60">
        正在召唤你的世界…
      </main>
    );
  }

  const lastPage = pages[pages.length - 1];
  const storyChoices = normalizeChoices(lastPage?.choices as unknown[] | undefined);
  const sceneLoc = lastPage?.scene?.location_name || session.world?.locations?.[0]?.name || "未知之地";
  const sceneLocId = lastPage?.scene?.location_id || session.world?.locations?.[0]?.id || null;
  const hasChoices = storyChoices.length > 0;
  const showDialogue = dialoguePinned || hasChoices || isOffline || Boolean(input.trim()) || loading;

  const playMode = derivePlayMode({
    sessionLoaded: true,
    hasBriefing: Boolean(briefing),
    wsReconnecting: wsConn.reconnecting,
    overlay: overlayFromKey(overlay),
    systemOpen,
    inDialogue: showDialogue,
    isOffline,
  });

  return (
    <main className="fixed inset-0 overflow-hidden bg-black text-stone-100">
      {briefing && (
        <WakeBriefingModal briefing={briefing} onClose={() => setBriefing(null)} />
      )}

      <div className="absolute inset-0">
        <World3D
          genre={session.world.genre}
          worldLocations={session.world.locations || []}
          agents={session.agents}
          playerId={session.player_id}
          fullscreen
          height={typeof window !== "undefined" ? window.innerHeight : 800}
          cameraMode={cameraMode}
          onCameraModeChange={(m) => {
            setCameraMode(m);
            savePlaySettings({ cameraMode: m });
          }}
          dormant={isOffline}
          hour={typeof session.world.clock?.hour === "number" ? session.world.clock.hour : 10}
          explorationEnabled={explorationEnabled}
          presentation={presentationRef.current}
          onMove={handleMove}
          onNearbyNpc={onNearbyNpc}
          characterLod={characterLod}
        />
      </div>

      <ScenePlate
        enabled={sceneArtOn && showDialogue}
        genre={session.world.genre}
        locationName={sceneLoc}
        summary={lastPage?.scene?.summary || ""}
        hour={typeof session.world.clock?.hour === "number" ? session.world.clock.hour : 12}
        tension={typeof lastPage?.tension === "number" ? lastPage.tension : 0.3}
        reducedMotion={reducedMotion}
      />

      <PlayHud
        session={session}
        player={player}
        isOffline={isOffline}
        isProxy={isProxy}
        isDormant={isDormant}
        degraded={wsConn.degraded}
        reconnecting={wsConn.reconnecting}
        reconnectFailed={wsConn.reconnectFailed}
        reconnectAttempt={wsConn.attempt}
        reconnectError={wsConn.lastError}
        onRetryReconnect={wsConn.retry}
        serviceError={actionError}
        onDismissServiceError={() => setActionError(null)}
        onWake={onWake}
        onSleep={onSleep}
        onInvite={onInvite}
        onRoster={() => { setRosterError(null); setRosterOpen(true); }}
        onExit={() => setSystemOpen(true)}
        onOpenOverlay={(k) => setOverlay((o) => toggleOverlay(o, k))}
      />

      <RoomRosterPanel
        open={rosterOpen}
        onClose={() => setRosterOpen(false)}
        session={session}
        isHost={isHost}
        busyId={rosterBusy}
        error={rosterError}
        onKick={onKick}
        onTransfer={onTransfer}
      />

      {!explorationEnabled && !overlay && !isOffline && (
        <SceneNpcBar
          sid={sid}
          agents={session.agents}
          playerId={session.player_id}
          currentLocationId={sceneLocId}
          currentLocationName={sceneLoc}
          genre={session.world.genre}
        />
      )}

      {explorationEnabled && !overlay && !isOffline && (
        <ProximityNpcPrompt npc={nearbyNpc} onTalk={talkNearbyNpc} />
      )}

      <PlayDialogueDock
        visible={(playMode === "DIALOGUE" || (playMode === "EXPLORE" && showDialogue)) && !overlay && !systemOpen}
        isOffline={isOffline}
        isProxy={isProxy}
        player={player}
        storyChoices={storyChoices}
        loading={loading}
        input={input}
        actionError={actionError}
        onPick={(a) => submit(a)}
        onInput={setInput}
        onAdvance={onAdvance}
        onSubmit={() => submit(input)}
        onWake={onWake}
      />

      {overlay && (
        <PlayOverlay
          kind={overlay}
          onClose={() => setOverlay(null)}
          session={session}
          stats={stats}
          pages={pages}
          tensionCurve={tensionCurve}
          sid={sid}
          player={player}
          sceneLocId={sceneLocId}
          sceneLoc={sceneLoc}
          loading={loading}
          isOffline={isOffline}
          skills={player?.skills}
          onUseSkill={onUseSkill}
          relationsOpen={relationsOpen}
          onRelationsToggle={() => setRelationsOpen((v) => !v)}
        />
      )}

      <PlaySystemMenu
        open={systemOpen}
        onClose={() => setSystemOpen(false)}
        ttsOn={ttsOn}
        sfxOn={sfxOn}
        bgmOn={bgmOn}
        sceneArtOn={sceneArtOn}
        ttsRate={ttsRate}
        ttsReadSpeech={ttsReadSpeech}
        quality={quality}
        reducedMotion={reducedMotion}
        onTts={(v) => { setTtsOn(v); savePlaySettings({ tts: v }); if (!v) stop(); }}
        onSfx={(v) => { setSfxOn(v); savePlaySettings({ sfx: v }); }}
        onBgm={(v) => { setBgmOn(v); savePlaySettings({ bgm: v }); }}
        onSceneArt={(v) => { setSceneArtOn(v); savePlaySettings({ sceneArt: v }); }}
        onTtsRate={(v) => { setTtsRate(v); savePlaySettings({ ttsRate: v }); }}
        onTtsReadSpeech={(v) => { setTtsReadSpeech(v); savePlaySettings({ ttsReadSpeech: v }); }}
        onQuality={(q) => { setQuality(q); savePlaySettings({ quality: q }); }}
        onReducedMotion={(v) => { setReducedMotion(v); savePlaySettings({ reducedMotion: v }); }}
        onExit={onExit}
      />

      {IS_DEV && (
        <div className="absolute bottom-2 right-2 z-50 max-w-xs opacity-90">
          <InjectPanel sid={sid} session={session} onUpdate={(s) => applySession(s)} />
        </div>
      )}
    </main>
  );
}
