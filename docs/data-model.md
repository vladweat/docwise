# Модель данных

Два слоя в одном Postgres: таблицы пользователей/файлов/чатов и индекс чанков с pgvector. ACL чанка дублирует `documents.access_roles`. Первичные ключи — **UUID** (`gen_random_uuid()` / SQLAlchemy `uuid4`). Роли и фильтр: [auth.md](auth.md).

## PostgreSQL

### `users`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | `gen_random_uuid()` |
| `email` | String unique | Логин |
| `hashed_password` | String nullable | Пусто у Google-only аккаунта |
| `google_id` | String unique nullable | `sub` из ID token |
| `is_active` | Boolean | |
| `role` | `admin` \| `manager` \| `employee` | CHECK-ограничение; первый зарегистрированный пользователь — `admin` |
| `departments` | `ARRAY(String)` | Например `['engineering', 'hr']` |
| `created_at` | DateTime | |

Роли ChainWise — только `user`/`admin`. Здесь: `admin` | `manager` | `employee` плюс `departments[]`.  
`user.allowed_roles` для фильтра поиска = `{role}` ∪ `departments` ∪ `{all}` (сборка — в [retrieval](retrieval.md)).

### `documents`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `title` | String | Имя для UI |
| `file_path` | String | Ключ в MinIO |
| `file_hash` | String | SHA-256, UNIQUE, защита от дублей |
| `file_size_bytes` | Integer | |
| `total_pages` | Integer | Заполняется после парсинга |
| `access_roles` | `ARRAY(String)` | Например `['admin', 'hr']` |
| `status` | Enum `pending` \| `processing` \| `ready` \| `failed` | В ChainWise аналог — `indexing`; при порте переименовать |
| `last_error` | Text nullable | Как `contracts.last_error` в ChainWise |
| `created_at`, `updated_at` | DateTime | |

Индексы: `file_hash`, `status`, GIN по `access_roles`.

### `chat_sessions`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK → users | |
| `title` | String nullable | Можно заполнять по первому вопросу |
| `created_at`, `updated_at` | DateTime | |

### `chat_messages`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `session_id` | UUID FK → chat_sessions | Каскад |
| `role` | Enum `user` \| `assistant` | |
| `content` | Text | |
| `sources` | JSONB | Список цитат: `doc_id` (UUID), `title`, `page`, `snippet` |
| `created_at` | DateTime | |

### `rag_audit_logs`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `user_id` | UUID FK | |
| `session_id` / `message_id` | UUID nullable | Связь с чатом |
| `query` | Text | |
| `retrieved_chunk_ids` | JSONB / UUID[] | После реранкера |
| `latency_ms` | Integer | |
| `tokens_used` | Integer nullable | |
| `feedback` | SmallInt nullable | `1` / `-1` |
| `created_at` | DateTime | |

Не писать в аудит полный текст restricted-чанков, если лог может увидеть тот же пользователь через API.

## Postgres: таблица `document_chunks`

Расширение `vector`. Dense: `embedding vector(384)`, cosine (`BAAI/bge-small-en-v1.5`). Индекс HNSW. ACL и `document_id` — обычные колонки + GIN по `access_roles`.

Sparse/BM25: колонка `tsvector` / FTS или in-memory BM25 только по dense-кандидатам (см. [retrieval](retrieval.md)).

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | стабильный ключ чанка в API |
| `document_id` | UUID FK | как `contract_id` в ChainWise, но UUID |
| `chunk_id` | String unique | стабильный ключ для re-upsert (`{document_id}:{page}:{n}`) |
| `page_number` | Integer | |
| `section_title` | String nullable | |
| `is_table` | Boolean | |
| `access_roles` | `ARRAY(String)` | копия с документа |
| `content` | Text | фрагмент **без** мета-заголовка `[Document: …]` (он только в `embed_text` перед FastEmbed) |
| `token_count` | Integer | |
| `embedding` | `vector(384)` | cosine |
| `doc_title` | String nullable | для цитат |
| `bbox` / `highlight_rects` | JSONB nullable | подсветка во вьюере |

При переиндексации удалять строки по `document_id`, затем вставлять заново.

## MinIO

Bucket `documents` — приватный (без anonymous `s3:GetObject`). `documents.file_path` — ключ объекта. Байты отдаются только через API (`GET /documents/{id}/raw`). Публичные URL и вечные pre-signed ссылки запрещены.

## Согласованность ACL

`documents.access_roles` — источник истины. Колонка чанка обязана совпадать. Смена ролей на файле = обновление Postgres документа **и** всех его чанков (или полный re-upsert). Поиск никогда не доверяет ролям, присланным клиентом в теле запроса.
