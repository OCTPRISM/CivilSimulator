"use client";

import type { AppError } from "@/lib/errors";

/** Dependency outage strip (Ollama / Redis / quota backend, etc.). */
export default function DependencyStatus({
  error,
  onRetry,
  onDismiss,
}: {
  error: AppError;
  onRetry?: () => void;
  onDismiss?: () => void;
}) {
  const label =
    error.code === "LLM_UNAVAILABLE"
      ? "叙事服务暂不可用"
      : error.code === "QUOTA_BACKEND_UNAVAILABLE"
        ? "配额后端暂不可用"
        : "依赖服务异常";

  return (
    <div
      className="pointer-events-auto mx-3 mt-2 sm:mx-auto sm:max-w-xl
                 rounded-lg border border-sky-700/45 bg-sky-950/90 px-3 py-2
                 text-[12px] text-sky-50 flex gap-2 items-start shadow-lg"
      role="alert"
    >
      <div className="flex-1 leading-relaxed min-w-0">
        <p className="font-medium text-sky-100/95">{label}</p>
        <p className="mt-0.5 opacity-90">{error.message}</p>
        {error.retryable && (
          <p className="mt-1 text-[11px] opacity-70">可稍后重试，当前世界状态已保留</p>
        )}
        {error.requestId && (
          <p className="mt-0.5 text-[10px] opacity-45 truncate">
            请求 {error.requestId}
          </p>
        )}
      </div>
      <div className="shrink-0 flex flex-col gap-1 items-end">
        {error.retryable && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="px-2.5 py-1 rounded border border-sky-500/55
                       bg-sky-900/40 hover:bg-sky-800/50 text-[11px]"
          >
            重试
          </button>
        )}
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="opacity-70 hover:opacity-100 text-[11px]"
          >
            关闭
          </button>
        )}
      </div>
    </div>
  );
}
