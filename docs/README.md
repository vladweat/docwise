# Документация Docwise

Предварительная спецификация. Источник истины по продукту — [srs.md](srs.md); по отклонениям от черновика ТЗ — [decisions.md](decisions.md). Пока нет OpenAPI из кода, контракты API живут в [api.md](api.md).

## С чего начать

1. [SRS](srs.md) — цели, FR, стек, критерии приёмки.
2. [Архитектура](architecture.md) — компоненты и два основных потока.
3. [Модель данных](data-model.md), [Auth](auth.md) — Postgres, pgvector, роли.
4. [Ingestion](ingestion.md) и [Retrieval](retrieval.md) — индекс и ответы.
5. [API](api.md) и [Frontend](frontend.md) — контракт и UX.
6. [NFR](nfr.md), [Оценка](evaluation.md), [Вехи](milestones.md).
7. [Соглашения](conventions.md) и [переиспользование ChainWise](reuse-from-chainwise.md).

## Инварианты продукта

- Права доступа проверяются **до** передачи чанков в LLM, SQL-фильтром `access_roles && allowed_roles`.
- Ответ без проверяемой цитаты `{документ, страница}` считается дефектом.
- Наивная нарезка текста по символам не используется.
- Корпусный поиск, не scroll всей коллекции в RAM.

## Правила Cursor

Каталог `.cursor/rules/` — короткие инструкции для агента (стек, RBAC, auth, API, ingestion, retrieval, frontend, tests/eval, reuse). При противоречии сначала эти документы, затем править правила и код вместе.
