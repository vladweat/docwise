"""DOCX extraction: logical sections as page-bounded units (page_number=0 in chunks).

Citations use ``section_title``, not invented PDF page numbers (see docs/pipeline/ingestion.md).
"""

from __future__ import annotations

import io
import logging
import re

from docx import Document as DocxDocument
from docx.document import Document as DocxDocumentType
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.services.ingestion.pdf_parser import BBox, PageBlock, ParsedDocument, ParsedPage, table_to_gfm

logger = logging.getLogger(__name__)

_DOCX_PAGE_WIDTH = 612.0
_DOCX_PAGE_HEIGHT = 792.0
_HEADING_STYLE_RE = re.compile(r"^heading\s*\d", re.IGNORECASE)
_DEFAULT_SECTION = "Document"


class DocxParserError(ValueError):
    """DOCX bytes could not be opened or contain no extractable text."""


def parse_docx(docx_bytes: bytes) -> ParsedDocument:
    if not docx_bytes:
        raise DocxParserError("DOCX is empty")
    try:
        doc = DocxDocument(io.BytesIO(docx_bytes))
    except Exception as exc:
        raise DocxParserError("Unable to open DOCX") from exc

    sections: list[tuple[str, list[PageBlock]]] = []
    current_title = _DEFAULT_SECTION
    current_blocks: list[PageBlock] = []
    y_cursor = 72.0

    def flush() -> None:
        nonlocal current_blocks, y_cursor
        if not current_blocks:
            return
        sections.append((current_title, list(current_blocks)))
        current_blocks = []
        y_cursor = 72.0

    for block in _iter_body_blocks(doc):
        if isinstance(block, Paragraph):
            text = _paragraph_text(block)
            if not text:
                continue
            if _is_heading(block):
                flush()
                current_title = text
                current_blocks.append(
                    _text_block(text, y_cursor, is_heading=True),
                )
                y_cursor += 28.0
                continue
            current_blocks.append(_text_block(text, y_cursor, is_heading=False))
            y_cursor += max(18.0, 14.0 * (text.count("\n") + 1))
        elif isinstance(block, Table):
            markdown = _table_markdown(block)
            if not markdown.strip():
                continue
            height = 24.0 * max(3, markdown.count("\n") + 1)
            current_blocks.append(
                PageBlock(
                    text=markdown,
                    bbox=(72.0, y_cursor, 540.0, y_cursor + height),
                    font_size=0.0,
                    is_table=True,
                    highlight_rects=(),
                )
            )
            y_cursor += height + 12.0

    flush()

    if not sections:
        raise DocxParserError("DOCX produced no extractable text")

    pages = [
        ParsedPage(
            page_number=0,
            width=_DOCX_PAGE_WIDTH,
            height=_DOCX_PAGE_HEIGHT,
            blocks=tuple(blocks),
        )
        for _section_title, blocks in sections
    ]
    return ParsedDocument(total_pages=None, pages=tuple(pages))


def estimate_docx_quota_units(docx_bytes: bytes) -> int:
    """Reserve plan pages at upload: one unit per logical section, minimum 1."""
    try:
        parsed = parse_docx(docx_bytes)
    except DocxParserError:
        return 1
    return max(1, len(parsed.pages))


def _iter_body_blocks(parent: DocxDocumentType):
    body = parent.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _paragraph_text(paragraph: Paragraph) -> str:
    return " ".join(paragraph.text.split())


def _is_heading(paragraph: Paragraph) -> bool:
    try:
        name = (paragraph.style.name or "").strip()
    except Exception:
        name = ""
    if _HEADING_STYLE_RE.match(name):
        return True
    try:
        outline = paragraph.paragraph_format.outline_level
    except Exception:
        outline = None
    return outline is not None and outline < 9


def _text_block(text: str, y0: float, *, is_heading: bool) -> PageBlock:
    y1 = y0 + (22.0 if is_heading else max(18.0, 14.0 * (text.count("\n") + 1)))
    bbox: BBox = (72.0, y0, 540.0, y1)
    return PageBlock(
        text=text,
        bbox=bbox,
        font_size=14.0 if is_heading else 11.0,
        is_heading=is_heading,
        highlight_rects=(bbox,),
    )


def _table_markdown(table: Table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            cells.append(" ".join(cell.text.split()))
        rows.append(cells)
    return table_to_gfm(rows)
