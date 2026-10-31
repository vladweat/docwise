# RAG benchmark

Generated: `2026-10-30T16:26:02+00:00`
Code revision: `unrecorded`
Golden dataset SHA-256: `cec613fc82e80eb098013b7b05deac1c8a1d5946edae63ce4e534c2079c52f9e`
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
Cases: 86 (45 positive, 41 ACL-negative)
Case errors: 0
Pipeline: hybrid `retrieve` → Top-4 → `build_messages` + `stream_openai` (retrieval + generation + Ragas judges)

Metrics follow Ragas definitions (Faithfulness, Context Precision, Answer Relevance) using the same OpenAI-compatible client as chat. Answer Relevance uses a fixed encoder per script: the historical BGE encoder for Latin questions and multilingual MiniLM for Cyrillic questions; the regression gate uses only the English slice. LangChain is not used.

## Ragas (positive cases)

| Metric | Score | n |
| --- | ---: | ---: |
| Faithfulness | 1.000 | 45 |
| Context Precision | 1.000 | 45 |
| Answer Relevance | 0.832 | 45 |
| Citation support | 0.978 | 45 |

## Retrieval

| Metric | Score | n |
| --- | ---: | ---: |
| Target document hit rate | 1.000 | 45 |
| Target page hit rate | 1.000 | 33 |
| Target section hit rate | 1.000 | 12 |

## Quality gates

Initial regression floors are based on the full run dated 2026-10-30; they are not statistical confidence bounds.

| Gate | Observed | Threshold | Status |
| --- | ---: | ---: | --- |
| ACL leaks | 0 | = 0 | PASS |
| Case errors | 0 | = 0 | PASS |
| Target document hit rate | 1.000 | >= 0.980 | PASS |
| Target page hit rate | 1.000 | >= 0.980 | PASS |
| Faithfulness | 1.000 | >= 0.800 | PASS |
| Context Precision | 1.000 | >= 0.975 | PASS |
| Answer Relevance (English) | 0.851 | >= 0.827 | PASS |



## Quality slices (positive cases)

### By language

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| en | 33 | 1.000 | 1.000 | n/a | 1.000 | 1.000 | 0.851 | 1.000 | 0 |
| mixed | 2 | 1.000 | n/a | 1.000 | 1.000 | 1.000 | 0.723 | 0.500 | 0 |
| ru | 10 | 1.000 | n/a | 1.000 | 1.000 | 1.000 | 0.792 | 1.000 | 0 |

### By persona

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| eval-employee@docwise.example.com | 30 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.837 | 1.000 | 0 |
| eval-engineering@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.792 | 0.667 | 0 |
| eval-finance@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.847 | 1.000 | 0 |
| eval-hr@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.883 | 1.000 | 0 |
| eval-legal@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.793 | 1.000 | 0 |
| eval-security@docwise.example.com | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.797 | 1.000 | 0 |

### By kind

| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| positive | 45 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.832 | 0.978 | 0 |

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
| hb-hours | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.932 | 1.000 | What are the core working hours at Docwise? |
| hb-lunch | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.871 | 1.000 | When is the unpaid lunch break? |
| hb-hybrid-office | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.888 | 1.000 | Which weekdays must employees come to the office under the hybrid policy? |
| hb-desk-booking | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.664 | 1.000 | By when must a desk be booked in the Places portal? |
| hb-personal-devices | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.943 | 1.000 | May employees store client personal data on personal devices? |
| hb-security-email | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.818 | 1.000 | Where should a security incident be reported, and how quickly? |
| hb-vendor-gifts | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.870 | 1.000 | What is the rule for gifts from vendors over 50 USD? |
| hb-warranty | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.939 | 1.000 | How long is the standard laptop warranty? |
| hb-badge-fee | eval-employee@docwise.example.com | positive | employee-handbook | hit | n/a | 0 | 1.000 | 1.000 | 0.785 | 1.000 | What is the replacement fee after the first lost badge? |
| lv-vacation-days | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.860 | 1.000 | How many paid vacation days do employees get per calendar year? |
| lv-sick-days | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.783 | 1.000 | How many paid sick days are employees entitled to? |
| lv-notice | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.748 | 1.000 | How far in advance must vacation requests be submitted? |
| lv-parental | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.894 | 1.000 | How long is parental leave? |
| lv-carryover | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.773 | 1.000 | How many unused vacation days may be carried into the next year? |
| lv-bereavement | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.869 | 1.000 | How many paid bereavement leave days are provided? |
| lv-unpaid | eval-employee@docwise.example.com | positive | leave-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.913 | 1.000 | Who must approve unpaid leave? |
| ex-taxi | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.963 | 1.000 | Do taxi receipts under forty dollars need a manager signature? |
| ex-meals | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.668 | 1.000 | What is the meal cap per person for local client meetings? |
| ex-deadline | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.912 | 1.000 | When are monthly expense reports due? |
| ex-intl-approval | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.676 | 1.000 | How far ahead must international travel be approved by a VP? |
| ex-per-diem | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.860 | 1.000 | What is the international travel per diem? |
| ex-business-class | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.842 | 1.000 | When is a business class flight allowed? |
| ex-card-limit | eval-employee@docwise.example.com | positive | expense-policy | hit | n/a | 0 | 1.000 | 1.000 | 0.944 | 1.000 | What is the company card limit for individual contributors? |
| eng-buddy | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.881 | 1.000 | How long is a new hire assigned a buddy? |
| eng-first-pr | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.704 | 1.000 | Within how many working days must a new engineer open their first pull request? |
| eng-python | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.915 | 1.000 | What is the default Python version for engineering? |
| eng-prod-approvers | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.901 | 1.000 | How many approvers are required for a production deploy? |
| eng-oncall | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | n/a | 0 | 1.000 | 1.000 | 0.737 | 1.000 | After how many days does the on-call starter rotation begin? |
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
| acl-allowed-hr | eval-hr@docwise.example.com | positive | hr-compensation | hit | n/a | 0 | 1.000 | 1.000 | 0.863 | 1.000 | What is the individual contributor L3 salary band? |
| acl-allowed-finance | eval-finance@docwise.example.com | positive | finance-q4 | hit | n/a | 0 | 1.000 | 1.000 | 0.935 | 1.000 | What was the gross margin in Q4? |
| acl-allowed-legal | eval-legal@docwise.example.com | positive | legal-templates | hit | n/a | 0 | 1.000 | 1.000 | 0.904 | 1.000 | What does the contract-redline template require before external circulation? |
| acl-allowed-security | eval-security@docwise.example.com | positive | security-controls | hit | n/a | 0 | 1.000 | 1.000 | 0.898 | 1.000 | How soon must privileged credentials be rotated after suspected exposure? |
| acl-allowed-engineering | eval-engineering@docwise.example.com | positive | engineering-release | hit | n/a | 0 | 1.000 | 1.000 | 0.929 | 1.000 | How long is the production canary window? |
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
| ru-employee-start | eval-employee@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.770 | 1.000 | Во сколько начинается рабочий день по московскому времени? |
| ru-employee-office-days | eval-employee@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.796 | 1.000 | В какие дни недели требуется приходить в офис? |
| ru-hr-vacation-days | eval-hr@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.940 | 1.000 | Сколько дней оплачиваемого отпуска положено за год? |
| ru-hr-carryover | eval-hr@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.846 | 1.000 | Сколько дней отпуска можно перенести на следующий год? |
| ru-finance-per-diem | eval-finance@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.837 | 1.000 | Какой размер суточных при международной поездке? |
| ru-finance-trip-approval | eval-finance@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.768 | 1.000 | За сколько дней нужно согласовать международную поездку? |
| ru-legal-contract-review | eval-legal@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.715 | 1.000 | Что требуется перед отправкой договора внешней стороне? |
| ru-legal-review-team | eval-legal@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.760 | 1.000 | Какая команда проверяет договор перед внешней отправкой? |
| ru-security-rotation | eval-security@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.760 | 1.000 | За какое время нужно сменить привилегированные данные после подозрения на утечку? |
| ru-security-report | eval-security@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.733 | 1.000 | За какое время нужно сообщить об инциденте безопасности? |
| ru-engineering-canary | eval-engineering@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.827 | 1.000 | Сколько длится canary-окно после production deployment? |
| ru-engineering-first-pr | eval-engineering@docwise.example.com | positive | ru-operations-guide | n/a | hit | 0 | 1.000 | 1.000 | 0.620 | 0.000 | Когда новый инженер должен открыть первый pull request? |
| ru-acl-employee-hr | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | Какая зарплатная вилка у сотрудника уровня L3? |
| ru-acl-employee-finance | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | Какой была выручка за четвёртый квартал? |
| ru-acl-employee-legal | eval-employee@docwise.example.com | acl_negative | legal-templates | miss | n/a | 0 | 1.000 | 1.000 | n/a | n/a | Что требует шаблон договора перед отправкой внешней стороне? |
| ru-acl-employee-security | eval-employee@docwise.example.com | acl_negative | security-controls | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | За какое время требуется сменить привилегированные данные после подозрения на утечку? |
| ru-acl-employee-engineering | eval-employee@docwise.example.com | acl_negative | engineering-release | miss | n/a | 0 | 1.000 | 0.000 | n/a | n/a | Сколько длится production canary-окно? |
