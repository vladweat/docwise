# Data retention and erasure

Product policy for pilots and DPA annexes. Retrieval audit rows are purged automatically by a daily Celery Beat job.

Canonical ADR: [ADR-017](../engineering/decisions.md#adr-017-data-retention-and-erasure-eu-pilot-policy).

## Summary

| Category | Retention (pilot default) | User-facing control |
| --- | --- | --- |
| Retrieval audit (`rag_audit_logs`) | **90 days** by default (`AUDIT_LOG_RETENTION_DAYS`, minimum 1; contract may shorten) | Not exposed in UI; contains query and optional feedback comment, not chunk bodies |
| Chat history | Until user deletes session | Session delete in UI → `DELETE` chat session (messages cascade) |
| Knowledge base files | Customer-defined | Org admin upload/delete; relational cascade + durable MinIO deletion outbox |
| LLM answer cache (Redis) | **24 h** TTL | Transparent; invalidated on ACL/ingest/delete |

## Erasure

- **Leave one organization:** v1 has invite/add members only; revoking access may require operator SQL or a future remove-member API. Global `users` row may remain for other orgs.
- **Delete global user (operator):** removing `users` row cascades that user’s chat sessions and `rag_audit_logs` rows ([data-model.md](data-model.md)).
- **Delete organization:** export backup first; purge `rag_audit_logs` for the org (FK **RESTRICT** on org), then corpus and org row — see private pilot runbook.

## EU / GDPR mapping (high level)

- **Purpose:** RAG Q&A, quota metering (`tokens_used`), security audit of retrieval (chunk UUIDs).
- **Minimization:** audit stores chunk IDs, not document text; inspect off in production by default.
- **Automated retention:** one Celery Beat scheduler deletes `rag_audit_logs` older than the configured cutoff daily at 03:15 UTC, in batches of 1000 rows. The index on `created_at` supports the purge query. Keep exactly one Beat service per deployment.

Embedding or model changes do not erase audit history; reindex runbook: `docs/_private/operations/embedding-model-migration.md` (private).

Document delete removes relational rows and inserts a storage cleanup request in one database
transaction. The scheduled worker removes the MinIO object and acknowledges the request; on
storage failure it keeps the request for retry. The deleted document is no longer available to
the API while object cleanup is pending. `make check-pilot-alerts` reports the pending backlog.
