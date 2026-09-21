"""Detect upload/ingest format from filename, media type, and magic bytes."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

PDF_MAGIC = b"%PDF"
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def suffix_format(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "docx"
    return None


def detect_format(filename: str, content: bytes, content_type: str | None) -> str | None:
    """Return ``pdf`` or ``docx`` when the upload looks valid, else ``None``."""
    if content.startswith(PDF_MAGIC):
        return "pdf"
    if _looks_like_docx(content):
        return "docx"
    by_name = suffix_format(filename)
    if by_name == "pdf":
        return None
    media = (content_type or "").split(";")[0].strip().lower()
    if by_name == "docx" and media in {DOCX_MEDIA, "application/octet-stream", ""}:
        return "docx"
    return by_name


def _looks_like_docx(content: bytes) -> bool:
    if len(content) < 4 or content[:2] != b"PK":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return "word/document.xml" in archive.namelist()
    except Exception:
        return False


def media_type_for_title(title: str) -> str:
    kind = suffix_format(title)
    if kind == "docx":
        return DOCX_MEDIA
    return "application/pdf"
