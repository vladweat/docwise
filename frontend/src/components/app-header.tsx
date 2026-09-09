"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LogOut } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

export function AppHeader() {
  const { isAuthenticated, user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <header className="shrink-0 border-b border-slate-800 bg-slate-950/80 pt-[env(safe-area-inset-top)] backdrop-blur">
      <div className="mx-auto flex min-h-12 max-w-6xl items-center justify-between gap-2 px-3 py-2 sm:h-14 sm:gap-4 sm:px-6 sm:py-0">
        <div className="flex min-w-0 items-center gap-2 sm:gap-6">
          <Link href="/" className="block shrink-0">
            <h1 className="text-base font-bold tracking-tight sm:text-lg">Docwise</h1>
          </Link>
        </div>

        <div className="flex shrink-0 items-center gap-2 text-sm">
          {isAuthenticated && user ? (
            <>
              <span className="hidden max-w-[180px] truncate text-slate-400 md:inline">
                {user.email}
              </span>
              <Button type="button" variant="ghost" size="sm" onClick={logout} aria-label="Выйти">
                <LogOut className="sm:hidden" />
                <span className="hidden sm:inline">Выйти</span>
              </Button>
            </>
          ) : pathname !== "/login" ? (
            <Button asChild variant="outline" size="sm">
              <Link href="/login">Войти</Link>
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
