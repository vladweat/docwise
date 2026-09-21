import { describe, expect, it } from "vitest";

import { translate } from "@/i18n/messages";
import { isQuotaExceeded, userFacingApiMessage, CHAT_PERSIST_FAILED } from "@/lib/quota";

describe("quota toast", () => {
  it("maps 402 and the English detail to the localized toast", () => {
    expect(isQuotaExceeded(402, "nope")).toBe(true);
    expect(isQuotaExceeded(200, "Organization quota exceeded")).toBe(true);
    expect(userFacingApiMessage(402, "Organization quota exceeded")).toBe(
      translate("ru", "errors.quotaExceeded"),
    );
    expect(userFacingApiMessage(400, "Only PDF files are supported")).toBe("Only PDF files are supported");
    expect(userFacingApiMessage(undefined, CHAT_PERSIST_FAILED)).toBe(
      translate("ru", "errors.chatPersistFailed"),
    );
  });
});
