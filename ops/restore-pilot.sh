#!/usr/bin/env bash
# Restore Postgres + MinIO from ops/backup-pilot.sh output. Destructive for DB/bucket data.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WIPE_VOLUMES=0
BACKUP_DIR=""

for arg in "$@"; do
  case "$arg" in
    --wipe-volumes) WIPE_VOLUMES=1 ;;
    -h | --help)
      echo "Usage: $0 <backup-dir> [--wipe-volumes]"
      echo "  --wipe-volumes  docker compose down -v before restore (local drill only)"
      exit 0
      ;;
    *)
      if [[ -z "$BACKUP_DIR" ]]; then
        BACKUP_DIR="$arg"
      else
        echo "error: unknown argument: $arg" >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$BACKUP_DIR" ]]; then
  BACKUP_DIR="$ROOT/backups/pilot-latest"
fi
if [[ -L "$BACKUP_DIR" ]]; then
  BACKUP_DIR="$(readlink -f "$BACKUP_DIR")"
fi
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd)"

if [[ ! -f "$BACKUP_DIR/postgres.dump" ]]; then
  echo "error: missing $BACKUP_DIR/postgres.dump" >&2
  exit 1
fi
if [[ ! -d "$BACKUP_DIR/minio" ]]; then
  echo "error: missing $BACKUP_DIR/minio/" >&2
  exit 1
fi

if [[ ! -f "$BACKUP_DIR/manifest.txt" ]]; then
  echo "error: missing $BACKUP_DIR/manifest.txt; refusing restore without revision metadata" >&2
  exit 1
fi
if [[ ! -f "$BACKUP_DIR/checksums.sha256" ]]; then
  echo "error: missing $BACKUP_DIR/checksums.sha256; refusing restore without integrity metadata" >&2
  exit 1
fi
echo "==> Verify backup checksums before stopping services"
if ! (cd "$BACKUP_DIR" && sha256sum --check --status checksums.sha256); then
  echo "error: backup checksum mismatch; refusing restore" >&2
  exit 1
fi
BACKUP_ALEMBIC_REVISION="$(sed -n 's/^alembic_revision=//p' "$BACKUP_DIR/manifest.txt" | tail -n 1)"
if [[ -z "$BACKUP_ALEMBIC_REVISION" ]]; then
  echo "error: backup manifest has no Alembic revision; refusing restore" >&2
  exit 1
fi

if [[ ! -x "$ROOT/backend/.venv/bin/python" ]]; then
  echo "error: backend/.venv is required to validate backup schema compatibility" >&2
  exit 1
fi
echo "==> Validate backup Alembic revision before stopping services"
(
  cd "$ROOT/backend"
  PYTHONPATH="$ROOT/backend" .venv/bin/python - "$BACKUP_ALEMBIC_REVISION" <<'PY'
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory

script = ScriptDirectory.from_config(Config("alembic.ini"))
backup_revisions = [value for value in sys.argv[1].split(",") if value]
known = {revision.revision for revision in script.walk_revisions()}
current_ancestry = set()
for head in script.get_heads():
    pending = [head]
    while pending:
        revision_id = pending.pop()
        if revision_id in current_ancestry:
            continue
        current_ancestry.add(revision_id)
        revision = script.get_revision(revision_id)
        if revision is None or revision.down_revision is None:
            continue
        if isinstance(revision.down_revision, str):
            pending.append(revision.down_revision)
        else:
            pending.extend(revision.down_revision)
unknown = sorted(set(backup_revisions) - known)
disconnected = sorted(set(backup_revisions) - current_ancestry)
if not backup_revisions or unknown or disconnected:
    details = unknown or disconnected or ["empty"]
    print("error: backup schema revision is unknown or not an ancestor of current Alembic heads: " + ",".join(details), file=sys.stderr)
    raise SystemExit(1)
print("Backup revision is an ancestor of the current Alembic head(s).")
PY
)

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-docwise}"
POSTGRES_DB="${POSTGRES_DB:-docwise_db}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-docwise}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-change_this_in_prod}"
MC_ENDPOINT="${MC_ENDPOINT:-http://minio:9000}"
MC_ACCESS_KEY="${MC_ACCESS_KEY:-$MINIO_ROOT_USER}"
MC_SECRET_KEY="${MC_SECRET_KEY:-$MINIO_ROOT_PASSWORD}"
S3_BUCKET="${S3_BUCKET:-documents}"
MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z}"

echo "==> Stopping writers and schedulers"
docker compose stop backend celery-worker celery-beat frontend db-migrate 2>/dev/null || true

if [[ "$WIPE_VOLUMES" == 1 ]]; then
  echo "==> Wiping compose volumes (destructive)"
  docker compose down -v
  docker compose up -d postgres redis minio
  echo "==> Waiting for postgres health"
  for _ in $(seq 1 60); do
    if docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d postgres >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
fi

if ! docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  docker compose up -d postgres redis minio
  sleep 5
fi

echo "==> Recreate database $POSTGRES_DB"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS $POSTGRES_DB;
CREATE DATABASE $POSTGRES_DB;
SQL

echo "==> pg_restore -> $POSTGRES_DB"
docker compose exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl <"$BACKUP_DIR/postgres.dump"

NETWORK="$(docker compose ps -q postgres | head -1 | xargs docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')"

echo "==> MinIO mirror /backup -> local/$S3_BUCKET"
docker run --rm \
  --network "$NETWORK" \
  -v "$BACKUP_DIR/minio:/backup:ro" \
  --entrypoint /bin/sh \
  "$MINIO_MC_IMAGE" \
  -c "mc alias set local '$MC_ENDPOINT' '$MC_ACCESS_KEY' '$MC_SECRET_KEY' && mc mb --ignore-existing local/$S3_BUCKET && mc mirror --overwrite --remove /backup local/$S3_BUCKET"

echo "==> Starting stack"
docker compose up -d

echo "==> Waiting for /ready"
for _ in $(seq 1 90); do
  if curl -sf "${RESTORE_READY_URL:-http://localhost:8001/ready}" >/dev/null 2>&1; then
    echo "==> Review ingestion recovery candidates (dry-run)"
    docker compose exec -T backend python /app/scripts/requeue_stale_ingestion.py
    echo "==> Restore complete from $BACKUP_DIR"
    exit 0
  fi
  sleep 2
done

echo "warning: stack up but /ready not OK yet — check: docker compose logs backend" >&2
exit 1
