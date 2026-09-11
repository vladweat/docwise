"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LogOut } from "lucide-react";

import { useAuth } from "@/features/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { canManageOrganization } from "@/lib/access-roles";
import { ApiRequestError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useToastStore } from "@/stores/toast-store";

const NAV: { href: string; label: string; match: (path: string) => boolean; adminOnly?: boolean }[] = [
  { href: "/", label: "Чат", match: (path: string) => path === "/" || path.startsWith("/chat") },
  { href: "/documents", label: "Документы", match: (path: string) => path.startsWith("/documents") },
  { href: "/settings", label: "Настройки", match: (path: string) => path.startsWith("/settings"), adminOnly: true },
];

export function AppHeader() {
  const { isAuthenticated, user, logout, switchOrganization } = useAuth();
  const pathname = usePathname();
  const orgs = user?.organizations ?? [];
  const canManageOrg = canManageOrganization(user);
  const navItems = NAV.filter((item) => !item.adminOnly || canManageOrg);
  const pushToast = useToastStore((state) => state.push);

  return (
    <header className="shrink-0 border-b border-slate-800 bg-slate-950/80 pt-[env(safe-area-inset-top)] backdrop-blur">
      <div className="flex min-h-12 items-center justify-between gap-2 px-3 py-2 sm:h-14 sm:gap-4 sm:px-4 sm:py-0">
        <div className="flex min-w-0 items-center gap-3 sm:gap-6">
          <Link href="/" className="block shrink-0">
            <h1 className="text-base font-bold tracking-tight sm:text-lg">Docwise</h1>
          </Link>
          {isAuthenticated ? (
            <nav className="flex items-center gap-1">
              {navItems.map((item) => {
                const active = item.match(pathname);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "rounded-md px-2 py-1 text-sm",
                      active ? "text-slate-100" : "text-slate-400 hover:text-slate-200",
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          ) : null}
        </div>

        <div className="flex min-w-0 shrink-0 items-center gap-2 text-sm">
          {isAuthenticated && user ? (
            <>
              {orgs.length > 1 ? (
                <div className="hidden min-w-0 md:block">
                  <span className="sr-only">Организация</span>
                  <Select
                    value={user.organization_id}
                    onValueChange={(organizationId) => {
                      void switchOrganization(organizationId).catch((err: unknown) => {
                        const message =
                          err instanceof ApiRequestError ? err.message : "Не удалось сменить организацию";
                        pushToast(message, "error");
                      });
                    }}
                  >
                    <SelectTrigger size="sm" className="max-w-[160px] bg-slate-900" aria-label="Организация">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {orgs.map((org) => (
                        <SelectItem key={org.id} value={org.id}>
                          {org.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ) : (
                <span className="hidden max-w-[140px] truncate text-slate-300 md:inline">
                  {user.organization_name}
                </span>
              )}
              <span className="hidden max-w-[180px] truncate text-slate-400 lg:inline">
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
