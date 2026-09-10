export const ORGANIZATION_QUOTA_EXCEEDED = "Organization quota exceeded";
export const QUOTA_TOAST = "Квота организации исчерпана";

export function isQuotaExceeded(status?: number, message?: string): boolean {
  return status === 402 || message === ORGANIZATION_QUOTA_EXCEEDED;
}

export function userFacingApiMessage(status: number | undefined, message: string): string {
  if (isQuotaExceeded(status, message)) return QUOTA_TOAST;
  return message;
}
