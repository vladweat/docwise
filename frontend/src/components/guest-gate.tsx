"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth-provider";

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
    return <p className="px-6 py-10 text-center text-sm text-slate-400">Загрузка…</p>;
  }
  if (isAuthenticated) {
    return <p className="px-6 py-10 text-center text-sm text-slate-400">Перенаправление…</p>;
  }
  return <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">{children}</div>;
}

export function GuestGate({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<p className="px-6 py-10 text-center text-sm text-slate-400">Загрузка…</p>}>
      <GuestRedirect>{children}</GuestRedirect>
    </Suspense>
  );
}
