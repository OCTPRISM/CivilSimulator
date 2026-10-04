"use client";

import { useEffect, useRef } from "react";

/** Minimal browser TTS hook — reads each new narration when enabled. */
export function useTTS(enabled: boolean) {
  const lastSaid = useRef<string>("");

  function speak(text: string) {
    if (!enabled || !text || typeof window === "undefined") return;
    if (text === lastSaid.current) return;
    lastSaid.current = text;
    try {
      const synth = window.speechSynthesis;
      if (!synth) return;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "zh-CN";
      u.rate = 0.95;
      u.pitch = 1.0;
      // pick a Chinese voice when available
      const voices = synth.getVoices();
      const zh = voices.find((v) => /zh|Chinese/i.test(v.lang || v.name));
      if (zh) u.voice = zh;
      synth.speak(u);
    } catch {
      /* no-op */
    }
  }

  function stop() {
    try { window.speechSynthesis?.cancel(); } catch {}
  }

  useEffect(() => {
    if (!enabled) stop();
  }, [enabled]);

  return { speak, stop };
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
      // brown-noise burst, exponential fade — sounds like paper.
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
    } catch {
      /* no-op */
    }
  }
  return { play };
}
