# Замер качества RAG

Создано: `2026-10-31T06:27:57+00:00`
Общее время команды: `1074.35s` (17 мин 54 с; включает подготовку данных, поиск, генерацию, оценки судей и пакетное построение векторных представлений)
Ревизия кода: `working-tree`
SHA-256 эталонного набора данных: `1ae3a808fba2d2d33968dd4bc4d5a175059c427138f67152411496d08e71f3de`
Параметры запуска (только безопасные поля):
- `answer_relevance_encoders`: `Latin=BAAI/bge-small-en-v1.5; Cyrillic=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `dense_top_k`: `25`
- `embedding_max_input_tokens`: `128`
- `embedding_model`: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `embedding_profile`: `multilingual-compact`
- `eval_chunk_max_tokens`: `80`
- `eval_concurrency`: `4`
- `eval_limit`: `0`
- `llm_model`: `openai/gpt-5-nano`
- `rerank_threshold`: `0.1`
- `rerank_top_k`: `4`
- `reranker_model`: `BAAI/bge-reranker-v2-m3-int8`
- `reranker_size_gb_estimate`: `0.57`
- `rrf_k`: `60`
- `rrf_top_k`: `15`
- `sparse_top_k`: `25`
- `system_prompt_sha256`: `481a5c41865174724c7abb196eb8669bf3c2e3e0a9e87ada043bb956c65a91bd`
Роли оценки: `employee`, `hr`, `finance`, `legal`, `security`, `engineering`
Случаи: 40 (40 `positive`, 0 `ACL-negative`)
Ошибки случаев: 0
Конвейер: гибридный `retrieve` → Top-4 → `build_messages` + `stream_openai` (поиск + генерация + оценки Ragas)

Метрики «верность контексту» (`Faithfulness`), «точность контекста» (`Context Precision`) и «релевантность ответа» (`Answer Relevance`) рассчитываются по определениям Ragas через тот же клиент, совместимый с OpenAI, что и чат. Для расчёта релевантности ответа (`Answer Relevance`) используется фиксированный кодировщик для каждой письменности: исторический BGE для вопросов латиницей и мультиязычная модель MiniLM для кириллицы; критерий регрессии применим только к английскому срезу. `LangChain` не используется.

## Ragas (положительные случаи)

| Метрика | Оценка | n |
| --- | ---: | ---: |
| Верность контексту (`Faithfulness`) | 0.960 | 25 |
| Точность контекста (`Context Precision`) | 0.886 | 38 |
| Релевантность ответа (`Answer Relevance`) | 0.480 | 40 |
| Поддержка цитатами (`Citation support`) | 1.000 | 25 |

## Покрытие ответов

| Метрика | Значение |
| --- | ---: |
| Ответы | 25 / 40 |
| Отказы | 15 / 40 |
| Случаи с контекстом | 38 / 40 |

## Поиск

| Метрика | Оценка | n |
| --- | ---: | ---: |
| Доля попаданий в целевой документ (`Target document hit rate`) | 0.925 | 40 |
| Доля попаданий на целевую страницу (`Target page hit rate`) | n/a | 0 |
| Доля попаданий в целевой раздел (`Target section hit rate`) | 0.850 | 40 |

## Диагностика этапов поиска

Списки на этапах оцениваются только по наличию и рангу целевого фрагмента; выдержки, ответы и текст фрагментов не выводятся.

### MIRACL v1.0 dev

| Этап | Случаи | Случаи с разделом | Попадание в целевой документ | Полнота поиска точного раздела на ранге 1 (`Recall@1`) | Полнота поиска (`Recall@4`) | Полнота поиска (`Recall@10`) | Средний обратный ранг (`MRR`) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dense | 40 | 40 | 1.000 | 0.400 | 0.800 | 0.950 | 0.592 |
| sparse | 40 | 40 | 0.925 | 0.325 | 0.750 | 0.825 | 0.483 |
| rrf | 40 | 40 | 1.000 | 0.450 | 0.800 | 0.925 | 0.595 |
| rerank_scored | 40 | 40 | 1.000 | 0.725 | 0.975 | 0.975 | 0.838 |
| rerank_thresholded | 40 | 40 | 0.925 | 0.675 | 0.850 | 0.850 | 0.762 |
| reranked | 40 | 40 | 0.925 | 0.675 | 0.850 | 0.850 | 0.762 |

Симуляция порогов по тем же оценкам повторного ранжирования (без дополнительного инференса):

| Порог | Попадание в целевой документ | Полнота поиска раздела на ранге 1 (`Recall@1`) | Полнота поиска раздела на рангах до 4 (`Recall@4`) | Средний обратный ранг раздела (`MRR`) | Среднее число результатов | Доля пустой выдачи |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.10 | 0.925 | 0.675 | 0.850 | 0.762 | 2.425 | 0.050 |
| 0.15 | 0.900 | 0.675 | 0.825 | 0.750 | 2.250 | 0.050 |
| 0.20 | 0.900 | 0.675 | 0.825 | 0.750 | 2.150 | 0.050 |
| 0.25 | 0.900 | 0.675 | 0.800 | 0.738 | 1.975 | 0.050 |
| 0.30 | 0.900 | 0.675 | 0.800 | 0.738 | 1.925 | 0.075 |

## Критерии качества

Начальные пороги регрессии заданы по полному запуску от 2026-10-30; это не статистические доверительные границы.

| Критерий качества | Результат | Порог | Статус |
| --- | ---: | ---: | --- |
| Утечки ACL | 0 | = 0 | PASS |
| Ошибки случаев | 0 | = 0 | PASS |
| Доля попаданий в целевой документ (`Target document hit rate`) | 0.925 | >= 0.980 | FAIL |
| Доля попаданий на целевую страницу (`Target page hit rate`) | n/a | n/a | N/A |
| Верность контексту (`Faithfulness`) | 0.960 | >= 0.800 | PASS |
| Точность контекста (`Context Precision`) | 0.886 | >= 0.975 | FAIL |
| Релевантность ответа на английском языке (`Answer Relevance (English)`) | 0.514 | >= 0.827 | FAIL |



## Срезы качества (положительные случаи)

### По языку

| Группа | Случаи | Попадание в документ | Попадание на страницу | Попадание в раздел | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Поддержка цитатами (`Citation support`) | Ошибки |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| en | 20 | 0.950 | n/a | 0.900 | 1.000 | 0.939 | 0.514 | 1.000 | 0 |
| mixed | 2 | 1.000 | n/a | 1.000 | n/a | 0.750 | 0.000 | n/a | 0 |
| ru | 18 | 0.889 | n/a | 0.778 | 0.917 | 0.843 | 0.496 | 1.000 | 0 |

### По роли

| Группа | Случаи | Попадание в документ | Попадание на страницу | Попадание в раздел | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Поддержка цитатами (`Citation support`) | Ошибки |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| eval-employee@docwise.example.com | 40 | 0.925 | n/a | 0.850 | 0.960 | 0.886 | 0.480 | 1.000 | 0 |

### По типу случая

| Группа | Случаи | Попадание в документ | Попадание на страницу | Попадание в раздел | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Поддержка цитатами (`Citation support`) | Ошибки |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| positive | 40 | 0.925 | n/a | 0.850 | 0.960 | 0.886 | 0.480 | 1.000 | 0 |

### По `source_dataset`

| Группа | Случаи | Попадание в документ | Попадание на страницу | Попадание в раздел | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Поддержка цитатами (`Citation support`) | Ошибки |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MIRACL v1.0 dev | 40 | 0.925 | n/a | 0.850 | 0.960 | 0.886 | 0.480 | 1.000 | 0 |

## Отрицательные случаи ACL

| Метрика | Значение |
| --- | --- |
| Случаи | 0 |
| Случаи с утечкой `must_not_doc_ids` | **0** |
| Результат | PASS |

Для каждого случая в `must_not_doc_ids` перечислены документы, недоступные этой роли. Утечкой считается любой фрагмент Top-4 из этих документов. Текст ограниченных фрагментов здесь не сохраняется.

## По вопросам

| `id` | `persona` | `kind` | Целевой документ | Попадание на страницу | Попадание в раздел | Утечка ACL | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Поддержка цитатами (`Citation support`) | Вопрос |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| miracl-en-224 | eval-employee@docwise.example.com | positive | fba2106d | n/a | hit | 0 | 1.000 | 1.000 | 0.922 | 1.000 | When was Tylenol introduced? |
| miracl-en-1489 | eval-employee@docwise.example.com | positive | ac6f6dea | n/a | hit | 0 | n/a | 1.000 | 0.000 | n/a | How long is the optic nerve? |
| miracl-en-1713 | eval-employee@docwise.example.com | positive | 53a92549 | n/a | hit | 0 | 1.000 | 1.000 | 0.815 | 1.000 | How well did Descent: FreeSpace – The Great War sale? |
| miracl-en-2284 | eval-employee@docwise.example.com | positive | 71a4d4b4 | n/a | hit | 0 | 1.000 | 1.000 | 0.784 | 1.000 | What is the magnetic force of the Earth? |
| miracl-en-2493 | eval-employee@docwise.example.com | positive | 8cc2510e | n/a | hit | 0 | 1.000 | 1.000 | 0.591 | 1.000 | Where did Richard Siegmund Lindzen study physics? |
| miracl-en-2679 | eval-employee@docwise.example.com | positive | 8ea60221 | n/a | miss | 0 | 1.000 | 1.000 | 0.855 | 1.000 | Does melioidosis affect humans? |
| miracl-en-1236 | eval-employee@docwise.example.com | positive | c6fee24c | n/a | hit | 0 | 1.000 | 1.000 | 0.568 | 1.000 | How big was the SS Great Eastern? |
| miracl-en-2085 | eval-employee@docwise.example.com | positive | 667e06ce | n/a | hit | 0 | 1.000 | 1.000 | 0.807 | 1.000 | When was Marin Heidegger born? |
| miracl-en-2959 | eval-employee@docwise.example.com | positive | 274bfb35 | n/a | hit | 0 | 1.000 | 1.000 | 0.873 | 1.000 | What is the population of Burntisland, Scotland? |
| miracl-en-495 | eval-employee@docwise.example.com | positive | 3de66a4c | n/a | hit | 0 | 1.000 | 1.000 | 0.677 | 1.000 | When did Wilton Norman Chamberlain die? |
| miracl-en-1063 | eval-employee@docwise.example.com | positive | 1560bcf0 | n/a | hit | 0 | 1.000 | 1.000 | 0.882 | 1.000 | What is the life expectancy of a horse? |
| miracl-en-3809 | eval-employee@docwise.example.com | positive | c1f83d0b | n/a | hit | 0 | n/a | 0.500 | 0.000 | n/a | How much dopamine is in the human brain? |
| miracl-en-277 | eval-employee@docwise.example.com | positive | bb6b260a | n/a | hit | 0 | n/a | 0.500 | 0.000 | n/a | What was the fastest fighter plane used by the U.S. in World War II? |
| miracl-en-3459 | eval-employee@docwise.example.com | positive | e4d05754 | n/a | hit | 0 | 1.000 | 1.000 | 0.795 | 1.000 | Where was Donald Malcolm Campbell born? |
| miracl-en-2204 | eval-employee@docwise.example.com | positive | 2167a945 | n/a | miss | 0 | n/a | n/a | 0.000 | n/a | Is Windows XP abandonware? |
| miracl-en-2195 | eval-employee@docwise.example.com | positive | 9400c840 | n/a | hit | 0 | 1.000 | 0.833 | 0.848 | 1.000 | Did Catalonia do trade with France? |
| miracl-en-4081 | eval-employee@docwise.example.com | positive | 4fd037dd | n/a | hit | 0 | n/a | 1.000 | 0.000 | n/a | What's the current population of Demopolis? |
| miracl-en-2546 | eval-employee@docwise.example.com | positive | 9ac309b2 | n/a | hit | 0 | n/a | 1.000 | 0.000 | n/a | When was the first safety pin developed? |
| miracl-en-1680 | eval-employee@docwise.example.com | positive | 0c2d61ef | n/a | hit | 0 | 1.000 | 1.000 | 0.868 | 1.000 | How many types of calendars are there? |
| miracl-en-365 | eval-employee@docwise.example.com | positive | 8f3fe743 | n/a | hit | 0 | n/a | 1.000 | 0.000 | n/a | How many copies did Salem's Lot sell? |
| miracl-ru-107 | eval-employee@docwise.example.com | positive | eb2cd183 | n/a | hit | 0 | 1.000 | 1.000 | 0.791 | 1.000 | Когда умер Ли Ха́рви О́свальд? |
| miracl-ru-2468 | eval-employee@docwise.example.com | positive | fb0a2618 | n/a | miss | 0 | n/a | n/a | 0.000 | n/a | Где был открыт памятник Бро́нзовый солда́т? |
| miracl-ru-1045 | eval-employee@docwise.example.com | positive | 03d061ce | n/a | hit | 0 | 1.000 | 1.000 | 0.648 | 1.000 | Болеют псориазом животные? |
| miracl-ru-3483 | eval-employee@docwise.example.com | positive | aba5a6c7 | n/a | hit | 0 | n/a | 1.000 | 0.000 | n/a | Где был первый концерт группы Judas Priest? |
| miracl-ru-5642 | eval-employee@docwise.example.com | positive | 22cde90e | n/a | hit | 0 | 1.000 | 1.000 | 0.530 | 1.000 | Когда появился первый глобус? |
| miracl-ru-6661 | eval-employee@docwise.example.com | positive | 32344e13 | n/a | hit | 0 | 1.000 | 1.000 | 0.614 | 1.000 | Как назывался Петербу́ргский метрополите́н до 1992 года? |
| miracl-ru-1914 | eval-employee@docwise.example.com | positive | 6f0ce79e | n/a | hit | 0 | 1.000 | 1.000 | 0.871 | 1.000 | Па́вел Ива́нович Ме́льников имел при жизни высокий литературный статус? |
| miracl-ru-3340 | eval-employee@docwise.example.com | positive | cc145e66 | n/a | hit | 0 | n/a | 1.000 | 0.000 | n/a | Где был построен первый зоопарк в мире? |
| miracl-ru-23 | eval-employee@docwise.example.com | positive | d0a54089 | n/a | hit | 0 | 1.000 | 1.000 | 0.840 | 1.000 | Когда в Китае начали есть палочками? |
| miracl-ru-4559 | eval-employee@docwise.example.com | positive | d3148829 | n/a | hit | 0 | 1.000 | 0.500 | 0.889 | 1.000 | Сколько воинов участвовало в Полтавской битве на стороне России? |
| miracl-ru-223 | eval-employee@docwise.example.com | positive | 619b4afe | n/a | miss | 0 | n/a | 1.000 | 0.000 | n/a | Что открыл  Ру́аль Э́нгельбрегт Гра́внинг А́мундсен? |
| miracl-ru-1086 | eval-employee@docwise.example.com | positive | b2108655 | n/a | miss | 0 | n/a | 0.000 | 0.000 | n/a | Смогли ли предотвратить взрыв при аварии на АЭС Три-Майл-Айленд? |
| miracl-ru-5857 | eval-employee@docwise.example.com | positive | ab553789 | n/a | hit | 0 | n/a | 0.500 | 0.000 | n/a | Сколько стран принимало участие в XXIX летних Олимпийских игрх? |
| miracl-ru-1808 | eval-employee@docwise.example.com | positive | 38544ff7 | n/a | hit | 0 | 1.000 | 1.000 | 0.787 | 1.000 | БА-64 использовался в Корейской войне? |
| miracl-ru-920 | eval-employee@docwise.example.com | positive | d5c64df4 | n/a | hit | 0 | 0.000 | 1.000 | 0.764 | 1.000 | Сколько лет Лев Николаевич Толстой писал роман «Война́ и мир»? |
| miracl-ru-4489 | eval-employee@docwise.example.com | positive | 5262af1e | n/a | miss | 0 | n/a | 0.000 | 0.000 | n/a | Какая максимальная скорость ЭР2? |
| miracl-ru-4783 | eval-employee@docwise.example.com | positive | 9ef54d1a | n/a | hit | 0 | 1.000 | 0.833 | 0.870 | 1.000 | Когда была основана Печерская Лавра в Киеве? |
| miracl-ru-4149 | eval-employee@docwise.example.com | positive | 00a3f618 | n/a | hit | 0 | 1.000 | 1.000 | 0.381 | 1.000 | Где учился Никола́й Семёнович Леско́в? |
| miracl-ru-168 | eval-employee@docwise.example.com | positive | ac2a7608 | n/a | hit | 0 | n/a | 1.000 | 0.000 | n/a | Кто первым в мире совершил Ка́минг-а́ут? |
| miracl-ru-643 | eval-employee@docwise.example.com | positive | 8dd4eb0e | n/a | hit | 0 | 1.000 | 1.000 | 0.941 | 1.000 | Когда в Германии отменили смертную казнь? |
