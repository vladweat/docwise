import { describe, expect, it } from "vitest";

import { canManageKnowledgeBase, canManageOrganization } from "@/lib/access-roles";
import type { UserResponse } from "@/types/auth";

function user(role: UserResponse["role"]): UserResponse {
  return {
    id: "1",
    email: `${role}@example.com`,
    role,
    departments: [],
    is_active: true,
    created_at: "2026-01-01T00:00:00",
    organization_id: "org",
    organization_name: "Acme",
    organizations: [],
  };
}

describe("role capabilities", () => {
  it("lets manager write the KB but not billing", () => {
    expect(canManageKnowledgeBase(user("manager"))).toBe(true);
    expect(canManageOrganization(user("manager"))).toBe(false);
    expect(canManageKnowledgeBase(user("employee"))).toBe(false);
    expect(canManageOrganization(user("admin"))).toBe(true);
  });
});
