# Портфолио — задачи владельца (вне агента)

Репозиторий закрывает **уровень B** (README, eval, скрины, границы M6). Этот файл — всё, что **только ты** делаешь для **уровня C** и карьерной упаковки.

Канон уровней: [portfolio-levels.md](portfolio-levels.md). Чеклист репо: [portfolio.md](portfolio.md). Деплой C1: [deploy-public-demo.md](deploy-public-demo.md).

---

## Критерий «портфолио полностью закрыто»

- [ ] Уровень **B** в репо (README narrative, dev billing/SSO в тексте, owner-файл и deploy-guide на месте).
- [ ] **C1:** HTTPS URL публичного demo в [README.md](../README.md) (блок Live demo).
- [ ] **C2:** ссылка на видео 60–90 с в README (блок Walkthrough video).
- [ ] Демо-скрипт employee → HR (salary) прогнан **на холодную 2–3 раза** (см. § Сценарий видео).
- [ ] Стори **S1b** 2–3 мин без шпаргалки (личная KB: `interview/stories.md`, если есть).
- [ ] Статус в [career-kb.md](career-kb.md) §1 обновлён на «portfolio B/C closed».

**Не входит в критерий:** live Stripe, живой SAML IdP, SCIM — см. README «Out of scope».

---

## C2 — видео 60–90 с

**Цель:** рекрутер без `make up` видит ACL + цитату + PDF.

| Время | Действие | Голос / субтитры (EN) |
| --- | --- | --- |
| 0–15 с | Login → **Войти как сотрудник** (или demo employee на публичном стенде) | «Enterprise RAG with SQL access control before the LLM.» |
| 15–30 с | Вопрос: *What are the core working hours at Docwise?* → ответ с цитатией → **клик** → PDF + подсветка | «Grounded answer with page citation.» |
| 30–45 с | Тот же пользователь: *What is the individual contributor L3 salary band in USD?* → **отказ** (без намёка на скрытый файл) | «HR-only chunks never reach the model for this employee.» |
| 45–65 с | Logout → **HR** → тот же salary-вопрос → цифры + цитата `HR-Compensation.pdf` | «Same question, HR role — allowed document in context.» |
| 65–90 с | (Опционально) admin → `/inspect` 5 с, без compensation если у admin нет `hr` | «Hybrid dense + FTS, same SQL filters as chat.» |

**Перед записью**

- `make up` → `make demo`; закрой вкладки с `.env`, терминалом с ключами, личными именами.
- Разрешение 1920×1080 или 1280×720; курсор не дёргать лишний раз.
- EN voiceover **или** EN subtitles (холодный EU/US рынок).

**После**

- Залить: YouTube **Unlisted** или Loom.
- В README заменить `TBD` в **Walkthrough video** на URL.
- В описании видео: synthetic PDFs, portfolio demo, ссылка на GitHub (когда репо публичный).

---

## C1 — публичный HTTPS demo

Пошагово: [deploy-public-demo.md](deploy-public-demo.md).

Краткий чеклист:

- [ ] VPS + Docker Compose, TLS (Caddy/Traefik/nginx).
- [ ] Сильные секреты; `ENVIRONMENT=production`, `BILLING_PROVIDER=dev`, `SSO_PROVIDER=dev`.
- [ ] `NEXT_PUBLIC_SHOW_DEMO_LOGINS=true` (demo-кнопки; регистрация скрыта в UI).
- [ ] `ENABLE_SEARCH_INSPECT=false` на публичном demo (по умолчанию в production).
- [ ] `make demo` на сервере; smoke: employee salary refuse, HR salary OK.
- [ ] Лимиты: `RATE_LIMIT_CHAT_PER_MINUTE`, квоты starter org — см. `.env.example` § Public demo.
- [ ] Disclaimer в README: только синтетические PDF из `eval/` / `samples/`, не прод-данные.

В README заменить `TBD` в **Live demo** на `https://…`.

---

## GitHub

- [ ] Создать **public** репозиторий, `git remote add origin …`, push `main`.
- [ ] В [README.md](../README.md) заменить `OWNER/REPO` в CI badge на реальный путь.
- [ ] Pin репозиторий; description EN one-liner (например: *Permission-aware enterprise RAG: hybrid pgvector+FTS, SQL ACL, PDF citations*).
- [ ] Проверить, что Actions зелёные на `main`.

---

## Вне репо (уровень B, карьера)

- [ ] CV / LinkedIn: 3–5 буллетов — [career-kb.md §11](career-kb.md#11-резюме--интервью).
- [ ] Title: **Backend / Applied AI (RAG)** — не ML Engineer.
- [ ] LinkedIn Featured: репо + видео + (если есть) live demo URL.
- [ ] Согласованность с другими pinned-проектами — не три равных AI-флагмана на одном резюме.

---

## Что не делать

| Не делать | Почему |
| --- | --- |
| Live Stripe / prod IdP | Out of scope; dev envelope достаточно для портфолио |
| Открытая регистрация на публичном demo | Риск абьюза и LLM-расходов (UI скрывает register при `NEXT_PUBLIC_SHOW_DEMO_LOGINS=true`) |
| NDA / реальные корпоративные PDF в demo | Только синтетика из репо |

---

## После закрытия

1. Отметить чеклисты в [portfolio-levels.md](portfolio-levels.md) (секции C и «full portfolio закрыт»).
2. Обновить [career-kb.md](career-kb.md) §1 (публичный URL, дата eval, ссылка на видео — без обязательного URL репо в KB, если политика KB прежняя).
