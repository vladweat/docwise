# RAG Quality Improvement Implementation Plan

> **For agentic workers:** Implement this plan task by task. Each task ends with its own verification and commit.

**Goal:** Improve RAG quality and verifiability using valid evaluation data, stage diagnostics, answerability checks, and measured end-to-end changes.

**Architecture:** Keep the existing synchronous FastAPI/SQLAlchemy architecture. First align production and evaluation semantics, then establish safe eval timing and improve throughput before running the full combined benchmark. Use that benchmark to evaluate retrieval and answer changes on positive, no-answer, and ACL-negative cases.

**Tech Stack:** FastAPI, SQLAlchemy/PostgreSQL/pgvector, FastEmbed/ONNX, Celery, pytest, MIRACL-derived evaluation fixtures, OpenAI-compatible LLM API.

**Spec:** The goal, selected approach, known evidence, constraints, and acceptance criteria in this document are the approved design brief.

## Global Constraints

- `organization_id` comes only from the authenticated session or trusted DB record.
- Dense and FTS retrieval apply organization and `access_roles` filters before RRF, reranking, and LLM.
- Restricted chunk text never enters prompt, cache, audit, errors, logs, or committed reports.
- ORM changes require a new Alembic migration; existing migrations are immutable.
- Ingestion changes require restarting `celery-worker`.
- Do not promote model profiles or thresholds unless full quality and ACL gates pass.
- Do not convert the project to async as part of this work.

## Review Focus

- English/Russian no-context responses must match production language behavior and count as refusals.
- An ACL-negative query must not send a leaked chunk into generation even if the eval detects a leak.
- A no-answer case must not be treated as a positive target-hit case or inflate answerable recall.
- Concurrent eval tasks must bind independent sessions and RLS context per case.
- Candidate models, threshold changes, and batching must preserve vector-profile consistency and input/result order.

---

## Цель

Улучшать RAG по воспроизводимым end-to-end результатам: ответы должны находить нужный фрагмент,
отвечать на языке вопроса, опираться на доступный контекст и корректно отказываться, когда данных нет.
Каждое изменение оценивается на одном закреплённом наборе данных и не попадает в production-профиль,
пока не пройдены quality и ACL gates.

Полный переход backend на `async` в этот план не входит. CPU-части retrieval остаются синхронными;
ускорение прогонов допускается через batching и ограниченный thread concurrency.

## Подходы

1. **Сначала достоверный eval, затем изменения пайплайна — выбранный подход.** Исправить расхождения
   eval/production, собрать репрезентативный benchmark, локализовать провалы по стадиям и менять крупные
   блоки только по диагностике. Это снижает риск оптимизации неверной метрики.
2. **Сначала ускорение прогонов.** Увеличить пропускную способность, не меняя качество продукта. Это
   полезно для частоты экспериментов, но само не исправляет замеченные ошибки ответа и retrieval.
3. **Сразу перестроить retrieval и генерацию.** Даёт большой потенциальный эффект, но существующая
   метрика отказов и неполный реальный набор затрудняют достоверно оценить результат.

## Что уже известно

- В отчёте MIRACL на 40 positive кейсах и без ACL-negative cases `Recall@4` упал с `0.975` после
  scoring reranker до `0.850` после threshold `0.10`; при `0.25` — до `0.800`.
- В том же прогоне Answer Relevance составил `0.480`, Context Precision — `0.886`. Отчёт распознаёт
  только русскую фразу отказа, а eval на пустом retrieval всегда возвращает русский текст; эти
  метрики требуют пересчёта после исправления parity.
- Полный eval уже ограничивает параллелизм generation/judges, но подготовка кейсов и retrieval идут
  последовательно. Один полный прогон занял около 18 минут вместе с подготовкой корпуса.
- В текущем workspace находятся незакоммиченные изменения eval-профилей, MIRACL, диагностики стадий,
  батчевого Answer Relevance и отчётов. Их следует сохранить отдельной базовой контрольной точкой.

## Этапы

### 0. Сохранить текущую работу и baseline

- Проверить состав незакоммиченных изменений и отделить уже выполненную MIRACL/eval-работу от новых
  улучшений.
- Сохранить текущий эксперимент локальными логичными коммитами; не включать секреты и `docs/superpowers/`.
- Работать над изменениями в отдельной ветке от сохранённой контрольной точки.
- Записать revision, dataset hash, настройки моделей и текущие отчёты.

**Готово, когда:** исходная работа восстановима из Git, а baseline не смешан с новыми изменениями.

