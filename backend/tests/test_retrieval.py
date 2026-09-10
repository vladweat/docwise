"""Hybrid retrieval: SQL ACL on dense candidates, BM25+RRF, rerank threshold."""

from __future__ import annotations

import inspect
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus, EMBEDDING_DIM, make_chunk_id
from app.services.embeddings import VECTOR_SIZE
from app.services.retrieval import (
    DENSE_CANDIDATE_LIMIT,
    DENSE_TOP_K,
    NO_CONTEXT_ANSWER,
    RERANK_TOP_K,
    SPARSE_TOP_K,
    allowed_roles_for,
    dense_search,
    retrieve,
)
from app.services.reranker import MODEL_NAME as RERANKER_MODEL, FastEmbedReranker, _sigmoid
from helpers import make_org, make_principal, wipe_app_tables


class FakeEmbedder:
    def __init__(self, vector: list[float]):
        self.vector = vector
        self.texts: list[str] = []

    def encode(self, texts, **_kwargs):
        self.texts = list(texts)
        return [list(self.vector) for _ in texts]


class FakeReranker:
    def __init__(self, score: float = 0.9, scores: list[float] | None = None):
        self.score_value = score
        self.scores = scores
        self.seen: list[str] = []

    def score(self, query: str, documents: list[str]) -> list[float]:
        self.seen = list(documents)
        if self.scores is not None:
            return list(self.scores)
        return [self.score_value for _ in documents]


class KeywordReranker:
    def score(self, query: str, documents: list[str]) -> list[float]:
        terms = set(query.lower().split())
        out: list[float] = []
        for doc in documents:
            lowered = doc.lower()
            hits = sum(1 for term in terms if term in lowered)
            out.append(0.9 if hits else 0.05)
        return out


def _vec(seed: int) -> list[float]:
    return [((seed + offset) % 17) / 17.0 for offset in range(EMBEDDING_DIM)]


def _document(org, **overrides) -> Document:
    payload = {
        "organization_id": org.id,
        "title": "Handbook.pdf",
        "file_path": f"{uuid4()}/Handbook.pdf",
        "file_hash": uuid4().hex,
        "file_size_bytes": 1024,
        "access_roles": ["all"],
        "status": DocumentStatus.ready.value,
    }
    payload.update(overrides)
    return Document(**payload)


def _chunk(document: Document, *, page: int, content: str, embedding: list[float], ordinal: int = 0) -> DocumentChunk:
    return DocumentChunk(
        document_id=document.id,
        organization_id=document.organization_id,
        chunk_id=make_chunk_id(document.id, page, ordinal),
        page_number=page,
        access_roles=list(document.access_roles),
        content=content,
        token_count=len(content.split()),
        embedding=embedding,
        doc_title=document.title,
    )


@pytest.fixture
def db():
    session: Session = SessionLocal()
    wipe_app_tables(session)
    yield session
    wipe_app_tables(session)
    session.close()


def test_allowed_roles_is_role_union_departments_and_all(db: Session):
    org = make_org(db)
    user = make_principal(db, org, role="employee", departments=["hr", "engineering"])
    roles = allowed_roles_for(user)
    assert set(roles) == {"employee", "hr", "engineering", "all"}
    assert "allowed_roles" not in inspect.signature(retrieve).parameters
    assert "access_roles" not in inspect.signature(retrieve).parameters


def test_reranker_model_and_sigmoid_unit_interval():
    assert RERANKER_MODEL == "BAAI/bge-reranker-base"
    assert 0.0 < _sigmoid(-2.0) < 0.5
    assert 0.5 < _sigmoid(2.0) < 1.0
    assert VECTOR_SIZE == 384

    class _Model:
        def rerank(self, query, documents):
            return [0.0 for _ in documents]

    scores = FastEmbedReranker(_Model()).score("q", ["a", "b"])
    assert scores == [0.5, 0.5]


