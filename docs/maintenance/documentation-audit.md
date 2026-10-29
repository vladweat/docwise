# Аудит документации

**Дата сверки:** 2026-10-29 · **источник кода:** текущий `main` · **runtime:** публичное демо на VPS.

Документы объясняют продукт и эксплуатацию; они не заменяют source. При расхождении приоритет у кода,
миграций, тестов и Compose.

## Карта канонических страниц

| Тема | Основной документ | Дополняют |
| --- | --- | --- |
| Первое знакомство | [README](../../README.md) | [docs index](../README.md) |
| Архитектура и продукт | [product/architecture.md](../product/architecture.md) | SRS, frontend, NFR |
| Tenant/auth/ACL | [platform/tenancy.md](../platform/tenancy.md) | auth, security, data model |
| Ingestion и retrieval | [pipeline/ingestion.md](../pipeline/ingestion.md) | [pipeline/retrieval.md](../pipeline/retrieval.md) |
| HTTP contract | [engineering/api.md](../engineering/api.md) | `backend/app/api/` и schemas |
| Config/local setup | [development/configuration.md](../development/configuration.md) | `.env.example`, Compose, `Settings` |
| Операции | [operations/operations.md](../operations/operations.md) | [public demo](../operations/public-demo.md) |
| Риски | [technical-debt.md](technical-debt.md) | source, migration и runtime evidence |

## Сверено и актуализировано

- README и навигация организованы для demo/interview, разработчика и оператора.
- Архитектура, retrieval и ingestion имеют визуальные схемы и короткое описание потока.
- API-контракт разделён на общий формат, documents, chat, inspect и organizations.
- Новый uncached chat отправляет ранний `meta` с `session_id` до citation/token stream; SRS, API, ADR,
  frontend и NFR описывают этот порядок.
- Compose задаёт `docwise_rls` для API/worker/Beat; `db-migrate` создаёт роль/grants до старта.
- В публичном профиле SSO отключён, billing использует `dev`, Garage — single-node storage.
- Retention, transactional storage deletion outbox и queue recovery описаны как реализованные механизмы;
  конфигурация restore drill имеется, но факт успешного запуска и отказоустойчивость не заявляются.
- `make restore-drill` восстанавливает backup в отдельный Compose project и проверяет readiness и наличие
  готовых документов; запуск всё ещё требует maintenance window, а реальный drill и off-site backup не заявляются.
- CI запускает Playwright UI flows на отдельном frontend/API fixture; сценарии не заменяют проверку живого
  backend и ingestion worker.
- Логи и Sentry очищают текст исключений/traceback; тесты проверяют короткие значения, которые не покрывались
  прежним bulk-text порогом.
- Backend `/metrics` отдаёт request counters и latency histograms с ограниченными labels; public Caddy route
  и base Compose host binding не публикуют этот endpoint на внешний интерфейс.
- RAG snapshot от 2026-09-22 помечен как historical: golden set вырос с 35 до 41 кейса, но метрики
  не пересчитаны. Новые eval/load отчёты записывают revision и hash dataset.

## Не считается гарантией

`reports/rag_benchmark.md` — результат запуска от указанной в отчёте даты. Он не подтверждает качество
нового corpus или следующей версии модели. Публичное демо — single-VPS synthetic-data profile, не HA production.

Private runbooks из gitignored `docs/_private/` не включены в clone; см. [PRIVATE.md](../PRIVATE.md).

## Проверка утверждений

| Тип изменения | Проверить и обновить |
| --- | --- |
| Route/schema/error | `backend/app/api/`, schemas, тесты и соответствующий файл `engineering/api/` |
| Setting/env alias | `Settings`, `.env.example`, Compose и `development/configuration.md` |
| Model/migration | ORM, Alembic, data model, backup/rollback compatibility |
| Retrieval/prompt/ACL/chunking | tests/eval, retrieval, ingestion, tenancy и security |
| Worker/queue/storage | worker code, Compose, operations и public demo |
| Измерение качества | Добавить дату, revision, dataset и conditions в report |

Избегайте копий одного контракта: краткое описание в README ссылается на каноническую страницу.

## Evidence по текущему публичному демо

Во время последнего обновления проверены Docker healthchecks backend/frontend, TLS и HTTP `200` для `/` и `/ready`.
Полный chat flow после последнего изменения раннего SSE `meta` в этой проверке не запускался.
Нагрузочные тесты, backup restore drill, firewall вне VPS и реальные IdP/Stripe credentials не проверялись.

## Результаты документационной валидации

| Проверка | Результат |
| --- | --- |
| Relative Markdown links и локальные anchors | **PASS** — 32 файла, `docs/superpowers/` исключён |
| Fenced code/mermaid balance | **PASS** — незакрытых блоков нет |
| `git diff --check` | **PASS** |
| Compose base/public-demo syntax | **PASS** — обе конфигурации прошли `docker compose config -q` |
| Markdownlint / Mermaid CLI | В репозитории не закреплены; внешние зависимости не добавлять для аудита |

Прошлые документы были аудированы 2026-10-12; эта запись актуализирует результаты для состояния 2026-10-29.
