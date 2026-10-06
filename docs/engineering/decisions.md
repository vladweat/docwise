# Decisions (ADR)

The draft spec sometimes diverges from v1 implementation. Deviations are recorded below. Product invariants (RBAC **before** LLM, page-bounded chunking, hybrid + rerank, page citations) are **not** weakened.

## ADR-001. Application skeleton, not greenfield

**Decision:** Start from an existing stack (FastAPI, Celery, cookie auth, Compose, SSE client); domain ingest and retrieval are custom.

**Why:** Auth, queues, health, and frontend API client were already aligned. “80% ready” is true for plumbing and **false** for corpus RAG (single-artifact in-RAM search does not transfer). Vector index — pgvector in Postgres, not separate Qdrant-only path.

**Consequence:** plumbing reused; corpus RAG is custom. Internal roadmap — `docs/_private/` (not in public repo).

## ADR-002. Sync SQLAlchemy Session, not asyncpg

**Spec:** SQLAlchemy 2 + asyncpg.  
**v1 decision:** sync `Session`. FastAPI handlers may be sync. Heavy work — in Celery.

**Why:** Rewriting entire backend async “alongside” domain — risk, not value. asyncpg remains a possible future migration.

## ADR-003. UUID PK

**Spec:** UUID.  
**v1 decision:** UUID PK on all entities (`users`, `documents`, `document_chunks`, chats, audit). `chunk_id` — separate stable string for re-upsert. Celery `document_id` and Redis `indexing_lock:{document_id}` — UUID string.

**Why:** Matches spec, does not expose sequential ids, simpler when objects live in MinIO/cache/SSE. Existing integer `users` strings migrated by alembic `003`.

## ADR-004. SSE JSON envelopes `data:`, not named `event:`

**Spec:** `event: citations` / `event: message` / `event: done`.  
**Decision:** lines `data: {json}\n\n` with field `type`: `citations` → `token` → `meta` → `data: [DONE]`. Errors: `type: error`.

**Why:** Frontend already parses this protocol (`lib/api.ts`, SSE reader). Spec intent (citations before tokens) preserved.

## ADR-005. Hybrid search without corpus scroll

**Spec (draft):** native dense + BM25 in separate vector store.

**Decision:** use `reciprocal_rank_fusion` formula (`k=60`) as-is. `bm25_scores` — unit tests for RRF formula. In-memory BM25 over full corpus — no. Index — Postgres + pgvector + FTS.

1. pgvector cosine Top-25 + FTS (`document_chunks.search_vector`, `simple` + GIN) Top-25, both with ACL `organization_id` and `access_roles && allowed_roles`, then RRF.
2. Forbidden `SELECT` all corpus chunks into RAM (including for BM25).

Intermediate “BM25 only on dense Top-50” removed by migration `012`.

## ADR-006. `last_error`, status `processing`

**Spec:** `error_message`, status `processing`.  
**Decision:** field `last_error` on document. Ingest status — `processing` (not `indexing`).

## ADR-007. Cookie session

**Spec:** JWT in login response body.  
**v1 decision:** httpOnly cookies `dw_access` / `dw_refresh` only. Login/register/google/refresh return `UserResponse`, not `access_token` in JSON. `Authorization: Bearer` ignored. `role` / `departments` always from server (membership), not JWT. Access JWT ~15 min, no `role` claim.

With `COOKIE_SAMESITE=none` (SPA on different origin) mutations on `/api/v1` require `Origin` from `CORS_ORIGINS` **or** header `X-Requested-With: Docwise`. With `lax`/`strict` check not needed. Refresh in Redis: SET fail-closed (503), GET fail-closed. First registration on empty DB gets `admin`, others — `employee`. Google ID token without `email_verified=true` rejected.

## ADR-008. Embeddings bge-small

**Decision:** FastEmbed, model `BAAI/bge-small-en-v1.5` (384d cosine), reranker `BAAI/bge-reranker-base`.

## ADR-009. Postgres 15 + pgvector + MinIO

**Spec (draft):** Postgres 16 without pgvector, vectors outside SQL.  
**v1 decision:** image `pgvector/pgvector:pg15`. Extension `vector` enabled by migration. Files — MinIO, not API container disk (local fallback only behind flag for tests).

## ADR-010. pgvector instead of separate Qdrant

**Decision:** chunks and dense vectors live in Postgres (`document_chunks.embedding vector(384)`, cosine / HNSW). ACL — SQL `access_roles && allowed_roles` on every dense and sparse query. No Qdrant service in Compose.

**Why:** One datastore for metadata and vectors; pgvector is explicit stack tool. RBAC and hybrid+RRF invariants preserved.

## ADR-011. Duplicate `file_hash` → 409

**Spec / api.md:** `409` or return existing record.  
**v1 decision:** `POST /documents/upload` on matching SHA-256 bytes responds `409` with fixed `detail`, without `id`/`title`/ACL of existing document.

**Why:** unique `file_hash` is source of truth; returning existing row would leak metadata of file user must not see in `GET /documents` (e.g. admin uploaded HR-only PDF). Re-upload same file does not change `access_roles`.

