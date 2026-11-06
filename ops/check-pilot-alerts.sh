#!/usr/bin/env bash
# Pilot alert probes (Compose). Exit 1 if any hard check fails.
# See docs/_private/operations/pilot-runbook.md §9.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

API_URL="${API_URL:-http://localhost:8001}"
READY_MAX_QUEUE="${READY_MAX_QUEUE:-50}"
FAILED_DOC_ALERT="${FAILED_DOC_ALERT:-5}"
P95_LATENCY_MS="${P95_LATENCY_MS:-8000}"
MAX_STALE_DOCUMENTS="${MAX_STALE_DOCUMENTS:-0}"
MAX_STORAGE_DELETE_BACKLOG="${MAX_STORAGE_DELETE_BACKLOG:-0}"
MAX_STORAGE_DELETE_AGE_MINUTES="${MAX_STORAGE_DELETE_AGE_MINUTES:-30}"

fail=0

echo "== /ready =="
ready_body="$(curl -sf "$API_URL/ready" 2>/dev/null || true)"
if [[ -z "$ready_body" ]]; then
  echo "FAIL: /ready unreachable or non-2xx ($API_URL/ready)"
  fail=1
else
  echo "$ready_body" | python3 -m json.tool 2>/dev/null || echo "$ready_body"
fi

echo ""
echo "== Runtime RLS role =="
rls_role="$(docker compose exec -T backend printenv DOCWISE_RLS_SESSION_ROLE 2>/dev/null | tr -d '\r' || true)"
worker_rls_role="$(docker compose exec -T celery-worker printenv DOCWISE_RLS_SESSION_ROLE 2>/dev/null | tr -d '\r' || true)"
role_state="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-docwise}" -d "${POSTGRES_DB:-docwise_db}" -t -A -F '|' -c \
  "SELECT rolsuper, rolbypassrls, rolcanlogin, pg_has_role(current_user, oid, 'MEMBER')
   FROM pg_roles WHERE rolname = 'docwise_rls';" 2>/dev/null | tr -d '\r' || true)"
echo "backend_role=${rls_role:-missing} worker_role=${worker_rls_role:-missing} role_attributes=${role_state:-missing}"
if [[ "$rls_role" != docwise_rls || "$worker_rls_role" != docwise_rls || "$role_state" != "f|f|f|t" ]]; then
  echo "FAIL: RLS runtime role is missing, unsafe, or not granted to the application login"
  fail=1
fi

echo ""
echo "== Celery queue depth (redis list 'celery') =="
queue_depth="$(docker compose exec -T redis redis-cli LLEN celery 2>/dev/null | tr -d '\r' || echo "unknown")"
echo "depth=$queue_depth (alert if > $READY_MAX_QUEUE)"
if [[ "$queue_depth" =~ ^[0-9]+$ ]] && (( queue_depth > READY_MAX_QUEUE )); then
  echo "FAIL: queue depth $queue_depth"
  fail=1
fi

echo ""
echo "== Celery worker health =="
worker_id="$(docker compose ps -q celery-worker 2>/dev/null | head -n 1)"
worker_health="unknown"
if [[ -n "$worker_id" ]]; then
  worker_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$worker_id" 2>/dev/null || echo unknown)"
fi
echo "health=$worker_health"
if [[ "$worker_health" != healthy ]]; then
  echo "FAIL: Celery worker is not healthy"
  fail=1
fi

echo ""
echo "== Ingestion retry and final-failure events (last 24h, retained logs) =="
worker_events="$(docker compose logs --since=24h --no-log-prefix --no-log-timestamp celery-worker 2>/dev/null || true)"
retry_events="$(grep -Fc '"event": "ingestion_retry_scheduled"' <<<"$worker_events" || true)"
failure_events="$(grep -Fc '"event": "ingestion_failed_permanently"' <<<"$worker_events" || true)"
echo "retry_events=$retry_events permanent_failure_events=$failure_events (counts only; no identifiers printed)"

