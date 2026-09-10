# Спецификация API

Базовый префикс: `/api/v1`. Формат: JSON, ошибки в теле `{ "detail": "..." }` (стиль FastAPI). Auth: только httpOnly cookies `dw_access` / `dw_refresh` (см. [auth.md](auth.md)). Bearer в v1 не принимается. Идентификаторы в JSON — UUID-строки.

Все эндпоинты `/api/v1/*`, кроме login/register/google, `GET/POST /auth/sso/{slug}/*` и Stripe webhook, требуют cookie-сессию. Списки документов и чанки поиска ограничены текущей организацией и ACL ([tenancy.md](tenancy.md)). Поля `org_id` / `organization_id` / `access_roles` / `document_ids` в теле чата и поиска не являются источником прав.

## Health

```http
GET /health
GET /ready
```

`GET /health` — liveness процесса: `200` `{ "status": "ok" }` без проверки зависимостей.

`GET /ready` — Postgres, pgvector, Redis, MinIO. M6: при `BILLING_PROVIDER=stripe` без ключей billing не `ok`. `BILLING_PROVIDER=dev` в `/ready` помечается явно (`dev`). `200` если обязательные зависимости `ok`, иначе `503` с теми же полями и `"status": "degraded"`.

OpenAPI `/docs` выключен при `ENVIRONMENT=production`.

## Auth

Куки `dw_*`. Тела — Pydantic, пароль не логировать. Ответы login/register/google/refresh — `UserResponse` (`id`, `email`, `role`, `departments`, `is_active`, `created_at`, `organization_id`, `organization_name`, `organizations`). Роль и отделы — **текущего membership**. Токен в JSON не возвращается.

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

Первый пользователь в пустой таблице `users` больше не «admin всей платформы»: `POST /register` создаёт user + org + membership `admin` (`organization_name`). Следующие люди входят в org по инвайту. Register/login/google ограничены `RATE_LIMIT_AUTH_PER_MINUTE` по IP. SSO login/ACS — по slug коннектора ([auth.md](auth.md) M6).

При `COOKIE_SAMESITE=none` POST на `/api/v1` без `Origin` из `CORS_ORIGINS` и без `X-Requested-With: Docwise` → `403`. `/me` не отдаёт `hashed_password`.

## Документы

```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data
```

Поля: `file` (PDF), `access_roles` (повторяющееся поле или JSON-список). Только `admin` текущей org (`require_admin`).  
Ответ `201`: метаданные документа, `status: pending`. Дубликат SHA-256 `file_hash` **в этой org** → `409` `{ "detail": "Document with this file hash already exists" }` без тела существующей записи (чтобы не утекали `id`/`title` файла вне ACL и не подтверждался чужой тенант). Unique `(organization_id, file_hash)`. Парсинг PDF в хендлере запрещён: байты в MinIO (префикс org), строка `pending` с `organization_id` сессии, Celery `ingestion.process_document`.

Лимит размера: `UPLOAD_MAX_BYTES` (по умолчанию 50 MiB) → `413`. Не-PDF → `400`. Rate limit: `RATE_LIMIT_UPLOAD_PER_MINUTE` по `user.id`. Квота страниц плана (M6): текущая сумма `total_pages` ≥ капа → `402` `{ "detail": "Organization quota exceeded" }` без Celery. Не использовать `404` на свою квоту.

```http
GET /api/v1/documents
```

Пагинация: `limit`, `offset` или cursor. Фильтры: `status`. Только документы **текущей org**, видимые роли пользователя. Поля: `id` (UUID), `title`, `file_size_bytes`, `total_pages`, `access_roles`, `status`, `last_error` (null, если не `failed`), `created_at`.

```http
GET /api/v1/documents/{id}/status
```

Опрос обработки: `pending | processing | ready | failed`, плюс `last_error` если failed и `stage` (`parse` \| `chunk` \| `embed` \| `null`). Воркер пишет `stage` между шагами ingest, чтобы UI показывал прогресс. `pending` → `stage: null`; `processing` → текущий шаг; `ready` → `embed`; `failed` → шаг, на котором упали. `404` если нет прав / нет записи.

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

