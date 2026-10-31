# Аудит документации

**Дата сверки:** 2026-10-31 · **источник кода:** текущая рабочая копия на `main` · **runtime:** публичное демо на VPS.

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
- Evaluation описывает подготовку MIRACL real-text candidate, источники/лицензии, ограничения выборки и отдельный запуск.
- Первый полный MIRACL run от 2026-10-30 зафиксирован: 40 real cases, ACL leaks/case errors `0`; retrieval/quality gates не пройдены, см. candidate report.
- Synthetic golden set теперь включает 45 answerable, 6 `no_answer` и 41 ACL-negative case; no-answer cases не входят в retrieval denominator и имеют отдельный refusal gate. Полный combined run отложен до измерения/снижения стоимости eval на VPS.
- Eval-отчёт отделяет ответы/отказы/наличие контекста, измеряет target-section Recall@1/4/10 + MRR на dense, sparse, RRF, rerank scoring, threshold и Top-4 стадиях и симулирует candidate thresholds на тех же scores; refusal/empty-context не получают идеальные Faithfulness/Context Precision.
- Generation/judge evaluation поддерживает bounded concurrency (`--concurrency`, `EVAL_CONCURRENCY`, `make eval EVAL_CONCURRENCY=N`) и пакетный Answer Relevance embedding: retrieval остаётся последовательным, отчёт сохраняет порядок кейсов, прогресс логируется; default concurrency — 4, embedding batch — до 128 текстов. Полный concurrent run на 40 MIRACL-кейсах завершился за `17m 54s`, case errors `0`, ACL leaks `0/0`; target doc/section hit `0.925/0.850`, Faithfulness `0.960`, Context Precision `0.886`, English Answer Relevance `0.514`, 15 refusals. Это не controlled speed benchmark: последовательный запуск занял примерно полчаса, но времена и judge outputs зависят от сети/модели; retrieval оставался последовательным.
- MIRACL stage diagnostic: target-document hit снизился `1.000 → 0.900` после threshold `0.25`; sweep `0.10` дал `0.925` document hit и `0.850` section Recall@4, всё ещё ниже gate. Отдельный generation/judge run candidate `0.10` завершился с одним case error: target document/section hit `0.925 / 0.850`, Faithfulness `1.000 (n=24)`, Context Precision `0.882 (n=37)`, English Answer Relevance `0.507 (n=20)`, 15 refusals из 40; ACL leaks `0`, но ACL-negative cases не запускались. Page gate для MIRACL теперь `N/A`, так как dataset не имеет page labels. Production threshold оставлен прежним.
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
- Demo seed поддерживает явный `--reset --confirm-reset` для чатов, audit и user uploads только организации
  `demo`, после чего повторно индексирует 12 синтетических fixtures.
- Upload/ACL UI группирует organization roles и динамические department memberships; `all` выбирается отдельно,
  preview объясняет аудиторию и собственный read access. API `/documents/access-options` ограничен текущей org.
- Historical RAG snapshot от 2026-09-22 рассчитан на 35 кейсах и не сравнивается напрямую с полным baseline
  от 2026-10-30 на 69 кейсах. Multilingual candidate от 2026-10-30 расширяет corpus до 10 документов и golden set
  до 86 кейсов: target document/page/section hit `1.000`, Faithfulness `1.000`, Context Precision `1.000`,
  citation support `0.978`, English Answer Relevance `0.851` (gate pass), Russian Answer Relevance `0.792`,
  `0/41` ACL leaks и 0 case errors. Повторный targeted citation judge для русского `ru-engineering-first-pr` дал
  `1.000` против `0.000` в полном снимке; не повышайте исходную агрегированную метрику вручную. Eval отчёт записывает
  hash dataset, безопасные model/retrieval параметры и hash
  system prompt, группирует positive кейсы по письменности/persona/kind и показывает quality gates. English relevance
  использует исторический BGE evaluator; Russian score пока без baseline. Полный прогон проваливается при нарушении
  порога, ACL leak, ошибке кейса или отсутствующей метрике; retrieval-only помечает generation gates как `N/A`.

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
| Relative Markdown targets в `docs/` (без private/superpowers) | **PASS** — 31 файл, битых файловых ссылок нет |
| Relative Markdown links и локальные anchors | **PASS** — 32 файла, `docs/superpowers/` исключён |
| Fenced code/mermaid balance | **PASS** — незакрытых блоков нет |
| `git diff --check` | **PASS** |
| Compose base/public-demo syntax | **PASS** — обе конфигурации прошли `docker compose config -q` |
| Markdownlint / Mermaid CLI | В репозитории не закреплены; внешние зависимости не добавлять для аудита |

Прошлые документы были аудированы 2026-10-12; эта запись актуализирует результаты для состояния 2026-10-30.
