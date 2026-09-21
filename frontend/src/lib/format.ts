import { getClientLocale } from "@/i18n/client-translate";

function dateLocale(): string {
  return getClientLocale() === "ru" ? "ru-RU" : "en-US";
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(dateLocale(), { dateStyle: "short", timeStyle: "short" });
}

export function formatBytes(bytes: number): string {
  const locale = dateLocale();
  if (bytes < 1024) {
    return new Intl.NumberFormat(locale, {
      style: "unit",
      unit: "byte",
      unitDisplay: "short",
      maximumFractionDigits: 0,
    }).format(bytes);
  }
  const kb = bytes / 1024;
  if (kb < 1024) {
    return new Intl.NumberFormat(locale, {
      style: "unit",
      unit: "kilobyte",
      unitDisplay: "short",
      maximumFractionDigits: kb < 10 ? 1 : 0,
    }).format(kb);
  }
  const mb = kb / 1024;
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: "megabyte",
    unitDisplay: "short",
    maximumFractionDigits: mb < 10 ? 1 : 0,
  }).format(mb);
}
