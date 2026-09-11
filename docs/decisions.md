# Решения (ADR)

Черновик ТЗ местами расходится с каркасом ChainWise. Ниже — зафиксированные отклонения. Продуктовые инварианты (RBAC **до** LLM, page-bounded chunking, hybrid + rerank, цитаты страниц) **не** ослабляются.

## ADR-001. Форк ChainWise, не greenfield

**Решение:** копировать обвязку из `../chainwise`, вырезать Solidity/Slither, заменить парсер и retrieval.

**Почему:** auth, Celery, SSE, Compose уже есть. Оценка «80% готово» верна для обвязки и **неверна** для `rag_engine.py` (поиск по одному контракту). Векторный индекс в Docwise — pgvector, не Qdrant.

**Следствие:** веха 0 — скелет; карта файлов — [reuse-from-chainwise.md](reuse-from-chainwise.md).

## ADR-002. Sync SQLAlchemy Session, не asyncpg

**ТЗ:** SQLAlchemy 2 + asyncpg.  
**Решение v1:** sync `Session`, как в ChainWise. FastAPI-хендлеры могут быть sync. Тяжёлая работа — в Celery.

**Почему:** переписывать весь backend на async «заодно» с портом — риск, не ценность. asyncpg можно взять отдельной вехой.

## ADR-003. UUID PK (отмена integer из ChainWise)

**ТЗ:** UUID.  
**Решение v1:** UUID PK на всех сущностях (`users`, `documents`, `document_chunks`, чаты, аудит). `chunk_id` — отдельная стабильная строка для re-upsert. Celery `document_id` и Redis `indexing_lock:{document_id}` — UUID-строка.

**Почему:** совпадает с ТЗ, не светит sequential id, проще когда объекты живут в MinIO/кэше/SSE. Integer PK ChainWise не копируем. Существующие integer-строки `users` мигрирует alembic `003`.

## ADR-004. SSE JSON-конверты ChainWise, не именованные `event:`

**ТЗ:** `event: citations` / `event: message` / `event: done`.  
**Решение:** строки `data: {json}\n\n` с полем `type`: `citations` → `token` → `meta` → `data: [DONE]`. Ошибки: `type: error`.

**Почему:** фронт ChainWise (`streamContractChat`) уже парсит этот протокол. Смысл ТЗ (цитаты до токенов) сохраняется.

## ADR-005. Hybrid search без scroll корпуса

**ТЗ:** native dense + BM25 в Qdrant.  
**ChainWise:** dense в Qdrant, BM25 в Python по **всем** чанкам одного контракта.

**Решение:** формулу `reciprocal_rank_fusion` (`k=60`) копировать. `bm25_scores` — unit-тесты. Вызов in-memory BM25 по dense-кандидатам — нет. Индекс — таблица Postgres + pgvector + FTS.

1. pgvector cosine Top-25 + FTS (`document_chunks.search_vector`, `simple` + GIN) Top-25, оба с ACL `organization_id` и `access_roles && allowed_roles`, затем RRF.
2. Запрещено `SELECT` всех чанков корпуса в RAM (в том числе для BM25).

Промежуточный шаг «BM25 только по dense Top-50» снят миграцией `012`.

## ADR-006. `last_error`, статус `processing`

**ТЗ:** `error_message`, статус `processing`.  
**Решение:** поле `last_error` (как `contracts.last_error`). Статус `indexing` ChainWise переименовать в `processing`.

## ADR-007. Cookie-session как в ChainWise

**ТЗ:** JWT в токене.  
**Решение v1:** только httpOnly cookies `dw_access` / `dw_refresh`. Login/register/google/refresh отдают `UserResponse`, не `access_token` в JSON. `Authorization: Bearer` игнорируется. `role` / `departments` всегда с сервера (membership), не из JWT. Access JWT ~15 мин, без claim `role`.

При `COOKIE_SAMESITE=none` (SPA на другом origin) мутации `/api/v1` требуют `Origin` из `CORS_ORIGINS` **или** заголовок `X-Requested-With: Docwise`. При `lax`/`strict` проверка не нужна. Refresh в Redis: SET fail-closed (503), GET fail-closed. Первая регистрация в пустой БД получает `admin`, остальные — `employee`. Google ID token без `email_verified=true` отклоняется.

## ADR-008. Эмбеддинги bge-small, не MiniLM

**Решение:** тот же FastEmbed-клиент, модель `BAAI/bge-small-en-v1.5` (384d cosine), реранкер `BAAI/bge-reranker-base`. MiniLM из ChainWise не оставлять «на время».

## ADR-009. Postgres 15 + pgvector + MinIO

**ТЗ (черновик):** Postgres 16 без pgvector, векторы в Qdrant.  
**Решение v1:** образ `pgvector/pgvector:pg15` (как в ChainWise). Расширение `vector` включено миграцией. Файлы — MinIO, не диск API-контейнера (локальный fallback допустим только за флагом для тестов).

## ADR-010. pgvector вместо Qdrant

