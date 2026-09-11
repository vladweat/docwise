import { describe, expect, it } from "vitest";

import { apiUrl, shouldRefreshOn401 } from "@/lib/api";

describe("apiUrl", () => {
  it("keeps the configured origin on localhost", () => {
    expect(apiUrl("localhost")).toBe("http://localhost:8001");
    expect(apiUrl("127.0.0.1")).toBe("http://localhost:8001");
  });

  it("rewrites hostname on a tenant host so host-only cookies stick", () => {
    expect(apiUrl("acme.localhost")).toBe("http://acme.localhost:8001");
    expect(apiUrl("kb.acme.example")).toBe("http://kb.acme.example:8001");
  });
});

describe("shouldRefreshOn401", () => {
  it("refreshes API calls and /auth/me, not login/refresh/SSO", () => {
    expect(shouldRefreshOn401("/auth/me")).toBe(true);
    expect(shouldRefreshOn401("/chat/sessions")).toBe(true);
    expect(shouldRefreshOn401("/auth/login")).toBe(false);
    expect(shouldRefreshOn401("/auth/refresh")).toBe(false);
    expect(shouldRefreshOn401("/auth/sso/acme/acs")).toBe(false);
  });
});
