# Инструкции для coding agents

## Навигация

- Backend: `backend/app/`; точка входа — `app.main:app`.
- HTTP API: `backend/app/api/`; схемы — `backend/app/schemas/`.
- Модели и миграции: `backend/app/models/`, `backend/alembic/versions/`.
- Ingestion worker: `backend/worker/celery_app.py`, `backend/app/services/ingestion/`.
- Retrieval и chat: `backend/app/services/retrieval/`, `backend/app/services/chat/`.
- Frontend: `frontend/src/`; App Router — `frontend/src/app/`.
- Документация: начните с `docs/README.md`.

## Неподлежащие нарушению границы

- `organization_id` берётся только из аутентифицированной сессии или доверенной записи БД.
- Dense и FTS-запросы фильтруются по `organization_id` и `access_roles` до RRF, rerank и LLM.
- Не считайте RLS активной защитой, пока runtime использует PostgreSQL superuser без
  `DOCWISE_RLS_SESSION_ROLE`.
- Не передавайте содержимое недоступных chunks в prompt, cache, audit или ошибки.
- Изменение ORM-моделей требует новой Alembic-миграции; существующие миграции не переписываются.
- Изменения ingestion-кода требуют перезапуска `celery-worker`.

## Проверки

```bash
make lint
make test-smoke
make test
make typecheck
make test-frontend
```

Команды `make test*` требуют запущенного Compose backend. `make lint` использует
`backend/.venv`, frontend-проверки — установленные `frontend/node_modules`.
Изменения retrieval, prompt, ACL или chunking дополнительно проверяйте через
`make eval-retrieval` или `make eval` при наличии нужной инфраструктуры и ключа LLM.

## Документация и безопасность

- Проверяйте утверждения по коду, миграциям, тестам и конфигурации.
- Сохраняйте English-имена символов, API и переменных; основной текст пишите по-русски.
- Не включайте секреты, дампы, документы пользователей и содержимое `.env`.
- При изменении маршрутов, конфигурации или операций синхронизируйте соответствующий документ
  и `docs/maintenance/documentation-audit.md`.
