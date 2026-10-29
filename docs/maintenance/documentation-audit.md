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
| `docs/engineering/api.md` | Ручной HTTP contract | Описывает HTTP error envelope, runtime delete outbox и routes | Сверять при изменении API |
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

## Добавление от 2026-10-29

- `docs/operations/public-demo.md` и `docker-compose.public-demo.yml` описывают отдельный
  публичный demo-профиль с Caddy/TLS, внутренними backend-портами и одноразовым созданием
  RLS session role. Из-за недоступности публичного образа MinIO профиль использует Garage;
  S3 bucket policy API в Garage не поддержан, поэтому demo-профиль отключает эту проверку.
  S3 readiness проверяется через authenticated bucket access. Демо рассчитано на synthetic
  data и не является отказоустойчивым storage deployment. На VM запущены backend, worker,
  frontend, PostgreSQL, Redis, Garage и Caddy; API readiness прошла, создана роль RLS с
  `NOSUPERUSER`/`NOBYPASSRLS`, засеяно 12 synthetic documents. DNS разрешается на адрес VM,
  Let's Encrypt certificate получен; публичные `/`, `/ready` и demo login отвечают `200`,
  registration закрыта `404`. После ручной смены модели backend/worker пересозданы; внешний
  `/ready`, demo login и короткий chat stream ответили `200`, stream завершился без error и
  включал токены с citations. Значения `.env` и текст ответа не выводились.
- `docs/maintenance/repository-review-2026-10-29.md` фиксирует статический обзор кода и
  рисков перед подготовкой публичного интервью-демо.
- Hardening changes from 2026-10-29: rate limit ignores XFF by default and fails closed on
  Redis errors; ingestion locks compare owner tokens, retry cleanup after transient Redis
  errors, and a dry-run-first recovery CLI handles lost Redis queue work (failed rows require
  explicit IDs); backup manifests include Alembic revision and restore checks it before
  destructive steps; Celery Beat purges audit rows daily; feedback comments persist; public
  profile disables dev SSO fixture; backend installs pinned `backend/requirements.lock`.
- Additional reliability changes from 2026-10-29: Compose binds host ports to loopback and
  configures runtime RLS; one `db-migrate` job precedes API/worker; backup checksums and exact
  MinIO restore mirroring; worker health and operational queue/outbox checks; transient-only
  ingestion retries; runtime frontend `API_BASE_URL`; one sanitized API error envelope; a
  transactional `storage_deletions` outbox. These source changes have not been deployed or
  runtime-tested. No tests or destructive restore drill were run.
- Chat-session concurrency change from 2026-10-29: PostgreSQL advisory locks reject a second
  active stream for the same existing session with the standard HTTP 409 envelope before SSE;
  different sessions proceed independently. Backend lock/chat tests and frontend localization
  tests passed in this workspace. The public VM was not updated; ACL/corpus snapshot consistency
  remains separate technical debt.

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
| Backend packages | `backend/requirements.lock`, with human-edited ranges in `backend/requirements.txt` |
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

## Результаты валидации

| Проверка | Результат |
| --- | --- |
| `git diff --check` | Пройдена |
| Локальные relative links и наличие linked files | Пройдена для 32 tracked Markdown-файлов |
| Баланс fenced code blocks | Пройден |
| Все aliases из `Settings` названы в configuration | Пройден после исправления grouped keys |
| Наличие документированных `GET /`, `/health`, `/ready` | Пройдено |
| `make -n` для документированных dev/ops targets | Пройдено; команды не выполнялись |
| Markdownlint | Пропущен: CLI отсутствует, новые зависимости не устанавливались |
| Базовая структура Mermaid blocks | Пройдена для трёх диаграмм |
| Полный Mermaid CLI parse | Пропущен: CLI отсутствует, новые зависимости не устанавливались |
| Runtime, pytest, Docker Compose, backup/restore | Пропущены как непропорциональные документационному изменению |

## Проверки hardening от 2026-10-29

| Проверка | Результат |
| --- | --- |
| Ruff (`app tests scripts worker`) | Пройдена |
| Mypy (`app worker scripts/requeue_stale_ingestion.py`) | Пройдена, 102 source files |
| Python compile (`app`, `worker`, `scripts`, `alembic`) | Пройдена |
| `bash -n` для backup/restore/setup scripts | Пройдена |
| `docker compose config --quiet` для base и public-demo | Пройдена; Compose runtime не запускался |
| `git diff --check` | Пройдена |
| Pytest / smoke / frontend tests | Не запускались по ограничению сессии |
| Публичный VM deploy, restore drill, purge task runtime | Не выполнялись |
