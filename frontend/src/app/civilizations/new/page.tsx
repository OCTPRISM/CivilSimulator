"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createCustomCivilization, type CustomCivilizationConfig } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const CLASS_LABELS: Record<string, string> = {
  ruling: "统治阶层", middle: "中产/市民", labor: "劳动阶层", marginal: "边缘群体",
};
const AGE_LABELS: Record<string, string> = {
  child: "0-14岁", youth: "15-29岁", adult: "30-44岁", middle_aged: "45-59岁", elder: "60岁以上",
};

const DEFAULT: CustomCivilizationConfig = {
  name: "",
  class_structure: { ruling: 0.05, middle: 0.35, labor: 0.50, marginal: 0.10 },
  age_structure: { child: 0.18, youth: 0.22, adult: 0.40, middle_aged: 0.12, elder: 0.08 },
  operating_logic: "",
  government_form: "",
  professions: [{ name: "", description: "", playable: true }],
  roles: [{ name: "", persona: "", profession: "" }],
  historical_events: [{ era: "", title: "", description: "" }],
  current_stage: "",
};

function RatioEditor({
  labels, values, onChange,
}: {
  labels: Record<string, string>;
  values: Record<string, number>;
  onChange: (v: Record<string, number>) => void;
}) {
  return (
    <div className="space-y-2">
      {Object.entries(labels).map(([k, label]) => (
        <label key={k} className="flex items-center gap-3 text-[12px]">
          <span className="w-24 shrink-0 opacity-80">{label}</span>
          <input type="range" min={0} max={100} value={Math.round((values[k] || 0) * 100)}
                 onChange={(e) => onChange({ ...values, [k]: Number(e.target.value) / 100 })}
                 className="flex-1" />
          <span className="w-10 text-right opacity-60">{Math.round((values[k] || 0) * 100)}%</span>
        </label>
      ))}
    </div>
  );
}

