"""Parse, chunk, and embed one document into ``document_chunks`` rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.document import EMBEDDING_DIM, Document, DocumentChunk, make_chunk_id
from app.services.ingestion.chunker import PreparedChunk, chunk_parsed_document
from app.services.ingestion.embeddings import EmbeddingError, embed_texts
from app.services.ingestion.format import PDF_MAGIC
from app.services.ingestion.docx_parser import DocxParserError, parse_docx
from app.services.ingestion.pdf_parser import PdfParserError, ParsedDocument, parse_pdf
from app.services.ingestion.stages import STAGE_CHUNK, STAGE_EMBED, STAGE_PARSE, set_ingestion_stage
from app.services.org.quotas import assert_ingest_pages_allowed


class IngestionError(Exception):
    """Terminal document parsing or indexing failure with a safe message."""


class RetryableIngestionError(IngestionError):
    """Transient infrastructure failure that Celery may retry."""


@dataclass(frozen=True)
class IndexResult:
    chunk_count: int
    total_pages: int | None = None


IndexFn = Callable[[Session, Document, bytes], IndexResult]


def _insert_chunks(
    db: Session,
    document: Document,
    chunks: list[PreparedChunk],
    vectors: list[list[float]],
) -> int:
    if len(vectors) != len(chunks):
        raise IngestionError("Embedding count does not match chunk count")
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise IngestionError(f"Expected {EMBEDDING_DIM}-dim embeddings, got {len(vector)}")

    ordinal_by_page: dict[int, int] = {}
    roles = list(document.access_roles)
    for chunk, vector in zip(chunks, vectors, strict=True):
        ordinal = ordinal_by_page.get(chunk.page_number, 0)
        ordinal_by_page[chunk.page_number] = ordinal + 1
        db.add(
            DocumentChunk(
                document_id=document.id,
                organization_id=document.organization_id,
                chunk_id=make_chunk_id(document.id, chunk.page_number, ordinal),
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                is_table=chunk.is_table,
                access_roles=list(roles),
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=vector,
                doc_title=document.title,
                bbox=chunk.bbox,
                highlight_rects=chunk.highlight_rects,
            )
        )
    return len(chunks)


def _index_parsed(
    db: Session,
    document: Document,
    parsed: ParsedDocument,
    *,
    embedder=None,
    total_pages: int | None,
) -> IndexResult:
    if total_pages is not None:
        assert_ingest_pages_allowed(
            db,
            document.organization_id,
            total_pages,
            exclude_document_id=document.id,
        )

    set_ingestion_stage(db, document, STAGE_CHUNK)
    chunks = chunk_parsed_document(parsed)
    if not chunks:
        raise IngestionError("Document produced no extractable text")

    set_ingestion_stage(db, document, STAGE_EMBED)
    texts = [chunk.embed_text(document.title) for chunk in chunks]
    try:
        vectors = embed_texts(texts, embedder=embedder)
    except EmbeddingError as exc:
        raise RetryableIngestionError("Embedding service failed") from exc

    count = _insert_chunks(db, document, chunks, vectors)
    return IndexResult(chunk_count=count, total_pages=total_pages)


def index_pdf(
    db: Session,
    document: Document,
    pdf_bytes: bytes,
    *,
    embedder=None,
) -> IndexResult:
    """Replace chunk rows for this PDF (caller deletes old rows first)."""
    if not pdf_bytes.startswith(PDF_MAGIC):
        raise IngestionError("Downloaded object is not a PDF")
    set_ingestion_stage(db, document, STAGE_PARSE)
    try:
        parsed = parse_pdf(pdf_bytes)
    except PdfParserError as exc:
        raise IngestionError("PDF parsing failed") from exc

    pdf_pages = parsed.total_pages
    if pdf_pages is None:
        raise IngestionError("PDF missing page count")

    return _index_parsed(db, document, parsed, embedder=embedder, total_pages=pdf_pages)


def index_docx(
    db: Session,
    document: Document,
    docx_bytes: bytes,
    *,
    embedder=None,
) -> IndexResult:
    set_ingestion_stage(db, document, STAGE_PARSE)
    try:
        parsed = parse_docx(docx_bytes)
    except DocxParserError as exc:
        raise IngestionError("DOCX parsing failed") from exc

    return _index_parsed(db, document, parsed, embedder=embedder, total_pages=None)
