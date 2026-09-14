import { describe, expect, it } from "vitest";

import { DEMO_ACCOUNTS, DEMO_EMPLOYEE_EMAIL, DEMO_HR_EMAIL } from "@/features/auth/demo-accounts";
import {
  DEMO_QUESTION_HOURS,
  DEMO_QUESTION_SALARY,
  chatSuggestionsFor,
  isDemoOrganization,
} from "@/features/chat/lib/chat-suggestions";
import type { UserResponse } from "@/types/auth";

function user(partial: Partial<UserResponse>): UserResponse {
  return {
    id: "u1",
    email: "x@example.com",
    role: "employee",
    departments: [],
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    organization_id: "o1",
    organization_name: "Demo",
    organizations: [],
    ...partial,
  };
}

describe("demo accounts", () => {
  it("keeps employee and HR as separate logins", () => {
    expect(DEMO_ACCOUNTS.map((item) => item.email)).toEqual([
      DEMO_EMPLOYEE_EMAIL,
      DEMO_HR_EMAIL,
      "admin@docwise.example.com",
    ]);
  });
});

describe("chatSuggestionsFor", () => {
  it("puts the salary question last for an employee so they can trigger a refuse", () => {
    const items = chatSuggestionsFor(user({ departments: [] }));
    expect(items[0]).toBe(DEMO_QUESTION_HOURS);
    expect(items).toContain(DEMO_QUESTION_SALARY);
    expect(items.at(-1)).toBe(DEMO_QUESTION_SALARY);
  });

  it("leads with salary for HR", () => {
    const items = chatSuggestionsFor(user({ departments: ["hr"] }));
    expect(items[0]).toBe(DEMO_QUESTION_SALARY);
  });
});

describe("isDemoOrganization", () => {
  it("matches the seeded org name", () => {
    expect(isDemoOrganization(user({ organization_name: "Demo" }))).toBe(true);
    expect(isDemoOrganization(user({ organization_name: "Acme" }))).toBe(false);
  });
});
