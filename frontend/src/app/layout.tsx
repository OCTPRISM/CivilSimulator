import type { Metadata } from "next";
import { Noto_Serif_SC } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const brandSerif = Noto_Serif_SC({
  weight: ["400", "600", "700"],
  subsets: ["latin"],
  variable: "--font-brand-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CivilSimulator",
  description: "活在小说里。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className={brandSerif.variable}>
      <body style={{ fontFamily: "var(--font-brand-serif), var(--brand-serif)" }}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
