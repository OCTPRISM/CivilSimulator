"use client";

/**
 * GameScene — side-scrolling parallax world.
 *
 * The player avatar stays roughly centred; pressing ←/→ (or buttons) increments
 * `position` (a virtual world-X). Each parallax layer scrolls at its own factor:
 *   sky / mountains  : slow (0.05 .. 0.15)
 *   mid-ground hills : 0.35
 *   trees / posts    : 0.7
 *   foreground grass : 1.0
 *
 * Layer visuals adapt to genre via colour palettes & glyph sets.
 */

import { useEffect, useRef, useState } from "react";

type Genre = "ancient" | "scifi" | "wuxia" | "xuanhuan" | "mystery" | string;

const PALETTES: Record<string, {
  sky: [string, string];
  mountains: string;
  hills: string;
  ground: string;
  trees: string[];
  glyph: string[];        // foreground prop emojis
  weather: string[];      // mid-air sprinkles
}> = {
  ancient:  { sky: ["#1f2230", "#3a3043"], mountains: "#2a2740",
              hills: "#3a3a52", ground: "#2a221a",
              trees: ["🌲","🍂","🏯"], glyph: ["⛩️","🏮","🪨"],
              weather: ["·","·"] },
  modern:   { sky: ["#1a2a3c", "#3a5878"], mountains: "#2a3a4c",
              hills: "#3d4a52", ground: "#2a2e32",
              trees: ["🏢","🌳","🚗"], glyph: ["🏬","🚏","☕"],
              weather: ["·","·"] },
  wuxia:    { sky: ["#2a2230", "#4a2f3a"], mountains: "#312033",
              hills: "#4d2c39", ground: "#2c1d1a",
              trees: ["🎋","🍃","🏮"], glyph: ["⚔️","🪷","🍶"],
              weather: ["花","·"] },
  xuanhuan: { sky: ["#1a1638", "#3d1d4d"], mountains: "#241846",
              hills: "#3a205a", ground: "#1a1430",
              trees: ["🌌","✨","🗿"], glyph: ["🐉","🔮","🌀"],
              weather: ["✦","·"] },
  scifi:    { sky: ["#0a1628", "#0f2a3d"], mountains: "#102338",
              hills: "#13344a", ground: "#0c1a26",
              trees: ["🛰️","📡","🌐"], glyph: ["🤖","🚀","💠"],
              weather: ["·","·"] },
  mystery:  { sky: ["#15171c", "#23202a"], mountains: "#1a1a22",
              hills: "#26232c", ground: "#16151a",
              trees: ["🕯️","🪦","🏚️"], glyph: ["🗝️","🪞","📜"],
              weather: ["·","·"] },
};

function paletteFor(genre: string) {
  return PALETTES[genre] || PALETTES.ancient;
}

export type GameSceneProps = {
  genre: Genre;
  locationName: string;
  playerName: string;
  /** Current scene narration (last beat) shown in a top banner. */
  caption?: string;
  /** Stats summaries printed as overhead text floating with parallax. */
  hud?: { politics: string; economy: string; livelihood: string; military: string };
  /** When player crosses this many world-units, trigger onAdvance. */
  advanceEvery?: number;
  onAdvance: () => void;       // fires when player has "walked" a step
  /** Disable input while a step is in flight. */
  busy?: boolean;
  /** NPCs present in this scene (rendered as nearby figures). */
  npcs?: { id: string; name: string; avatar: string }[];
};

