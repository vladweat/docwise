import { describe, expect, it } from "vitest";

import { consumeSseBuffer, parseSseBlock } from "@/lib/sse";
import type { ChatStreamEvent } from "@/types/chat";

describe("parseSseBlock", () => {
  it("parses citations before tokens", () => {
    const citations = parseSseBlock(
      'data: {"type":"citations","citations":[{"doc_id":"11111111-1111-1111-1111-111111111111","doc_title":"Policy.pdf","page":2,"snippet":"cap"}]}\n',
    );
    expect(citations?.type).toBe("citations");
    if (citations?.type === "citations") {
      expect(citations.citations[0]?.page).toBe(2);
    }
    expect(parseSseBlock('data: {"type":"token","content":"Hello"}\n')?.type).toBe("token");
    expect(parseSseBlock("data: [DONE]\n")).toEqual({ type: "done" });
  });

  it("ignores malformed JSON", () => {
    expect(parseSseBlock("data: {not-json}\n")).toBeNull();
    expect(parseSseBlock("event: ping\n")).toBeNull();
  });
});

describe("consumeSseBuffer", () => {
  it("keeps a partial trailing frame", () => {
    const events: ChatStreamEvent[] = [];
    const rest = consumeSseBuffer(
      'data: {"type":"token","content":"a"}\n\ndata: {"type":"token","content":"b"}',
      (event) => events.push(event),
    );
    expect(events).toHaveLength(1);
    expect(rest).toBe('data: {"type":"token","content":"b"}');
  });
});
