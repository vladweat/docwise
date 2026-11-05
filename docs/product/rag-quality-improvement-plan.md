# RAG Quality Improvement Implementation Plan

> **For agentic workers:** Implement this plan task by task. Each task ends with its own verification and commit.

**Goal:** Improve RAG quality and verifiability using valid evaluation data, stage diagnostics, answerability checks, and measured end-to-end changes.

**Architecture:** Keep the existing synchronous FastAPI/SQLAlchemy architecture. Evaluation semantics and instrumentation are in place, and a combined benchmark now covers positive, no-answer, and ACL-negative cases. Use it to evaluate retrieval and answer changes without promoting profiles or thresholds before all gates pass.

**Tech Stack:** FastAPI, SQLAlchemy/PostgreSQL/pgvector, FastEmbed/ONNX, Celery, pytest, MIRACL-derived evaluation fixtures, OpenAI-compatible LLM API.

**Spec:** The goal, selected approach, known evidence, constraints, and acceptance criteria in this document are the approved design brief.

## Статус на 2026-11-01

- Eval parity, answerability slices, and the full 132-case end-to-end benchmark are complete. The corrected Top-4
  run and paired Top-2 comparison are recorded in [reports](../../reports/README.md).
- RAG quality work remains **in progress**. Top-4 fails Context Precision (`0.952`, gate `0.975`) and English
  Answer Relevance (`0.799`, gate `0.827`); Top-2 also fails and is rejected. Production defaults are unchanged.
- Task 3 Step 3 remains open: validate false refusals and blinded per-rank context labels, then add a regression
  test for a selected behavior before changing runtime retrieval or abstention.
- Task 4's measured evaluation batching work is complete. Task 5 remains partial: the backend suite and focused
  Ruff checks passed, but `make lint`, Make test targets, typecheck, and frontend checks were not run here.

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

- Парный Top-4/Top-2 benchmark использует одинаковый dataset hash
  (`04e8b54242c9951607330e39030a6a461f1398c9eab50d4c33e066aacf225f84`), профиль `multilingual-compact`,
  reranker `BAAI/bge-reranker-v2-m3-int8` и threshold `0.01`; различается `rerank_top_k`.
- Оба запуска прошли ACL и case-error checks (`0` leaks, `0` errors), а no-answer refusals — `6/6`; оба
  нарушили Context Precision и English Answer Relevance floors. Полный результат — в
  [сравнении](../../reports/rag_quality_corrected_classifier_comparison.md).
- Артефакты указывают `code_revision=unrecorded`. Сохранены dataset hash и параметры, но byte-for-byte
  воспроизводимость не установлена; generation и LLM judge scores могут меняться между прогонами.
- Тексты локальных MIRACL excerpt-ов находятся в ignored `eval/local_data`; их не добавлять в Git.

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

- [x] **Step 1: After Task 4, run and save the full combined-dataset baseline** at current production profiles.
- [x] **Step 2: Compare multilingual profiles and threshold sweep** on identical positive, no-answer, and ACL-negative cases.
- [ ] **Step 3: Inspect named weak cases and add one regression test per chosen behavior** before production changes.
- [x] **Step 4: Change only the best-supported retrieval or prompt behavior**; preserve candidate defaults until gates pass. No candidate profile or threshold was promoted; the Unicode FTS correctness fix is recorded separately below.
- [x] **Step 5: Re-run full evaluation and record all quality/ACL gate outcomes** against the recorded baseline. Full candidate evaluation completed with the target-document, Context Precision, and English Answer Relevance gates failing.
- [x] **Step 6: Save candidate report and commit each confirmed product change separately.** No candidate passed the available combined quality gates, so findings are recorded and defaults remain unchanged. See [constrained Task 3 diagnostic](../../reports/rag_quality_task3_diagnostic.md).

