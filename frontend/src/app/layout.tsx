import type { Metadata, Viewport } from "next";

import { AppHeader } from "@/components/app-header";
import { AuthProvider } from "@/components/auth-provider";
import { QueryProvider } from "@/components/query-provider";
import { ToastHost } from "@/components/toast-host";

import "./globals.css";

export const metadata: Metadata = {
  title: "Docwise",
  description: "Корпоративный поиск и Q&A по документам с учётом прав доступа",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0a0f1a",
  interactiveWidget: "resizes-content",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="flex h-dvh flex-col overflow-hidden">
        <QueryProvider>
          <AuthProvider>
            <AppHeader />
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
            <ToastHost />
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
