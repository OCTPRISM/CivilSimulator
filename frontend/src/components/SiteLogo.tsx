import Link from "next/link";
import Image from "next/image";

type Props = {
  href?: string | null;
  compact?: boolean;
  /** Hero-scale mark + wordmark for entry first viewport. */
  hero?: boolean;
};

export default function SiteLogo({ href = "/", compact = false, hero = false }: Props) {
  const size = hero ? 72 : compact ? 36 : 44;
  const inner = (
    <div className={`flex items-center group ${hero ? "flex-col gap-4 text-center" : "gap-3"}`}>
      <Image
        src="/brand/logo-mark.svg"
        alt=""
        width={size}
        height={size}
        className={`shrink-0 opacity-95 group-hover:opacity-100 transition ${hero ? "drop-shadow-lg" : ""}`}
        priority={hero}
      />
      <div className={`leading-tight ${hero ? "" : ""}`}>
        <div
          className={`font-serif tracking-[0.18em] text-[var(--brand-ink)]
                      ${hero ? "text-3xl sm:text-5xl tracking-[0.22em]" : compact ? "text-lg" : "text-xl sm:text-2xl"}`}
        >
          CivilSimulator
        </div>
        {!compact && (
          <div
            className={`tracking-[0.35em] mt-1 text-[var(--brand-ink-muted)]
                        ${hero ? "text-[11px] sm:text-xs" : "text-[10px]"}`}
          >
            文明 · 实验 · 创造
          </div>
        )}
      </div>
    </div>
  );

  if (href === null) return inner;
  return (
    <Link href={href || "/"} className="hover:opacity-90 transition inline-flex">
      {inner}
    </Link>
  );
}
