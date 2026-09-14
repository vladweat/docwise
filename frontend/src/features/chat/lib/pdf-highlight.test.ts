import { describe, expect, it } from "vitest";

import { findSnippetRects } from "@/features/chat/lib/pdf-highlight";

describe("findSnippetRects", () => {
  it("maps a snippet onto viewport rectangles", () => {
    const items = [
      { str: "Core working hours at Docwise", transform: [1, 0, 0, 1, 72, 400], width: 180, height: 12 },
      { str: "are 09:00 to 18:00", transform: [1, 0, 0, 1, 72, 380], width: 120, height: 12 },
    ];
    const rects = findSnippetRects(items, (rect) => rect, "Core working hours at Docwise are 09:00 to 18:00");
    expect(rects.length).toBeGreaterThan(0);
    expect(rects[0]?.width).toBeGreaterThan(1);
  });

  it("returns empty when the snippet is too short", () => {
    expect(findSnippetRects([], (rect) => rect, "ab")).toEqual([]);
  });
});
