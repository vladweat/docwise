"""Deterministic PDFs for parser / chunker tests (no GPU, no live LLM)."""

from __future__ import annotations

import fitz

A4 = (595.0, 842.0)

TABLE_CELLS = [
    ["Benefit", "Days", "Notes"],
    ["Vacation", "20", "Annual leave"],
    ["Sick", "10", "Paid"],
]


def policy_pdf_bytes() -> bytes:
    """Two-page HR policy: headings, prose, and a ruled table pdfplumber can see."""
    doc = fitz.open()
    page1 = doc.new_page(width=A4[0], height=A4[1])
    page1.insert_text((72, 72), "Leave Policy", fontsize=18, fontname="helv")
    page1.insert_textbox(
        fitz.Rect(72, 100, 523, 170),
        "Employees are entitled to twenty days of paid vacation per calendar year. "
        "Requests must be submitted two weeks in advance.",
        fontsize=11,
        fontname="helv",
    )
    _draw_table(page1, origin=(72, 200), col_widths=[140.0, 80.0, 180.0], row_h=22.0, cells=TABLE_CELLS)

    page2 = doc.new_page(width=A4[0], height=A4[1])
    page2.insert_text((72, 72), "Expenses", fontsize=18, fontname="helv")
    page2.insert_textbox(
        fitz.Rect(72, 100, 523, 180),
        "Taxi receipts under forty dollars do not need a manager signature. "
        "Keep original receipts attached to the monthly report.",
        fontsize=11,
        fontname="helv",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def blank_pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page(width=A4[0], height=A4[1])
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _draw_table(
    page: fitz.Page,
    *,
    origin: tuple[float, float],
    col_widths: list[float],
    row_h: float,
    cells: list[list[str]],
) -> None:
    x0, y0 = origin
    n_rows = len(cells)
    width = sum(col_widths)
    height = n_rows * row_h
    x1, y1 = x0 + width, y0 + height

    for row_i in range(n_rows + 1):
        y = y0 + row_i * row_h
        page.draw_line(fitz.Point(x0, y), fitz.Point(x1, y), color=(0, 0, 0), width=1.0)
    x = x0
    page.draw_line(fitz.Point(x0, y0), fitz.Point(x0, y1), color=(0, 0, 0), width=1.0)
    for col_w in col_widths:
        x += col_w
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y1), color=(0, 0, 0), width=1.0)

    for row_i, row in enumerate(cells):
        x = x0
        for col_i, value in enumerate(row):
            page.insert_text(
                (x + 6, y0 + row_i * row_h + 15),
                value,
                fontsize=10,
                fontname="helv",
            )
            x += col_widths[col_i]
