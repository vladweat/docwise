import type { MessageKey } from "@/i18n/messages";
import type { UserResponse } from "@/types/auth";

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

export function isDemoOrganization(user: UserResponse | null): boolean {
  return user?.organization_name === "Demo";
}
