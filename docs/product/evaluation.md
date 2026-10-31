# Оценка качества RAG

Evaluation использует golden set и проходит через тот же retrieval/generation path, что и приложение.
Отчёт — снимок конкретного запуска, не обещание качества на новых документах или вопросах.

## Сохранённый baseline

Полный прогон от **2026-10-30**: retrieval, generation и LLM judges для 69 кейсов (33 positive,
36 ACL-negative), 9 synthetic PDFs и шести evaluator personas. Target document/page hit rate — `1.000`;
Faithfulness — `1.000`, Context Precision — `0.995`, Answer Relevance — `0.847`; ACL leaks и ошибки кейсов — `0`.
Прогон использует исправленный eval RLS context. Безопасные параметры, revision и hash dataset записаны
в [отчёте](../../reports/rag_benchmark.md).

| Метрика | Результат | Интерпретация |
| --- | ---: | --- |
| Target document hit | `1.000 (33/33)` | Для каждого positive кейса найден ожидаемый документ |
| Target page hit | `1.000 (33/33)` | Для каждого positive кейса найдена ожидаемая страница |
| Faithfulness | `1.000` | Оценка опирается на retrieved context |
| Context Precision | `0.995` | В Top-K почти не было лишних chunks |
| Answer Relevance | `0.847` | Насколько ответ адресует вопрос |
| ACL leaks | `0 / 36` | Запрещённый документ не попал в Top-4 |
| Case errors | `0` | Все кейсы завершились и получили валидные judge scores |

Этот baseline использует default `BAAI/bge-small-en-v1.5`. Исторические scores от **2026-09-22** рассчитаны
на 35 кейсах и напрямую с ним не сравниваются.

## Multilingual candidate: 2026-10-30

Изолированный полный прогон добавил синтетический русский DOCX и 17 русскоязычных кейсов. Он использовал
кандидатные `paraphrase-multilingual-MiniLM-L12-v2` и `bge-reranker-v2-m3-int8`; default-приложение на них
не переключено.

| Метрика | Candidate | Результат |
| --- | ---: | --- |
| Target document/page/section hit | `1.000` | Все 45 positive кейсов нашли целевой документ и страницу/секцию |
| Faithfulness / Context Precision | `1.000 / 1.000` | Без ухудшения на этом корпусе |
| Citation support | `0.978` | В одном кейсе judge не связал claim с источником; см. повторную проверку ниже |
| Answer Relevance, English | `0.851` | Выше floor `0.827`; regression gate пройден |
| Answer Relevance, Russian | `0.792` | Показатель добавлен впервые, baseline для сравнения отсутствует |
| ACL leaks / case errors | `0 / 0` | Все 41 ACL-negative прошли |

Повторный полный запуск после уточнения chat prompt дал общий Answer Relevance `0.832`; English regression slice —
`0.851` по 33 вопросам. Target document/page/section hit, Faithfulness и Context Precision остались `1.000`;
case errors и ACL leaks — `0`. Профиль остаётся кандидатом: эти оценки относятся к синтетическому golden set,
а default модели приложения не переключены. Смешанный общий score не используется для regression gate.
Метрики, quality slices, weak cases и конфигурация записаны в [candidate report](../../reports/rag_candidate_multilingual.md).

`hb-personal-devices` теперь имеет Answer Relevance `0.943` против baseline `0.944`; `hb-hybrid-office` — `0.888`
против `0.881`; `hb-desk-booking` остаётся слабым с `0.664` против `0.825`. Дополнение prompt с просьбой сохранять
названные системы и условия подняло повторный targeted замер бронирования до `0.873`, но полный прогон снова дал
`0.664`. Поэтому единичный score этого кейса нестабилен и не доказывает устойчивое улучшение; сам ответ и citation
при этом остались grounded.

В полном запуске `eng-python` получил Citation support `1.000`. Единственный нулевой citation score оказался у
`ru-engineering-first-pr`; отдельный повтор с тем же профилем и русским источником дал `1.000`, а judge указал оба
релевантных источника. Это указывает на вариативность LLM judge/generation; полный отчёт сохраняет исходный
результат `0.978`, а вывод о корректности конкретной цитаты проверяется по тексту источника.

### Historical full generation run: 2026-09-22, 35 cases

