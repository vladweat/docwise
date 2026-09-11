"""Shared text helpers for ingest budget, BM25 lexicon, and role tags.

Chunk size uses whitespace tokens (independent of FastEmbed). BM25 uses a
lexical split (latin words, digits, Cyrillic) — not a Solidity identifier parser.
`access_roles` and membership `departments` share one tag syntax.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

INGEST_TOKEN_RE = re.compile(r"\S+", re.UNICODE)
LEXICAL_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\W\d_]+", re.UNICODE)
ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")
MAX_ROLE_TAGS = 16


class InvalidRoleTag(ValueError):
    """Tag does not match ROLE_RE."""


class TooManyRoleTags(ValueError):
    """More tags than MAX_ROLE_TAGS (or the caller cap)."""


def ingest_tokens(text: str) -> list[str]:
    """Whitespace-delimited tokens for page/section chunk budgets."""
    return INGEST_TOKEN_RE.findall(text)


def count_ingest_tokens(text: str) -> int:
    return len(ingest_tokens(text))


def lexical_tokens(text: str) -> list[str]:
    """Lowercased words for BM25 over PDF/DOCX text."""
    return [token.lower() for token in LEXICAL_TOKEN_RE.findall(text)]


def normalize_role_tags(raw: Iterable[str], *, max_count: int = MAX_ROLE_TAGS) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        role = item.strip().lower()
        if not role:
            continue
        if not ROLE_RE.match(role):
            raise InvalidRoleTag(role)
        if role not in seen:
            seen.add(role)
            normalized.append(role)
    if len(normalized) > max_count:
        raise TooManyRoleTags(len(normalized))
    return normalized
