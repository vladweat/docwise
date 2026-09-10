"""Load and validate `golden_dataset.json`."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

MIN_CASES = 30


class GoldenDatasetError(ValueError):
    """Raised when the golden set is missing required fields."""


@dataclass(frozen=True)
class GoldenCase:
    id: str
    question: str
    ground_truth_answer: str
    target_doc_id: str
    target_page: int | None = None
    must_not_doc_ids: tuple[str, ...] = ()
    kind: str = "positive"

    @property
    def is_acl_negative(self) -> bool:
        return self.kind == "acl_negative"


@dataclass(frozen=True)
class GoldenDataset:
    eval_user_email: str
    items: list[GoldenCase] = field(default_factory=list)

    @property
    def acl_negatives(self) -> list[GoldenCase]:
        return [item for item in self.items if item.is_acl_negative]

    @property
    def positives(self) -> list[GoldenCase]:
        return [item for item in self.items if not item.is_acl_negative]


def default_dataset_path() -> Path:
    return Path(__file__).resolve().parent / "golden_dataset.json"


def load_golden_dataset(path: Path | None = None) -> GoldenDataset:
    dataset_path = path or default_dataset_path()
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GoldenDatasetError("golden_dataset.json must be an object with an items array")
    email = str(raw.get("eval_user_email") or "").strip()
    if not email:
        raise GoldenDatasetError("eval_user_email is required")
    items_raw = raw.get("items")
    if not isinstance(items_raw, list):
        raise GoldenDatasetError("items must be a list")
    items = [_parse_case(entry, index) for index, entry in enumerate(items_raw)]
    if len(items) < MIN_CASES:
        raise GoldenDatasetError(f"golden set must contain at least {MIN_CASES} items, got {len(items)}")
    return GoldenDataset(eval_user_email=email, items=items)


def _parse_case(entry: object, index: int) -> GoldenCase:
    if not isinstance(entry, dict):
        raise GoldenDatasetError(f"items[{index}] must be an object")
    question = str(entry.get("question") or "").strip()
    ground_truth = str(entry.get("ground_truth_answer") or "").strip()
    target_doc_id = str(entry.get("target_doc_id") or "").strip()
    if not question or not ground_truth or not target_doc_id:
        raise GoldenDatasetError(
            f"items[{index}] needs question, ground_truth_answer, and target_doc_id"
        )
    _require_uuid(target_doc_id, f"items[{index}].target_doc_id")
    target_page = entry.get("target_page")
    page: int | None
    if target_page is None or target_page == "":
        page = None
    else:
        page = int(target_page)
        if page < 1:
            raise GoldenDatasetError(f"items[{index}].target_page must be >= 1")
    must_not_raw = entry.get("must_not_doc_ids") or []
    if not isinstance(must_not_raw, list):
        raise GoldenDatasetError(f"items[{index}].must_not_doc_ids must be a list")
    must_not: list[str] = []
    for item in must_not_raw:
        value = str(item).strip()
        if not value:
            continue
        _require_uuid(value, f"items[{index}].must_not_doc_ids")
        must_not.append(value)
    kind = str(entry.get("kind") or "positive").strip() or "positive"
    if kind not in {"positive", "acl_negative"}:
        raise GoldenDatasetError(f"items[{index}].kind must be positive or acl_negative")
    case_id = str(entry.get("id") or f"q-{index + 1}").strip()
    return GoldenCase(
        id=case_id,
        question=question,
        ground_truth_answer=ground_truth,
        target_doc_id=target_doc_id,
        target_page=page,
        must_not_doc_ids=tuple(must_not),
        kind=kind,
    )


def _require_uuid(value: str, field_name: str) -> None:
    try:
        UUID(value)
    except (ValueError, TypeError) as exc:
        raise GoldenDatasetError(f"{field_name} must be a UUID") from exc
