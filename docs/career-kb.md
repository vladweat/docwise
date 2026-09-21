# Docwise — карьерная база знаний

Снимок фактов по репозиторию. Не выдумывать: при расхождении с кодом править этот файл и `docs/decisions.md`. Продуктовая спека: [srs.md](srs.md). Дорожная карта репо: [milestones.md](milestones.md) (M0–M6).

## Решения владельца KB (зафиксировано)

| Тема | Решение |
| --- | --- |
| URL репозитория в KB | не указывать |
| Как описывать retrieval / ACL | **Postgres pgvector + FTS + SQL ACL** (не Qdrant, не payload-фильтр в отдельном vector DB) |
| Шкалы вех | **две**: личный DoD M1–M12 (месяц «можно показать») и **M0–M6** в репо — не сливать |
| Прод / пилот у заказчика | в KB **не** выделять (сейчас нет) |
| Перед интервью | перегнать `make eval` при изменении RAG; последний прогон **2026-09-21** — [reports/rag_benchmark.md](../reports/rag_benchmark.md) |
| Видео 60–90 с, публичный стенд | **в планах** (уровень C — [portfolio-levels.md](portfolio-levels.md)) |
| Уровни портфолио A/B/C | [portfolio-levels.md](portfolio-levels.md); статус B/C — см. чеклист в конце файла |
| Роли в демо | достаточно **employee / hr / admin** (manager в скрипт не включать) |

---

## 1. Статус

- **Путь:** `/home/lzvw/projects/docwise`, ветка `main`
- **Стадия:** уровень **A** закрыт (`make up` + `make demo`); **B/C** — [portfolio-levels.md](portfolio-levels.md); операционный чеклист — [portfolio.md](portfolio.md)
- **Публичный URL / прод:** нет

**E2E (при поднятом Compose и `OPENAI_API_KEY`):** PDF upload → Celery ingest → hybrid search (pgvector + FTS, RRF k=60, rerank) → SSE chat с цитатами → клик → PDF страница + подсветка; list/raw/chat/inspect с `organization_id` + `access_roles`.

**Не работает / вне скоупа:** DOCX ingest, Qdrant, LangChain, Bearer-auth, live Stripe / live IdP, публичный хост, platform admin с чтением чужих корпусов.

---

## 2. Продукт

- **EN:** Permission-aware enterprise RAG over PDF: SQL-scoped hybrid search, reranking, page-exact citations — multi-tenant B2B on one stack.
- **RU:** Корпоративный RAG по PDF: изоляция org + роли на SQL до LLM, гибридный поиск, цитаты на страницу.

**JTBD:** сотрудник ищет ответ в регламентах и проверяет по оригиналу PDF; admin/manager ведут KB с ACL.

**Не является:** ChatPDF без ACL, naive char-split RAG, ChainWise (Solidity/Qdrant one-contract), готовый коммерческий прод.

---

## 3. Scope (кратко)

| Область | Статус |
| --- | --- |
| PDF ingest | есть |
| DOCX | нет (только в SRS как желательно) |
| Chunking | страница/секция, 400–600 tok, overlap 50 внутри страницы |
| Embeddings | FastEmbed `bge-small-en-v1.5`, 384d |
| Hybrid | dense pgvector + Postgres FTS Top-25 each → RRF **k=60** |
| Rerank | `bge-reranker-base`, порог 0.25, Top-4 |
| Цитаты | `doc_id`, `doc_title`, `page`, `snippet` (SSE до токенов) |
| ACL | **pre-retrieval SQL** на documents/chunks (+ org_id) |
| Multi-tenant | есть (`organizations`, memberships) |
| Auth | cookies `dw_*` (JWT внутри), Google, dev SSO |
| UI | chat split-pane, PDF viewer, KB admin, settings (billing/sso/domain dev) |
| Eval | golden 35 кейсов; CI без eval; отчёт в `reports/` |
| CI | ruff, mypy, pytest, frontend tsc/vitest/lint/build |

---

## 4. Архитектура (факт)

API (sync FastAPI) + Celery worker + Postgres 15 pgvector + Redis + MinIO + Next.js 15. **Qdrant нет.**

ChainWise: переиспользована обвязка (auth, Celery, SSE, Compose-паттерн, RRF-формула); retrieval/ingest — свои, corpus-wide SQL ACL.

Поток: upload → MinIO + `documents` → worker parse/chunk/embed → `document_chunks` → query → ACL SQL → hybrid → rerank → LLM stream + audit (chunk UUIDs, без текста restricted).

