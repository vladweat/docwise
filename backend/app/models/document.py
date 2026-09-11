import enum
from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

EMBEDDING_DIM = 384


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


def make_chunk_id(document_id: UUID, page_number: int, ordinal: int) -> str:
    return f"{document_id}:{page_number}:{ordinal}"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "ingestion_stage IS NULL OR ingestion_stage IN ('parse', 'chunk', 'embed')",
            name="ck_documents_ingestion_stage",
        ),
        UniqueConstraint("id", "organization_id", name="uq_documents_id_organization_id"),
        Index("ix_documents_organization_id_file_hash", "organization_id", "file_hash", unique=True),
        Index("ix_documents_organization_id", "organization_id"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_access_roles", "access_roles", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    access_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentStatus.pending.value,
        server_default=DocumentStatus.pending.value,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="[DocumentChunk.document_id, DocumentChunk.organization_id]",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_organization_id", "organization_id"),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            name="fk_document_chunks_document_organization",
            ondelete="CASCADE",
        ),
        Index("ix_document_chunks_chunk_id", "chunk_id", unique=True),
        Index("ix_document_chunks_access_roles", "access_roles", postgresql_using="gin"),
        Index("ix_document_chunks_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_id: Mapped[str] = mapped_column(String(128), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_table: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    access_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple'::regconfig, coalesce(content, ''))", persisted=True),
        nullable=True,
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    doc_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    highlight_rects: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    document: Mapped[Document] = relationship(
        back_populates="chunks",
        foreign_keys="[DocumentChunk.document_id, DocumentChunk.organization_id]",
    )
