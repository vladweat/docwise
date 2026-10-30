import type { Metadata, Viewport } from "next";
import Script from "next/script";

import { AppHeader } from "@/components/app-header";
import { AuthProvider } from "@/features/auth/auth-provider";
import { LocaleProvider } from "@/i18n/locale-provider";
import { QueryProvider } from "@/components/query-provider";
import { ToastHost } from "@/components/toast-host";

import "./globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "DOCwise",
  description: "Permission-aware corporate document search and Q&A",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0a0f1a",
  interactiveWidget: "resizes-content",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const runtimeConfig = JSON.stringify({ apiBaseUrl: process.env.API_BASE_URL ?? "" }).replace(
    /</g,
    "\\u003c",
  );

  return (
    <html lang="ru">
      <head>
        <Script
          id="docwise-runtime-config"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: `window.__DOCWISE_RUNTIME_CONFIG__=${runtimeConfig};` }}
        />
      </head>
      <body className="flex h-dvh flex-col overflow-hidden">
        <QueryProvider>
          <LocaleProvider>
            <AuthProvider>
              <AppHeader />
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
              <ToastHost />
            </AuthProvider>
          </LocaleProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
