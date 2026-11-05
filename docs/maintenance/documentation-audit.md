# Аудит документации

**Дата сверки:** 2026-11-05 · **источник кода:** текущая рабочая копия · **runtime:** Docwise public demo приостановлено; контейнеры остановлены, TLS не проходит.

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
- 2026-10-31 завершён full end-to-end eval на 132 кейсах с обеими Answer Relevance encoder-моделями: case errors `0`, ACL leaks `0/41`, no-answer refusals `6/6`; target-document hit `0.776`, Context Precision `0.961`, English Answer Relevance `0.722` — эти три gates не пройдены. Агрегаты: `reports/rag_quality_task3_diagnostic.md`; подробный per-question report содержит тексты и остаётся вне Git, отдельный sanitized JSON хранит только IDs, ranks, scores и метрики.
- Same-dataset multilingual candidate `multilingual-compact` также завершил все 132 кейса: при пороге `0.25` document hit `0.953`, section hit `0.846`, Context Precision `0.944`, English Answer Relevance `0.741`, no-answer `6/6`, ACL leaks `0/41`, errors `0`. Полный run при пороге `0.10` поднял retrieval hit до `0.965`, но Context Precision упал до `0.927`, English Answer Relevance — до `0.739`, citation support — до `0.891`; no-answer `6/6`, ACL leaks `0/41`, errors `0`. Reranking занял `1,192.39–1,257.78s` против `612.04s` у current. Все quality gates не пройдены; production profile/threshold не изменены.
- Дополнительный полный run кандидата при пороге `0.01` поднял target-document hit до `1.000` (`85/85`), target-section — до `0.981` (`51/52`), MIRACL section hit — до `0.975` (`39/40`). English Answer Relevance вырос до `0.777`, all-language — до `0.720`, citation support — до `0.935`; Context Precision составил `0.922`, ниже floor `0.975`. No-answer `6/6`, ACL leaks `0/41`, case errors `0`; три некорректных первых ответа judge успешно повторены. Reranking занял около `1,201.5s`, почти вдвое дольше текущего профиля. Пять из шести прежних промахов секции восстановились; `miracl-ru-223` не находился ни на одной стадии retrieval. Порог `0.01` не принят: остаются провалы precision/relevance gates и высокая стоимость reranking.
- Повторный полный run кандидата при пороге `0.01` на том же dataset hash подтвердил recall (`85/85` документов, `51/52` секций, `39/40` MIRACL exact sections), но Context Precision `0.941` и English Answer Relevance `0.768` снова ниже floors. ACL leaks `0/41`, no-answer `6/6`, errors `0`; rerank — `1,203.6s`. Sanitized per-case артефакт `reports/rag_quality_candidate_001_case_diagnostics.json` содержит только IDs, ranks, scores и агрегатные метрики, без вопросов, ответов и passage text. Анализ показывает концентрацию низкого Context Precision в MIRACL (`0.878`, synthetic `0.996`), но пока не обосновывает Top-K change; следующий прогон должен сохранять per-rank relevance labels для controlled selection comparison.
- Instrumented повтор кандидата `0.01` сохранил per-rank context relevance и boolean отказа (`reports/rag_quality_candidate_001_instrumented_case_diagnostics.json`). Один из 132 кейсов завершился judge error; ACL leaks `0/41`, no-answer `6/6`, document hit `85/85`, section hit `51/52`, Context Precision `0.940`, English Answer Relevance `0.770`. Offline Top-K sweep без rerank: Top-2 CP `0.952`, exact-section `49/52`; Top-4 CP `0.940`, exact-section `51/52`. Подробности и ограничения: `reports/rag_quality_context_selection_topk.md`; Top-2 остаётся кандидатом для отдельного end-to-end теста, runtime defaults не изменены.
- Targeted повторы 11 положительных отказов: первый replay классифицировал `9/11` ответов как отказы, второй — `10/11`; в последнем пять были точной фразой отказа, пять содержали её внутри более длинного ответа, один был обычным ответом. Per-rank verdict совпал с исходным run для `6/11` кейсов. Same-model rubric-review первого replay признал контекст достаточным в 6 случаях, частичным в 1, недостаточным в 4; отказ уместным в 4, неуместным в 7. Это предварительная LLM-оценка, не независимая разметка и не оценка второго replay. Все целевые кейсы имели непустой контекст и `0` ACL leaks; сырые тексты не сохранены. См. `reports/rag_quality_refusal_case_analysis.md` и структурные метки `reports/rag_quality_refusal_case_analysis.json`.
- После targeted анализа eval-классификатор отказа исправлен: точная стандартная фраза, встроенная фраза, обычный и пустой ответ теперь разделяются; только точный отказ считается `answer_is_refusal` и корректным `no_answer` abstention. В отчёт добавлены четыре взаимоисключающие категории положительных ответов. Это изменение метрик и отчётности, генерация и production prompt не менялись; старые отчёты сохраняют классификацию на момент своего прогона.
- MIRACL stage diagnostic кандидата локализует часть потери в глобальном reranker threshold: exact target section в Top-4 есть у `39/40` кейсов после scoring, `34/40` при threshold `0.10` и `32/40` при `0.25`. Понижение порога возвращает recall, но ухудшает Context Precision/citation support; RU/EN-specific пороги не вводятся без отдельной калибровки.
- При threshold `0.10` остались шесть MIRACL exact-section misses (2 English, 4 Russian); report хранит только их IDs, а per-question details остаются вне Git. Entity/term matching записан как гипотеза, не подтверждённая причина.
- `eval/run_eval.py` теперь добавляет в новый report stage ranks для каждого exact-section miss (case ID, dense/sparse/RRF/reranker/final ranks и threshold ranks), без текста chunks; покрыто `backend/tests/test_eval_reporting.py`.
- Для кириллических слов с Unicode combining acute marks устранено расхождение Python FTS-токенизации и PostgreSQL `simple` lexemes; query validation теперь принимает combining marks. Regression покрывает токены и PostgreSQL-backed sparse search. Полный current-profile retrieval-only run после исправления сохранил `66/85` target-document hit, `0/41` ACL leaks, `0` ошибок. В `miracl-ru-223` точная секция поднялась до reranker rank `1`, но была отброшена порогом `0.25`; aggregate quality gain не заявляется, end-to-end judge метрики не запускались.
- Synthetic golden set теперь включает 45 answerable, 6 `no_answer` и 41 ACL-negative case; no-answer cases не входят в retrieval denominator и имеют отдельный refusal gate. Полный combined baseline и same-dataset multilingual candidate comparison завершены 2026-10-31; три quality gates не пройдены, production defaults оставлены без изменений.
- Eval report описывает aggregate runtime profile (query embedding, DB search, rerank); eval использует bounded synchronous query/document batches (`EVAL_EMBEDDING_BATCH_SIZE=1` by default, `EVAL_RERANK_BATCH_SIZE=64`) без async migration. На фиксированном synthetic slice query batch `32` не ускорил прогон; length-bucketed rerank pair batches дали предварительные `-3.7%` rerank time и `-1.6%` wall time при равных метриках. Это ждёт проверки на full combined benchmark.
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

