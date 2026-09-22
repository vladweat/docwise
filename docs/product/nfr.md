# Non-functional requirements

Supplements [srs.md](srs.md). Performance thresholds below are guidelines for local Docker Compose / one organization, not a cloud SLA. Zero cross-org leaks are mandatory (see [tenancy.md](../platform/tenancy.md)).

## Security

- Auth required on all `/api/v1/*` except login/register/google, SSO login/ACS and Stripe webhook. `/health` and `/ready` are public.
- Session only in httpOnly cookies; Bearer not accepted. CSRF header/Origin when `SameSite=None`. Cookies **host-only** ([ADR-015](../engineering/decisions.md)).
- RBAC enforcement: SQL filter `organization_id` **and** `access_roles && allowed_roles` on pgvector/FTS **before** LLM. Prompt is not ACL mechanism and does not isolate companies. Plan, SAML attribute, and hostname do not replace this filter; hostname may only pin org.
- Same ACL on list / status / raw / search / inspect / chat, plus same `org_id`.
- Do not confirm existence of foreign file (“document X is hidden”), including another organization’s file.
- LLM cache key includes `org_id`, index generation, and caller’s `allowed_roles` (otherwise cache is ACL hole, cross-tenant, or stale after corpus change).
- Secrets only in env. Do not commit `.env`, keys, NDA dumps. Stripe keys not required for Compose (`BILLING_PROVIDER=dev`).
- Audit: `rag_audit_logs` without chunk body (UUIDs after reranker only). Inspect in production behind `ENABLE_SEARCH_INSPECT` (off by default); foreign file not confirmed.
- Upload: size limit (guideline 50 MB), PDF and DOCX, SHA-256, rate limit by IP/user. Org quota: PDF pages or DOCX logical sections → `402` (not `429`).
- Chat: period token quota → refusal before retrieval. Chat rate limit → `429`.
- XSS: do not render HTML from PDF/LLM as `dangerouslySetInnerHTML` without sanitization. Answer markdown — safe renderer.

## Ingestion reliability

- Parsing and embeddings only in Celery, not in upload handler.
- Redis lock `indexing_lock:{document_id}`. Task retry is idempotent.
- Celery: `acks_late`, `worker_prefetch_multiplier=1`, `soft_time_limit` 20 min / `time_limit` 25 min, up to 3 retries with backoff (do not retry `SoftTimeLimitExceeded` / `TimeLimitExceeded`).
- Worker crash: `failed` + `last_error`, index either complete or removed (no “half-ready” document with status ready).
- Cascading DELETE: Postgres (document + chunks), MinIO object. Log partial success and retry index removal.

## Performance (guidelines)

| Operation | Target |
| --- | --- |
| Upload ACK | < 2 s to `201` + `pending` (no parsing) |
| Ingest PDF ~20 pages | minutes, not hours; progress via status |
| Chat TTFT (citations) | first SSE citations before token stream |
| Retrieval Top-4 | dense+sparse+RRF+rerank on CPU, no scrolling full collection |

Forbidden: `scroll` all corpus points into RAM for BM25.

## Observability

- JSON logs with redaction (tokens, passwords, long PDF text).
- `rag_audit_logs`: query, user, chunk UUIDs after reranker, latency_ms, tokens_used, feedback. Written by chat and inspect. Not UUID and not full text.
- `/health` — liveness (`{"status":"ok"}`). `/ready` — Postgres + pgvector + Redis + MinIO (`200` / `503`). Billing field: `dev` (explicit) or `stripe` (no keys — not `ok`).

## RAG quality

- Faithfulness: answer only from Top-4. Otherwise fixed refusal phrase.
- Every factual clause — citation `{doc_id, page}`.
- Eval: [evaluation.md](evaluation.md). Release: Faithfulness ≥ 0.8 and **zero** ACL leaks on `must_not_doc_ids`. Latest live run **2026-09-21** (FTS migration `012`, 35 cases): Faithfulness 1.000, Context Precision 0.994, Answer Relevance 0.725, page hit 0.929, ACL PASS — [reports/rag_benchmark.md](../../reports/rag_benchmark.md). Zero leaks of `must_not` documents from **another** org, even with tag `all`.

## Compatibility and i18n

- Documents: EN/RU corporate text.
- UI strings and LLM refusals: Russian or English — one interface language per organization. i18n framework not required.
- API identifiers and code — English.
