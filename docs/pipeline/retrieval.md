# Search and generation (Retrieval)

Step order is fixed. Skipping reranker or RBAC filter on a “happy path” is not allowed.

## Step 1. RBAC in SQL (before LLM)

Session yields current `organization_id` and `allowed_roles` ([auth.md](../platform/auth.md); org wall — [tenancy.md](../platform/tenancy.md)). Apply both conjuncts on **every** dense and FTS query before RRF, rerank, or the LLM. Do not filter “later in prompt”. Original download (`GET .../raw`) uses the same semantics on the `documents` row.

## Step 2. Hybrid search

Do not load full corpus into RAM for BM25. Search — SQL Top-K with ACL on every query.

Dense: query embedding, Top-25, cosine (`embedding <=> query`), ACL filter. HNSW index is global; before query `SET LOCAL hnsw.iterative_scan` (`relaxed_order`) and `hnsw.max_scan_tuples` (`HNSW_MAX_SCAN_TUPLES`, default 20000) so org/ACL filter does not truncate neighbors. Capacity and Redis SPOF — [nfr.md](../product/nfr.md#capacity-and-scaling-v1-guidelines).
2. **Sparse / FTS:** Top-25 independent of dense, Postgres `tsvector` (`simple`) + GIN, same `organization_id` and `access_roles && allowed_roles`.
3. **RRF** (`k = 60`) — `reciprocal_rank_fusion` without formula change:

\[
RRF(d) = \sum_{m \in \{\text{dense},\ \text{sparse}\}} \frac{1}{60 + \mathrm{rank}_m(d)}
\]

Document missing from one list contributes only from methods where it appears. Result: **Top-15**.

## Step 3. Cross-encoder rerank

Model: `BAAI/bge-reranker-base` (fastembed). Pairs `(query, document_chunks.content)` — same text sent to LLM prompt (no meta header `[Document: …]`, dense embed only at ingest).

- Drop score **< 0.25** (configurable threshold, `RERANK_THRESHOLD`, default 0.25). Raw bge-reranker logit passed through sigmoid to `(0, 1)`.
- LLM context: **Top-4**.

Empty list after threshold → refusal per step 4, no creative completion.

## Step 4. Generation without hallucination

System prompt (meaning required, wording may be bilingual):

> You are a corporate AI assistant. Answer strictly from the provided context.
> If the answer is not in the context, say: «В предоставленных документах нет информации по данному вопросу.» Do not invent facts.
> Every fact must cite document and page as `[Title.pdf, page N]`. Lists and tables — Markdown.

Only Top-4 chunks in context: text, title, page, chunk_id.

## Step 5. SSE

Endpoint: `POST /api/v1/chat/stream`. SSE protocol: lines `data: <json>\n\n`, final `data: [DONE]` (see [api.md](../engineering/api.md)).

| Order | `type` | Data |
| --- | --- | --- |
| 1 | `citations` | `{citations: [{doc_id, doc_title, page, snippet}, ...]}` |
| 2 | `token` | `{content}` — text deltas |
| 3 | `meta` | `{tokens_used, cached, session_id, message_id, ...}` then `[DONE]` |
| error | `error` | `{content}` without stack and without foreign filenames |

Citations **before** tokens so UI can open PDF immediately. LLM cache (`llm_cache:{version}:{org_id}:{generation}:{roles_hash}:{question_hash}`) must include current org `org_id`, index generation, and canonical `allowed_roles`; cache warmed for admin or another org is not served. Cache hit: `tokens_used` in audit null. PATCH ACL / DELETE / ready ingest bump `organizations.llm_index_generation` and invalidate org keys.

After answer: row in `chat_messages` + `rag_audit_logs` (see below).

## Retrieval audit

Every successful retrieval pass (chat and inspect) writes `rag_audit_logs`:

| Field | Chat | Inspect |
| --- | --- | --- |
| `query` | question | question |
| `user_id` | caller | caller |
| `organization_id` | current org | current org |
| `retrieved_chunk_ids` | UUID PK Top-4 after reranker | same |
| `latency_ms` | yes | yes |
| `tokens_used` | from LLM; on cache hit — null | null |
| `session_id` / `message_id` | chat turn | null |
| `feedback` | `POST /chat/feedback` `+1`/`-1` | null |

`retrieved_chunk_ids` — canonical UUID strings only. Chunk text, `snippet`, `embed_text` not written to table (log may later be visible to same user). Non-UUID values dropped, not stored.

## Inspect

`POST /api/v1/search/inspect` — same four stages as chat, with scores. Contract: [api.md](../engineering/api.md).

- Org-admin only + `ENABLE_SEARCH_INSPECT` (off by default in production → `404`).
- Same SQL `organization_id = :current_org AND access_roles && allowed_roles`. Admin without `hr` in `allowed_roles` does not see `access_roles = ['hr']`. Foreign org not confirmed.
- `limit` trims **response** (default 15 per list), does not rebuild pipeline Top-K.
- `snippet` in JSON — preview of **visible** chunks. Hidden document: empty list, no id/title.
