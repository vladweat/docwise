"""Physical-page PDF extraction (PyMuPDF + pdfplumber tables).

Page numbers are 1-based, matching the API and citations. This is not
ChainWise `semantic_splitter.py` (AST / function bounds).
"""

from __future__ import annotations

import io
import logging
import statistics
from dataclasses import dataclass
from typing import Any

import fitz
import pdfplumber

logger = logging.getLogger(__name__)

BBox = tuple[float, float, float, float]

_HEADING_MAX_WORDS = 16
_HEADING_SIZE_RATIO = 1.15
_HEADING_SIZE_DELTA = 1.0
_TABLE_CONTAINMENT = 0.5


class PdfParserError(ValueError):
    """PDF bytes could not be opened or are not a readable document."""


@dataclass(frozen=True)
class PageBlock:
    text: str
    bbox: BBox
    font_size: float
    is_heading: bool = False
    is_table: bool = False
    highlight_rects: tuple[BBox, ...] = ()


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    width: float
    height: float
    blocks: tuple[PageBlock, ...]


@dataclass(frozen=True)
class ParsedDocument:
    total_pages: int
    pages: tuple[ParsedPage, ...]


def parse_pdf(pdf_bytes: bytes) -> ParsedDocument:
    """Extract reading-order blocks and GFM tables for every physical page."""
    if not pdf_bytes:
        raise PdfParserError("PDF is empty")
    try:
        fitz_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PdfParserError("Unable to open PDF") from exc

    plumber: Any = None
    try:
        if fitz_doc.needs_pass:
            raise PdfParserError("PDF is password-protected")
        try:
            plumber = pdfplumber.open(io.BytesIO(pdf_bytes))
        except Exception:
            logger.warning("pdfplumber failed to open document; tables will be skipped")
            plumber = None

        pages: list[ParsedPage] = []
        for index in range(len(fitz_doc)):
            fitz_page = fitz_doc[index]
            plumber_page = None
            if plumber is not None and index < len(plumber.pages):
                plumber_page = plumber.pages[index]
            pages.append(_parse_page(fitz_page, plumber_page, page_number=index + 1))
        return ParsedDocument(total_pages=len(fitz_doc), pages=tuple(pages))
    finally:
        fitz_doc.close()
        if plumber is not None:
            plumber.close()


def table_to_gfm(rows: list[list[Any]]) -> str:
    """Serialize a rectangular table as GitHub-flavored Markdown."""
    if not rows:
        return ""
    width = max((len(row) for row in rows), default=0)
    if width == 0:
        return ""
    normalized: list[list[str]] = []
    for row in rows:
        cells = [_gfm_cell(row[i]) if i < len(row) else "" for i in range(width)]
        normalized.append(cells)
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for body_row in normalized[1:]:
        lines.append("| " + " | ".join(body_row) + " |")
    return "\n".join(lines)


