# Модель данных

Два слоя в одном Postgres: таблицы пользователей/организаций/файлов/чатов и индекс чанков с pgvector. Изоляция компаний — `org_id` ([tenancy.md](tenancy.md)). ACL чанка дублирует `documents.access_roles`; `org_id` чанка дублирует документ. Первичные ключи — **UUID** (`gen_random_uuid()` / SQLAlchemy `uuid4`). Роли и фильтр: [auth.md](auth.md).

До M5 таблиц организаций не было. Ниже — модель SaaS; миграция `007` переносит роли на membership и создаёт bootstrap-org для уже существующих строк. Колонки `users.role` / `users.departments` удалены.

## PostgreSQL

### `organizations` (M5)

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `name` | String | Отображаемое имя компании |
| `slug` | String unique | Стабильный ключ URL (`{slug}.localhost`); не ACL |
| `status` | `active` \| `suspended` | Suspended — логин в эту org отклоняется; M6: ещё `past_due` / cancel биллинга |
| `plan` | `starter` \| `team` \| `enterprise` | M6; новая org — `starter`. Не источник `org_id` |
| `billing_status` | `active` \| `past_due` \| `canceled` | M6; `past_due`/`canceled` → `status = suspended` |
| `current_period_start` / `current_period_end` | DateTime nullable | Окно квоты токенов |
| `sso_enforced` | Boolean | M6; default false |
| `llm_index_generation` | Integer | Поколение корпуса для LLM-кэша; bump при PATCH ACL / DELETE / ready ingest |
| `stripe_customer_id` / `stripe_subscription_id` | String nullable | Только адаптер Stripe; не JWT |
| `created_at` | DateTime | |

### `organization_memberships` (M5)

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `organization_id` | UUID FK → organizations | Каскад при удалении org (отдельная процедура, не случайный DELETE) |
| `user_id` | UUID FK → users | |
| `role` | `admin` \| `manager` \| `employee` | CHECK; **не** колонка `users` |
| `departments` | `ARRAY(String)` | Например `['engineering', 'hr']` |
| `created_at` | DateTime | |

Unique `(organization_id, user_id)`. `allowed_roles` для поиска = `{membership.role}` ∪ `membership.departments` ∪ `{all}` — только этой org.

### `organization_invites`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `organization_id` | UUID FK | |
| `email` | String | Нормализованный lower-case |
| `role` | `admin` \| `manager` \| `employee` | Роль будущего membership |
| `departments` | `ARRAY(String)` | |
| `token_hash` | String unique | SHA-256 токена; сырой токен отдаётся org-admin один раз |
| `invited_by_user_id` | UUID FK nullable | |
| `expires_at` | DateTime | По умолчанию 14 дней |
| `accepted_at` | DateTime nullable | |
| `created_at` | DateTime | |

Unique pending `(organization_id, email) WHERE accepted_at IS NULL`. Существующий пользователь при инвайте получает membership сразу, без токена. Инвайт сверх seats-квоты плана → `402` (M6).

### `organization_sso_connections` (M6)

Один коннектор на org в v1. Org для ACS — FK, не атрибут IdP.

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `organization_id` | UUID FK unique | |
| `protocol` | `saml` \| `oidc` | |
| `idp_entity_id` / metadata | Text / JSONB | Сертификат IdP, ACS URL строится из slug |
| `attribute_map` | JSONB | группы IdP → `role` / `departments` |
| `jit_enabled` | Boolean | default false |
| `created_at`, `updated_at` | DateTime | |

### `organization_domains` (M6)

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `organization_id` | UUID FK | |
| `hostname` | String unique | lower-case; `{slug}.localhost` или CNAME клиента |
| `kind` | `platform` \| `custom` | |
| `verified_at` | DateTime nullable | custom без verify не пинит Host |
| `created_at` | DateTime | |

Неподтверждённый custom не участвует в резолве. Unique hostname глобально.

### `billing_events` (M6)

Идемпотентность вебхука и `dev/simulate`.

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `organization_id` | UUID FK | всегда текущая org события; simulate чужой org не создаёт строку |
| `provider` | `dev` \| `stripe` | |
| `external_id` | String | unique вместе с `provider` |
| `event_type` | String | |
| `payload` | JSONB | без chunk text, без PDF |
| `processed_at` | DateTime | |

### `users`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | `gen_random_uuid()` |
| `email` | String unique | Логин |
| `hashed_password` | String nullable | Пусто у Google-only / SSO-only аккаунта |
| `google_id` | String unique nullable | `sub` из ID token |
| `is_active` | Boolean | |
| `created_at` | DateTime | |

Роли ChainWise — только `user`/`admin`. Здесь: `admin` | `manager` | `employee` плюс `departments[]` **на членстве в организации**.  
`allowed_roles` для фильтра поиска = `{role}` ∪ `departments` ∪ `{all}` текущей org (сборка — в [retrieval](retrieval.md)). Email уникален глобально: один человек — несколько org.