---

## 5. ACL (канон для интервью)

```sql
WHERE organization_id = :current_org
  AND access_roles && :allowed_roles
```

`allowed_roles = {membership.role} ∪ departments ∪ {all}`. Тег `all` — все в **этой org**, не весь SaaS. Без доступа: нет в list; `/raw` и чужой tenant → **404** без title; chat — отказ без «файл скрыт».

**Демо:** `make demo` — employee (8× `all`), hr (+ HR PDF), admin (тот же retrieval ACL что membership); `Finance-Q4-Memo.pdf` — только `finance`.

---

## 6. Стек

Python 3.12, FastAPI, SQLAlchemy sync, Celery 5, Redis 7, Postgres `pgvector/pgvector:pg15`, MinIO, fastembed, httpx → LLM, Next.js 15 / React 19 / Tailwind 4 / pdfjs-dist 4.10. Compose: `BILLING_PROVIDER=dev`, `SSO_PROVIDER=dev`.

---

## 7. Две шкалы вех

### Личный DoD M1–M12 (месяц «можно показать»)

| ID | Пункт | Статус |
| --- | --- | --- |
| M1 | PDF ingest | готово |
| M2 | DOCX | не начато |
| M3 | hybrid + RRF | готово (FTS, не Qdrant BM25) |
| M3b | rerank | готово |
| M4 | citations / grounded refuse | готово |
| M5 | ACL retrieval | готово |
| M6 | chat UI | готово |
| M7 | PDF jump + highlight | готово |
| M8 | auth + ≥2 роли | готово (employee, hr, admin) |
| M9 | демо-данные | готово (`make demo`) |
| M10 | happy-path в README | готово |
| M11 | EN README | готово |
| M12 | eval note | готово — прогон **2026-09-21** (post-`012`); Faithfulness 1.0, ACL 0 leaks |

### Репозиторий M0–M6

Все критерии закрыты в [milestones.md](milestones.md), включая shared tenancy и commercial dev-envelope (планы, квоты, SSO/domain dev).

---

## 8. Eval

- Dataset: `eval/golden_dataset.json` (35 кейсов).
- Запуск: `make up` → `make eval` (нужен LLM key; `--seed` индексирует фикстуры).
- Gate: **0** leaks `must_not_doc_ids`; Faithfulness ≥ 0.8 (Ragas при полном прогоне).
- Последний прогон: **2026-09-21** — Faithfulness **1.000**, Context Precision **0.994**, Answer Relevance **0.725**, page hit **0.929**, ACL **0** / PASS ([reports/rag_benchmark.md](../reports/rag_benchmark.md)).

Пример ACL-негатива: employee спрашивает L3 salary → golden `acl-l3-band`, HR chunks не в Top-4; hr в демо → диапазон из `HR-Compensation.pdf`.

---

## 9. Демо 2–3 мин (employee → hr)

1. Employee: часы работы → цитата handbook → клик PDF.
2. Employee: L3 salary → отказ.
3. HR: тот же salary → ответ с цифрами + цитата.
4. (Опционально) admin `/inspect` — стадии dense/FTS/RRF/rerank; без `hr` в membership compensation не виден.

Логины: [README.md](../README.md) § Run the demo.

---

## 10. Планы (вне кода)

Уровни **B** (eval ritual, README polish, S1b) и **C** (C1 публичный demo **или** C2 видео): [portfolio-levels.md](portfolio-levels.md).

- Видео 60–90 с (screen recording) — C2.
- Публичный стенд (хостинг, DNS, ключ LLM) — C1.

---

## 11. Резюме / интервью

- **Postgres pgvector + FTS + SQL ACL** до LLM, multi-tenant `org_id`.
- Page-bounded chunking, таблицы Markdown, hybrid + RRF + cross-encoder.
- SSE citations-first, PDF page citations, golden eval с ACL-негативами.
- От ChainWise: та же обвязка, **другой** retrieval (корпус + SQL, не Qdrant one-contract).
- Обещать на моке: ACL walkthrough, inspect, CI guardrails, локальный demo.
- После `make eval` актуального: цифры Faithfulness / page hit из `rag_benchmark.md`.

---

## 12. Out of scope

Live Stripe/IdP, SCIM, platform operator corpus, RLS вместо SQL ACL, DOCX v1, LangChain, Qdrant, asyncpg rewrite.
