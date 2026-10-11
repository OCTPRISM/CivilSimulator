"use client";

import type { AppError } from "@/lib/errors";

/** Dedicated quota / rate-limit strip (architecture §7.1 UI strategy). */
export default function QuotaNotice({
  error,
  onDismiss,
}: {
  error: AppError;
  onDismiss?: () => void;
}) {
  const mins =
    error.retryAfterMs != null
      ? Math.max(1, Math.ceil(error.retryAfterMs / 60_000))
      : null;
  const resetHint =
    error.code === "RATE_LIMITED"
      ? mins
        ? `请约 ${mins} 分钟后再试`
        : "请稍后再试"
      : mins
        ? `配额约 ${mins} 分钟后重置`
        : "请待配额重置后再试";

  return (
    <div
      className="pointer-events-auto mx-3 mt-2 sm:mx-auto sm:max-w-xl
                 rounded-lg border border-amber-600/45 bg-amber-950/90 px-3 py-2
                 text-[12px] text-amber-50 flex gap-2 items-start shadow-lg"
      role="status"
    >
      <div className="flex-1 leading-relaxed min-w-0">
        <p className="font-medium text-amber-100/95">
          {error.code === "RATE_LIMITED" ? "请求过于频繁" : "LLM 配额已用尽"}
        </p>
        <p className="mt-0.5 opacity-90">{error.message}</p>
        <p className="mt-1 text-[11px] opacity-70">
          {resetHint} · 请勿自动重试
        </p>
        {error.requestId && (
          <p className="mt-0.5 text-[10px] opacity-45 truncate">
            请求 {error.requestId}
          </p>
        )}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 opacity-70 hover:opacity-100 text-[11px]"
        >
          关闭
        </button>
      )}
    </div>
  );
}
