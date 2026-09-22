# Документация Docwise

Источник истины по продукту — [srs.md](product/srs.md); по архитектурным решениям — [decisions.md](engineering/decisions.md). Канон HTTP — [api.md](engineering/api.md). FastAPI отдаёт `/docs` и `/openapi.json` вне `production` (в production выключены); OpenAPI не заменяет `api.md`.

## Раскладка каталога

| Каталог | Содержимое |
| --- | --- |
| `product/` | SRS, архитектура, roadmap, NFR, frontend, evaluation |
| `platform/` | tenancy, auth, billing, data-model |
| `pipeline/` | ingestion, retrieval |
| `engineering/` | api, ADR/decisions, tech-debt |
| `portfolio/` | скриншоты для README, [гайд публичного demo](portfolio/deploy-public-demo.md) |
| `meta/` | соглашения репозитория (`conventions.md`) |

## С чего начать

1. [SRS](product/srs.md) — цели, FR, стек, критерии приёмки.
2. [Архитектура](product/architecture.md) — компоненты, чат и inspect.
3. [Модель данных](platform/data-model.md), [Auth](platform/auth.md), [Tenancy](platform/tenancy.md), [Billing](platform/billing.md) — Postgres, pgvector, роли, организации, планы/квоты.
4. [Ingestion](pipeline/ingestion.md) и [Retrieval](pipeline/retrieval.md) — индекс, ответы, inspect, аудит.
5. [API](engineering/api.md) и [Frontend](product/frontend.md) — контракт и UX.
6. [NFR](product/nfr.md), [Оценка](product/evaluation.md), [Roadmap](product/milestones.md) (чекбоксы вех).
7. [Техдолг](engineering/tech-debt.md) — структурные заметки после M0–M6 (не инварианты продукта).
8. [Публичный demo на VPS](portfolio/deploy-public-demo.md) — TLS, env, smoke (опционально).
9. [Соглашения](meta/conventions.md).

## Инварианты продукта

- Права доступа проверяются **до** передачи чанков в LLM: SQL `organization_id` (M5) **и** `access_roles && allowed_roles` (чат, inspect, list, `/raw`).
- План, SSO и hostname не заменяют `org_id`. Квота своей org → `402`; фича не в плане → `403`.
- `all` — все в **этой** организации, не все залогиненные в SaaS.
- Ответ без проверяемой цитаты `{документ, страница}` считается дефектом.
- Наивная нарезка текста по символам не используется.
- Корпусный поиск, не scroll всей коллекции в RAM.
- Inspect и аудит: стадии пайплайна только admin + флаг; в `rag_audit_logs` UUID чанков, не текст.

## Правила Cursor

Каталог `.cursor/rules/` — короткие инструкции для агента (стек, RBAC, auth, API, ingestion, retrieval, frontend, tests/eval, billing). При противоречии сначала эти документы, затем править правила и код вместе.
