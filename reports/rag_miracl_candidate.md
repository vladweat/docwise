# RAG benchmark

Generated: `2026-10-30T19:44:38+00:00`
Code revision: `eca0b58`
Working tree state: dirty during this run; the code revision identifies `HEAD` only.
Golden dataset SHA-256: `19c8cbaec501d6e36b5e7ab4f1dc690a2c3d3d8d7251aa1f5b581813b3a54de0`
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
Cases: 126 (85 positive, 41 ACL-negative)
Case errors: 0
Pipeline: hybrid `retrieve` → Top-4 → `build_messages` + `stream_openai` (retrieval + generation + Ragas judges)

Metrics follow Ragas definitions (Faithfulness, Context Precision, Answer Relevance) using the same OpenAI-compatible client as chat. Answer Relevance uses a fixed encoder per script: the historical BGE encoder for Latin questions and multilingual MiniLM for Cyrillic questions; the regression gate uses only the English slice. LangChain is not used.

**Scoring caveat:** This run predates the 2026-10-31 correction for refusal and empty-context handling. Refusals could receive Faithfulness `1.0`, and empty contexts could receive Context Precision `1.0`; those two aggregates may be inflated. Use the retrieval-only stage diagnostic for current retrieval evidence; a full generation rerun is needed for corrected judge aggregates.

## Ragas (positive cases)

| Metric | Score | n |
| --- | ---: | ---: |
| Faithfulness | 0.976 | 85 |
| Context Precision | 0.929 | 85 |
| Answer Relevance | 0.660 | 85 |
| Citation support | 0.933 | 71 |

## Retrieval

| Metric | Score | n |
| --- | ---: | ---: |
| Target document hit rate | 0.953 | 85 |
| Target page hit rate | 1.000 | 33 |
| Target section hit rate | 0.846 | 52 |

## Quality gates

Initial regression floors are based on the full run dated 2026-10-30; they are not statistical confidence bounds.

| Gate | Observed | Threshold | Status |
| --- | ---: | ---: | --- |
| ACL leaks | 0 | = 0 | PASS |
| Case errors | 0 | = 0 | PASS |
| Target document hit rate | 0.953 | >= 0.980 | FAIL |
| Target page hit rate | 1.000 | >= 0.980 | PASS |
| Faithfulness | 0.976 | >= 0.800 | PASS |
| Context Precision | 0.929 | >= 0.975 | FAIL |
| Answer Relevance (English) | 0.757 | >= 0.827 | FAIL |



## Quality slices (positive cases)

### By language

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| en | 53 | 0.981 | 1.000 | 0.850 | 0.962 | 0.972 | 0.757 | 0.954 | 0 |
| mixed | 4 | 1.000 | n/a | 1.000 | 1.000 | 0.625 | 0.364 | 1.000 | 0 |
| ru | 28 | 0.893 | n/a | 0.821 | 1.000 | 0.893 | 0.518 | 0.875 | 0 |

### By persona

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| eval-employee@docwise.example.com | 70 | 0.943 | 1.000 | 0.810 | 0.971 | 0.914 | 0.638 | 0.915 | 0 |
| eval-engineering@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.801 | 1.000 | 0 |
| eval-finance@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.556 | 1.000 | 0 |
| eval-hr@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.820 | 1.000 | 0 |
| eval-legal@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.754 | 1.000 | 0 |
| eval-security@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.868 | 1.000 | 0 |

### By kind

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| positive | 85 | 0.953 | 1.000 | 0.846 | 0.976 | 0.929 | 0.660 | 0.933 | 0 |

### By source_dataset

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MIRACL v1.0 dev | 40 | 0.900 | n/a | 0.800 | 0.950 | 0.850 | 0.491 | 0.817 | 0 |
| synthetic-golden | 45 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.809 | 1.000 | 0 |

## ACL negatives

| Metric | Value |
| --- | --- |
| Cases | 41 |
| Cases with a `must_not_doc_ids` leak | **0** |
| Result | PASS |

Each case lists documents outside that persona's access in `must_not_doc_ids`. A leak is any Top-4 chunk from those documents. Restricted chunk text is not written here.

## Per-question

