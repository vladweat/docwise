# Замер качества RAG

Создано: `2026-10-30T13:15:42+00:00`
Ревизия кода: `eca0b58-working-tree`
SHA-256 эталонного набора данных: `1d4c5af6bb8c85ba8e79ef643a8d543eabba54247b51fc4f7d44b14c524a5477`
Параметры запуска (только безопасные поля):
- `dense_top_k`: `25`
- `embedding_model`: `BAAI/bge-small-en-v1.5`
- `llm_model`: `openai/gpt-5-nano`
- `rerank_threshold`: `0.25`
- `rerank_top_k`: `4`
- `reranker_model`: `BAAI/bge-reranker-base`
- `rrf_k`: `60`
- `rrf_top_k`: `15`
- `sparse_top_k`: `25`
- `system_prompt_sha256`: `481a5c41865174724c7abb196eb8669bf3c2e3e0a9e87ada043bb956c65a91bd`
Роли оценки: `employee`, `hr`, `finance`, `legal`, `security`, `engineering`
Случаи: 69 (33 `positive`, 36 `ACL-negative`)
Ошибки случаев: 0
Конвейер: гибридный `retrieve` → Top-4 → `build_messages` + `stream_openai` (поиск + генерация + оценки Ragas)

Метрики «верность контексту» (`Faithfulness`), «точность контекста» (`Context Precision`) и «релевантность ответа» (`Answer Relevance`) рассчитываются по определениям Ragas через тот же клиент, совместимый с OpenAI, что и чат. `LangChain` не используется.

## Ragas (положительные случаи)

| Метрика | Оценка | n |
| --- | ---: | ---: |
| Верность контексту (`Faithfulness`) | 1.000 | 33 |
| Точность контекста (`Context Precision`) | 0.995 | 33 |
| Релевантность ответа (`Answer Relevance`) | 0.847 | 33 |

## Поиск

| Метрика | Оценка | n |
| --- | ---: | ---: |
| Доля попаданий в целевой документ (`Target document hit rate`) | 1.000 | 33 |
| Доля попаданий на целевую страницу (`Target page hit rate`) | 1.000 | 33 |

## Критерии качества

Начальные пороги регрессии заданы по этому полному запуску; это не статистические доверительные границы.

| Критерий качества | Результат | Порог | Статус |
| --- | ---: | ---: | --- |
| Утечки ACL | 0 | = 0 | PASS |
| Ошибки случаев | 0 | = 0 | PASS |
| Доля попаданий в целевой документ (`Target document hit rate`) | 1.000 | >= 0.980 | PASS |
| Доля попаданий на целевую страницу (`Target page hit rate`) | 1.000 | >= 0.980 | PASS |
| Верность контексту (`Faithfulness`) | 1.000 | >= 0.800 | PASS |
| Точность контекста (`Context Precision`) | 0.995 | >= 0.975 | PASS |
| Релевантность ответа (`Answer Relevance`) | 0.847 | >= 0.827 | PASS |

## Срезы качества (положительные случаи)

### По языку

| Группа | Случаи | Попадание в документ | Попадание на страницу | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Ошибки |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| en | 33 | 1.000 | 1.000 | 1.000 | 0.995 | 0.847 | 0 |

### По роли

| Группа | Случаи | Попадание в документ | Попадание на страницу | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Ошибки |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| eval-employee@docwise.example.com | 28 | 1.000 | 1.000 | 1.000 | 0.994 | 0.849 | 0 |
| eval-engineering@docwise.example.com | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 0.914 | 0 |
| eval-finance@docwise.example.com | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 0.934 | 0 |
| eval-hr@docwise.example.com | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 0.874 | 0 |
| eval-legal@docwise.example.com | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 0.729 | 0 |
| eval-security@docwise.example.com | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 0.741 | 0 |

### По типу случая

| Группа | Случаи | Попадание в документ | Попадание на страницу | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Ошибки |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| positive | 33 | 1.000 | 1.000 | 1.000 | 0.995 | 0.847 | 0 |

## Отрицательные случаи ACL

| Метрика | Значение |
| --- | --- |
| Случаи | 36 |
| Случаи с утечкой `must_not_doc_ids` | **0** |
| Результат | PASS |

Для каждого случая в `must_not_doc_ids` перечислены документы, недоступные этой роли. Утечкой считается любой фрагмент Top-4 из этих документов. Текст ограниченных фрагментов здесь не сохраняется.

