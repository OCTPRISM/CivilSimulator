"use client";

import { useCallback, useEffect, useRef } from "react";

export type TtsOptions = {
  rate?: number;
  /** When true, also read NPC speech beats (speaker lines). */
  readSpeech?: boolean;
};

/** Browser Speech Synthesis — cancels previous utterance on each speak. */
export function useTTS(enabled: boolean, opts: TtsOptions = {}) {
  const lastSaid = useRef<string>("");
  const speakingRef = useRef(false);
  const onSpeakingRef = useRef<((v: boolean) => void) | undefined>(undefined);

  const stop = useCallback(() => {
    try {
      window.speechSynthesis?.cancel();
    } catch { /* ignore */ }
    speakingRef.current = false;
    onSpeakingRef.current?.(false);
  }, []);

  const speak = useCallback((text: string) => {
    if (!enabled || !text || typeof window === "undefined") return;
    const trimmed = text.trim();
    if (!trimmed) return;
    if (trimmed === lastSaid.current) return;
    lastSaid.current = trimmed;
    try {
      const synth = window.speechSynthesis;
      if (!synth) return;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(trimmed);
      u.lang = "zh-CN";
      u.rate = Math.max(0.6, Math.min(1.4, opts.rate ?? 0.95));
      u.pitch = 1.0;
      const voices = synth.getVoices();
      const zh =
        voices.find((v) => /zh-CN|zh_CN/i.test(v.lang)) ||
        voices.find((v) => /zh|Chinese|中文/i.test(v.lang || v.name));
      if (zh) u.voice = zh;
      u.onstart = () => {
        speakingRef.current = true;
        onSpeakingRef.current?.(true);
      };
      u.onend = () => {
        speakingRef.current = false;
        onSpeakingRef.current?.(false);
      };
      u.onerror = () => {
        speakingRef.current = false;
        onSpeakingRef.current?.(false);
      };
      synth.speak(u);
    } catch { /* no-op */ }
  }, [enabled, opts.rate]);

  useEffect(() => {
    if (!enabled) stop();
  }, [enabled, stop]);

  const setSpeakingListener = useCallback((fn?: (v: boolean) => void) => {
    onSpeakingRef.current = fn;
  }, []);

  return { speak, stop, setSpeakingListener, readSpeech: Boolean(opts.readSpeech) };
}

/** Tiny synthesised "page turn" whoosh using WebAudio — no asset needed. */
export function usePageTurnSound(enabled: boolean) {
  const ctxRef = useRef<AudioContext | null>(null);

  function play() {
    if (!enabled || typeof window === "undefined") return;
    try {
      const Ctx =
        (window as any).AudioContext || (window as any).webkitAudioContext;
      if (!Ctx) return;
      const ctx: AudioContext = ctxRef.current ?? new Ctx();
      ctxRef.current = ctx;
      if (ctx.state === "suspended") void ctx.resume();
      const dur = 0.25;
      const sr = ctx.sampleRate;
      const buf = ctx.createBuffer(1, Math.floor(sr * dur), sr);
      const ch = buf.getChannelData(0);
      let last = 0;
      for (let i = 0; i < ch.length; i++) {
        const white = Math.random() * 2 - 1;
        last = (last + 0.04 * white) / 1.04;
        const env = Math.pow(1 - i / ch.length, 2.5);
        ch[i] = last * 6 * env;
      }
      const src = ctx.createBufferSource();
      src.buffer = buf;
      const filter = ctx.createBiquadFilter();
      filter.type = "bandpass";
      filter.frequency.value = 1800;
      filter.Q.value = 0.9;
      const gain = ctx.createGain();
      gain.gain.value = 0.35;
      src.connect(filter).connect(gain).connect(ctx.destination);
      src.start();
    } catch { /* no-op */ }
  }
  return { play };
}

type BgmProfile = {
  /** Base drone Hz */
  f1: number;
  f2: number;
  /** Soft noise color amount 0..1 */
  noise: number;
  /** Filter Hz */
  filter: number;
  /** Base gain */
  gain: number;
};

