import Link from "next/link";
import Image from "next/image";

type Props = { href?: string; compact?: boolean };

export default function SiteLogo({ href = "/", compact = false }: Props) {
  const inner = (
    <div className="flex items-center gap-3 group">
      <Image
        src="/brand/logo-mark.svg"
        alt=""
        width={compact ? 36 : 44}
        height={compact ? 36 : 44}
        className="shrink-0 opacity-95 group-hover:opacity-100 transition"
      />
      <div className="leading-tight">
        <div className={`font-serif tracking-[0.18em] ${compact ? "text-lg" : "text-xl sm:text-2xl"}`}>
          CivilSimulator
        </div>
        {!compact && (
          <div className="text-[10px] opacity-45 tracking-[0.35em] mt-0.5">文明 · 实验 · 创造</div>
        )}
      </div>
    </div>
  );
  return href ? (
    <Link href={href} className="hover:opacity-90 transition">
      {inner}
    </Link>
  ) : inner;
}