echo ""
echo "== documents.status=failed (count) =="
failed_count="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-docwise}" -d "${POSTGRES_DB:-docwise_db}" -t -A -c \
  "SELECT count(*) FROM documents WHERE status = 'failed';" 2>/dev/null | tr -d '\r' || echo "unknown")"
echo "failed=$failed_count (alert if >= $FAILED_DOC_ALERT)"
if [[ "$failed_count" =~ ^[0-9]+$ ]] && (( failed_count >= FAILED_DOC_ALERT )); then
  echo "FAIL: too many failed documents"
  fail=1
fi

echo ""
echo "== Stale ingestion documents (status and count only) =="
stale_count="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-docwise}" -d "${POSTGRES_DB:-docwise_db}" -t -A -c \
  "SELECT count(*) FROM documents WHERE status IN ('pending','processing') AND updated_at < now() - interval '60 minutes';" \
  2>/dev/null | tr -d '\r' || echo unknown)"
echo "stale=$stale_count (alert if > $MAX_STALE_DOCUMENTS)"
if [[ "$stale_count" =~ ^[0-9]+$ ]] && (( stale_count > MAX_STALE_DOCUMENTS )); then
  echo "FAIL: stale ingestion work needs recovery review"
  fail=1
fi

echo ""
echo "== Pending object-storage deletions =="
delete_backlog="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-docwise}" -d "${POSTGRES_DB:-docwise_db}" -t -A -F ' ' -c \
  "SELECT count(*), coalesce(max(extract(epoch FROM (now() - created_at)))::int, 0) FROM storage_deletions;" \
  2>/dev/null | tr -d '\r' || echo unknown)"
delete_count="${delete_backlog%% *}"
delete_age_seconds="${delete_backlog##* }"
echo "pending=$delete_count oldest_seconds=$delete_age_seconds"
if [[ "$delete_count" =~ ^[0-9]+$ ]] && (( delete_count > MAX_STORAGE_DELETE_BACKLOG )); then
  echo "FAIL: object cleanup backlog needs review"
  fail=1
fi
if [[ "$delete_age_seconds" =~ ^[0-9]+$ ]] && (( delete_age_seconds > MAX_STORAGE_DELETE_AGE_MINUTES * 60 )); then
  echo "FAIL: object cleanup has exceeded the age threshold"
  fail=1
fi

echo ""
echo "== Audit retention task in the last 26h =="
retention_success="$(docker compose logs --since=26h --no-log-prefix celery-worker 2>/dev/null | grep -F 'purged expired rag audit logs' | tail -n 1 || true)"
if [[ -z "$retention_success" ]]; then
  echo "WARN: no successful audit retention task found in worker logs"
else
  echo "Recent audit retention task found"
fi

echo ""
echo "== rag_audit_logs p95 latency_ms (24h, chat+inspect) =="
docker compose exec -T postgres psql -U "${POSTGRES_USER:-docwise}" -d "${POSTGRES_DB:-docwise_db}" -c \
  "SELECT count(*) AS n,
          percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)::int AS p95_ms
   FROM rag_audit_logs
   WHERE created_at > now() - interval '24 hours'
     AND latency_ms IS NOT NULL;" 2>/dev/null || echo "(postgres unavailable)"

p95="$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-docwise}" -d "${POSTGRES_DB:-docwise_db}" -t -A -c \
  "SELECT coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)::int, 0)
   FROM rag_audit_logs
   WHERE created_at > now() - interval '24 hours'
     AND latency_ms IS NOT NULL;" 2>/dev/null | tr -d '\r' || echo "0")"
if [[ "$p95" =~ ^[0-9]+$ ]] && (( p95 > P95_LATENCY_MS )); then
  echo "WARN: p95 latency ${p95}ms > ${P95_LATENCY_MS}ms (tune threshold via P95_LATENCY_MS)"
fi

exit "$fail"
