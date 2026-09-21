import { describe, expect, it } from "vitest";

import { translate } from "@/i18n/messages";

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
});
