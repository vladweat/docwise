"""Pure claim-to-source support scoring for the evaluation harness."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
import re
import unicodedata


class CitationJudgeError(ValueError):
    """The citation judge returned a JSON object with an unusable shape."""


@dataclass(frozen=True)
class CitationReferenceMetrics:
    """Deterministic validity counts for inline references in an answer."""

    valid_references: int
    total_references: int

    @property
    def precision(self) -> float | None:
        if self.total_references == 0:
            return None
        return self.valid_references / self.total_references


_CITATION_LOCATION_RE = re.compile(
    r",\s*(?:стр(?:\.|аница)?|page|раздел|section)\s*[:.]?\s*",
    re.IGNORECASE,
)
_CRITICAL_SOURCE_TOKENS = frozenset(
    {
        "not",
        "no",
        "never",
        "none",
        "neither",
        "without",
        "cannot",
        "must",
        "shall",
        "should",
        "may",
        "might",
        "can",
        "only",
        "required",
        "prohibited",
        "allowed",
        "allow",
        "не",
        "нет",
        "ни",
        "никогда",
        "без",
        "нельзя",
        "можно",
        "может",
        "могут",
        "должен",
        "должна",
        "должны",
        "обязан",
        "обязана",
        "обязаны",
        "только",
        "требуется",
        "запрещено",
        "разрешено",
    }
)


def citation_reference_metrics(
    answer: str,
    sources: Sequence[Mapping[str, object]],
) -> CitationReferenceMetrics:
    """Count inline source references that resolve to a retrieved title and location.

    This verifies only that each bracketed page/section reference points to a
    retrieved source. It does not establish that the source semantically
    supports any claim in the answer.
    """
    known_references = {
        _normalize_reference(label)
        for source in sources
        if (label := _source_reference_label(source)) is not None
    }
    references = list(_citation_references(answer or ""))
    valid_count = sum(
        _normalize_reference(reference) in known_references for reference in references
    )
    return CitationReferenceMetrics(valid_references=valid_count, total_references=len(references))


def _citation_references(answer: str) -> Iterator[str]:
    start: int | None = None
    depth = 0
    for index, character in enumerate(answer):
        if character == "\n":
            start = None
            depth = 0
        elif character == "[":
            if depth == 0:
                start = index
            depth += 1
        elif character == "]" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                reference = answer[start + 1 : index]
                if _CITATION_LOCATION_RE.search(reference):
                    yield reference
                start = None


def _source_reference_label(source: Mapping[str, object]) -> str | None:
    title = source.get("doc_title")
    if not isinstance(title, str) or not title.strip() or "\n" in title or "\r" in title:
        return None
    page = source.get("page")
    if isinstance(page, int) and not isinstance(page, bool) and page > 0:
        return f"{title}, стр. {page}"
    section = source.get("section")
    if isinstance(section, str) and section.strip():
        return f"{title}, раздел: {section.strip()}"
    return None


def _normalize_reference(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split())


def citation_support_rate(
    payload: object,
    *,
    source_count: int,
    sources: list[str] | None = None,
) -> float | None:
    """Return the fraction of factual claims linked to a valid supporting source."""
    if not isinstance(payload, Mapping) or not isinstance(payload.get("claims"), list):
        raise CitationJudgeError("citation judge returned an invalid claims list")
    claims = payload["claims"]
    if not claims:
        return None

    supported = 0
    for claim in claims:
        if not isinstance(claim, Mapping) or not str(claim.get("claim", "")).strip():
            raise CitationJudgeError("citation judge returned an invalid claim")
        indexes = claim.get("source_indexes")
        if not isinstance(indexes, list) or any(
            not isinstance(index, int) or isinstance(index, bool) for index in indexes
        ):
            raise CitationJudgeError("citation judge returned invalid source indexes")
        has_valid_source_index = any(0 <= index < source_count for index in indexes)
        has_verbatim_source_support = any(
            _normalized_claim_is_present(str(claim["claim"]), source)
            for source in (sources or [])
        )
        if has_valid_source_index or has_verbatim_source_support:
            supported += 1
    return supported / len(claims)


def _normalized_claim_is_present(claim: str, source: str) -> bool:
    """Recognize an almost verbatim claim when the LLM judge misses its source."""
    claim_text = re.sub(r"\[[^\]]*\]", " ", claim)
    claim_tokens = _normalize_text(claim_text).split()
    if not claim_tokens:
        return False

    source_sentences = re.split(r"(?<=[.!?。！？])\s+|[\n;]+", source)
    for sentence in source_sentences:
        source_tokens = _normalize_text(sentence).split()
        if not source_tokens or _critical_tokens(claim_tokens) != _critical_tokens(source_tokens):
            continue
        if len(claim_tokens) == 1:
            if claim_tokens[0] in source_tokens:
                return True
            continue

        for start, token in enumerate(source_tokens):
            if token != claim_tokens[0]:
                continue
            claim_index = 1
            skipped_source_tokens = 0
            for source_token in source_tokens[start + 1 :]:
                if source_token == claim_tokens[claim_index]:
                    claim_index += 1
                    if claim_index == len(claim_tokens):
                        return True
                else:
                    skipped_source_tokens += 1
                    if skipped_source_tokens > 1:
                        break
    return False


def _critical_tokens(tokens: Sequence[str]) -> list[str]:
    return [
        token
        for token in tokens
        if token in _CRITICAL_SOURCE_TOKENS or re.fullmatch(r"\d+", token)
    ]


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("’", "'")
    normalized = normalized.replace("can't", "can not").replace("won't", "will not")
    normalized = normalized.replace("shan't", "shall not")
    normalized = re.sub(r"n't\b", " not", normalized)
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))