| Метрика | Результат | Интерпретация |
| --- | ---: | --- |
| Faithfulness | `1.000` | В положительных кейсах ответ оставался в пределах контекста |
| Context Precision | `0.994` | В Top-K почти не было лишних chunks |
| Answer Relevance | `0.776` | Насколько ответ адресует вопрос |
| Target document hit | `1.000` | Найден ожидаемый документ |
| Target page hit | `1.000` | Найдена ожидаемая страница |
| ACL leaks | `0 / 7` | Ограниченный документ не попал в Top-4 |

Полная таблица по вопросам: [reports/rag_benchmark.md](../../reports/rag_benchmark.md).
Результат относится только к сохранённому dataset, пользователю и версии проекта из отчёта.

## Что входит в evaluation

| Артефакт | Назначение |
| --- | --- |
| `eval/golden_dataset.json` | Вопросы, ожидаемые ответы, целевые страницы/секции и запрещённые документы |
| `eval/run_eval.py` | Прогон через retrieval и generation с фиксированными evaluator personas |
| `eval/concurrency.py` | Ограниченная параллельная обработка независимых generation/judge кейсов |
| `eval/corpus.py` | 9 synthetic PDFs и русский synthetic DOCX со стабильными IDs и ACL tags |
| `eval/seed_demo.py` | Локальный demo corpus: 3 роли и 12 PDF |
| `reports/rag_benchmark.md` | Сохранённые метрики и подробности прогона |
| `reports/rag_candidate_multilingual.md` | Multilingual candidate benchmark, срезы и per-question результаты |
| `eval/prepare_miracl.py` | Загружает закреплённые MIRACL topics/qrels и выбранные Wikipedia passages; eval не запускает |

Текущий синтетический golden set содержит 92 кейса: 45 answerable, 6 `no_answer` и 41 `acl_negative`.
`no_answer` кейс не указывает `target_doc_id` и не участвует в retrieval recall; он измеряет, откажется
ли generation отвечать на вопрос, отсутствующий в корпусе. ACL-negative cases измеряют изоляцию и
остаются отдельным security gate. При сборке MIRACL набора исходные synthetic и ACL cases сохраняются.

Пользователь по умолчанию — `eval-employee@docwise.example.com`, membership `employee`, без отделов.
Для матрицы используются фиксированные синтетические evaluator accounts с подразделениями `hr`, `finance`,
`legal`, `security` и `engineering`; поле `eval_user_email` в кейсе выбирает нужный аккаунт. Каждый кейс
перечисляет недоступные документы в `must_not_doc_ids`; роли из request body не принимаются.

## Метрики и обязательные проверки

- **Faithfulness**, **Context Precision**, **Answer Relevance** считаются по определениям Ragas;
  judge использует OpenAI-compatible client. `ragas` и LangChain не нужны runtime-приложению.
- Answer Relevance использует закреплённый evaluator encoder: исторический BGE для Latin-вопросов и
  multilingual MiniLM для Cyrillic-вопросов. Gate `Answer Relevance (English)` сравним с сохранённым English baseline;
  русский результат остаётся отдельным исследовательским срезом до накопления baseline.
- **Citation support** — для каждого ответа доля factual claims, для которых LLM judge указал хотя бы один
  индексированный retrieved source, напрямую поддерживающий claim; итог усредняется по ответам. Отчёт хранит только
  score, не текст claim или источника.
- Дополнительные asserts проверяют target page, cross-org isolation и отсутствие запрещённых IDs в Top-4
  для каждого evaluator account.
- **Ноль ACL leaks и ноль case errors** — обязательные gates. Пороговые значения качества применяются к средним
  метрикам положительных кейсов; значение на границе проходит.
- `No-answer refusal rate` оценивается только по `no_answer` cases; начальный floor — `0.800`. Он не
  смешивается с answerable recall или ACL leak count. В retrieval-only запуске оценка generation имеет `N/A`.
- Начальные regression floors: target document/page hit `≥ 0.980`, Faithfulness `≥ 0.800`, Context Precision
  `≥ 0.975`, English Answer Relevance `≥ 0.827`. Retrieval floors оставляют запас 0.02 от текущего baseline;
  Context Precision и English Answer Relevance также допускают снижение на 0.02. Faithfulness сохраняет ранее
  установленный минимум `0.800`. Это начальные пороги одного golden set, а не статистические доверительные границы.