## По вопросам

| `id` | `persona` | `kind` | Целевой документ | Страница | Утечка ACL | Верность контексту (`Faithfulness`) | Точность контекста (`Context Precision`) | Релевантность ответа (`Answer Relevance`) | Вопрос |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| hb-hours | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.758 | What are the core working hours at Docwise? |
| hb-lunch | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.918 | When is the unpaid lunch break? |
| hb-hybrid-office | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.881 | Which weekdays must employees come to the office under the hybrid policy? |
| hb-desk-booking | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.825 | By when must a desk be booked in the Places portal? |
| hb-personal-devices | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.944 | May employees store client personal data on personal devices? |
| hb-security-email | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.824 | Where should a security incident be reported, and how quickly? |
| hb-vendor-gifts | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.817 | What is the rule for gifts from vendors over 50 USD? |
| hb-warranty | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.936 | How long is the standard laptop warranty? |
| hb-badge-fee | eval-employee@docwise.example.com | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.940 | What is the replacement fee after the first lost badge? |
| lv-vacation-days | eval-employee@docwise.example.com | positive | leave-policy | hit | 0 | 1.000 | 0.833 | 0.860 | How many paid vacation days do employees get per calendar year? |
| lv-sick-days | eval-employee@docwise.example.com | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.826 | How many paid sick days are employees entitled to? |
| lv-notice | eval-employee@docwise.example.com | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.913 | How far in advance must vacation requests be submitted? |
| lv-parental | eval-employee@docwise.example.com | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.894 | How long is parental leave? |
| lv-carryover | eval-employee@docwise.example.com | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.661 | How many unused vacation days may be carried into the next year? |
| lv-bereavement | eval-employee@docwise.example.com | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.786 | How many paid bereavement leave days are provided? |
| lv-unpaid | eval-employee@docwise.example.com | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.916 | Who must approve unpaid leave? |
| ex-taxi | eval-employee@docwise.example.com | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.953 | Do taxi receipts under forty dollars need a manager signature? |
| ex-meals | eval-employee@docwise.example.com | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.769 | What is the meal cap per person for local client meetings? |
| ex-deadline | eval-employee@docwise.example.com | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.883 | When are monthly expense reports due? |
| ex-intl-approval | eval-employee@docwise.example.com | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.840 | How far ahead must international travel be approved by a VP? |
| ex-per-diem | eval-employee@docwise.example.com | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.861 | What is the international travel per diem? |
| ex-business-class | eval-employee@docwise.example.com | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.868 | When is a business class flight allowed? |
| ex-card-limit | eval-employee@docwise.example.com | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.927 | What is the company card limit for individual contributors? |
| eng-buddy | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.677 | How long is a new hire assigned a buddy? |
| eng-first-pr | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.725 | Within how many working days must a new engineer open their first pull request? |
| eng-python | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.922 | What is the default Python version for engineering? |
| eng-prod-approvers | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.920 | How many approvers are required for a production deploy? |
| eng-oncall | eval-employee@docwise.example.com | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.723 | After how many days does the on-call starter rotation begin? |
| acl-l3-band | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What is the individual contributor L3 salary band in USD? |
| acl-bonus-pct | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What percent of base salary is the annual performance bonus target? |
| acl-bonus-day | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | On what date is the performance bonus paid? |
| acl-ceo-multiplier | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What is the CEO cash bonus multiplier for this fiscal year? |
| acl-q4-revenue | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What was Q4 revenue in USD? |
| acl-headcount-freeze | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | Until which date is headcount frozen except for backfills? |
| acl-marketing-budget | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What is next quarter's marketing budget? |
| acl-promotion-packet-deadline | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | When are HR promotion packets due? |
| acl-retention-rsus | eval-employee@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | How long do retention RSUs vest for L4 and above? |
| acl-gross-margin | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What gross margin did Finance report for Q4? |
| acl-customer-concentration | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What share of ARR came from the largest customer? |
| acl-bad-debt-reserve | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | How much did Finance set aside for the bad debt reserve? |
| acl-board-pack-deadline | eval-employee@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | When is the Finance board meeting pack due? |
| acl-allowed-hr | eval-hr@docwise.example.com | positive | hr-compensation | hit | 0 | 1.000 | 1.000 | 0.874 | What is the individual contributor L3 salary band? |
| acl-allowed-finance | eval-finance@docwise.example.com | positive | finance-q4 | hit | 0 | 1.000 | 1.000 | 0.934 | What was the gross margin in Q4? |
| acl-allowed-legal | eval-legal@docwise.example.com | positive | legal-templates | hit | 0 | 1.000 | 1.000 | 0.729 | What does the contract-redline template require before external circulation? |
| acl-allowed-security | eval-security@docwise.example.com | positive | security-controls | hit | 0 | 1.000 | 1.000 | 0.741 | How soon must privileged credentials be rotated after suspected exposure? |
| acl-allowed-engineering | eval-engineering@docwise.example.com | positive | engineering-release | hit | 0 | 1.000 | 1.000 | 0.914 | How long is the production canary window? |
| acl-denied-employee-legal | eval-employee@docwise.example.com | acl_negative | legal-templates | miss | 0 | 1.000 | 1.000 | n/a | What does the contract-redline template require before external circulation? |
| acl-denied-employee-security | eval-employee@docwise.example.com | acl_negative | security-controls | miss | 0 | 1.000 | 1.000 | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| acl-denied-employee-engineering | eval-employee@docwise.example.com | acl_negative | engineering-release | miss | 0 | 1.000 | 1.000 | n/a | How long is the production canary window? |
| acl-matrix-hr-denies-finance | eval-hr@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What was the gross margin in Q4? |
| acl-matrix-hr-denies-legal | eval-hr@docwise.example.com | acl_negative | legal-templates | miss | 0 | 1.000 | 1.000 | n/a | What does the contract-redline template require before external circulation? |
| acl-matrix-hr-denies-security | eval-hr@docwise.example.com | acl_negative | security-controls | miss | 0 | 1.000 | 1.000 | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| acl-matrix-hr-denies-engineering | eval-hr@docwise.example.com | acl_negative | engineering-release | miss | 0 | 1.000 | 1.000 | n/a | How long is the production canary window? |
| acl-matrix-finance-denies-hr | eval-finance@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What is the individual contributor L3 salary band? |
| acl-matrix-finance-denies-legal | eval-finance@docwise.example.com | acl_negative | legal-templates | miss | 0 | 1.000 | 1.000 | n/a | What does the contract-redline template require before external circulation? |
| acl-matrix-finance-denies-security | eval-finance@docwise.example.com | acl_negative | security-controls | miss | 0 | 1.000 | 1.000 | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| acl-matrix-finance-denies-engineering | eval-finance@docwise.example.com | acl_negative | engineering-release | miss | 0 | 1.000 | 1.000 | n/a | How long is the production canary window? |
| acl-matrix-legal-denies-hr | eval-legal@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What is the individual contributor L3 salary band? |
| acl-matrix-legal-denies-finance | eval-legal@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What was the gross margin in Q4? |
| acl-matrix-legal-denies-security | eval-legal@docwise.example.com | acl_negative | security-controls | miss | 0 | 1.000 | 1.000 | n/a | How soon must privileged credentials be rotated after suspected exposure? |
| acl-matrix-legal-denies-engineering | eval-legal@docwise.example.com | acl_negative | engineering-release | miss | 0 | 1.000 | 1.000 | n/a | How long is the production canary window? |
| acl-matrix-security-denies-hr | eval-security@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What is the individual contributor L3 salary band? |
| acl-matrix-security-denies-finance | eval-security@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What was the gross margin in Q4? |
| acl-matrix-security-denies-legal | eval-security@docwise.example.com | acl_negative | legal-templates | miss | 0 | 1.000 | 1.000 | n/a | What does the contract-redline template require before external circulation? |
| acl-matrix-security-denies-engineering | eval-security@docwise.example.com | acl_negative | engineering-release | miss | 0 | 1.000 | 1.000 | n/a | How long is the production canary window? |
| acl-matrix-engineering-denies-hr | eval-engineering@docwise.example.com | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What is the individual contributor L3 salary band? |
| acl-matrix-engineering-denies-finance | eval-engineering@docwise.example.com | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What was the gross margin in Q4? |
| acl-matrix-engineering-denies-legal | eval-engineering@docwise.example.com | acl_negative | legal-templates | miss | 0 | 1.000 | 1.000 | n/a | What does the contract-redline template require before external circulation? |
| acl-matrix-engineering-denies-security | eval-engineering@docwise.example.com | acl_negative | security-controls | miss | 0 | 1.000 | 1.000 | n/a | How soon must privileged credentials be rotated after suspected exposure? |