### 1. Сделать метрики отказа и генерации достоверными

- Устранить конфликт между фиксированной русской фразой отказа в system prompt и правилом языка
  пользователя.
- Использовать одинаковое поведение для пустого retrieval в production и eval.
- Распознавать стандартные отказы на русском и английском при расчёте coverage, faithfulness и
  answer relevance.
- Оставить ACL leak cases без текста restricted chunks в prompt, логах и отчёте.

**Готово, когда:** тесты фиксируют RU/EN отказ для пустого и нерелевантного контекста; eval report
считает их одинаково, а ACL regression не передаёт недоступный текст в generation.

### 2. Собрать сравнимый end-to-end benchmark

- Объединить релевантные synthetic ACL fixtures с real-text MIRACL cases в одном полном запуске.
- Добавить явные случаи без ответа и сохранить существующую матрицу ролей/организаций.
- Отчёт должен разделять synthetic и real-text slices, RU/EN, positive, no-answer и ACL-negative.
- Сохранять версии и hash кода/dataset/config; не записывать ответы, тексты chunks или секреты.
- Разделить стабильные regression gates и исследовательские scores; повторять вариативные judge
  измерения там, где единичный запуск не даёт надёжного вывода.

**Готово, когда:** полный прогон включает положительные, no-answer и ACL-negative кейсы, а любой
провал можно найти по вопросу и стадии retrieval без утечки содержимого.

### 3. Улучшить отбор контекста и abstention

- Сопоставить dense, sparse, RRF, reranker scoring, threshold и финальный Top-K.
- Проверить threshold sweep и fallback для низкой уверенности совместно на positive и no-answer
  примерах; выбирать конфигурацию по recall, precision, правильным отказам и качеству ответа.
- Сравнить текущий embedding/reranker профиль с multilingual candidate на одной и той же разметке.
- Не менять production defaults без прохождения quality и ACL gates.

**Готово, когда:** выбранная конфигурация улучшает end-to-end показатели на real-text slice без
регрессии synthetic baseline, ACL isolation и отказов на no-answer cases.

### 4. Улучшить generation и проверяемость ответа

- Разобрать низкие Answer Relevance и Context Precision на конкретных вопросах, не полагаясь на один
  агрегированный judge score.
- Снизить долю отказов при наличии релевантного контекста и не допустить ответов без опоры на источники.
- Сохранить ответ на языке последнего вопроса и проверяемые citations для каждого фактического claim.
- Повторить judge-оценки слабых случаев и вручную сверить небольшую фиксированную выборку с evidence.

**Готово, когда:** улучшение подтверждено полным прогоном и выборочной проверкой, а Faithfulness,
citation support, language parity и ACL gates остаются пройдены.

### 5. Ускорить эксперименты без миграции на async

- Сначала измерить длительность seeding, query embedding, DB search, reranker, generation и judges.
- Пакетировать query embeddings там, где это не меняет модельный профиль или порядок данных.
- При необходимости распараллелить retrieval с отдельной SQLAlchemy-сессией и RLS-контекстом для
  каждого кейса; сохранять ограничение concurrency и измерять peak memory/CPU.
- Не распараллеливать ONNX компоненты без подтверждения потокобезопасности и измерения на VPS.

**Готово, когда:** прогон быстрее на той же машине и dataset, результаты совпадают по retrieval,
качество не падает, а CPU/RAM остаются в заданных ресурсных пределах.

## Порядок проверки и выпуска

1. Для каждого исправления сначала добавить regression test и увидеть ожидаемый провал.
2. Проверить профильные unit/integration tests и полный golden eval после каждого завершённого этапа.
3. Сравнивать baseline и candidate на том же dataset hash; не считать одноразовый нестабильный score
   доказательством выигрыша.
4. Отдельный коммит на каждый завершённый этап; не пушить и не обновлять публичное демо без отдельного
   запроса.

## Исполнительные задачи

### Task 1: Локализованный отказ и parity production/eval

**Files:**
- Modify: `backend/app/services/chat/prompt.py`
- Modify: `eval/run_eval.py`
- Modify: `eval/metrics.py`
- Test: `backend/tests/test_chat.py`
- Test: `backend/tests/test_eval_reporting.py`
- Test: `backend/tests/test_rag_multilingual.py`

**Interfaces:** `prompt.no_context_answer(question: str) -> str` is the source of truth;
`metrics.is_refusal(answer: str) -> bool` classifies either supported localized response.

