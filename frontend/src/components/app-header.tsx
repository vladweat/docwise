"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LanguageSwitcher } from "@/components/language-switcher";
import { UserAccountMenu } from "@/components/user-account-menu";
import { useAuth } from "@/features/auth/auth-provider";
import { useI18n } from "@/i18n/locale-provider";
import type { MessageKey } from "@/i18n/messages";
import { Button } from "@/components/ui/button";
import { canManageOrganization } from "@/lib/access-roles";
import { cn } from "@/lib/utils";

const NAV: { href: string; labelKey: MessageKey; match: (path: string) => boolean; adminOnly?: boolean }[] = [
  { href: "/", labelKey: "nav.chat", match: (path: string) => path === "/" || path.startsWith("/chat") },
  { href: "/documents", labelKey: "nav.documents", match: (path: string) => path.startsWith("/documents") },
  { href: "/inspect", labelKey: "nav.inspect", match: (path: string) => path.startsWith("/inspect"), adminOnly: true },
  { href: "/settings", labelKey: "nav.settings", match: (path: string) => path.startsWith("/settings"), adminOnly: true },
];

function NavLinks({
  pathname,
  items,
  className,
}: {
  pathname: string;
  items: typeof NAV;
  className?: string;
}) {
  const { t } = useI18n();
  return (
    <nav className={className}>
      {items.map((item) => {
        const active = item.match(pathname);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "shrink-0 rounded-md px-2.5 py-1.5 text-sm whitespace-nowrap",
              active ? "text-slate-100" : "text-slate-400 hover:text-slate-200",
            )}
          >
            {t(item.labelKey)}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppHeader() {
  const { t } = useI18n();
  const { isAuthenticated, user } = useAuth();
  const pathname = usePathname();
  const canManageOrg = canManageOrganization(user);
  const navItems = NAV.filter((item) => !item.adminOnly || canManageOrg);

  return (
    <header className="shrink-0 border-b border-slate-800 bg-slate-950/80 pt-[env(safe-area-inset-top)] backdrop-blur">
      <div className="sm:flex sm:h-14 sm:items-center sm:justify-between sm:gap-4 sm:px-4">
        <div className="flex min-h-12 items-center justify-between gap-2 px-3 py-2 sm:min-h-0 sm:flex-1 sm:justify-start sm:gap-6 sm:px-0 sm:py-0">
          <Link href="/" className="block shrink-0">
            <h1 className="text-base font-bold tracking-tight sm:text-lg">Docwise</h1>
          </Link>

          {isAuthenticated ? (
            <NavLinks
              pathname={pathname}
              items={navItems}
              className="hidden items-center gap-0.5 sm:flex"
            />
          ) : null}

          <div className="flex shrink-0 items-center gap-2 text-sm">
            {isAuthenticated && user ? (
              <div className="sm:hidden">
                <UserAccountMenu />
              </div>
            ) : (
              <>
                <LanguageSwitcher compact />
                {pathname !== "/login" ? (
                  <Button asChild variant="outline" size="sm">
                    <Link href="/login">{t("nav.login")}</Link>
                  </Button>
                ) : null}
              </>
            )}
          </div>
        </div>

        {isAuthenticated ? (
          <NavLinks
            pathname={pathname}
            items={navItems}
            className="flex items-center gap-0.5 overflow-x-auto border-t border-slate-800/80 px-2 py-1.5 [-ms-overflow-style:none] [scrollbar-width:none] sm:hidden [&::-webkit-scrollbar]:hidden"
          />
        ) : null}

        {isAuthenticated && user ? (
          <div className="hidden shrink-0 sm:flex sm:pr-0">
            <UserAccountMenu />
          </div>
        ) : null}
      </div>
    </header>
  );
}
