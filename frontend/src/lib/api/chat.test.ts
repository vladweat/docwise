import { afterEach, describe, expect, it, vi } from "vitest";

import { streamChat } from "@/lib/api/chat";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamChat", () => {
  it("rejects a stream that closes before a completion event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('data: {"type":"token","content":"Partial answer"}\n\n', {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        }),
      ),
    );

    await expect(streamChat("Question", () => undefined)).rejects.toThrow(
      "Chat stream ended before completion",
    );
  });
});
