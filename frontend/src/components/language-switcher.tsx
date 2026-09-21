"use client";

import { useI18n } from "@/i18n/locale-provider";
import { LOCALES, type Locale } from "@/i18n/messages";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export function LanguageSwitcher({
  className,
  compact = false,
}: {
  className?: string;
  compact?: boolean;
}) {
  const { locale, setLocale, t } = useI18n();

  if (compact) {
    return (
      <div
        className={cn("inline-flex rounded-md border border-slate-800 bg-slate-900/80 p-0.5", className)}
        role="group"
        aria-label={t("language.label")}
      >
        {LOCALES.map((item) => (
          <button
            key={item}
            type="button"
            className={cn(
              "min-w-[2.25rem] rounded px-2 py-1 text-xs font-medium uppercase tracking-wide transition-colors",
              locale === item ? "bg-slate-700 text-slate-100" : "text-slate-500 hover:text-slate-300",
            )}
            aria-pressed={locale === item}
            onClick={() => setLocale(item)}
          >
            {item}
          </button>
        ))}
      </div>
    );
  }

  return (
    <Select value={locale} onValueChange={(value) => setLocale(value as Locale)}>
      <SelectTrigger size="sm" className={className ?? "w-[112px] bg-slate-900"} aria-label={t("language.label")}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {LOCALES.map((item) => (
          <SelectItem key={item} value={item}>
            {t(item === "ru" ? "language.ru" : "language.en")}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
