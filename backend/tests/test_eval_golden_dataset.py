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
    assert len(golden.acl_negatives) >= 12
    assert len(golden.positives) >= 20

    known_ids = set(corpus_mod.CATALOG_BY_ID)
    restricted_ids = set(corpus_mod.restricted_doc_ids())
    evaluator_accounts = {account.email: account for account in corpus_mod.EVAL_ACCOUNTS}
    seen_ids: set[str] = set()
    for item in golden.items:
        assert item.id not in seen_ids
        seen_ids.add(item.id)
        assert item.eval_user_email is None or item.eval_user_email in evaluator_accounts
        if item.is_no_answer:
            assert item.target_doc_id is None
            assert item.ground_truth_answer == ""
            assert item.target_page is None and item.target_section is None
            continue
        UUID(item.target_doc_id)
        assert item.target_doc_id in known_ids
        assert (item.target_page is not None and item.target_page >= 1) or item.target_section
        forbidden = set(item.must_not_doc_ids)
        if item.is_acl_negative:
            assert item.target_doc_id in restricted_ids
            assert item.target_doc_id in forbidden
            assert item.ground_truth_answer == NO_CONTEXT_ANSWER
        else:
            account = evaluator_accounts.get(item.eval_user_email or "")
            allowed_roles = set(account.departments) if account else set()
            allowed_ids = {
                doc_id
                for doc_id in restricted_ids
                if set(corpus_mod.CATALOG_BY_ID[doc_id].access_roles) & allowed_roles
            }
            assert forbidden == restricted_ids - allowed_ids
            if item.target_doc_id in restricted_ids:
                assert item.eval_user_email is not None
                assert item.target_doc_id not in forbidden


def test_acl_dataset_covers_allowed_and_denied_access_for_each_restricted_department():
    corpus = _load_module("corpus")
    dataset = _load_module("dataset").load_golden_dataset(_eval_dir() / "golden_dataset.json")
    accounts = {account.email: account for account in corpus.EVAL_ACCOUNTS}
    restricted = {
        "hr": str(corpus.HR_COMP_ID),
        "finance": str(corpus.FINANCE_ID),
        "legal": str(corpus.LEGAL_ID),
        "security": str(corpus.SECURITY_RESTRICTED_ID),
        "engineering": str(corpus.ENGINEERING_RESTRICTED_ID),
    }

    specs = {str(spec.id): spec for spec in corpus.CATALOG}
    assert len(corpus.CATALOG) == 10
    assert len(dataset.items) == 92
    assert len(dataset.positives) == 45
    assert len(dataset.no_answer_cases) == 6
    assert len(dataset.acl_negatives) == 41
    assert accounts[dataset.eval_user_email].departments == ()

    for department, document_id in restricted.items():
        assert specs[document_id].access_roles == (department,)
        assert any(
            item.eval_user_email is None
            and item.target_doc_id == document_id
            and item.is_acl_negative
            for item in dataset.items
        )
        account = next(account for account in accounts.values() if account.departments == (department,))
        assert any(
            item.eval_user_email == account.email
            and item.target_doc_id == document_id
            and not item.is_acl_negative
            and document_id not in item.must_not_doc_ids
            for item in dataset.items
        )
        for other_department, other_document_id in restricted.items():
            if department == other_department:
                continue
            assert any(
                item.eval_user_email == account.email
                and item.target_doc_id == other_document_id
                and item.is_acl_negative
                and other_document_id in item.must_not_doc_ids
                for item in dataset.items
            )


def test_new_restricted_pdf_fixtures_contain_the_facts_used_by_acl_cases():
    import fitz

    corpus = _load_module("corpus")
    specs = {spec.slug: spec for spec in corpus.CATALOG}
    expected = {
        "legal-templates": ("contract-redline", "legal-review"),
        "security-controls": ("rotation window", "24 hours"),
        "engineering-release": ("canary window", "30 minutes"),
    }
    for slug, phrases in expected.items():
        pdf = fitz.open(stream=corpus.build_pdf(specs[slug]), filetype="pdf")
        text = " ".join(page.get_text() for page in pdf).lower()
        pdf.close()
        for phrase in phrases:
            assert phrase in text


