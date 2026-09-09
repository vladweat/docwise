# Соглашения репозитория

## Каталоги (целевые)

```
docwise/
  backend/
    app/                 # FastAPI: api, models, schemas, services
    worker/              # Celery app + tasks (можно держать в app/)
    alembic/
    tests/
  frontend/              # Next.js App Router
  eval/
  docs/
  reports/               # gitignore кроме rag_benchmark.md — по желанию
  .cursor/rules/
  docker-compose.yml
  AGENTS.md
  README.md
```

Код в v1 появляется **форком** `../chainwise` (см. [reuse-from-chainwise.md](reuse-from-chainwise.md)), а не пустыми пакетами. Не копировать `slither/`, `semantic_splitter.py`, `rag_engine` целиком.

## Язык

- Код, идентификаторы API, комментарии в коде: английский.
- Пользовательские строки UI и отказы LLM: русский или английский — один язык интерфейса на инстанс (i18n не обязателен в v1).
- Рабочие `docs/*`: русский. Портфолио-README в конце M4: английский.
- Источник истины: [srs.md](srs.md) (продукт), [decisions.md](decisions.md) (техника v1), [api.md](api.md) (HTTP).

## Git и секреты

- Не коммитить `.env`, ключи LLM, дампы MinIO с реальными NDA.
- Пример конфигурации: `.env.example`.
- Коммиты — по запросу владельца репозитория; сообщения в императиве, с фокусом на «зачем».

## Качество кода

- Backend: ruff или flake8 как в ChainWise на первом порте, типы, pytest. Парсинг PDF только в Celery. ORM — sync Session.
- Frontend: TypeScript strict, компоненты shadcn, без `any` в API-слое.
- Изменение контракта API = обновление `docs/api.md` в том же изменении.
- Изменение инварианта RAG/ACL = обновление `docs/` и `.cursor/rules/`.
- Новая продуктовая фича вне SRS = сначала правка [srs.md](srs.md) / [decisions.md](decisions.md).

## Что не делать

- Наивный chunker по символам «временно».
- ACL только в системном промпте.
- Подмена стека (LangChain как ядро, другой векторный движок) без явной просьбы.
- Переписывание всего backend на asyncpg «заодно» с портом.
- Retrieval через `SELECT` всех чанков в RAM (паттерн одного контракта в ChainWise).
- Публичные ссылки на PDF без проверки прав.
