# Pilot operations (Compose)

Scripts for **self-host / pilot** backup and restore. Canonical runbook (prod checklist, secret rotation, TLS): `docs/_private/operations/pilot-runbook.md` (gitignored; copy from your team backup). **Embedding model change:** `docs/_private/operations/embedding-model-migration.md`.

| Command | Action |
| --- | --- |
| `make backup-pilot` | `pg_dump` + MinIO mirror → `backups/<timestamp>/` |
| `make restore-pilot BACKUP_DIR=backups/pilot-latest` | Restore DB + bucket (writers stopped) |
| `RESTORE_DRILL_CONFIRM=YES make restore-drill` | Backup source → isolated restore → readiness/data check → remove drill volumes |
| `make requeue-stale-ingestion` | Dry-run: list pending and stale processing document IDs after Redis loss |
| `make requeue-stale-ingestion APPLY=1` | Enqueue the listed candidates; use `ARGS='--stale-minutes 90'` to tune the stale window |
| `make requeue-stale-ingestion ARGS='--include-failed --document-id <uuid>' APPLY=1` | Requeue one inspected failed document after its lock TTL has elapsed |
| `make reconcile-minio` | Dry-run: MinIO keys vs live document paths + pending deletion outbox |
| `make reconcile-minio DELETE=1` | Remove orphan objects only (`ops/reconcile-minio.sh --delete`) |
| `make check-pilot-alerts` | `/ready`, worker health, queue/stale counts, deletion backlog, retention log, p95 audit latency |
| `make load-baseline` | Hybrid `retrieve` latency sweep → `reports/load_baseline.md` (offline, no LLM) |

`backups/` is gitignored. Do not commit dumps or object bytes. Backup pauses backend, worker
and Beat during the DB/object snapshot; schedule a maintenance window. Previously running
services are restarted on success or failure.

Backup включает PostgreSQL и MinIO, но **не Redis**. После restore отсутствуют refresh
sessions, Celery queue/in-flight tasks, locks, rate-limit counters и LLM cache. Manifest
содержит Alembic revision; checksums и migration ancestry проверяются до destructive действий.
MinIO restore удаляет target keys, отсутствующие в backup. После старта сервисов restore
показывает кандидатов ingestion в dry-run.
Проверьте IDs и при необходимости выполните `make requeue-stale-ingestion APPLY=1`. Полные
ограничения и порядок восстановления: [docs/operations/operations.md](../docs/operations/operations.md).

`make restore-drill` по умолчанию берёт источник `docwise-public-demo`, на короткое время останавливает его
writers для согласованного backup, затем восстанавливает копию в отдельный Compose project. Запускайте его
только в согласованное окно обслуживания. Команда требует явного `RESTORE_DRILL_CONFIRM=YES`, использует
отдельные volumes и loopback port `18001`, проверяет `/ready` и наличие ready documents, затем удаляет только
временный project. Backup остаётся в `backups/restore-drills/`. При ошибке изолированный project сохраняется
для диагностики. Для другого источника задайте `RESTORE_DRILL_SOURCE_PROJECT`; скрипт рассчитан на public-demo
Compose профиль с Garage.

Compose pins **server** `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`. Backup/restore use **client** `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z` (`MINIO_MC_IMAGE` override) — tags come from [minio/mc releases](https://github.com/minio/mc/releases), not the server repo. Prefer Quay over Docker Hub behind corporate proxy.