def test_multilingual_docx_fixture_preserves_russian_text_and_has_expected_sections():
    from io import BytesIO
    from docx import Document as DocxDocument

    corpus = _load_module("corpus")
    dataset = _load_module("dataset").load_golden_dataset(_eval_dir() / "golden_dataset.json")
    spec = next(item for item in corpus.CATALOG if item.slug == "ru-operations-guide")
    document = DocxDocument(BytesIO(corpus.build_docx(spec)))
    text = " ".join(paragraph.text for paragraph in document.paragraphs)
    sections = [paragraph.text for paragraph in document.paragraphs if paragraph.style.name.startswith("Heading")]

    assert "Рабочее время" in text
    assert "09:00" in text
    assert "Рабочее время" in sections
    assert any(item.target_section == "Рабочее время" for item in dataset.positives)


def test_dataset_parser_accepts_a_docx_section_target_without_a_fake_page_number():
    dataset = _load_module("dataset")
    case = dataset._parse_case(
        {
            "id": "docx-section",
            "question": "Во сколько начинается рабочий день?",
            "ground_truth_answer": "В 09:00.",
            "target_doc_id": "aaaaaaaa-1111-4111-8111-000000000010",
            "target_section": "Рабочее время",
        },
        0,
    )

    assert case.target_page is None
    assert case.target_section == "Рабочее время"


def test_dataset_parser_accepts_no_answer_without_target_document():
    dataset = _load_module("dataset")

    case = dataset._parse_case(
        {
            "id": "no-answer-en",
            "kind": "no_answer",
            "question": "What is the boiling point of gallium?",
            "ground_truth_answer": "",
            "source_dataset": "synthetic-no-answer",
        },
        0,
    )

    assert case.target_doc_id is None
    assert case.is_no_answer
    assert not case.is_acl_negative


def test_no_answer_cases_are_not_counted_as_answerable_positives():
    dataset = _load_module("dataset")
    golden = dataset.load_golden_dataset(_eval_dir() / "golden_dataset.json")

    assert len(golden.no_answer_cases) == 6
    assert all(case.kind == "positive" for case in golden.positives)


def test_load_baseline_runs_each_positive_case_as_its_assigned_persona(monkeypatch):
    load_baseline = _load_module("load_baseline")
    calls = []
    questions = [
        ("eval-hr@docwise.example.com", "What is the L3 salary band?"),
        ("eval-legal@docwise.example.com", "What does the redline require?"),
    ]
    monkeypatch.setattr(
        load_baseline,
        "_one_retrieval",
        lambda email, question: calls.append((email, question)) or 10.0,
    )

    latencies = load_baseline._run_load(questions, rounds=1, concurrency=1)

    assert latencies == [10.0, 10.0]
    assert calls == questions


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


def test_demo_reset_is_scoped_to_the_seeded_fixture_catalog():
    corpus = _load_module("corpus")
    seeded_ids = {item.id for item in corpus.demo_specs()}
    assert len(seeded_ids) == 12
    assert corpus.demo_fixture_document_ids() == seeded_ids
    assert corpus.DEMO_ORG_SLUG == "demo"


@pytest.mark.parametrize("args", [["--reset"], ["--confirm-reset"]])
def test_demo_reset_requires_both_explicit_confirmation_flags(monkeypatch, args):
    seed_script = _load_module("seed_demo")
    monkeypatch.setattr(sys, "argv", ["seed_demo.py", *args])
    with pytest.raises(SystemExit) as error:
        seed_script.main()
    assert error.value.code == 2


def test_golden_json_is_valid_utf8():
    payload = json.loads((_eval_dir() / "golden_dataset.json").read_text(encoding="utf-8"))
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) >= 30


def test_eval_report_provenance_is_stable(monkeypatch):
    provenance = _load_module("provenance")
    dataset = _eval_dir() / "golden_dataset.json"
    digest = provenance.dataset_sha256(dataset)
    assert len(digest) == 64
    monkeypatch.setenv("DOCWISE_GIT_REVISION", "abc1234")
    assert provenance.code_revision() == "abc1234"
