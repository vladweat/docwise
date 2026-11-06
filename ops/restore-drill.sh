#!/usr/bin/env bash
# Copy a source Compose project into a temporary isolated project, restore it, then verify readiness.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

EXPLICIT_COMPOSE_FILE="${COMPOSE_FILE:-}"
EXPLICIT_COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-}"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [[ -n "$EXPLICIT_COMPOSE_FILE" ]]; then
  COMPOSE_FILE="$EXPLICIT_COMPOSE_FILE"
fi
if [[ -n "$EXPLICIT_COMPOSE_PROJECT_NAME" ]]; then
  COMPOSE_PROJECT_NAME="$EXPLICIT_COMPOSE_PROJECT_NAME"
fi
unset EXPLICIT_COMPOSE_FILE EXPLICIT_COMPOSE_PROJECT_NAME

if [[ "${RESTORE_DRILL_CONFIRM:-}" != "YES" ]]; then
  echo "error: this drill briefly stops source writers; set RESTORE_DRILL_CONFIRM=YES after choosing a maintenance window" >&2
  exit 2
fi

COMPOSE_FILES="docker-compose.yml:docker-compose.public-demo.yml"
SOURCE_PROJECT="${RESTORE_DRILL_SOURCE_PROJECT:-${COMPOSE_PROJECT_NAME:-docwise-public-demo}}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
DRILL_PROJECT="${RESTORE_DRILL_PROJECT:-docwise-restore-drill-$STAMP}"
BACKUP_DIR="${RESTORE_DRILL_BACKUP_DIR:-$ROOT/backups/restore-drills/$STAMP}"
if [[ -z "${MC_ENDPOINT:-}" && "$SOURCE_PROJECT" == "docwise-public-demo" ]]; then
  export MC_ENDPOINT=http://minio:3900
fi

if [[ ! "$DRILL_PROJECT" =~ ^docwise-restore-drill-[a-z0-9-]+$ ]]; then
  echo "error: RESTORE_DRILL_PROJECT must start with docwise-restore-drill- and contain only lowercase letters, digits, and hyphens" >&2
  exit 2
fi
if [[ "$SOURCE_PROJECT" == "$DRILL_PROJECT" ]]; then
  echo "error: source and drill Compose projects must be different" >&2
  exit 2
fi
if [[ -e "$BACKUP_DIR" ]]; then
  echo "error: backup path already exists: $BACKUP_DIR" >&2
  exit 2
fi

echo "==> Create backup from source project: $SOURCE_PROJECT"
COMPOSE_FILE="$COMPOSE_FILES" COMPOSE_PROJECT_NAME="$SOURCE_PROJECT" \
  bash ops/backup-pilot.sh "$BACKUP_DIR"

echo "==> Restore into isolated project: $DRILL_PROJECT"
COMPOSE_FILE="$COMPOSE_FILES:ops/restore-drill.compose.yml" COMPOSE_PROJECT_NAME="$DRILL_PROJECT" \
  RESTORE_READY_URL=http://127.0.0.1:18001/ready \
  bash ops/restore-pilot.sh "$BACKUP_DIR" --wipe-volumes --allow-project-mismatch

echo "==> Verify isolated application and restored database"
curl -fsS http://127.0.0.1:18001/ready >/dev/null
DOC_COUNT="$(COMPOSE_FILE="$COMPOSE_FILES:ops/restore-drill.compose.yml" COMPOSE_PROJECT_NAME="$DRILL_PROJECT" \
  docker compose exec -T postgres psql -U "${POSTGRES_USER:-docwise}" -d "${POSTGRES_DB:-docwise_db}" -Atqc \
    "SELECT count(*) FROM documents WHERE status = 'ready';")"
if [[ ! "$DOC_COUNT" =~ ^[0-9]+$ ]] || (( DOC_COUNT == 0 )); then
  echo "error: restored database has no ready documents" >&2
  exit 1
fi

echo "==> Restore drill passed: ready_documents=$DOC_COUNT backup=$BACKUP_DIR"
echo "==> Remove isolated containers and volumes"
COMPOSE_FILE="$COMPOSE_FILES:ops/restore-drill.compose.yml" COMPOSE_PROJECT_NAME="$DRILL_PROJECT" \
  docker compose down --volumes --remove-orphans
