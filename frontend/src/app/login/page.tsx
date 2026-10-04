"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login, register, user, loading: authLoading } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (authLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center opacity-60">
        正在验证登录…
      </main>
    );
  }

  if (user) {
    router.replace("/");
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await register(username, password, displayName);
      }
      router.replace("/");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-10">
      <h1 className="font-serif text-4xl tracking-widest mb-2">文明模拟器</h1>
      <p className="opacity-60 mb-8 text-sm">注册或登录后，方可踏入文明世界</p>

      <div className="w-full max-w-sm rounded-xl border border-stone-700 bg-stone-900/50 p-6">
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

        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              placeholder="显示名（可选）"
              className="w-full rounded-md bg-stone-950 border border-stone-700
                         px-3 py-2 text-sm focus:border-amber-400 outline-none" />
          )}
          <input value={username} onChange={(e) => setUsername(e.target.value)}
            placeholder="用户名（至少 3 字）" required minLength={3}
            className="w-full rounded-md bg-stone-950 border border-stone-700
                       px-3 py-2 text-sm focus:border-amber-400 outline-none" />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="密码（至少 6 位）" required minLength={6}
            className="w-full rounded-md bg-stone-950 border border-stone-700
                       px-3 py-2 text-sm focus:border-amber-400 outline-none" />
          <button type="submit" disabled={loading}
            className="w-full py-2.5 rounded-md bg-amber-500/90 text-stone-900
                       font-semibold disabled:opacity-40 hover:bg-amber-400">
            {loading ? "请稍候…" : mode === "login" ? "登录" : "注册并登录"}
          </button>
        </form>
        {err && <p className="text-rose-400 text-sm mt-3">{err}</p>}
      </div>
    </main>
  );
}
