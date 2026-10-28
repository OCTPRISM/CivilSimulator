import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import LanguageSwitch from "@/components/LanguageSwitch";

export const metadata: Metadata = {
  title: "CivilSimulator",
  description: "活在小说里。Live inside the novel.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Do not use next/font/google here: first compile downloads Noto Serif SC
  // from fonts.googleapis.com and can hang `next dev` for minutes when the
  // network is slow or blocked (AbortError × retries). CSS already stacks
  // Noto Serif SC / Songti SC / Source Han Serif.
  return (
    <html lang="zh-CN">
      <body>
        <I18nProvider>
          <AuthProvider>
            {children}
            <LanguageSwitch dock />
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