**Task 3 execution note (2026-10-31):** The full 132-case retrieval-only baseline and a later
full generation/judge run completed at current production profiles and rerank batch size 16.
End-to-end metrics: target-document hit `0.776`, Faithfulness `0.984`, Context Precision `0.961`,
English Answer Relevance `0.722`, all-language Answer Relevance `0.591`, citation support `0.980`,
no-answer refusals `6 / 6`, ACL leaks `0 / 41`, and case errors `0`. The target-document,
Context Precision, and English Answer Relevance gates failed. Observed retrieval RSS was `2.25 GiB`
(`2,353,732 KiB`); the generation container stayed around `2.40 / 2.73 GiB` with about `0.64 GiB`
host available RAM. Reranker scoring retained `39 / 40` MIRACL target documents, while
thresholding/Top-4 retained `25 / 40`; threshold `0.10` raised total positive target hits to
`70 / 85` (`0.824`), still below the `0.980` floor. The full multilingual judge encoder was cached,
so the earlier 30-case Answer Relevance errors are superseded by the full-run scores. The full
132-case `multilingual-compact` comparison then ran against the identical dataset hash and prompt:
target-document hit `0.953`, target-section hit `0.846`, Context Precision `0.944`, English
Answer Relevance `0.741`, all-language Answer Relevance `0.666`, no-answer refusals `6/6`, ACL
leaks `0/41`, case errors `0`. This improves retrieval over current (`0.776` doc hit) but fails
three quality floors. A full `0.10` run reached target-document hit `0.965` and section hit `0.885`,
but Context Precision fell to `0.927`, English Answer Relevance to `0.739`, and citation support to
`0.891`; ACL remained `0/41`, no-answer refusals `6/6`, errors `0`. Candidate reranking took
`1,192.39 s` at `0.10` and `1,257.78 s` at `0.25`, against `612.04 s` for current. The lower
threshold is not promoted because it trades a small coverage gain for worse context/citation
scores and still fails three gates. The full local candidate report contains per-case question text
and is removed after analysis; retained diagnostics for this experiment contain case IDs, scores,
ranks, and metrics without question, answer, or passage text. Older reports vary; see the
[report catalog](../../reports/README.md) before treating an artifact as aggregate-only. Step 2 and full verification
Step 5 are complete; Step 3 remains open for deeper review of the six MIRACL section misses at
threshold `0.10` (2 English, 4 Russian) and a regression test if a concrete behavior is selected.
Threshold `0.10` rescued two of the eight misses at `0.25`, but worsened precision/citation metrics.
Production defaults remain unchanged because candidate gates fail.
Additional stage-level review shows the multilingual target section in MIRACL Top-4 at `39/40`
after reranker scoring, falling to `34/40` with threshold `0.10` and `32/40` with `0.25`.
This attributes part of the loss to thresholding; it does not validate a language-specific threshold,
because the full run shows Context Precision/citation regressions and the sample is too small to
calibrate separate policies. Step 3 remains open for case-level review and a regression test tied to
a specific selected behavior.
To make the next case review actionable without emitting passage text, the evaluator now includes
each exact-section miss's case ID and stage ranks (including `0.10`/`0.25` simulations) in its
report; the focused reporting suite passes. Existing candidate reports predate this field, so Step 3
still needs a new retrieval run to inspect those case-level ranks.

The rerun is recorded in [`rag_quality_candidate_001_case_diagnostics.json`](../../reports/rag_quality_candidate_001_case_diagnostics.json).
It confirms the threshold `0.01` recall gain, while repeated Context Precision / English Answer
Relevance remain below their floors. The follow-up instrumentation stores per-rank binary context
relevance and refusal booleans in [`instrumented diagnostics`](../../reports/rag_quality_candidate_001_instrumented_case_diagnostics.json),
still without question, answer, or passage text. Its offline same-case Top-K sweep gives Top-2
Context Precision `0.952` versus `0.940` at Top-4, but exact-section recall falls from `51/52` to
`49/52`; Top-2 remains below the `0.975` Context Precision floor. This is a test candidate, not a
production selection. Generated answer metrics and target-document hit@2 still need an end-to-end
comparison. See [Top-K analysis](../../reports/rag_quality_context_selection_topk.md).

The follow-up on 11 positive refusals produced `9/11` refusals on the first replay and `10/11` on a
second replay. The latest replay classified five responses as exact refusal, five as a refusal phrase
embedded in a longer answer, and one as a regular answer. Its per-rank context-verdict vectors
matched the original run for `6/11` cases. A same-model reviewer from the first replay rated context
sufficient in `6`, partial in `1`, insufficient in `4`, and considered refusal inappropriate in
`7/11`; this is not independent ground truth and does not describe the second replay. All cases had
nonempty retrieved context and no ACL leaks. See
[refusal case analysis](../../reports/rag_quality_refusal_case_analysis.md). Before adjusting
abstention, manually validate the cases. The evaluation metrics now split exact refusals, embedded
phrases, regular answers, and empty responses; this instrumentation does not change runtime
generation or abstention behavior.

