# Соглашения репозитория

## Каталоги (целевые)

```
docwise/
  backend/
    app/                 # FastAPI
      api/v1/            # HTTP-адаптер: один модуль на ресурс
      api/health.py      # /health, /ready — без /api/v1
      core/              # процесс: config, DB, JWT, cookies, CSRF, Redis, rate limit, logging
      models/            # ORM, один файл на агрегат
      schemas/           # Pydantic; import из модуля ресурса, не из бочки
      services/          # домен по подпакетам: `billing/`, `chat/`, `documents/`, `ingestion/`, `retrieval/`, `org/`; общие `storage.py`, `text.py`
    worker/              # Celery app + tasks (`worker.celery_app`)
    alembic/
    tests/
  frontend/              # Next.js App Router
    src/
      app/               # RSC-маршруты и metadata; клиентские острова из features/
      features/          # chat, documents, settings, auth, inspect, health — UI + сторы фичи
      components/        # shell (header, providers) + shadcn `ui/`
      lib/               # `api/` (client + ресурсы), format, quota, ACL helpers; barrel `lib/api.ts`
      stores/            # общее UI-состояние (toast)
      types/             # контракты API (как Pydantic)
  eval/
  docs/                  # README.md + product/, platform/, pipeline/, engineering/, portfolio/, meta/
  reports/               # gitignore кроме rag_benchmark.md — по желанию
  .cursor/rules/
  docker-compose.yml
  AGENTS.md
  README.md
```

### Слои backend

| Слой | Что входит | Что нет |
| --- | --- | --- |
| `core/` | Инфра процесса: settings, Session, JWT/cookies/CSRF, Redis-клиент и lock, rate limit, JSON-логи, Sentry, lifespan/middleware | Доменные правила, ORM-агрегаты |
| `services/` | Подпакеты: `documents/`, `chat/` (LLM, SSE, cache), `ingestion/` (parse, chunk, embed), `retrieval/` (hybrid, inspect, audit), `org/` (tenancy, domains, SSO, quotas), `billing/`. Middleware **может** звать `org.domains` / `org.sso`. Ошибки домена — `AppError` (`core/errors.py`); сервисы не кидают `HTTPException`. | HTTPException в доменном слое |
| `api/v1/` | Парсинг запроса, auth deps, вызов сервиса. Имя модуля = ресурс URL. Auth — пакет `auth/` (password / Google / session; `issue.py` — Set-Cookie, не маршрут) | Тяжёлый парсинг PDF |
| `models/` | Один агрегат на файл (`organization`, `sso`, `domain`, `billing`, `audit`, `chat`, `document`, `user`) | Схемы HTTP |
| `worker/` | Celery-обёртка задачи. Домен — в `services.ingestion` | Копировать `tests/` в прод-образ |

`utils/` нет: Redis и rate limit — `core/`. Сервис документа — `services/documents/` (как `api/v1/documents.py`). Inspect — `services/retrieval/inspect.py` (как `api/v1/search.py`); гибридный поиск чата — `services/retrieval/` (sparse — Postgres FTS; `bm25_scores` только для unit-тестов). Выдача cookie-сессии — `api/v1/auth/issue.py`, не отдельный HTTP-ресурс. Общие строки: `services/text.py` (`ingest_tokens` для бюджета чанка, `lexical_tokens` для лексики/тестов, `normalize_role_tags` для ACL и departments).

### Слои frontend

| Слой | Что входит | Что нет |
| --- | --- | --- |
| `app/` | RSC-маршрут, `metadata`, сборка островов | `"use client"` на `page.tsx` |
| `features/` | Экран фичи, её Zustand, узкие helpers (`chat/lib`) | Общий `api.ts`, shadcn |
| `components/ui` | shadcn/Radix-примитивы | Вёрстка страниц |
| `lib/` | `api.ts`, `sse.ts`, format, quota, ACL helpers | Парсеры SSE внутри экрана чата |

Каркас взят из `../chainwise` ([reuse-from-chainwise.md](../engineering/reuse-from-chainwise.md) — карта порта, не backlog). Не копировать `slither/`, `semantic_splitter.py`, `rag_engine` целиком. Sparse в коде — Postgres FTS (ADR-005), не BM25 по пулу в RAM.

## Язык

- Код, идентификаторы API, комментарии в коде: английский.
- Пользовательские строки UI и отказы LLM: русский или английский — один язык интерфейса на инстанс (i18n не обязателен в v1).
- Рабочие `docs/*`: русский. Портфолио-README в конце M4: английский.
- Источник истины: [srs.md](../product/srs.md) (продукт), [tenancy.md](../platform/tenancy.md) (организации), [billing.md](../platform/billing.md) (планы/квоты), [decisions.md](../engineering/decisions.md) (техника), [api.md](../engineering/api.md) (HTTP).

## Git и секреты

- Не коммитить `.env`, ключи LLM, дампы MinIO с реальными NDA.
- Пример конфигурации: `.env.example`.
- Коммиты — по запросу владельца репозитория; сообщения в императиве, с фокусом на «зачем».

## Качество кода

- Backend: ruff (`make lint` / CI), типы, pytest. Парсинг PDF только в Celery. ORM — sync Session.
- Frontend: TypeScript strict, компоненты shadcn (`components/ui`), без `any` в API-слое. Маршруты — RSC; интерактив — `features/`.
- Изменение контракта API = обновление `docs/engineering/api.md` в том же изменении.
- Изменение инварианта RAG/ACL = обновление `docs/` и `.cursor/rules/`.
- Новая продуктовая фича вне SRS = сначала правка [srs.md](../product/srs.md) / [decisions.md](../engineering/decisions.md).

## Что не делать

- Наивный chunker по символам «временно».
- ACL только в системном промпте.
- Подмена стека (LangChain как ядро, другой векторный движок) без явной просьбы.
- Переписывание всего backend на asyncpg «заодно» с портом.
- Retrieval через `SELECT` всех чанков в RAM (паттерн одного контракта в ChainWise).
- Публичные ссылки на PDF без проверки прав.
