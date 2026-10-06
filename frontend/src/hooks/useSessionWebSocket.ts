"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Agent, Page, Session, WorldStats } from "@/lib/api";

export type AgentTransform = {
  agent_id: string;
  world_x: number;
  world_z: number;
  behavior?: string;
  tick?: number;
};

type WsPayload = {
  type: string;
  session?: Session;
  page?: Page;
  stats?: WorldStats;
  player_id?: string;
  presence?: string;
  rationale?: string;
  briefing?: unknown;
  transform?: AgentTransform;
  transforms?: AgentTransform[];
  agent?: Agent;
  message?: string;
  reason?: string;
};

export type SessionConnection = {
  connected: boolean;
  degraded: boolean;
  reconnecting: boolean;
  /** True after max auto-retries exhausted until manual retry. */
  reconnectFailed: boolean;
  attempt: number;
  lastError: string | null;
  send: (msg: Record<string, unknown>) => void;
  retry: () => void;
};

type Options = {
  sid: string;
  playerId?: string | null;
  enabled: boolean;
  onSession: (s: Session) => void;
  onPage?: (page: Page, stats?: WorldStats) => void;
  onPresence?: (playerId: string, presence: string, rationale?: string) => void;
  onAgentTransform?: (t: AgentTransform) => void;
  onAgentTransforms?: (ts: AgentTransform[]) => void;
  onPlayerJoined?: (playerId: string, agent?: Agent, session?: Session) => void;
  onKicked?: (playerId?: string) => void;
};

/** MP-3: finite auto-reconnect budget before requiring manual retry. */
const MAX_AUTO_ATTEMPTS = 8;

/** Auth / membership failures must not burn the reconnect budget. */
const FATAL_WS_RE = /成员|未登录|登录已过期|移出|无权|forbidden|unauthorized/i;

