# Пайплайн обработки документов (Ingestion)

Задача Celery: `process_document(doc_id)` (как `load_contract_task` в ChainWise). Redis-лок `indexing_lock:{document_id}`, TTL как в `redis_lock.py`. Воркер: `acks_late`, prefetch 1, лимит 20/25 мин, ретраи идемпотентного ingest.

Идемпотентность: повторный запуск для того же `doc_id` удаляет старые строки `document_chunks` и перезаписывает чанки. Статусы: `pending → processing → ready | failed`. Во время `processing` поле `ingestion_stage` проходит `parse → chunk → embed` (коммитится между шагами для `GET /documents/{id}/status`).

## 1. Extraction

1. Скачать объект из MinIO по `documents.file_path`.
2. Документ уже несёт `organization_id` (M5); воркер **не** принимает org из аргументов задачи как источник истины — только строка Postgres.
2. Открыть PDF через `fitz` (PyMuPDF).
3. Для каждой физической страницы:
   - извлечь текст в порядке чтения;
   - сохранить номер страницы (1-based в API и цитатах);
   - при наличии сетки таблицы извлечь её через pdfplumber в Markdown (`| Header | Header |`);
   - по возможности сохранить координаты блоков (для подсветки во вьюере).
4. Записать `total_pages` в Postgres.

DOCX: `python-docx`, логические разделы (Heading) → отдельные «страницы» парсера; в Postgres `page_number = 0`, цитаты через `section` (без выдуманного `page`). Таблицы — GFM Markdown, как у PDF.

## 2. Structure-aware chunking

Запрещено: скользящее окно по всему тексту файла без учёта страниц.

Правила:

- Чанк **не пересекает** границу страницы.
- Предпочтительно резать по заголовкам секций внутри страницы.
- Размер: **400–600 токенов**, overlap **50 токенов** только внутри той же страницы/секции.
- Таблицы по возможности держать одним чанком (`is_table: true`); если таблица длиннее лимита — резать по строкам, повторяя header Markdown.

Перед векторизацией в начало чанка инжектится мета-заголовок:

```
[Document: HR_Policy.pdf | Section: Expenses | Page: 12]
{content}
```

Это часть эмбеддинга, не колонка в Postgres. Правило v1 (не смешивать):

- `document_chunks.content` — чистый фрагмент для UI, LLM и цитат (без служебной строки).
- `embed_text` = мета-заголовок + `\n` + `content` (считается в `chunker.format_embed_text` перед FastEmbed).
- Сниппет цитаты берётся из `content` (`citation_snippet`); если в текст случайно попал заголовок `[Document:`, он отбрасывается.

Реранкер в M2 получает `embed_text`, не сырой `content` без мета.

## 3. Embed & upsert

1. Батч dense-векторов FastEmbed `BAAI/bge-small-en-v1.5` (384d cosine) по `embed_text`.
2. `delete` строк `document_chunks` по `document_id`.
3. Insert: vectors + payload (`document_id`, `organization_id` с документа, `chunk_id`, `page_number`, `section_title`, `is_table`, `access_roles` с документа, `content`, `token_count`).
4. `documents.status = ready`. Любое исключение: `failed` + `last_error`, без «частично готового» индекса (либо явный rollback delete).

Sparse BM25/FTS — Postgres `search_vector` + GIN, Top-25 независимо от dense ([ADR-005](../engineering/decisions.md)).

Смена ACL без re-ingest: `PATCH /documents/{id}` копирует `access_roles` на документ и все его чанки.

## 4. Тест качества парсера

Фикстура: PDF с таблицей и многоуровневыми заголовками.

Проверки:

- у каждого чанка одна `page_number`;
- таблица сериализована в Markdown и `is_table=true`;
- `access_roles` чанка равны ролям документа;
- `organization_id` чанка равен документу;
- повторный `process_document` не плодит дубликаты в `document_chunks`.
