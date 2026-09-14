import { describe, expect, it } from "vitest";

import { inspectErrorMessage } from "@/features/inspect/inspect-error";
import { ApiRequestError } from "@/lib/api";

describe("inspect error copy", () => {
  it("does not advertise the pipeline when the flag is off", () => {
    expect(inspectErrorMessage(new ApiRequestError("Not Found", 404))).toContain("выключена");
  });

  it("does not explain a missing document on 403", () => {
    expect(inspectErrorMessage(new ApiRequestError("Admin access required", 403))).toBe(
      "Недостаточно прав.",
    );
  });
});
