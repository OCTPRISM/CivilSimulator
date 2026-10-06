"use client";

import { useEffect, useState } from "react";

const KEY = "civsim_onboarded";

const STEPS = [
  {
    title: "选文明，生成角色",
    body: "在「文明模拟器」挑选内建世界或自定义规则，确认形象后进入 3D 叙事。",
  },
  {
    title: "行动与对话",
    body: "WASD 移动，靠近 NPC 交谈；用选择支或底部自由输入推进下一幕。Esc 打开系统菜单（朗读 / BGM / 插画）。",
  },
  {
    title: "邀请好友同世",
    body: "Play 页点「邀请」复制链接；对方登录后加入，各自操控自己的角色。活世界随后端进程结束。",
  },
] as const;

export default function OnboardingModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(KEY)) setOpen(true);
    } catch {
      /* ignore */
    }
  }, []);

  function dismiss() {
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      /* ignore */
    }
    setOpen(false);
  }

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-[80] bg-black/70" onClick={dismiss} />
      <div
        className="fixed left-1/2 top-1/2 z-[90] w-[min(420px,92vw)] -translate-x-1/2 -translate-y-1/2
                   rounded-2xl border border-amber-900/40 bg-stone-950 p-6 shadow-2xl space-y-4"
        role="dialog"
        aria-labelledby="onboard-title"
      >
        <h2 id="onboard-title" className="font-serif text-xl text-amber-100 tracking-wider">
          如何游玩
        </h2>
        <p className="text-[12px] text-amber-200/70 leading-relaxed">
          Tech Preview · 推荐桌面浏览器。世界随后端进程结束，请及时体验。
        </p>
        <ol className="space-y-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex gap-3">
              <span className="shrink-0 w-6 h-6 rounded-full border border-amber-700/50
                               text-[11px] flex items-center justify-center text-amber-200/80">
                {i + 1}
              </span>
              <div>
                <div className="text-sm text-amber-50/95">{s.title}</div>
                <p className="text-[12px] opacity-60 mt-0.5 leading-relaxed">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
        <button
          type="button"
          onClick={dismiss}
          className="w-full py-2.5 rounded-lg bg-amber-500/90 text-stone-900 font-semibold
                     hover:bg-amber-400 text-sm"
        >
          开始探索
        </button>
      </div>
    </>
  );
}
