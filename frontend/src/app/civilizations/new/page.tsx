"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createCustomCivilization } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import CivilizationRuleEditor, {
  DEFAULT_CIV_CONFIG,
  cleanCivConfig,
} from "@/components/CivilizationRuleEditor";

export default function NewCustomCivilizationPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [cfg, setCfg] = useState(DEFAULT_CIV_CONFIG);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (authLoading || !user) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">载入中…</main>;
  }

  async function onSubmit() {
    setBusy(true);
    setErr(null);
    try {
      const { civilization } = await createCustomCivilization(cleanCivConfig(cfg));
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
          <div className="flex gap-3 text-[11px] opacity-50">
            <Link href="/simulator" className="hover:opacity-80">← 文明模拟器</Link>
            <Link href="/civilizations" className="hover:opacity-80">我的文明</Link>
          </div>
          <h1 className="font-serif text-3xl tracking-wider mt-2">创建自定义文明</h1>
          <p className="text-sm opacity-60 mt-1">
            编辑世界规则、地点与势力，生成可游玩的文明种子。
          </p>
        </div>

        <CivilizationRuleEditor
          cfg={cfg}
          onChange={setCfg}
          onSubmit={onSubmit}
          busy={busy}
          err={err}
          submitLabel="创建文明并选择角色"
        />
      </div>
    </main>
  );
}
