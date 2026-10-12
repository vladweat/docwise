# Pilot operations (Compose)

Scripts for **self-host / pilot** backup and restore. Canonical runbook (prod checklist, secret rotation, TLS): `docs/_private/operations/pilot-runbook.md` (gitignored; copy from your team backup). **Embedding model change:** `docs/_private/operations/embedding-model-migration.md`.

| Command | Action |
| --- | --- |
| `make backup-pilot` | `pg_dump` + MinIO mirror → `backups/<timestamp>/` |
| `make restore-pilot BACKUP_DIR=backups/pilot-latest` | Restore DB + bucket (writers stopped) |
| `make restore-drill` | Backup → wipe volumes → restore → `make health` (local only) |
| `make reconcile-minio` | Dry-run: MinIO keys vs `documents.file_path` (orphans + missing) |
| `make reconcile-minio DELETE=1` | Remove orphan objects only (`ops/reconcile-minio.sh --delete`) |
| `make check-pilot-alerts` | `/ready`, Celery queue depth, `documents.status=failed`, p95 `rag_audit_logs` (24h) |
| `make load-baseline` | Hybrid `retrieve` latency sweep → `reports/load_baseline.md` (offline, no LLM) |

`backups/` is gitignored. Do not commit dumps or object bytes.

Backup включает PostgreSQL и MinIO, но **не Redis**. После restore отсутствуют refresh
sessions, Celery queue/in-flight tasks, locks, rate-limit counters и LLM cache. Проверьте
документы в `pending`/`processing` до повторной постановки ingestion. Полные ограничения и
порядок восстановления: [docs/operations/operations.md](../docs/operations/operations.md).

Compose pins **server** `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`. Backup/restore use **client** `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z` (`MINIO_MC_IMAGE` override) — tags come from [minio/mc releases](https://github.com/minio/mc/releases), not the server repo. Prefer Quay over Docker Hub behind corporate proxy.
