# Техдолг

Снимок после M0–M6 (2026-09-10). Инварианты продукта (SQL `organization_id` + `access_roles` до LLM, page-bounded chunking, SSE цитаты→токены, UUID PK) **не** в этом списке: они соблюдены.

В коде нет `TODO` / `FIXME`. Долг структурный. ADR-002 (sync Session), ADR-004 (SSE JSON), ADR-007 (cookies), ADR-010 (pgvector), ADR-013 (`BILLING_PROVIDER=dev`) — решения, не мусор. ADR-005 закрыт: sparse — Postgres FTS (`tsvector` + GIN), Top-25 независимо от dense.

Как помечать: закрытый пункт — `- [x]` в том же изменении, что и код/тест. Не вычёркивать high, пока нет регрессионного теста.

## Раскладка и практики

Не баги runtime, а то, как проект врёт о своей структуре.

- [x] **Плоский `services/` и `docs/`.** Домен — подпакеты `chat/`, `documents/`, `ingestion/`, `retrieval/`, `org/` (+ `billing/`). Документация — `docs/product|platform|pipeline|engineering|portfolio|meta/`; индекс в [docs/README.md](../README.md).

### Версия API — строка, не граница модуля

- [x] **Нет `app/api/v1/`.** Роутеры в `app/api/v1/`, префикс `API_V1` (`app/api/__init__.py`), один `include_router` в `main.py`. CSRF, SSO paths и клиент (`apiFetch` + `v1Url`) берут ту же константу. Health остаётся на `/health` `/ready`. Pytest по-прежнему бьёт в публичный URL `/api/v1` (это контракт, не grep-долг). `FastAPI(..., version="0.1.0")` — semver приложения, не URL.

- [x] **Health и миграции в `main.py`.** Liveness/readiness — `app/api/health.py`; `alembic upgrade` — `app/core/migrations.py`; lifespan и CORS/CSRF middleware — `app/core/lifespan.py` / `app/core/middleware.py`. `main.py` собирает приложение.

### Слои названы, границы нет

- [x] **`core` vs `utils` vs `services` без правила.** `core/` — инфра процесса (config, DB, JWT, cookies, CSRF, Redis, rate limit, логи). `services/` — домен по подпакетам (`chat/`, `org/`, …); middleware может звать `org.domains` / `org.sso`. Правило: [conventions.md](../meta/conventions.md).

- [x] **Celery не там, куда указывает карта.** Задача в `backend/worker/celery_app.py` (`celery -A worker.celery_app`). Прод-образ копирует `app/` и `worker/`, не `tests/`.

- [x] **Модели свалены не по агрегату.** `organization` (org, membership, invite, plan); `sso`; `domain`; `billing` (`BillingStatus` + events); `chat`; `audit` (`RagAuditLog`). HTTP домена — `api/v1/domains.py`.

- [x] **SSO разрезан по трём пакетам.** HTTP ACS/login и CRUD коннектора — `api/v1/sso.py`; логика — `services/org/sso.py`. `foreign_organization_id()` — `schemas/common.py`.

- [x] **Имена сервис ≠ ресурс.** `api/v1/documents.py` → `services/documents/`. `api/v1/search.py` → `services/retrieval/inspect.py`. Retrieval чата — `services/retrieval/`.

- [x] **Бочки `__init__.py` врут.** `services/__init__.py` описывает слой. `schemas/__init__.py` не реэкспортирует контракты — import из модуля ресурса.

### Дубли и наследие ChainWise

- [x] **Два линтера.** Один ruff: CI и `make lint` — `ruff check app tests scripts worker`. Конфиг `backend/ruff.toml`. flake8 и `.flake8` убраны.

- [x] **`test_rag_engine.py` тестирует `retrieval.py`.** Файл — `test_retrieval.py`. Фикстура — текст политики/графика, не Solidity (`onlyOwner` / `msg.sender`).

- [x] **Два токенизатора.** Оба в `services/text.py`: `ingest_tokens` (бюджет чанка) и `lexical_tokens` (лексика для unit-теста BM25 и FTS-запроса). `ROLE_RE` / `normalize_role_tags` — там же, для `documents` и `organizations`.

- [x] **Мёртвый фронт.** Убраны неиспользуемый `API_URL` и `lib/auth-storage.ts` (`docwise_token` в localStorage). `JSONResponse` везде из `fastapi.responses`.

### Frontend: App Router

- [x] **Страницы — RSC, фичи колоцированы.** `app/*/page.tsx` без `"use client"`: metadata + клиентский остров из `features/`. Чат (UI + Zustand + `lib/chat`) — `features/chat/`; документы, settings, auth, health — рядом со своими экранами. Общее: `components/ui` (shadcn), `lib/api.ts`, `stores/toast-store.ts`.

- [x] **Клиент хардкодит `/api/v1/...` в каждой функции** вместо `apiFetch("/auth/login")` + базовый префикс. Закрыто вместе с `app/api/v1/`: `API_V1` + `v1Url` в `lib/api.ts`; `/ready` без префикса.

- [x] **shadcn — система экранов.** К button/card/input/label/badge/separator/textarea добавлены dialog, alert-dialog, select, checkbox, table, tabs, progress, alert, skeleton, fade-in (`framer-motion`). Модалки, таблица KB, селекты, чекбоксы, квоты и тосты идут через эти примитивы, не через сырой Tailwind.

## High

Исправлять до первого реального тенанта / нагрузки.

- [x] **LLM-кэш без инвалидации.** Ключ `llm_cache:{v}:{org_id}:{generation}:{roles_hash}:{question_hash}`, TTL 24 ч (`backend/app/services/chat/llm_cache.py`). Поколение — `organizations.llm_index_generation`; bump + SCAN-delete ключей org при PATCH ACL, DELETE и ready ingest. Cache hit пишет `tokens_used=null` (квоту не жжёт). История диалога в ключ по-прежнему не входит.

