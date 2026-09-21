import {
  DEFAULT_LOCALE,
  translate,
  type Locale,
  type MessageKey,
} from "@/i18n/messages";

let clientLocale: Locale = DEFAULT_LOCALE;

export function setClientLocale(locale: Locale): void {
  clientLocale = locale;
}

export function getClientLocale(): Locale {
  return clientLocale;
}

export function formatMessage(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  let out = template;
  for (const [key, value] of Object.entries(params)) {
    out = out.replaceAll(`{${key}}`, String(value));
  }
  return out;
}

export function tClient(key: MessageKey, params?: Record<string, string | number>): string {
  return formatMessage(translate(clientLocale, key), params);
}
