"use client";

import { useEffect, useState } from "react";

/** Coarse pointer and/or narrow viewport → mobile narrative shell (architecture §9.7). */
export function prefersMobileNarrative(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    const narrow = window.matchMedia("(max-width: 900px)").matches;
    // Prefer coarse; also treat phone-width fine pointers (some iPads report fine) as mobile.
    return coarse || (narrow && window.matchMedia("(hover: none)").matches);
  } catch {
    return false;
  }
}

/**
 * Resolves after mount to avoid SSR/desktop flash then flipping to mobile.
 * Until `ready`, callers should treat mode as undecided (prefer not mounting World3D).
 */
export function useMobileNarrative(): { mobile: boolean; ready: boolean } {
  const [mobile, setMobile] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const update = () => setMobile(prefersMobileNarrative());
    update();
    setReady(true);
    const mqCoarse = window.matchMedia("(pointer: coarse)");
    const mqNarrow = window.matchMedia("(max-width: 900px)");
    const mqHover = window.matchMedia("(hover: none)");
    const listen = (mq: MediaQueryList, fn: () => void) => {
      if (typeof mq.addEventListener === "function") mq.addEventListener("change", fn);
      else mq.addListener(fn);
    };
    const unlisten = (mq: MediaQueryList, fn: () => void) => {
      if (typeof mq.removeEventListener === "function") mq.removeEventListener("change", fn);
      else mq.removeListener(fn);
    };
    listen(mqCoarse, update);
    listen(mqNarrow, update);
    listen(mqHover, update);
    window.addEventListener("orientationchange", update);
    return () => {
      unlisten(mqCoarse, update);
      unlisten(mqNarrow, update);
      unlisten(mqHover, update);
      window.removeEventListener("orientationchange", update);
    };
  }, []);

  return { mobile, ready };
}
