# Каталог экспериментов и отчётов

Отчёты фиксируют отдельные запуски, а не обещают качество на новых данных. Сначала сверяйте дату,
dataset, профиль и ограничения в самом файле. Текущий статус gates и каноническая интерпретация метрик
описаны в [evaluation](../docs/product/evaluation.md).

## Baseline и candidate

- **Актуальная пара Top-4 / Top-2, 2026-11-01:** [сравнение и решение](rag_quality_corrected_classifier_comparison.md),
  [Top-4 JSON](rag_quality_corrected_classifier_baseline.json), [Top-2 JSON](rag_quality_corrected_classifier_top2.json).
  Это полный прогон на 132 кейсах с одинаковым dataset hash. Context Precision и English Answer Relevance
  gates не пройдены; Top-2 отклонён. В обоих JSON `code_revision=unrecorded`, поэтому byte-for-byte
  воспроизводимость не подтверждена.
- [Разбор причин провала текущих gates](rag_quality_failure_analysis.md) связывает English Answer Relevance
  с refusals на positive cases и показывает падение judge-релевантности контекстов на поздних MIRACL ranks.
- [Task 3 diagnostics](rag_quality_task3_diagnostic.md) — более ранний retrieval/generation baseline,
  candidate-профили и ограничения VPS; результаты исторические относительно парного прогона выше.
- [RAG benchmark](rag_benchmark.md) и [multilingual candidate](rag_candidate_multilingual.md) — прежние
  полные запуски с другими наборами, настройками или классификацией отказов. Не сравнивайте их scores
  напрямую с текущим парным прогоном.

## MIRACL

- [Candidate report](rag_miracl_candidate.md) — ранний retrieval/generation candidate на MIRACL.
- [Stage diagnostic](rag_miracl_stage_diagnostic.md) — потери target document/section между retrieval stages.
- [Threshold `0.10`](rag_miracl_threshold_010.md) и [concurrent rerun](rag_miracl_threshold_010_concurrent.md) —
  отдельные кандидаты и ограничения сравнения; не являются текущим production benchmark.
- [Concurrency smoke](rag_miracl_concurrency_smoke.md) — ранний короткий замер пути конкурентного eval,
  не чистый benchmark ускорения.

## Top-K и выбор контекста

- [Top-K context-selection analysis](rag_quality_context_selection_topk.md) — offline simulation на сохранённых
  per-rank labels; не end-to-end сравнение и не заменяет [полный Top-4/Top-2 прогон](rag_quality_corrected_classifier_comparison.md).

## Refusal и error diagnostics

- [Failure analysis](rag_quality_failure_analysis.md) — текущие English AR и Context Precision failure slices.
- [Refusal case analysis](rag_quality_refusal_case_analysis.md) и [структурный JSON](rag_quality_refusal_case_analysis.json) —
  повторные проверки 11 positive refusals и ограничения same-model rubric review.
- [Candidate case diagnostics](rag_quality_candidate_001_case_diagnostics.json) и
  [instrumented diagnostics](rag_quality_candidate_001_instrumented_case_diagnostics.json) — безопасные
  per-case IDs, ranks, scores, booleans и числовые метрики без prompts, answers или passage text.

## Нагрузка и производительность

- [Load baseline](load_baseline.md) — исторический retrieval snapshot от 2026-09-22; code revision и dataset
  digest не записаны, поэтому latency не является текущим capacity baseline.
- [MIRACL concurrency smoke](rag_miracl_concurrency_smoke.md) — небольшой ранний замер; см. также MIRACL раздел.

## Содержимое и ограничения

Последние Top-4/Top-2 JSON, comparison, failure analysis и новые диагностические JSON не содержат вопросов,
ответов, prompts, текста документов или passages. Это свойство не распространяется автоматически на старые
отчёты. В частности, per-case question fields есть в следующих архивных benchmark reports:
[RAG benchmark](rag_benchmark.md), [multilingual candidate](rag_candidate_multilingual.md),
[MIRACL candidate](rag_miracl_candidate.md), [MIRACL stage diagnostic](rag_miracl_stage_diagnostic.md),
[threshold `0.10`](rag_miracl_threshold_010.md), [concurrent threshold run](rag_miracl_threshold_010_concurrent.md)
и [concurrency smoke](rag_miracl_concurrency_smoke.md). Не описывайте архив целиком как aggregate-only
или sanitized.

Подготовленные MIRACL excerpts находятся только в игнорируемом `eval/local_data`; в этот каталог и Git они
не включены.
