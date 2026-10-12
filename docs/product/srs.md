# SRS: Docwise

**Repository:** `docwise`  
**Name:** Docwise  
**Type:** shared B2B SaaS document search and Q&A (many organizations on one deploy). Private cloud / on-prem uses the same code with a single organization; see [tenancy.md](../platform/tenancy.md).

Canonical product specification. Implementation details that differ from the draft spec (asyncpg → sync Session, SSE format) are recorded in [decisions.md](../engineering/decisions.md). PKs are UUID, as in the spec.

---

## 1. Problem

Companies accumulate thousands of PDF/DOCX files (policies, NDAs, reports, contracts).

| Pain | Why a naive approach fails |
| --- | --- |
| Semantics | Keyword search does not match how people ask questions |
| PDF structure | Fixed-size splits break tables and lose headings |
| ACL leakage | A shared chat without vector filtering exposes C-level finance to interns |
| Trust | Without an exact page in the source, model answers cannot be verified |

Docwise addresses this with: **organization isolation**, **RBAC on retrieval**, **structure-aware chunking**, **hybrid search + rerank**, **citations in the PDF viewer**.

---

## 2. Product goals

1. Upload PDFs, index structure (pages, sections, tables), and answer questions only from that corpus.
2. Never send the LLM a chunk the user is not allowed to read.
3. Every factual claim cites `{document, page}`; clicking opens the original on that page.
4. If the allowed context does not contain an answer — explicit refusal, no guessing.
5. Retrieval quality is measurable (Ragas + ACL negatives), not “seems fine.”

Access layers: **organization** (`org_id`) on the outside, roles/departments inside. Shared SaaS uses SQL `organization_id` plus inner ACL; see [tenancy.md](../platform/tenancy.md).

Commercial envelope: plans and quotas, SSO/SAML, custom domain; billing behind a port (`dev` by default, Stripe not required). Spec: [billing.md](../platform/billing.md).

