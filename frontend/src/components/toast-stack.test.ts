import { describe, expect, it } from "vitest";

import { scrollToLatestToastStack } from "@/components/toast-stack";

describe("scrollToLatestToastStack", () => {
  it("keeps the newest toast visible after the stack grows beyond its viewport", () => {
    const stack = { scrollHeight: 620, scrollTop: 0 };

    scrollToLatestToastStack(stack);

    expect(stack.scrollTop).toBe(620);
  });

  it("does nothing when the toast stack is not mounted", () => {
    expect(() => scrollToLatestToastStack(null)).not.toThrow();
  });
});
