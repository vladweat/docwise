import type { UserResponse } from "@/types/auth";

export const DEMO_QUESTION_HOURS = "What are the core working hours at Docwise?";
export const DEMO_QUESTION_VACATION = "How many paid vacation days do employees get per year?";
export const DEMO_QUESTION_SALARY = "What is the individual contributor L3 salary band in USD?";

export function chatSuggestionsFor(user: UserResponse | null): string[] {
  const hasHr = Boolean(user?.departments?.includes("hr"));
  if (hasHr) {
    return [DEMO_QUESTION_SALARY, DEMO_QUESTION_HOURS, DEMO_QUESTION_VACATION];
  }
  return [DEMO_QUESTION_HOURS, DEMO_QUESTION_VACATION, DEMO_QUESTION_SALARY];
}

export function isDemoOrganization(user: UserResponse | null): boolean {
  return user?.organization_name === "Demo";
}
