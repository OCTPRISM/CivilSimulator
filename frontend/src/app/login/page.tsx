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

type Mode = "login" | "register" | "forgot" | "reset" | "magic" | "verify";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { login, register, user, loading: authLoading, persistToken } = useAuth();
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
        setCfgErr(e instanceof Error ? e.message : "无法加载注册策略");
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
          if (!cancelled) setInfo("邮箱已验证，请登录。");
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
        正在验证登录…
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
        if (!cfg) throw new Error(cfgErr || "注册策略未就绪，请刷新后重试");
        await register(username, password, displayName, inviteCode, email);
        router.replace(nextPath);
      } else if (mode === "forgot") {
        const j = await forgotPassword(identity);
        setInfo(j.message + (j.dev_link ? `（开发链接已返回，见下方）` : ""));
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
            注册或登录后，方可踏入文明世界。
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
                  {m === "login" ? "登录" : "注册"}
                </button>
              ))}
            </div>
          )}

          {mode === "forgot" && (
            <h2 className="text-sm mb-4 text-amber-100/90 font-serif tracking-wider">重置密码</h2>
          )}
          {mode === "reset" && (
            <h2 className="text-sm mb-4 text-amber-100/90 font-serif tracking-wider">设置新密码</h2>
          )}
          {mode === "magic" && !token && (
            <h2 className="text-sm mb-4 text-amber-100/90 font-serif tracking-wider">魔法链接登录</h2>
          )}

          <form onSubmit={submit} className="space-y-3">
            {mode === "register" && (
              <>
                <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="显示名（可选）" className={fieldClass} />
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="邮箱（可选，用于重置/魔法链接）" className={fieldClass} />
                {inviteOnly && (
                  <input value={inviteCode} onChange={(e) => setInviteCode(e.target.value)}
                    placeholder="邀测注册码" required className={fieldClass} />
                )}
              </>
            )}

            {(mode === "login" || mode === "register") && (
              <>
                <input value={username} onChange={(e) => setUsername(e.target.value)}
                  placeholder="用户名（至少 3 字）" required minLength={3} className={fieldClass} />
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "register" ? `密码（至少 ${minPw} 位）` : "密码"}
                  required minLength={mode === "register" ? minPw : 1}
                  className={fieldClass} />
              </>
            )}

            {(mode === "forgot" || (mode === "magic" && !token)) && (
              <input value={identity} onChange={(e) => setIdentity(e.target.value)}
                placeholder="用户名或邮箱" required className={fieldClass} />
            )}

            {mode === "reset" && (
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder={`新密码（至少 ${minPw} 位）`}
                required minLength={minPw} className={fieldClass} />
            )}

            {!(mode === "magic" && token) && !(mode === "verify") && (
              <button type="submit" disabled={loading || registerBlocked}
                className="brand-cta w-full disabled:opacity-40">
                {loading
                  ? "请稍候…"
                  : mode === "login"
                    ? "登录"
                    : mode === "register"
                      ? "注册并登录"
                      : mode === "forgot"
                        ? "发送重置链接"
                        : mode === "reset"
                          ? "更新密码并登录"
                          : "发送魔法链接"}
              </button>
            )}
          </form>

          {err && <p className="text-rose-300 text-sm mt-3 whitespace-pre-wrap">{err}</p>}
          {info && <p className="text-emerald-300/90 text-sm mt-3 whitespace-pre-wrap break-all">{info}</p>}
          {mode === "register" && cfgErr && (
            <p className="text-rose-300 text-sm mt-3">{cfgErr}</p>
          )}
          {mode === "register" && inviteOnly && (
            <p className="text-[11px] text-[var(--brand-ink-muted)] mt-3">当前为邀测模式，注册需要有效注册码。</p>
          )}

          <div className="mt-5 flex flex-col gap-2 text-[12px] text-[var(--brand-ink-muted)]">
            {mode === "login" && (
              <>
                <button type="button" className="text-left hover:text-[var(--brand-amber)]"
                  onClick={() => { setMode("forgot"); setErr(null); setInfo(null); }}>
                  忘记密码？
                </button>
                <button type="button" className="text-left hover:text-[var(--brand-amber)]"
                  onClick={() => { setMode("magic"); setToken(""); setErr(null); setInfo(null); }}>
                  使用魔法链接登录
                </button>
              </>
            )}
            {(mode === "forgot" || mode === "magic" || mode === "reset") && (
              <button type="button" className="text-left hover:text-[var(--brand-amber)]"
                onClick={() => { setMode("login"); setErr(null); setInfo(null); }}>
                返回登录
              </button>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <main className="brand-surface min-h-screen flex items-center justify-center text-[var(--brand-ink-muted)]">
        加载中…
      </main>
    }>
      <LoginInner />
    </Suspense>
  );
}