def test_dense_search_applies_sql_acl(db: Session):
    org = make_org(db)
    public = _document(org, title="Public.pdf", access_roles=["all"], file_hash=uuid4().hex)
    secret = _document(org, title="HR.pdf", access_roles=["hr"], file_hash=uuid4().hex)
    db.add_all([public, secret])
    db.flush()
    public_vec = _vec(1)
    hr_vec = _vec(9)
    db.add_all(
        [
            _chunk(public, page=1, content="Office hours are 9 to 18.", embedding=public_vec),
            _chunk(secret, page=3, content="Parental leave is 140 days.", embedding=hr_vec),
        ]
    )
    db.commit()

    employee = make_principal(db, org, role="employee")
    hits = dense_search(
        db,
        hr_vec,
        allowed_roles_for(employee),
        organization_id=org.id,
        limit=DENSE_CANDIDATE_LIMIT,
    )
    titles = {chunk.doc_title for chunk, _dist in hits}
    assert "HR.pdf" not in titles
    assert titles == {"Public.pdf"}


def test_dense_search_skips_non_ready_documents(db: Session):
    org = make_org(db)
    pending = _document(org, status=DocumentStatus.processing.value, access_roles=["all"])
    db.add(pending)
    db.flush()
    db.add(_chunk(pending, page=1, content="Draft policy text.", embedding=_vec(1)))
    db.commit()
    hits = dense_search(db, _vec(1), ["all", "employee"], organization_id=org.id, limit=10)
    assert hits == []


def test_blank_query_refuses_without_embedding(db: Session):
    org = make_org(db)
    user = make_principal(db, org)
    db.commit()
    embedder = FakeEmbedder(_vec(1))
    result = retrieve(db, user, "   ", embedder=embedder, reranker=FakeReranker(0.9))
    assert result.should_generate is False
    assert result.refusal_text == NO_CONTEXT_ANSWER
    assert embedder.texts == []


def test_employee_never_sees_hr_chunk_in_fused_or_reranked(db: Session):
    org = make_org(db)
    public = _document(org, title="Public.pdf", access_roles=["all"], file_hash=uuid4().hex)
    hr_doc = _document(org, title="HR.pdf", access_roles=["hr"], file_hash=uuid4().hex)
    admin_doc = _document(org, title="Board.pdf", access_roles=["admin"], file_hash=uuid4().hex)
    db.add_all([public, hr_doc, admin_doc])
    db.flush()
    hr_vec = _vec(3)
    db.add_all(
        [
            _chunk(public, page=1, content="The canteen menu is published weekly.", embedding=_vec(1)),
            _chunk(hr_doc, page=4, content="Severance is three monthly salaries.", embedding=hr_vec),
            _chunk(admin_doc, page=2, content="Board compensation is confidential.", embedding=_vec(7)),
        ]
    )
    employee = make_principal(db, org, role="employee")
    db.commit()

    result = retrieve(
        db,
        employee,
        "severance salaries",
        embedder=FakeEmbedder(hr_vec),
        reranker=FakeReranker(0.99),
    )
    contents = {chunk.content for chunk in result.chunks}
    snippets = [hit.snippet for hit in result.dense + result.sparse + result.rrf + result.reranked]
    titles = {chunk.doc_title for chunk in result.chunks}
    joined = " ".join(snippets)
    assert "Severance" not in joined
    assert "Board compensation" not in joined
    assert "HR.pdf" not in titles
    assert "Board.pdf" not in titles
    assert "Severance is three monthly salaries." not in contents
    assert "Board compensation is confidential." not in contents
    assert set(result.allowed_roles) == {"all", "employee"}