Ответ: `Content-Type: text/event-stream`. Cookie-сессия, лимит `RATE_LIMIT_CHAT_PER_MINUTE` по `user.id`. Квота токенов периода (M6): если исчерпана → SSE `{ "type": "error", "content": "Organization quota exceeded" }` **до** retrieval (тот же смысл, что HTTP `402`). Формат как в ChainWise (не именованные `event:` из чернового ТЗ):

```
data: {"type":"citations","citations":[{"doc_id":"3fa85f64-5717-4562-b3fc-2c963f66afa6","doc_title":"Travel.pdf","page":4,"snippet":"..."}]}

data: {"type":"token","content":"Employees "}

data: {"type":"meta","cached":false,"tokens_used":640,"session_id":"...","message_id":"..."}

data: [DONE]
```

`session_id` пустой — создать сессию при сохранении хода (с `organization_id` сессии). История предыдущих реплик может уточнять запрос в промпте, но retrieval всё равно с SQL `org_id` + ACL текущего членства; `access_roles` / `document_ids` / `organization_id` в теле игнорируются. Ключ Redis-кэша LLM включает `org_id` и канонический набор `allowed_roles` (отсортированный unique). `meta.session_id` и `meta.message_id` — UUID новой/текущей сессии и сообщения ассистента (для feedback).

```http
GET /api/v1/chat/sessions
```

Сессии текущего пользователя **в текущей org**: `{ items: [{id, title, created_at, updated_at}], total, limit, offset }`. Пагинация `limit`/`offset`. Чужие сессии и сессии другой org не видны.

```http
GET /api/v1/chat/sessions/{id}
```

Сообщения сессии (`id`, `role`, `content`, `sources`, `created_at`). Нет прав / нет записи / другая org → `404` с тем же `detail`, без подтверждения чужой сессии.

```http
POST /api/v1/chat/feedback
```

Тело: `{ "message_id": "<uuid>", "rating": 1 | -1, "comment": "..." }`. Пишет `rag_audit_logs.feedback`. Только свои **assistant**-сообщения. Успех `204`. Чужое / пользовательское сообщение → `404`.

## Инспекция (admin)

Отладка hybrid-пайплайна. Не обход ACL: те же роли, что у чата. Спека retrieval: [retrieval.md](retrieval.md).

```http
POST /api/v1/search/inspect
Content-Type: application/json
```

Тело:

```json
{
  "query": "What is the daily travel reimbursement cap?",
  "limit": 15
}
```

`query` — 1…4000 символов после trim. `limit` — 1…50, по умолчанию 15: максимум хитов **в каждом** списке (пайплайн как у чата, ответ обрезается). `access_roles` / `document_ids` / `user_id` / `organization_id` в теле игнорируются.

Ответ `200`:

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

Каждый хит: `chunk_id` (стабильная строка), `document_id` (UUID), `page`, `score`, `snippet` (превью, не полный текст). Списки: `dense`, `sparse`, `rrf`, `reranked`. Чанк вне ACL в ответ не попадает; существование чужого файла не подтверждается (пустые списки, без title/id скрытого документа).

Пишет `rag_audit_logs`: `query`, `user_id`, `retrieved_chunk_ids` (UUID PK чанков **после** реранкера), `latency_ms`. `session_id` / `message_id` / `tokens_used` — null. В JSONB только UUID-строки, не тело чанка.

| Условие | Код | `detail` |
| --- | --- | --- |
| Нет cookie-сессии | `401` | `Not authenticated` |
| `ENABLE_SEARCH_INSPECT` выкл | `404` | `Not Found` (и для admin; эндпоинт не рекламируется) |
| Не `admin` текущей org (флаг вкл) | `403` | `Admin access required` |
| Пустой `query` / `limit` вне диапазона | `422` | валидация Pydantic |
| Сбой эмбеддинга / реранкера | `503` | `Search inspect failed` (без названий файлов) |

