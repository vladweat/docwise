# Локальная разработка

Этот документ описывает подтверждённый репозиторием Compose-сценарий. Архитектура и
ограничения среды — в [обзоре архитектуры](../product/architecture.md).

## Требования

- Docker с Compose plugin;
- Python 3.12 для подготовки backend virtualenv и локальных lint-проверок;
- Node.js 20 и npm для frontend;
- доступ в интернет на шаге `make deps`;
- ключ OpenAI-compatible API для генерации ответов. Индексация и retrieval-only проверки
  работают без ключа LLM.

Backend-зависимости устанавливаются по exact pins из `backend/requirements.lock`; исходные
ranges лежат в `backend/requirements.txt`. Точные frontend-версии зафиксированы в
`frontend/package-lock.json`. Сборка контейнеров выполняется с
`build.network: none`, поэтому зависимости и ONNX-модели подготавливаются на хосте заранее.

## Первый запуск

```bash
cp .env.example .env
# Задайте безопасный SECRET_KEY и, если нужен chat, OPENAI_API_KEY.
make deps
make up
curl -fsS http://localhost:8001/ready | python3 -m json.tool
make demo
```

Интерфейс доступен на `http://localhost:3001`, API — на `http://localhost:8001`.
MinIO API и console используют `9000` и `9001`; PostgreSQL и Redis — `5432` и `6379`.
Эти порты опубликованы Compose на хосте и не должны без firewall выставляться наружу.

`make up` собирает и запускает `postgres`, `redis`, `minio`, `backend`, `celery-worker`,
`celery-beat` и `frontend`. При старте backend автоматически выполняет `alembic upgrade head` и создаёт
закрытый bucket MinIO. Для явного запуска миграций после старта:

```bash
make migrate
```

`make demo` создаёт demo organization, три учётные записи и 12 PDF. Пароли и сценарий
проверки ACL приведены в корневом `README.md`; это только локальные тестовые данные.

## Быстрый цикл

Backend в Compose запущен с Uvicorn `--reload`. Worker не перезапускается автоматически:

```bash
make restart-worker
```

Для frontend без пересборки контейнера:

```bash
make deps-frontend
make up-fast
cd frontend
API_BASE_URL=http://localhost:8001 npm run dev
```

Dev server будет доступен на `http://localhost:3000`. Переменные `NEXT_PUBLIC_*` в
production image задаются во время build; изменение runtime environment без пересборки
образа не меняет встроенный URL.

## Проверки

```bash
make lint
make test-smoke
make test
make typecheck
make test-frontend
```

- `make lint` запускает Ruff и mypy через `backend/.venv`.
- `make test-smoke` и `make test` запускают pytest внутри работающего backend-контейнера.
- Pytest создаёт отдельную БД `docwise_test`; рабочая `docwise_db` не используется.
- `make typecheck` и `make test-frontend` выполняются на хосте в `frontend/`.
- Полная CI дополнительно запускает frontend lint/build и advisory `pip-audit`/`npm audit`.

Команды выше подтверждены по `Makefile` и CI. В ходе последнего аудита документации
runtime-стек не запускался; актуальный результат проверок фиксируется в
[аудите документации](../maintenance/documentation-audit.md).

## Сброс локальных данных

```bash
make demo-fresh
```

Повторно применяет миграции и demo seed, сохраняя volumes.

```bash
make demo-fresh-volumes
```

Удаляет Compose volumes PostgreSQL и MinIO. Команда необратима и предназначена только для
локальной среды. `make restore-drill` также разрушителен: он проверяет восстановление через
удаление volumes.

## Типовые проблемы

| Симптом | Проверка |
| --- | --- |
| `/health` отвечает, но приложение не готово | Используйте `/ready`: он проверяет PostgreSQL, pgvector, Redis, MinIO и billing adapter |
| Ingestion не меняет статус | `docker compose logs celery-worker`; после изменения worker-кода выполните `make restart-worker` |
| Ошибка модели FastEmbed | Повторите `make embeddings`; worker ожидает `backend/.models` как `/app/.models` |
| Chat не генерирует ответ | Проверьте `OPENAI_API_KEY`, а при custom gateway — `OPENAI_BASE_URL` и `OPENAI_MODEL` |
| Cookie auth не работает между `:3001` и `:8001` | Сверьте `COOKIE_SAMESITE`, `COOKIE_SECURE`, `CORS_ORIGINS` и используемый hostname |
| Endpoint inspect возвращает `404` | Проверьте `ENABLE_SEARCH_INSPECT`; в production он выключен по умолчанию |
| Миграция не применяется | Проверьте `docker compose logs db-migrate`; при ошибке миграции backend и worker не запустятся |

Остановка стека:

```bash
make down
```
