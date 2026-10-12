# Аудит документации

Дата: 2026-10-12. Метод: статическая сверка tracked Markdown с исходным кодом,
конфигурацией, миграциями, тестами и CI. Runtime services в рамках аудита не запускались.

## Реестр

| Документ | Назначение | Результат | Действие |
| --- | --- | --- | --- |
| `README.md` | Вход, demo, stack | Полезен, но завышал LLM support и смешивал liveness/readiness | Обновить ключевые оговорки и навигацию |
| `docs/README.md` | Индекс | Не охватывал development/operations/security/maintenance | Обновить |
| `docs/product/srs.md` | Product requirements | В основном соответствует коду; содержит целевую спецификацию | Сохранить, отличать requirements от runtime |
| `docs/product/architecture.md` | Компоненты и потоки | Архитектура верна; Anthropic отсутствует в коде | Обновить |
| `docs/product/nfr.md` | NFR и capacity | Baseline соответствует report; часть требований — policy | Сохранить |
| `docs/product/frontend.md` | UX/frontend | Путь App Router должен быть `frontend/src/app/` | Исправить |
| `docs/product/evaluation.md` | Eval и gates | Есть битая ссылка на отсутствующий report anchor | Исправить |
| `docs/platform/tenancy.md` | Multi-tenancy/RLS | Application filters точны; production RLS prerequisite был недостаточно явен | Дополнить |
| `docs/platform/auth.md` | Auth/ACL/SSO | Auth/ACL точны; SSO runtime фактически dev fixture | Дополнить |
| `docs/platform/billing.md` | Quotas/billing | Соответствует `Settings` и adapters | Сохранить |
| `docs/platform/data-model.md` | Модели и связи | Подробно соответствует ORM/migrations | Сохранить |
| `docs/platform/data-retention.md` | Retention policy | Верно отмечает отсутствие purge job | Сохранить |
| `docs/pipeline/ingestion.md` | Worker pipeline | Имя задачи устарело; строгая idempotency заявлена сильнее реализации | Исправить |
| `docs/pipeline/retrieval.md` | Hybrid retrieval | Соответствует константам и SQL flow | Сохранить |
| `docs/engineering/api.md` | Ручной HTTP contract | Почти полон; не описывал `GET /`, `preview_snippet`; feedback comment не сохраняется | Дополнить |
| `docs/engineering/decisions.md` | ADR history | ADR-007 содержал устаревший registration statement | Исправить без переписывания истории |
| `docs/engineering/python-style.md` | Python conventions | Нормативный документ, конфликтов не найдено | Сохранить |
| `docs/portfolio/screenshots/README.md` | Screenshot workflow | Предлагал повторный `npm init`, хотя package files уже есть | Исправить |
| `ops/README.md` | Pilot commands | Команды верны; не раскрывал отсутствие Redis backup | Дополнить, оставить кратким |
| `reports/*.md` | Результаты прогонов | Исторические артефакты; не считать текущей runtime гарантией | Сохранить |
| `samples/documents/README.md` | Sample corpus | Содержал абсолютный путь чужой машины | Исправить |
| `.github/pull_request_template.md` | PR checklist | Неверный anchor evaluation | Исправить |
| `docs/PRIVATE.md` | Указатель private docs | Объясняет намеренно отсутствующие runbooks | Сохранить |

## Созданные документы

- `AGENTS.md` — короткие repository-specific ограничения и проверки.
- `docs/development/getting-started.md` — проверяемый local workflow.
- `docs/development/configuration.md` — inventory environment variables.
- `docs/operations/operations.md` — Compose, health, migration, backup/restore и rollback gaps.
- `docs/security/overview.md` — trust boundaries и подтверждённые ограничения.
- `docs/maintenance/technical-debt.md` — приоритизированный risk register.
- Этот реестр — точка следующего документационного аудита.

## Канонические источники

| Тема | Источник |
| --- | --- |
| Runtime config | `backend/app/core/config.py`, затем `.env.example`/Compose overrides |
| HTTP routes | `backend/app/api/`, OpenAPI только в non-production |
| Схема БД | Alembic migrations и ORM models |
| Retrieval constants | `backend/app/services/retrieval/types.py` |
| Worker semantics | `backend/worker/celery_app.py`, `app.services.ingestion` |
| Локальные команды | `Makefile`, затем CI workflows |
| Frontend versions | `frontend/package-lock.json` |
| Исторические решения | `docs/engineering/decisions.md` |

## Известное дублирование

README, SRS и architecture повторяют stack и RAG flow. Канон деталей retrieval —
`docs/pipeline/retrieval.md`; README должен оставаться кратким. Полный API вручную описан в
`docs/engineering/api.md`, а OpenAPI генерируется из кода только вне production. При
изменении route/schema сначала обновляется код и тест, затем ручной contract.

## Проверка при следующих изменениях

- route/schema: OpenAPI diff + `docs/engineering/api.md`;
- `Settings`: `.env.example` + `docs/development/configuration.md`;
- Compose/Makefile/CI: getting-started и operations;
- models/migrations: data-model и backup/rollback impact;
- auth/tenancy/retrieval: auth, tenancy, security и threat-oriented tests;
- worker retry/queue: ingestion и operations;
- новый report: дата, commit/revision и условия запуска.

## Ограничения аудита

Не проверены внешние URL, private gitignored runbooks, production infrastructure, secret
manager, firewall, backup schedule, реальные IdP/Stripe credentials и provider policies.
Отсутствие evidence в репозитории отмечено как пробел, а не заменено предположением.
