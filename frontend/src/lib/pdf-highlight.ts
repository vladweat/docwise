export interface HighlightRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

type TextPiece = {
  str: string;
  transform: number[];
  width: number;
  height: number;
};

function normalize(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

export function findSnippetRects(
  items: TextPiece[],
  convertToViewportRectangle: (rect: number[]) => number[],
  snippet: string,
): HighlightRect[] {
  const needle = normalize(snippet).slice(0, 120);
  if (needle.length < 6) return [];

  let haystack = "";
  const spans: { start: number; end: number; item: TextPiece }[] = [];
  for (const item of items) {
    const str = item.str ?? "";
    if (!str) continue;
    if (haystack.length > 0) haystack += " ";
    const start = haystack.length;
    haystack += normalize(str);
    spans.push({ start, end: haystack.length, item });
  }

  let from = haystack.indexOf(needle);
  let to = from + needle.length;
  if (from < 0) {
    const short = needle.slice(0, Math.min(40, needle.length));
    from = haystack.indexOf(short);
    to = from + short.length;
  }
  if (from < 0) return [];

  const rects: HighlightRect[] = [];
  for (const span of spans) {
    if (span.end <= from || span.start >= to) continue;
    const item = span.item;
    const tx = item.transform[4] ?? 0;
    const ty = item.transform[5] ?? 0;
    const w = item.width || 0;
    const h = item.height || Math.abs(item.transform[3] ?? 0) || 8;
    const converted = convertToViewportRectangle([tx, ty, tx + w, ty + h]);
    const left = Math.min(converted[0], converted[2]);
    const top = Math.min(converted[1], converted[3]);
    const width = Math.abs(converted[2] - converted[0]);
    const height = Math.abs(converted[3] - converted[1]);
    if (width < 1 || height < 1) continue;
    rects.push({ left, top, width, height });
  }
  return rects;
}