На проверке **2026-11-05** контейнеры `docwise-public-demo-*` были exited, HTTPS для `docwise.wvzl.site`
завершался ошибкой TLS, и публичное демо считалось приостановленным/недоступным. Более ранние результаты
healthchecks, TLS и HTTP `200` для `/` и `/ready` — исторические; полный chat flow после изменения раннего
SSE `meta` тогда не запускался. Отдельные `labtrack-demo-*` контейнеры к Docwise не относятся.
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

## Обновление eval-документации — 2026-11-01

Добавлено парное end-to-end сравнение Top-4 и Top-2 после исправления классификатора отказов:
[product evaluation](../product/evaluation.md), [RAG quality plan](../product/rag-quality-improvement-plan.md),
[Task 3 diagnostic](../../reports/rag_quality_task3_diagnostic.md) и
[sanitized comparison](../../reports/rag_quality_corrected_classifier_comparison.md). Записаны
dataset SHA-256, конфигурация, результаты и ограничения; per-case артефакты не содержат prompts,
вопросов, ответов или текста passages. Роуты, API schemas, runtime configuration и demo operation
не менялись.

Кейс-уровневый разбор причин низких оценок добавлен в
[RAG failure analysis](../../reports/rag_quality_failure_analysis.md), а агрегаты eval обновлены
с отдельными `en`, `ru` и mixed-script buckets. Он фиксирует false refusals на answerable EN cases,
падение judged context relevance после rank 1 в MIRACL и ограничения вывода без сохранённых chunk
текстов. Изменение порогов и production retrieval не выполнялось.

## Каталог экспериментов и текущий статус — 2026-11-05

README теперь показывает актуальный полный Top-4 результат от 2026-11-01 и ссылается на каноническую
[evaluation](../product/evaluation.md) и новый [каталог reports](../../reports/README.md). Индекс охватывает
все 18 result artifacts: 9 ранее существовавших отчётов и 9 новых report/artifact files; вместе с самим
индексом это 10 существующих файлов report surface и 9 новых артефактов. Материалы сгруппированы как
baseline/candidate, MIRACL, Top-K, refusal/error и load/performance; старые per-case question fields
обозначены отдельно без копирования анализа в индекс. Техдолг обновлён с устаревшего 35-case статуса на
текущие проваленные Context Precision и English Answer Relevance gates. План оставляет RAG quality work
незавершённой: Top-2 отклонён, а Task 3 Step 3 остаётся открытым.

Для последней пары указаны dataset hash, профиль, threshold, метрики и ограничение `code_revision=unrecorded`;
воспроизводимость не заявляется. В этот документационный проход tests и eval повторно не запускались.
Изменялись только документы; GitHub metadata/visibility и runtime не менялись.
