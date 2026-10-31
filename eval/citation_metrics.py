"""Pure claim-to-source support scoring for the evaluation harness."""

from __future__ import annotations

from collections.abc import Mapping
import re
import unicodedata


class CitationJudgeError(ValueError):
    """The citation judge returned a JSON object with an unusable shape."""


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
        if not isinstance(indexes, list) or any(not isinstance(index, int) or isinstance(index, bool) for index in indexes):
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
    source_tokens = _normalize_text(source).split()
    if not claim_tokens:
        return False
    if len(claim_tokens) == 1:
        return claim_tokens[0] in source_tokens

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


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))
