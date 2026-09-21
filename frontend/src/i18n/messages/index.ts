import { en } from "@/i18n/messages/en";
import { ru } from "@/i18n/messages/ru";

export type Locale = "ru" | "en";

export const DEFAULT_LOCALE: Locale = "ru";
export const LOCALES: Locale[] = ["ru", "en"];
export const LOCALE_STORAGE_KEY = "dw_locale";

export type Messages = typeof ru;

type StringTree<T> = {
  [K in keyof T]: T[K] extends object ? StringTree<T[K]> : string;
};

type MessageCatalog = StringTree<Messages>;

type Join<K extends string, P extends string> = `${K}.${P}`;

type NestedKeyOf<ObjectType extends object> = {
  [Key in keyof ObjectType & string]: ObjectType[Key] extends object
    ? Join<Key, NestedKeyOf<ObjectType[Key]>>
    : Key;
}[keyof ObjectType & string];

export type MessageKey = NestedKeyOf<Messages>;

const catalogs: Record<Locale, MessageCatalog> = { ru, en };

function resolveMessage(messages: MessageCatalog, key: string): string | undefined {
  const parts = key.split(".");
  let current: unknown = messages;
  for (const part of parts) {
    if (current === null || typeof current !== "object" || !(part in current)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === "string" ? current : undefined;
}

export function translate(locale: Locale, key: MessageKey): string {
  return resolveMessage(catalogs[locale], key) ?? resolveMessage(catalogs.ru, key) ?? key;
}

export function detectBrowserLocale(): Locale {
  if (typeof navigator === "undefined") return DEFAULT_LOCALE;
  const lang = navigator.language.toLowerCase();
  if (lang.startsWith("en")) return "en";
  return DEFAULT_LOCALE;
}

export function readStoredLocale(): Locale | null {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return stored === "ru" || stored === "en" ? stored : null;
}
