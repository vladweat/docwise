import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchDocumentAccessOptions, patchDocumentAccess } from "@/lib/api/documents";

const apiFetch = vi.fn();

vi.mock("@/lib/api/client", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}));

describe("patchDocumentAccess", () => {
  beforeEach(() => {
    apiFetch.mockReset();
    apiFetch.mockResolvedValue({ id: "doc-1", access_roles: ["hr"] });
  });

  it("PATCHes access_roles JSON body", async () => {
    await patchDocumentAccess("doc-1", ["hr", "all"]);
    expect(apiFetch).toHaveBeenCalledWith("/documents/doc-1", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_roles: ["hr", "all"] }),
    });
  });
});

describe("fetchDocumentAccessOptions", () => {
  it("loads the roles and departments configured for the current organization", async () => {
    apiFetch.mockResolvedValue({ roles: ["admin", "employee", "manager"], departments: ["finance", "hr"] });
    await fetchDocumentAccessOptions();
    expect(apiFetch).toHaveBeenCalledWith("/documents/access-options");
  });
});
