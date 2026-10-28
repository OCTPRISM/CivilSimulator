"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  consumeMagicLink,
  forgotPassword,
  formatActionError,
  getAuthConfig,
  requestMagicLink,
  resetPassword,
  verifyEmail,
  type AuthConfig,
} from "@/lib/api";
import { safeNextPath } from "@/lib/errors";
import SiteLogo from "@/components/SiteLogo";
import BrandAtmosphere from "@/components/BrandAtmosphere";
import { useI18n } from "@/lib/i18n";

type Mode = "login" | "register" | "forgot" | "reset" | "magic" | "verify";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { login, register, user, loading: authLoading, persistToken } = useAuth();
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [identity, setIdentity] = useState("");
  const [token, setToken] = useState("");
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [cfgErr, setCfgErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    getAuthConfig()
      .then((c) => {
        setCfg(c);
        setCfgErr(null);
      })
      .catch((e) => {
        setCfg(null);
        setCfgErr(e instanceof Error ? e.message : t("login.cfgFail"));
      });
  }, []);

  const nextPath = safeNextPath(params.get("next"), "/");

  useEffect(() => {
    const m = (params.get("mode") || "").toLowerCase() as Mode;
    const t = params.get("token") || "";
    if (m === "reset" || m === "magic" || m === "verify" || m === "forgot") {
      setMode(m);
    }
    if (t) setToken(t);
  }, [params]);

  useEffect(() => {
    if (mode !== "magic" && mode !== "verify") return;
    if (!token || authLoading || user) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErr(null);
      try {
        if (mode === "magic") {
          const j = await consumeMagicLink(token);
          persistToken(j.token, j.user);
          router.replace(nextPath);
        } else {
          await verifyEmail(token);
          if (!cancelled) setInfo(t("login.emailVerified"));
          setMode("login");
        }
      } catch (e) {
        if (!cancelled) setErr(formatActionError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, token, authLoading, user, persistToken, router, nextPath]);

  if (authLoading) {
    return (
      <main className="brand-surface min-h-screen flex items-center justify-center text-[var(--brand-ink-muted)]">
        {t("common.verifying")}
      </main>
    );
  }

  if (user && mode !== "verify") {
    router.replace(nextPath);
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    setInfo(null);
    try {
      if (mode === "login") {
        await login(username, password);
        router.replace(nextPath);
      } else if (mode === "register") {
        if (!cfg) throw new Error(cfgErr || t("login.cfgNotReady"));
        await register(username, password, displayName, inviteCode, email);
        router.replace(nextPath);
      } else if (mode === "forgot") {
        const j = await forgotPassword(identity);
        setInfo(j.message + (j.dev_link ? t("login.devLink") : ""));
        if (j.dev_link) setInfo(`${j.message}\n${j.dev_link}`);
      } else if (mode === "reset") {
        const j = await resetPassword(token, password);
        persistToken(j.token, j.user);
        router.replace(nextPath);
      } else if (mode === "magic" && !token) {
        const j = await requestMagicLink(identity);
        setInfo(j.dev_link ? `${j.message}\n${j.dev_link}` : j.message);
      }
    } catch (e) {
      setErr(formatActionError(e));
    } finally {
      setLoading(false);
    }
  }

  const minPw = cfg?.min_password_length || 8;
  const inviteOnly = Boolean(cfg?.invite_only);
  const registerBlocked = mode === "register" && (!cfg || Boolean(cfgErr));
  const fieldClass =
    "w-full rounded-md bg-[var(--brand-bg-deep)]/80 border border-[var(--brand-line)] "
    + "px-3 py-2.5 text-sm text-[var(--brand-ink)] focus:border-[var(--brand-amber)] outline-none "
    + "placeholder:text-[var(--brand-ink-muted)]";

  return (
    <main className="brand-surface min-h-screen flex flex-col">
      <BrandAtmosphere />
      <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-5 py-12">
        <div className="brand-hero-in flex flex-col items-center text-center mb-8 sm:mb-10">
          <SiteLogo href={null} hero />
          <p className="mt-6 text-sm sm:text-base text-[var(--brand-ink-muted)] tracking-wide max-w-sm">
            {t("login.lead")}
          </p>
        </div>

        <div className="brand-panel brand-panel-in w-full max-w-sm p-6 sm:p-7">
          {(mode === "login" || mode === "register") && (
            <div className="flex gap-2 mb-6">
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`flex-1 py-2.5 rounded-md text-sm border transition
                    ${mode === m
                      ? "border-[var(--brand-amber)] bg-amber-500/15 text-amber-50"
                      : "border-[var(--brand-line)] text-[var(--brand-ink-muted)]"}`}
                >
                  {m === "login" ? t("login.login") : t("login.register")}
                </button>
              ))}
            </div>
          )}

          {mode === "forgot" && (
            <h2 className="text-sm mb-4 text-amber-100/90 font-serif tracking-wider">{t("login.resetTitle")}</h2>
          )}
          {mode === "reset" && (
            <h2 className="text-sm mb-4 text-amber-100/90 font-serif tracking-wider">{t("login.newPasswordTitle")}</h2>
          )}
          {mode === "magic" && !token && (
            <h2 className="text-sm mb-4 text-amber-100/90 font-serif tracking-wider">{t("login.magicTitle")}</h2>
          )}

          <form onSubmit={submit} className="space-y-3">
            {mode === "register" && (
              <>
                <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                  placeholder={t("login.displayName")} className={fieldClass} />
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder={t("login.email")} className={fieldClass} />
                {inviteOnly && (
                  <input value={inviteCode} onChange={(e) => setInviteCode(e.target.value)}
                    placeholder={t("login.invite")} required className={fieldClass} />
                )}
              </>
            )}

            {(mode === "login" || mode === "register") && (
              <>
                <input value={username} onChange={(e) => setUsername(e.target.value)}
                  placeholder={t("login.username")} required minLength={3} className={fieldClass} />
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "register" ? t("login.passwordMin", { n: minPw }) : t("login.password")}
                  required minLength={mode === "register" ? minPw : 1}
                  className={fieldClass} />
              </>
            )}

            {(mode === "forgot" || (mode === "magic" && !token)) && (
              <input value={identity} onChange={(e) => setIdentity(e.target.value)}
                placeholder={t("login.identity")} required className={fieldClass} />
            )}

            {mode === "reset" && (
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder={t("login.newPasswordMin", { n: minPw })}
                required minLength={minPw} className={fieldClass} />
            )}

            {!(mode === "magic" && token) && !(mode === "verify") && (
              <button type="submit" disabled={loading || registerBlocked}
                className="brand-cta w-full disabled:opacity-40">
                {loading
                  ? t("login.wait")
                  : mode === "login"
                    ? t("login.login")
                    : mode === "register"
                      ? t("login.registerAndEnter")
                      : mode === "forgot"
                        ? t("login.sendReset")
                        : mode === "reset"
                          ? t("login.updateAndLogin")
                          : t("login.sendMagic")}
              </button>
            )}
          </form>

          {err && <p className="text-rose-300 text-sm mt-3 whitespace-pre-wrap">{err}</p>}
          {info && <p className="text-emerald-300/90 text-sm mt-3 whitespace-pre-wrap break-all">{info}</p>}
          {mode === "register" && cfgErr && (
            <p className="text-rose-300 text-sm mt-3">{cfgErr}</p>
          )}
          {mode === "register" && inviteOnly && (
            <p className="text-[11px] text-[var(--brand-ink-muted)] mt-3">{t("login.inviteHint")}</p>
          )}

          <div className="mt-5 flex flex-col gap-2 text-[12px] text-[var(--brand-ink-muted)]">
            {mode === "login" && (
              <>
                <button type="button" className="text-left hover:text-[var(--brand-amber)]"
                  onClick={() => { setMode("forgot"); setErr(null); setInfo(null); }}>
                  {t("login.forgot")}
                </button>
                <button type="button" className="text-left hover:text-[var(--brand-amber)]"
                  onClick={() => { setMode("magic"); setToken(""); setErr(null); setInfo(null); }}>
                  {t("login.magic")}
                </button>
              </>
            )}
            {(mode === "forgot" || mode === "magic" || mode === "reset") && (
              <button type="button" className="text-left hover:text-[var(--brand-amber)]"
                onClick={() => { setMode("login"); setErr(null); setInfo(null); }}>
                {t("login.back")}
              </button>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

function LoginFallback() {
  const { t } = useI18n();
  return (
    <main className="brand-surface min-h-screen flex items-center justify-center text-[var(--brand-ink-muted)]">
      {t("common.loadingShort")}
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginInner />
    </Suspense>
  );
}
