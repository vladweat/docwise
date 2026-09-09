# Спецификация API

Базовый префикс: `/api/v1`. Формат: JSON, ошибки в теле `{ "detail": "..." }` (стиль FastAPI). Auth: только httpOnly cookies `dw_access` / `dw_refresh` (см. [auth.md](auth.md)). Bearer в v1 не принимается. Идентификаторы в JSON — UUID-строки.

Все эндпоинты `/api/v1/*`, кроме login/register/google, требуют cookie-сессию. Списки документов и чанки поиска ограничены ACL.

## Health

```http
GET /health
GET /ready
```

`GET /health` — liveness процесса: `200` `{ "status": "ok" }` без проверки зависимостей.

`GET /ready` — Postgres, pgvector, Redis, MinIO. `200` если все `ok`, иначе `503` с теми же полями и `"status": "degraded"`.

OpenAPI `/docs` выключен при `ENVIRONMENT=production`.

## Auth

Куки `dw_*`. Тела — Pydantic, пароль не логировать. Ответы login/register/google/refresh — `UserResponse` (`id`, `email`, `role`, `departments`, `is_active`, `created_at`). Токен в JSON не возвращается.

```http
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/google
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

Первый пользователь в пустой таблице `users` получает `role=admin`, следующие — `employee`. Register/login/google ограничены `RATE_LIMIT_AUTH_PER_MINUTE` по IP.

При `COOKIE_SAMESITE=none` POST на `/api/v1` без `Origin` из `CORS_ORIGINS` и без `X-Requested-With: Docwise` → `403`. `/me` не отдаёт `hashed_password`.

## Документы

```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data
```

Поля: `file` (PDF), `access_roles` (повторяющееся поле или JSON-список). Только `admin` (`require_admin`).  
Ответ `201`: метаданные документа, `status: pending`. Дубликат SHA-256 `file_hash` → `409` `{ "detail": "Document with this file hash already exists" }` без тела существующей записи (чтобы не утекали `id`/`title` файла вне ACL). Парсинг PDF в хендлере запрещён: байты в MinIO, строка `pending`, Celery `ingestion.process_document`.

Лимит размера: `UPLOAD_MAX_BYTES` (по умолчанию 50 MiB) → `413`. Не-PDF → `400`. Rate limit: `RATE_LIMIT_UPLOAD_PER_MINUTE` по `user.id`.

```http
GET /api/v1/documents
```

Пагинация: `limit`, `offset` или cursor. Фильтры: `status`. Только документы, видимые роли пользователя. Поля: `id` (UUID), `title`, `file_size_bytes`, `total_pages`, `access_roles`, `status`, `created_at`.

```http
GET /api/v1/documents/{id}/status
```

Опрос обработки: `pending | processing | ready | failed`, плюс `last_error` если failed. `404` если нет прав / нет записи.

```http
PATCH /api/v1/documents/{id}
Content-Type: application/json
```

Тело: `{ "access_roles": ["hr", "admin"] }`. Только `require_admin`. В одной транзакции обновляет `documents.access_roles` и все `document_chunks.access_roles` этого файла (без re-embed). Пустой список → `422`. Документ без строки → `404` с тем же `detail`. Manager не может. Retrieval после смены ACL сразу видит новые роли чанков.

```http
DELETE /api/v1/documents/{id}
```

Каскад: Postgres (документ + чанки) + объект MinIO. Только `require_admin` (manager в v1 не может). `204`. Документ без строки → `404` с тем же `detail`, что и у чтения; удаление не требует пересечения ACL (управление KB).

```http
GET /api/v1/documents/{id}/raw
```

Байты файла для PDF-вьюера. Те же ACL, что у строки документа. `Content-Type: application/pdf`. Без публичных URL вечно живущих pre-signed без auth.

## Поиск и диалог

```http
POST /api/v1/chat/stream
Content-Type: application/json
```

Тело:

```json
{
  "query": "What is the daily travel reimbursement cap?",
  "session_id": null
}
```

Ответ: `Content-Type: text/event-stream`. Формат как в ChainWise (не именованные `event:` из чернового ТЗ):

```
data: {"type":"citations","citations":[{"doc_id":"3fa85f64-5717-4562-b3fc-2c963f66afa6","doc_title":"Travel.pdf","page":4,"snippet":"..."}]}

data: {"type":"token","content":"Employees "}

data: {"type":"meta","cached":false,"tokens_used":640}

data: [DONE]
```

`session_id` пустой — создать сессию. История предыдущих реплик может уточнять запрос, но retrieval всё равно с ACL.

```http
GET /api/v1/chat/sessions
```

Сессии текущего пользователя (id, title, updated_at). Детали сообщений — `GET /api/v1/chat/sessions/{id}` (добавить в реализации).

```http
POST /api/v1/chat/feedback
```

Тело: `{ "message_id": "<uuid>", "rating": 1 | -1, "comment": "..." }`. Пишет `rag_audit_logs.feedback`. Только свои сообщения.

## Инспекция (dev/admin)

```http
POST /api/v1/search/inspect
```

Тело: `{ "query": "...", "limit": 15 }`.  
Ответ: списки `dense`, `sparse`, `rrf`, `reranked` с `chunk_id`, `score`, `page`, `document_id`, превью текста. Тот же RBAC-фильтр. В production за флагом `ENABLE_SEARCH_INSPECT`.
