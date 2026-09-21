import { getClientLocale, tClient } from "@/i18n/client-translate";
import { translate, type Locale } from "@/i18n/messages";
import type { Citation } from "@/types/chat";

/** Keep Russian text in sync with backend `NO_CONTEXT_ANSWER` in `retrieval.py`. */
export function isNoContextAnswer(content: string): boolean {
  const trimmed = content.trim();
  return (
    trimmed === translate("ru", "chat.noContextAnswer") ||
    trimmed === translate("en", "chat.noContextAnswer")
  );
}

export function citationLabel(
  citation: Pick<Citation, "doc_title" | "page" | "section">,
  locale: Locale = getClientLocale(),
): string {
  const title = citation.doc_title.trim() || translate(locale, "common.document");
  if (citation.page != null && citation.page > 0) {
    const pageWord = translate(locale, "chat.pageShort");
    return `${title} (${pageWord} ${citation.page})`;
  }
  const section = citation.section?.trim();
  return section ? `${title} (${section})` : title;
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
  section?: string,
): Citation | undefined {
  const needle = normalizeTitle(title);
  if (section) {
    const sectionNeedle = section.trim().toLowerCase();
    return citations.find(
      (item) =>
        normalizeTitle(item.doc_title) === needle &&
        (item.section?.trim().toLowerCase() === sectionNeedle ||
          item.section?.trim().toLowerCase().includes(sectionNeedle)),
    );
  }
  return (
    citations.find(
      (item) => item.page === page && normalizeTitle(item.doc_title) === needle,
    ) ?? citations.find((item) => item.page === page)
  );
}

const INLINE_CITE_RE =
  /\[([^\]\n]+?),\s*(?:p\.|стр\.?)\s*(\d+)\]|\[([^\]\n]+?),\s*(?:раздел:|section:)\s*([^\]]+)\]|\[\^(\d+)\]/gi;

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
    const docxTitle = match[3];
    const docxSection = match[4];
    const caret = match[5];
    let citation: Citation | undefined;
    if (title && pageFromTitle) {
      citation = resolveCitation(citations, title, Number(pageFromTitle));
    } else if (docxTitle && docxSection) {
      citation = resolveCitation(citations, docxTitle, 0, docxSection);
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

export function stripCitationMarkers(content: string): string {
  return content
    .replace(INLINE_CITE_RE, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
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

export function localizedNoContextAnswer(): string {
  return tClient("chat.noContextAnswer");
}
