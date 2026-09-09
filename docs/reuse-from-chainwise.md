# Переиспользование ChainWise

Источник: соседний репозиторий `../chainwise` (AI-аудит Solidity). Docwise **не пишется с нуля**: берём каркас, выкидываем компилятор/Slither, меняем парсер и retrieval.

Оценка «80% архитектуры уже есть» верна для **обвязки**. Она **неверна**, если копировать `rag_engine.py` как есть: там поиск по **одному** `contract_id`, а не по корпусу документов с RBAC.

## Чего нельзя копировать слепо

| Утверждение из разбора | Факт в ChainWise | Что делать в Docwise |
| --- | --- | --- |
| Hybrid search = Qdrant dense + BM25 sparse | Dense в Qdrant; BM25 **в Python** по пулу чанков | Формулы `bm25_scores` / `reciprocal_rank_fusion` копировать. Индекс — **pgvector**, не Qdrant |
| Пул чанков | `scroll_contract_chunks(contract_id)` — **все** точки одного контракта | Запрещено скроллить весь корпус. Кандидаты только из SQL query + ACL |
| Коллекция | `code_chunks`, фильтр `contract_id: int`, payload строк `.sol` | Таблица `document_chunks`, UUID `document_id`, `page_number`, `access_roles`, `embedding vector(384)` |
| Эмбеддинги | `all-MiniLM-L6-v2` 384d FastEmbed | Тот же клиент; модель `BAAI/bge-small-en-v1.5` |
| Реранкер | нет | Добавить `bge-reranker-base` |
| SSE | JSON в `data:`: `citations` → `token` → `meta` → `[DONE]` | **Оставить этот протокол**, не `event: message` из чернового ТЗ |
| Статусы | `pending` / `indexing` / `ready` / `failed`, поле `last_error` | Маппинг: `indexing` → `processing`; поле можно оставить `last_error` |
| Auth роли | `user` \| `admin`, PK `int`, sync SQLAlchemy | `employee` \| `manager` \| `admin` + `departments[]`; PK **UUID** |
| SHA256 | `sha256(chain_id:source_code)` → синтетический адрес | SHA256 **байтов PDF** → `documents.file_hash` |
| Postgres | `pgvector/pgvector:pg15` | Тот же образ. Векторы **в Postgres** (`CREATE EXTENSION vector`). Отдельного Qdrant нет. MinIO — новый сервис |
| ORM | sync `SessionLocal` | **Оставить sync** (как в ChainWise). asyncpg в v1 не обязателен |

## Что забирать почти целиком

Пути — относительно `../chainwise`.

### RAG / SSE

- `backend/app/services/rag_engine.py` — только чистые функции и стрим, **не** Solidity-ветки:
  - `bm25_scores`, `tokenize`, `reciprocal_rank_fusion` (`RRF_K = 60`)
  - `stream_openai`, `_sse`, `iter_sse_events` (каркас событий)
  - Redis LLM cache (`llm_cache:{version}:...`) — в ключ обязательно добавить **роли пользователя**, иначе кэш станет дырой ACL
- FastEmbed-клиент из `qdrant_indexer.py` (`_FastEmbedEncoder`, `encode_texts`) — **без** Qdrant upsert/search
- `backend/tests/test_rag_engine.py` — тесты BM25/RRF

Не копировать `qdrant_indexer` search/upsert. Не переносить из `rag_engine.py`: overview-вопросы про аудит, interface stubs, dump всех primary chunks, Slither findings в промпте, привязку к одному контракту.

### Celery и индексы

- `backend/app/celery_config.py` — задача + `failed`/`last_error` + release lock
- `backend/app/utils/redis_lock.py` — ключ сменить на `indexing_lock:{document_id}`
- Машина состояний из `indexing_worker.py` / `contract_service.py` (обёртка try/except), без `solc`/`slither`/`split_code_chunks`

### Auth, лимиты, логи, health

- `backend/app/api/auth.py`, `core/auth_cookies.py`, `core/security.py`, `core/deps.py`
- Куки переименовать `cw_*` → `dw_*`
- `backend/app/utils/rate_limit.py`, `utils/logging.py` (расширить redaction под текст PDF)
- `GET /health` (liveness) и `GET /ready` (Postgres, pgvector, Redis, MinIO); без slither/Qdrant
- `backend/tests/test_auth*.py`, `test_rate_limit.py`, `test_logging.py`

Google OAuth — опционально, не блокер v1.

### Frontend

- `frontend/src/lib/api.ts` — `credentials: "include"`, `streamContractChat` (переименовать, сменить URL)
- `frontend/src/types/contract.ts` — тип `ChatStreamEvent` оставить; `Citation` заменить на `{doc_id, doc_title, page, snippet}`
- Чат: `contract-chat-panel.tsx` (авторесайз, бейджи, клик по цитате)
- Поллинг: идея `contract-indexing-status.tsx`, шаги пайплайна переписать (parse → chunk → embed)
- `components/ui/*`, auth pages, `auth-provider.tsx`

Не тащить: `contract-source-viewer.tsx`, findings, risk badge, загрузку адреса Etherscan.

### Инфра

- `docker-compose.yml` — postgres (pgvector), redis, backend, celery-worker, frontend. Удалить `slither` и **Qdrant**. Добавить MinIO. Убрать `SOLCX_*`, `SLITHER_URL`, `RISK_MODEL_PATH`, `QDRANT_*`
- `.github/workflows/ci.yml` — оставить lint + pytest; убрать cov на `pragma_parser`/`risk_scorer`
- `Makefile` — `up`/`down`/`test`/`logs`; вычистить `solc`/`slither`/`train-risk`

## Что писать с нуля

1. `pdf_parser.py` + page-bounded chunker (не `semantic_splitter.py` на AST).
2. SQL-фильтр `access_roles && allowed_roles` на **каждый** search (dense и sparse/BM25-кандидаты).
3. Cross-encoder rerank Top-15 → Top-4, порог 0.25.
4. PDF viewer + `#page=N` / подсветка; upload drag-and-drop + чекбоксы ролей.
5. `eval/run_eval.py` (Ragas).
6. Таблицы `documents`, `rag_audit_logs`; сессии чата без `contract_id`.

## Целевой гибридный поиск (не как в ChainWise)

```
pgvector cosine Top-25  ──┐
  ACL access_roles &&      ├── RRF(k=60) Top-15 → rerank → Top-4 → LLM
FTS / BM25 Top-25          ┘
  + тот же ACL
```

Промежуточный шаг, если FTS-колонки ещё нет: dense Top-50 с ACL, затем **in-memory BM25+RRF только по этим 50**, не по всему индексу.

## Порядок работ

См. [milestones.md](milestones.md): форк каркаса → ingest PDF → corpus retrieval + RBAC → UI → eval.
