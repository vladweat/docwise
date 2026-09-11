import { describe, expect, it } from "vitest";

import { isQuotaExceeded, QUOTA_TOAST, userFacingApiMessage, CHAT_PERSIST_TOAST } from "@/lib/quota";

describe("quota toast", () => {
  it("maps 402 and the English detail to the Russian toast", () => {
    expect(isQuotaExceeded(402, "nope")).toBe(true);
    expect(isQuotaExceeded(200, "Organization quota exceeded")).toBe(true);
    expect(userFacingApiMessage(402, "Organization quota exceeded")).toBe(QUOTA_TOAST);
    expect(userFacingApiMessage(400, "Only PDF files are supported")).toBe("Only PDF files are supported");
    expect(userFacingApiMessage(undefined, "Chat was not saved. Try again.")).toBe(CHAT_PERSIST_TOAST);
  });
});
