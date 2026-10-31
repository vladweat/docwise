# RAG benchmark — concurrency smoke

Generated: `2026-10-31T05:22:56+00:00`
Code revision: `working-tree`
Golden dataset SHA-256: `1ae3a808fba2d2d33968dd4bc4d5a175059c427138f67152411496d08e71f3de`
Run configuration (safe fields only):
- `eval_concurrency`: `4`
- `eval_limit`: `8`
- `answer_relevance_encoders`: `Latin=BAAI/bge-small-en-v1.5; Cyrillic=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `dense_top_k`: `25`
- `embedding_max_input_tokens`: `128`
- `embedding_model`: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `embedding_profile`: `multilingual-compact`
- `eval_chunk_max_tokens`: `80`
- `llm_model`: `openai/gpt-5-nano`
- `rerank_threshold`: `0.1`
- `rerank_top_k`: `4`
- `reranker_model`: `BAAI/bge-reranker-v2-m3-int8`
- `reranker_size_gb_estimate`: `0.57`
- `rrf_k`: `60`
- `rrf_top_k`: `15`
- `sparse_top_k`: `25`
- `system_prompt_sha256`: `481a5c41865174724c7abb196eb8669bf3c2e3e0a9e87ada043bb956c65a91bd`
Eval personas: `employee`, `hr`, `finance`, `legal`, `security`, `engineering`
Cases: 8 (8 positive, 0 ACL-negative)
Case errors: 0
Pipeline: hybrid `retrieve` → Top-4 → `build_messages` + `stream_openai` (retrieval + generation + Ragas judges)

This limited 8-case run is an execution smoke test, not a full quality benchmark. Wall time was `263.26s`, including fixture and external corpus indexing, model warmup, sequential retrieval, generation, judges, and batched embeddings; it is not a measured speedup against a serial run.

Metrics follow Ragas definitions (Faithfulness, Context Precision, Answer Relevance) using the same OpenAI-compatible client as chat. Answer Relevance uses a fixed encoder per script: the historical BGE encoder for Latin questions and multilingual MiniLM for Cyrillic questions; the regression gate uses only the English slice. LangChain is not used.

## Ragas (positive cases)

| Metric | Score | n |
| --- | ---: | ---: |
| Faithfulness | 1.000 | 7 |
| Context Precision | 1.000 | 8 |
| Answer Relevance | 0.728 | 8 |
| Citation support | 0.857 | 7 |

## Response coverage

| Metric | Value |
| --- | ---: |
| Answers | 7 / 8 |
| Refusals | 1 / 8 |
| Cases with context | 8 / 8 |

## Retrieval

| Metric | Score | n |
| --- | ---: | ---: |
| Target document hit rate | 1.000 | 8 |
| Target page hit rate | n/a | 0 |
| Target section hit rate | 0.875 | 8 |

## Retrieval stage diagnostics

Stage lists are evaluated only for target presence/rank; snippets, answers, and passage text are not emitted.

### MIRACL v1.0 dev

| Stage | Cases | Section cases | Target doc hit | Exact section Recall@1 | Recall@4 | Recall@10 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dense | 8 | 8 | 1.000 | 0.500 | 0.875 | 1.000 | 0.688 |
| sparse | 8 | 8 | 1.000 | 0.125 | 0.750 | 1.000 | 0.329 |
| rrf | 8 | 8 | 1.000 | 0.250 | 0.875 | 1.000 | 0.494 |
| rerank_scored | 8 | 8 | 1.000 | 0.750 | 1.000 | 1.000 | 0.844 |
| rerank_thresholded | 8 | 8 | 1.000 | 0.750 | 0.875 | 0.875 | 0.812 |
| reranked | 8 | 8 | 1.000 | 0.750 | 0.875 | 0.875 | 0.812 |

Threshold simulation from the same reranker scores (no extra inference):

| Threshold | Target doc hit | Section Recall@1 | Section Recall@4 | Section MRR | Mean returned | Empty rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.10 | 1.000 | 0.750 | 0.875 | 0.812 | 2.125 | 0.000 |
| 0.15 | 1.000 | 0.750 | 0.875 | 0.812 | 1.750 | 0.000 |
| 0.20 | 1.000 | 0.750 | 0.875 | 0.812 | 1.750 | 0.000 |
| 0.25 | 1.000 | 0.750 | 0.875 | 0.812 | 1.500 | 0.000 |
| 0.30 | 1.000 | 0.750 | 0.875 | 0.812 | 1.500 | 0.000 |

## Quality gates

Initial regression floors are based on the full run dated 2026-10-30; they are not statistical confidence bounds.

| Gate | Observed | Threshold | Status |
| --- | ---: | ---: | --- |
| ACL leaks | 0 | = 0 | PASS |
| Case errors | 0 | = 0 | PASS |
| Target document hit rate | 1.000 | >= 0.980 | PASS |
| Target page hit rate | n/a | n/a | N/A |
| Faithfulness | 1.000 | >= 0.800 | PASS |
| Context Precision | 1.000 | >= 0.975 | PASS |
| Answer Relevance (English) | 0.728 | >= 0.827 | FAIL |



## Quality slices (positive cases)

### By language

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| en | 8 | 1.000 | n/a | 0.875 | 1.000 | 1.000 | 0.728 | 0.857 | 0 |

### By persona

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| eval-employee@docwise.example.com | 8 | 1.000 | n/a | 0.875 | 1.000 | 1.000 | 0.728 | 0.857 | 0 |

### By kind

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| positive | 8 | 1.000 | n/a | 0.875 | 1.000 | 1.000 | 0.728 | 0.857 | 0 |

### By source_dataset

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MIRACL v1.0 dev | 8 | 1.000 | n/a | 0.875 | 1.000 | 1.000 | 0.728 | 0.857 | 0 |

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
| miracl-en-224 | eval-employee@docwise.example.com | positive | fba2106d | n/a | hit | 0 | 1.000 | 1.000 | 0.942 | 1.000 | When was Tylenol introduced? |
| miracl-en-1489 | eval-employee@docwise.example.com | positive | ac6f6dea | n/a | hit | 0 | n/a | 1.000 | 0.000 | n/a | How long is the optic nerve? |
| miracl-en-1713 | eval-employee@docwise.example.com | positive | 53a92549 | n/a | hit | 0 | 1.000 | 1.000 | 0.831 | 1.000 | How well did Descent: FreeSpace – The Great War sale? |
| miracl-en-2284 | eval-employee@docwise.example.com | positive | 71a4d4b4 | n/a | hit | 0 | 1.000 | 1.000 | 0.772 | 1.000 | What is the magnetic force of the Earth? |
| miracl-en-2493 | eval-employee@docwise.example.com | positive | 8cc2510e | n/a | hit | 0 | 1.000 | 1.000 | 0.676 | 1.000 | Where did Richard Siegmund Lindzen study physics? |
| miracl-en-2679 | eval-employee@docwise.example.com | positive | 8ea60221 | n/a | miss | 0 | 1.000 | 1.000 | 0.941 | 0.000 | Does melioidosis affect humans? |
| miracl-en-1236 | eval-employee@docwise.example.com | positive | c6fee24c | n/a | hit | 0 | 1.000 | 1.000 | 0.809 | 1.000 | How big was the SS Great Eastern? |
| miracl-en-2085 | eval-employee@docwise.example.com | positive | 667e06ce | n/a | hit | 0 | 1.000 | 1.000 | 0.854 | 1.000 | When was Marin Heidegger born? |
