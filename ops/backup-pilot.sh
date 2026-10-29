#!/usr/bin/env bash
# Backup Postgres (pg_dump custom) + MinIO bucket mirror for Compose pilot/self-host.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

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
# Client image: github.com/minio/mc/releases (not the same tag as minio/minio server).
MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z}"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
DEST="${1:-$ROOT/backups/$STAMP}"
if [[ -d "$DEST" && -n "$(ls -A "$DEST")" ]]; then
  echo "error: backup destination is not empty: $DEST" >&2
  exit 1
fi
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
mkdir -p "$DEST/minio"

if ! docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  echo "error: postgres service is not running (run: make up)" >&2
  exit 1
fi
if docker compose ps --status running --services 2>/dev/null | grep -qx db-migrate; then
  echo "error: db-migrate is running; wait for the migration job before backup" >&2
  exit 1
fi

mapfile -t RUNNING_WRITERS < <(
  docker compose ps --status running --services 2>/dev/null \
    | grep -E '^(backend|celery-worker|celery-beat)$' || true
)
restore_writers() {
  if ((${#RUNNING_WRITERS[@]} > 0)); then
    echo "==> Restarting previously running writers/schedulers"
    docker compose start "${RUNNING_WRITERS[@]}"
  fi
}
trap restore_writers EXIT
if ((${#RUNNING_WRITERS[@]} > 0)); then
  echo "==> Pausing writers/schedulers for a consistent DB + object snapshot"
  docker compose stop "${RUNNING_WRITERS[@]}"
fi

read_alembic_revision() {
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc \
    "SELECT string_agg(version_num, ',' ORDER BY version_num) FROM alembic_version"
}

ALEMBIC_REVISION="$(read_alembic_revision)"
if [[ -z "$ALEMBIC_REVISION" ]]; then
  echo "error: could not read Alembic revision; refusing to create an unversioned backup" >&2
  exit 1
fi

echo "==> Postgres dump -> $DEST/postgres.dump"
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" >"$DEST/postgres.dump"

if [[ "$(read_alembic_revision)" != "$ALEMBIC_REVISION" ]]; then
  echo "error: Alembic revision changed during backup; discard $DEST and retry" >&2
  exit 1
fi

NETWORK="$(docker compose ps -q postgres | head -1 | xargs docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')"
if [[ -z "$NETWORK" ]]; then
  echo "error: could not resolve compose network" >&2
  exit 1
fi

echo "==> MinIO mirror local/$S3_BUCKET -> $DEST/minio/"
docker run --rm \
  --network "$NETWORK" \
  -v "$DEST/minio:/backup" \
  --entrypoint /bin/sh \
  "$MINIO_MC_IMAGE" \
  -c "mc alias set local '$MC_ENDPOINT' '$MC_ACCESS_KEY' '$MC_SECRET_KEY' && mc mirror --overwrite local/$S3_BUCKET /backup"

cat >"$DEST/manifest.txt" <<EOF
created_utc=$STAMP
postgres_user=$POSTGRES_USER
postgres_db=$POSTGRES_DB
s3_bucket=$S3_BUCKET
alembic_revision=$ALEMBIC_REVISION
compose_project=$(basename "$ROOT")
EOF

echo "==> Create checksums"
(
  cd "$DEST"
  {
    sha256sum postgres.dump manifest.txt
    find minio -type f -print0 | sort -z | xargs -0 -r sha256sum
  } >checksums.sha256
)

mkdir -p "$ROOT/backups"
ln -sfn "$DEST" "$ROOT/backups/pilot-latest"

echo "==> Done: $DEST"
echo "    Latest: backups/pilot-latest"
