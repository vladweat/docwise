# Документация Docwise

Предварительная спецификация. Источник истины по продукту — [srs.md](srs.md); по отклонениям от черновика ТЗ — [decisions.md](decisions.md). Пока нет OpenAPI из кода, контракты API живут в [api.md](api.md).

## С чего начать

1. [SRS](srs.md) — цели, FR, стек, критерии приёмки.
2. [Архитектура](architecture.md) — компоненты, чат и inspect.
3. [Модель данных](data-model.md), [Auth](auth.md), [Tenancy](tenancy.md) — Postgres, pgvector, роли, организации.
4. [Ingestion](ingestion.md) и [Retrieval](retrieval.md) — индекс, ответы, inspect, аудит.
5. [API](api.md) и [Frontend](frontend.md) — контракт и UX.
6. [NFR](nfr.md), [Оценка](evaluation.md), [Roadmap](milestones.md) (чекбоксы вех).
7. [Соглашения](conventions.md) и [переиспользование ChainWise](reuse-from-chainwise.md).

## Инварианты продукта

- Права доступа проверяются **до** передачи чанков в LLM: SQL `organization_id` (M5) **и** `access_roles && allowed_roles` (чат, inspect, list, `/raw`).
- `all` — все в **этой** организации, не все залогиненные в SaaS.
- Ответ без проверяемой цитаты `{документ, страница}` считается дефектом.
- Наивная нарезка текста по символам не используется.
- Корпусный поиск, не scroll всей коллекции в RAM.
- Inspect и аудит: стадии пайплайна только admin + флаг; в `rag_audit_logs` UUID чанков, не текст.

## Правила Cursor

Каталог `.cursor/rules/` — короткие инструкции для агента (стек, RBAC, auth, API, ingestion, retrieval, frontend, tests/eval, reuse). При противоречии сначала эти документы, затем править правила и код вместе.
