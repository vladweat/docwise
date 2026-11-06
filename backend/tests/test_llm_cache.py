from uuid import UUID

from app.services.chat.prompt import load_cached_answer


def test_prompt_change_does_not_read_answers_from_previous_cache_version(monkeypatch):
    read_keys: list[str] = []

    def redis_get(key: str) -> dict | None:
        read_keys.append(key)
        if key.startswith("llm_cache:v4:"):
            return {
                "answer": "answer generated with the previous prompt",
                "citations": [],
                "chunk_ids": [],
            }
        return None

    monkeypatch.setattr("app.services.chat.prompt.redis_get", redis_get)

    result = load_cached_answer(
        "What does the policy say?",
        ["all"],
        organization_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    )

    assert result is None
    assert len(read_keys) == 1
    assert not read_keys[0].startswith("llm_cache:v4:")
