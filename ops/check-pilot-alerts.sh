#!/usr/bin/env bash
# Pilot alert probes (Compose). Exit 1 if any hard check fails.
# See docs/_private/operations/pilot-runbook.md §9.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_URL="${API_URL:-http://localhost:8001}"
READY_MAX_QUEUE="${READY_MAX_QUEUE:-50}"
FAILED_DOC_ALERT="${FAILED_DOC_ALERT:-5}"
P95_LATENCY_MS="${P95_LATENCY_MS:-8000}"

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
echo "== Celery queue depth (redis list 'celery') =="
queue_depth="$(docker compose exec -T redis redis-cli LLEN celery 2>/dev/null | tr -d '\r' || echo "unknown")"
echo "depth=$queue_depth (alert if > $READY_MAX_QUEUE)"
if [[ "$queue_depth" =~ ^[0-9]+$ ]] && (( queue_depth > READY_MAX_QUEUE )); then
  echo "FAIL: queue depth $queue_depth"
  fail=1
fi

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
