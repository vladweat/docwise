import { describe, expect, it } from "vitest";

import {
  canManageKnowledgeBase,
  canManageOrganization,
  normalizeAccessRoles,
  toggleAccessRole,
} from "@/lib/access-roles";
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

describe("document audience selection", () => {
  it("makes organization-wide access exclusive", () => {
    expect(toggleAccessRole(["hr"], "all", true)).toEqual(["all"]);
    expect(toggleAccessRole(["all"], "finance", true)).toEqual(["finance"]);
  });

  it("allows multiple targeted roles or departments", () => {
    expect(toggleAccessRole(["hr"], "finance", true)).toEqual(["hr", "finance"]);
    expect(toggleAccessRole(["hr", "finance"], "hr", false)).toEqual(["finance"]);
  });

  it("normalizes legacy all plus restricted tags to all", () => {
    expect(normalizeAccessRoles(["hr", "all", "finance"])).toEqual(["all"]);
  });
});