| id | persona | kind | target doc | page hit | section hit | ACL leak | faith | ctx p | ans rel | citation support | question |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| hb-hours | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.755 | 1.000 | What are the core working hours at Docwise? |
| hb-lunch | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.814 | 1.000 | When is the unpaid lunch break? |
| hb-hybrid-office | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.690 | 1.000 | Which weekdays must employees come to the office under the hybrid policy? |
| hb-desk-booking | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.643 | 1.000 | By when must a desk be booked in the Places portal? |
| hb-personal-devices | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.931 | 1.000 | May employees store client personal data on personal devices? |
| hb-security-email | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.784 | 1.000 | Where should a security incident be reported, and how quickly? |
| hb-vendor-gifts | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.859 | 1.000 | What is the rule for gifts from vendors over 50 USD? |
| hb-warranty | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.926 | 1.000 | How long is the standard laptop warranty? |
| hb-badge-fee | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.786 | 1.000 | What is the replacement fee after the first lost badge? |
| lv-vacation-days | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.857 | 1.000 | How many paid vacation days do employees get per calendar year? |
| lv-sick-days | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.869 | 1.000 | How many paid sick days are employees entitled to? |
| lv-notice | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.897 | 1.000 | How far in advance must vacation requests be submitted? |
| lv-parental | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.938 | 1.000 | How long is parental leave? |
| lv-carryover | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.808 | 1.000 | How many unused vacation days may be carried into the next year? |
| lv-bereavement | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.879 | 1.000 | How many paid bereavement leave days are provided? |
| lv-unpaid | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.741 | 1.000 | Who must approve unpaid leave? |
| ex-taxi | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.910 | 1.000 | Do taxi receipts under forty dollars need a manager signature? |
| ex-meals | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.790 | 1.000 | What is the meal cap per person for local client meetings? |
| ex-deadline | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.849 | 1.000 | When are monthly expense reports due? |
| ex-intl-approval | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.724 | 1.000 | How far ahead must international travel be approved by a VP? |
| ex-per-diem | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.916 | 1.000 | What is the international travel per diem? |
| ex-business-class | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.824 | 1.000 | When is a business class flight allowed? |
| ex-card-limit | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.949 | 1.000 | What is the company card limit for individual contributors? |
| eng-buddy | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.887 | 1.000 | How long is a new hire assigned a buddy? |
| eng-first-pr | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.913 | 1.000 | Within how many working days must a new engineer open their first pull request? |
| eng-python | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.909 | 1.000 | What is the default Python version for engineering? |
| eng-prod-approvers | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.906 | 1.000 | How many approvers are required for a production deploy? |
| eng-oncall | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.651 | 1.000 | After how many days does the on-call starter rotation begin? |
| acl-l3-band | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What is the individual contributor L3 salary band in USD? |
| acl-bonus-pct | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What percent of base salary is the annual performance bonus target? |
| acl-bonus-day | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | On what date is the performance bonus paid? |
| acl-ceo-multiplier | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What is the CEO cash bonus multiplier for this fiscal year? |
| acl-q4-revenue | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What was Q4 revenue in USD? |
| acl-headcount-freeze | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | Until which date is headcount frozen except for backfills? |
| acl-marketing-budget | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What is next quarter's marketing budget? |
| acl-promotion-packet-deadline | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | When are HR promotion packets due? |
| acl-retention-rsus | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | How long do retention RSUs vest for L4 and above? |
| acl-gross-margin | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What gross margin did Finance report for Q4? |
| acl-customer-concentration | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What share of ARR came from the largest customer? |
| acl-bad-debt-reserve | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | How much did Finance set aside for the bad debt reserve? |
| acl-board-pack-deadline | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | When is the Finance board meeting pack due? |
| acl-allowed-hr | eval-hr@docwise.example.com | positive | hr-compensation | hit | n/a | 0 | 1.000 | 1.000 | 0.884 | 1.000 | What is the individual contributor L3 salary band? |
| acl-allowed-finance | eval-finance@docwise.example.com | positive | finance-q4 | hit | n/a | 0 | 1.000 | 1.000 | 0.905 | 1.000 | What was the gross margin in Q4? |
| acl-allowed-legal | eval-legal@docwise.example.com | positive | legal-templates | hit | n/a | 0 | 1.000 | 1.000 | 0.704 | 1.000 | What does the contract-redline template require before external circulation? |
| acl-allowed-security | eval-security@docwise.example.com | positive | security-controls | hit | n/a | 0 | 1.000 | 1.000 | 0.950 | 1.000 | How soon must privileged credentials be rotated after suspected exposure? |
| acl-allowed-engineering | eval-engineering@docwise.example.com | positive | engineering-release | hit | n/a | 0 | 1.000 | 1.000 | 0.947 | 1.000 | How long is the production canary window? |
| acl-denied-employee-legal | eval-employee@docwise.example.com | acl_negative | legal-templates | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What does the contract-redline template require before external circulation? |
| acl-denied-employee-security | eval-employee@docwise.example.com | acl_negative | security-controls | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| acl-denied-employee-engineering | eval-employee@docwise.example.com | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How long is the production canary window? |
| acl-matrix-hr-denies-finance | eval-hr@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What was the gross margin in Q4? |
| acl-matrix-hr-denies-legal | eval-hr@docwise.example.com | acl_negative | legal-templates | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What does the contract-redline template require before external circulation? |
| acl-matrix-hr-denies-security | eval-hr@docwise.example.com | acl_negative | security-controls | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| acl-matrix-hr-denies-engineering | eval-hr@docwise.example.com | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How long is the production canary window? |
| acl-matrix-finance-denies-hr | eval-finance@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What is the individual contributor L3 salary band? |
| acl-matrix-finance-denies-legal | eval-finance@docwise.example.com | acl_negative | legal-templates | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What does the contract-redline template require before external circulation? |
| acl-matrix-finance-denies-security | eval-finance@docwise.example.com | acl_negative | security-controls | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| acl-matrix-finance-denies-engineering | eval-finance@docwise.example.com | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How long is the production canary window? |
| acl-matrix-legal-denies-hr | eval-legal@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What is the individual contributor L3 salary band? |
| acl-matrix-legal-denies-finance | eval-legal@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What was the gross margin in Q4? |
| acl-matrix-legal-denies-security | eval-legal@docwise.example.com | acl_negative | security-controls | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| acl-matrix-legal-denies-engineering | eval-legal@docwise.example.com | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How long is the production canary window? |
| acl-matrix-security-denies-hr | eval-security@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What is the individual contributor L3 salary band? |
| acl-matrix-security-denies-finance | eval-security@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What was the gross margin in Q4? |
| acl-matrix-security-denies-legal | eval-security@docwise.example.com | acl_negative | legal-templates | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What does the contract-redline template require before external circulation? |
| acl-matrix-security-denies-engineering | eval-security@docwise.example.com | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How long is the production canary window? |
| acl-matrix-engineering-denies-hr | eval-engineering@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What is the individual contributor L3 salary band? |
| acl-matrix-engineering-denies-finance | eval-engineering@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What was the gross margin in Q4? |
| acl-matrix-engineering-denies-legal | eval-engineering@docwise.example.com | acl_negative | legal-templates | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | What does the contract-redline template require before external circulation? |
| acl-matrix-engineering-denies-security | eval-engineering@docwise.example.com | acl_negative | security-controls | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| ru-employee-start | eval-employee@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.769 | 1.000 | Во сколько начинается рабочий день по московскому времени? |
| ru-employee-office-days | eval-employee@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.833 | 1.000 | В какие дни недели требуется приходить в офис? |
| ru-hr-vacation-days | eval-hr@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.909 | 1.000 | Сколько дней оплачиваемого отпуска положено за год? |
| ru-hr-carryover | eval-hr@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.668 | 1.000 | Сколько дней отпуска можно перенести на следующий год? |
| ru-finance-per-diem | eval-finance@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.366 | 1.000 | Какой размер суточных при международной поездке? |
| ru-finance-trip-approval | eval-finance@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.398 | 1.000 | За сколько дней нужно согласовать международную поездку? |
| ru-legal-contract-review | eval-legal@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.747 | 1.000 | Что требуется перед отправкой договора внешней стороне? |
| ru-legal-review-team | eval-legal@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.812 | 1.000 | Какая команда проверяет договор перед внешней отправкой? |
| ru-security-rotation | eval-security@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.750 | 1.000 | За какое время нужно сменить привилегированные данные после подозрения на утечку? |
| ru-security-report | eval-security@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.904 | 1.000 | За какое время нужно сообщить об инциденте безопасности? |
| ru-engineering-canary | eval-engineering@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.747 | 1.000 | Сколько длится canary-окно после production deployment? |
| ru-engineering-first-pr | eval-engineering@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.709 | 1.000 | Когда новый инженер должен открыть первый pull request? |
| ru-acl-employee-hr | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | Какая зарплатная вилка у сотрудника уровня L3? |
| ru-acl-employee-finance | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | Какой была выручка за четвёртый квартал? |
| ru-acl-employee-legal | eval-employee@docwise.example.com | acl_negative | legal-templates | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | Что требует шаблон договора перед отправкой внешней стороне? |
| ru-acl-employee-security | eval-employee@docwise.example.com | acl_negative | security-controls | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | За какое время требуется сменить привилегированные данные после подозрения на утечку? |
| ru-acl-employee-engineering | eval-employee@docwise.example.com | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | Сколько длится production canary-окно? |
| miracl-en-224 | eval-employee@docwise.example.com | positive | fba2106d | n/a | hit | 0 | 1.000 | 1.000 | 0.941 | 1.000 | When was Tylenol introduced? |
| miracl-en-1489 | eval-employee@docwise.example.com | positive | ac6f6dea | n/a | hit | 0 | 1.000 | 1.000 | 0.844 | 1.000 | How long is the optic nerve? |
| miracl-en-1713 | eval-employee@docwise.example.com | positive | 53a92549 | n/a | hit | 0 | 0.000 | 1.000 | 0.821 | 1.000 | How well did Descent: FreeSpace – The Great War sale? |
| miracl-en-2284 | eval-employee@docwise.example.com | positive | 71a4d4b4 | n/a | hit | 0 | 1.000 | 1.000 | 0.803 | 1.000 | What is the magnetic force of the Earth? |
| miracl-en-2493 | eval-employee@docwise.example.com | positive | 8cc2510e | n/a | hit | 0 | 1.000 | 1.000 | 0.761 | 1.000 | Where did Richard Siegmund Lindzen study physics? |
| miracl-en-2679 | eval-employee@docwise.example.com | positive | 8ea60221 | n/a | miss | 0 | 1.000 | 1.000 | 0.880 | 0.750 | Does melioidosis affect humans? |
| miracl-en-1236 | eval-employee@docwise.example.com | positive | c6fee24c | n/a | hit | 0 | 1.000 | 1.000 | 0.609 | 1.000 | How big was the SS Great Eastern? |
| miracl-en-2085 | eval-employee@docwise.example.com | positive | 667e06ce | n/a | hit | 0 | 1.000 | 1.000 | 0.817 | 1.000 | When was Marin Heidegger born? |
| miracl-en-2959 | eval-employee@docwise.example.com | positive | 274bfb35 | n/a | hit | 0 | 1.000 | 1.000 | 0.877 | 1.000 | What is the population of Burntisland, Scotland? |
| miracl-en-495 | eval-employee@docwise.example.com | positive | 3de66a4c | n/a | hit | 0 | 1.000 | 1.000 | 0.539 | 1.000 | When did Wilton Norman Chamberlain die? |
| miracl-en-1063 | eval-employee@docwise.example.com | positive | 1560bcf0 | n/a | hit | 0 | 1.000 | 1.000 | 0.872 | 1.000 | What is the life expectancy of a horse? |
| miracl-en-3809 | eval-employee@docwise.example.com | positive | c1f83d0b | n/a | miss | 0 | 1.000 | 0.000 | 0.000 | n/a | How much dopamine is in the human brain? |
| miracl-en-277 | eval-employee@docwise.example.com | positive | bb6b260a | n/a | hit | 0 | 1.000 | 0.500 | 0.000 | n/a | What was the fastest fighter plane used by the U.S. in World War II? |
| miracl-en-3459 | eval-employee@docwise.example.com | positive | e4d05754 | n/a | hit | 0 | 1.000 | 1.000 | 0.566 | 1.000 | Where was Donald Malcolm Campbell born? |
| miracl-en-2204 | eval-employee@docwise.example.com | positive | 2167a945 | n/a | miss | 0 | 1.000 | 1.000 | 0.000 | n/a | Is Windows XP abandonware? |
| miracl-en-2195 | eval-employee@docwise.example.com | positive | 9400c840 | n/a | hit | 0 | 1.000 | 1.000 | 0.844 | 1.000 | Did Catalonia do trade with France? |
| miracl-en-4081 | eval-employee@docwise.example.com | positive | 4fd037dd | n/a | hit | 0 | 0.000 | 1.000 | 0.442 | 0.000 | What's the current population of Demopolis? |
| miracl-en-2546 | eval-employee@docwise.example.com | positive | 9ac309b2 | n/a | hit | 0 | 1.000 | 1.000 | 0.868 | 0.000 | When was the first safety pin developed? |
| miracl-en-1680 | eval-employee@docwise.example.com | positive | 0c2d61ef | n/a | hit | 0 | 1.000 | 1.000 | 0.827 | 1.000 | How many types of calendars are there? |
| miracl-en-365 | eval-employee@docwise.example.com | positive | 8f3fe743 | n/a | hit | 0 | 1.000 | 1.000 | 0.000 | n/a | How many copies did Salem's Lot sell? |
| miracl-ru-107 | eval-employee@docwise.example.com | positive | eb2cd183 | n/a | hit | 0 | 1.000 | 1.000 | 0.000 | n/a | Когда умер Ли Ха́рви О́свальд? |
| miracl-ru-2468 | eval-employee@docwise.example.com | positive | fb0a2618 | n/a | miss | 0 | 1.000 | 1.000 | 0.000 | n/a | Где был открыт памятник Бро́нзовый солда́т? |
| miracl-ru-1045 | eval-employee@docwise.example.com | positive | 03d061ce | n/a | hit | 0 | 1.000 | 1.000 | 0.532 | 1.000 | Болеют псориазом животные? |
| miracl-ru-3483 | eval-employee@docwise.example.com | positive | aba5a6c7 | n/a | hit | 0 | 1.000 | 0.000 | 0.000 | n/a | Где был первый концерт группы Judas Priest? |
| miracl-ru-5642 | eval-employee@docwise.example.com | positive | 22cde90e | n/a | hit | 0 | 1.000 | 1.000 | 0.856 | 1.000 | Когда появился первый глобус? |
| miracl-ru-6661 | eval-employee@docwise.example.com | positive | 32344e13 | n/a | hit | 0 | 1.000 | 1.000 | 0.634 | 1.000 | Как назывался Петербу́ргский метрополите́н до 1992 года? |
| miracl-ru-1914 | eval-employee@docwise.example.com | positive | 6f0ce79e | n/a | hit | 0 | 1.000 | 1.000 | 0.887 | 1.000 | Па́вел Ива́нович Ме́льников имел при жизни высокий литературный статус? |
| miracl-ru-3340 | eval-employee@docwise.example.com | positive | cc145e66 | n/a | hit | 0 | 1.000 | 1.000 | 0.784 | 0.000 | Где был построен первый зоопарк в мире? |
| miracl-ru-23 | eval-employee@docwise.example.com | positive | d0a54089 | n/a | hit | 0 | 1.000 | 1.000 | 0.845 | 1.000 | Когда в Китае начали есть палочками? |
| miracl-ru-4559 | eval-employee@docwise.example.com | positive | d3148829 | n/a | miss | 0 | 1.000 | 0.000 | 0.000 | n/a | Сколько воинов участвовало в Полтавской битве на стороне России? |
| miracl-ru-223 | eval-employee@docwise.example.com | positive | 619b4afe | n/a | miss | 0 | 1.000 | 0.000 | 0.000 | n/a | Что открыл  Ру́аль Э́нгельбрегт Гра́внинг А́мундсен? |
| miracl-ru-1086 | eval-employee@docwise.example.com | positive | b2108655 | n/a | miss | 0 | 1.000 | 1.000 | 0.000 | n/a | Смогли ли предотвратить взрыв при аварии на АЭС Три-Майл-Айленд? |
| miracl-ru-5857 | eval-employee@docwise.example.com | positive | ab553789 | n/a | hit | 0 | 1.000 | 0.500 | 0.000 | n/a | Сколько стран принимало участие в XXIX летних Олимпийских игрх? |
| miracl-ru-1808 | eval-employee@docwise.example.com | positive | 38544ff7 | n/a | hit | 0 | 1.000 | 1.000 | 0.657 | 0.500 | БА-64 использовался в Корейской войне? |
| miracl-ru-920 | eval-employee@docwise.example.com | positive | d5c64df4 | n/a | hit | 0 | 1.000 | 1.000 | 0.508 | 1.000 | Сколько лет Лев Николаевич Толстой писал роман «Война́ и мир»? |
| miracl-ru-4489 | eval-employee@docwise.example.com | positive | 5262af1e | n/a | miss | 0 | 1.000 | 0.000 | 0.000 | n/a | Какая максимальная скорость ЭР2? |
| miracl-ru-4783 | eval-employee@docwise.example.com | positive | 9ef54d1a | n/a | hit | 0 | 1.000 | 1.000 | 0.000 | n/a | Когда была основана Печерская Лавра в Киеве? |
| miracl-ru-4149 | eval-employee@docwise.example.com | positive | 00a3f618 | n/a | hit | 0 | 1.000 | 1.000 | 0.776 | 0.000 | Где учился Никола́й Семёнович Леско́в? |
| miracl-ru-168 | eval-employee@docwise.example.com | positive | ac2a7608 | n/a | hit | 0 | 1.000 | 1.000 | 0.000 | n/a | Кто первым в мире совершил Ка́минг-а́ут? |
| miracl-ru-643 | eval-employee@docwise.example.com | positive | 8dd4eb0e | n/a | hit | 0 | 1.000 | 1.000 | 0.866 | 1.000 | Когда в Германии отменили смертную казнь? |
