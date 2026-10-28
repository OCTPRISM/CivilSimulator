"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createCustomCivilization, formatActionError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import CivilizationRuleEditor, {
  DEFAULT_CIV_CONFIG,
  cleanCivConfig,
} from "@/components/CivilizationRuleEditor";
import { useI18n } from "@/lib/i18n";

export default function NewCustomCivilizationPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { t } = useI18n();
  const [cfg, setCfg] = useState(DEFAULT_CIV_CONFIG);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent("/civilizations/new")}`);
    }
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return <main className="min-h-screen flex items-center justify-center opacity-60">{t("common.loadingShort")}</main>;
  }

  async function onSubmit() {
    setBusy(true);
    setErr(null);
    try {
      const { civilization } = await createCustomCivilization(cleanCivConfig(cfg));
      router.push(`/create/${civilization.key}`);
    } catch (e) {
      setErr(formatActionError(e));
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <div className="flex gap-3 text-[11px] opacity-50">
            <Link href="/simulator" className="hover:opacity-80">← {t("nav.simulator")}</Link>
            <Link href="/civilizations" className="hover:opacity-80">{t("civs.mine")}</Link>
          </div>
          <h1 className="font-serif text-3xl tracking-wider mt-2">{t("civs.createTitle")}</h1>
          <p className="text-sm opacity-60 mt-1">
            {t("civs.createLead")}
          </p>
        </div>

        <CivilizationRuleEditor
          cfg={cfg}
          onChange={setCfg}
          onSubmit={onSubmit}
          busy={busy}
          err={err}
          submitLabel={t("civs.createSubmit")}
        />
      </div>
    </main>
  );
}
