"use client";

import type { AgentSkill } from "@/lib/api";

type Props = {
  skills: AgentSkill[];
  loading?: boolean;
  disabled?: boolean;
  onUse: (skillId: string) => void;
};

export default function SkillPanel({ skills, loading, disabled, onUse }: Props) {
  if (!skills?.length) return null;

  const basic = skills.filter((s) => s.kind === "basic");
  const unique = skills.filter((s) => s.kind === "unique");

  return (
    <div className="rounded-xl border border-stone-800 bg-stone-900/50 p-3">
      <div className="text-[11px] uppercase tracking-widest opacity-60 mb-2">
        动作 · 技能
      </div>
      {basic.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] opacity-50 mb-1">常规</div>
          <div className="flex flex-wrap gap-1.5">
            {basic.map((s) => (
              <SkillBtn key={s.id} skill={s} loading={loading} disabled={disabled}
                        onUse={onUse} tone="basic" />
            ))}
          </div>
        </div>
      )}
      {unique.length > 0 && (
        <div>
          <div className="text-[10px] opacity-50 mb-1">特有</div>
          <div className="flex flex-wrap gap-1.5">
            {unique.map((s) => (
              <SkillBtn key={s.id} skill={s} loading={loading} disabled={disabled}
                        onUse={onUse} tone="unique" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SkillBtn({
  skill, loading, disabled, onUse, tone,
}: {
  skill: AgentSkill;
  loading?: boolean;
  disabled?: boolean;
  onUse: (id: string) => void;
  tone: "basic" | "unique";
}) {
  const ready = skill.ready !== false;
  const blocked = disabled || loading || !ready;
  return (
    <button
      type="button"
      disabled={blocked}
      title={skill.description || skill.action_prompt}
      onClick={() => onUse(skill.id)}
      className={`px-2.5 py-1.5 rounded-md text-[12px] border transition disabled:opacity-40
        ${tone === "unique"
          ? "border-violet-500/50 text-violet-200 hover:bg-violet-500/15"
          : "border-stone-600 text-stone-200 hover:border-amber-400/60 hover:bg-amber-500/10"}`}
    >
      {skill.name}
      {!ready && skill.cooldown > 0 ? (
        <span className="opacity-50 ml-1 text-[10px]">冷却</span>
      ) : null}
    </button>
  );
}
