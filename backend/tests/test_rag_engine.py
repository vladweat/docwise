"""BM25 / RRF port from ChainWise — no GPU, no live LLM, no Solidity heuristics."""

from pathlib import Path

from app.services.retrieval import (
    RRF_K,
    bm25_scores,
    reciprocal_rank_fusion,
    tokenize,
)

RETRIEVAL_PY = Path(__file__).resolve().parents[1] / "app" / "services" / "retrieval.py"


def test_tokenize_keeps_identifiers_and_cyrillic():
    tokens = tokenize("function onlyOwner() { msg.sender; }")
    assert "function" in tokens
    assert "onlyowner" in tokens
    assert "msg" in tokens
    assert "sender" in tokens
    cyrillic = tokenize("контракт безопасен?")
    assert "контракт" in cyrillic
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


def test_no_solidity_heuristics_in_retrieval():
    source = RETRIEVAL_PY.read_text()
    assert "is_overview_question" not in source
    assert "citations_are_interface_stubs" not in source
    assert "select_overview_code_chunks" not in source
    assert "scroll_contract_chunks" not in source
    assert "load_search_pool" not in source
    assert "_analysis_chunk" not in source
    assert "primary_contract_names" not in source
