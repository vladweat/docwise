import { tClient } from "@/i18n/client-translate";

import { userFacingApiMessage } from "@/lib/quota";

const LLM_NOT_CONFIGURED_MARKERS = ["OPENAI_API_KEY is not configured", "OPENAI_API_KEY"];

export function isLlmNotConfiguredMessage(message: string): boolean {
  return LLM_NOT_CONFIGURED_MARKERS.some((marker) => message.includes(marker));
}

export function userFacingChatError(
  status: number | undefined,
  message: string,
  options?: { showDevLlmHint?: boolean },
): string {
  if (isLlmNotConfiguredMessage(message)) {
    const base = tClient("errors.llmNotConfigured");
    if (options?.showDevLlmHint) {
      return `${base} ${tClient("errors.llmNotConfiguredDev")}`;
    }
    return base;
  }
  return userFacingApiMessage(status, message);
}
