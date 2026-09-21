"use client";

import { ChatWorkspace } from "@/features/chat/chat-workspace";
import { useAuth } from "@/features/auth/auth-provider";
import { WelcomePage } from "@/features/marketing/welcome-page";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/i18n/locale-provider";

function HomeLoading() {
  const { t } = useI18n();
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10">
      <Skeleton className="h-4 w-40" />
      <p className="text-sm text-slate-400">{t("gate.loading")}</p>
    </div>
  );
}

export function HomePage() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return <HomeLoading />;
  if (!isAuthenticated) return <WelcomePage />;
  return <ChatWorkspace />;
}
