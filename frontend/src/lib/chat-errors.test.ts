import { describe, expect, it } from "vitest";

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
});
