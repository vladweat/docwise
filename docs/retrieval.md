# Поиск и генерация (Retrieval)

Порядок шагов фиксирован. Пропускать реранкер или RBAC-фильтр на «счастливой» ветке нельзя.

## Шаг 1. RBAC в SQL (до LLM)

Из JWT/сессии: текущая `organization_id`, роль и `departments` членства (сборка — [auth.md](auth.md), изоляция — [tenancy.md](tenancy.md)).

Сборка `allowed_roles`:

- всегда включать глобальную роль (`employee` / `manager` / `admin`);
- включить каждый элемент `departments`;
- включить литерал `all` для общедоступных документов.

Фильтр на **каждый** dense и FTS/BM25 запрос:

```sql
WHERE organization_id = :current_org
  AND access_roles && ARRAY['employee', 'hr', 'all']::text[]
ORDER BY embedding <=> :query_vec
LIMIT 25
```

До M5 в коде есть только `access_roles && …` (один неявный тенант). Чанки вне org или ACL не участвуют в RRF, реранке и промпте. Не фильтровать «потом в промпте». Не подменять `org_id` тегом в `access_roles`.

Скачивание оригинала (`GET .../raw`) использует ту же семантику по строке `documents`, не по «раз пользователь нашёл цитату».

## Шаг 2. Hybrid search

Не копировать ChainWise-путь `scroll_contract_chunks` + BM25 по всем чанкам сущности. Там поиск ограничен одним контрактом; здесь — весь корпус.

1. **Dense:** эмбеддинг вопроса, Top-25, cosine (`embedding <=> query`), фильтр ACL.
2. **Sparse / BM25:** Top-25 с тем же ACL (Postgres FTS или BM25 **только** по объединению dense-кандидатов).
   Пока нет колонки `tsvector`, код берёт dense Top-50 с ACL и считает `bm25_scores` только по этим строкам ([ADR-005](decisions.md)).
3. **RRF** (`k = 60`) — функция из ChainWise `reciprocal_rank_fusion` без изменений:

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
> Каждый факт сопровожди сноской на документ и страницу.

В контекст передавать только Top-4 чанка: текст, title, page, chunk_id.

## Шаг 5. SSE

Эндпоинт: `POST /api/v1/chat/stream`. Протокол как в ChainWise (клиент `streamContractChat` почти 1:1): строки `data: <json>\n\n`, финал `data: [DONE]`.

| Порядок | `type` | Данные |
| --- | --- | --- |
| 1 | `citations` | `{citations: [{doc_id, doc_title, page, snippet}, ...]}` |
| 2 | `token` | `{content}` — дельты текста |
| 3 | `meta` | `{tokens_used, cached, session_id, message_id, ...}` затем `[DONE]` |
| ошибка | `error` | `{content}` без стека и без названий чужих файлов |

Цитаты уходят **до** токенов, чтобы UI сразу открыл PDF. Кеш LLM (`llm_cache:{version}:{org_id}:{roles_hash}:{question_hash}`) обязан включать `org_id` текущей организации и канонический набор `allowed_roles`; кэш, прогретый под admin или под другую org, не отдаётся. До M5 в ключе нет `org_id` — деплоить два клиента на этот кэш нельзя.

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
| `tokens_used` | из LLM / кэша | null |
| `session_id` / `message_id` | ход чата | null |
| `feedback` | `POST /chat/feedback` `+1`/`-1` | null |

В `retrieved_chunk_ids` только канонические UUID-строки. Текст чанка, `snippet`, `embed_text` в таблицу не пишутся (лог может позже отдаваться тому же пользователю). Не-UUID значения отбрасываются, не сохраняются.

## Инспекция

`POST /api/v1/search/inspect` — те же четыре стадии, что у чата, со скорами. Контракт: [api.md](api.md).

- Только org-admin + флаг `ENABLE_SEARCH_INSPECT` (в production по умолчанию выкл → `404`).
- Тот же SQL `organization_id = :current_org AND access_roles && allowed_roles`. Admin без `hr` в `allowed_roles` не видит `access_roles = ['hr']`. Чужая org не подтверждается.
- `limit` режет **ответ** (до 15 по умолчанию на список), не пересобирает Top-K пайплайна.
- `snippet` в JSON — превью **видимых** чанков. Скрытый документ: пустой список, без id/title.