After [ADR-012](#adr-012-shared-b2b-saas-org_id-as-outer-wall) uniqueness — `(org_id, file_hash)`. `409` only if duplicate **in current** organization; byte match at another customer not confirmed.

## ADR-012. Shared B2B SaaS: `org_id` as outer wall

**Spec (draft) / v1:** single tenant; multi-tenant out of scope.  
**Decision:** target product — **shared B2B SaaS** (many orgs on one deploy). Company isolation — `org_id` column in SQL, not prompt and not tag in `access_roles`. Roles/departments remain **inner** ACL inside org. Canonical: [tenancy.md](../platform/tenancy.md).

**Why:** `all` and `hr` are shared literals. Without `org_id` Globex employee sees Acme General/HR; LLM cache by roles alone serves foreign answer; global unique `file_hash` breaks identical template PDFs for two customers.

**Consequence:**

- User is global (email); `role` and `departments` on `organization_memberships`.
- Current org — in session, not chat/upload body.
- Chunks, documents, chat sessions, audit, MinIO key, and LLM cache key carry `org_id`.
- `require_admin` — admin of **current** org. No platform operator with foreign corpus access.
- Implementation — [tenancy.md](../platform/tenancy.md) (shared SaaS).

## ADR-013. Billing behind port; quotas in DB; default `dev`

**Product:** Stripe, billing, quotas as first-class org fields.  
**Decision:** plan, `billing_status`, quotas — organization columns. Payment provider (`BILLING_PROVIDER=dev` \| `stripe`) only writes these fields. Upload/chat/invite handlers read Postgres, not acquirer API.

`dev` — Compose default and non-`production`: org-admin changes plan without money (**Dev billing** badge). Stripe test keys **do not** replace `dev` (need account and network to `api.stripe.com`; often unavailable from some regions). Live Stripe is not required for local/portfolio acceptance. `stripe` adapter in code OK; CI without network. YooKassa — separate provider on the same port.

Codes: quota → `402`; feature not in plan → `403`; anti-abuse → `429`. Do not mask own quota as `404`. `POST /billing/dev/simulate` current org + `require_admin` only; else `404`.

Canonical: [billing.md](../platform/billing.md).

## ADR-014. SSO: org from connector, not assertion

**Decision:** SAML 2.0 SP (OIDC IdP — same connector). Org determined by connector (`/auth/sso/{slug}/…`), not assertion attribute or request body. Success sets `dw_*` cookies (ADR-007); Bearer ignored.

JIT creates membership **only in that org**. `sso_enforced`: password, Google, and `switch-organization` without fresh SSO into this org — denied. IdP groups → `role` / `departments` per org-admin table; not in document `access_roles` and not instead of `org_id`.

Compose: `SSO_PROVIDER=dev` (fixture assertion). Live Okta/WorkOS not required for local/portfolio acceptance. SCIM — out of scope.

## ADR-015. Custom domain: host-only cookie, hostname pins org

**Decision:** `{slug}` already on `organizations` (not ACL). Platform host `{slug}.localhost` / `{slug}.docwise.app`; verified customer CNAME — Enterprise option.

Session cookies **host-only** (no `Domain` on parent suffix). If `Host` bound to org, it **must** match session `org_id`. Hostname — additional conjunct, not replacement for SQL `organization_id`. On Acme host cannot switch session to Globex.

Unverified domain not bound; one hostname — one org. CORS/CSRF allowlist — from verified domain, not body. Compose: `/etc/hosts`, no Let's Encrypt in CI.

## ADR-016. Postgres RLS only on corpus

**Decision:** `FORCE ROW LEVEL SECURITY` on `documents` and `document_chunks`. GUC `app.organization_id`; Celery — `fetch_document_for_ingestion` (bypass only on `get` by id). `bind_session_rls` after resolve principal and on SSE paths where retrieval runs.

**Why:** these tables feed dense/FTS; one forgotten org bind in SQL — cross-tenant text in RRF. Chat and audit already always filter `organization_id` (and `user_id`); RLS on `chat_messages` without org column — unnecessary complexity.

**Consequence:** migration `015`. Inner ACL (`access_roles`) not in RLS. Pytest: `RLS_TEST_FIXTURE_BYPASS` only for direct ORM corpus fixtures. Postgres **superusers always bypass RLS** (FORCE only affects the table owner); CI/pytest set `DOCWISE_RLS_SESSION_ROLE=docwise_rls` and `SET LOCAL ROLE` each transaction so corpus policies apply under `POSTGRES_USER`.

## ADR-017. Data retention and erasure (EU pilot policy)

**Context:** GDPR-style pilots ask how long queries and retrieval metadata are kept, and what happens when a person leaves. v1 has **no** automated retention job or self-service “delete my account” API.

**Decision:** Product defaults and erasure notes live in [data-retention.md](../platform/data-retention.md). Summary: audit logs **90 days** (when contract requires a purge job); chat until session delete; KB customer-controlled; LLM Redis cache **24 h**. Audit never stores chunk body text. Embedding rotation does not erase audit — private runbook `docs/_private/operations/embedding-model-migration.md`.

**Consequence:** no schema change in ADR-017. When a pilot mandates a shorter audit TTL, add migration-safe purge job + env in the same PR as implementation.
