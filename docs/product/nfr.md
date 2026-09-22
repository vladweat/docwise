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
- Audit: `rag_audit_logs` without chunk body (UUIDs after reranker only). Inspect in production behind `ENABLE_SEARCH_INSPECT` (off by default); foreign file not confirmed. Retention and erasure policy: [data-retention.md](../platform/data-retention.md) ([ADR-017](../engineering/decisions.md#adr-017-data-retention-and-erasure-eu-pilot-policy)).
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

## Capacity and scaling (v1 guidelines)

Not a cloud SLA. Shared B2B deploy: one Postgres holds **all tenants’** `document_chunks`; dense search uses a **global** HNSW on `embedding`, with `organization_id` and `access_roles` applied in SQL on every query ([retrieval.md](../pipeline/retrieval.md)).

| Topic | v1 behavior | Pilot guidance |
| --- | --- | --- |
| Dense index | Global HNSW + per-query ACL filter | Before each dense query: `SET LOCAL hnsw.iterative_scan` (`HNSW_ITERATIVE_SCAN`, default `relaxed_order`) and `hnsw.max_scan_tuples` (`HNSW_MAX_SCAN_TUPLES`, default **20000**) so filtered neighbors are not truncated |
| Corpus size | ~one chunk per PDF page / DOCX section (typical) | **Per org:** plan page quotas (Starter 200 / Team 2000 / Enterprise 20000 pages) bound ingest; expect **roughly similar order of chunks** unless many sections per page |
| Comfort zone (single deploy) | Compose / one Postgres 15 + pgvector, CPU rerank | **Validated in dev:** demo + eval corpora (hundreds of chunks total). **Pilot target:** up to **~10k–50k chunks total** across all orgs on one instance with default `HNSW_MAX_SCAN_TUPLES`; Team-scale **per-org** corpus is the design center |
| Degradation signs | Rising dense latency, empty dense after filter, inspect shows weak dense stage | Raise `HNSW_MAX_SCAN_TUPLES` temporarily; measure p95 retrieval (`rag_audit_logs.latency_ms`, see pilot `make check-pilot-alerts`); long-term — org-partitioned ANN (see engineering backlog / ADR when corpus forces it) |
| Load baseline (pilot) | Not a SLA | **2026-09-22 (Compose dev, 135 chunks / 4 orgs):** hybrid `retrieve` p95 **2051 ms** (28×2 sequential, no LLM) — [reports/load_baseline.md](../../reports/load_baseline.md). `HNSW_MAX_SCAN_TUPLES=20000` unchanged. Re-run `make load-baseline` after corpus growth; chat soak → p95 in `rag_audit_logs` via `make check-pilot-alerts` |
| Redis | Broker, result backend, rate limits, indexing locks, refresh tokens | **Single instance in Compose — SPOF** for queue and sessions; no HA in v1. Postgres + MinIO are the durable stores; rebuild Redis loses in-flight queue work, not the corpus |
| Celery workers | Horizontal scale possible; one worker common on pilot | Ingest throughput scales with workers; embedding CPU is the bottleneck |

FTS (GIN on `tsvector`) scales with filtered row count per org; still no full-table scroll into RAM.

## Observability

- JSON logs with redaction (tokens, passwords, long PDF text).
- `rag_audit_logs`: query, user, chunk UUIDs after reranker, latency_ms, tokens_used, feedback. Written by chat and inspect. Not UUID and not full text.
- `/health` — liveness (`{"status":"ok"}`). `/ready` — Postgres + pgvector + Redis + MinIO (`200` / `503`). Billing field: `dev` (explicit) or `stripe` (no keys — not `ok`).

## RAG quality

- Faithfulness: answer only from Top-4. Otherwise fixed refusal phrase.
- Every factual clause — citation `{doc_id, page}`.
- Release gates, how to run, and live scores: [evaluation.md](evaluation.md) and [reports/rag_benchmark.md](../../reports/rag_benchmark.md). Zero leaks of `must_not` documents from **another** org, even with tag `all`.

## Compatibility and i18n

- Documents: EN/RU corporate text.
- UI strings and LLM refusals: Russian or English — one interface language per organization. i18n framework not required.
- API identifiers and code — English.