**ТЗ / ChainWise:** отдельный сервис Qdrant.  
**Решение:** чанки и dense-векторы живут в Postgres (`document_chunks.embedding vector(384)`, cosine / HNSW). ACL — SQL `access_roles && allowed_roles` на каждый dense и sparse запрос. Сервиса Qdrant в Compose нет.

**Почему:** один datastore для метаданных и векторов; pgvector — явный инструмент стека. Инварианты RBAC и hybrid+RRF сохраняются.

## ADR-011. Дубликат `file_hash` → 409

**ТЗ / api.md:** `409` или вернуть существующую запись.  
**Решение v1:** `POST /documents/upload` при совпадении SHA-256 байтов отвечает `409` с фиксированным `detail`, без `id`/`title`/ACL существующего документа.

**Почему:** unique-индекс `file_hash` — источник истины; возврат существующей строки раскрыл бы метаданные файла, который текущий пользователь не должен видеть в `GET /documents` (например admin залил HR-only PDF). Повторная загрузка того же файла не меняет `access_roles`.

После [ADR-012](#adr-012-shared-b2b-saas-org_id-как-внешняя-стена) уникальность — `(org_id, file_hash)`. `409` только если дубль **в текущей** организации; совпадение байтов у другого клиента не подтверждается.

## ADR-012. Shared B2B SaaS: `org_id` как внешняя стена

**ТЗ (черновик) / v1:** один тенант; мультитеннант вне скоупа.  
**Решение:** целевой продукт — **shared B2B SaaS** (много организаций на одном деплое). Изоляция компаний — колонка `org_id` в SQL, не промпт и не тег в `access_roles`. Роли/отделы остаются **внутренней** ACL внутри org. Канон: [tenancy.md](tenancy.md).

**Почему:** `all` и `hr` — общие литералы. Без `org_id` сотрудник Globex видит General/HR Acme; LLM-кэш по одним ролям отдаёт чужой ответ; глобальный unique `file_hash` ломает одинаковые типовые PDF у двух клиентов.

**Следствие:**

- Пользователь глобальный (email); `role` и `departments` живут на `organization_memberships`.
- Текущая org — в сессии, не в теле chat/upload.
- Чанки, документы, чат-сессии, аудит, ключ MinIO и ключ LLM-кэша несут `org_id`.
- `require_admin` — admin **текущей** org. Оператора платформы с доступом к чужим корпусам нет.
- Реализация — [M5](milestones.md#milestone-5--shared-tenancy-b2b-saas).

## ADR-013. Биллинг за портом; квоты в БД; default `dev`

**ТЗ / «вне M5»:** Stripe, биллинг, квоты как продукт.  
**Решение:** план, `billing_status` и квоты — колонки организации. Провайдер оплаты (`BILLING_PROVIDER=dev` \| `stripe`) только пишет эти поля. Хендлеры upload/chat/инвайтов читают Postgres, не API эквайринга.

`dev` — дефолт Compose и не-`production`: org-admin меняет план без денег (бейдж Dev billing). Stripe test keys **не** заменяют `dev` (нужны аккаунт и сеть до `api.stripe.com`; с РФ это часто недоступно). Живой Stripe не критерий [M6](milestones.md#milestone-6--commercial-saas). Адаптер `stripe` в коде допустим; CI без сети. ЮKassa — отдельный провайдер тем же портом, не M6.

Коды: квота → `402`; фича не в плане → `403`; антиабьюз → `429`. Свою квоту не маскировать под `404`. `POST /billing/dev/simulate` только текущая org + `require_admin`; иначе `404`.

Канон: [billing.md](billing.md).

## ADR-014. SSO: org из коннектора, не из assertion

**Решение:** SAML 2.0 SP (OIDC IdP — тем же коннектором). Org определяется коннектором (`/auth/sso/{slug}/…`), не атрибутом assertion и не телом запроса. Успех ставит `dw_*` cookies (ADR-007); Bearer игнорируется.

JIT создаёт membership **только этой** org. `sso_enforced`: пароль, Google и `switch-organization` без свежего SSO в эту org — отказ. Группы IdP → `role` / `departments` по таблице org-admin; не в `access_roles` документов и не вместо `org_id`.

Compose: `SSO_PROVIDER=dev` (фикстурная assertion). Живой Okta/WorkOS не критерий M6. SCIM — вне скоупа.

## ADR-015. Custom domain: host-only cookie, hostname пинит org

**Решение:** `{slug}` уже на `organizations` (не ACL). Платформенный хост `{slug}.localhost` / `{slug}.docwise.app`; verified customer CNAME — опция Enterprise.

Сессионные куки **host-only** (без `Domain` на родительский суффикс). Если `Host` привязан к org, он **должен** совпасть с `org_id` сессии. Hostname — дополнительный конъюнкт, не замена SQL `organization_id`. На хосте Acme нельзя переключить сессию в Globex.

Неподтверждённый домен не биндится; один hostname — одна org. CORS/CSRF allowlist — из проверенного домена, не из тела. Compose: `/etc/hosts`, без Let's Encrypt в CI.
