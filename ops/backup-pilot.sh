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
S3_BUCKET="${S3_BUCKET:-documents}"
# Client image: github.com/minio/mc/releases (not the same tag as minio/minio server).
MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z}"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
DEST="${1:-$ROOT/backups/$STAMP}"
mkdir -p "$DEST/minio"

if ! docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  echo "error: postgres service is not running (run: make up)" >&2
  exit 1
fi

echo "==> Postgres dump -> $DEST/postgres.dump"
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" >"$DEST/postgres.dump"

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
  -c "mc alias set local http://minio:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' && mc mirror --overwrite local/$S3_BUCKET /backup"

cat >"$DEST/manifest.txt" <<EOF
created_utc=$STAMP
postgres_user=$POSTGRES_USER
postgres_db=$POSTGRES_DB
s3_bucket=$S3_BUCKET
compose_project=$(basename "$ROOT")
EOF

mkdir -p "$ROOT/backups"
ln -sfn "$DEST" "$ROOT/backups/pilot-latest"

echo "==> Done: $DEST"
echo "    Latest: backups/pilot-latest"
