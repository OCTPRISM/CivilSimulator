"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  consumeMagicLink,
  forgotPassword,
  getAuthConfig,
  requestMagicLink,
  resetPassword,
  verifyEmail,
  type AuthConfig,
} from "@/lib/api";

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
          router.replace("/");
        } else {
          await verifyEmail(token);
          if (!cancelled) setInfo("邮箱已验证，请登录。");
          setMode("login");
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "链接无效");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, token, authLoading, user, persistToken, router]);

  if (authLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center opacity-60">
        正在验证登录…
      </main>
    );
  }

  if (user && mode !== "verify") {
    router.replace("/");
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
        router.replace("/");
      } else if (mode === "register") {
        if (!cfg) throw new Error(cfgErr || "注册策略未就绪，请刷新后重试");
        await register(username, password, displayName, inviteCode, email);
        router.replace("/");
      } else if (mode === "forgot") {
        const j = await forgotPassword(identity);
        setInfo(j.message + (j.dev_link ? `（开发链接已返回，见下方）` : ""));
        if (j.dev_link) setInfo(`${j.message}\n${j.dev_link}`);
      } else if (mode === "reset") {
        const j = await resetPassword(token, password);
        persistToken(j.token, j.user);
        router.replace("/");
      } else if (mode === "magic" && !token) {
        const j = await requestMagicLink(identity);
        setInfo(j.dev_link ? `${j.message}\n${j.dev_link}` : j.message);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  const minPw = cfg?.min_password_length || 8;
  const inviteOnly = Boolean(cfg?.invite_only);
  const registerBlocked = mode === "register" && (!cfg || Boolean(cfgErr));

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-10">
      <h1 className="font-serif text-4xl tracking-widest mb-2">文明模拟器</h1>
      <p className="opacity-60 mb-1 text-sm">注册或登录后，方可踏入文明世界</p>
      <p className="opacity-35 mb-8 text-[11px] tracking-wider">Tech Preview 0.5</p>

      <div className="w-full max-w-sm rounded-xl border border-stone-700 bg-stone-900/50 p-6">
        {(mode === "login" || mode === "register") && (
          <div className="flex gap-2 mb-6">
            {(["login", "register"] as const).map((m) => (
              <button key={m} type="button" onClick={() => setMode(m)}
                className={`flex-1 py-2 rounded-md text-sm border transition
                  ${mode === m
                    ? "border-amber-400 bg-amber-500/15 text-amber-100"
                    : "border-stone-700 text-stone-400"}`}>
                {m === "login" ? "登录" : "注册"}
              </button>
            ))}
          </div>
        )}

        {mode === "forgot" && (
          <h2 className="text-sm mb-4 text-amber-100/90">重置密码</h2>
        )}
        {mode === "reset" && (
          <h2 className="text-sm mb-4 text-amber-100/90">设置新密码</h2>
        )}
        {mode === "magic" && !token && (
          <h2 className="text-sm mb-4 text-amber-100/90">魔法链接登录</h2>
        )}

        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <>
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                placeholder="显示名（可选）"
                className="w-full rounded-md bg-stone-950 border border-stone-700
                           px-3 py-2 text-sm focus:border-amber-400 outline-none" />
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="邮箱（可选，用于重置/魔法链接）"
                className="w-full rounded-md bg-stone-950 border border-stone-700
                           px-3 py-2 text-sm focus:border-amber-400 outline-none" />
              {inviteOnly && (
                <input value={inviteCode} onChange={(e) => setInviteCode(e.target.value)}
                  placeholder="邀测注册码" required
                  className="w-full rounded-md bg-stone-950 border border-stone-700
                             px-3 py-2 text-sm focus:border-amber-400 outline-none" />
              )}
            </>
          )}

          {(mode === "login" || mode === "register") && (
            <>
              <input value={username} onChange={(e) => setUsername(e.target.value)}
                placeholder="用户名（至少 3 字）" required minLength={3}
                className="w-full rounded-md bg-stone-950 border border-stone-700
                           px-3 py-2 text-sm focus:border-amber-400 outline-none" />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "register" ? `密码（至少 ${minPw} 位）` : "密码"}
                required minLength={mode === "register" ? minPw : 1}
                className="w-full rounded-md bg-stone-950 border border-stone-700
                           px-3 py-2 text-sm focus:border-amber-400 outline-none" />
            </>
          )}

          {(mode === "forgot" || (mode === "magic" && !token)) && (
            <input value={identity} onChange={(e) => setIdentity(e.target.value)}
              placeholder="用户名或邮箱" required
              className="w-full rounded-md bg-stone-950 border border-stone-700
                         px-3 py-2 text-sm focus:border-amber-400 outline-none" />
          )}

          {mode === "reset" && (
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder={`新密码（至少 ${minPw} 位）`}
              required minLength={minPw}
              className="w-full rounded-md bg-stone-950 border border-stone-700
                         px-3 py-2 text-sm focus:border-amber-400 outline-none" />
          )}

          {!(mode === "magic" && token) && !(mode === "verify") && (
            <button type="submit" disabled={loading || registerBlocked}
              className="w-full py-2.5 rounded-md bg-amber-500/90 text-stone-900
                         font-semibold disabled:opacity-40 hover:bg-amber-400">
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

        {err && <p className="text-rose-400 text-sm mt-3 whitespace-pre-wrap">{err}</p>}
        {info && <p className="text-emerald-400/90 text-sm mt-3 whitespace-pre-wrap break-all">{info}</p>}
        {mode === "register" && cfgErr && (
          <p className="text-rose-400 text-sm mt-3">{cfgErr}</p>
        )}
        {mode === "register" && inviteOnly && (
          <p className="text-[11px] opacity-45 mt-3">当前为邀测模式，注册需要有效注册码。</p>
        )}

        <div className="mt-5 flex flex-col gap-2 text-[12px] opacity-55">
          {mode === "login" && (
            <>
              <button type="button" className="text-left hover:text-amber-200"
                onClick={() => { setMode("forgot"); setErr(null); setInfo(null); }}>
                忘记密码？
              </button>
              <button type="button" className="text-left hover:text-amber-200"
                onClick={() => { setMode("magic"); setToken(""); setErr(null); setInfo(null); }}>
                使用魔法链接登录
              </button>
            </>
          )}
          {(mode === "forgot" || mode === "magic" || mode === "reset") && (
            <button type="button" className="text-left hover:text-amber-200"
              onClick={() => { setMode("login"); setErr(null); setInfo(null); }}>
              返回登录
            </button>
          )}
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen flex items-center justify-center opacity-60">加载中…</main>
    }>
      <LoginInner />
    </Suspense>
  );
}
