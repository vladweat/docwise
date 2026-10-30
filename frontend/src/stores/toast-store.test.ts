import { afterEach, describe, expect, it, vi } from "vitest";

import { useToastStore } from "@/stores/toast-store";

describe("toast store", () => {
  afterEach(() => {
    for (const toast of useToastStore.getState().toasts) {
      useToastStore.getState().dismiss(toast.id);
    }
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("coalesces duplicate messages with the same severity", () => {
    vi.useFakeTimers();
    vi.stubGlobal("window", globalThis);

    useToastStore.getState().push("Could not save", "error");
    useToastStore.getState().push("Could not save", "error");

    expect(useToastStore.getState().toasts).toHaveLength(1);
  });

  it("keeps only the three newest visible notices", () => {
    vi.useFakeTimers();
    vi.stubGlobal("window", globalThis);

    useToastStore.getState().push("First", "info");
    useToastStore.getState().push("Second", "info");
    useToastStore.getState().push("Third", "info");
    useToastStore.getState().push("Fourth", "info");

    expect(useToastStore.getState().toasts.map((toast) => toast.message)).toEqual([
      "Second",
      "Third",
      "Fourth",
    ]);
  });
});
