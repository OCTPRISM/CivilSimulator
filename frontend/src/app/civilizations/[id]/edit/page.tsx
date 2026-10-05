"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getCustomCivilization,
  updateCustomCivilization,
  type CustomCivilizationConfig,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import CivilizationRuleEditor, {
  DEFAULT_CIV_CONFIG,
  cleanCivConfig,
} from "@/components/CivilizationRuleEditor";

export default function EditCustomCivilizationPage({ params }: { params: { id: string } }) {
  const civId = params.id;
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [cfg, setCfg] = useState<CustomCivilizationConfig | null>(null);
  const [seedKey, setSeedKey] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) router.replace(`/login?next=/civilizations/${civId}/edit`);
  }, [authLoading, user, router, civId]);

  useEffect(() => {
    if (!user) return;
    getCustomCivilization(civId)
      .then((row) => {
        setSeedKey(row.key);
        setCfg({
          ...DEFAULT_CIV_CONFIG,
          ...row.config,
          rules: row.config.rules?.length ? row.config.rules : [""],
          locations: row.config.locations?.length
            ? row.config.locations
            : [{ name: "", description: "", tags: [] }],
          factions: row.config.factions?.length
            ? row.config.factions
            : [{ name: "", ideology: "" }],
          professions: row.config.professions?.length
            ? row.config.professions
            : [{ name: "", playable: true }],
          roles: row.config.roles?.length ? row.config.roles : [{ name: "" }],
          historical_events: row.config.historical_events?.length
            ? row.config.historical_events
            : [{ title: "" }],
        });
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [user, civId]);

  async function onSubmit() {
    if (!cfg) return;
    setBusy(true);
    setErr(null);
    try {
      await updateCustomCivilization(civId, cleanCivConfig(cfg));
      router.push(seedKey ? `/create/${seedKey}` : "/civilizations");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
      setBusy(false);
    }
  }

  if (authLoading || !user || loading) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">载入中…</main>;
  }

  if (!cfg) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center gap-3">
        <p className="text-red-400 text-sm">{err || "未找到该文明"}</p>
        <Link href="/civilizations" className="text-sm opacity-70 hover:opacity-100">返回列表</Link>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <div className="flex gap-3 text-[11px] opacity-50">
            <Link href="/civilizations" className="hover:opacity-80">← 我的文明</Link>
            {seedKey && (
              <Link href={`/create/${seedKey}`} className="hover:opacity-80">进入选角</Link>
            )}
          </div>
          <h1 className="font-serif text-3xl tracking-wider mt-2">编辑文明规则</h1>
          <p className="text-sm opacity-60 mt-1">{cfg.name || "未命名文明"}</p>
        </div>

        <CivilizationRuleEditor
          cfg={cfg}
          onChange={setCfg}
          onSubmit={onSubmit}
          busy={busy}
          err={err}
          submitLabel="保存并继续选角"
        />
      </div>
    </main>
  );
}
