import type { MessageKey } from "@/i18n/messages";
import type { UserResponse } from "@/types/auth";

export const DEMO_QUESTION_HOURS = "What are the core working hours at Docwise?";
export const DEMO_QUESTION_VACATION = "How many paid vacation days do employees get per year?";
export const DEMO_QUESTION_SALARY = "What is the individual contributor L3 salary band in USD?";

const SUGGESTION_HOURS: MessageKey = "chat.suggestionHours";
const SUGGESTION_VACATION: MessageKey = "chat.suggestionVacation";
const SUGGESTION_SALARY: MessageKey = "chat.suggestionSalary";

export function chatSuggestionKeysFor(user: UserResponse | null): MessageKey[] {
  const hasHr = Boolean(user?.departments?.includes("hr"));
  if (hasHr) {
    return [SUGGESTION_SALARY, SUGGESTION_HOURS, SUGGESTION_VACATION];
  }
  return [SUGGESTION_HOURS, SUGGESTION_VACATION, SUGGESTION_SALARY];
}

/** @deprecated use chatSuggestionKeysFor with i18n */
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
