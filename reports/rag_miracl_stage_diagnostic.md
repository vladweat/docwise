# RAG benchmark

Generated: `2026-10-31T04:20:10+00:00`
Code revision: `working-tree`
Golden dataset SHA-256: `1ae3a808fba2d2d33968dd4bc4d5a175059c427138f67152411496d08e71f3de`
Run configuration (safe fields only):
- `answer_relevance_encoders`: `Latin=BAAI/bge-small-en-v1.5; Cyrillic=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `dense_top_k`: `25`
- `embedding_max_input_tokens`: `128`
- `embedding_model`: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `embedding_profile`: `multilingual-compact`
- `eval_chunk_max_tokens`: `80`
- `llm_model`: `openai/gpt-5-nano`
- `rerank_threshold`: `0.25`
- `rerank_top_k`: `4`
- `reranker_model`: `BAAI/bge-reranker-v2-m3-int8`
- `reranker_size_gb_estimate`: `0.57`
- `rrf_k`: `60`
- `rrf_top_k`: `15`
- `sparse_top_k`: `25`
- `system_prompt_sha256`: `481a5c41865174724c7abb196eb8669bf3c2e3e0a9e87ada043bb956c65a91bd`
Eval personas: `employee`, `hr`, `finance`, `legal`, `security`, `engineering`
Cases: 40 (40 positive, 0 ACL-negative)
Case errors: 0
Pipeline: hybrid `retrieve` → Top-4 → `build_messages` + `stream_openai` (retrieval-only (Ragas judges skipped))

Metrics follow Ragas definitions (Faithfulness, Context Precision, Answer Relevance) using the same OpenAI-compatible client as chat. Answer Relevance uses a fixed encoder per script: the historical BGE encoder for Latin questions and multilingual MiniLM for Cyrillic questions; the regression gate uses only the English slice. LangChain is not used.

## Ragas (positive cases)

| Metric | Score | n |
| --- | ---: | ---: |
| Faithfulness | n/a | 0 |
| Context Precision | n/a | 0 |
| Answer Relevance | n/a | 0 |
| Citation support | n/a | 0 |

## Response coverage

| Metric | Value |
| --- | ---: |
| Answers | n/a (retrieval-only) |
| Refusals | n/a (retrieval-only) |
| Cases with context | n/a (retrieval-only) |

## Retrieval

| Metric | Score | n |
| --- | ---: | ---: |
| Target document hit rate | 0.900 | 40 |
| Target page hit rate | n/a | 0 |
| Target section hit rate | 0.800 | 40 |

## Retrieval stage diagnostics

Stage lists are evaluated only for target presence/rank; snippets, answers, and passage text are not emitted.

### MIRACL v1.0 dev

| Stage | Cases | Section cases | Target doc hit | Exact section Recall@1 | Recall@4 | Recall@10 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dense | 40 | 40 | 1.000 | 0.400 | 0.800 | 0.950 | 0.592 |
| sparse | 40 | 40 | 0.925 | 0.325 | 0.750 | 0.825 | 0.493 |
| rrf | 40 | 40 | 1.000 | 0.450 | 0.800 | 0.925 | 0.593 |
| rerank_scored | 40 | 40 | 1.000 | 0.750 | 0.975 | 0.975 | 0.846 |
| rerank_thresholded | 40 | 40 | 0.900 | 0.700 | 0.800 | 0.800 | 0.750 |
| reranked | 40 | 40 | 0.900 | 0.700 | 0.800 | 0.800 | 0.750 |

Threshold simulation from the same reranker scores (no extra inference):

| Threshold | Target doc hit | Section Recall@1 | Section Recall@4 | Section MRR | Mean returned | Empty rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.10 | 0.925 | 0.700 | 0.850 | 0.775 | 2.425 | 0.050 |
| 0.15 | 0.900 | 0.700 | 0.800 | 0.750 | 2.175 | 0.050 |
| 0.20 | 0.900 | 0.700 | 0.800 | 0.750 | 2.075 | 0.050 |
| 0.25 | 0.900 | 0.700 | 0.800 | 0.750 | 1.950 | 0.050 |
| 0.30 | 0.900 | 0.700 | 0.800 | 0.750 | 1.925 | 0.075 |

## Quality gates

Initial regression floors are based on the full run dated 2026-10-30; they are not statistical confidence bounds.

| Gate | Observed | Threshold | Status |
| --- | ---: | ---: | --- |
| ACL leaks | 0 | = 0 | PASS |
| Case errors | 0 | = 0 | PASS |
| Target document hit rate | 0.900 | >= 0.980 | FAIL |
| Target page hit rate | n/a | >= 0.980 | FAIL |
| Faithfulness | n/a | n/a | N/A |
| Context Precision | n/a | n/a | N/A |
| Answer Relevance (English) | n/a | n/a | N/A |

Generation quality was not evaluated in this retrieval-only run.

## Quality slices (positive cases)

### By language

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| en | 20 | 0.950 | n/a | 0.850 | n/a | n/a | n/a | n/a | 0 |
| mixed | 2 | 1.000 | n/a | 1.000 | n/a | n/a | n/a | n/a | 0 |
| ru | 18 | 0.833 | n/a | 0.722 | n/a | n/a | n/a | n/a | 0 |

### By persona

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| eval-employee@docwise.example.com | 40 | 0.900 | n/a | 0.800 | n/a | n/a | n/a | n/a | 0 |

### By kind

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| positive | 40 | 0.900 | n/a | 0.800 | n/a | n/a | n/a | n/a | 0 |

### By source_dataset

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MIRACL v1.0 dev | 40 | 0.900 | n/a | 0.800 | n/a | n/a | n/a | n/a | 0 |

## ACL negatives

| Metric | Value |
| --- | --- |
| Cases | 0 |
| Cases with a `must_not_doc_ids` leak | **0** |
| Result | PASS |

Each case lists documents outside that persona's access in `must_not_doc_ids`. A leak is any Top-4 chunk from those documents. Restricted chunk text is not written here.

## Per-question

| id | persona | kind | target doc | page hit | section hit | ACL leak | faith | ctx p | ans rel | citation support | question |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| miracl-en-224 | eval-employee@docwise.example.com | positive | fba2106d | n/a | hit | 0 | n/a | n/a | n/a | n/a | When was Tylenol introduced? |
| miracl-en-1489 | eval-employee@docwise.example.com | positive | ac6f6dea | n/a | hit | 0 | n/a | n/a | n/a | n/a | How long is the optic nerve? |
| miracl-en-1713 | eval-employee@docwise.example.com | positive | 53a92549 | n/a | hit | 0 | n/a | n/a | n/a | n/a | How well did Descent: FreeSpace – The Great War sale? |
| miracl-en-2284 | eval-employee@docwise.example.com | positive | 71a4d4b4 | n/a | hit | 0 | n/a | n/a | n/a | n/a | What is the magnetic force of the Earth? |
| miracl-en-2493 | eval-employee@docwise.example.com | positive | 8cc2510e | n/a | hit | 0 | n/a | n/a | n/a | n/a | Where did Richard Siegmund Lindzen study physics? |
| miracl-en-2679 | eval-employee@docwise.example.com | positive | 8ea60221 | n/a | miss | 0 | n/a | n/a | n/a | n/a | Does melioidosis affect humans? |
| miracl-en-1236 | eval-employee@docwise.example.com | positive | c6fee24c | n/a | hit | 0 | n/a | n/a | n/a | n/a | How big was the SS Great Eastern? |
| miracl-en-2085 | eval-employee@docwise.example.com | positive | 667e06ce | n/a | hit | 0 | n/a | n/a | n/a | n/a | When was Marin Heidegger born? |
| miracl-en-2959 | eval-employee@docwise.example.com | positive | 274bfb35 | n/a | hit | 0 | n/a | n/a | n/a | n/a | What is the population of Burntisland, Scotland? |
| miracl-en-495 | eval-employee@docwise.example.com | positive | 3de66a4c | n/a | hit | 0 | n/a | n/a | n/a | n/a | When did Wilton Norman Chamberlain die? |
| miracl-en-1063 | eval-employee@docwise.example.com | positive | 1560bcf0 | n/a | hit | 0 | n/a | n/a | n/a | n/a | What is the life expectancy of a horse? |
| miracl-en-3809 | eval-employee@docwise.example.com | positive | c1f83d0b | n/a | miss | 0 | n/a | n/a | n/a | n/a | How much dopamine is in the human brain? |
| miracl-en-277 | eval-employee@docwise.example.com | positive | bb6b260a | n/a | hit | 0 | n/a | n/a | n/a | n/a | What was the fastest fighter plane used by the U.S. in World War II? |
| miracl-en-3459 | eval-employee@docwise.example.com | positive | e4d05754 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Where was Donald Malcolm Campbell born? |
| miracl-en-2204 | eval-employee@docwise.example.com | positive | 2167a945 | n/a | miss | 0 | n/a | n/a | n/a | n/a | Is Windows XP abandonware? |
| miracl-en-2195 | eval-employee@docwise.example.com | positive | 9400c840 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Did Catalonia do trade with France? |
| miracl-en-4081 | eval-employee@docwise.example.com | positive | 4fd037dd | n/a | hit | 0 | n/a | n/a | n/a | n/a | What's the current population of Demopolis? |
| miracl-en-2546 | eval-employee@docwise.example.com | positive | 9ac309b2 | n/a | hit | 0 | n/a | n/a | n/a | n/a | When was the first safety pin developed? |
| miracl-en-1680 | eval-employee@docwise.example.com | positive | 0c2d61ef | n/a | hit | 0 | n/a | n/a | n/a | n/a | How many types of calendars are there? |
| miracl-en-365 | eval-employee@docwise.example.com | positive | 8f3fe743 | n/a | hit | 0 | n/a | n/a | n/a | n/a | How many copies did Salem's Lot sell? |
| miracl-ru-107 | eval-employee@docwise.example.com | positive | eb2cd183 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Когда умер Ли Ха́рви О́свальд? |
| miracl-ru-2468 | eval-employee@docwise.example.com | positive | fb0a2618 | n/a | miss | 0 | n/a | n/a | n/a | n/a | Где был открыт памятник Бро́нзовый солда́т? |
| miracl-ru-1045 | eval-employee@docwise.example.com | positive | 03d061ce | n/a | hit | 0 | n/a | n/a | n/a | n/a | Болеют псориазом животные? |
| miracl-ru-3483 | eval-employee@docwise.example.com | positive | aba5a6c7 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Где был первый концерт группы Judas Priest? |
| miracl-ru-5642 | eval-employee@docwise.example.com | positive | 22cde90e | n/a | hit | 0 | n/a | n/a | n/a | n/a | Когда появился первый глобус? |
| miracl-ru-6661 | eval-employee@docwise.example.com | positive | 32344e13 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Как назывался Петербу́ргский метрополите́н до 1992 года? |
| miracl-ru-1914 | eval-employee@docwise.example.com | positive | 6f0ce79e | n/a | hit | 0 | n/a | n/a | n/a | n/a | Па́вел Ива́нович Ме́льников имел при жизни высокий литературный статус? |
| miracl-ru-3340 | eval-employee@docwise.example.com | positive | cc145e66 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Где был построен первый зоопарк в мире? |
| miracl-ru-23 | eval-employee@docwise.example.com | positive | d0a54089 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Когда в Китае начали есть палочками? |
| miracl-ru-4559 | eval-employee@docwise.example.com | positive | d3148829 | n/a | miss | 0 | n/a | n/a | n/a | n/a | Сколько воинов участвовало в Полтавской битве на стороне России? |
| miracl-ru-223 | eval-employee@docwise.example.com | positive | 619b4afe | n/a | miss | 0 | n/a | n/a | n/a | n/a | Что открыл  Ру́аль Э́нгельбрегт Гра́внинг А́мундсен? |
| miracl-ru-1086 | eval-employee@docwise.example.com | positive | b2108655 | n/a | miss | 0 | n/a | n/a | n/a | n/a | Смогли ли предотвратить взрыв при аварии на АЭС Три-Майл-Айленд? |
| miracl-ru-5857 | eval-employee@docwise.example.com | positive | ab553789 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Сколько стран принимало участие в XXIX летних Олимпийских игрх? |
| miracl-ru-1808 | eval-employee@docwise.example.com | positive | 38544ff7 | n/a | hit | 0 | n/a | n/a | n/a | n/a | БА-64 использовался в Корейской войне? |
| miracl-ru-920 | eval-employee@docwise.example.com | positive | d5c64df4 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Сколько лет Лев Николаевич Толстой писал роман «Война́ и мир»? |
| miracl-ru-4489 | eval-employee@docwise.example.com | positive | 5262af1e | n/a | miss | 0 | n/a | n/a | n/a | n/a | Какая максимальная скорость ЭР2? |
| miracl-ru-4783 | eval-employee@docwise.example.com | positive | 9ef54d1a | n/a | hit | 0 | n/a | n/a | n/a | n/a | Когда была основана Печерская Лавра в Киеве? |
| miracl-ru-4149 | eval-employee@docwise.example.com | positive | 00a3f618 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Где учился Никола́й Семёнович Леско́в? |
| miracl-ru-168 | eval-employee@docwise.example.com | positive | ac2a7608 | n/a | hit | 0 | n/a | n/a | n/a | n/a | Кто первым в мире совершил Ка́минг-а́ут? |
| miracl-ru-643 | eval-employee@docwise.example.com | positive | 8dd4eb0e | n/a | hit | 0 | n/a | n/a | n/a | n/a | Когда в Германии отменили смертную казнь? |