### Флаг `ENABLE_SEARCH_INSPECT`

| `ENVIRONMENT` | Переменная не задана | `true` / `false` |
| --- | --- | --- |
| не `production` | вкл | как задано |
| `production` | **выкл** | как задано |

В production явно: `ENABLE_SEARCH_INSPECT=true`. Org-admin **не** видит HR-only чанки, если в `allowed_roles` нет `hr` (нет admin-override), и **не** видит другую организацию. `employee` / `manager` — `403`, не списки.

## Организации

```http
POST /api/v1/auth/register
```

Тело: `{ "email", "password", "organization_name" }` или `{ "email", "password", "invite_token" }`. Без инвайта создаёт user + org + membership `admin`. `201` + `UserResponse` с `organization_id`.

```http
POST /api/v1/auth/switch-organization
```

Тело: `{ "organization_id": "<uuid>" }`. Только если есть membership. Перевыпускает куки с новым `org_id`. Чужой id → `404` (без списка доступных org в `detail`). Если `Host` привязан к другой org (M6) → отказ, без смены cookie.

```http
GET  /api/v1/organizations/members
POST /api/v1/organizations/invites
```

Список членов текущей org (org-admin). Инвайт: `{ "email", "role", "departments" }`. Существующий email → `status: added` (membership сразу). Новый → `status: invited` + `invite_token` для `POST /auth/register`. Не org-admin → `403`. Seats ≥ капа плана → `402`.

## Биллинг и квоты (M6)

Канон: [billing.md](billing.md). Только cookie-сессия текущей org. Поля `organization_id` / `plan` в теле не источник прав (план в теле `POST /billing/plan` — желаемый план, применяется провайдером к **сессионной** org).

```http
GET  /api/v1/billing/subscription
GET  /api/v1/billing/usage
POST /api/v1/billing/plan
```

`subscription`: `plan`, `billing_status`, период, entitlements (`sso`, `custom_domain`). `usage`: seats / pages / tokens и капы плана. Только org-admin; иначе `403`.

`POST /billing/plan` тело `{ "plan": "team" }`. `BILLING_PROVIDER=dev` — пишет Postgres сразу. `stripe` — `{ "checkout_url": "..." }` (без ключей → `503`). Не org-admin → `403`.

```http
POST /api/v1/billing/dev/simulate
```

Тело: `{ "action": "set_plan" | "past_due" | "cancel" | "activate", "plan": "enterprise" }`. Только `BILLING_PROVIDER=dev` **и** org-admin текущей org. Иначе `404` `{ "detail": "Not Found" }` (как выключенный inspect). Не принимает `organization_id`.

```http
POST /api/v1/billing/webhooks/stripe
```

Без cookie. Подпись Stripe. Идемпотентность `billing_events`. Не критерий M6; без адаптера — `404`.

## SSO (M6)

```http
GET  /api/v1/auth/sso/{slug}/login
POST /api/v1/auth/sso/{slug}/acs
```

`{slug}` → org коннектора. Нет коннектора / нет entitlement → `404` (не подтверждать чужой slug отдельно от «нет SSO»). Успех ACS — Set-Cookie `dw_*`, редирект на фронт. Compose `SSO_PROVIDER=dev` принимает фикстурную assertion.

```http
GET  /api/v1/organizations/sso
PUT  /api/v1/organizations/sso
```

Org-admin текущей org. План без SSO → `403`. Тело upsert: metadata IdP, `jit_enabled`, `attribute_map`, `sso_enforced`.

## Домен (M6)

```http
GET  /api/v1/organizations/domain
PUT  /api/v1/organizations/domain
POST /api/v1/organizations/domain/verify
```

Org-admin. План без custom domain: `PUT` custom hostname → `403`; платформенный `{slug}` читается всегда. `verify` — TXT/HTTP challenge. Неподтверждённый Host не пинит сессию.
