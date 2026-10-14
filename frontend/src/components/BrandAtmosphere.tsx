"use client";

type Props = {
  /** Map art under the veil — defaults to ancient seed. */
  imageSrc?: string;
  reducedMotion?: boolean;
};

/** Full-bleed atmospheric plane for entry surfaces (login / home). */
export default function BrandAtmosphere({
  imageSrc = "/maps/ancient.png",
  reducedMotion = false,
}: Props) {
  return (
    <div className="brand-atmosphere pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <div
        className={`absolute inset-0 bg-cover bg-center ${reducedMotion ? "" : "brand-atmosphere-drift"}`}
        style={{
          backgroundImage: `linear-gradient(120deg, rgba(10,7,6,0.55), rgba(28,20,16,0.35)), url(${imageSrc})`,
        }}
      />
      <div className="absolute inset-0 brand-atmosphere-veil" />
      <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[var(--brand-bg-deep)] via-[var(--brand-bg-deep)]/80 to-transparent" />
    </div>
  );
}
