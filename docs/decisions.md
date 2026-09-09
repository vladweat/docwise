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

**Решение:** формулы `bm25_scores` / `reciprocal_rank_fusion` (`k=60`) копировать. Вызов — нет. Индекс — таблица Postgres + pgvector.

1. Цель: pgvector cosine Top-25 + FTS/BM25 Top-25, оба с ACL `access_roles && allowed_roles`, затем RRF.
2. Пока отдельного sparse-индекса нет: dense Top-50 с ACL, BM25+RRF **только по этим кандидатам**.
3. Запрещено `SELECT` всех чанков корпуса в RAM.

## ADR-006. `last_error`, статус `processing`

**ТЗ:** `error_message`, статус `processing`.  
**Решение:** поле `last_error` (как `contracts.last_error`). Статус `indexing` ChainWise переименовать в `processing`.

## ADR-007. Cookie-session как в ChainWise

**ТЗ:** JWT в токене.  
**Решение v1:** только httpOnly cookies `dw_access` / `dw_refresh`. Login/register/google/refresh отдают `UserResponse`, не `access_token` в JSON. `Authorization: Bearer` игнорируется. `role` / `departments` всегда с сервера.

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
