# Data retention and erasure

Product policy for pilots and DPA annexes. Implementation defaults: **no automated purge job in v1** until a contract requires it.

Canonical ADR: [ADR-017](../engineering/decisions.md#adr-017-data-retention-and-erasure-eu-pilot-policy).

## Summary

| Category | Retention (pilot default) | User-facing control |
| --- | --- | --- |
| Retrieval audit (`rag_audit_logs`) | **90 days** (contract may shorten) | Not exposed in UI; contains question text, not chunk bodies |
| Chat history | Until user deletes session | Session delete in UI → `DELETE` chat session (messages cascade) |
| Knowledge base files | Customer-defined | Org admin upload/delete; MinIO + Postgres cascade |
| LLM answer cache (Redis) | **24 h** TTL | Transparent; invalidated on ACL/ingest/delete |

## Erasure

- **Leave one organization:** v1 has invite/add members only; revoking access may require operator SQL or a future remove-member API. Global `users` row may remain for other orgs.
- **Delete global user (operator):** removing `users` row cascades that user’s chat sessions and `rag_audit_logs` rows ([data-model.md](data-model.md)).
- **Delete organization:** export backup first; purge `rag_audit_logs` for the org (FK **RESTRICT** on org), then corpus and org row — see private pilot runbook.

## EU / GDPR mapping (high level)

- **Purpose:** RAG Q&A, quota metering (`tokens_used`), security audit of retrieval (chunk UUIDs).
- **Minimization:** audit stores chunk IDs, not document text; inspect off in production by default.
- **Automated retention:** recommended 90-day audit TTL — **schedule job when pilot signs** (tracked in ADR-017).

Embedding or model changes do not erase audit history; reindex runbook: `docs/_private/operations/embedding-model-migration.md` (private).
