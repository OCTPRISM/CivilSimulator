/** App error envelope from backend http_contract (§7.1). */

export type ErrorCategory =
  | "auth"
  | "authorization"
  | "validation"
  | "conflict"
  | "quota"
  | "dependency"
  | "realtime"
  | "persistence"
  | "simulation"
  | "internal"
  | string;

export type AppErrorBody = {
  code: string;
  category: ErrorCategory;
  message: string;
  retryable?: boolean;
  retry_after_ms?: number;
  details?: Record<string, unknown>;
  field_errors?: Record<string, string[]>;
};

export class AppError extends Error {
  readonly code: string;
  readonly category: ErrorCategory;
  readonly retryable: boolean;
  readonly retryAfterMs?: number;
  readonly requestId?: string;
  readonly status: number;
  readonly fieldErrors?: Record<string, string[]>;

  constructor(
    body: AppErrorBody,
    opts: { status: number; requestId?: string },
  ) {
    super(body.message || "请求失败");
    this.name = "AppError";
    this.code = body.code || "INTERNAL_ERROR";
    this.category = body.category || "internal";
    this.retryable = Boolean(body.retryable);
    this.retryAfterMs = body.retry_after_ms;
    this.requestId = opts.requestId;
    this.status = opts.status;
    this.fieldErrors = body.field_errors;
  }

  /** Short UI copy with category-aware hints. */
  displayMessage(): string {
    if (this.category === "quota") {
      if (this.code === "RATE_LIMITED") {
        return this.message || "请求过于频繁，请稍后再试";
      }
      return `${this.message}（配额类错误，请勿自动重试）`;
    }
    if (this.category === "dependency" && this.retryable) {
      return `${this.message}（可稍后重试）`;
    }
    if (this.category === "conflict" && this.retryable) {
      return `${this.message}（请刷新后重试）`;
    }
    return this.message;
  }
}

/** Same-origin relative path only — blocks open redirects. */
export function safeNextPath(raw: string | null | undefined, fallback = "/"): string {
  if (!raw) return fallback;
  const t = raw.trim();
  if (!t.startsWith("/") || t.startsWith("//")) return fallback;
  if (t.includes("://") || t.includes("\\")) return fallback;
  return t;
}

export function parseApiError(
  status: number,
  text: string,
  requestId?: string | null,
): AppError | Error {
  try {
    const j = JSON.parse(text) as {
      error?: AppErrorBody;
      detail?: unknown;
      message?: string;
    };
    if (j.error && typeof j.error === "object" && j.error.message) {
      return new AppError(j.error, {
        status,
        requestId: requestId || undefined,
      });
    }
    const d = j.detail;
    let msg: string;
    if (typeof d === "string") msg = d;
    else if (Array.isArray(d)) {
      msg = d.map((x: { msg?: string }) => x.msg).filter(Boolean).join("; ") || text;
    } else if (d && typeof d === "object" && "message" in (d as object)) {
      msg = String((d as { message: string }).message);
    } else {
      msg = j.message || text || "请求失败";
    }
    return new Error(String(msg).replace(/^Error:\s*/i, ""));
  } catch {
    return new Error(text || "请求失败");
  }
}