const BGM_BY_GENRE: Record<string, BgmProfile> = {
  ancient: { f1: 98, f2: 147, noise: 0.08, filter: 420, gain: 0.045 },
  wuxia: { f1: 110, f2: 165, noise: 0.05, filter: 520, gain: 0.04 },
  xianxia: { f1: 87, f2: 130.5, noise: 0.06, filter: 380, gain: 0.042 },
  scifi: { f1: 55, f2: 82.5, noise: 0.12, filter: 280, gain: 0.038 },
  mystery: { f1: 73, f2: 110, noise: 0.15, filter: 240, gain: 0.04 },
  default: { f1: 90, f2: 135, noise: 0.07, filter: 400, gain: 0.04 },
};

function profileFor(genre?: string | null): BgmProfile {
  const key = (genre || "default").toLowerCase();
  return BGM_BY_GENRE[key] || BGM_BY_GENRE.default;
}

/**
 * Procedural looping ambient BGM (WebAudio) — no binary assets required.
 * Duck volume while TTS is speaking.
 */
export function useBgm(enabled: boolean, genre?: string | null) {
  const ctxRef = useRef<AudioContext | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const nodesRef = useRef<{ stop: () => void } | null>(null);
  const duckedRef = useRef(false);
  const genreRef = useRef(genre);
  genreRef.current = genre;

  const teardown = useCallback(() => {
    try {
      nodesRef.current?.stop();
    } catch { /* ignore */ }
    nodesRef.current = null;
  }, []);

  const start = useCallback(async () => {
    if (typeof window === "undefined") return;
    const Ctx =
      (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!Ctx) return;
    const ctx: AudioContext = ctxRef.current ?? new Ctx();
    ctxRef.current = ctx;
    if (ctx.state === "suspended") await ctx.resume();

    teardown();
    const p = profileFor(genreRef.current);
    const master = ctx.createGain();
    master.gain.value = duckedRef.current ? p.gain * 0.15 : p.gain;
    master.connect(ctx.destination);
    masterRef.current = master;

    const mkOsc = (freq: number, type: OscillatorType, g: number) => {
      const osc = ctx.createOscillator();
      osc.type = type;
      osc.frequency.value = freq;
      const gain = ctx.createGain();
      gain.gain.value = g;
      const filter = ctx.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.value = p.filter;
      osc.connect(gain).connect(filter).connect(master);
      osc.start();
      return () => {
        try {
          osc.stop();
          osc.disconnect();
        } catch { /* ignore */ }
      };
    };

    const stops = [
      mkOsc(p.f1, "sine", 0.55),
      mkOsc(p.f2, "triangle", 0.28),
      mkOsc(p.f1 * 0.5, "sine", 0.22),
    ];

    // Soft looping noise bed
    const sr = ctx.sampleRate;
    const seconds = 4;
    const buf = ctx.createBuffer(1, sr * seconds, sr);
    const data = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < data.length; i++) {
      const white = Math.random() * 2 - 1;
      last = (last + 0.02 * white) / 1.02;
      data[i] = last * p.noise * 4;
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buf;
    noise.loop = true;
    const nGain = ctx.createGain();
    nGain.gain.value = 0.35;
    const nFilter = ctx.createBiquadFilter();
    nFilter.type = "lowpass";
    nFilter.frequency.value = p.filter * 0.7;
    noise.connect(nGain).connect(nFilter).connect(master);
    noise.start();
    stops.push(() => {
      try {
        noise.stop();
        noise.disconnect();
      } catch { /* ignore */ }
    });

    nodesRef.current = {
      stop: () => stops.forEach((fn) => fn()),
    };
  }, [teardown]);

  useEffect(() => {
    if (!enabled) {
      teardown();
      return;
    }
    void start();
    return () => teardown();
  }, [enabled, genre, start, teardown]);

  const setDucked = useCallback((ducked: boolean) => {
    duckedRef.current = ducked;
    const master = masterRef.current;
    const ctx = ctxRef.current;
    if (!master || !ctx) return;
    const p = profileFor(genreRef.current);
    const target = ducked ? p.gain * 0.12 : p.gain;
    try {
      master.gain.cancelScheduledValues(ctx.currentTime);
      master.gain.linearRampToValueAtTime(target, ctx.currentTime + 0.25);
    } catch {
      master.gain.value = target;
    }
  }, []);

  return { setDucked };
}
