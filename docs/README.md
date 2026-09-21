# Документация Docwise

Источник истины по продукту — [srs.md](product/srs.md); по отклонениям от черновика ТЗ — [decisions.md](engineering/decisions.md). Канон HTTP — [api.md](engineering/api.md). FastAPI отдаёт `/docs` и `/openapi.json` вне `production` (в production выключены); OpenAPI не заменяет `api.md`.

## Раскладка каталога

| Каталог | Содержимое |
| --- | --- |
| `product/` | SRS, архитектура, roadmap, NFR, frontend, evaluation |
| `platform/` | tenancy, auth, billing, data-model |
| `pipeline/` | ingestion, retrieval |
| `engineering/` | api, ADR/decisions, tech-debt, reuse-from-chainwise |
| `portfolio/` | витрина, уровни A/B/C, owner tasks, deploy demo, career-kb, screenshots |
| `meta/` | соглашения репозитория (`conventions.md`) |

## С чего начать

1. [SRS](product/srs.md) — цели, FR, стек, критерии приёмки.
2. [Архитектура](product/architecture.md) — компоненты, чат и inspect.
3. [Модель данных](platform/data-model.md), [Auth](platform/auth.md), [Tenancy](platform/tenancy.md), [Billing](platform/billing.md) — Postgres, pgvector, роли, организации, планы/квоты.
4. [Ingestion](pipeline/ingestion.md) и [Retrieval](pipeline/retrieval.md) — индекс, ответы, inspect, аудит.
5. [API](engineering/api.md) и [Frontend](product/frontend.md) — контракт и UX.
6. [NFR](product/nfr.md), [Оценка](product/evaluation.md), [Roadmap](product/milestones.md) (чекбоксы вех).
7. [Техдолг](engineering/tech-debt.md) — structural backlog после M0–M6 (не инварианты продукта).
8. [Портфолио](portfolio/portfolio.md) — закрытие витрины (не вехи продукта).
9. [Уровни портфолио A/B/C](portfolio/portfolio-levels.md) — interview-ready и abroad (не product roadmap).
10. [Задачи владельца (видео, demo, GitHub)](portfolio/portfolio-owner-tasks.md) — уровень C, вне кода.
11. [Публичный demo VPS](portfolio/deploy-public-demo.md) — C1 deploy checklist.
12. [Карьерная KB](portfolio/career-kb.md) — факты для резюме/интервью (не продуктовая спека).
13. [Соглашения](meta/conventions.md) и [переиспользование ChainWise](engineering/reuse-from-chainwise.md).

## Инварианты продукта

- Права доступа проверяются **до** передачи чанков в LLM: SQL `organization_id` (M5) **и** `access_roles && allowed_roles` (чат, inspect, list, `/raw`).
- План, SSO и hostname не заменяют `org_id`. Квота своей org → `402`; фича не в плане → `403`.
- `all` — все в **этой** организации, не все залогиненные в SaaS.
- Ответ без проверяемой цитаты `{документ, страница}` считается дефектом.
- Наивная нарезка текста по символам не используется.
- Корпусный поиск, не scroll всей коллекции в RAM.
- Inspect и аудит: стадии пайплайна только admin + флаг; в `rag_audit_logs` UUID чанков, не текст.

## Правила Cursor

Каталог `.cursor/rules/` — короткие инструкции для агента (стек, RBAC, auth, API, ingestion, retrieval, frontend, tests/eval, reuse, billing). При противоречии сначала эти документы, затем править правила и код вместе.
