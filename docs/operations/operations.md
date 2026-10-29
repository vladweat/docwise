# Эксплуатация

Репозиторий поддерживает локальный/self-host pilot через Docker Compose. Для публичного
интервью-демо см. [отдельный профиль](public-demo.md): он добавляет Caddy и автоматический
TLS, но не является отказоустойчивой production-платформой. Kubernetes manifests, secret
manager и production-grade HA в публичном репозитории отсутствуют; описанные ниже процедуры
не следует считать готовым production deployment.

## Сервисы и запуск

| Сервис | Назначение | Host port | Проверка Compose |
| --- | --- | --- | --- |
| `postgres` | Данные и pgvector/FTS | `127.0.0.1:5432` | `pg_isready` |
| `redis` | Celery, sessions, rate limits, locks, LLM cache | `127.0.0.1:6379` | `redis-cli ping` |
| `minio` | Оригиналы документов | `127.0.0.1:9000`, console `9001` | S3 bucket readiness |
| `backend` | FastAPI | `127.0.0.1:8001` → `8000` | отдельного healthcheck нет в base profile |
| `celery-worker` | Ingestion | не публикуется | Celery ping healthcheck |
| `celery-beat` | Scheduled cleanup jobs | не публикуется | singleton service; health через worker checks |
| `frontend` | Next.js | `127.0.0.1:3001` → `3000` | healthcheck в public profile |
| `db-migrate` | Однократная роль RLS и Alembic upgrade | не публикуется | должен завершиться до API/worker |

```bash
make deps
make up
curl -fsS http://localhost:8001/ready | python3 -m json.tool
```

`/health` проверяет только процесс. `/ready` проверяет PostgreSQL, extension pgvector, Redis,
MinIO/bucket и billing adapter; при деградации возвращает `503`.

В локальном Compose `minio` — MinIO. Публичный профиль использует то же имя сервиса для
Garage; подробности и S3 compatibility ограничения описаны в
[`public-demo.md`](public-demo.md).

Compose запускает единственный `db-migrate` до backend и worker. Он гарантирует grants для
`docwise_rls`, затем применяет Alembic; ошибка миграции блокирует запуск зависимых сервисов.
Вне Compose deployment должен запускать migration job отдельно до масштабирования API.

## Deployment-факты и ограничения

- Backend и frontend images собираются без сети и с `pull_policy: never`; чистому хосту
  предварительно нужны `make deps` и локальные build inputs.
- Compose запускает backend с `--reload` и bind-mount исходников — это dev-профиль.
- Frontend `API_BASE_URL` читается при runtime; смена API URL не требует rebuild image.
- Base Compose публикует host ports только на `127.0.0.1`; public-demo не публикует
  PostgreSQL, Redis, object storage, API или frontend ports и использует Caddy ingress.
- В Compose используются placeholder credentials. Их необходимо заменить.
- Runtime API, worker и Beat используют `SET LOCAL ROLE docwise_rls`; migration service
  создаёт роль и grants перед schema upgrade.
- Worker healthcheck выполняет Celery ping; readiness API всё ещё отдельно проверяется по
  `/ready`.

## Миграции

Применение выполняет выделенный Compose service либо вручную:

```bash
make migrate
```

Alembic chain находится в `backend/alembic/versions/`; текущий head — миграция
`017_storage_deletion_outbox.py`. Откат миграций и blue/green strategy не автоматизированы.
Перед изменением версии приложения создайте backup и проверьте restore на совместимой версии.

## Логи и наблюдаемость

```bash
make logs
make logs-frontend
docker compose logs celery-worker
docker compose logs celery-beat
```

Backend пишет структурированные JSON-логи с redaction в `app.core.logging`. Sentry включается
через `SENTRY_DSN`; тела запросов и чувствительные ключи scrubbed. Prometheus, OpenTelemetry,
централизованное хранение логов и dashboard в репозитории не реализованы.

Pilot-проверки:

```bash
make check-pilot-alerts
```

