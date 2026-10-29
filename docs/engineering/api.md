# API specification

Base prefix: `/api/v1`. Format: JSON. HTTP errors use `{ "error": { "code", "message", "details?" } }`. Auth: httpOnly cookies `dw_access` / `dw_refresh` only (see [auth.md](../platform/auth.md)). Bearer not accepted in v1. JSON identifiers — UUID strings.

## Errors

All API HTTP failures, including authentication/authorization, CSRF, FastAPI exceptions,
request validation, and unhandled server errors use one envelope:

```json
{"error":{"code":"request.validation","message":"Request validation failed","details":{"issues":[{"location":["body","query"],"code":"missing"}]}}}
```

`details.issues` contains only field locations and validator codes; submitted values and
internal exception text are omitted. Unhandled errors return a generic `500`. During rollout,
the frontend client accepts both this envelope and legacy `{ "detail": ... }` responses.
Streaming errors after SSE headers are sent use the chat event format described below.

All `/api/v1/*` endpoints except login/register/google, `GET/POST /auth/sso/{slug}/*` and Stripe webhook require cookie session. Document lists and search chunks limited to current organization and ACL ([tenancy.md](../platform/tenancy.md)). Fields `org_id` / `organization_id` / `access_roles` / `document_ids` in chat and search bodies are not authority.

## Health

```http
GET /
GET /health
GET /ready
```

`GET /` — metadata процесса: `{"service":"docwise-backend","docs":"/docs"}`; поле `docs`
равно `null` в production.

`GET /health` — process liveness: `200` `{ "status": "ok" }` without dependency checks.

`GET /ready` — Postgres, pgvector, Redis, MinIO. Response includes `billing`: with `BILLING_PROVIDER=dev` value `"dev"` (not an error). With `BILLING_PROVIDER=stripe` without keys `"error"` — billing not `ok`. `200` if required dependencies `ok` and billing `ok` or `dev`, else `503` with same fields and `"status": "degraded"`.

OpenAPI `/docs` disabled when `ENVIRONMENT=production`.

## Auth

Cookies `dw_*`. Bodies — Pydantic, do not log password. login/register/google/refresh responses — `UserResponse` (`id`, `email`, `role`, `departments`, `is_active`, `created_at`, `organization_id`, `organization_name`, `organizations`). Role and departments — **current membership**. Token not returned in JSON.

```http
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/google
GET  /api/v1/auth/sso/{slug}/login
POST /api/v1/auth/sso/{slug}/acs
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

First user in empty `users` table is no longer “admin of whole platform”: `POST /register` creates user + org + membership `admin` (`organization_name`). Others join org via invite. Register/login/google limited by `RATE_LIMIT_AUTH_PER_MINUTE` per IP. SSO login/ACS — by connector slug ([auth.md](../platform/auth.md)).

With `COOKIE_SAMESITE=none` POST to `/api/v1` without `Origin` from `CORS_ORIGINS` and without `X-Requested-With: Docwise` → `403`. `/me` does not return `hashed_password`.

## Documents

```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data
```

Fields: `file` (PDF or DOCX), `access_roles` (repeated field or JSON list). `admin` or `manager` of current org (`require_kb_admin`).  
Response `201`: document metadata (`content_format`: `pdf` \| `docx`), `status: pending`, `total_pages` — for PDF file `page_count`; for DOCX count of logical sections (quota), no text extraction in handler. Duplicate SHA-256 `file_hash` **in this org** → `409` with code `resource.conflict` and no existing record body (avoid leaking `id`/`title` outside ACL and confirming foreign tenant). Unique `(organization_id, file_hash)`. No text extraction in handler: bytes to MinIO (org prefix), `pending` row with session `organization_id`, Celery `ingestion.process_document`.

Size limit: `UPLOAD_MAX_BYTES` (default 50 MiB) → `413`. Unsupported format → `400`. Rate limit: `RATE_LIMIT_UPLOAD_PER_MINUTE` by `user.id`. Plan page quota: occupied (including `pending`/`processing`) plus incoming file units (PDF pages or DOCX sections) > cap → `402` with code `billing.payment_required`, without Celery. Do not use `404` for own quota.

```http
GET /api/v1/documents
```

Pagination: `limit` (1…100, default 20), `offset`. Filters: `status`. Only documents of
**current org** visible to user role. Fields: `id` (UUID), `title`, `file_size_bytes`,
`total_pages`, `access_roles`, `status`, `last_error` (null if not `failed`), `created_at`,
`preview_snippet`.

```http
GET /api/v1/documents/{id}/status
```

Processing poll: `pending | processing | ready | failed`, plus `last_error` if failed and `stage` (`parse` \| `chunk` \| `embed` \| `null`). Worker writes `stage` between ingest steps for UI progress. `pending` → `stage: null`; `processing` → current step; `ready` → `embed`; `failed` → step where failed. `404` if no rights / no row.

```http
PATCH /api/v1/documents/{id}
Content-Type: application/json
```

Body: `{ "access_roles": ["hr", "admin"] }`. `require_kb_admin` (admin or manager). One transaction updates `documents.access_roles` and all `document_chunks.access_roles` for file (no re-embed). Empty list → `422`. Missing document → `404` with code `resource.not_found`. Employee cannot. Retrieval after ACL change sees new chunk roles immediately.

```http
DELETE /api/v1/documents/{id}
```

Cascade: Postgres document/chunks delete and `storage_deletions` outbox insert commit in one transaction. `require_kb_admin` (admin or manager). `204`. Missing document → `404` with code `resource.not_found`; delete does not require ACL intersection (KB management). A scheduled worker deletes the private MinIO object and removes the outbox row; failures remain queued for retry and are visible to ops checks.

```http
GET /api/v1/documents/{id}/raw
```

Original bytes for viewer (PDF or DOCX). Same ACL as document row. `Content-Type`: `application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`. No public eternally-lived pre-signed URLs without auth.

## Search and chat

```http
POST /api/v1/chat/stream
Content-Type: application/json
```

Body:

```json
{
  "query": "What is the daily travel reimbursement cap?",
  "session_id": null
}
```

Response: `Content-Type: text/event-stream`. Cookie session, limit `RATE_LIMIT_CHAT_PER_MINUTE` by `user.id`. Period token quota: if exhausted → SSE `{ "type": "error", "content": "Organization quota exceeded" }` **before** retrieval (same meaning as HTTP `402`). A second active request for the same existing `session_id` returns HTTP `409` with the standard `{ "error": { "code": "resource.conflict", "message": "..." } }` envelope **before** SSE starts; retry after the active reply completes. Different sessions remain independent. SSE format (not named `event:` from draft spec):

```
data: {"type":"citations","citations":[{"doc_id":"3fa85f64-5717-4562-b3fc-2c963f66afa6","doc_title":"Travel.pdf","page":4,"section":null,"snippet":"..."}]}

