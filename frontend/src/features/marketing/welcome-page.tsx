"use client";

import Link from "next/link";
import { FileSearch, Lock, Quote } from "lucide-react";

import { showDemoLogins } from "@/features/auth/demo-accounts";
import { useI18n } from "@/i18n/locale-provider";
import { Button } from "@/components/ui/button";

const BULLETS = [
  { key: "welcome.bulletAcl" as const, icon: Lock },
  { key: "welcome.bulletHybrid" as const, icon: FileSearch },
  { key: "welcome.bulletCitations" as const, icon: Quote },
] as const;

export function WelcomePage() {
  const { t } = useI18n();
  const demoAvailable = showDemoLogins();

  return (
    <main className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-10 sm:px-6">
      <div className="mx-auto flex w-full max-w-lg flex-col items-center gap-8 text-center">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("welcome.title")}</h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">{t("welcome.subtitle")}</p>
        </div>

        <ul className="w-full space-y-4 text-left">
          {BULLETS.map(({ key, icon: Icon }) => (
            <li key={key} className="flex gap-3 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
              <Icon className="mt-0.5 size-5 shrink-0 text-blue-400" aria-hidden />
              <p className="text-sm text-slate-300">{t(key)}</p>
            </li>
          ))}
        </ul>

        <div className="flex w-full flex-col gap-2 sm:flex-row sm:justify-center">
          <Button asChild size="lg" className="w-full sm:w-auto">
            <Link href="/login">{t("welcome.signIn")}</Link>
          </Button>
          {demoAvailable ? (
            <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
              <Link href="/login">{t("welcome.tryDemo")}</Link>
            </Button>
          ) : null}
        </div>
      </div>
    </main>
  );
}