- Полный benchmark завершается ошибкой при провале любого applicable gate. Отсутствующий score или пустая
  выборка в полном прогоне считается провалом, а не нулём или успехом. В retrieval-only запуске generation gates
  имеют статус `N/A`. Некорректный JSON от LLM judge повторяется один раз; второй невалидный ответ становится
  case error и проваливает gate.
  В Markdown-отчёт входит только число ошибок, без текста исключений.
- Новый отчёт фиксирует безопасные параметры запуска: IDs embedding/reranker/LLM моделей, Top-K,
  rerank threshold и SHA-256 system prompt. API key и base URL не записываются.
- Метрики положительных кейсов агрегируются по Unicode script bucket (`en`, `ru`, `mixed`, `unknown`),
  evaluator persona, `kind` и `source_dataset`. Языковой bucket описывает письменность вопроса, а не язык ответа.
- Отказ получает Faithfulness `N/A`, а пустая выдача — Context Precision `N/A`; эти случаи не считаются
  идеальными scores. Refusal сохраняет Answer Relevance `0`, а полный отчёт отдельно показывает
  ответы, отказы и positive cases с контекстом; для retrieval-only generation coverage помечается `N/A`.
- Для каждого source slice отчёт содержит target-document hit и точный target-section rank на стадиях dense,
  sparse, RRF, reranker scoring, после порога и после Top-4: Recall@1/4/10 и MRR. Кандидатные пороги reranker
  `0.10–0.30` дополнительно симулируются на том же наборе scores; отчёт показывает coverage и долю пустой выдачи.
  В отчёт попадают только агрегаты; stage snippets, ответы и текст passages не сохраняются.

## Подготовленный real-data candidate: MIRACL

`eval/prepare_miracl.py` формирует локальный набор на основе MIRACL v1.0 dev для English и Russian.
В MIRACL вопросы написаны носителями языка, а passage relevance размечена людьми. Это retrieval dataset,
а не benchmark с эталонными QA-ответами: полный текст единственного релевантного passage используется как
evidence и reference для generation judges. Поэтому генерационные scores следует читать как исследовательскую
оценку grounded ответа, а не как точность относительно вручную написанного ответа.

По умолчанию готовятся 20 вопросов на язык. В выборку входят вопросы с одной положительной qrel-меткой и
минимум двумя judged-negative passages; в корпус берутся positive passage и до трёх отрицательных passages.
Для ограничения скачивания используется Wikipedia page ID не выше 500,000 и стабильный hash sample. Низкие
page ID чаще относятся к ранним страницам Wikipedia, поэтому подвыборка смещена по возрасту/популярности страниц
и не является репрезентативной выборкой всей Wikipedia или внутренних документов компаний. Это небольшая
проверка переноса retrieval на реальный текст, а не замена синтетических ACL/cross-tenant кейсов.

Источник закреплён на MIRACL topics/qrels revision `5be20db` и corpus revision
`a7362f0b9d54dce8a8af3cd42a8cf2a5ef570475`. MIRACL dataset metadata опубликованы под Apache-2.0;
исследовательская статья MIRACL — CC BY 4.0. Wikipedia passage text распространяется по CC BY-SA 4.0
(для некоторых материалов также применим GFDL). DOCX сохраняют текст passage, добавляют заголовки с MIRACL
docid и метаданные attribution/source. Перед внешним распространением prepared files нужно сохранить
атрибуцию и соблюдать ShareAlike для производных материалов.

Подготовка сохраняет исходные TSV, DOCX, hashes и provenance в `eval/local_data/miracl/`; этот каталог
исключён из Git, так как содержит сторонний текст. Для пересборки используется:

```bash
backend/.venv/bin/python eval/prepare_miracl.py
```

Подготовленный corpus включается в eval только при явном запуске с `--seed --external-corpus` и
`--dataset eval/local_data/miracl/golden_dataset.json`. Подготовка сама не индексирует документы, не вызывает
LLM и не запускает evaluation. Итоговый dataset содержит прежние синтетические/ACL кейсы плюс 40 MIRACL
positive cases. В отчёте их можно отделить по срезу `source_dataset`.

### Первый полный прогон: 2026-10-30