### `documents`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `organization_id` | UUID FK → organizations | M5; NOT NULL. Источник — сессия upload, не тело |
| `title` | String | Имя для UI |
| `file_path` | String | Ключ в MinIO (`orgs/{org_id}/…`) |
| `file_hash` | String | SHA-256; unique **вместе с** `organization_id` |
| `file_size_bytes` | Integer | |
| `total_pages` | Integer | Резерв квоты на upload (`page_count`); ingest может уточнить |
| `access_roles` | `ARRAY(String)` | Например `['admin', 'hr']` — внутри org, не id компании |
| `status` | Enum `pending` \| `processing` \| `ready` \| `failed` | В ChainWise аналог — `indexing`; при порте переименовать |
| `last_error` | Text nullable | Как `contracts.last_error` в ChainWise |
| `ingestion_stage` | String nullable | `parse` \| `chunk` \| `embed`; для поллинга `GET .../status` |
| `created_at`, `updated_at` | DateTime | |

Индексы: unique `(organization_id, file_hash)`, unique `(id, organization_id)` (цель составного FK чанков), `status`, `(organization_id)`, GIN по `access_roles`.

### `chat_sessions`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `organization_id` | UUID FK | M5; копия с пользователя на момент создания, сессии не пересекают org |
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
| `sources` | JSONB | Список цитат: `doc_id` (UUID), `title`, `page` (PDF), `section` (DOCX), `snippet` |
| `created_at` | DateTime | |

### `rag_audit_logs`

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | |
| `organization_id` | UUID FK | M5; та же org, что у retrieval |
| `user_id` | UUID FK | |
| `session_id` / `message_id` | UUID nullable | Связь с чатом |
| `query` | Text | |
| `retrieved_chunk_ids` | JSONB, список UUID-строк | PK `document_chunks.id` после реранкера; не `chunk_id`, не текст |
| `latency_ms` | Integer | |
| `tokens_used` | Integer nullable | Чат; у inspect — null |
| `feedback` | SmallInt nullable | `1` / `-1` с `POST /chat/feedback`; только свои assistant-сообщения |
| `created_at` | DateTime | |

Пишут чат и inspect. Inspect: `session_id` / `message_id` null. Колонок `content` / `snippet` нет. Не-UUID в `retrieved_chunk_ids` отбрасываются. Не писать полный текст чанков (в т.ч. restricted), если лог может увидеть тот же пользователь через API.

## Postgres: таблица `document_chunks`

Расширение `vector`. Dense: `embedding vector(384)`, cosine (`BAAI/bge-small-en-v1.5`). Индекс HNSW. ACL, `document_id` и (M5) `organization_id` — обычные колонки + GIN по `access_roles` + btree/hash по `organization_id`.

Sparse: колонка `search_vector` (`tsvector`, `to_tsvector('simple', content)`, GIN). Каждый поиск: `organization_id = :current_org` **и** GIN ACL. Dense Top-25 и FTS Top-25 независимы, затем RRF.

| Поле | Тип | Заметки |
| --- | --- | --- |
| `id` | UUID PK | стабильный ключ чанка в API |
| `document_id` | UUID | как `contract_id` в ChainWise, но UUID; FK только в составе пары с `organization_id` |
| `organization_id` | UUID | M5; копия с документа. Единственный FK на документ: `(document_id, organization_id) → documents(id, organization_id)` |
| `chunk_id` | String unique | стабильный ключ для re-upsert (`{document_id}:{page}:{n}`) |
| `page_number` | Integer | |
| `section_title` | String nullable | |
| `is_table` | Boolean | |
| `access_roles` | `ARRAY(String)` | копия с документа |
| `content` | Text | фрагмент **без** мета-заголовка `[Document: …]` (он только в `embed_text` перед FastEmbed) |
| `search_vector` | `tsvector` generated | `to_tsvector('simple', content)`, GIN; не писать из приложения |
| `token_count` | Integer | |
| `embedding` | `vector(384)` | cosine |
| `doc_title` | String nullable | для цитат |
| `bbox` / `highlight_rects` | JSONB nullable | подсветка во вьюере |

При переиндексации удалять строки по `document_id`, затем вставлять заново. `organization_id` чанка всегда равен документу (составной FK, не только приложение).

## MinIO

Bucket `documents` — приватный (без anonymous `s3:GetObject`). `documents.file_path` — ключ объекта. Префикс `orgs/{organization_id}/…`. Байты отдаются только через API (`GET /documents/{id}/raw`). Публичные URL и вечные pre-signed ссылки запрещены.

## Согласованность ACL

`documents.access_roles` — источник истины для **внутренней** ACL. `documents.organization_id` — источник истины для тенанта. Обе колонки чанка обязаны совпадать с документом. Смена ролей: `PATCH /api/v1/documents/{id}` обновляет документ **и** все его чанки (без re-embed). `organization_id` с клиента не принимается. Поиск никогда не доверяет ролям и org, присланным в теле запроса.