Out of product scope — see [§7](#7-out-of-scope).

---

## 3. Stack (target)

| Layer | Technologies |
| --- | --- |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2 **sync Session** |
| Queues | Redis 7, Celery 5 |
| Data | PostgreSQL 15 + pgvector (`pgvector/pgvector:pg15`), dense 384d cosine + FTS (`tsvector` + GIN) independent of dense |
| Parsing | PyMuPDF (`fitz`), pdfplumber (tables → Markdown) |
| ML | fastembed `BAAI/bge-small-en-v1.5`, `BAAI/bge-reranker-base`; LLM через OpenAI-compatible HTTP client |
| Frontend | Next.js 15 App Router, React 19, TypeScript 5, Tailwind 4, shadcn/ui, pdf.js |
| Infra | Docker Compose, MinIO, GitHub Actions (ruff + mypy + pytest; frontend tsc + vitest + lint + build) |

Do not substitute the stack (LangChain as core, a separate vector-only service instead of pgvector) without an explicit request.

---

## 4. Functional requirements

### FR-1. Knowledge base

- An authorized user with KB manage rights uploads PDFs and assigns `access_roles[]`.
- The system computes SHA-256, stores bytes in MinIO, a row in `documents` (`pending`), and enqueues a Celery task.
- Statuses: `pending → processing → ready | failed`. Failed retains `last_error`.
- Paginated document list with statuses; delete cascades (Postgres + MinIO).
- Original file delivery only under the same ACL as the document row. Public bucket URLs are forbidden.

### FR-2. Ingestion

- Parse by physical pages; tables as GitHub-flavored Markdown; store block coordinates when available.
- A chunk must not cross a page boundary; 400–600 tokens, overlap 50 only within the same page/section.
- Before embedding — meta header `[Document: … | Section: … | Page: N]`.
- Chunk payload includes the document’s `access_roles`. Re-ingest is idempotent (delete by `document_id`).

### FR-3. Retrieval + chat

- SQL filter `access_roles && allowed_roles` on **every** dense and sparse/FTS query.
- Hybrid: dense Top-25 + FTS Top-25 (independent) → RRF `k=60` → Top-15 → cross-encoder → threshold 0.25 → Top-4.
- Generation strictly from Top-4. Empty list after threshold → fixed refusal without creative completion.
- SSE: citations first, then tokens, then metrics. Protocol — JSON envelopes on `data:` (see [api.md](../engineering/api.md)).

### FR-4. UI

- Split-pane: sessions (hideable) / chat with min-width / PDF ~55% remainder. Footnotes — interactive tags `Doc.pdf (page N)`. Left and right panes can be fully hidden; footnote click opens PDF.
- Click: open file, go to page, highlight fragment.
- KB admin: table + drag-and-drop + access tags + status polling.

### FR-5. Evaluation and audit

- Every retrieval (chat and inspect) writes to `rag_audit_logs`: query, user, chunk UUIDs after reranker, latency_ms, tokens_used, feedback.
- Do not write full chunk text to audit (including restricted).
- Feedback `+1 / -1` on own assistant messages (`POST /api/v1/chat/feedback`).
- `eval/` with golden set ≥ 30 questions and Ragas report.

### FR-6. Inspect (admin)

- `POST /api/v1/search/inspect` — lists `dense` / `sparse` / `rrf` / `reranked` with scores. Same SQL ACL as chat; roles not from request body.
- `admin` only. `ENABLE_SEARCH_INSPECT`: off by default in production (`404`), otherwise on. Explicit `true`/`false` overrides default.
- No admin override: HR-only chunk invisible to admin without `hr` in `allowed_roles`. User without role does not see the chunk and must not learn the file exists.

### FR-7. Organizations (shared SaaS)

- Documents, chunks, chat, and audit belong to `organizations`. Search never crosses another org’s `org_id`.
- User is global; role and departments live on org membership. Current org only from session.
- `all` means everyone **in this organization**, not every logged-in SaaS user.
- Self-serve: registration creates an organization; org-admin invites follow.
- Spec: [tenancy.md](../platform/tenancy.md). Acceptance criteria — §8 below.

### FR-8. Plans, SSO, domain

- Organization has plan (`starter` \| `team` \| `enterprise`) and quotas for seats / pages / chat tokens per period. Exhaustion → `402` on upload / invite / chat **before** retrieval. Rate limit remains `429`.
- SSO/SAML and custom domain — Enterprise entitlement. Org SSO comes from the connector, not the assertion. Hostname pins org; SQL `organization_id` is not waived.
- Payment provider is not the ACL source. Compose acceptance uses `BILLING_PROVIDER=dev`. Spec: [billing.md](../platform/billing.md).

---

## 5. Non-functional requirements

See [nfr.md](nfr.md). Briefly: zero ACL leaks; refusal without hallucination; parsing not in HTTP request; secrets only in env.

---

## 6. Acceptance criteria

- [x] Upload complex PDF with table → `ready`, chunks with single `page_number`, table in Markdown.
- [x] Question finds correct page; UI click opens it.
- [x] User without role does not see chunk in inspect, chat, or `/raw`.
- [x] Insufficient context → refusal “no information in documents”, no invented facts.
- [x] Re-ingest same `document_id` does not duplicate rows in `document_chunks`.
- [x] Ragas run writes `reports/rag_benchmark.md`; ACL negatives — zero leaks.
- [x] CI: ruff + pytest (parser, RRF) without GPU and without live LLM in unit tests.

---

## 7. Out of scope

Not in product scope (separate decisions or later releases):

- platform operator console with access to other tenants’ corpora
- SCIM / directory sync; mapping IdP groups directly to document `access_roles`
- live payment processing as acceptance criterion (Stripe adapter and `BILLING_PROVIDER=dev` — see [billing.md](../platform/billing.md))
- online file editing
- tool-calling agents outside the corpus
- training custom embeddings
- Solidity audit domain, Slither/solc, Qdrant as separate vector store

---

## 8. Shared SaaS and commercial envelope

Shared SaaS: zero leaks **between organizations**, including documents with `access_roles = ['all']`. Criteria — [tenancy.md](../platform/tenancy.md).

Commercial envelope: quotas and SSO/domain do not cross org boundaries; local and CI runs use `BILLING_PROVIDER=dev` without live Stripe. Criteria — [billing.md](../platform/billing.md) and FR-8 above.
