# Оценка качества RAG

Evaluation использует golden set и проходит через тот же retrieval/generation path, что и приложение.
Отчёт — снимок конкретного запуска, не обещание качества на новых документах или вопросах.

## Сохранённый historical benchmark

Прогон от **2026-09-22**, 35 кейсов: 28 положительных и 7 ACL-negative. После расширения golden set
текущий набор содержит 41 кейс: 28 положительных и 13 ACL-negative. Для текущих метрик нужно выполнить
новый retrieval-only или полный прогон; сохранённые scores не пересчитываются без запущенного Compose backend.
Текущая embedding-модель `BAAI/bge-small-en-v1.5` English-only, поэтому русскоязычные кейсы добавлять
после выбора multilingual embedding model и корпуса на русском.

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
| `eval/golden_dataset.json` | Вопросы, ожидаемые ответы, документы/страницы и запреты на документы |
| `eval/run_eval.py` | Прогон через retrieval и generation |
| `eval/corpus.py` | Synthetic PDFs со стабильными IDs и ACL tags |
| `eval/seed_demo.py` | Локальный demo corpus: 3 роли и 12 PDF |
| `reports/rag_benchmark.md` | Сохранённые метрики и подробности прогона |

Eval user — `eval-employee@docwise.example.com`, membership `employee`, без отделов. HR/Finance IDs
указаны как `must_not_doc_ids`; роли из request body не принимаются.

## Метрики и обязательные проверки

- **Faithfulness**, **Context Precision**, **Answer Relevance** считаются по определениям Ragas;
  judge использует OpenAI-compatible client. `ragas` и LangChain не нужны runtime-приложению.
- Дополнительные asserts проверяют target page, cross-org isolation и отсутствие запрещённых IDs в Top-4.
- **Ноль ACL leaks** — обязательный gate. Остальные метрики помогают увидеть регрессию и требуют оценки контекста.

## Запуск

```bash
make eval                 # retrieval + generation + LLM judges
make eval-retrieval       # retrieval/ACL без LLM judges
```

Нужны запущенный Compose stack; полному evaluation — LLM key и FastEmbed cache.
`run_eval.py --seed` создаёт тестового пользователя, synthetic corpus и foreign-tenant decoy.
CI unit suite не запускает полный evaluation по умолчанию.

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
