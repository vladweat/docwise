# План масштабного улучшения RAG

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

### Задача 1 — parity отказов

**Изменяем:** `backend/app/services/chat/prompt.py`, `eval/run_eval.py`, `eval/metrics.py`.
**Проверяем:** `backend/tests/test_chat.py`, `backend/tests/test_eval_reporting.py`,
`backend/tests/test_rag_multilingual.py`.

- [ ] Тесты: prompt задаёт локализованный стандартный отказ, не конфликтующий с языком пользователя;
  английский и русский отказ определяются evaluator-ом, включая текст с вводной фразой.
- [ ] Тесты: пустой retrieval в eval возвращает ровно тот ответ, который вернул бы production.
- [ ] Прогнать целевые тестовые модули, затем полный backend suite.
- [ ] Пересчитать полный benchmark и сохранить отчёт с новой provenance.
- [ ] Commit: `fix: align localized RAG refusals in chat and eval`.

### Задача 2 — валидные answerability и ACL slices

**Изменяем:** `eval/dataset.py`, `eval/run_eval.py`, `eval/reporting.py`,
`eval/quality_gates.py`, `eval/golden_dataset.json`, `backend/tests/test_eval_golden_dataset.py`,
`backend/tests/test_eval_reporting.py`.

- [ ] Добавить отдельный `no_answer` kind с вопросами, на которые корпус не содержит ответа;
  сохранить существующий `acl_negative` и требования к UUID для answerable cases.
- [ ] Тесты: parser валидирует `no_answer`, отчёт отдельно считает правильные отказы, ложные ответы,
  ACL утечки и answerable recall.
- [ ] Объединённый полный dataset включает synthetic ACL matrix и real MIRACL cases; отчёт показывает
  разрезы по `source_dataset`, языку и kind.
- [ ] Не писать в report ответы, passages или restricted chunk text.
- [ ] Прогнать dataset/report tests и полный retrieval-only suite; сохранить report.
- [ ] Commit: `eval: add no-answer cases and separate retrieval coverage gates`.

### Задача 3 — измеренное улучшение retrieval и generation

**Изменяем только после benchmark из задач 1–2:** `backend/app/services/retrieval/`,
`backend/app/services/ingestion/embedding_profiles.py`, `backend/app/services/chat/prompt.py`,
`eval/quality_gates.py` и соответствующие тесты.

- [ ] Сначала сохранить полный baseline report на том же combined dataset и активном профиле.
- [ ] Сравнить candidate profiles и пороги `0.10–0.30` на одинаковом наборе, включая positive,
  no-answer и ACL-negative cases.
- [ ] До production-изменения добавить regression test на каждый выявленный слабый сценарий.
- [ ] Выбирать candidate только по совместным gates: retrieval hit, Context Precision, Answer
  Relevance, правильные отказы, Faithfulness, citations и ACL leaks.
- [ ] Сохранить baseline/candidate отчёты; commit отдельным сообщением для каждого подтверждённого
  product change. Если ни один candidate не проходит gates, не менять runtime defaults и записать
  конкретный вывод в отчёт.

### Задача 4 — ускорение eval без async-перехода

**Изменяем при наличии профиля длительности:** `eval/run_eval.py`, `eval/concurrency.py`,
`backend/app/services/retrieval/__init__.py`, `backend/app/services/retrieval/search.py` и тесты.

- [ ] Измерить отдельное время seeding, embedding, DB search, rerank, generation и judges на одном
  полном прогоне.
- [ ] Если query embedding занимает заметную часть времени, сначала добавить пакетное embedding API
  и тест порядка результатов; затем передавать заранее вычисленный вектор в retrieval без повторного
  embedding.
- [ ] Если DB/retrieval остаётся узким местом, ограниченно распараллелить независимые кейсы с отдельной
  `SessionLocal`, `bind_session_rls` и сохранением входного порядка результатов.
- [ ] Проверить то же качество/ACL gates и замерить wall time, peak memory и CPU; не повышать
  concurrency выше того, что выдерживает VPS.
- [ ] Commit: `perf: batch eval query embeddings` и отдельный commit для retrieval concurrency,
  только если каждый шаг измеримо ускоряет полный прогон.

### Задача 5 — итоговая проверка и отчётность

- [ ] Запустить `make lint`, `make test-smoke`, `make test`, `make typecheck`, `make test-frontend`;
  команды, требующие compose, запускать только при доступной инфраструктуре и достаточных ресурсах.
- [ ] Запустить полный RAG eval и приложить dataset hash, revision и итоговые gates.
- [ ] Проверить ACL границы, diff и документацию; не пушить и не разворачивать демо без отдельного запроса.
- [ ] Финальный review изменений и список отложенных проблем.

## Ограничения

- Не менять ORM-модели без Alembic-миграции.
- В retrieval dense и FTS должны фильтроваться по `organization_id` и `access_roles` до RRF,
  reranker и LLM.
- `organization_id` берётся только из authenticated session/trusted DB; не считать RLS защитой,
  если runtime использует superuser без `DOCWISE_RLS_SESSION_ROLE`.
- Не передавать restricted chunk text в prompt, cache, audit, logs или errors.
- При изменении ingestion-кода перезапустить `celery-worker`.

