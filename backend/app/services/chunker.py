"""Page- and section-bounded chunking for Docwise.

Chunks never cross a physical page. Overlap applies only inside the same
page and section. Tables stay Markdown (`is_table`). This replaces
ChainWise `semantic_splitter.py` (do not port AST splitting).

Rule for embed vs UI text (locked):
- `content` / citation snippet: the fragment only, no meta header
- `embed_text`: `[Document: … | Section: … | Page: N]` + newline + `content`
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.pdf_parser import BBox, PageBlock, ParsedDocument, ParsedPage

CHUNK_MIN_TOKENS = 400
CHUNK_MAX_TOKENS = 600
CHUNK_OVERLAP_TOKENS = 50
UNTITLED_SECTION = "Untitled"

_TOKEN_RE = re.compile(r"\S+", re.UNICODE)
_META_HEADER = "[Document: {document} | Section: {section} | Page: {page}]"


@dataclass(frozen=True)
class PreparedChunk:
    page_number: int
    section_title: str | None
    is_table: bool
    content: str
    token_count: int
    bbox: dict[str, float] | None
    highlight_rects: list[dict[str, float]] | None
    page_width: float
    page_height: float

    def embed_text(self, document_title: str) -> str:
        return format_embed_text(
            document_title=document_title,
            section_title=self.section_title,
            page_number=self.page_number,
            content=self.content,
        )


def tokenize(text: str) -> list[str]:
    """Ingest budget tokenizer (whitespace-delimited). Independent of FastEmbed."""
    return _TOKEN_RE.findall(text)


def count_tokens(text: str) -> int:
    return len(tokenize(text))


def format_embed_text(
    *,
    document_title: str,
    section_title: str | None,
    page_number: int,
    content: str,
) -> str:
    section = (section_title or "").strip() or UNTITLED_SECTION
    header = _META_HEADER.format(
        document=document_title,
        section=section,
        page=page_number,
    )
    return f"{header}\n{content}"


def citation_snippet(content: str, limit: int = 280) -> str:
    """Snippet for SSE citations: never include the embed meta line."""
    text = content.strip()
    if text.startswith("[Document:"):
        text = text.split("\n", 1)[-1].strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def chunk_parsed_document(parsed: ParsedDocument) -> list[PreparedChunk]:
    chunks: list[PreparedChunk] = []
    for page in parsed.pages:
        chunks.extend(chunk_page(page))
    return chunks


def chunk_page(page: ParsedPage) -> list[PreparedChunk]:
    chunks: list[PreparedChunk] = []
    for section_title, blocks in _section_groups(page.blocks):
        chunks.extend(_chunk_section(page, section_title, blocks))
    return chunks


def _section_groups(blocks: tuple[PageBlock, ...]) -> list[tuple[str | None, list[PageBlock]]]:
    groups: list[tuple[str | None, list[PageBlock]]] = []
    current_title: str | None = None
    current: list[PageBlock] = []
    for block in blocks:
        if block.is_heading and not block.is_table:
            if current:
                groups.append((current_title, current))
            current_title = block.text.strip() or None
            current = [block]
        else:
            current.append(block)
    if current:
        groups.append((current_title, current))
    return groups


def _chunk_section(
    page: ParsedPage,
    section_title: str | None,
    blocks: list[PageBlock],
) -> list[PreparedChunk]:
    chunks: list[PreparedChunk] = []
    prose: list[PageBlock] = []

    def flush_prose() -> None:
        if not prose:
            return
        chunks.extend(_chunk_prose(page, section_title, list(prose)))
        prose.clear()

    for block in blocks:
        if block.is_table:
            flush_prose()
            chunks.extend(_chunk_table(page, section_title, block))
        else:
            prose.append(block)
    flush_prose()
    return chunks


def _chunk_prose(
    page: ParsedPage,
    section_title: str | None,
    blocks: list[PageBlock],
) -> list[PreparedChunk]:
    pieces = [block.text.strip() for block in blocks if block.text.strip()]
    if not pieces:
        return []
    text = "\n\n".join(pieces)
    windows = _token_windows(text, CHUNK_MAX_TOKENS, CHUNK_OVERLAP_TOKENS)
    ownership = _char_ranges(pieces)
    result: list[PreparedChunk] = []
    cursor = 0
    for window in windows:
        start = text.find(window, cursor)
        if start < 0:
            start = text.find(window)
        end = start + len(window) if start >= 0 else len(text)
        if start >= 0:
            cursor = start + max(len(window) - 1, 0)
        used = _blocks_for_span(blocks, ownership, start, end)
        result.append(_make_chunk(page, section_title, window, is_table=False, blocks=used))
    return result


def _char_ranges(pieces: list[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for index, piece in enumerate(pieces):
        if index:
            cursor += 2
        start = cursor
        cursor += len(piece)
        ranges.append((start, cursor))
    return ranges


def _blocks_for_span(
    blocks: list[PageBlock],
    ranges: list[tuple[int, int]],
    start: int,
    end: int,
) -> list[PageBlock]:
    nonempty = [block for block in blocks if block.text.strip()]
    used: list[PageBlock] = []
    for block, (b0, b1) in zip(nonempty, ranges):
        if b1 > start and b0 < end:
            used.append(block)
    return used or nonempty


def _token_windows(text: str, max_tokens: int, overlap: int) -> list[str]:
    spans = [(match.start(), match.end()) for match in _TOKEN_RE.finditer(text)]
    if not spans:
        stripped = text.strip()
        return [stripped] if stripped else []
    if len(spans) <= max_tokens:
        stripped = text.strip()
        return [stripped] if stripped else []
    windows: list[str] = []
    start = 0
    n = len(spans)
    while start < n:
        end = min(start + max_tokens, n)
        windows.append(text[spans[start][0] : spans[end - 1][1]].strip())
        if end >= n:
            break
        next_start = end - overlap
        start = next_start if next_start > start else end
    return windows


def _chunk_table(
    page: ParsedPage,
    section_title: str | None,
    block: PageBlock,
) -> list[PreparedChunk]:
    parts = _split_markdown_table(block.text, CHUNK_MAX_TOKENS)
    return [_make_chunk(page, section_title, part, is_table=True, blocks=[block]) for part in parts]


def _split_markdown_table(markdown: str, max_tokens: int) -> list[str]:
    lines = [line for line in markdown.strip().splitlines() if line.strip()]
    if not lines:
        return []
    if count_tokens(markdown) <= max_tokens:
        return [markdown.strip()]
    header = lines[0]
    separator = None
    body_start = 1
    if len(lines) > 1 and "---" in lines[1]:
        separator = lines[1]
        body_start = 2
    prefix_lines = [header] if separator is None else [header, separator]
    prefix = "\n".join(prefix_lines)
    body = lines[body_start:]
    if not body:
        return [prefix]

    chunks: list[str] = []
    current: list[str] = []

    def render(rows: list[str]) -> str:
        return "\n".join([*prefix_lines, *rows])

    for row in body:
        trial_rows = [*current, row]
        if current and count_tokens(render(trial_rows)) > max_tokens:
            chunks.append(render(current))
            current = [row]
        else:
            current.append(row)
    if current:
        chunks.append(render(current))
    return chunks


def _make_chunk(
    page: ParsedPage,
    section_title: str | None,
    content: str,
    *,
    is_table: bool,
    blocks: list[PageBlock],
) -> PreparedChunk:
    content = content.strip()
    rects = [rect for block in blocks for rect in (block.highlight_rects or (block.bbox,))]
    if not rects and blocks:
        rects = [block.bbox for block in blocks]
    bbox = _union_bbox(rects) if rects else None
    return PreparedChunk(
        page_number=page.page_number,
        section_title=section_title,
        is_table=is_table,
        content=content,
        token_count=count_tokens(content),
        bbox=_bbox_payload(bbox, page.width, page.height) if bbox else None,
        highlight_rects=[_rect_payload(rect) for rect in rects] if rects else None,
        page_width=page.width,
        page_height=page.height,
    )


def _union_bbox(rects: list[BBox]) -> BBox:
    return (
        min(rect[0] for rect in rects),
        min(rect[1] for rect in rects),
        max(rect[2] for rect in rects),
        max(rect[3] for rect in rects),
    )


def _rect_payload(rect: BBox) -> dict[str, float]:
    return {
        "x0": round(rect[0], 2),
        "y0": round(rect[1], 2),
        "x1": round(rect[2], 2),
        "y1": round(rect[3], 2),
    }


def _bbox_payload(rect: BBox, page_width: float, page_height: float) -> dict[str, float]:
    payload = _rect_payload(rect)
    payload["page_width"] = round(page_width, 2)
    payload["page_height"] = round(page_height, 2)
    return payload