def test_hr_department_user_sees_hr_chunk(db: Session):
    org = make_org(db)
    public = _document(org, title="Public.pdf", access_roles=["all"], file_hash=uuid4().hex)
    hr_doc = _document(org, title="HR.pdf", access_roles=["hr"], file_hash=uuid4().hex)
    db.add_all([public, hr_doc])
    db.flush()
    hr_vec = _vec(4)
    db.add_all(
        [
            _chunk(public, page=1, content="Canteen menu.", embedding=_vec(1)),
            _chunk(hr_doc, page=4, content="Severance is three monthly salaries.", embedding=hr_vec),
        ]
    )
    hr_user = make_principal(db, org, role="employee", departments=["hr"])
    db.commit()

    result = retrieve(
        db,
        hr_user,
        "severance salaries",
        embedder=FakeEmbedder(hr_vec),
        reranker=FakeReranker(0.9),
    )
    assert any(chunk.doc_title == "HR.pdf" for chunk in result.chunks)
    assert {chunk.page_number for chunk in result.chunks} & {4}
    assert "hr" in result.allowed_roles


def test_empty_after_rerank_threshold_refuses_without_llm(db: Session):
    org = make_org(db)
    doc = _document(org, access_roles=["all"])
    db.add(doc)
    db.flush()
    db.add(_chunk(doc, page=1, content="Travel cap is 150 USD per day.", embedding=_vec(2)))
    user = make_principal(db, org)
    db.commit()

    get_settings.cache_clear()
    result = retrieve(
        db,
        user,
        "travel cap",
        embedder=FakeEmbedder(_vec(2)),
        reranker=FakeReranker(0.1),
    )
    assert result.chunks == []
    assert result.should_generate is False
    assert result.refusal_text == NO_CONTEXT_ANSWER
    assert result.reranked == []
    assert result.rrf  # fused candidates existed; threshold dropped them
    source = inspect.getsource(retrieve)
    assert "openai" not in source.lower()
    assert "call_llm" not in source.lower()


def test_hybrid_bm25_recovers_lexical_chunk(db: Session):
    org = make_org(db)
    doc = _document(org, access_roles=["all"])
    db.add(doc)
    db.flush()
    wifi_vec = _vec(1)
    leave_vec = _vec(12)
    db.add_all(
        [
            _chunk(
                doc,
                page=1,
                content="The office wifi password is posted at reception.",
                embedding=wifi_vec,
                ordinal=0,
            ),
            _chunk(
                doc,
                page=8,
                content="Parental leave is one hundred forty calendar days.",
                embedding=leave_vec,
                ordinal=1,
            ),
        ]
    )
    user = make_principal(db, org)
    db.commit()

    result = retrieve(
        db,
        user,
        "parental leave calendar days",
        embedder=FakeEmbedder(wifi_vec),
        reranker=KeywordReranker(),
    )
    assert result.should_generate is True
    assert result.chunks[0].page_number == 8
    assert "Parental leave" in result.chunks[0].content
    sparse_pages = {hit.page for hit in result.sparse}
    assert 8 in sparse_pages


def test_pipeline_limits_match_spec():
    assert DENSE_TOP_K == 25
    assert SPARSE_TOP_K == 25
    assert DENSE_CANDIDATE_LIMIT == 50
    assert RERANK_TOP_K == 4
    assert get_settings().rerank_threshold == 0.25


def test_citation_shape_uses_uuid_doc_id(db: Session):
    org = make_org(db)
    doc = _document(org, title="Policy.pdf", access_roles=["all"])
    db.add(doc)
    db.flush()
    db.add(_chunk(doc, page=2, content="Remote work is allowed on Friday.", embedding=_vec(5)))
    user = make_principal(db, org)
    db.commit()

    result = retrieve(
        db,
        user,
        "remote work Friday",
        embedder=FakeEmbedder(_vec(5)),
        reranker=FakeReranker(0.8),
    )
    assert len(result.chunks) == 1
    citation = result.chunks[0].to_citation()
    assert citation["doc_id"] == str(doc.id)
    assert citation["doc_title"] == "Policy.pdf"
    assert citation["page"] == 2
    assert "Remote work" in citation["snippet"]
    assert "file.sol" not in citation["snippet"]
