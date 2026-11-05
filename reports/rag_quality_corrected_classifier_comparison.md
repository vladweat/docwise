# Исправленный baseline и end-to-end сравнение Top-4 / Top-2

**Дата:** 2026-11-01
**Набор:** 132 кейса; SHA-256 `04e8b54242c9951607330e39030a6a461f1398c9eab50d4c33e066aacf225f84`
**Профиль:** `multilingual-compact`; reranker `BAAI/bge-reranker-v2-m3-int8`; threshold `0.01`; rerank batch `16`; eval concurrency `4`; LLM `openai/gpt-5-nano`.

## Что сравнивалось

Top-4 — новый полный baseline после исправления распознавания точного отказа. Top-2 — отдельный
полный end-to-end прогон на том же датасете и конфигурации, с изменённым только `rerank_top_k`.
Состав набора: 85 positive (45 synthetic-golden и 40 MIRACL v1.0 dev), 6 no-answer и 41
ACL-negative. Обе конфигурации сохранены в sanitized JSON:

- [Top-4 diagnostics](rag_quality_corrected_classifier_baseline.json)
- [Top-2 diagnostics](rag_quality_corrected_classifier_top2.json)

В JSON не записаны вопросы, ответы, prompts, содержимое документов и passages. Raw Markdown-отчёты
прогона остались во временных контейнерах и удалены вместе с ними.

Прогоны работали против отдельной временной PostgreSQL/pgvector базы с RLS session role. Для
наполнения БД вызовы объектного storage были заглушены в процессе; документы загружались в память
для ingestion, пользовательский S3/MinIO и публичное демо не использовались. Оба eval-контейнера
имели лимит памяти 2.5 GB. Модель reranker исполнялась на CPU.

## Результаты

| Метрика | Top-4 | Top-2 | Изменение Top-2 |
| --- | ---: | ---: | ---: |
| Target document hit | `85/85` (`1.000`) | `84/85` (`0.988`) | `-1` кейс |
| Exact target section hit | `51/52` (`0.981`) | `48/52` (`0.923`) | `-3` кейса |
| Context Precision | `0.952` (`n=85`) | `0.959` (`n=85`) | `+0.007` |
| Faithfulness | `0.974` (`n=76`) | `0.952` (`n=76`) | `-0.022` |
| Citation support | `0.931` (`n=76`) | `0.932` (`n=76`) | `+0.001` |
| English Answer Relevance (pure English slice) | `0.799` (`n=53`) | `0.743` (`n=53`) | `-0.057` |
| Russian Answer Relevance (pure Russian slice) | `0.635` (`n=28`) | `0.591` (`n=28`) | `-0.043` |
| Mixed-script Answer Relevance | `0.369` (`n=4`) | `0.553` (`n=4`) | `+0.184` |
| Среднее число возвращённых chunks | `2.79` | `1.78` | `-0.67` |
| No-answer refusals | `6/6` | `6/6` | без изменений |
| ACL leaks / case errors | `0 / 0` | `0 / 0` | без изменений |

Quality gates Context Precision (`0.975`) и English Answer Relevance (`0.827`) не пройдены ни в
одном запуске. Точный отказ у positive-кейса засчитан только при совпадении со стандартной
локализованной фразой; Top-4 содержит 9 таких ответов, Top-2 — 12 точных и один embedded отказ.
`embedded` не учитывается как точный отказ.

Top-2 улучшил Context Precision всего на `0.007`, при этом потерял одно попадание в документ и
три exact section, а Faithfulness и Answer Relevance снизились. Уменьшение числа контекстов не
сократило этап reranking: для обеих конфигураций нужно оценить все 1,980 candidate pairs. Top-2
rerank занял `1,243.27 s` (`20m43s`) с batch `16`; после reranking Top-K влияет только на число
chunks, передаваемых дальше по pipeline.

## Решение

Оставить production `rerank_top_k=4` и threshold `0.01`. Этот Top-2 прогон не даёт достаточного
выигрыша в точности и ухудшает recall/ответы; он также не улучшает две непройденные quality gates.
Не менять production настройки по итогам этого эксперимента.

Метрики генерации и LLM-судей являются наблюдениями одного запуска: ответы и судейские оценки
могут меняться между повторами. Изменение Top-K — единственное отличие конфигураций, но результаты
не доказывают, что каждое изменение answer metrics вызвано только им. Dataset hash, отсутствие
ошибок и парное сравнение retrieval метрик позволяют считать вывод достаточным для отказа от
Top-2 как default, но не для дальнейшего выбора модели или порога.

**Уточнение языковых агрегатов:** предыдущая версия этого отчёта относила mixed-script кейсы к
EN/RU и показывала неверные размеры языковых выборок. Evaluator bucket-ит языки отдельно по
Unicode script; gate `Answer Relevance (English)` использует только bucket `en` (`n=53`). Точные
агрегаты по `en`, `ru` и `mixed` приведены выше. Диагностические выводы в [case-level analysis](rag_quality_failure_analysis.md).
