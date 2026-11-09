# RAG benchmark

Generated: `2026-11-09T09:38:45+00:00`
Code revision: `44b3f4251f0acfc4573b601a0ed272075168d10f`
Golden dataset SHA-256: `0aa3a62ab0e9a3d2adfd2a45c2f8057e3b88146f2993993380bb03869ad784b4`
Run configuration (safe fields only):
- `answer_relevance_encoders`: `Latin=BAAI/bge-small-en-v1.5; Cyrillic=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `dense_top_k`: `25`
- `embedding_max_input_tokens`: `512`
- `embedding_model`: `BAAI/bge-small-en-v1.5`
- `embedding_profile`: `current`
- `eval_chunk_max_tokens`: `600`
- `eval_concurrency`: `4`
- `eval_embedding_batch_size`: `1`
- `eval_limit`: `0`
- `eval_rerank_batch_size`: `64`
- `evaluation_profile`: `current`
- `generation_temperature`: `0.2`
- `hnsw_iterative_scan`: `relaxed_order`
- `hnsw_max_scan_tuples`: `20000`
- `judge_model`: `openai/gpt-5-nano`
- `judge_temperature`: `0.0`
- `llm_model`: `openai/gpt-5-nano`
- `rerank_threshold`: `0.25`
- `rerank_top_k`: `4`
- `reranker_model`: `BAAI/bge-reranker-base`
- `reranker_size_gb_estimate`: `1.04`
- `rrf_k`: `60`
- `rrf_top_k`: `15`
- `sparse_top_k`: `25`
- `system_prompt_sha256`: `1036de3ee1ca5ef33da1e147544e8ed19aa36d8cc104441c0349796a0317778f`

## Run metadata

| Field | Value |
| --- | --- |
| `schema_version` | `1` |
| `git_commit_sha` | `44b3f4251f0acfc4573b601a0ed272075168d10f` |
| `working_tree_dirty` | `true` |
| `dataset_sha256` | `0aa3a62ab0e9a3d2adfd2a45c2f8057e3b88146f2993993380bb03869ad784b4` |
| `evaluation_profile` | `current` |
| `embedding_model_identifier` | `BAAI/bge-small-en-v1.5` |
| `reranker_model_identifier` | `BAAI/bge-reranker-base` |
| `llm_model_identifier` | `openai/gpt-5-nano` |
| `judge_model_identifier` | `openai/gpt-5-nano` |
| `retrieval_parameters` | `{"dense_top_k": 25, "hnsw_iterative_scan": "relaxed_order", "hnsw_max_scan_tuples": 20000, "rrf_k": 60, "rrf_top_k": 15, "sparse_top_k": 25}` |
| `reranking_parameters` | `{"batch_size": 64, "threshold": 0.25, "top_k": 4}` |
| `runtime_parameters` | `{"concurrency": 4, "embedding_batch_size": 1, "limit": 0, "retrieval_only": false}` |
| `timestamp` | `2026-11-09T09:38:45+00:00` |
| `evaluation_framework` | `Docwise in-repo Ragas-style evaluator` |
| `evaluation_framework_version` | `not_applicable (versioned with the Git commit)` |
Eval personas: `employee`, `hr`, `finance`, `legal`, `security`, `engineering`
Cases: 92 (45 positive, 6 no-answer, 41 ACL-negative)
Case errors: 0
Pipeline: hybrid `retrieve` → Top-4 → `build_messages` + `stream_openai` (retrieval + generation + Ragas judges)

Metrics follow Ragas definitions (Faithfulness, Context Precision, Answer Relevance) using the same OpenAI-compatible client as chat. Answer Relevance uses a fixed encoder per script: the historical BGE encoder for Latin questions and multilingual MiniLM for Cyrillic questions; the regression gate uses only the English slice. LangChain is not used.

## Ragas (positive cases)

| Metric | Score | n |
| --- | ---: | ---: |
| Faithfulness | 1.000 | 42 |
| Context Precision | 0.996 | 42 |
| Answer Relevance | 0.770 | 45 |
| Citation support | 1.000 | 42 |

## Deterministic source reference check

This check verifies that each inline page or section citation matches a retrieved source title and location. It does not measure whether the cited source semantically supports an answer claim.

| Metric | Value |
| --- | ---: |
| Inline references matching retrieved sources | 50 / 51 |
| Citation reference precision | 0.980 |

## Response coverage

| Metric | Value |
| --- | ---: |
| Regular answers | 42 / 45 |
| Exact refusals | 3 / 45 |
| Embedded refusal phrases | 0 / 45 |
| Empty responses | 0 / 45 |
| Cases with context | 42 / 45 |
| Correct no-answer refusals | 6 / 6 |
| False no-answer answers | 0 / 6 |

## Runtime profile

Timings are aggregate milliseconds only; query and passage text are not repeated in this section.

| Stage | Total ms | Mean ms/item | Count |
| --- | ---: | ---: | ---: |
| Query embedding | 1534.587 | 16.680 | 92 |
| DB search | 1549.786 | 16.846 | 92 |
| Rerank (batched) | 208600.350 | 2267.395 | 1380 |

## No-answer behavior

No-answer questions are evaluated separately from answerable retrieval and ACL cases.

| Metric | Value |
| --- | ---: |
| Cases | 6 |
| Correct refusal rate | 1.000 |


## Retrieval

| Metric | Score | n |
| --- | ---: | ---: |
| Target document hit rate | 0.911 | 45 |
| Target page hit rate | 1.000 | 33 |
| Target section hit rate | 0.667 | 12 |

## Retrieval stage diagnostics

Stage lists are evaluated only for target presence/rank; snippets, answers, and passage text are not emitted.

### synthetic-golden

| Stage | Cases | Section cases | Target doc hit | Exact section Recall@1 | Recall@4 | Recall@10 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dense | 45 | 12 | 1.000 | 0.750 | 1.000 | 1.000 | 0.847 |
| sparse | 45 | 12 | 1.000 | 0.917 | 1.000 | 1.000 | 0.958 |
| rrf | 45 | 12 | 1.000 | 0.917 | 1.000 | 1.000 | 0.958 |
| rerank_scored | 45 | 12 | 1.000 | 0.917 | 1.000 | 1.000 | 0.958 |
| rerank_thresholded | 45 | 12 | 0.911 | 0.667 | 0.667 | 0.667 | 0.667 |
| reranked | 45 | 12 | 0.911 | 0.667 | 0.667 | 0.667 | 0.667 |

Threshold simulation from the same reranker scores (no extra inference):

| Threshold | Target doc hit | Section Recall@1 | Section Recall@4 | Section MRR | Mean returned | Empty rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.10 | 0.956 | 0.833 | 0.833 | 0.833 | 1.444 | 0.022 |
| 0.15 | 0.956 | 0.833 | 0.833 | 0.833 | 1.333 | 0.022 |
| 0.20 | 0.933 | 0.750 | 0.750 | 0.750 | 1.311 | 0.044 |
| 0.25 | 0.911 | 0.667 | 0.667 | 0.667 | 1.244 | 0.067 |
| 0.30 | 0.889 | 0.583 | 0.583 | 0.583 | 1.178 | 0.089 |

## Exact-section misses by case

Ranks include only case ID and target-section position; `—` means the exact section was absent at that stage.

| Case | Dense | Sparse | RRF | Reranker scored | Active threshold | Threshold 0.10 | Threshold 0.25 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ru-hr-vacation-days | 1 | 1 | 1 | 1 | — | 1 | — |
| ru-finance-per-diem | 2 | 1 | 1 | 1 | — | — | — |
| ru-finance-trip-approval | 3 | 2 | 2 | 1 | — | 1 | — |
| ru-engineering-first-pr | 1 | 1 | 1 | 2 | — | — | — |

## Quality gates

Initial regression floors are based on the full run dated 2026-10-30; they are not statistical confidence bounds.

| Gate | Observed | Threshold | Status |
| --- | ---: | ---: | --- |
| ACL leaks | 0 | = 0 | PASS |
| Case errors | 0 | = 0 | PASS |
| Target document hit rate | 0.911 | >= 0.980 | FAIL |
| Target page hit rate | 1.000 | >= 0.980 | PASS |
| Faithfulness | 1.000 | >= 0.800 | PASS |
| Context Precision | 0.996 | >= 0.975 | PASS |
| Answer Relevance (English) | 0.851 | >= 0.827 | PASS |
| No-answer refusal rate | 1.000 | >= 0.800 | PASS |



## Quality slices (positive cases)

### By language

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| en | 33 | 1.000 | 1.000 | n/a | 1.000 | 0.995 | 0.851 | 1.000 | 0 |
| mixed | 2 | 0.500 | n/a | 0.500 | 1.000 | 1.000 | 0.725 | 1.000 | 0 |
| ru | 10 | 0.700 | n/a | 0.700 | 1.000 | 1.000 | 0.513 | 1.000 | 0 |

### By persona

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| employee | 30 | 1.000 | 1.000 | 1.000 | 1.000 | 0.994 | 0.837 | 1.000 | 0 |
| engineering | 3 | 0.667 | 1.000 | 0.500 | 1.000 | 1.000 | 0.784 | 1.000 | 0 |
| finance | 3 | 0.333 | 1.000 | 0.000 | 1.000 | 1.000 | 0.308 | 1.000 | 0 |
| hr | 3 | 0.667 | 1.000 | 0.500 | 1.000 | 1.000 | 0.511 | 1.000 | 0 |
| legal | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.798 | 1.000 | 0 |
| security | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.780 | 1.000 | 0 |

### By kind

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| positive | 45 | 0.911 | 1.000 | 0.667 | 1.000 | 0.996 | 0.770 | 1.000 | 0 |

### By source_dataset

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| synthetic-golden | 45 | 0.911 | 1.000 | 0.667 | 1.000 | 0.996 | 0.770 | 1.000 | 0 |

## ACL negatives

| Metric | Value |
| --- | --- |
| Cases | 41 |
| Cases with a `must_not_doc_ids` leak | **0** |
| Result | PASS |

Each case lists documents outside that persona's access in `must_not_doc_ids`. A leak is any Top-4 chunk from those documents. Restricted chunk text is not written here.

## Per-case

| id | persona | kind | target doc | page | section | ACL leak | faith | ctx p | ans rel | citation |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| hb-hours | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.843 | 1.000 |
| hb-lunch | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.902 | 1.000 |
| hb-hybrid-office | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.921 | 1.000 |
| hb-desk-booking | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.831 | 1.000 |
| hb-personal-devices | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.909 | 1.000 |
| hb-security-email | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.812 | 1.000 |
| hb-vendor-gifts | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.773 | 1.000 |
| hb-warranty | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.928 | 1.000 |
| hb-badge-fee | employee | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.796 | 1.000 |
| lv-vacation-days | employee | positive | leave-policy | hit | n/a | 0 | 1.000 | 0.833 | 0.896 | 1.000 |
| lv-sick-days | employee | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.790 | 1.000 |
| lv-notice | employee | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.763 | 1.000 |
| lv-parental | employee | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.888 | 1.000 |
| lv-carryover | employee | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.733 | 1.000 |
| lv-bereavement | employee | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.796 | 1.000 |
| lv-unpaid | employee | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.897 | 1.000 |
| ex-taxi | employee | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.980 | 1.000 |
| ex-meals | employee | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.922 | 1.000 |
| ex-deadline | employee | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.883 | 1.000 |
| ex-intl-approval | employee | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.853 | 1.000 |
| ex-per-diem | employee | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.934 | 1.000 |
| ex-business-class | employee | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.784 | 1.000 |
| ex-card-limit | employee | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.927 | 1.000 |
| eng-buddy | employee | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.649 | 1.000 |
| eng-first-pr | employee | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.683 | 1.000 |
| eng-python | employee | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.934 | 1.000 |
| eng-prod-approvers | employee | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.907 | 1.000 |
| eng-oncall | employee | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.754 | 1.000 |
| acl-l3-band | employee | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-bonus-pct | employee | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-bonus-day | employee | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-ceo-multiplier | employee | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-q4-revenue | employee | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-headcount-freeze | employee | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-marketing-budget | employee | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-promotion-packet-deadline | employee | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-retention-rsus | employee | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-gross-margin | employee | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-customer-concentration | employee | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-bad-debt-reserve | employee | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-board-pack-deadline | employee | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-allowed-hr | hr | positive | hr-compensation | hit | n/a | 0 | 1.000 | 1.000 | 0.873 | 1.000 |
| acl-allowed-finance | finance | positive | finance-q4 | hit | n/a | 0 | 1.000 | 1.000 | 0.925 | 1.000 |
| acl-allowed-legal | legal | positive | legal-templates | hit | n/a | 0 | 1.000 | 1.000 | 0.888 | 1.000 |
| acl-allowed-security | security | positive | security-controls | hit | n/a | 0 | 1.000 | 1.000 | 0.806 | 1.000 |
| acl-allowed-engineering | engineering | positive | engineering-release | hit | n/a | 0 | 1.000 | 1.000 | 0.902 | 1.000 |
| acl-denied-employee-legal | employee | acl_negative | legal-templates | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-denied-employee-security | employee | acl_negative | security-controls | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-denied-employee-engineering | employee | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a |
| acl-matrix-hr-denies-finance | hr | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-hr-denies-legal | hr | acl_negative | legal-templates | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-hr-denies-security | hr | acl_negative | security-controls | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-hr-denies-engineering | hr | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a |
| acl-matrix-finance-denies-hr | finance | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-finance-denies-legal | finance | acl_negative | legal-templates | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-finance-denies-security | finance | acl_negative | security-controls | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-finance-denies-engineering | finance | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a |
| acl-matrix-legal-denies-hr | legal | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-legal-denies-finance | legal | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-legal-denies-security | legal | acl_negative | security-controls | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-legal-denies-engineering | legal | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a |
| acl-matrix-security-denies-hr | security | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-security-denies-finance | security | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-security-denies-legal | security | acl_negative | legal-templates | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-security-denies-engineering | security | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a |
| acl-matrix-engineering-denies-hr | engineering | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-engineering-denies-finance | engineering | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-engineering-denies-legal | engineering | acl_negative | legal-templates | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| acl-matrix-engineering-denies-security | engineering | acl_negative | security-controls | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| ru-employee-start | employee | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.646 | 1.000 |
| ru-employee-office-days | employee | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.782 | 1.000 |
| ru-hr-vacation-days | hr | positive | ru-operations-guide | n/a | miss | 0 | n/a | n/a | 0.000 | n/a |
| ru-hr-carryover | hr | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.660 | 1.000 |
| ru-finance-per-diem | finance | positive | ru-operations-guide | n/a | miss | 0 | n/a | n/a | 0.000 | n/a |
| ru-finance-trip-approval | finance | positive | ru-operations-guide | n/a | miss | 0 | n/a | n/a | 0.000 | n/a |
| ru-legal-contract-review | legal | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.750 | 1.000 |
| ru-legal-review-team | legal | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.755 | 1.000 |
| ru-security-rotation | security | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.791 | 1.000 |
| ru-security-report | security | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.743 | 1.000 |
| ru-engineering-canary | engineering | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.722 | 1.000 |
| ru-engineering-first-pr | engineering | positive | ru-operations-guide | n/a | miss | 0 | 1.000 | 1.000 | 0.728 | 1.000 |
| ru-acl-employee-hr | employee | acl_negative | hr-compensation | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| ru-acl-employee-finance | employee | acl_negative | finance-q4 | miss | n/a | 0 | n/a | n/a | n/a | n/a |
| ru-acl-employee-legal | employee | acl_negative | legal-templates | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a |
| ru-acl-employee-security | employee | acl_negative | security-controls | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a |
| ru-acl-employee-engineering | employee | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a |
| no-answer-en-office-paint | employee | no_answer | — | n/a | n/a | 0 | n/a | n/a | n/a | n/a |
| no-answer-en-pet-policy | employee | no_answer | — | n/a | n/a | 0 | n/a | n/a | n/a | n/a |
| no-answer-en-lunar-travel | employee | no_answer | — | n/a | n/a | 0 | n/a | n/a | n/a | n/a |
| no-answer-ru-office-paint | employee | no_answer | — | n/a | n/a | 0 | n/a | n/a | n/a | n/a |
| no-answer-ru-pet-policy | employee | no_answer | — | n/a | n/a | 0 | n/a | n/a | n/a | n/a |
| no-answer-ru-lunar-travel | employee | no_answer | — | n/a | n/a | 0 | n/a | n/a | n/a | n/a |
