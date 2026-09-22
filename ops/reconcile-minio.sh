#!/usr/bin/env bash
# List (and optionally remove) MinIO objects with no matching documents.file_path row.
# Compares bucket keys to Postgres after the delete contract: DB commit first, then S3.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DELETE=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [--delete]

  Dry-run (default): report orphan objects and DB rows whose file_path is missing in MinIO.
  --delete          Remove orphan objects only (never deletes rows in Postgres).

Requires: docker compose with postgres and minio running (see: make up).

Orphans usually come from MinIO delete failing after DELETE /documents/{id} committed.
Avoid --delete during heavy upload traffic (brief window between put_object and DB commit).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --delete)
      DELETE=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

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

for svc in postgres minio; do
  if ! docker compose ps --status running --services 2>/dev/null | grep -qx "$svc"; then
    echo "error: $svc service is not running (run: make up)" >&2
    exit 1
  fi
done

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "==> Loading documents.file_path from Postgres"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A \
  -c "SELECT file_path FROM documents ORDER BY file_path" \
  | grep -v '^$' \
  | sort -u >"$WORKDIR/db.txt"

NETWORK="$(docker compose ps -q postgres | head -1 | xargs docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')"
if [[ -z "$NETWORK" ]]; then
  echo "error: could not resolve compose network" >&2
  exit 1
fi

echo "==> Listing objects in MinIO bucket $S3_BUCKET"
docker run --rm \
  --network "$NETWORK" \
  --entrypoint /bin/sh \
  "$MINIO_MC_IMAGE" \
  -c "mc alias set local http://minio:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' && mc ls -r --json local/$S3_BUCKET" \
  | python3 -c '
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line or not line.startswith("{"):
        continue
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        continue
    if row.get("type") == "file" and row.get("key"):
        print(row["key"])
' \
  | sort -u >"$WORKDIR/s3.txt"

DB_COUNT="$(wc -l <"$WORKDIR/db.txt" | tr -d ' ')"
S3_COUNT="$(wc -l <"$WORKDIR/s3.txt" | tr -d ' ')"
comm -23 "$WORKDIR/s3.txt" "$WORKDIR/db.txt" >"$WORKDIR/orphans.txt"
comm -13 "$WORKDIR/s3.txt" "$WORKDIR/db.txt" >"$WORKDIR/missing.txt"
ORPHAN_COUNT="$(wc -l <"$WORKDIR/orphans.txt" | tr -d ' ')"
MISSING_COUNT="$(wc -l <"$WORKDIR/missing.txt" | tr -d ' ')"

echo ""
echo "Summary: db_paths=$DB_COUNT s3_objects=$S3_COUNT orphans=$ORPHAN_COUNT missing_objects=$MISSING_COUNT"

if [[ "$ORPHAN_COUNT" -gt 0 ]]; then
  echo ""
  echo "Orphan keys (in MinIO, not in documents.file_path):"
  sed 's/^/  /' "$WORKDIR/orphans.txt"
fi

if [[ "$MISSING_COUNT" -gt 0 ]]; then
  echo ""
  echo "Missing objects (file_path in DB, not in MinIO — re-upload or restore from backup):"
  sed 's/^/  /' "$WORKDIR/missing.txt"
fi

if [[ "$ORPHAN_COUNT" -eq 0 && "$MISSING_COUNT" -eq 0 ]]; then
  echo "No drift detected."
  exit 0
fi

if [[ "$DELETE" != true ]]; then
  if [[ "$ORPHAN_COUNT" -gt 0 ]]; then
    echo ""
    echo "Dry-run only. To remove orphans: bash ops/reconcile-minio.sh --delete"
  fi
  exit 0
fi

if [[ "$ORPHAN_COUNT" -eq 0 ]]; then
  exit 0
fi

echo ""
echo "==> Removing $ORPHAN_COUNT orphan object(s)"
while IFS= read -r key; do
  [[ -z "$key" ]] && continue
  echo "  rm $key"
  docker run --rm \
    --network "$NETWORK" \
    --entrypoint /bin/sh \
    "$MINIO_MC_IMAGE" \
    -c "mc alias set local http://minio:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' && mc rm --force 'local/$S3_BUCKET/$key'"
done <"$WORKDIR/orphans.txt"

echo "==> Done"