- [x] **Sparse-поиск — всё ещё interim ADR-005.** `document_chunks.search_vector` (`simple`, GIN). FTS Top-25 с тем же `organization_id` и `access_roles && allowed_roles`, независимо от dense, затем RRF (`backend/app/services/retrieval/`). Регрессия: `test_sparse_fts_finds_lexical_hit_outside_dense_top`. Живой eval (`make eval` / `make eval-retrieval`) после смены fusion не гонялся — смотреть `hb-security-email`, `eng-python`.

- [x] **Чат держит DB-сессию на весь SSE.** `iter_sse_events` закрывает сессию после retrieval (эмбеддинг запроса и cross-encoder — без соединения); persist — отдельная сессия. `create_engine(..., pool_size=DB_POOL_SIZE, max_overflow=DB_MAX_OVERFLOW)` (дефолт 10/20).

## Medium

- [x] **Двойная запись ACL и `org_id` на чанки.** Составной FK `document_chunks (document_id, organization_id) → documents (id, organization_id)` (миграции `013`–`014`; простой `document_id` FK снят, иначе два пути ломают join). PATCH копирует `access_roles` только на чанки той же org. RLS по-прежнему вне скоупа ([milestones.md](../product/milestones.md)).

- [x] **Глобальный HNSW, фильтр по org после индекса.** Индекс тот же; перед dense `SET LOCAL hnsw.iterative_scan = relaxed_order` и `hnsw.max_scan_tuples` (`HNSW_MAX_SCAN_TUPLES`, дефолт 20000). Org-partitioned ANN не делали.

- [x] **Сервисы кидают `HTTPException`.** Домен — `AppError` (`core/errors.py`), хендлер в `main.py`. `HTTPException` остаётся в `api/` / `core/` (deps, CSRF, rate limit).

- [x] **God-модули.** `api/v1/auth/` (password / Google / session), `chat/` (`sse`, `persist`, `sessions`), `ingestion/` (`worker`, `indexing`), settings: `billing-section` / `sso-section` / `domain-section`.

- [x] **Delete: MinIO раньше Postgres.** Сначала commit строки БД, потом `delete_object`. Сбой MinIO после commit — `204`, сирота в бакете, список согласован.

- [x] **`datetime.now()` без UTC в `_persist_turn`.** `utcnow_naive()` (`core/time.py`), как у квот/инвайтов.

- [x] **Роль `manager` — ярлык, не capability.** Manager: KB (`require_kb_admin`). Admin: инвайты, биллинг, SSO, домен, inspect.

- [x] **Квоты без блокировок.** `SELECT FOR UPDATE` на org. Upload считает `page_count` входящего PDF и `pending`. Persist чата повторно проверяет токены под локом.

- [x] **Frontend: 0 тестов; CI только `tsc`.** Vitest: SSE, `apiUrl` host-only, цитата → viewer, тост квоты. CI: `tsc` + `vitest` + `next lint` + `next build`.

- [x] **Ответ чата — plain text.** `AnswerMarkdown` (GFM). Промпт: `[Title.pdf, стр. N]`, списки/таблицы Markdown.

- [x] **SSO и Stripe — уровня Compose.** Живой IdP по-прежнему ADR-014 (`SSO_PROVIDER=dev`). Stripe: org только по `stripe_customer_id` / `stripe_subscription_id` или `client_reference_id` на `checkout.session.completed`; `metadata.organization_id` больше не резолвит тенанта.

## Low

- [x] **Статус M6 в таблице roadmap.** [milestones.md](../product/milestones.md): строка сводки «готово», чекбоксы и критерий вехи — `[x]`.

- [x] **Celery: `time_limit` / `acks_late` / prefetch.** `acks_late`, `worker_prefetch_multiplier=1`, soft 20 мин / hard 25 мин, до 3 ретраев с backoff; `SoftTimeLimitExceeded` / `TimeLimitExceeded` не ретраятся (`worker/celery_app.py`).

- [x] **mypy.** `backend/mypy.ini`, `make lint` и CI (`mypy app worker`). Compose: `minio/minio:latest` (pin не делаем).

- [x] **`_persist_turn` не глотает исключение.** Пишет Sentry, SSE `type: error` (`Chat was not saved. Try again.`) после токенов; `session_id` / `message_id` в meta остаются null. UI не затирает ответ.

- [x] **DELETE сессии чата.** `DELETE /api/v1/chat/sessions/{id}` (свои, текущая org; иначе 404). `pdfjs-dist` 4.10.38 (Next 15). Access JWT 15 мин без claim `role`; клиент рефрешит по 401. Миграция `001` — UUID baseline; integer PK закрыт `003`.

## Не долг

- Tenancy: `org_id` из сессии, не из тела; `all` только внутри org; ключ LLM-кэша уже включает `org_id` + роли (дыра — инвалидация, не кросс-тенант).
- Чанк на одной странице; meta-заголовок эмбеддинга не попадает в сниппет цитаты.
- Inspect — org-admin + `ENABLE_SEARCH_INSPECT`.
- Upload не парсит PDF; байты только через API с тем же ACL.
- Cookies host-only (ADR-015).
- MinIO в Compose — `minio/minio:latest` (намеренно не pin).

Eval (employee, 35 кейсов, 2026-09-10, ещё BM25 по dense): Faithfulness 1.000, Context Precision 0.976, ACL 0 утечек, page hit 0.929. После FTS прогон не обновлялся. Отчёт: [rag_benchmark.md](../reports/rag_benchmark.md).
