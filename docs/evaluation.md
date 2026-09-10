# Оценка качества (Ragas)

Модуль `eval/` доказывает, что система не наивный RAG: верность контексту, чистота чанков, релевантность ответа.

## Состав

| Артефакт | Назначение |
| --- | --- |
| `eval/golden_dataset.json` | ≥ 30 пар: `question`, `ground_truth_answer`, `target_doc_id` (желательно `target_page`, `must_not_doc_ids` для ACL) |
| `eval/run_eval.py` | Прогон через реальный пайплайн retrieval+generation |
| `eval/corpus.py` | Синтетические PDF со стабильными UUID и тегами `all` / `hr` / `finance` |
| `eval/seed_demo.py` | Локальное демо: employee vs HR и два PDF с разным ACL (`make demo`) |
| `reports/rag_benchmark.md` | Таблица метрик для README |

Синтетический набор допустим на старте; для портфолио лучше 10–15 вопросов по реальным (обезличенным) PDF плюс негативные кейсы.

Golden set гоняется под пользователем `eval-employee@docwise.example.com` (`employee`, `departments=[]`). Роли не берутся из тела запроса. Документы `hr` и `finance` стоят в `must_not_doc_ids` у **каждого** вопроса.

## Метрики

Считаются по определениям Ragas тем же OpenAI-совместимым клиентом, что и чат (`complete_openai` / `stream_openai`). LangChain и пакет `ragas` в рантайм не входят.

1. **Faithfulness** — ответ не выходит за контекст (анти-галлюцинация).
2. **Context Precision** — в Top-K мало мусорных чанков.
3. **Answer Relevance** — ответ по существу закрывает вопрос (косинус эмбеддингов сгенерированных вопросов к исходному).

Дополнительно (свои assert'ы):

- страница найденного чанка совпадает с `target_page` в доле кейсов;
- пользователь-employee не получает чанки из `must_not_doc_ids` (exit code 1 при любой утечке);
- после M5: пользователь org A не получает документы org B (в т.ч. с `access_roles = ['all']`).

## Запуск

```bash
make eval
# или только retrieval + ACL, без LLM-судей:
make eval-retrieval
```

Эквивалент внутри backend-контейнера:

```bash
python /eval/run_eval.py --seed
```

`--seed` создаёт eval-пользователя и прогоняет фикстурные PDF через реальный `index_pdf` (не Celery). Требования: поднятый стек, ключ LLM, кэш FastEmbed. Unit-тесты CI **не** вызывают этот скрипт по умолчанию.

Локальное ACL-демо (employee vs HR, два PDF):

```bash
make demo
```

Скрипт: [eval/seed_demo.py](../eval/seed_demo.py). Пользователи и проход — в корневом [README.md](../README.md).

## Когда гонять

После изменений чанкинга, RRF, порога реранкера, системного промпта или эмбеддингов. В PR — кратко: выросли/упали метрики, не только «добавлен eval».

## Пороги релиза

После первого прогона (2026-09-10, 35 кейсов, employee без `hr`/`finance`):

| Метрика | Порог | Факт |
| --- | ---: | ---: |
| Faithfulness | ≥ 0.8 | 1.000 |
| Context Precision | ориентир ≥ 0.9 | 0.976 |
| Answer Relevance | ориентир, не гейт | 0.789 |
| Target page hit | ориентир | 0.929 |
| ACL `must_not_doc_ids` | **0 утечек** | 0 / PASS |

Вывод: это не наивный RAG. SQL-RBAC до LLM держит корпус: HR/Finance не попали в Top-4. Ответы не выходят за контекст (Faithfulness 1.0). Answer Relevance тянут два позитива (`hb-security-email`, `eng-python`): после порога реранкера 0.25 контекст пустой, модель отказывается — это качество retrieval, не дыра ACL. Таблица: [reports/rag_benchmark.md](../reports/rag_benchmark.md).