Скрипт проверяет `/ready`, Redis queue key `celery`, worker health, failed/stale documents,
storage deletion backlog, успешный запуск retention за последние 26 часов и p95 latency по
`rag_audit_logs` за 24 часа. p95 выдаёт warning, а `LLEN celery` является эвристикой и может
не отражать очередь при другой Celery routing configuration.

## Ingestion worker

Основная задача — `ingestion.process_document`. Worker использует `acks_late`,
`task_reject_on_worker_lost`, prefetch `1`, soft/hard limits 20/25 минут и до трёх retry с
backoff только для transient storage, database, Redis и embedding ошибок. Ошибки формата,
парсинга и quota terminal и остаются `failed`. Task logs содержат duration и error class, не
exception text или document content. Отдельная maintenance task обрабатывает storage outbox.

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

Повтор использует owner-token Redis lock с атомарным compare-and-delete и повторно индексирует
chunks. Вся обработка не является одной транзакцией: статусы/stages фиксируются отдельными
commit. После потери Redis backup не содержит очередь, поэтому сначала просмотрите кандидатов
в dry-run:

```bash
make requeue-stale-ingestion
make requeue-stale-ingestion APPLY=1
```

По умолчанию выбираются все `pending` и `processing`, не обновлявшиеся не менее 60 минут;
команда выводит только статус и document ID, ограничивает один запуск 500 документами и не
меняет БД. Перед `APPLY=1` проверьте вывод. Окно можно поднять через
`ARGS='--stale-minutes 90'`; значение меньше 30 минут запрещено, поскольку worker hard timeout
— 25 минут. Пропуск одного документа безопасно повторить: работающий owner lock отклонит
дубликат. Failed document можно выбрать только явно, с конкретным UUID и
`--include-failed`; предварительно проверьте `last_error`, поскольку постоянные ошибки тоже
попадают в `failed`:

```bash
make requeue-stale-ingestion ARGS='--include-failed --document-id 00000000-0000-0000-0000-000000000000'
make requeue-stale-ingestion ARGS='--include-failed --document-id 00000000-0000-0000-0000-000000000000' APPLY=1
```

## Backup

```bash
make backup-pilot
```

`ops/backup-pilot.sh` временно останавливает backend, worker и Beat, чтобы сделать согласованный
снимок PostgreSQL и MinIO; запланируйте короткое окно недоступности. Затем он создаёт
`pg_dump -Fc` и mirror MinIO в `backups/<timestamp>/`, сохраняет Alembic revision в manifest,
делает SHA-256 checksums и перезапускает ранее работавшие сервисы даже при ошибке. Каталог
исключён из Git. Backup не включает Redis: теряются
queued/in-flight tasks, refresh sessions, locks, rate limit counters и LLM cache. Restore до
остановки сервисов проверяет, что ревизия есть в migration graph текущего кода; старые
известные ревизии можно обновить Alembic при старте.

## Restore

```bash
make restore-pilot BACKUP_DIR=backups/pilot-latest
```

Скрипт сначала проверяет manifest, checksums и revision, затем останавливает writers и
schedulers, пересоздаёт БД, выполняет `pg_restore`, зеркалирует MinIO с удалением объектов,
отсутствующих в backup, запускает Compose, ожидает `/ready` и выводит
dry-run кандидатов для ingestion recovery. Повторная постановка требует отдельного запуска
`make requeue-stale-ingestion APPLY=1`. Это разрушительная операция. Вариант
`make restore-drill` дополнительно удаляет volumes и разрешён только в изолированной local
среде.

Ограничения:

- manifest старого формата без Alembic revision не принимается;
- проверка подтверждает известную migration revision, но не заменяет отдельный restore drill;
- Redis не восстанавливается;
- point-in-time recovery не настроен;
- нет off-site replication, encryption policy и автоматического расписания;
- RPO/RTO не определены публичной конфигурацией.

## Согласование MinIO и PostgreSQL

```bash
make reconcile-minio
make reconcile-minio DELETE=1
```

Первая команда — dry-run. Она учитывает ссылки из `documents.file_path` и pending storage
outbox. Вторая удаляет только объекты без таких ссылок; отсутствующие объекты не
восстанавливаются. Перед `DELETE=1`
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
