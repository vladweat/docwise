import { describe, expect, it } from "vitest";

import { resolveHomeView } from "@/features/home/home-view";

describe("resolveHomeView", () => {
  it("renders the guest landing immediately when there is no session cookie", () => {
    expect(resolveHomeView({ isAuthenticated: false, loading: true, hasSessionCookie: false })).toBe("landing");
  });

  it("keeps the loading state while a cookie-backed session is being checked", () => {
    expect(resolveHomeView({ isAuthenticated: false, loading: true, hasSessionCookie: true })).toBe("loading");
  });

  it("shows chat for authenticated users", () => {
    expect(resolveHomeView({ isAuthenticated: true, loading: false, hasSessionCookie: true })).toBe("chat");
  });
});
