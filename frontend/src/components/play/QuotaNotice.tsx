"use client";

import type { AppError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";

/** Dedicated quota / rate-limit strip (architecture §7.1 UI strategy). */
export default function QuotaNotice({
  error,
  onDismiss,
}: {
  error: AppError;
  onDismiss?: () => void;
}) {
  const { t } = useI18n();
  const mins =
    error.retryAfterMs != null
      ? Math.max(1, Math.ceil(error.retryAfterMs / 60_000))
      : null;
  const resetHint =
    error.code === "RATE_LIMITED"
      ? mins
        ? t("quota.retryMins", { n: mins })
        : t("quota.retryLater")
      : mins
        ? t("quota.resetMins", { n: mins })
        : t("quota.resetWait");

  return (
    <div
      className="pointer-events-auto mx-3 mt-2 sm:mx-auto sm:max-w-xl
                 rounded-lg border border-amber-600/45 bg-amber-950/90 px-3 py-2
                 text-[12px] text-amber-50 flex gap-2 items-start shadow-lg"
      role="status"
    >
      <div className="flex-1 leading-relaxed min-w-0">
        <p className="font-medium text-amber-100/95">
          {error.code === "RATE_LIMITED" ? t("quota.rate") : t("quota.exhausted")}
        </p>
        <p className="mt-0.5 opacity-90">{error.message}</p>
        <p className="mt-1 text-[11px] opacity-70">
          {resetHint} · {t("quota.noAuto")}
        </p>
        {error.requestId && (
          <p className="mt-0.5 text-[10px] opacity-45 truncate">
            {t("quota.request", { id: error.requestId })}
          </p>
        )}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 opacity-70 hover:opacity-100 text-[11px]"
        >
          {t("common.close")}
        </button>
      )}
    </div>
  );
}
