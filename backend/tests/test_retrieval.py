"""BM25 / RRF / FTS over document text — no GPU, no live LLM, no Solidity heuristics."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus, EMBEDDING_DIM, make_chunk_id
from app.services.retrieval import (
    DENSE_TOP_K,
    RRF_K,
    SPARSE_TOP_K,
    _fts_or_query,
    bm25_scores,
    reciprocal_rank_fusion,
    retrieve,
    sparse_search,
)
from app.services.text import lexical_tokens
from helpers import make_org, make_principal, wipe_app_tables

RETRIEVAL_PY = Path(__file__).resolve().parents[1] / "app" / "services" / "retrieval.py"


def test_lexical_tokens_keep_words_digits_and_cyrillic():
    tokens = lexical_tokens("Parental leave: 140 calendar days.")
    assert "parental" in tokens
    assert "leave" in tokens
    assert "140" in tokens
    assert "days" in tokens
    cyrillic = lexical_tokens("график работы безопасен?")
    assert "график" in cyrillic
    assert "работы" in cyrillic
    assert "безопасен" in cyrillic


def test_bm25_ranks_relevant_document_first():
    docs = [
        "Employees may take parental leave of 140 calendar days.",
        "The office wifi password is posted at reception.",
        "Travel reimbursement is capped at 150 USD per day.",
    ]
    scores = bm25_scores("parental leave 140 days", docs)
    assert scores[0] == max(scores)


def test_reciprocal_rank_fusion_prefers_overlap():
    fused = reciprocal_rank_fusion([[0, 1, 2], [1, 0, 2]])
    assert fused[0][0] in (0, 1)
    assert {idx for idx, _score in fused} == {0, 1, 2}


def test_reciprocal_rank_fusion_uses_k_60():
    assert RRF_K == 60
    fused = reciprocal_rank_fusion([[0], [0]], k=RRF_K)
    assert fused[0][1] == 2.0 / (60 + 1)


def test_fts_query_drops_stopwords_and_ors_content_terms():
    q = _fts_or_query("What is the default Python version for engineering?")
    assert q is not None
    parts = set(q.split(" | "))
    assert "python" in parts
    assert "default" in parts
    assert "version" in parts
    assert "engineering" in parts
    assert "what" not in parts
    assert "the" not in parts
    assert "is" not in parts


def test_no_solidity_heuristics_in_retrieval():
    source = RETRIEVAL_PY.read_text()
    assert "is_overview_question" not in source
    assert "citations_are_interface_stubs" not in source
    assert "select_overview_code_chunks" not in source
    assert "scroll_contract_chunks" not in source
    assert "load_search_pool" not in source
    assert "_analysis_chunk" not in source
    assert "primary_contract_names" not in source
    assert "def sparse_search" in source
    assert "_sparse_ranking" not in source
    assert "hnsw.iterative_scan" in source
    assert "SET LOCAL" in source
    assert DENSE_TOP_K == 25
    assert SPARSE_TOP_K == 25


@pytest.fixture
def db():
    session: Session = SessionLocal()
    wipe_app_tables(session)
    yield session
    wipe_app_tables(session)
    session.close()


def _vec(seed: int) -> list[float]:
    return [((seed + offset) % 17) / 17.0 for offset in range(EMBEDDING_DIM)]


class _KeywordReranker:
    def __init__(self, needle: str):
        self.needle = needle.lower()

    def score(self, _query: str, documents: list[str]) -> list[float]:
        return [0.99 if self.needle in doc.lower() else 0.05 for doc in documents]


def _ready_doc(db: Session, org, *, title: str, roles: list[str]) -> Document:
    doc = Document(
        organization_id=org.id,
        title=title,
        file_path=f"{uuid4()}/{title}",
        file_hash=uuid4().hex,
        file_size_bytes=32,
        access_roles=roles,
        status=DocumentStatus.ready.value,
    )
    db.add(doc)
    db.flush()
    return doc


def _chunk(db: Session, doc: Document, *, page: int, content: str, embedding: list[float]) -> DocumentChunk:
    row = DocumentChunk(
        document_id=doc.id,
        organization_id=doc.organization_id,
        chunk_id=make_chunk_id(doc.id, page, 0),
        page_number=page,
        access_roles=list(doc.access_roles),
        content=content,
        token_count=len(content.split()),
        embedding=embedding,
        doc_title=doc.title,
    )
    db.add(row)
    db.flush()
    return row


def test_sparse_fts_finds_lexical_hit_outside_dense_top(db: Session):
    org = make_org(db)
    user = make_principal(db, org)
    public = _ready_doc(db, org, title="Handbook.pdf", roles=["all"])
    noise_vec = _vec(1)
    lexical = "Default Python version is 3.12 xyzzy-python-unique."
    for page in range(1, 31):
        _chunk(db, public, page=page, content=f"Noise filler page {page} office wifi.", embedding=noise_vec)
    target = _chunk(db, public, page=99, content=lexical, embedding=_vec(9))
    db.commit()

    class _Embedder:
        def encode(self, texts, **_kwargs):
            return [noise_vec for _ in texts]

    result = retrieve(
        db,
        user,
        "What is the default Python version xyzzy-python-unique?",
        embedder=_Embedder(),
        reranker=_KeywordReranker("xyzzy-python-unique"),
    )
    sparse_ids = {hit.chunk_id for hit in result.sparse}
    assert target.chunk_id in sparse_ids
    assert any(chunk.id == target.id for chunk in result.chunks)


def test_sparse_search_applies_org_and_acl(db: Session):
    org = make_org(db)
    other = make_org(db)
    user = make_principal(db, org)
    visible = _ready_doc(db, org, title="Public.pdf", roles=["all"])
    hidden = _ready_doc(db, org, title="HR.pdf", roles=["hr"])
    foreign = _ready_doc(db, other, title="Foreign.pdf", roles=["all"])
    needle = "security incident report to security@docwise.example within one hour"
    _chunk(db, visible, page=2, content=f"Public {needle}", embedding=_vec(1))
    secret = _chunk(db, hidden, page=2, content=f"Secret {needle}", embedding=_vec(2))
    foreign_chunk = _chunk(db, foreign, page=2, content=f"Foreign {needle}", embedding=_vec(3))
    db.commit()

    hits = sparse_search(
        db,
        "security incident security@docwise.example",
        list(user.allowed_roles()),
        organization_id=org.id,
        limit=25,
    )
    ids = {chunk.id for chunk, _score in hits}
    assert secret.id not in ids
    assert foreign_chunk.id not in ids
    assert any("Public" in chunk.content for chunk, _score in hits)
