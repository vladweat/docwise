import type { DocumentResponse } from "@/types/document";

export function isDocxDocument(doc: Pick<DocumentResponse, "content_format" | "title">): boolean {
  return doc.content_format === "docx" || doc.title.toLowerCase().endsWith(".docx");
}