- [x] **Step 1: Write failing tests** named `test_build_messages_localizes_no_context_instruction`,
  `test_eval_is_refusal_recognizes_ru_and_en`, and `test_eval_empty_retrieval_uses_localized_refusal`.
- [x] **Step 2: Run tests to verify expected failures** with the focused pytest selection.
- [x] **Step 3: Implement localized refusal text** in the system prompt and reuse `no_context_answer` in eval.
- [x] **Step 4: Implement bilingual refusal classification** in `eval/metrics.py` and use it for all refusal metrics.
- [x] **Step 5: Run focused tests, then full backend suite**; record results.
- [x] **Step 6: Run full benchmark** if LLM/eval infrastructure is configured; save report with code and dataset provenance.
- [x] **Step 7: Commit** as `fix: align localized RAG refusals in chat and eval`.

### Task 2: Answerability dataset and separate ACL slices

**Files:**
- Modify: `eval/dataset.py`, `eval/run_eval.py`, `eval/reporting.py`, `eval/quality_gates.py`, `eval/golden_dataset.json`
- Modify: `docs/product/evaluation.md`
- Test: `backend/tests/test_eval_golden_dataset.py`, `backend/tests/test_eval_reporting.py`, `backend/tests/test_eval_concurrency.py`

**Interfaces:** `GoldenCase.kind` supports `positive`, `acl_negative`, and `no_answer`;
`target_doc_id` is required for the first two kinds and absent for `no_answer`.

- [x] **Step 1: Write failing parser/report tests** for `no_answer`, missing target UUID, answerable recall denominator, and refusal/false-answer counts.
- [x] **Step 2: Run them and confirm expected failures** before changing parser or report code.
- [x] **Step 3: Add `GoldenCase.is_no_answer` and nullable target handling**; keep ACL-negative checks separate.
- [x] **Step 4: Add no-answer coverage fields and report slices** without writing answer/context text.
- [x] **Step 5: Add a small fixed set of RU/EN questions absent from the synthetic corpus** and compose it with the existing ACL cases.
- [x] **Step 6: Run dataset/report tests and a fixed 30-case retrieval-only integration slice**; inspect generated report for restricted content. Defer the full combined benchmark until Task 4 reduces its measured resource cost.
- [x] **Step 7: Commit** as `eval: add no-answer cases and separate retrieval coverage gates`.

### Task 3: Evidence-led retrieval and generation improvements

**Files:** Change only after measuring: `backend/app/services/retrieval/`,
`backend/app/services/ingestion/embedding_profiles.py`, `backend/app/services/chat/prompt.py`,
`eval/quality_gates.py`, and tests that reproduce each selected weak case.

**Interfaces:** Keep `retrieve(db, user, query)` tenant/ACL semantics; keep candidate embedding and reranker profiles isolated from production defaults.

- [ ] **Step 1: After Task 4, run and save the full combined-dataset baseline** at current production profiles.
- [ ] **Step 2: Compare multilingual profiles and threshold sweep** on identical positive, no-answer, and ACL-negative cases.
- [ ] **Step 3: Inspect named weak cases and add one regression test per chosen behavior** before production changes.
- [ ] **Step 4: Change only the best-supported retrieval or prompt behavior**; preserve runtime defaults until gates pass.
- [ ] **Step 5: Re-run full evaluation and verify all quality/ACL gates** against the recorded baseline.
- [x] **Step 6: Save candidate report and commit each confirmed product change separately.** No candidate passed the available combined quality gates, so findings are recorded and defaults remain unchanged. See [constrained Task 3 diagnostic](../../reports/rag_quality_task3_diagnostic.md).

**Task 3 execution note (2026-10-31):** The full 132-case retrieval-only baseline completed at
batch size 16: target-document hit was `0.776`, ACL leaks `0 / 41`, and case errors `0`. Observed
process peak RSS was `2.25 GiB` (`2,353,732 KiB`). Reranker
scoring retained `39 / 40` MIRACL target documents, while thresholding/Top-4 retained `25 / 40`.
Threshold `0.10` raised total positive target hits to `70 / 85` (`0.824`), still below the `0.980`
floor and without a full generation/no-answer comparison. A 30-case generation slice completed
with all six no-answer refusals correct and zero ACL leaks, but target-document hit was `0.750`
and Context Precision was `0.944`; Answer Relevance could not be computed because the evaluator's
multilingual MiniLM ONNX model was absent from the image. The full 132-case generation attempt was
stopped at the VPS memory limit. These are diagnostic results, not a promotion gate. Steps 1,
2, 3, and 5 remain open: full end-to-end baseline, same-dataset current/candidate comparison,
complete weak-case review, and full candidate verification require a larger-memory eval worker
with the evaluator model cache. No retrieval or prompt behavior was changed.
The final branch review also closed an eval-gate gap: a generation run with no no-answer cases now
fails that gate; retrieval-only runs continue to mark generation gates `N/A`. A regression test
covers both modes.