function wsUrl(sid: string, playerId?: string | null): string {
  if (typeof window === "undefined") return "";
  const params = new URLSearchParams();
  if (playerId) params.set("player_id", playerId);
  // R0-2: never put bearer tokens in the URL (proxy/access logs). Auth via hello frame.
  const q = params.toString() ? `?${params.toString()}` : "";

  // Prefer explicit public backend URL (must match BACKEND_URL / uvicorn).
  const env = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (env) {
    const u = new URL(env);
    const proto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${u.host}/ws/sessions/${sid}${q}`;
  }
  // Local default: frontend :3000 → backend :8000 (R0-6).
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    return `ws://127.0.0.1:8000/ws/sessions/${sid}${q}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/sessions/${sid}${q}`;
}

export function useSessionWebSocket({
  sid,
  playerId,
  enabled,
  onSession,
  onPage,
  onPresence,
  onAgentTransform,
  onAgentTransforms,
  onPlayerJoined,
  onKicked,
}: Options): SessionConnection {
  const [conn, setConn] = useState<Omit<SessionConnection, "send" | "retry">>({
    connected: false,
    degraded: false,
    reconnecting: false,
    reconnectFailed: false,
    attempt: 0,
    lastError: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attemptRef = useRef(0);
  const stopReconnectRef = useRef(false);
  const kickedHandledRef = useRef(false);
  const fatalErrorRef = useRef<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);
  const playerIdRef = useRef(playerId);
  playerIdRef.current = playerId;
  const handlersRef = useRef({
    onSession, onPage, onPresence, onAgentTransform, onAgentTransforms, onPlayerJoined, onKicked,
  });
  handlersRef.current = {
    onSession, onPage, onPresence, onAgentTransform, onAgentTransforms, onPlayerJoined, onKicked,
  };

  const clearRetry = useCallback(() => {
    if (retryRef.current) {
      clearTimeout(retryRef.current);
      retryRef.current = null;
    }
  }, []);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const markKicked = useCallback((pid?: string) => {
    if (kickedHandledRef.current) return;
    kickedHandledRef.current = true;
    stopReconnectRef.current = true;
    clearRetry();
    clearHeartbeat();
    handlersRef.current.onKicked?.(pid);
    setConn({
      connected: false,
      degraded: true,
      reconnecting: false,
      reconnectFailed: false,
      attempt: 0,
      lastError: "你已被房主移出此世界",
    });
  }, [clearRetry, clearHeartbeat]);

  const send = useCallback((msg: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      const pid = playerIdRef.current;
      const payload = pid && msg.player_id === undefined
        ? { ...msg, player_id: pid }
        : msg;
      ws.send(JSON.stringify(payload));
    }
  }, []);

  const retry = useCallback(() => {
    if (kickedHandledRef.current) return;
    stopReconnectRef.current = false;
    fatalErrorRef.current = null;
    attemptRef.current = 0;
    setConn((c) => ({
      ...c,
      reconnectFailed: false,
      reconnecting: true,
      degraded: true,
      attempt: 0,
      lastError: "正在重新连接…",
    }));
    setRetryNonce((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!enabled || !sid) return;

    let closed = false;
    // Do not clear kickedHandled / stopReconnect here — only manual retry may resume.
    if (!kickedHandledRef.current) {
      stopReconnectRef.current = false;
      fatalErrorRef.current = null;
    }

    function scheduleReconnect() {
      if (closed || stopReconnectRef.current || kickedHandledRef.current) return;
      if (fatalErrorRef.current) {
        setConn({
          connected: false,
          degraded: true,
          reconnecting: false,
          reconnectFailed: false,
          attempt: attemptRef.current,
          lastError: fatalErrorRef.current,
        });
        return;
      }
      if (attemptRef.current >= MAX_AUTO_ATTEMPTS) {
        setConn({
          connected: false,
          degraded: true,
          reconnecting: false,
          reconnectFailed: true,
          attempt: attemptRef.current,
          lastError: `连接中断（已重试 ${MAX_AUTO_ATTEMPTS} 次），可手动重连或刷新`,
        });
        return;
      }
      const n = attemptRef.current + 1;
      attemptRef.current = n;
      const delay = Math.min(8000, 800 + (n - 1) * 1200);
      setConn({
        connected: false,
        degraded: true,
        reconnecting: true,
        reconnectFailed: false,
        attempt: n,
        lastError: `连接断开，正在重连（${n}/${MAX_AUTO_ATTEMPTS}）…`,
      });
      clearRetry();
      retryRef.current = setTimeout(connect, delay);
    }

    function connect() {
      if (closed || stopReconnectRef.current || kickedHandledRef.current) return;
      clearRetry();
      clearHeartbeat();
      try {
        const ws = new WebSocket(wsUrl(sid, playerIdRef.current));
        wsRef.current = ws;

        ws.onopen = () => {
          attemptRef.current = 0;
          setConn({
            connected: true,
            degraded: false,
            reconnecting: false,
            reconnectFailed: false,
            attempt: 0,
            lastError: null,
          });
          const pid = playerIdRef.current;
          const token = localStorage.getItem("civsim_token");
          // Auth must be first frame when query omits token (R0-2).
          if (token) {
            ws.send(JSON.stringify({
              type: "hello",
              token,
              ...(pid ? { player_id: pid } : {}),
            }));
          } else {
            // Without a token the server will reject; stop burning retries.
            fatalErrorRef.current = "未登录或登录已过期";
            stopReconnectRef.current = true;
            ws.close();
            return;
          }
          clearHeartbeat();
          heartbeatRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              const hbPid = playerIdRef.current;
              ws.send(JSON.stringify({
                type: "heartbeat",
                ...(hbPid ? { player_id: hbPid } : {}),
              }));
            }
          }, 20_000);
        };

        ws.onmessage = (ev) => {
          let msg: WsPayload;
          try {
            msg = JSON.parse(ev.data);
          } catch {
            return;
          }
          if (msg.type === "ping") {
            try { ws.send(JSON.stringify({ type: "pong" })); } catch { /* ignore */ }
            return;
          }
          if (msg.type === "pong") return;
          if (msg.type === "error" && msg.message) {
            const text = String(msg.message);
            if (FATAL_WS_RE.test(text)) {
              fatalErrorRef.current = text;
              stopReconnectRef.current = true;
              clearRetry();
              // Membership loss while already in Play ≈ kicked / revoked.
              if (/成员|移出/.test(text)) {
                markKicked(playerIdRef.current || undefined);
                try { ws.close(); } catch { /* ignore */ }
                return;
              }
              setConn((c) => ({
                ...c,
                connected: false,
                degraded: true,
                reconnecting: false,
                reconnectFailed: false,
                lastError: text,
              }));
              return;
            }
            setConn((c) => ({ ...c, lastError: text || c.lastError }));
            return;
          }
          if (msg.type === "player_kicked") {
            const kickedId = msg.player_id;
            const selfId = playerIdRef.current;
            // Only the victim stops; others refresh roster via session.
            if (!kickedId || kickedId === selfId) {
              markKicked(kickedId || selfId || undefined);
              try { ws.close(); } catch { /* ignore */ }
              // Do NOT apply session for the victim — would resurrect Play state.
              return;
            }
            if (msg.session) handlersRef.current.onSession(msg.session);
            return;
          }
          if ((msg.type === "snapshot" || msg.type === "hello_ack") && msg.session) {
            handlersRef.current.onSession(msg.session);
            return;
          }
          if (msg.type === "page" && msg.page) {
            handlersRef.current.onPage?.(msg.page, msg.stats);
            return;
          }
          if (msg.type === "presence" && msg.player_id && msg.presence) {
            handlersRef.current.onPresence?.(msg.player_id, msg.presence, msg.rationale);
            return;
          }
          if (msg.type === "agent_transform" && msg.transform) {
            handlersRef.current.onAgentTransform?.(msg.transform);
            return;
          }
          if (msg.type === "agent_transforms" && msg.transforms?.length) {
            handlersRef.current.onAgentTransforms?.(msg.transforms);
            return;
          }
          if (msg.type === "player_joined" && msg.player_id) {
            handlersRef.current.onPlayerJoined?.(msg.player_id, msg.agent, msg.session);
            if (msg.session) handlersRef.current.onSession(msg.session);
            return;
          }
          if (msg.type === "host_transferred" && msg.session) {
            handlersRef.current.onSession(msg.session);
            return;
          }
          if (msg.session) {
            handlersRef.current.onSession(msg.session);
          }
        };

        ws.onerror = () => {
          setConn((c) => ({ ...c, lastError: c.lastError || "WebSocket 连接异常" }));
        };

        ws.onclose = (ev) => {
          wsRef.current = null;
          clearHeartbeat();
          if (closed || stopReconnectRef.current || kickedHandledRef.current) return;
          // 4001 = kicked close from server
          if (ev.code === 4001) {
            markKicked(playerIdRef.current || undefined);
            return;
          }
          if (fatalErrorRef.current) {
            setConn({
              connected: false,
              degraded: true,
              reconnecting: false,
              reconnectFailed: false,
              attempt: attemptRef.current,
              lastError: fatalErrorRef.current,
            });
            return;
          }
          scheduleReconnect();
        };
      } catch (e) {
        setConn((c) => ({
          ...c,
          connected: false,
          degraded: true,
          reconnecting: true,
          lastError: e instanceof Error ? e.message : "连接失败",
        }));
        scheduleReconnect();
      }
    }

    connect();

    return () => {
      closed = true;
      clearRetry();
      clearHeartbeat();
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sid, enabled, clearRetry, clearHeartbeat, playerId, retryNonce, markKicked]);

  return { ...conn, send, retry };
}
