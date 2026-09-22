import { describe, expect, it } from "vitest";

import { isDocxDocument } from "@/features/documents/document-format";

describe("isDocxDocument", () => {
  it("detects docx by content_format or file extension", () => {
    expect(isDocxDocument({ content_format: "docx", title: "Policy" })).toBe(true);
    expect(isDocxDocument({ content_format: "pdf", title: "Travel.docx" })).toBe(true);
    expect(isDocxDocument({ content_format: "pdf", title: "Handbook.pdf" })).toBe(false);
  });
});