### Task 4: Faster evaluation with batching, without async migration

**Files:** If timings justify changes, modify `eval/run_eval.py`, `eval/concurrency.py`,
`backend/app/services/retrieval/__init__.py`, `backend/app/services/retrieval/search.py`, `Makefile`,
`docs/product/evaluation.md`, and tests.

**Interfaces:** Retrieval accepts either a query or a precomputed vector while deriving organization and roles only from the authenticated principal.

- [x] **Step 1: Add stage timing output** and test that timings are complete, non-negative, and contain no query/content.
- [x] **Step 2: Measure the fixed 30-case integration slice** to identify whether embedding or DB/retrieval dominates, while recording CPU and peak memory.
- [x] **Step 3: Write failing order/alignment tests** for bounded query/document pair batches; leave query embedding batch size at `1` by default because size `32` did not improve the slice.
- [x] **Step 4: Skip retrieval DB workers**; DB search was under 1% of measured retrieval time, so concurrent sessions would add RLS complexity without targeting the bottleneck.
- [x] **Step 5: Re-run the same slice and compare quality, wall time, CPU, and peak memory.** The cross-query reranker candidate improved the measured rerank and wall time; the full end-to-end combined baseline remains gated on VPS resources.
- [x] **Step 6: Commit the measured reranker batching separately** with a `perf:` message; do not add DB concurrency without evidence.

**Execution order note:** A full 132-case retrieval-only run later completed with rerank batch `16` in `10m43s`; peak process RSS was `2.25 GiB` (`2,353,732 KiB`), target-document hit `0.776`, and ACL leaks/errors stayed `0`. Full generation was stopped when host available RAM fell below `0.5 GiB`. On the fixed synthetic 30-case slice, batch-1 control took `73.05 s`, `2.08 GiB` (`2,181,088 KiB`) peak RSS, with query embedding `1.16 s`, DB search `0.53 s`, rerank `68.15 s`. Embedding batch `32` took `75.22 s` and did not improve retrieval, so the default remains `1`. Length-bucketed cross-query rerank batches of `64` took `71.87 s`, `2.07 GiB` (`2,172,012 KiB`) peak RSS; rerank was `65.60 s`, target-document hit stayed `1.000`, ACL leaks/errors stayed `0`. On the 30-case long-passage generation diagnostic, rerank batch `16` took `155.50 s` at about `2.23 GiB` RSS (`2,335,236 KiB`); batch `32` took `171.11 s` and reached about `2.47 GiB` (`2,594,328 KiB`). The speed/memory tradeoff therefore depends on passage length; keep the existing default until it is validated on a larger-memory worker. Keep monitoring VPS resources.

### Task 5: Final verification and handoff

- [ ] Run `make lint`, `make test-smoke`, `make test`, `make typecheck`, and `make test-frontend` when required infrastructure is available.
- [ ] Run the full RAG eval and record code revision, dataset hash, configuration, and gate outcomes.
- [x] Review ACL boundaries, docs, and complete diff; do not push or deploy the demo without a separate request.
- [x] Complete a fresh whole-branch review and report deferred issues.

**Verification status (2026-10-31):** The backend suite passed `356` tests with `3`
deprecation warnings; focused Ruff checks and updated-document relative links passed. The `make`
binary is unavailable, so Make targets, typecheck, and frontend checks were not run. The full
end-to-end RAG generation benchmark and same-dataset candidate comparison remain open as recorded
in Task 3.

## Ограничения

- Не менять ORM-модели без Alembic-миграции.
- В retrieval dense и FTS должны фильтроваться по `organization_id` и `access_roles` до RRF,
  reranker и LLM.
- `organization_id` берётся только из authenticated session/trusted DB; не считать RLS защитой,
  если runtime использует superuser без `DOCWISE_RLS_SESSION_ROLE`.
- Не передавать restricted chunk text в prompt, cache, audit, logs или errors.
- При изменении ingestion-кода перезапустить `celery-worker`.