Полный run на `multilingual-compact` завершился без case errors и ACL leaks, но regression gates не пройдены:
на всей выборке document hit `0.953` (floor `0.980`), Context Precision `0.929` (floor `0.975`) и English
Answer Relevance `0.757` (floor `0.827`). Срез MIRACL (40 вопросов): Target document hit `0.900`, section hit `0.800`, Faithfulness `0.950`,
Context Precision `0.850`, Answer Relevance `0.491`, Citation support `0.817`. Для синтетических positive кейсов
этого же запуска document/section hit, Faithfulness и Context Precision остались `1.000`; English Answer Relevance
составил `0.809`. На этой небольшой выборке заметно падение retrieval precision и answer relevance на real-text
срезе относительно synthetic fixtures; это направление для анализа, а не оценка всей Wikipedia или внутренних
корпусов. Не переключайте production profile по этому candidate.

Полные метрики и промахи по отдельным вопросам: [MIRACL candidate report](../../reports/rag_miracl_candidate.md).
Report указывает `HEAD` revision; рабочее дерево во время запуска было изменено, поэтому revision не является
полным идентификатором исполнявшегося кода. Этот generation report предшествует исправлению метрик отказа и пустого
контекста 2026-10-31; Faithfulness и Context Precision могут быть завышены. Текущий retrieval stage snapshot:
[MIRACL stage diagnostic](../../reports/rag_miracl_stage_diagnostic.md). Для обновлённых generation aggregates нужен
полный повтор judges.

В stage snapshot на тех же 40 MIRACL запросах target-document coverage был `1.000` после RRF и reranker scoring,
затем `0.900` после порога `0.25`; positive-section Recall@4 снизился с `0.975` до `0.800`. Симуляция порогов
показала для `0.10` document hit `0.925`, section Recall@4 `0.850` и empty rate `0.050`. Это диагностический
сигнал в пользу дальнейшего эксперимента с threshold, но retrieval gates остаются ниже цели; production threshold
не изменён.

### Generation candidate с threshold `0.10`: 2026-10-31

Отдельный запуск тех же 40 MIRACL positive cases с генерацией и judges зарегистрировал один case error: запрос
`miracl-en-2085` завершился ошибкой после provider timeout во время judge-оценки. Ошибка не содержит сохранённого
текста исключения. В отчёте: ответы — `25/40`, отказы — `15/40`, контекст — `38/40`; ACL leaks — `0`, но
ACL-negative cases в этом запуске отсутствуют. Для ошибочного кейса unavailable judge scores исключены из их `n`.

| Метрика | Candidate `0.10` | Regression floor |
| --- | ---: | ---: |
| Target document / section hit | `0.925 / 0.850` | `0.980 / —` |
| Faithfulness | `1.000` (`n=24`) | `0.800` |
| Context Precision | `0.882` (`n=37`) | `0.975` |
| Answer Relevance, English | `0.507` (`n=20`) | `0.827` |
| Answer Relevance, all languages | `0.481` (`n=39`) | — |
| Citation support | `0.913` (`n=24`) | — |

Target-page gate имеет статус `N/A`: у MIRACL нет page labels. Threshold `0.10` поднял section Recall@4 с `0.800`
в старом `0.25` запуске до `0.850`, но target document hit остался ниже floor, Context Precision и Answer Relevance
не прошли gates, а высокий refusal rate требует отдельного анализа. Это не основание менять production threshold:
сравнение ограничено 40 вопросами и одним run, есть case error, и данные не включают ACL-negative cases.
Подробная таблица по вопросам и стадиям: [generation report](../../reports/rag_miracl_threshold_010.md).

### Concurrent full rerun: 2026-10-31

Повтор тех же 40 MIRACL cases с concurrency `4` завершился за `17m 54s` wall time; в это входят seeding,
последовательный retrieval, generation, judges и пакетные embeddings. Case errors — `0`, ACL leaks — `0/0`
(ACL-negative cases по-прежнему не запускались), rate-limit ошибок не было. Метрики: Faithfulness `0.960 (n=25)`,
Context Precision `0.886 (n=38)`, Answer Relevance English `0.514 (n=20)`, общий Answer Relevance `0.480 (n=40)`,
citation support `1.000 (n=25)`, target document/section hit `0.925 / 0.850`; 15 из 40 ответов — отказы.
Quality gates по target document hit, Context Precision и English Answer Relevance не пройдены; page gate — `N/A`.

