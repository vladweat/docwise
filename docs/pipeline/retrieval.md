# Поиск и генерация (Retrieval)

Порядок шагов фиксирован. Пропускать реранкер или RBAC-фильтр на «счастливой» ветке нельзя.

## Шаг 1. RBAC в SQL (до LLM)

Из JWT/сессии: текущая `organization_id`, роль и `departments` членства (сборка — [auth.md](../platform/auth.md), изоляция — [tenancy.md](../platform/tenancy.md)).

Сборка `allowed_roles`:

- всегда включать глобальную роль (`employee` / `manager` / `admin`);
- включить каждый элемент `departments`;
- включить литерал `all` для общедоступных документов.

Фильтр на **каждый** dense и FTS запрос:

```sql
WHERE organization_id = :current_org
  AND access_roles && ARRAY['employee', 'hr', 'all']::text[]
ORDER BY embedding <=> :query_vec
LIMIT 25
```

Чанки вне org или ACL не участвуют в RRF, реранке и промпте. Не фильтровать «потом в промпте». Не подменять `org_id` тегом в `access_roles`.

Скачивание оригинала (`GET .../raw`) использует ту же семантику по строке `documents`, не по «раз пользователь нашёл цитату».

## Шаг 2. Hybrid search

Не загружать весь корпус в RAM для BM25. Поиск — SQL Top-K с ACL на каждом запросе.

Dense: эмбеддинг вопроса, Top-25, cosine (`embedding <=> query`), фильтр ACL. Индекс HNSW глобальный; перед запросом `SET LOCAL hnsw.iterative_scan` (`relaxed_order`) и `hnsw.max_scan_tuples` (`HNSW_MAX_SCAN_TUPLES`, дефолт 20000), чтобы org/ACL-фильтр не обрезал соседей.
2. **Sparse / FTS:** Top-25 независимо от dense, Postgres `tsvector` (`simple`) + GIN, тот же `organization_id` и `access_roles && allowed_roles`.
3. **RRF** (`k = 60`) — `reciprocal_rank_fusion` без изменений формулы:

\[
RRF(d) = \sum_{m \in \{\text{dense},\ \text{sparse}\}} \frac{1}{60 + \mathrm{rank}_m(d)}
\]

Документ, отсутствующий в одном из списков, даёт вклад только от методов, где он есть. Итог: **Top-15**.

## Шаг 3. Cross-encoder rerank

Модель: `BAAI/bge-reranker-base` (fastembed). Пары `(query, chunk_text)`.

- Отбросить score **< 0.25** (порог конфигурируемый, `RERANK_THRESHOLD`, дефолт 0.25). Сырой логит bge-reranker пропускается через sigmoid в `(0, 1)`.
- В контекст LLM: **Top-4**.

Пустой список после порога → отказ по правилам шага 4, без «творчества» модели.

## Шаг 4. Генерация без галлюцинаций

Системный промпт (смысл обязателен, формулировка может быть двуязычной):

> Ты — корпоративный AI-ассистент. Отвечай строго на основе переданного контекста.
> Если ответа в контексте нет, скажи: «В предоставленных документах нет информации по данному вопросу.» Не выдумывай.
> Каждый факт сопровожди сноской на документ и страницу в виде `[Title.pdf, стр. N]`. Списки и таблицы — Markdown.

В контекст передавать только Top-4 чанка: текст, title, page, chunk_id.

## Шаг 5. SSE

Эндпоинт: `POST /api/v1/chat/stream`. Протокол SSE: строки `data: <json>\n\n`, финал `data: [DONE]` (см. [api.md](../engineering/api.md)).

| Порядок | `type` | Данные |
| --- | --- | --- |
| 1 | `citations` | `{citations: [{doc_id, doc_title, page, snippet}, ...]}` |
| 2 | `token` | `{content}` — дельты текста |
| 3 | `meta` | `{tokens_used, cached, session_id, message_id, ...}` затем `[DONE]` |
| ошибка | `error` | `{content}` без стека и без названий чужих файлов |

Цитаты уходят **до** токенов, чтобы UI сразу открыл PDF. Кеш LLM (`llm_cache:{version}:{org_id}:{generation}:{roles_hash}:{question_hash}`) обязан включать `org_id` текущей организации, поколение индекса и канонический набор `allowed_roles`; кэш, прогретый под admin или под другую org, не отдаётся. Cache hit: `tokens_used` в аудите null. PATCH ACL / DELETE / ready ingest бампают `organizations.llm_index_generation` и сбрасывают ключи org.

После ответа: строка в `chat_messages` + `rag_audit_logs` (см. ниже).

## Аудит retrieval

Каждый успешный проход retrieval (чат и inspect) пишет `rag_audit_logs`:

| Поле | Чат | Inspect |
| --- | --- | --- |
| `query` | вопрос | вопрос |
| `user_id` | вызывающий | вызывающий |
| `organization_id` | текущая org (M5) | текущая org (M5) |
| `retrieved_chunk_ids` | UUID PK Top-4 после реранкера | то же |
| `latency_ms` | да | да |
| `tokens_used` | из LLM; на cache hit — null | null |
| `session_id` / `message_id` | ход чата | null |
| `feedback` | `POST /chat/feedback` `+1`/`-1` | null |

В `retrieved_chunk_ids` только канонические UUID-строки. Текст чанка, `snippet`, `embed_text` в таблицу не пишутся (лог может позже отдаваться тому же пользователю). Не-UUID значения отбрасываются, не сохраняются.

## Инспекция

`POST /api/v1/search/inspect` — те же четыре стадии, что у чата, со скорами. Контракт: [api.md](../engineering/api.md).

- Только org-admin + флаг `ENABLE_SEARCH_INSPECT` (в production по умолчанию выкл → `404`).
- Тот же SQL `organization_id = :current_org AND access_roles && allowed_roles`. Admin без `hr` в `allowed_roles` не видит `access_roles = ['hr']`. Чужая org не подтверждается.
- `limit` режет **ответ** (до 15 по умолчанию на список), не пересобирает Top-K пайплайна.
- `snippet` в JSON — превью **видимых** чанков. Скрытый документ: пустой список, без id/title.
