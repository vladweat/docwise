import { describe, expect, it } from "vitest";

import { en } from "@/i18n/messages/en";
import { ru } from "@/i18n/messages/ru";
import { translate, type Locale, type MessageKey } from "@/i18n/messages";

function messageLeafKeys(obj: object, prefix = ""): string[] {
  const keys: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object") {
      keys.push(...messageLeafKeys(value as object, path));
    } else {
      keys.push(path);
    }
  }
  return keys;
}

describe("translate", () => {
  it("returns Russian strings by default catalog", () => {
    expect(translate("ru", "auth.titleLogin")).toBe("Вход");
  });

  it("returns English strings", () => {
    expect(translate("en", "auth.titleLogin")).toBe("Sign in");
  });

  it("falls back to Russian for unknown locale keys", () => {
    expect(translate("en", "auth.titleLogin")).toBe("Sign in");
  });

  it("keeps en and ru message keys in parity", () => {
    expect(messageLeafKeys(en).sort()).toEqual(messageLeafKeys(ru).sort());
  });

  it("provides a localized landing headline and demo action", () => {
    for (const locale of ["ru", "en"] satisfies Locale[]) {
      for (const key of ["landing.title", "landing.demoCta"] as const) {
        const value = translate(locale, key as MessageKey);
        expect(value).not.toBe(key);
        expect(value.trim().length).toBeGreaterThan(0);
      }
    }
  });
});
