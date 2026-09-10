"""ACL leak checks for the golden set. Never log restricted chunk bodies."""

from __future__ import annotations


def leaked_doc_ids(retrieved_doc_ids: list[str], must_not_doc_ids: list[str]) -> list[str]:
    """Return retrieved ids that the eval user is forbidden to see."""
    banned = {str(item) for item in must_not_doc_ids if str(item).strip()}
    if not banned:
        return []
    leaks: list[str] = []
    seen: set[str] = set()
    for doc_id in retrieved_doc_ids:
        key = str(doc_id)
        if key in banned and key not in seen:
            seen.add(key)
            leaks.append(key)
    return leaks
