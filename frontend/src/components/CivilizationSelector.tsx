"use client";

import { useEffect, useState } from "react";
import { listSeeds, type Seed } from "@/lib/api";

type Props = {
  value: string;
  onChange: (key: string, seed?: Seed) => void;
  className?: string;
};

export default function CivilizationSelector({ value, onChange, className = "" }: Props) {
  const [seeds, setSeeds] = useState<Seed[]>([]);

  useEffect(() => {
    listSeeds().then(setSeeds).catch(() => setSeeds([]));
  }, []);

  return (
    <label className={`block text-[11px] space-y-1 ${className}`}>
      <span className="opacity-70">绑定文明</span>
      <select
        value={value}
        onChange={(e) => {
          const key = e.target.value;
          onChange(key, seeds.find((s) => s.key === key));
        }}
        className="w-full bg-stone-950 border border-stone-700 rounded px-2 py-1.5 text-[12px]"
      >
        {seeds.map((s) => (
          <option key={s.key} value={s.key}>
            {s.is_custom ? "★ " : ""}{s.name} ({s.genre})
          </option>
        ))}
      </select>
    </label>
  );
}
