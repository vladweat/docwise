"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/auth-provider";

function GateStatus({ label }: { label: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10">
      <Skeleton className="h-4 w-40" />
      <p className="text-sm text-slate-400">{label}</p>
    </div>
  );
}

export function AuthGate({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading || isAuthenticated) return;
    const next = pathname && pathname !== "/login" ? `?next=${encodeURIComponent(pathname)}` : "";
    router.replace(`/login${next}`);
  }, [isAuthenticated, loading, pathname, router]);

  if (loading) {
    return <GateStatus label="Загрузка…" />;
  }
  if (!isAuthenticated) {
    return <GateStatus label="Перенаправление на вход…" />;
  }
  return <div className="flex min-h-0 flex-1 flex-col">{children}</div>;
}