Это подтверждает корректную работу concurrency на полном наборе, но не является контролируемым сравнением скорости:
предыдущий последовательный run завершился примерно за полчаса и имел один timeout, поэтому времена и judge scores
могли измениться из-за сети и вариативности модели. По логам нового прогона около 12 минут ушло до начала
generation/judges; следующий bottleneck — последовательные retrieval и cross-encoder calls. Подробности:
[concurrent report](../../reports/rag_miracl_threshold_010_concurrent.md).

## Запуск

```bash
make eval                                      # retrieval + generation + judges, до 4 кейсов одновременно
make eval EVAL_CONCURRENCY=2                  # снизить параллельность generation/judges
make eval-retrieval                           # retrieval/ACL без LLM judges
make eval-retrieval EVAL_EMBEDDING_BATCH_SIZE=16 # ограничить размер batch query embeddings
make eval-retrieval EVAL_RERANK_BATCH_SIZE=32     # ограничить размер batch query/document pairs
```

Нужны запущенный Compose stack; полному evaluation — LLM key и FastEmbed cache.
Query embeddings считаются до открытия DB-сессии; default batch size — `1`, поскольку на фиксированном 30-case срезе batch `32` не ускорил прогон.
Каждый retrieval по-прежнему отдельно привязывает RLS-контекст и получает tenant/ACL из resolved principal.
После закрытия per-case DB-сессий разрешённые пары query/document передаются cross-encoder пакетами; default — `64` пар.
Пары сортируются по оценочной длине до пакетирования, а затем scores возвращаются в исходный порядок; в одном сопоставимом прогоне rerank стал быстрее на `3.7%`, весь прогон — на `1.6%`, с теми же retrieval метриками. Это небольшой предварительный выигрыш, который нужно сверить на полном benchmark. Benchmark report содержит агрегированное время query embedding, DB search и rerank без текста запросов и passages.
`run_eval.py --seed` создаёт шесть тестовых evaluator personas, synthetic corpus и foreign-tenant decoy.
Retrieval выполняется последовательно; после него до четырёх независимых кейсов одновременно проходят generation
и judges через существующий HTTP-клиент. Answer Relevance embeddings считаются следующими пакетно: по языковому профилю,
до 128 текстов на вызов encoder. Отчёт сохраняет исходный порядок dataset, а лог показывает завершение каждого
кейса. Для прямого запуска доступны `--concurrency N` и `EVAL_CONCURRENCY=N`; значение должно быть положительным.
Если API отвечает `429` или часто даёт timeout, уменьшите concurrency до `2` или `1`.
Первые 8 MIRACL кейсов прошли без case errors за `263.26s`, включая повторную индексацию и холодный старт;
затем тот же concurrency path был проверен на всех 40 кейсах выше. Эти значения не являются чистым замером
ускорения ([8-case smoke report](../../reports/rag_miracl_concurrency_smoke.md)).
CI unit suite не запускает полный evaluation по умолчанию. Benchmark запускайте с отдельной базой и
volume; не подключайте его к базе публичного демо или документам пользователей.

Запуск подготовленного MIRACL candidate требует отдельного решения о старте:

```bash
python eval/run_eval.py --seed \
  --model-profile multilingual-compact \
  --dataset eval/local_data/miracl/golden_dataset.json \
  --external-corpus eval/local_data/miracl/manifest.json
```

Для локального ACL walkthrough:

```bash
make demo
```

## Когда запускать

Повторяйте evaluation после изменения chunking, embeddings, FTS, RRF, rerank threshold, system prompt,
refusal wording или ACL. PR должен коротко фиксировать изменение ключевых метрик и любой ACL leak.

| Изменение | Проверка | Когда обновить отчёт |
| --- | --- | --- |
| Retrieval без prompt | `make eval-retrieval` | Если изменился page hit или ACL |
| FTS/RRF/rerank/chunking/embeddings | `make eval` | При заметном движении метрик (≥ 0.02) или ACL leak |
| Prompt/refusal/длина ответа | `make eval` | Сравнить faithfulness и answer relevance по вопросам |

Release thresholds и optional CI workflow: [`eval.yml`](../../.github/workflows/eval.yml).
