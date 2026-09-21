import { tClient } from "@/i18n/client-translate";

export const ORGANIZATION_QUOTA_EXCEEDED = "Organization quota exceeded";
export const CHAT_PERSIST_FAILED = "Chat was not saved. Try again.";

export function isQuotaExceeded(status?: number, message?: string): boolean {
  return status === 402 || message === ORGANIZATION_QUOTA_EXCEEDED;
}

export function userFacingApiMessage(status: number | undefined, message: string): string {
  if (isQuotaExceeded(status, message)) return tClient("errors.quotaExceeded");
  if (message === CHAT_PERSIST_FAILED) return tClient("errors.chatPersistFailed");
  return message;
}
