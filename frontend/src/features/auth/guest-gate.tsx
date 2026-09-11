"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, type ReactNode } from "react";

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

function postLoginPath(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/login")) {
    return "/";
  }
  // Chat session ids belong to one user; do not restore another account's thread.
  if (next.startsWith("/chat/")) return "/";
  return next;
}

function GuestRedirect({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (loading || !isAuthenticated) return;
    router.replace(postLoginPath(searchParams.get("next")));
  }, [isAuthenticated, loading, router, searchParams]);

  if (loading) {
    return <GateStatus label="Загрузка…" />;
  }
  if (isAuthenticated) {
    return <GateStatus label="Перенаправление…" />;
  }
  return <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">{children}</div>;
}

export function GuestGate({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<GateStatus label="Загрузка…" />}>
      <GuestRedirect>{children}</GuestRedirect>
    </Suspense>
  );
}
