"use client";

import type { CustomCivilizationConfig } from "@/lib/api";

const CLASS_LABELS: Record<string, string> = {
  ruling: "统治阶层", middle: "中产/市民", labor: "劳动阶层", marginal: "边缘群体",
};
const AGE_LABELS: Record<string, string> = {
  child: "0-14岁", youth: "15-29岁", adult: "30-44岁", middle_aged: "45-59岁", elder: "60岁以上",
};

export const GENRE_OPTIONS = [
  { value: "custom", label: "自定义" },
  { value: "ancient", label: "古代" },
  { value: "wuxia", label: "武侠" },
  { value: "xuanhuan", label: "玄幻" },
  { value: "scifi", label: "科幻" },
  { value: "mystery", label: "悬疑" },
  { value: "modern", label: "现代" },
] as const;

export const DEFAULT_CIV_CONFIG: CustomCivilizationConfig = {
  name: "",
  genre: "ancient",
  premise: "",
  class_structure: { ruling: 0.05, middle: 0.35, labor: 0.50, marginal: 0.10 },
  age_structure: { child: 0.18, youth: 0.22, adult: 0.40, middle_aged: 0.12, elder: 0.08 },
  operating_logic: "",
  government_form: "",
  professions: [{ name: "", description: "", playable: true }],
  roles: [{ name: "", persona: "", profession: "" }],
  historical_events: [{ era: "", title: "", description: "" }],
  current_stage: "",
  rules: [""],
  locations: [{ name: "", description: "", tags: [] }],
  factions: [{ name: "", ideology: "" }],
  opening_scene: "",
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

const field =
  "w-full bg-stone-950 border border-stone-700 rounded px-3 py-2 text-[12px]";
const fieldSm =
  "bg-stone-950 border border-stone-700 rounded px-2 py-1 text-[12px]";

type Props = {
  cfg: CustomCivilizationConfig;
  onChange: (cfg: CustomCivilizationConfig) => void;
  onSubmit: () => void;
  busy?: boolean;
  submitLabel?: string;
  err?: string | null;
};

/** Shared M4 rule editor — create & edit custom civilization seeds. */
export default function CivilizationRuleEditor({
  cfg, onChange, onSubmit, busy, submitLabel = "保存", err,
}: Props) {
  const set = (patch: Partial<CustomCivilizationConfig>) => onChange({ ...cfg, ...patch });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }}
      className="space-y-8"
    >
      <section className="space-y-3">
        <h2 className="font-serif text-lg">基本信息</h2>
        <label className="block text-[12px] space-y-1">
          文明名称
          <input value={cfg.name} onChange={(e) => set({ name: e.target.value })} className={field} />
        </label>
        <label className="block text-[12px] space-y-1">
          气质 / 时代（影响氛围音画）
          <select
            value={cfg.genre || "custom"}
            onChange={(e) => set({ genre: e.target.value })}
            className={field}
          >
            {GENRE_OPTIONS.map((g) => (
              <option key={g.value} value={g.value}>{g.label}</option>
            ))}
          </select>
        </label>
        <label className="block text-[12px] space-y-1">
          世界前提
          <textarea
            value={cfg.premise || ""}
            onChange={(e) => set({ premise: e.target.value })}
            rows={2}
            placeholder="一句话概括这个文明正在发生什么"
            className={`${field} leading-relaxed`}
          />
        </label>
        <label className="block text-[12px] space-y-1">
          政权组织形式
          <input value={cfg.government_form}
                 onChange={(e) => set({ government_form: e.target.value })}
                 placeholder="如：联邦共和制 / 宗藩体系 / 企业城邦"
                 className={field} />
        </label>
        <label className="block text-[12px] space-y-1">
          当前所处阶段
          <input value={cfg.current_stage}
                 onChange={(e) => set({ current_stage: e.target.value })}
                 placeholder="如：变法前夜 / 工业扩张期 / 星际殖民初期"
                 className={field} />
        </label>
        <label className="block text-[12px] space-y-1">
          <span>文明运行逻辑 <span className="text-red-400">*</span></span>
          <textarea value={cfg.operating_logic}
                    onChange={(e) => set({ operating_logic: e.target.value })}
                    required
                    rows={4}
                    placeholder="描述该文明的基本运行法则：经济如何运转、权力如何分配、冲突如何升级…"
                    className={`${field} leading-relaxed`} />
        </label>
        <label className="block text-[12px] space-y-1">
          开场旁白
          <textarea
            value={cfg.opening_scene || ""}
            onChange={(e) => set({ opening_scene: e.target.value })}
            rows={2}
            placeholder="玩家踏入世界时读到的第一段叙述"
            className={`${field} leading-relaxed`}
          />
        </label>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-lg">世界规则</h2>
        <p className="text-[11px] opacity-50">叙事与 NPC 推理会遵守这些硬约束（最多 12 条）。留空则由运行逻辑自动生成。</p>
        {(cfg.rules || []).map((rule, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={rule}
              onChange={(e) => {
                const rules = [...(cfg.rules || [])];
                rules[i] = e.target.value;
                set({ rules });
              }}
              placeholder={`规则 ${i + 1}，如：无超自然力量`}
              className={`flex-1 ${fieldSm}`}
            />
            <button
              type="button"
              className="text-[11px] opacity-50 hover:opacity-100 px-2"
              onClick={() => set({ rules: (cfg.rules || []).filter((_, j) => j !== i) })}
            >
              删
            </button>
          </div>
        ))}
        <button
          type="button"
          disabled={(cfg.rules || []).length >= 12}
          onClick={() => set({ rules: [...(cfg.rules || []), ""] })}
          className="text-[11px] opacity-60 hover:opacity-100 disabled:opacity-30"
        >
          + 添加规则
        </button>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-lg">地点</h2>
        <p className="text-[11px] opacity-50">留空则自动生成「中枢 / 市井 / 边域」。</p>
        {(cfg.locations || []).map((loc, i) => (
          <div key={i} className="space-y-2 rounded border border-stone-800 p-3">
            <div className="flex gap-2">
              <input
                value={loc.name}
                onChange={(e) => {
                  const locations = [...(cfg.locations || [])];
                  locations[i] = { ...locations[i], name: e.target.value };
                  set({ locations });
                }}
                placeholder="地点名"
                className={`flex-1 ${fieldSm}`}
              />
              <input
                value={(loc.tags || []).join("，")}
                onChange={(e) => {
                  const locations = [...(cfg.locations || [])];
                  locations[i] = {
                    ...locations[i],
                    tags: e.target.value.split(/[,，]/).map((t) => t.trim()).filter(Boolean),
                  };
                  set({ locations });
                }}
                placeholder="标签，逗号分隔"
                className={`flex-1 ${fieldSm}`}
              />
            </div>
            <textarea
              value={loc.description || ""}
              onChange={(e) => {
                const locations = [...(cfg.locations || [])];
                locations[i] = { ...locations[i], description: e.target.value };
                set({ locations });
              }}
              placeholder="地点描述"
              rows={2}
              className={`w-full ${fieldSm}`}
            />
          </div>
        ))}
        <button
          type="button"
          onClick={() => set({
            locations: [...(cfg.locations || []), { name: "", description: "", tags: [] }],
          })}
          className="text-[11px] opacity-60 hover:opacity-100"
        >
          + 添加地点
        </button>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-lg">势力</h2>
        <p className="text-[11px] opacity-50">留空则按阶层比例自动生成。</p>
        {(cfg.factions || []).map((fac, i) => (
          <div key={i} className="grid sm:grid-cols-2 gap-2">
            <input
              value={fac.name}
              onChange={(e) => {
                const factions = [...(cfg.factions || [])];
                factions[i] = { ...factions[i], name: e.target.value };
                set({ factions });
              }}
              placeholder="势力名"
              className={fieldSm}
            />
            <input
              value={fac.ideology || ""}
              onChange={(e) => {
                const factions = [...(cfg.factions || [])];
                factions[i] = { ...factions[i], ideology: e.target.value };
                set({ factions });
              }}
              placeholder="主张 / 意识形态"
              className={fieldSm}
            />
          </div>
        ))}
        <button
          type="button"
          onClick={() => set({ factions: [...(cfg.factions || []), { name: "", ideology: "" }] })}
          className="text-[11px] opacity-60 hover:opacity-100"
        >
          + 添加势力
        </button>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-lg">人口结构 · 阶层比例</h2>
        <RatioEditor labels={CLASS_LABELS} values={cfg.class_structure}
                     onChange={(v) => set({ class_structure: v })} />
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-lg">人口结构 · 年龄段比例</h2>
        <RatioEditor labels={AGE_LABELS} values={cfg.age_structure}
                     onChange={(v) => set({ age_structure: v })} />
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-lg">可操作职业</h2>
        {cfg.professions.map((p, i) => (
          <div key={i} className="flex gap-2 items-start">
            <input value={p.name}
                   onChange={(e) => {
                     const ps = [...cfg.professions];
                     ps[i] = { ...ps[i], name: e.target.value };
                     set({ professions: ps });
                   }}
                   placeholder="职业名称"
                   className={`flex-1 ${fieldSm}`} />
            <input value={p.description || ""}
                   onChange={(e) => {
                     const ps = [...cfg.professions];
                     ps[i] = { ...ps[i], description: e.target.value };
                     set({ professions: ps });
                   }}
                   placeholder="描述"
                   className={`flex-[2] ${fieldSm}`} />
            <label className="text-[10px] flex items-center gap-1 shrink-0 pt-1">
              <input type="checkbox" checked={p.playable !== false}
                     onChange={(e) => {
                       const ps = [...cfg.professions];
                       ps[i] = { ...ps[i], playable: e.target.checked };
                       set({ professions: ps });
                     }} />
              可扮演
            </label>
          </div>
        ))}
        <button type="button"
                onClick={() => set({ professions: [...cfg.professions, { name: "", playable: true }] })}
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
                     set({ roles: rs });
                   }}
                   placeholder="角色名"
                   className={fieldSm} />
            <input value={r.profession || ""}
                   onChange={(e) => {
                     const rs = [...cfg.roles];
                     rs[i] = { ...rs[i], profession: e.target.value };
                     set({ roles: rs });
                   }}
                   placeholder="身份/职业"
                   className={fieldSm} />
            <textarea value={r.persona || ""}
                      onChange={(e) => {
                        const rs = [...cfg.roles];
                        rs[i] = { ...rs[i], persona: e.target.value };
                        set({ roles: rs });
                      }}
                      placeholder="人物设定"
                      rows={2}
                      className={`sm:col-span-2 ${fieldSm}`} />
          </div>
        ))}
        <button type="button"
                onClick={() => set({ roles: [...cfg.roles, { name: "" }] })}
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
                     set({ historical_events: es });
                   }}
                   placeholder="年代"
                   className={fieldSm} />
            <input value={ev.title}
                   onChange={(e) => {
                     const es = [...cfg.historical_events];
                     es[i] = { ...es[i], title: e.target.value };
                     set({ historical_events: es });
                   }}
                   placeholder="事件标题"
                   className={`sm:col-span-2 ${fieldSm}`} />
            <textarea value={ev.description || ""}
                      onChange={(e) => {
                        const es = [...cfg.historical_events];
                        es[i] = { ...es[i], description: e.target.value };
                        set({ historical_events: es });
                      }}
                      placeholder="事件描述"
                      rows={2}
                      className={`sm:col-span-3 ${fieldSm}`} />
          </div>
        ))}
        <button type="button"
                onClick={() => set({
                  historical_events: [...cfg.historical_events, { title: "" }],
                })}
                className="text-[11px] opacity-60 hover:opacity-100">+ 添加事件</button>
      </section>

      {err && <p className="text-red-400 text-sm">{err}</p>}

      <button type="submit" disabled={busy || !cfg.operating_logic.trim()}
              className="w-full py-3 rounded-lg bg-amber-500/90 text-stone-950 font-semibold
                         disabled:opacity-40">
        {busy ? "保存中…" : submitLabel}
      </button>
    </form>
  );
}

/** Strip empty rows before API submit. */
export function cleanCivConfig(cfg: CustomCivilizationConfig): CustomCivilizationConfig {
  return {
    ...cfg,
    name: cfg.name.trim() || "未命名文明",
    premise: (cfg.premise || "").trim(),
    opening_scene: (cfg.opening_scene || "").trim(),
    rules: (cfg.rules || []).map((r) => r.trim()).filter(Boolean),
    locations: (cfg.locations || []).filter((l) => l.name.trim()).map((l) => ({
      ...l,
      name: l.name.trim(),
      description: (l.description || "").trim(),
      tags: (l.tags || []).filter(Boolean),
    })),
    factions: (cfg.factions || []).filter((f) => f.name.trim()).map((f) => ({
      ...f,
      name: f.name.trim(),
      ideology: (f.ideology || "").trim(),
    })),
    professions: cfg.professions.filter((p) => p.name.trim()),
    roles: cfg.roles.filter((r) => r.name.trim()),
    historical_events: cfg.historical_events.filter((ev) => ev.title.trim()),
  };
}
