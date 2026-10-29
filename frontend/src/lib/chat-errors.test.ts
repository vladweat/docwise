import { describe, expect, it } from "vitest";

import { getClientLocale, setClientLocale } from "@/i18n/client-translate";
import { translate } from "@/i18n/messages";
import { userFacingChatError } from "@/lib/chat-errors";

describe("userFacingChatError", () => {
  it("maps missing OpenAI key to localized message", () => {
    expect(userFacingChatError(503, "OPENAI_API_KEY is not configured")).toBe(
      translate("ru", "errors.llmNotConfigured"),
    );
  });

  it("appends dev hint when requested", () => {
    const message = userFacingChatError(503, "OPENAI_API_KEY is not configured", {
      showDevLlmHint: true,
    });
    expect(message).toContain(translate("ru", "errors.llmNotConfigured"));
    expect(message).toContain(translate("ru", "errors.llmNotConfiguredDev"));
  });

  it("localizes a busy chat session in Russian and English", () => {
    const previousLocale = getClientLocale();
    try {
      setClientLocale("ru");
      expect(userFacingChatError(409, "generic conflict")).toBe(
        "В этом чате уже формируется ответ. Попробуйте немного позже.",
      );

      setClientLocale("en");
      expect(userFacingChatError(409, "generic conflict")).toBe(
        "A reply is already being generated for this chat. Please try again shortly.",
      );
    } finally {
      setClientLocale(previousLocale);
    }
  });
});
