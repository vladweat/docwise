# Обработка документов (Ingestion)

Celery task: `ingestion.process_document`, аргумент `document_id`. Redis lock:
`indexing_lock:{document_id}` хранит уникальный owner token; Lua compare-and-delete не позволяет
устаревшему worker снять lock нового запуска. TTL — 60 минут, hard task limit — 25 минут.
Worker: `acks_late`, prefetch 1, soft/hard limits 20/25 минут. До трёх retry с backoff
применяются только к transient object storage, database, Redis и embedding errors. Ошибки
формата, парсера и quota terminal: документ остаётся `failed` и требует проверки. Перед
transient retry worker удаляет partial chunks, возвращает документ в `pending` и фиксирует
безопасное обобщённое сообщение.

Повторный запуск для того же `document_id` удаляет старые `document_chunks` и записывает
новые chunks завершаются общим DB commit; statuses/stages фиксируются отдельными commit, а
MinIO — внешняя система. Поэтому строгой транзакционной идемпотентности для всего pipeline
нет. Document delete отдельно использует transactional outbox для повторяемой очистки MinIO.
Status:
`pending → processing → ready | failed`. Во время `processing` `ingestion_stage` проходит
`parse → chunk → embed` с commit между этапами для `GET /documents/{id}/status`.

После потери Redis (Celery queue не входит в pilot backup) `make requeue-stale-ingestion`
показывает pending и processing старше 60 минут в dry-run; `APPLY=1` ставит их в очередь.
Один вызов ограничен 500 документами, выводятся только статусы и IDs. Рабочий lock безопасно
отклонит duplicate task.

## 1. Extraction

1. Download object from MinIO via `documents.file_path`.
2. Document row already has `organization_id`; worker **does not** treat org from task args as source of truth — only Postgres row.
3. Open PDF via `fitz` (PyMuPDF).
4. For each physical page:
   - extract text in reading order;
   - keep page number (1-based in API and citations);
   - if table grid present, extract via pdfplumber as Markdown (`| Header | Header |`);
   - store block coordinates when possible (viewer highlight).
5. Write `total_pages` to Postgres.

DOCX: `python-docx`, logical sections (Heading) → separate parser “pages”; in Postgres `page_number = 0`, citations via `section` (no invented `page`). Tables — GFM Markdown, same as PDF.

## 2. Structure-aware chunking

Forbidden: sliding window over full file text ignoring pages.

Rules:

- Chunk **must not cross** page boundary.
- Prefer splits at section headings within page.
- Size: **400–600 tokens**, overlap **50 tokens** only within same page/section.
- Tables preferably one chunk (`is_table: true`); if table exceeds limit — split by rows, repeat Markdown header.

Before vectorization inject meta header at chunk start:

```
[Document: HR_Policy.pdf | Section: Expenses | Page: 12]
{content}
```

Part of embedding, not a Postgres column. v1 rule (do not mix):

- `document_chunks.content` — clean fragment for UI, LLM, cross-encoder rerank and citations (no service line).
- `embed_text` = meta header + `\n` + `content` (computed in `chunker.format_embed_text` only before FastEmbed; not stored in Postgres).
- Citation snippet from `content` (`citation_snippet`); if `[Document:` accidentally in text, strip it.

Meta header affects dense via embedding; rerank and LLM prompt use `content` (see [retrieval.md](retrieval.md)).

## 3. Embed & upsert

1. Batch dense vectors FastEmbed `BAAI/bge-small-en-v1.5` (384d cosine) on `embed_text`.
2. `delete` `document_chunks` rows by `document_id`.
3. Insert: vectors + payload (`document_id`, `organization_id` from document, `chunk_id`, `page_number`, `section_title`, `is_table`, `access_roles` from document, `content`, `token_count`).
4. `documents.status = ready`. Terminal exception: `failed` + safe `last_error`; transient exception: remove partial chunks, set `pending`, then bounded Celery retry.

Sparse BM25/FTS — Postgres `search_vector` + GIN, Top-25 independent of dense ([ADR-005](../engineering/decisions.md)).

ACL change without re-ingest: `PATCH /documents/{id}` copies `access_roles` to document and all chunks.

## 4. Parser quality test

Fixture: PDF with table and multi-level headings.

Checks:

- each chunk has one `page_number`;
- table serialized to Markdown and `is_table=true`;
- chunk `access_roles` equal document roles;
- chunk `organization_id` equals document;
- повторный запуск `ingestion.process_document` не дублирует `document_chunks`.