def _gfm_cell(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    return text.replace("|", "\\|")


def _parse_page(
    fitz_page: fitz.Page,
    plumber_page: Any,
    *,
    page_number: int,
) -> ParsedPage:
    width, height = float(fitz_page.rect.width), float(fitz_page.rect.height)
    tables = _extract_tables(plumber_page)
    text_blocks = _extract_text_blocks(fitz_page)
    kept_text = [block for block in text_blocks if not _overlaps_any_table(block.bbox, tables)]
    merged = _assign_headings([*kept_text, *tables])
    ordered = sorted(merged, key=lambda block: (_sort_y(block.bbox[1]), block.bbox[0]))
    return ParsedPage(
        page_number=page_number,
        width=width,
        height=height,
        blocks=tuple(ordered),
    )


def _sort_y(y0: float) -> float:
    return round(y0, 1)


def _extract_tables(plumber_page: Any) -> list[PageBlock]:
    if plumber_page is None:
        return []
    found: list[PageBlock] = []
    for table in _find_tables(plumber_page):
        try:
            rows = table.extract()
            bbox = tuple(float(v) for v in table.bbox)
        except Exception:
            logger.debug("skipping a table that failed to extract", exc_info=True)
            continue
        if len(bbox) != 4:
            continue
        markdown = table_to_gfm(rows or [])
        if not markdown.strip():
            continue
        rect: BBox = (bbox[0], bbox[1], bbox[2], bbox[3])
        found.append(
            PageBlock(
                text=markdown,
                bbox=rect,
                font_size=0.0,
                is_table=True,
                highlight_rects=(rect,),
            )
        )
    return found


def _find_tables(plumber_page: Any) -> list[Any]:
    settings_attempts: tuple[dict[str, str], ...] = (
        {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
        {"vertical_strategy": "lines_strict", "horizontal_strategy": "lines_strict"},
    )
    for settings in settings_attempts:
        try:
            tables = plumber_page.find_tables(table_settings=settings)
        except Exception:
            continue
        if tables:
            return list(tables)
    return []


def _extract_text_blocks(fitz_page: fitz.Page) -> list[PageBlock]:
    payload = fitz_page.get_text("dict")
    raw_blocks = payload.get("blocks") or []
    extracted: list[tuple[str, BBox, float, tuple[BBox, ...]]] = []
    sizes: list[float] = []
    for raw in raw_blocks:
        if raw.get("type", 0) != 0:
            continue
        text, bbox, font_size, rects = _from_fitz_block(raw)
        if not text:
            continue
        extracted.append((text, bbox, font_size, rects))
        if font_size > 0:
            sizes.append(font_size)
    if not extracted:
        return []
    median_size = statistics.median(sizes) if sizes else 0.0
    max_size = max(sizes) if sizes else 0.0
    blocks: list[PageBlock] = []
    for text, bbox, font_size, rects in extracted:
        blocks.append(
            PageBlock(
                text=text,
                bbox=bbox,
                font_size=font_size,
                is_heading=_is_heading(text, font_size, median_size, max_size),
                highlight_rects=rects or (bbox,),
            )
        )
    return blocks


def _from_fitz_block(raw: dict[str, Any]) -> tuple[str, BBox, float, tuple[BBox, ...]]:
    line_texts: list[str] = []
    span_sizes: list[float] = []
    rects: list[BBox] = []
    for line in raw.get("lines") or []:
        spans = line.get("spans") or []
        line_texts.append("".join(str(span.get("text") or "") for span in spans))
        for span in spans:
            piece = str(span.get("text") or "")
            if not piece.strip():
                continue
            span_sizes.append(float(span.get("size") or 0.0))
            span_bbox = span.get("bbox")
            if span_bbox and len(span_bbox) == 4:
                rects.append(tuple(float(v) for v in span_bbox))  # type: ignore[arg-type]
        line_bbox = line.get("bbox")
        if not spans and line_bbox and len(line_bbox) == 4:
            rects.append(tuple(float(v) for v in line_bbox))  # type: ignore[arg-type]
    text = "\n".join(line_texts).strip()
    raw_bbox = raw.get("bbox") or (0.0, 0.0, 0.0, 0.0)
    bbox: BBox = tuple(float(v) for v in raw_bbox)  # type: ignore[assignment]
    font_size = statistics.median(span_sizes) if span_sizes else 0.0
    return text, bbox, float(font_size), tuple(rects)


def _is_heading(text: str, font_size: float, median_size: float, max_size: float) -> bool:
    if not text or len(text.split()) > _HEADING_MAX_WORDS:
        return False
    if median_size <= 0 or max_size <= median_size + 0.5:
        return False
    return font_size >= median_size * _HEADING_SIZE_RATIO and font_size >= median_size + _HEADING_SIZE_DELTA


def _overlaps_any_table(bbox: BBox, tables: list[PageBlock]) -> bool:
    return any(_contained_fraction(bbox, table.bbox) >= _TABLE_CONTAINMENT for table in tables)


def _contained_fraction(inner: BBox, outer: BBox) -> float:
    ix0 = max(inner[0], outer[0])
    iy0 = max(inner[1], outer[1])
    ix1 = min(inner[2], outer[2])
    iy1 = min(inner[3], outer[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inner_area = max((inner[2] - inner[0]) * (inner[3] - inner[1]), 1e-6)
    return ((ix1 - ix0) * (iy1 - iy0)) / inner_area


def _assign_headings(blocks: list[PageBlock]) -> list[PageBlock]:
    """Keep table flags; headings never apply to table blocks."""
    result: list[PageBlock] = []
    for block in blocks:
        if block.is_table and block.is_heading:
            result.append(
                PageBlock(
                    text=block.text,
                    bbox=block.bbox,
                    font_size=block.font_size,
                    is_heading=False,
                    is_table=True,
                    highlight_rects=block.highlight_rects,
                )
            )
        else:
            result.append(block)
    return result