export default function NewCustomCivilizationPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [cfg, setCfg] = useState<CustomCivilizationConfig>(DEFAULT);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (authLoading || !user) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">载入中…</main>;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const cleaned: CustomCivilizationConfig = {
        ...cfg,
        name: cfg.name.trim() || "未命名文明",
        professions: cfg.professions.filter((p) => p.name.trim()),
        roles: cfg.roles.filter((r) => r.name.trim()),
        historical_events: cfg.historical_events.filter((ev) => ev.title.trim()),
      };
      const { civilization } = await createCustomCivilization(cleaned);
      router.push(`/create/${civilization.key}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <Link href="/" className="text-[11px] opacity-50 hover:opacity-80">← 返回首页</Link>
          <h1 className="font-serif text-3xl tracking-wider mt-2">自定义文明</h1>
          <p className="text-sm opacity-60 mt-1">配置人口、运行逻辑与历史阶段，创建属于你的独有文明模拟器。</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-8">
          <section className="space-y-3">
            <h2 className="font-serif text-lg">基本信息</h2>
            <label className="block text-[12px] space-y-1">
              文明名称
              <input value={cfg.name} onChange={(e) => setCfg({ ...cfg, name: e.target.value })}
                     className="w-full bg-stone-950 border border-stone-700 rounded px-3 py-2" />
            </label>
            <label className="block text-[12px] space-y-1">
              政权组织形式
              <input value={cfg.government_form}
                     onChange={(e) => setCfg({ ...cfg, government_form: e.target.value })}
                     placeholder="如：联邦共和制 / 宗藩体系 / 企业城邦"
                     className="w-full bg-stone-950 border border-stone-700 rounded px-3 py-2" />
            </label>
            <label className="block text-[12px] space-y-1">
              当前所处阶段
              <input value={cfg.current_stage}
                     onChange={(e) => setCfg({ ...cfg, current_stage: e.target.value })}
                     placeholder="如：变法前夜 / 工业扩张期 / 星际殖民初期"
                     className="w-full bg-stone-950 border border-stone-700 rounded px-3 py-2" />
            </label>
            <label className="block text-[12px] space-y-1">
              <span>文明运行逻辑 <span className="text-red-400">*</span></span>
              <textarea value={cfg.operating_logic}
                        onChange={(e) => setCfg({ ...cfg, operating_logic: e.target.value })}
                        required
                        rows={4}
                        placeholder="描述该文明的基本运行法则：经济如何运转、权力如何分配、冲突如何升级…"
                        className="w-full bg-stone-950 border border-stone-700 rounded px-3 py-2 leading-relaxed" />
            </label>
          </section>

          <section className="space-y-3">
            <h2 className="font-serif text-lg">人口结构 · 阶层比例</h2>
            <RatioEditor labels={CLASS_LABELS} values={cfg.class_structure}
                         onChange={(v) => setCfg({ ...cfg, class_structure: v })} />
          </section>

          <section className="space-y-3">
            <h2 className="font-serif text-lg">人口结构 · 年龄段比例</h2>
            <RatioEditor labels={AGE_LABELS} values={cfg.age_structure}
                         onChange={(v) => setCfg({ ...cfg, age_structure: v })} />
          </section>

          <section className="space-y-3">
            <h2 className="font-serif text-lg">可操作职业</h2>
            {cfg.professions.map((p, i) => (
              <div key={i} className="flex gap-2 items-start">
                <input value={p.name}
                       onChange={(e) => {
                         const ps = [...cfg.professions];
                         ps[i] = { ...ps[i], name: e.target.value };
                         setCfg({ ...cfg, professions: ps });
                       }}
                       placeholder="职业名称"
                       className="flex-1 bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]" />
                <input value={p.description || ""}
                       onChange={(e) => {
                         const ps = [...cfg.professions];
                         ps[i] = { ...ps[i], description: e.target.value };
                         setCfg({ ...cfg, professions: ps });
                       }}
                       placeholder="描述"
                       className="flex-[2] bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]" />
                <label className="text-[10px] flex items-center gap-1 shrink-0 pt-1">
                  <input type="checkbox" checked={p.playable !== false}
                         onChange={(e) => {
                           const ps = [...cfg.professions];
                           ps[i] = { ...ps[i], playable: e.target.checked };
                           setCfg({ ...cfg, professions: ps });
                         }} />
                  可扮演
                </label>
              </div>
            ))}
            <button type="button"
                    onClick={() => setCfg({ ...cfg, professions: [...cfg.professions, { name: "", playable: true }] })}
                    className="text-[11px] opacity-60 hover:opacity-100">+ 添加职业</button>
          </section>

          <section className="space-y-3">
            <h2 className="font-serif text-lg">可选角色</h2>
            {cfg.roles.map((r, i) => (
              <div key={i} className="grid sm:grid-cols-2 gap-2">
                <input value={r.name}
                       onChange={(e) => {
                         const rs = [...cfg.roles];
                         rs[i] = { ...rs[i], name: e.target.value };
                         setCfg({ ...cfg, roles: rs });
                       }}
                       placeholder="角色名"
                       className="bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]" />
                <input value={r.profession || ""}
                       onChange={(e) => {
                         const rs = [...cfg.roles];
                         rs[i] = { ...rs[i], profession: e.target.value };
                         setCfg({ ...cfg, roles: rs });
                       }}
                       placeholder="身份/职业"
                       className="bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]" />
                <textarea value={r.persona || ""}
                          onChange={(e) => {
                            const rs = [...cfg.roles];
                            rs[i] = { ...rs[i], persona: e.target.value };
                            setCfg({ ...cfg, roles: rs });
                          }}
                          placeholder="人物设定"
                          rows={2}
                          className="sm:col-span-2 bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]" />
              </div>
            ))}
            <button type="button"
                    onClick={() => setCfg({ ...cfg, roles: [...cfg.roles, { name: "" }] })}
                    className="text-[11px] opacity-60 hover:opacity-100">+ 添加角色</button>
          </section>

          <section className="space-y-3">
            <h2 className="font-serif text-lg">关键历史事件</h2>
            {cfg.historical_events.map((ev, i) => (
              <div key={i} className="grid sm:grid-cols-3 gap-2">
                <input value={ev.era || ""}
                       onChange={(e) => {
                         const es = [...cfg.historical_events];
                         es[i] = { ...es[i], era: e.target.value };
                         setCfg({ ...cfg, historical_events: es });
                       }}
                       placeholder="年代"
                       className="bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]" />
                <input value={ev.title}
                       onChange={(e) => {
                         const es = [...cfg.historical_events];
                         es[i] = { ...es[i], title: e.target.value };
                         setCfg({ ...cfg, historical_events: es });
                       }}
                       placeholder="事件标题"
                       className="sm:col-span-2 bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]" />
                <textarea value={ev.description || ""}
                          onChange={(e) => {
                            const es = [...cfg.historical_events];
                            es[i] = { ...es[i], description: e.target.value };
                            setCfg({ ...cfg, historical_events: es });
                          }}
                          placeholder="事件描述"
                          rows={2}
                          className="sm:col-span-3 bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]" />
              </div>
            ))}
            <button type="button"
                    onClick={() => setCfg({
                      ...cfg,
                      historical_events: [...cfg.historical_events, { title: "" }],
                    })}
                    className="text-[11px] opacity-60 hover:opacity-100">+ 添加事件</button>
          </section>

          {err && <p className="text-red-400 text-sm">{err}</p>}

          <button type="submit" disabled={busy || !cfg.operating_logic.trim()}
                  className="w-full py-3 rounded-lg bg-amber-500/90 text-stone-950 font-semibold
                             disabled:opacity-40">
            {busy ? "正在创建…" : "创建文明并选择角色"}
          </button>
        </form>
      </div>
    </main>
  );
}
