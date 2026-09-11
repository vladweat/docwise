"""Ingest vs lexical tokenizers and shared role-tag syntax."""

import pytest

from app.services.text import (
    InvalidRoleTag,
    TooManyRoleTags,
    ingest_tokens,
    lexical_tokens,
    normalize_role_tags,
)


def test_ingest_keeps_punctuation_lexical_strips_it():
    text = "Leave: 140 days."
    assert ingest_tokens(text) == ["Leave:", "140", "days."]
    assert lexical_tokens(text) == ["leave", "140", "days"]


def test_normalize_role_tags_lowercases_and_dedupes():
    assert normalize_role_tags(["HR", "hr", " all "]) == ["hr", "all"]
    assert normalize_role_tags(["", "  "]) == []


def test_normalize_role_tags_rejects_invalid_and_overflow():
    with pytest.raises(InvalidRoleTag):
        normalize_role_tags(["HR Dept"])
    with pytest.raises(TooManyRoleTags):
        normalize_role_tags([f"role{i}" for i in range(17)])