export default function GameScene({
  genre, locationName, playerName, caption, hud,
  advanceEvery = 240, onAdvance, busy = false, npcs = [],
}: GameSceneProps) {
  const pal = paletteFor(genre);
  const [x, setX] = useState(0);                   // world position
  const [walking, setWalking] = useState<-1 | 0 | 1>(0);
  const [facing, setFacing] = useState<1 | -1>(1);
  const lastAdvanceX = useRef(0);
  const rafRef = useRef<number | null>(null);

  // keyboard input
  useEffect(() => {
    const dn = (e: KeyboardEvent) => {
      if (e.repeat) return;
      if (e.key === "ArrowRight" || e.key === "d") {
        setWalking(1); setFacing(1);
      } else if (e.key === "ArrowLeft" || e.key === "a") {
        setWalking(-1); setFacing(-1);
      } else if (e.key === " ") {
        e.preventDefault();
        if (!busy) onAdvance();
      }
    };
    const up = (e: KeyboardEvent) => {
      if (["ArrowRight", "ArrowLeft", "a", "d"].includes(e.key)) setWalking(0);
    };
    window.addEventListener("keydown", dn);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", dn);
      window.removeEventListener("keyup", up);
    };
  }, [busy, onAdvance]);

  // movement loop
  useEffect(() => {
    if (walking === 0) return;
    const step = () => {
      setX((p) => {
        const next = p + walking * 4;     // px/frame
        if (Math.abs(next - lastAdvanceX.current) >= advanceEvery && !busy) {
          lastAdvanceX.current = next;
          onAdvance();
        }
        return next;
      });
      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [walking, busy, advanceEvery, onAdvance]);

  // helpers to render repeating layers
  const layerRow = (
    items: string[], factor: number, baseTop: string, size: number, gap: number,
  ) => {
    const offset = -(x * factor) % (gap * items.length);
    const repeats = 14;
    const row: JSX.Element[] = [];
    for (let i = -2; i < repeats; i++) {
      const ch = items[((i % items.length) + items.length) % items.length];
      row.push(
        <span key={i}
              style={{ position: "absolute", left: i * gap + offset,
                       top: baseTop, fontSize: size, opacity: 0.95,
                       textShadow: "0 2px 8px rgba(0,0,0,0.5)" }}>
          {ch}
        </span>,
      );
    }
    return row;
  };

  return (
    <div className="relative w-full overflow-hidden rounded-xl border
                    border-stone-800 select-none"
         style={{ height: 360,
                  background: `linear-gradient(180deg, ${pal.sky[0]} 0%, ${pal.sky[1]} 60%, ${pal.ground} 100%)` }}>
      {/* far mountains */}
      <div className="absolute inset-x-0" style={{ bottom: 130, height: 110 }}>
        <svg viewBox="0 0 1200 200" preserveAspectRatio="none"
             className="w-full h-full"
             style={{ transform: `translateX(${-(x * 0.08) % 1200}px)` }}>
          <polygon points="0,200 120,90 240,140 360,60 540,150 720,80 900,160 1080,90 1200,150 1200,200"
                   fill={pal.mountains} opacity={0.85} />
        </svg>
      </div>
      {/* mid hills */}
      <div className="absolute inset-x-0" style={{ bottom: 80, height: 90 }}>
        <svg viewBox="0 0 1200 200" preserveAspectRatio="none"
             className="w-full h-full"
             style={{ transform: `translateX(${-(x * 0.25) % 1200}px)` }}>
          <polygon points="0,200 100,120 250,170 420,110 600,170 780,130 960,180 1100,140 1200,170 1200,200"
                   fill={pal.hills} />
        </svg>
      </div>

      {/* parallax HUD lines (very slow) */}
      {hud && (
        <div className="absolute inset-x-0 top-2 flex justify-center pointer-events-none">
          <div className="text-[11px] tracking-wide opacity-70 text-stone-300
                          flex gap-4 px-3 py-1 rounded-full
                          bg-black/30 backdrop-blur-sm">
            <span>政 {hud.politics}</span>
            <span>经 {hud.economy}</span>
            <span>民 {hud.livelihood}</span>
            <span>军 {hud.military}</span>
          </div>
        </div>
      )}

      {/* tree row */}
      <div className="absolute inset-x-0 pointer-events-none"
           style={{ bottom: 60, height: 80, color: "#fff" }}>
        {layerRow(pal.trees, 0.7, "0", 38, 110)}
      </div>

      {/* foreground glyphs (closer, faster) */}
      <div className="absolute inset-x-0 pointer-events-none"
           style={{ bottom: 14, height: 60, color: "#fff" }}>
        {layerRow(pal.glyph, 1.0, "0", 30, 160)}
      </div>

      {/* ground line */}
      <div className="absolute inset-x-0 bottom-0 h-2"
           style={{ background:
             `linear-gradient(90deg, transparent, ${pal.ground} 30%, ${pal.ground} 70%, transparent)` }}/>

      {/* player avatar (centred) */}
      <div className="absolute"
           style={{ left: "50%", bottom: 36,
                    transform: `translateX(-50%) scaleX(${facing})` }}>
        <div className="relative">
          <div className="text-5xl"
               style={{ filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.5))",
                        transform: walking !== 0
                          ? `translateY(${Math.sin(x * 0.08) * 2}px)`
                          : undefined }}>
            🚶
          </div>
          <div className="absolute -top-7 left-1/2 -translate-x-1/2
                          text-xs whitespace-nowrap text-amber-200
                          bg-black/40 px-2 py-0.5 rounded">
            {playerName}
          </div>
        </div>
      </div>

      {/* present NPCs (positioned around the player at fixed scene anchors) */}
      {npcs.slice(0, 5).map((n, i) => {
        const slots = [
          { lx: "22%", b: 40 }, { lx: "75%", b: 44 },
          { lx: "38%", b: 38 }, { lx: "62%", b: 36 },
          { lx: "12%", b: 42 },
        ];
        const s = slots[i % slots.length];
        const drift = (-(x * 0.5)) % 60;
        return (
          <div key={n.id} className="absolute pointer-events-none"
               style={{ left: s.lx, bottom: s.b,
                        transform: `translateX(${drift}px)` }}>
            <div className="relative flex flex-col items-center">
              <div className="text-3xl"
                   style={{ filter: "drop-shadow(0 3px 5px rgba(0,0,0,0.55))" }}>
                {n.avatar || "👤"}
              </div>
              <div className="text-[10px] whitespace-nowrap text-stone-200
                              bg-black/55 px-1.5 py-0.5 rounded mt-0.5">
                {n.name}
              </div>
            </div>
          </div>
        );
      })}

      {/* location label */}
      <div className="absolute top-2 left-3 text-xs text-stone-300/80
                      bg-black/30 backdrop-blur-sm px-2 py-1 rounded">
        📍 {locationName} · 行至 {Math.floor(Math.abs(x) / 4)} 步
      </div>

      {/* caption banner */}
      {caption && (
        <div className="absolute inset-x-0 bottom-2 px-4 pointer-events-none">
          <div className="mx-auto max-w-2xl text-center text-[13px]
                          text-stone-200/90 bg-black/45 backdrop-blur-sm
                          px-3 py-1.5 rounded line-clamp-2">
            {caption}
          </div>
        </div>
      )}

      {/* on-screen controls */}
      <div className="absolute right-3 bottom-3 flex gap-2">
        <CtrlBtn label="◀"
                 onDown={() => { setWalking(-1); setFacing(-1); }}
                 onUp={() => setWalking(0)} />
        <CtrlBtn label="▶"
                 onDown={() => { setWalking(1); setFacing(1); }}
                 onUp={() => setWalking(0)} />
        <button
          onClick={() => !busy && onAdvance()}
          disabled={busy}
          className="px-3 py-2 rounded-md bg-amber-500/90 text-stone-900
                     text-sm font-semibold disabled:opacity-40
                     hover:bg-amber-400">
          {busy ? "演绎中…" : "继续 ⏎"}
        </button>
      </div>

      {/* keyboard hint */}
      <div className="absolute left-3 bottom-3 text-[10px] opacity-50">
        ← → 移动 · 空格 继续
      </div>
    </div>
  );
}

function CtrlBtn(
  { label, onDown, onUp }:
  { label: string; onDown: () => void; onUp: () => void },
) {
  return (
    <button
      onMouseDown={onDown} onMouseUp={onUp} onMouseLeave={onUp}
      onTouchStart={(e) => { e.preventDefault(); onDown(); }}
      onTouchEnd={(e) => { e.preventDefault(); onUp(); }}
      className="w-10 h-10 rounded-md bg-stone-800/80 border border-stone-600
                 text-stone-100 hover:bg-stone-700 active:bg-amber-500/30">
      {label}
    </button>
  );
}
