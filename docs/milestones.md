# Roadmap

Ориентир v1: **1–2 недели** после M0, потому что каркас уже в `../chainwise`. Не начинать с пустого Compose. Карта файлов: [reuse-from-chainwise.md](reuse-from-chainwise.md). Продукт: [srs.md](srs.md). Отклонения: [decisions.md](decisions.md).

**Как отмечать.** Закрытый пункт — `- [x]` в том же изменении, что и код. Критерий вехи не ставить, пока не выполнен целиком. Приёмка продукта — в конце файла и в [srs.md](srs.md) §6.

| Веха | Статус | Ориентир |
| --- | --- | --- |
| [M0 Скелет](#milestone-0--скелет-из-chainwise) | готово | 0.5–1 день |
| [M1 PDF ingest](#milestone-1--pdf-ingest) | готово | 2–3 дня |
| [M2 Retrieval + RBAC + SSE](#milestone-2--corpus-retrieval--rbac--sse) | готово | 3–4 дня |
| [M3 Split-screen UI](#milestone-3--split-screen-ui) | открыто | 2–3 дня |
| [M4 Eval, CI, портфолио](#milestone-4--eval-ci-портфолио) | открыто | 1–2 дня |

```mermaid
flowchart LR
  M0[M0 fork ChainWise] --> M1[M1 PDF ingest]
  M1 --> M2[M2 retrieval + RBAC]
  M2 --> M3[M3 PDF UI]
  M2 --> M4[M4 eval + CI]
  M3 --> M4
```

M3 и M4 после M2 можно вести параллельно, но клик по цитате и eval оба требуют живого retrieval.

---

## Milestone 0 — Скелет из ChainWise

**Критерий:** `make up` поднимает postgres, redis, minio, backend, worker, frontend. Логин/регистрация работают (cookies, UUID `id`). `/ready` показывает `pgvector: ok`.

### Каркас

- [x] Скопировать `backend/` без slither / solc / risk / etherscan
- [x] Скопировать `frontend/` (ui + auth + api client)
- [x] `docker-compose.yml`, `Makefile`, GitHub Actions
- [x] Выкинуть сервис `slither`, пути `SOLCX_*` / `RISK_MODEL_*` / Qdrant
- [x] Добавить MinIO
- [x] Образ Postgres `pgvector/pgvector:pg15`, миграция `CREATE EXTENSION vector`
- [x] Переименовать куки `cw_*` → `dw_*`, приложение → Docwise
- [x] Sync SQLAlchemy Session (не asyncpg)
- [x] UUID PK на `users` (и заложить UUID на остальные сущности)
- [x] Роли `admin` \| `manager` \| `employee` + `departments[]`, CHECK на `role`

### Сессия и здоровье

- [x] Cookie-only auth: login/register/google/refresh отдают `UserResponse`, без `access_token` в JSON
- [x] `Authorization: Bearer` игнорируется
- [x] CSRF при `COOKIE_SAMESITE=none` (`Origin` / `X-Requested-With: Docwise`)
- [x] Refresh Redis fail-closed; rate limit login/register/google по IP
- [x] Google требует `email_verified`; первый пользователь в пустой БД — `admin`
- [x] `GET /health` — liveness; `GET /ready` — postgres, pgvector, redis, minio
- [x] OpenAPI `/docs` выключен в `production`

**Критерий вехи:** [x] стек поднимается, логин работает, `/ready` с `pgvector: ok`

---

## Milestone 1 — PDF ingest

Спеки: [ingestion.md](ingestion.md), [data-model.md](data-model.md), [api.md](api.md). Не парсить PDF в upload-handler.

**Критерий:** upload → `ready`, чанки с `page_number` и `access_roles`.

### Данные и хранение

- [x] Модель `documents`: UUID PK, `title`, `file_path`, `file_hash`, `file_size_bytes`, `total_pages`, `access_roles[]`, `status` (`pending` \| `processing` \| `ready` \| `failed`), `last_error`
- [x] Модель `document_chunks`: UUID PK, UUID `document_id`, стабильный `chunk_id`, `page_number`, `section_title`, `is_table`, `access_roles[]` (копия с документа), `content`, `token_count`, `embedding vector(384)`, `doc_title`, bbox/highlight JSONB
- [x] Индексы: `file_hash`, `status`, GIN `access_roles`, HNSW на `embedding`
- [x] Alembic-миграция таблиц (не `create_all` в рантайме)
- [x] MinIO bucket `documents`; байты только через API, без публичных вечных URL

### API документов

- [x] `POST /api/v1/documents/upload` — multipart PDF + `access_roles`, `201` + `pending`, enqueue Celery
- [x] SHA-256 байтов; дубликат `file_hash` → `409` (без тела существующей записи, [ADR-011](decisions.md))
- [x] `GET /api/v1/documents` — пагинация, фильтр `status`, только ACL пользователя
- [x] `GET /api/v1/documents/{id}/status` — статус + `last_error`; нет прав / нет записи → `404`
- [x] `GET /api/v1/documents/{id}/raw` — `application/pdf`, тот же ACL, `404` без утечки названия
- [x] `DELETE /api/v1/documents/{id}` — каскад Postgres (документ + чанки) + MinIO; только manage KB
- [x] Upload и delete: `require_admin`
- [x] Rate limit upload (`RATE_LIMIT_UPLOAD_PER_MINUTE`); лимит размера (~50 MB), только PDF в v1

### Celery

- [x] Задача `ingestion.process_document(document_id: UUID-str)` вместо stub
- [x] Redis lock `indexing_lock:{document_id}`; повтор задачи идемпотентен
- [x] Статусы `pending → processing → ready | failed`; на ошибке `last_error`, индекс полный или удалён (нет «полуготового» `ready`)
- [x] Скачать объект из MinIO по `file_path`

### Парсер и чанкинг

- [x] `pdf_parser`: PyMuPDF по физическим страницам (1-based в API)
- [x] Таблицы через pdfplumber → GitHub-flavored Markdown, `is_table`
- [x] Координаты блоков в payload, если доступны (подсветка в M3)
- [x] Чанк не пересекает границу страницы; резать по секциям внутри страницы
- [x] 400–600 токенов, overlap 50 только внутри той же страницы/секции
- [x] Мета-заголовок перед эмбеддингом: `[Document: … | Section: … | Page: N]`
- [x] `embed_text` vs `content` для UI — одно правило, сниппет в цитатах без служебной строки
- [x] Не портировать `semantic_splitter.py`

### Эмбеддинги

- [x] FastEmbed `BAAI/bge-small-en-v1.5`, `vector(384)` cosine
- [x] Перед insert удалять строки `document_chunks` по `document_id`
- [x] Скопировать `access_roles` документа на каждый чанк
- [x] Смена ACL файла обновляет документ **и** все его чанки (или полный re-upsert)

### Тесты M1

- [x] Фикстурный PDF с таблицей и заголовками
- [x] Один `page_number` на чанк; таблица в Markdown; `access_roles` совпадают с документом
- [x] Re-ingest того же `document_id` / `file_hash` не плодит дубли чанков
- [x] `/raw` и list не отдают чужой файл (404, не 403 с title)

**Критерий вехи:** [x] upload → `ready`, точки с `page_number` и `access_roles`

---

## Milestone 2 — Corpus retrieval + RBAC + SSE

Спеки: [retrieval.md](retrieval.md), [auth.md](auth.md), [api.md](api.md). Запрещено `SELECT` всего корпуса в RAM (путь ChainWise `scroll_contract_chunks`).

**Критерий:** вопрос находит страницу; пользователь без роли не видит чанк в inspect; чужой ACL не протекает через LLM cache.

### Retrieval

- [x] Вырезать Solidity-эвристики, overview-аудит, interface stubs, findings-in-context
- [x] Dense Top-25: `embedding <=> query`, SQL `access_roles && allowed_roles`
- [x] Sparse/FTS Top-25 с тем же ACL (или BM25 только по dense-кандидатам, пока нет отдельного sparse-индекса — [ADR-005](decisions.md))
- [x] Порт `bm25_scores` + `reciprocal_rank_fusion` (`k=60`) → Top-15
- [x] Cross-encoder `BAAI/bge-reranker-base`: порог 0.25 → Top-4
- [x] Пустой список после порога → отказ, без вызова «творчества» LLM
- [x] `allowed_roles` = `{role} ∪ departments ∪ {all}`; роли не из тела запроса

### Чат и SSE

- [x] `POST /api/v1/chat/stream` — cookie session, rate limit chat
- [x] SSE JSON-конверты ChainWise: `citations` → `token` → `meta` → `[DONE]`; ошибки `type: error`
- [x] Цитаты `{doc_id: UUID, doc_title, page, snippet}` до первого токена
- [x] Каждый факт в ответе цитируем; иначе отказ фиксированной фразой
- [x] `session_id` пустой → создать `chat_sessions`; история не обходит ACL
- [x] `GET /api/v1/chat/sessions` (+ детали сессии)
- [x] `POST /api/v1/chat/feedback` — `+1/-1` только на свои сообщения
- [x] LLM cache key включает канонический набор `allowed_roles` (или кэш не шарить)

### Inspect и аудит

- [x] `POST /api/v1/search/inspect` — списки dense / sparse / rrf / reranked; тот же SQL ACL
- [x] Флаг `ENABLE_SEARCH_INSPECT`; в production по умолчанию выкл
- [x] Таблица `rag_audit_logs`: query, user, chunk ids, latency_ms, tokens_used, feedback
- [x] В аудит не писать полный текст restricted-чанков, если лог доступен тому же пользователю через API

### Тесты M2

- [x] Порт `test_rag_engine.py`: BM25 и RRF `k=60` без GPU / без живого LLM
- [x] Пользователь, чей `allowed_roles` не пересекается с чанком, отсутствует в fused / reranked / промпте
- [x] Inspect и chat не подтверждают существование чужого файла
- [x] Кэш, прогретый под admin, не отдаёт HR-чанки employee

**Критерий вехи:** [x] страница находится; ACL держит inspect и cache

---

## Milestone 3 — Split-screen UI

Спека: [frontend.md](frontend.md). База — ChainWise chat + auth; code-viewer не тащить.

**Критерий:** end-to-end клик по цитате открывает нужную страницу.

### Чат

- [x] Маршруты `/` или `/chat`, `/chat/[sessionId]`, `/documents`, `/login`
- [x] Split-pane ~45% чат / ~55% PDF (разделитель желателен)
- [x] SSE-ридер: `citations | token | meta | error | done`
- [x] Сноски-теги `Doc.pdf (стр. N)`, не `file.sol:L10-20` и не сырой `[^n]`
- [x] Стрим токенов без ожидания полного ответа; ошибка чата — тост, не развал страницы
- [x] Список сессий; пустое правое состояние — плейсхолдер «выберите цитату»

### PDF viewer

- [x] Встроенный viewer (`pdfjs-dist` / `@react-pdf-viewer/core`)
- [x] Файл с `GET /api/v1/documents/{id}/raw` (cookies)
- [x] Клик по сноске: нужный файл → страница → подсветка bbox/текста, скролл в вид
- [x] Пока PDF грузится, ответ в чате читать можно

### Админка KB

- [ ] Таблица: название, размер, страницы, теги доступа, статус; `last_error` при failed
- [ ] Drag-and-drop upload + чекбоксы ролей (`HR`, `Finance`, `General`/`all`, …)
- [ ] Поллинг `GET .../status` со шагами parse → chunk → embed
- [ ] Удаление с подтверждением; только manage KB
- [ ] Не показывать документы вне ACL

### Тесты / проверка M3

- [ ] Ручной проход: вопрос → сноска → верная страница (браузер)
- [ ] Employee не видит HR-файл в списке и не открывает `/raw`

**Критерий вехи:** [ ] клик по цитате открывает нужную страницу

---

## Milestone 4 — Eval, CI, портфолио

Спеки: [evaluation.md](evaluation.md), [nfr.md](nfr.md). Unit CI без GPU и без живого LLM.

**Критерий:** зелёный CI; нулевые утечки ACL на негативных кейсах eval.

### Eval

- [ ] `eval/golden_dataset.json` ≥ 30 вопросов: `question`, `ground_truth_answer`, `target_doc_id`, желательно `target_page`, `must_not_doc_ids`
- [ ] `eval/run_eval.py` гоняет **реальный** retrieval+generation под роль eval-пользователя
- [ ] `reports/rag_benchmark.md`: Faithfulness, Context Precision, Answer Relevance
- [ ] ACL-негативы: ноль утечек `must_not_doc_ids`
- [ ] Eval не в default CI (нужен ключ LLM и проиндексированные фикстуры)

### CI и качество репо

- [ ] GitHub Actions: ruff или flake8 + pytest (парсер, RRF, ACL)
- [ ] Frontend `tsc --noEmit` в CI
- [ ] Нет coverage-хуков на `pragma_parser` / `risk_scorer`
- [ ] CI зелёный на `main` / PR

### Портфолио

- [ ] Английский README: схема, why not naive RAG, стек, как поднять demo
- [ ] В README — ссылка на метрики eval и коротко про SQL-RBAC
- [ ] Demo-скрипт или раздел: тестовые пользователи employee vs hr, два PDF с разным ACL

**Критерий вехи:** [ ] зелёный CI; нулевые ACL-утечки в eval

---

## Приёмка продукта v1

Канонический список — [srs.md](srs.md) §6. Закрывать вместе с этим файлом.

- [ ] Upload сложного PDF с таблицей → `ready`, чанки с одной `page_number`, таблица в Markdown
- [ ] Вопрос находит верную страницу; клик в UI открывает её
- [ ] Пользователь без роли не видит чанк в inspect, chat и `/raw`
- [ ] Нехватка контекста → отказ «в документах нет информации», без выдуманных фактов
- [ ] Повторный ingest того же `document_id` не плодит дубли в `document_chunks`
- [ ] Ragas-прогон пишет `reports/rag_benchmark.md`; ACL-негативы — ноль утечек
- [ ] CI: lint + pytest (парсер, RRF) без GPU и без живого LLM в unit-тестах

---

## Вне скоупа v1

Не открывать отдельные вехи, пока не закрыта приёмка:

- мультитеннант, SSO/SAML
- онлайн-редактирование файлов
- агенты с tool-calling за пределы корпуса
- обучение своих эмбеддингов
- DOCX как обязательный формат (желателен, не блокер)
- из ChainWise: Slither, solc, Etherscan, XGBoost risk, PDF-отчёт аудита, Qdrant
