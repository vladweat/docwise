import { describe, expect, it } from "vitest";

import {
  citationLabel,
  resolveCitation,
  splitAnswerParts,
  stripCitationMarkers,
} from "@/features/chat/lib/chat";
import type { Citation } from "@/types/chat";

const CITATION: Citation = {
  doc_id: "11111111-1111-1111-1111-111111111111",
  doc_title: "Policy.pdf",
  page: 2,
  snippet: "travel cap",
};

describe("splitAnswerParts", () => {
  it("turns English and Russian citation markers into tags", () => {
    const english = splitAnswerParts("Cap is 150 [Policy.pdf, p. 2].", [CITATION]);
    expect(english).toEqual([
      { type: "text", value: "Cap is 150 " },
      { type: "citation", citation: CITATION, label: "Policy.pdf (стр. 2)" },
      { type: "text", value: "." },
    ]);
    const russian = splitAnswerParts("Лимит [Policy.pdf, стр. 2].", [CITATION]);
    expect(russian.some((part) => part.type === "citation")).toBe(true);
  });

  it("keeps markdown lists as text for the markdown renderer", () => {
    const parts = splitAnswerParts("- item one\n- item two", []);
    expect(parts).toEqual([{ type: "text", value: "- item one\n- item two" }]);
  });
});

describe("citationLabel", () => {
  it("uses стр. for the chip", () => {
    expect(citationLabel(CITATION)).toBe("Policy.pdf (стр. 2)");
  });
});

describe("resolveCitation", () => {
  it("matches title and page", () => {
    expect(resolveCitation([CITATION], "policy.pdf", 2)).toEqual(CITATION);
  });
});

describe("stripCitationMarkers", () => {
  it("removes inline markers without leaving broken spacing", () => {
    expect(stripCitationMarkers("Cap is 150 [Policy.pdf, p. 2].")).toBe("Cap is 150.");
    expect(stripCitationMarkers("Лимит [Policy.pdf, стр. 2] !")).toBe("Лимит!");
  });
});
