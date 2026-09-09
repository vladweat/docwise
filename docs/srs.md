# SRS: Docwise (Enterprise Doc AI)

**Репозиторий:** `docwise`  
**Название:** Docwise / Enterprise RAG Workspace  
**Тип:** B2B SaaS или внутренний корпоративный сервис умного поиска и Q&A по документам.

Это каноническое продуктовое ТЗ. Детали реализации, отличающиеся от черновика (asyncpg → sync Session, SSE-конверт ChainWise), зафиксированы в [decisions.md](decisions.md). PK — UUID, как в ТЗ. Карта кода: [reuse-from-chainwise.md](reuse-from-chainwise.md).

**Позиционирование:** *Production-grade Enterprise RAG system built with FastAPI, PostgreSQL/pgvector, Celery, and Next.js, featuring permission-aware retrieval, hybrid search with reranking, and exact PDF page citations.*

---

## 1. Проблема

В компаниях копятся тысячи PDF/DOCX (регламенты, политики, NDA, отчёты, договоры).

| Боль | Почему наивный подход ломается |
| --- | --- |
| Семантика | Keyword-поиск не понимает формулировку вопроса |
| Структура PDF | Нарезка по N символам рвёт таблицы и теряет заголовки |
| Утечка ACL | Общий чат без фильтра векторов отдаёт стажёру финансы C-level |
| Доверие | Без точной страницы в оригинале ответ модели нельзя проверить |

Docwise закрывает это связкой: **RBAC на retrieval**, **structure-aware chunking**, **hybrid search + rerank**, **цитаты в PDF-вьюере**.

---

## 2. Цели продукта (v1)

1. Загрузить PDF, проиндексировать структуру (страницы, секции, таблицы) и отвечать на вопросы только по этому корпусу.
2. Не отдать в LLM ни одного чанка, к которому у пользователя нет права.
3. Каждый факт в ответе цитируется как `{document, page}`; клик открывает оригинал на этой странице.
4. Если в разрешённом контексте ответа нет — явный отказ, без догадок.
5. Качество retrieval измеримо (Ragas + ACL-негативы), а не «кажется, отвечает».

Вне скоупа v1: мультитеннант, SSO/SAML, онлайн-редактирование файлов, агенты с tool-calling за пределы корпуса, обучение своих эмбеддингов, DOCX как обязательный формат (желателен, не блокер).

---

## 3. Стек (целевой)

| Слой | Технологии |
| --- | --- |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2 **sync Session** |
| Очереди | Redis 7, Celery 5 |
| Данные | PostgreSQL 15 + pgvector (`pgvector/pgvector:pg15`), dense 384d cosine + FTS/BM25 на кандидатах |
| Парсинг | PyMuPDF (`fitz`), pdfplumber (таблицы → Markdown) |
| ML | fastembed `BAAI/bge-small-en-v1.5`, `BAAI/bge-reranker-base`; LLM `gpt-4o-mini` / Anthropic через `httpx` |
| Frontend | Next.js 15 App Router, React 19, TypeScript 5, Tailwind 4, shadcn/ui, pdf.js |
| Инфра | Docker Compose, MinIO, GitHub Actions (ruff + pytest) |

Происхождение каркаса: соседний [ChainWise](../../chainwise/README.md). Не подменять стек (LangChain как ядро, другой векторный движок) без явной просьбы.

---

## 4. Функциональные требования

### FR-1. Knowledge base

- Авторизованный пользователь с правом manage KB загружает PDF и назначает `access_roles[]`.
- Система считает SHA-256, кладёт байты в MinIO, строку в `documents` (`pending`) и ставит Celery-задачу.
- Статусы: `pending → processing → ready | failed`. Failed сохраняет `last_error`.
- Список документов с пагинацией и статусами; удаление каскадно (Postgres + MinIO).
- Отдача оригинала только при том же ACL, что и у строки документа. Публичный URL ведра запрещён.

### FR-2. Ingestion

- Парсинг по физическим страницам; таблицы — GitHub-flavored Markdown; координаты блоков сохранять, если доступны.
- Чанк не пересекает границу страницы; 400–600 токенов, overlap 50 только внутри страницы/секции.
- Перед эмбеддингом — мета-заголовок `[Document: … | Section: … | Page: N]`.
- Payload чанка содержит `access_roles` документа. Re-ingest идемпотентен (delete by `document_id`).

### FR-3. Retrieval + chat

- Фильтр SQL `access_roles && allowed_roles` на **каждый** dense и sparse/FTS запрос.
- Hybrid: dense Top-25 + sparse/BM25 Top-25 → RRF `k=60` → Top-15 → cross-encoder → порог 0.25 → Top-4.
- Генерация строго по Top-4. Пустой список после порога → фиксированный отказ без вызова «творчества».
- SSE: сначала цитаты, затем токены, затем метрики. Протокол — JSON-конверты ChainWise (см. [api.md](api.md)).

### FR-4. UI

- Split-pane: чат ~45% / PDF ~55%. Сноска — интерактивный тег `Doc.pdf (стр. N)`.
- Клик: открыть файл, перейти на страницу, подсветить фрагмент.
- Админка KB: таблица + drag-and-drop + теги доступа + поллинг статуса.

### FR-5. Оценка и аудит

- Каждый retrieval (чат и inspect) пишется в `rag_audit_logs`: query, user, UUID чанков после реранкера, latency_ms, tokens_used, feedback.
- В аудит не писать полный текст чанков (в т.ч. restricted).
- Feedback `+1 / -1` на своё assistant-сообщение (`POST /api/v1/chat/feedback`).
- `eval/` с golden set ≥ 30 вопросов и отчётом Ragas.

### FR-6. Инспекция (admin)

- `POST /api/v1/search/inspect` — списки `dense` / `sparse` / `rrf` / `reranked` со скорами. Тот же SQL ACL, что у чата; роли не из тела запроса.
- Только `admin`. `ENABLE_SEARCH_INSPECT`: в production по умолчанию выкл (`404`), иначе вкл. Явное `true`/`false` перекрывает дефолт.
- Нет admin-override: HR-only чанк не виден admin без `hr` в `allowed_roles`. Пользователь без роли не видит чанк и не узнаёт, что файл есть.

---

## 5. Нефункциональные требования

См. [nfr.md](nfr.md). Кратко: нулевые утечки ACL; отказ без галлюцинаций; парсинг не в HTTP-запросе; секреты только в env.

---

## 6. Критерии приёмки v1

- [ ] Upload сложного PDF с таблицей → `ready`, чанки с одной `page_number`, таблица в Markdown.
- [ ] Вопрос находит верную страницу; клик в UI открывает её.
- [ ] Пользователь без роли не видит чанк в inspect, chat и `/raw`.
- [ ] Нехватка контекста → отказ «в документах нет информации», без выдуманных фактов.
- [ ] Повторный ingest того же `document_id` не плодит дубли в `document_chunks`.
- [ ] Ragas-прогон пишет `reports/rag_benchmark.md`; ACL-негативы — ноль утечек.
- [ ] CI: ruff + pytest (парсер, RRF) без GPU и без живого LLM в unit-тестах.
