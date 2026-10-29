# RAG benchmark

> Historical snapshot for the 35-case golden set from 2026-09-22. The current dataset has 69 cases;
> this report has no recorded code revision or dataset digest and must not be quoted as a current result.

Generated: `2026-09-22T13:22:33+00:00`
Code revision: `unrecorded`
Golden dataset SHA-256: `unrecorded`
Eval user: `eval-employee@docwise.example.com` (role `employee`, departments `[]`)
Cases: 35 (28 positive, 7 ACL-negative)
Pipeline: hybrid `retrieve` → Top-4 → `build_messages` + `stream_openai` (retrieval + generation + Ragas judges)

Metrics follow Ragas definitions (Faithfulness, Context Precision, Answer Relevance) using the same OpenAI-compatible client as chat. LangChain is not used.

## Ragas (positive cases)

| Metric | Score | n |
| --- | ---: | ---: |
| Faithfulness | 1.000 | 28 |
| Context Precision | 0.994 | 28 |
| Answer Relevance | 0.776 | 28 |

Release gate (preliminary): Faithfulness ≥ 0.8 on the golden set.

## Retrieval

| Metric | Score | n |
| --- | ---: | ---: |
| Target document hit rate | 1.000 | 28 |
| Target page hit rate | 1.000 | 28 |

## ACL negatives

| Metric | Value |
| --- | --- |
| Cases | 7 |
| Cases with a `must_not_doc_ids` leak | **0** |
| Result | PASS |

Every golden item also lists HR/Finance ids in `must_not_doc_ids`. A leak is any Top-4 chunk from those documents. Restricted chunk text is not written here.

## Per-question

| id | kind | target doc | page | ACL leak | faith | ctx p | ans rel | question |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| hb-hours | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.949 | What are the core working hours at Docwise? |
| hb-lunch | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.860 | When is the unpaid lunch break? |
| hb-hybrid-office | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.545 | Which weekdays must employees come to the office under the hybrid policy? |
| hb-desk-booking | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.864 | By when must a desk be booked in the Places portal? |
| hb-personal-devices | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.449 | May employees store client personal data on personal devices? |
| hb-security-email | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.865 | Where should a security incident be reported, and how quickly? |
| hb-vendor-gifts | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.853 | What is the rule for gifts from vendors over 50 USD? |
| hb-warranty | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.384 | How long is the standard laptop warranty? |
| hb-badge-fee | positive | employee-handbook | hit | 0 | 1.000 | 1.000 | 0.904 | What is the replacement fee after the first lost badge? |
| lv-vacation-days | positive | leave-policy | hit | 0 | 1.000 | 0.833 | 0.859 | How many paid vacation days do employees get per calendar year? |
| lv-sick-days | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.861 | How many paid sick days are employees entitled to? |
| lv-notice | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.912 | How far in advance must vacation requests be submitted? |
| lv-parental | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.904 | How long is parental leave? |
| lv-carryover | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.456 | How many unused vacation days may be carried into the next year? |
| lv-bereavement | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.448 | How many paid bereavement leave days are provided? |
| lv-unpaid | positive | leave-policy | hit | 0 | 1.000 | 1.000 | 0.913 | Who must approve unpaid leave? |
| ex-taxi | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.872 | Do taxi receipts under forty dollars need a manager signature? |
| ex-meals | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.886 | What is the meal cap per person for local client meetings? |
| ex-deadline | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.921 | When are monthly expense reports due? |
| ex-intl-approval | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.433 | How far ahead must international travel be approved by a VP? |
| ex-per-diem | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.831 | What is the international travel per diem? |
| ex-business-class | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.851 | When is a business class flight allowed? |
| ex-card-limit | positive | expense-policy | hit | 0 | 1.000 | 1.000 | 0.938 | What is the company card limit for individual contributors? |
| eng-buddy | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.776 | How long is a new hire assigned a buddy? |
| eng-first-pr | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.912 | Within how many working days must a new engineer open their first pull request? |
| eng-python | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.941 | What is the default Python version for engineering? |
| eng-prod-approvers | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.502 | How many approvers are required for a production deploy? |
| eng-oncall | positive | engineering-onboarding | hit | 0 | 1.000 | 1.000 | 0.850 | After how many days does the on-call starter rotation begin? |
| acl-l3-band | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What is the individual contributor L3 salary band in USD? |
| acl-bonus-pct | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What percent of base salary is the annual performance bonus target? |
| acl-bonus-day | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | On what date is the performance bonus paid? |
| acl-ceo-multiplier | acl_negative | hr-compensation | miss | 0 | 1.000 | 1.000 | n/a | What is the CEO cash bonus multiplier for this fiscal year? |
| acl-q4-revenue | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What was Q4 revenue in USD? |
| acl-headcount-freeze | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | Until which date is headcount frozen except for backfills? |
| acl-marketing-budget | acl_negative | finance-q4 | miss | 0 | 1.000 | 1.000 | n/a | What is next quarter's marketing budget? |
