"""Golden eval set: schema, size, ACL negatives. No live LLM."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from uuid import UUID

import pytest

from app.services.retrieval import NO_CONTEXT_ANSWER

HR_ID = "aaaaaaaa-1111-4111-8111-000000000005"
FINANCE_ID = "aaaaaaaa-1111-4111-8111-000000000006"
RESTRICTED = {HR_ID, FINANCE_ID}


def _eval_dir() -> Path:
    env = os.environ.get("EVAL_DIR")
    if env:
        path = Path(env)
        if (path / "golden_dataset.json").is_file():
            return path
    here = Path(__file__).resolve()
    candidates = [here.parents[2] / "eval", Path("/eval")]
    for path in candidates:
        if (path / "golden_dataset.json").is_file():
            return path
    pytest.fail("eval/golden_dataset.json not found; mount eval/ or run tests from the repo")


def _load_module(name: str):
    path = _eval_dir() / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"eval_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_golden_dataset_meets_eval_contract():
    dataset_mod = _load_module("dataset")
    corpus_mod = _load_module("corpus")
    golden = dataset_mod.load_golden_dataset(_eval_dir() / "golden_dataset.json")

    assert golden.eval_user_email == "eval-employee@docwise.example.com"
    assert len(golden.items) >= dataset_mod.MIN_CASES
    assert len(golden.acl_negatives) >= 5
    assert len(golden.positives) >= 20

    known_ids = set(corpus_mod.CATALOG_BY_ID)
    seen_ids: set[str] = set()
    for item in golden.items:
        assert item.id not in seen_ids
        seen_ids.add(item.id)
        UUID(item.target_doc_id)
        assert item.target_doc_id in known_ids
        assert item.target_page is not None and item.target_page >= 1
        assert RESTRICTED.issubset(set(item.must_not_doc_ids))
        if item.is_acl_negative:
            assert item.target_doc_id in RESTRICTED
            assert item.ground_truth_answer == NO_CONTEXT_ANSWER
        else:
            assert item.target_doc_id not in RESTRICTED


def test_context_precision_formula():
    metrics = _load_module("metrics")
    assert metrics._precision_at_k([]) == 0.0
    assert metrics._precision_at_k([False, False]) == 0.0
    assert metrics._precision_at_k([True, False, True]) == pytest.approx((1.0 + 2.0 / 3.0) / 2.0)


def test_acl_leak_helper_and_ci_does_not_run_eval():
    acl = _load_module("acl")
    assert acl.leaked_doc_ids(["a", "b", "a"], ["b", "c"]) == ["b"]
    assert acl.leaked_doc_ids(["a"], ["x"]) == []

    ci = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():
        ci = Path("/eval").parent / ".github" / "workflows" / "ci.yml"
    text = ci.read_text(encoding="utf-8") if ci.is_file() else ""
    if ci.is_file():
        assert "run_eval.py" not in text
        assert "golden_dataset.json" not in text
        assert "seed_demo.py" not in text
        assert "pragma_parser" not in text
        assert "risk_scorer" not in text
        assert "--cov=" not in text
        assert "ruff check" in text
        assert "tsc --noEmit" in text
        assert "pytest tests/" in text


def test_demo_accounts_split_employee_and_hr_acl():
    corpus = _load_module("corpus")
    accounts = {item.email: item for item in corpus.DEMO_ACCOUNTS}
    employee = accounts["employee@docwise.example.com"]
    hr = accounts["hr@docwise.example.com"]
    assert employee.role == "employee"
    assert list(employee.departments) == []
    assert hr.role == "employee"
    assert "hr" in hr.departments

    specs = {item.slug: item for item in corpus.demo_specs()}
    assert set(specs) == {
        "employee-handbook",
        "leave-policy",
        "expense-policy",
        "engineering-onboarding",
        "hr-compensation",
        "finance-q4",
        "security-runbook",
        "recruiting-faq",
        "travel-policy",
        "it-access-checklist",
        "operations-handbook",
        "people-compendium",
    }
    assert specs["employee-handbook"].access_roles == ("all",)
    assert specs["hr-compensation"].access_roles == ("hr",)
    assert specs["finance-q4"].access_roles == ("finance",)
    assert str(specs["employee-handbook"].id) != str(corpus.HANDBOOK_ID)


def test_golden_json_is_valid_utf8():
    payload = json.loads((_eval_dir() / "golden_dataset.json").read_text(encoding="utf-8"))
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) >= 30
