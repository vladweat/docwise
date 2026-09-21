"""Minimal DOCX bytes for parser/ingestion tests."""

from __future__ import annotations

import io

from docx import Document


def policy_docx_bytes() -> bytes:
    doc = Document()
    doc.add_heading("Travel policy", level=1)
    doc.add_paragraph("The office travel cap is 150 USD per night for domestic trips.")
    doc.add_heading("Expenses", level=2)
    doc.add_paragraph("Submit receipts within 30 days through the finance portal.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Tier"
    table.cell(0, 1).text = "Limit"
    table.cell(1, 0).text = "L3"
    table.cell(1, 1).text = "150 USD"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