data: {"type":"token","content":"Employees "}

data: {"type":"meta","cached":false,"tokens_used":640,"session_id":"...","message_id":"..."}

data: [DONE]
```

Empty `session_id` — create session when saving turn (with session `organization_id`). Prior turn history may refine query in prompt, but retrieval still uses SQL `org_id` + ACL of current membership; `access_roles` / `document_ids` / `organization_id` in body ignored. Redis LLM cache key includes `org_id` and canonical `allowed_roles` (sorted unique). `meta.session_id` and `meta.message_id` — UUID of new/current session and assistant message (for feedback).

```http
GET /api/v1/chat/sessions
```

Sessions of current user **in current org**: `{ items: [{id, title, created_at, updated_at}], total, limit, offset }`. Pagination `limit`/`offset`. Foreign sessions and other org sessions not visible.

```http
GET /api/v1/chat/sessions/{id}
```

Session messages (`id`, `role`, `content`, `sources`, `created_at`). No rights / no row / other org → `404` with code `resource.not_found`, without confirming foreign session.

```http
DELETE /api/v1/chat/sessions/{id}
```

Deletes session of current user **in current org** with messages (Postgres `ON DELETE CASCADE`). Audit (`rag_audit_logs.session_id`) nulled (`SET NULL`). Success `204`. Foreign session / other org / no row → same `404` as GET.

```http
POST /api/v1/chat/feedback
```

Body: `{ "message_id": "<uuid>", "rating": 1 | -1, "comment": "..." }`. `comment` is
optional, trimmed, limited to 2000 characters, and stored in `rag_audit_logs.feedback_comment`;
blank comments become `null`. Own **assistant** messages only. Success `204`. Foreign / user
message → `404`. Feedback comments follow the audit retention period.

## Inspect (admin)

Hybrid pipeline debug. Not ACL bypass: same roles as chat. Retrieval spec: [retrieval.md](../pipeline/retrieval.md).

```http
POST /api/v1/search/inspect
Content-Type: application/json
```

Body:

```json
{
  "query": "What is the daily travel reimbursement cap?",
  "limit": 15
}
```

`query` — 1…4000 chars after trim. `limit` — 1…50, default 15: max hits **in each** list (pipeline as chat, response trimmed). `access_roles` / `document_ids` / `user_id` / `organization_id` in body ignored.

Response `200`:

```json
{
  "dense": [
    {
      "chunk_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6:4:0",
      "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "page": 4,
      "score": 0.81,
      "snippet": "Daily travel reimbursement is capped at 150 USD."
    }
  ],
  "sparse": [],
  "rrf": [],
  "reranked": []
}
```

Each hit: `chunk_id` (stable string), `document_id` (UUID), `page`, `score`, `snippet` (preview, not full text). Lists: `dense`, `sparse`, `rrf`, `reranked`. Chunk outside ACL not in response; foreign file existence not confirmed (empty lists, no hidden doc title/id).

Writes `rag_audit_logs`: `query`, `user_id`, `retrieved_chunk_ids` (chunk UUID PKs **after** reranker), `latency_ms`. `session_id` / `message_id` / `tokens_used` — null. JSONB UUID strings only, not chunk body.

| Condition | HTTP | `error.code` |
| --- | --- | --- |
| No cookie session | `401` | `auth.unauthorized` |
| `ENABLE_SEARCH_INSPECT` off | `404` | `resource.not_found` (even for admin; endpoint not advertised) |
| Not `admin` of current org (flag on) | `403` | `auth.forbidden` |
| Empty `query` / `limit` out of range | `422` | `request.validation` |
| Embed / rerank failure | `503` | `service.unavailable` (no filenames) |

### Flag `ENABLE_SEARCH_INSPECT`

| `ENVIRONMENT` | Variable unset | `true` / `false` |
| --- | --- | --- |
| not `production` | on | as set |
| `production` | **off** | as set |

In production explicitly: `ENABLE_SEARCH_INSPECT=true`. Org-admin **does not** see HR-only chunks without `hr` in `allowed_roles` (no admin override), and **does not** see another organization. `employee` / `manager` — `403`, not lists.

## Organizations

```http
POST /api/v1/auth/register
```

Body: `{ "email", "password", "organization_name" }` or `{ "email", "password", "invite_token" }`. Without invite creates user + org + membership `admin`. `201` + `UserResponse` with `organization_id`.

```http
POST /api/v1/auth/switch-organization
```

Body: `{ "organization_id": "<uuid>" }`. Only if membership exists. Reissues cookies with new `org_id`. Foreign id → `404` (no list of available orgs in error). If `Host` bound to other org → deny, no cookie change.

```http
GET  /api/v1/organizations/members
POST /api/v1/organizations/invites
```

Member list of current org (org-admin). Invite: `{ "email", "role", "departments" }`. Existing email → `status: added` (membership immediately). New → `status: invited` + `invite_token` for `POST /auth/register`. Not org-admin → `403`. Seats ≥ plan cap → `402`.

## Billing and quotas

Canonical: [billing.md](../platform/billing.md). Cookie session of current org only. Fields `organization_id` / `plan` in body not authority (`plan` in `POST /billing/plan` body — desired plan, provider applies to **session** org).

```http
GET  /api/v1/billing/subscription
GET  /api/v1/billing/usage
POST /api/v1/billing/plan
```

`subscription`: `plan`, `billing_status`, period, entitlements (`sso`, `custom_domain`), `provider` (`dev` \| `stripe`). `usage`: seats / pages / tokens and plan caps. Org-admin only; else `403`.

`POST /billing/plan` body `{ "plan": "team" }`. `BILLING_PROVIDER=dev` — writes Postgres immediately. `stripe` — `{ "checkout_url": "..." }` (no keys → `503`). Not org-admin → `403`.

```http
POST /api/v1/billing/dev/simulate
```

Body: `{ "action": "set_plan" | "past_due" | "cancel" | "activate", "plan": "enterprise" }`. Only `BILLING_PROVIDER=dev` **and** org-admin of current org. Else `404` with code `resource.not_found` (like disabled inspect). Does not accept `organization_id`.

```http
POST /api/v1/billing/webhooks/stripe
```

No cookie. Stripe signature. Idempotency `billing_events`. Without Stripe adapter configured — `404`.

## SSO

```http
GET  /api/v1/auth/sso/{slug}/login
POST /api/v1/auth/sso/{slug}/acs
```

`{slug}` → connector org. No connector / no entitlement → `404` (do not confirm foreign slug separately from “no SSO”). If `SSO_PROVIDER != dev`, login/ACS return `404`; the public demo sets `disabled`. In local Compose only, the dev fixture ACS accepts `{ "email", "email_verified", "groups" }` and must not be treated as a real IdP. Fixture fields `organization_id` / `org_id` in assertion are ignored. Bearer not accepted.

```http
GET  /api/v1/organizations/sso
PUT  /api/v1/organizations/sso
```

Org-admin of current org. Plan without SSO → `403`. Upsert body: IdP metadata, `jit_enabled`, `attribute_map`, `sso_enforced`.

## Domain

```http
GET  /api/v1/organizations/domain
PUT  /api/v1/organizations/domain
POST /api/v1/organizations/domain/verify
```

Org-admin. Plan without custom domain: `PUT` custom hostname → `403`; platform `{slug}` always readable. `verify` — TXT/HTTP token (Compose/`dev`: same token from GET, no Let's Encrypt). Unverified Host does not pin session.

`GET` / `PUT` / `verify` response:

```json
{
  "slug": "acme-a1b2c3",
  "platform_hostnames": ["acme-a1b2c3.localhost", "acme-a1b2c3.docwise.app"],
  "custom_hostname": "kb.acme.example",
  "custom_verified": false,
  "verified_at": null,
  "verification_token": "…",
  "entitlement": true
}
```

`PUT` body `{ "hostname": "kb.acme.example" }` or `{ "hostname": null }` (remove custom). Own `{slug}.localhost` / `{slug}.docwise.app` — `200`, custom not created (already in `platform_hostnames`). Free `{label}.docwise.app` may be saved as custom (verify). Foreign existing `{slug}` on same suffix → `409` without org name. Foreign `organization_id` in body → `404`. Hostname taken by other org → `409`. `verification_token` only while custom not verified.
