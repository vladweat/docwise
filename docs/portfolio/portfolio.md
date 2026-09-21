# Портфолио: что закрыть

Не roadmap продукта и не [milestones.md](../product/milestones.md). Цель — превратить уже собранный стенд (SQL-ACL, hybrid retrieval, цитаты страниц, eval) в **закрытый кейс**, который можно открыть за 90 секунд.

**Уровни A / B / C** (локальный DoD → interview-ready → abroad): канон в [portfolio-levels.md](portfolio-levels.md). Этот файл — чеклист **репозитория** (≈ уровень A + часть B).

**Уровень B в репо закрыт** (README narrative, dev billing/SSO в тексте, [portfolio-owner-tasks.md](portfolio-owner-tasks.md), [deploy-public-demo.md](deploy-public-demo.md)). Уровень **C** — только владелец (видео + публичный URL).

Критерий готовности: чужой человек проходит «зашёл → понял ценность → увидел ACL → кликнул цитату» без онбординга из ТЗ. Дальше фичи замораживаются.

## Сделать (порядок)

- [x] **1. Демо-сид** — org Demo, 12 PDF, employee / HR / admin, `make demo`.
- [x] **2. Сценарий ACL** — тот же вопрос про L3 salary: employee отказ; HR цитата. UI не объясняет, что файл скрыт.
- [x] **3. Онбординг в UI** — на localhost кнопки «Войти как сотрудник / HR / admin».
- [x] **4. Пустые и ошибочные состояния** — отказ без контекста, ingest `failed` + `last_error`, `402` тост, `/raw` 404 без утечки названия.
- [x] **5. README-витрина** — проблема, схема, цифры eval, команды, ACL-проход.
- [x] **5b. Скриншоты в README** — `docs/portfolio/screenshots/01`–`04`, галерея в README; regen: [screenshots/README.md](screenshots/README.md).
- [x] **6. Перегон eval после FTS** — `make eval` 2026-09-21 (Ragas + ACL PASS). Отчёт [reports/rag_benchmark.md](../reports/rag_benchmark.md).
- [x] **7. Inspect UI** — `/inspect` для org-admin; Compose `ENABLE_SEARCH_INSPECT=true`; prod по умолчанию выкл.
- [x] **8. 5 security-сценариев в README**.
- [x] **9. Визуальный удар** — подсветка сниппета на странице PDF по клику на цитату.
- [x] **10. Заморозка скоупа** — README «Out of scope».
- [ ] **11. Видео 60–90 с** — [portfolio-owner-tasks.md](portfolio-owner-tasks.md#c2--видео-6090-с).
- [ ] **12. Публичный стенд** — [deploy-public-demo.md](deploy-public-demo.md) + owner tasks.

Пункты **1–10** — репозиторий (все закрыты; п.6 — закоммитить отчёт при политике репо). **11–12** — вокруг репозитория (сценарий и чеклист в репо, исполнение — владелец).

## Кто делает

| # | Что | Агент в репо | Нужно от владельца |
| --- | --- | --- | --- |
| 1 | Сид, PDF, `make demo` | Да | Синтетические PDF, не реальные NDA |
| 2 | ACL-сценарий (UX/seed поверх существующего SQL) | Да | Проверить двумя логинами |
| 3 | Демо-вход на `/login` | Да | Текст аккаунтов |
| 4 | Empty/error UX | Да | Прокликать в браузере |
| 5 | README-витрина | Да | Язык витрины (EN сверху / RU ок) |
| 6 | `make eval` | Частично: запуск и правка отчёта | Живой LLM/эмбеддинги, поднятый Compose |
| 7 | Inspect UI (API уже есть) | Да | Не включать в prod без флага |
| 8 | Security-блок в README | Да | — |
| 9 | Подсветка PDF / sample export / DOCX ingest | Да | PDF highlight + `samples/documents/`; DOCX ingest + chat snippet (без Word-preview в KB) |
| 10 | Скоуп в README | Да | — |
| 11 | Видео | Сценарий в [portfolio-owner-tasks.md](portfolio-owner-tasks.md) | Запись и ссылка в README |
| 12 | Деплой в интернет | [deploy-public-demo.md](deploy-public-demo.md), `.env.example` § Public demo | Хостинг, DNS, ключ LLM, URL в README |

## Не делать для этой цели

Живой Stripe, настоящий SAML IdP заказчика, SCIM, RLS в Postgres, консоль оператора платформы, свои эмбеддинги, агенты с tool-calling, переписывание sync Session → asyncpg.

Код уже тянет на сильный backend+RAG кейс. Без сида, двух входов и видео он остаётся локальным стендом.

## Старт

`make up` → `make demo` → http://localhost:3001 → «Войти как сотрудник».
