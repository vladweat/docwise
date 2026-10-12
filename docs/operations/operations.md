# Эксплуатация

Репозиторий поддерживает локальный/self-host pilot через Docker Compose. Полноценная
production-платформа, Kubernetes manifests, reverse proxy, TLS automation и secret manager
в публичном репозитории отсутствуют. Поэтому описанные ниже процедуры нельзя считать
готовым production deployment.

## Сервисы и запуск

| Сервис | Назначение | Host port | Проверка Compose |
| --- | --- | --- | --- |
| `postgres` | Данные и pgvector/FTS | `5432` | `pg_isready` |
| `redis` | Celery, sessions, rate limits, locks, LLM cache | `6379` | `redis-cli ping` |
| `minio` | Оригиналы документов | `9000`, console `9001` | MinIO live endpoint |
| `backend` | FastAPI | `8001` → `8000` | отдельного healthcheck нет |
| `celery-worker` | Ingestion | не публикуется | healthcheck нет |
| `frontend` | Next.js | `3001` → `3000` | healthcheck нет |

```bash
make deps
make up
curl -fsS http://localhost:8001/ready | python3 -m json.tool
```

`/health` проверяет только процесс. `/ready` проверяет PostgreSQL, extension pgvector, Redis,
MinIO/bucket и billing adapter; при деградации возвращает `503`.

Startup backend выполняет миграции и проверяет MinIO. При нескольких API replicas нет
leader election для Alembic, поэтому одновременный startup создаёт риск конкурирующих
миграций. Compose предназначен для одной backend replica.

## Deployment-факты и ограничения

- Backend и frontend images собираются без сети и с `pull_policy: never`; чистому хосту
  предварительно нужны `make deps` и локальные build inputs.
- Compose запускает backend с `--reload` и bind-mount исходников — это dev-профиль.
- Frontend `NEXT_PUBLIC_*` встраиваются во время build; смена API URL требует rebuild.
- PostgreSQL, Redis и MinIO опубликованы на host interfaces без TLS. Ограничьте доступ
  firewall или измените Compose перед внешним размещением.
- В Compose используются placeholder credentials. Их необходимо заменить.
- Для настоящего RLS необходима non-superuser DB role и `DOCWISE_RLS_SESSION_ROLE`; готовая
  production-настройка в репозитории отсутствует.
- Worker зависит от факта старта backend, а не от `/ready`; cold start может потребовать
  повторной проверки очереди и failed documents.

## Миграции

Применение выполняется автоматически через `app.core.lifespan.lifespan` либо вручную:

```bash
make migrate
```

Alembic chain находится в `backend/alembic/versions/`; текущий head — миграция
`015_row_level_security.py`. Откат миграций и blue/green strategy не автоматизированы.
Перед изменением версии приложения создайте backup и проверьте restore на совместимой версии.

## Логи и наблюдаемость

```bash
make logs
make logs-frontend
docker compose logs celery-worker
```

Backend пишет структурированные JSON-логи с redaction в `app.core.logging`. Sentry включается
через `SENTRY_DSN`; тела запросов и чувствительные ключи scrubbed. Prometheus, OpenTelemetry,
централизованное хранение логов и dashboard в репозитории не реализованы.

Pilot-проверки:

```bash
make check-pilot-alerts
```

Скрипт проверяет `/ready`, Redis queue key `celery`, число failed documents и p95 latency по
`rag_audit_logs` за 24 часа. p95 выдаёт warning, а `LLEN celery` является эвристикой и может
не отражать очередь при другой Celery routing configuration.

## Ingestion worker

Единственная задача — `ingestion.process_document`. Worker использует `acks_late`,
`task_reject_on_worker_lost`, prefetch `1`, soft/hard limits 20/25 минут и до трёх retry с
backoff. `SoftTimeLimitExceeded` и `TimeLimitExceeded` автоматически не повторяются.

После изменения `backend/app/services/ingestion/` или `backend/worker/`:

```bash
make restart-worker
```

При расследовании проверьте:

1. `docker compose logs celery-worker`;
2. status и `ingestion_stage` документа;
3. доступность Redis и MinIO;
4. наличие `backend/.models`;
5. lock `indexing_lock:{document_id}`;
6. page quota организации.

Retry повторно удаляет и записывает chunks, однако вся обработка не является одной
транзакцией: статусы/stages фиксируются отдельными commit. Не называйте задачу строго
идемпотентной при внешних сбоях.

## Backup

```bash
make backup-pilot
```

`ops/backup-pilot.sh` создаёт `pg_dump -Fc` и mirror MinIO в
`backups/<timestamp>/`, затем обновляет `backups/pilot-latest`. Каталог исключён из Git.
Backup не включает Redis: теряются queued/in-flight tasks, refresh sessions, locks, rate
limit counters и LLM cache. После восстановления найдите документы, оставшиеся в
`pending`/`processing`, и определите безопасную повторную постановку вручную.

## Restore

```bash
make restore-pilot BACKUP_DIR=backups/pilot-latest
```

Скрипт останавливает writers, пересоздаёт БД, выполняет `pg_restore`, зеркалирует MinIO,
запускает Compose и ожидает `/ready`. Это разрушительная операция. Вариант
`make restore-drill` дополнительно удаляет volumes и разрешён только в изолированной local
среде.

Ограничения:

- совместимость dump и версии кода автоматически не проверяется;
- Redis не восстанавливается;
- point-in-time recovery не настроен;
- нет off-site replication, encryption policy и автоматического расписания;
- RPO/RTO не определены публичной конфигурацией.

## Согласование MinIO и PostgreSQL

```bash
make reconcile-minio
make reconcile-minio DELETE=1
```

Первая команда — dry-run. Вторая удаляет только объекты без ссылок из
`documents.file_path`; отсутствующие объекты не восстанавливаются. Перед `DELETE=1`
сделайте backup.

## Rollback

Подтверждённого автоматического rollback нет. Безопасный общий порядок:

1. остановить writers;
2. сохранить DB/MinIO backup;
3. вернуть совместимую версию image/source;
4. восстановить backup, если новая миграция необратима;
5. проверить `/ready`, login, upload/ingestion и ACL retrieval.

Это рамка, а не проверенный production runbook: конкретная совместимость зависит от
миграции и версии backup.
