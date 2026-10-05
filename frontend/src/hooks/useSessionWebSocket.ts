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
};

export type SessionConnection = {
  connected: boolean;
  degraded: boolean;
  reconnecting: boolean;
  lastError: string | null;
  send: (msg: Record<string, unknown>) => void;
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
};

function wsUrl(sid: string, playerId?: string | null): string {
  if (typeof window === "undefined") return "";
  const q = playerId ? `?player_id=${encodeURIComponent(playerId)}` : "";
  const env = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (env) {
    const u = new URL(env);
    const proto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${u.host}/ws/sessions/${sid}${q}`;
  }
  if (window.location.hostname === "localhost") {
    const port = window.location.port;
    if (port === "3002" || port === "3001" || port === "3003") {
      return `ws://localhost:8001/ws/sessions/${sid}${q}`;
    }
    if (port === "3000") return `ws://localhost:8000/ws/sessions/${sid}${q}`;
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
}: Options): SessionConnection {
  const [conn, setConn] = useState<Omit<SessionConnection, "send">>({
    connected: false,
    degraded: false,
    reconnecting: false,
    lastError: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef = useRef(0);
  const playerIdRef = useRef(playerId);
  playerIdRef.current = playerId;
  const handlersRef = useRef({
    onSession, onPage, onPresence, onAgentTransform, onAgentTransforms, onPlayerJoined,
  });
  handlersRef.current = {
    onSession, onPage, onPresence, onAgentTransform, onAgentTransforms, onPlayerJoined,
  };

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

  const clearRetry = useCallback(() => {
    if (retryRef.current) {
      clearTimeout(retryRef.current);
      retryRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled || !sid) return;

    let closed = false;

    function scheduleReconnect() {
      if (closed) return;
      const delay = Math.min(8000, 800 + attemptRef.current * 1200);
      attemptRef.current += 1;
      setConn((c) => ({ ...c, connected: false, degraded: true, reconnecting: true }));
      clearRetry();
      retryRef.current = setTimeout(connect, delay);
    }

    function connect() {
      if (closed) return;
      clearRetry();
      try {
        const ws = new WebSocket(wsUrl(sid, playerIdRef.current));
        wsRef.current = ws;

        ws.onopen = () => {
          attemptRef.current = 0;
          setConn({ connected: true, degraded: false, reconnecting: false, lastError: null });
          const pid = playerIdRef.current;
          if (pid) {
            ws.send(JSON.stringify({ type: "hello", player_id: pid }));
          } else {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        };

        ws.onmessage = (ev) => {
          let msg: WsPayload;
          try {
            msg = JSON.parse(ev.data);
          } catch {
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
          if (msg.session) {
            handlersRef.current.onSession(msg.session);
          }
        };

        ws.onerror = () => {
          setConn((c) => ({ ...c, lastError: "WebSocket 连接异常" }));
        };

        ws.onclose = () => {
          wsRef.current = null;
          if (!closed) scheduleReconnect();
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
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sid, enabled, clearRetry, playerId]);

  return { ...conn, send };
}