A full candidate end-to-end run at threshold `0.01` tested the cutoff hypothesis on the same
132-case dataset and changed no production setting. Target-document hit reached `1.000` (`85/85`),
target-section hit `0.981` (`51/52`), and MIRACL section hit `0.975` (`39/40`). Against `0.10`,
English Answer Relevance improved from `0.739` to `0.777`, all-language Answer Relevance from
`0.661` to `0.720`, and citation support from `0.891` to `0.935`; Context Precision declined from
`0.927` to `0.922`. The candidate still fails Context Precision (`0.975` floor) and English Answer
Relevance (`0.827` floor). No-answer remained `6/6`, ACL leaks `0/41`, and case errors `0`.
Reranking took about `1,201.5 s`, close to twice the current profile. Five of six previous section
misses were recovered; `miracl-ru-223` was absent at every retrieval stage under the multilingual
candidate's 80-token chunking/profile and remains a candidate-specific first-stage investigation.
The cutoff is confirmed as one recall bottleneck, but `0.01` is not
promoted because end-to-end quality gates fail and inference cost is high. Step 3 stays open for
precision/relevance improvements that preserve recall and investigation of the first-stage miss.

The next case investigation found a Unicode FTS tokenization bug: Python split Cyrillic words at
combining acute accents while PostgreSQL's `simple` parser kept them as single lexemes, and FTS query
validation discarded the marked tokens. The tokenizer and validation now preserve those marks; both
unit and PostgreSQL-backed sparse-search regression tests pass. A fresh full current-profile
retrieval-only run retained `66/85` target-document hits and `0/41` ACL leaks, so this correctness
fix did not measurably move aggregate recall on the fixed set. On `miracl-ru-223`, current-profile
reranker scoring ranked the exact section first, but threshold `0.25` removed it; the multilingual
candidate has a profile-specific earlier-stage miss. This does not solve Context Precision or
Answer Relevance, so Step 3 remains open and no production profile or threshold is promoted.
The final branch review also closed an eval-gate gap: a generation run with no no-answer cases now
fails that gate; retrieval-only runs continue to mark generation gates `N/A`. A regression test
covers both modes.

**Failure slice follow-up (2026-11-01):** The corrected Top-4 English Answer Relevance gate uses
the evaluator's pure `en` script bucket (`n=53`), not mixed-script cases. Three exact refusals on
positive EN cases have target-document and exact-section hits; their `0.0` Answer Relevance lowers
the overall mean to `0.799`. Among the 50 non-refusal answers the mean is `0.847`, above the gate,
so the actionable issue is answerability/abstention, not a reason to lower the gate. MIRACL has
`40/40` target-document hits and `39/40` target-section hits, but judged Context Precision `0.902`;
context relevance falls from `34/40` at rank 1 to `12/39`, `5/38`, and `6/30` at later ranks. The
Top-2 E2E run only raises MIRACL Context Precision to `0.913` and loses document/section hits.
See the [case-level failure analysis](../../reports/rag_quality_failure_analysis.md). Step 3 stays
open for a bounded answerability replay and a blinded human check of MIRACL per-rank context labels;
the safe artifacts omit text, so they cannot prove whether later chunks are truly irrelevant or the
judge is wrong. Do not change gates or production retrieval until those checks are complete.

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

- [x] Backend suite passed (`363` tests, `3` pre-existing warnings); focused Ruff checks passed.
- [ ] `make lint`, `make test-smoke`, `make test`, `make typecheck`, and `make test-frontend` were not run in this environment; Make target availability and required infrastructure were not verified.
- [x] Run the full corrected Top-4 baseline and paired Top-2 end-to-end eval; record dataset hash, configuration, metrics, and gate outcomes in `reports/rag_quality_corrected_classifier_comparison.md`.
- [x] Review ACL boundaries, docs, and complete diff.
- [x] Complete a fresh whole-branch review and report deferred issues.
- [ ] Publish the finalized changes to the user's existing private GitHub repository. Repository visibility remains private; no public visibility or license change is in scope. No push has occurred yet.

**Verification status (2026-11-05):** Prior verification passed the backend suite (`363` tests, `3`
pre-existing warnings) and focused Ruff checks. This documentation turn reran no tests or evaluation.
`make lint`, `make test-smoke`, `make test`, `make typecheck`, and `make test-frontend` remain unrun;
availability and required infrastructure were not verified. The previously completed corrected Top-4
and paired Top-2 runs each covered `132/132` cases with zero case errors and ACL leaks and `6/6`
no-answer refusals, while Context Precision and English Answer Relevance gates failed. Top-2 lost
document/section hits and had lower Faithfulness and Answer Relevance; production Top-4 remains
unchanged. See the [sanitized comparison](../../reports/rag_quality_corrected_classifier_comparison.md).

## Ограничения

- Не менять ORM-модели без Alembic-миграции.
- В retrieval dense и FTS должны фильтроваться по `organization_id` и `access_roles` до RRF,
  reranker и LLM.
- `organization_id` берётся только из authenticated session/trusted DB; не считать RLS защитой,
  если runtime использует superuser без `DOCWISE_RLS_SESSION_ROLE`.
- Не передавать restricted chunk text в prompt, cache, audit, logs или errors.
- При изменении ingestion-кода перезапустить `celery-worker`.

