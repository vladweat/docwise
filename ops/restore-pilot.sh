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
S3_BUCKET="${S3_BUCKET:-documents}"
MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z}"

echo "==> Stopping writers (backend, celery-worker, frontend)"
docker compose stop backend celery-worker frontend 2>/dev/null || true

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
  -c "mc alias set local http://minio:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' && mc mb --ignore-existing local/$S3_BUCKET && mc mirror --overwrite /backup local/$S3_BUCKET"

echo "==> Starting stack"
docker compose up -d

echo "==> Waiting for /ready"
for _ in $(seq 1 90); do
  if curl -sf http://localhost:8001/ready >/dev/null 2>&1; then
    echo "==> Restore complete from $BACKUP_DIR"
    exit 0
  fi
  sleep 2
done

echo "warning: stack up but /ready not OK yet — check: docker compose logs backend" >&2
exit 1
