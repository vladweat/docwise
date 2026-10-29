# Архитектурные решения (ADR)

Короткий журнал ключевых решений и причин. История не заменяет актуальный контракт: детали см. в
[архитектуре](../product/architecture.md), [tenancy](../platform/tenancy.md), [API](api.md) и коде.

## Карта решений

| Тема | Решение | ADR |
| --- | --- | --- |
| Приложение и база | Существующий FastAPI/Celery stack, sync SQLAlchemy, PostgreSQL | 001–003, 009–010 |
| Поиск | pgvector + FTS, RRF, rerank; без загрузки всего corpus в RAM | 005, 008, 010 |
| Auth и tenants | Cookie session; shared SaaS; `organization_id` — внешняя граница | 007, 012 |
| Биллинг и SSO | Provider port; connector выбирает org; fixture не является IdP | 013–014 |
| Hostname и RLS | Host только pin-ит org; RLS дополнительно защищает corpus tables | 015–016 |
| SSE и retention | JSON envelopes; ранний session meta; audit retention по сроку | 004, 017 |

## Решения

### ADR-001. Существующий application skeleton, не greenfield

Переиспользуем FastAPI, Celery, cookie auth, Compose и frontend API client. Corpus ingestion/retrieval реализованы
специально для Docwise; существующая инфраструктурная обвязка не означает, что corpus RAG был готов заранее.

### ADR-002. Sync SQLAlchemy Session

Используется SQLAlchemy 2 sync Session. HTTP handlers могут быть sync; тяжёлая обработка вынесена в Celery.
Переход на async не нужен без отдельной измеренной причины.

### ADR-003. UUID primary keys

Основные сущности используют UUID; `chunk_id` — отдельный стабильный строковый ключ для upsert.
Публичные ID не раскрывают последовательный номер записи.

### ADR-004. SSE JSON envelopes `data:`, not named `event:`

Все события передаются как `data: {json}\n\n`; тип находится в поле `type`. Для нового uncached чата после
успешного retrieval порядок: ранний `meta` (`session_id`, `message_id: null`) → `citations` → token events →
финальный `meta` → `[DONE]`. У existing session/cache hit раннего `meta` нет.

**Почему:** общий envelope упрощает frontend parser; ранний session ID позволяет показать chat до конца генерации.
Полный контракт: [api/chat.md](api/chat.md).

### ADR-005. Hybrid search без полного scroll corpus

Dense Top-25 в pgvector и FTS Top-25 в PostgreSQL применяют одинаковые tenant/ACL-фильтры до RRF (`k=60`).
В production нельзя загружать все chunks в память для BM25.

### ADR-006. `last_error` и `processing`

Документ хранит `last_error`; активная индексация обозначается `processing`. Ошибка не раскрывает внутренний stack.

### ADR-007. Cookie session

Клиент получает HttpOnly `dw_access`/`dw_refresh`, а не token в JSON. Role и departments читаются из membership,
не из JWT claim. Регистрация создаёт organization; вход в существующую выполняется через invite.
Подробности: [auth.md](../platform/auth.md).

### ADR-008. FastEmbed `bge-small`

Для embeddings используется `BAAI/bge-small-en-v1.5` (384d cosine); rerank — `BAAI/bge-reranker-base`.
Модельные версии следует менять вместе с evaluation и reindex plan.

### ADR-009. PostgreSQL 15 + pgvector + MinIO/S3

Metadata и vectors хранятся в PostgreSQL; исходные файлы — в private S3-compatible storage.
Локально это MinIO; публичный single-node demo использует Garage.

### ADR-010. pgvector вместо отдельного Qdrant

Vectors находятся в `document_chunks.embedding`; tenant и role ACL применяются SQL предикатами для dense и FTS.
Отдельный vector-only сервис не нужен текущему масштабу проекта.

### ADR-011. Duplicate `file_hash` → `409`

Повтор файла в одной организации возвращает `409 resource.conflict`, без существующего ID/title.
Уникальность `(organization_id, file_hash)` не подтверждает совпадение между разными организациями.

### ADR-012. Shared B2B SaaS: `org_id` as outer wall

Пользователи глобальные; документы, сессии и audit принадлежат организации. `organization_id` — внешняя граница,
а `access_roles` — внутренний ACL. Текущая org определяется сессией, не prompt/body.
Канонический документ: [tenancy.md](../platform/tenancy.md).

### ADR-013. Billing provider port, quotas in DB, default `dev`

Plan/status/quota хранятся на organization row; handlers читают БД. `dev` не списывает деньги и используется в local,
CI и публичном demo. Stripe подключается отдельно; коммерческая интеграция не ослабляет tenant/ACL проверки.

### ADR-014. SSO: org from connector, not assertion

Целевая модель определяет tenant по connector slug; assertion не задаёт `organization_id`.
**Текущий runtime:** production SAML/OIDC adapter отсутствует. `SSO_PROVIDER=dev` — fixture; public demo использует `disabled`.
Подробности и ограничения: [auth.md](../platform/auth.md).

### ADR-015. Custom domain pins organization; cookie remains host-only

Проверенный hostname — дополнительное условие для текущей org, не замена SQL tenant filter.
Cookie не устанавливает parent `Domain`; смена tenant на hostname другой org запрещена.

### ADR-016. PostgreSQL RLS только на corpus

RLS защищает `documents` и `document_chunks`; inner `access_roles` проверяется приложением.
Base/public-demo Compose задаёт `DOCWISE_RLS_SESSION_ROLE=docwise_rls`, а `db-migrate` создаёт роль/grants.
PostgreSQL superuser обходит RLS; application filters обязательны даже при включённом RLS.

### ADR-017. Data retention and erasure (EU pilot policy)

Audit не хранит body chunks; срок хранения настраивается через `AUDIT_LOG_RETENTION_DAYS` (default 90).
Один Celery Beat ежедневно очищает просроченные audit rows. Chat history удаляется вместе с сессией;
удаление файла использует повторяемый storage outbox.
Актуальная policy и ограничения: [data-retention.md](../platform/data-retention.md).
