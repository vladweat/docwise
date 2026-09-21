# DocWise — полноценное портфолио

**Сейчас:** продукт и локальный DoD **закрыты** ([career-kb.md](career-kb.md), [portfolio.md](portfolio.md)).  
**Полное портфолио** = чтобы рекрутер/инженер **без созвона** понял ценность и мог **увидеть** ACL+RAG (или за 60 с на видео).

Три уровня — не путать:

| Уровень | Для кого | Суть |
|---------|----------|------|
| **A. Локальный DoD** | мок, screen share | `make up` + `make demo` + EN README — **готово** |
| **B. Interview-ready** | отклики + интервью | A + свежий eval + стори S1b + цифры/скрины в README |
| **C. Full portfolio (abroad)** | LinkedIn, cold apply, EU/US | B + **одно** публичное демо **или** видео 60–90 с + упаковка кейса на EN |

M0–M6 в репо уже закрыты — это **код**, не замена уровня C.

---

## Уровень B — interview-ready (обязательный минимум перед откликами с DocWise)

### 1. Доказательство качества (eval)

- [x] `make up` → `make eval` на актуальной ветке (после FTS migration `012` — **перегнать**) — **2026-09-21**
- [x] `reports/rag_benchmark.md` обновлён и **закоммичен** (или ссылка в README на последний прогон — политика репо)
- [x] В README или eval note: **0** leaks `must_not_doc_ids`; Faithfulness ≥ 0.8 (если Ragas прогонялся)
- [x] 1 абзац «how we measure» + пример ACL-негатива (employee / L3 salary)

**Не обязательно:** Ragas в CI на каждый PR (дорого); достаточно ритуала перед волной откликов.

### 2. Упаковка репозитория (EN)

- [x] README: problem → **architecture diagram** → ACL SQL → hybrid pipeline → `make demo` (схема синхронизирована с `docs/architecture.md`, 2026-09-21)
- [x] Скриншоты (3–5): chat+citation, PDF highlight, ACL отказ, `/inspect` — `docs/screenshots/01`–`04`, галерея в README
- [x] «Not ChatPDF» / «Not ChainWise» — 2 буллета в README
- [ ] Badges: CI status (если публичный CI виден)
- [x] `.env.example` без секретов; quickstart ≤15 мин для reviewer (абзац в README + `.env.example`)

### 3. Карьерная упаковка (вне репо, но часть портфолио)

- [ ] CV/LinkedIn: 3–5 буллетов ([маркеры в career-kb](career-kb.md#11-резюме--интервью))
- [ ] Title: **Backend / Applied AI (RAG)** — не ML Engineer
- [ ] Стори **S1b** 2–3 мин без шпаргалки (личная KB: `interview/stories.md`)
- [ ] Демо-скрипт employee→hr прогнан на холодную 2–3 раза

### 4. Честные границы (написать вслух и в README)

- [x] DOCX ingest есть; честно: цитаты по разделу, без Word-preview в KB; eval golden пока PDF-only
- [ ] Live Stripe / live IdP — dev envelope only
- [ ] Нет публичного URL — ок **на моке**, не ок **в cold CV без видео**

**Критерий B:** можешь отправить ссылку на репо + сказать «цифры в rag_benchmark от DD.MM» + провести ACL live за 3 мин.

---

## Уровень C — full portfolio abroad (полноценно для холодного рынка)

Нужно **хотя бы одно** из двух (оба — идеал):

### Вариант C1 — Публичное демо (предпочтительно для B2B/AI)

- [ ] Деплой read-only/demo tenant (employee/hr логины **demo**, не прод-данные)
- [ ] HTTPS URL в README и LinkedIn
- [ ] Rate limit / cost cap на LLM
- [ ] Политика: что залито (синтетические PDF), disclaimer
- [ ] Smoke: ingest не обязателен публично — достаточно pre-seeded `make demo` data

**Инфра (вне кода):** хостинг, DNS, секреты LLM, возможно managed Postgres или один VPS + Compose.

### Вариант C2 — Видео 60–90 с (если стенд откладываешь)

- [ ] Screen recording: handbook → citation → PDF → salary отказ → hr OK
- [ ] EN voiceover или EN subtitles
- [ ] Залить (YouTube unlisted / Loom) — ссылка в README top
- [ ] Без утечки внутренних имён/ключей

### Общее для C

- [ ] GitHub pin + description EN one-liner
- [ ] Один **case study** блок (можно секция README «Portfolio narrative»): Problem / Approach / ACL / Results (metrics)
- [ ] Согласованность с Landlords/Puffins pinned — **не** три равных AI-флагмана на одном резюме

**Критерий C:** рекрутер за 2 минуты без твоего участия видит ACL+RAG; ты не стыдишься ссылки в cold message.

---

## Что НЕ нужно для «полного» портфолио (частые ловушки)

| Не делать | Почему |
|-----------|--------|
| Полноценный Word-viewer в UI | ingest есть; viewer — snippet + download |
| Qdrant / LangChain rewrite | ломает канон и стори |
| Live Stripe + prod IdP | out of scope; dev envelope достаточно |
| Platform admin / SCIM | не маркер middle RAG |
| Второй RAG-репо | решение KB — не зоопарк |
| Eval в CI на каждый push | опционально; ритуал перед откликами дешевле |
| Сайт-портфолио отдельный | KB: репо + README + demo/video достаточно |

---

## Порядок работ (практический)

```text
1. M12: make eval → rag_benchmark.md → абзац в README     [B]
2. Скриншоты + polish README                               [B]
3. S1b репетиция + CV bullets                              [B]
4. Видео 60–90 с  ИЛИ  публичный demo tenant               [C]
5. LinkedIn Featured + pin                                  [C]
```

Оценка усилий: **B** — в основном ритуалы и упаковка (код готов). **C** — один инфра/медиа проект, не новый продукт.

---

## Связь с планом KB (вне репо)

- Месяц 1 после DoD: M12 + теория + README других pinned (`strategy/plan-month-1.md`)
- Месяц 2: CV EN, **одно публичное демо**, карта компаний (`strategy/plan-3-months.md`)
- DocWise = pinned #2 AI; ChainWise — Also/стори, не дублировать narrative

---

## Чеклист «full portfolio закрыт»

Отметь, когда готово к холодным откликам с DocWise в центре:

- [ ] Уровень B полностью
- [ ] C1 **или** C2 выполнен
- [ ] Ссылка в CV/LinkedIn проверена с чужого браузера / без VPN-сюрпризов
- [ ] KB: статус в [career-kb.md](career-kb.md) обновлён на «portfolio B/C closed»

См. также операционный чеклист репозитория: [portfolio.md](portfolio.md) (пункты 1–12).
