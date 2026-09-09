import type { Citation } from "@/types/chat";

/** Keep in sync with backend `NO_CONTEXT_ANSWER` in `retrieval.py`. */
export const NO_CONTEXT_ANSWER =
  "В предоставленных документах нет информации по данному вопросу.";

export function citationLabel(citation: Pick<Citation, "doc_title" | "page">): string {
  const title = citation.doc_title.trim() || "Документ";
  return `${title} (стр. ${citation.page})`;
}

export type AnswerPart =
  | { type: "text"; value: string }
  | { type: "citation"; citation: Citation; label: string };

function normalizeTitle(value: string): string {
  return value.trim().toLowerCase();
}

export function resolveCitation(
  citations: Citation[],
  title: string,
  page: number,
): Citation | undefined {
  const needle = normalizeTitle(title);
  return (
    citations.find(
      (item) => item.page === page && normalizeTitle(item.doc_title) === needle,
    ) ?? citations.find((item) => item.page === page)
  );
}

const INLINE_CITE_RE = /\[([^\]\n]+?),\s*(?:p\.|стр\.?)\s*(\d+)\]|\[\^(\d+)\]/gi;

export function splitAnswerParts(content: string, citations: Citation[]): AnswerPart[] {
  if (!content) return [];
  const parts: AnswerPart[] = [];
  let last = 0;
  const pattern = new RegExp(INLINE_CITE_RE.source, INLINE_CITE_RE.flags);
  let match = pattern.exec(content);
  while (match) {
    if (match.index > last) {
      parts.push({ type: "text", value: content.slice(last, match.index) });
    }
    const title = match[1];
    const pageFromTitle = match[2];
    const caret = match[3];
    let citation: Citation | undefined;
    if (title && pageFromTitle) {
      citation = resolveCitation(citations, title, Number(pageFromTitle));
    } else if (caret) {
      const n = Number(caret);
      citation = citations[n - 1] ?? citations.find((item) => item.page === n);
    }
    if (citation) {
      parts.push({ type: "citation", citation, label: citationLabel(citation) });
    } else {
      parts.push({ type: "text", value: match[0] });
    }
    last = match.index + match[0].length;
    match = pattern.exec(content);
  }
  if (last < content.length) {
    parts.push({ type: "text", value: content.slice(last) });
  }
  return parts;
}

export function uniqueCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>();
  const out: Citation[] = [];
  for (const item of citations) {
    const key = `${item.doc_id}:${item.page}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}
