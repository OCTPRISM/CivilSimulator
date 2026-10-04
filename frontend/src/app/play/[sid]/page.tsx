"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  sendHeartbeat, sleepSession, stepSession, useSkill, wakeSession,
  type Page, type Session, type WakeBriefing, type WorldStats, type Agent,
} from "@/lib/api";
import { useTTS, usePageTurnSound } from "@/lib/audio";
import { loadPlaySettings, savePlaySettings } from "@/lib/playSettings";
import { derivePlayMode, overlayFromKey, toggleOverlay, type OverlayKey } from "@/lib/playState";
import { useSessionWebSocket } from "@/hooks/useSessionWebSocket";
import World3D from "@/components/World3D";
import { WorldPresentationStore } from "@/lib/worldPresentationStore";
import WakeBriefingModal from "@/components/WakeBriefingModal";
import InjectPanel from "@/components/InjectPanel";
import { normalizeChoices } from "@/components/ChoicePanel";
import {
  PlayHud, PlayOverlay, PlaySystemMenu, SceneNpcBar, PlayDialogueDock, ProximityNpcPrompt,
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
  const initialSettings = loadPlaySettings();

  const [session, setSession] = useState<Session | null>(null);
  const [pages, setPages] = useState<Page[]>([]);
  const [stats, setStats] = useState<WorldStats | undefined>();
  const [tensionCurve, setTensionCurve] = useState<number[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<OverlayKey | null>(null);
  const [systemOpen, setSystemOpen] = useState(false);
  const [relationsOpen, setRelationsOpen] = useState(false);
  const [ttsOn, setTtsOn] = useState(initialSettings.tts);
  const [sfxOn, setSfxOn] = useState(initialSettings.sfx);
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

  const { speak, stop } = useTTS(ttsOn);
  const { play: playTurn } = usePageTurnSound(sfxOn);

  const applySession = useCallback((s: Session) => {
    setSession(s);
    presentationRef.current.seedFromAgents(s.agents);
    if (s.pages?.length) setPages(s.pages);
    if (s.stats) setStats(s.stats);
    if (s.tension_curve) setTensionCurve(s.tension_curve);
    sessionStorage.setItem(`sess_${sid}`, JSON.stringify(s));
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
      const next = { ...prev, agents };
      sessionStorage.setItem(`sess_${sid}`, JSON.stringify(next));
      return next;
    });
  }, [sid]);

  const wsConn = useSessionWebSocket({
    sid,
    enabled: Boolean(session),
    onSession: applySession,
    onPage: onWsPage,
    onPresence: onWsPresence,
    onAgentTransform: onWsTransform,
    onAgentTransforms: onWsTransforms,
  });

  const handleMove = useCallback((world_x: number, world_z: number) => {
    wsConn.send({ type: "move", world_x, world_z });
  }, [wsConn.send]);

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
        setSession(s);
        setPages(s.pages || []);
        setStats(s.stats);
        setTensionCurve(s.tension_curve || []);
      } catch { /* ignore */ }
    }
    fetch(`/api/sessions/${sid}`)
      .then((r) => r.json())
      .then((j) => { if (j.session) applySession(j.session); })
      .catch(() => {});
  }, [sid, applySession]);

  // HTTP fallback poll only when WS degraded (v1.4 NET-010)
  useEffect(() => {
    if (!session || wsConn.connected) return;
    const poll = () => {
      fetch(`/api/sessions/${sid}`)
        .then((r) => r.json())
        .then((j) => { if (j.session) applySession(j.session); })
        .catch(() => {});
    };
    poll();
    const iv = setInterval(poll, 4000);
    return () => clearInterval(iv);
  }, [sid, applySession, session, wsConn.connected]);

  useEffect(() => {
    if (!session) return;
    const beat = () => {
      const p = session.agents.find((a) => a.id === session.player_id);
      if (p?.presence === "dormant" || p?.presence === "proxy") return;
      sendHeartbeat(sid).catch(() => {});
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
          sleepSession(sid, "tab_hidden").then((j) => {
            if (j.session) applySession(j.session);
          }).catch(() => {});
        }, TAB_SLEEP_MS);
      } else {
        clearSleepTimer();
        const p = session.agents.find((a) => a.id === session.player_id);
        if (p?.presence === "dormant" || p?.presence === "proxy") {
          wakeSession(sid).then((j) => {
            if (j.session) applySession(j.session);
            if (j.briefing) setBriefing(j.briefing);
          }).catch(() => {});
        }
      }
    };
    const onUnload = () => {
      try {
        navigator.sendBeacon?.(
          `/api/sessions/${sid}/sleep`,
          new Blob([JSON.stringify({ reason: "unload" })], { type: "application/json" }),
        );
      } catch { /* ignore */ }
    };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("pagehide", onUnload);
    return () => {
      clearInterval(iv);
      clearSleepTimer();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("pagehide", onUnload);
    };
  }, [sid, session?.id, applySession, session]);

  useEffect(() => {
    if (pages.length === 0) return;
    playTurn();
    const latest = pages[pages.length - 1];
    const narr = latest?.beats?.find((b) => b.kind === "narration");
    if (narr) speak(narr.content);
  }, [pages.length, playTurn, speak]);

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
      const { page, stats: newStats, session: next } = await stepSession(sid, trimmed);
      applyStepResult(page, newStats, next);
      if (trimmed !== null) setInput("");
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "行动失败");
    } finally {
      setLoading(false);
    }
  }, [sid, loading, isOffline, applyStepResult]);

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
      const { page, stats: newStats, session: next } = await useSkill(sid, skillId);
      applyStepResult(page, newStats, next);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "技能失败");
    } finally {
      setLoading(false);
    }
  }, [sid, loading, isOffline, applyStepResult]);

  const onAdvance = useCallback(() => {
    if (loading || isOffline) return;
    submit(WALK_PROMPTS[walkRng.current++ % WALK_PROMPTS.length]);
  }, [submit, loading, isOffline]);

  const onSleep = useCallback(async () => {
    const j = await sleepSession(sid, "manual");
    if (j.session) applySession(j.session);
  }, [sid, applySession]);

  const onWake = useCallback(async () => {
    setLoading(true);
    try {
      const j = await wakeSession(sid);
      if (j.session) applySession(j.session);
      if (j.briefing) setBriefing(j.briefing);
    } finally {
      setLoading(false);
    }
  }, [sid, applySession]);

  const onExit = useCallback(() => {
    try {
      navigator.sendBeacon?.(
        `/api/sessions/${sid}/sleep`,
        new Blob([JSON.stringify({ reason: "exit" })], { type: "application/json" }),
      );
    } catch { /* ignore */ }
    sessionStorage.removeItem(`sess_${sid}`);
    router.push("/");
  }, [sid, router]);

  if (!session) {
    return (
      <main className="fixed inset-0 flex items-center justify-center bg-black opacity-60">
        正在召唤你的世界…
      </main>
    );
  }

  const lastPage = pages[pages.length - 1];
  const storyChoices = normalizeChoices(lastPage?.choices as unknown[] | undefined);
  const sceneLoc = lastPage?.scene.location_name || session.world?.locations?.[0]?.name || "未知之地";
  const sceneLocId = lastPage?.scene.location_id || session.world?.locations?.[0]?.id || null;
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

      <PlayHud
        session={session}
        player={player}
        isOffline={isOffline}
        isProxy={isProxy}
        isDormant={isDormant}
        degraded={wsConn.degraded}
        reconnecting={wsConn.reconnecting}
        onWake={onWake}
        onSleep={onSleep}
        onExit={() => setSystemOpen(true)}
        onOpenOverlay={(k) => setOverlay((o) => toggleOverlay(o, k))}
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
        quality={quality}
        reducedMotion={reducedMotion}
        onTts={(v) => { setTtsOn(v); savePlaySettings({ tts: v }); if (!v) stop(); }}
        onSfx={(v) => { setSfxOn(v); savePlaySettings({ sfx: v }); }}
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
