#!/usr/bin/env bash
# Validate the merged public-demo Compose configuration without starting services.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

docker compose -p docwise-public-demo \
  -f docker-compose.yml -f docker-compose.public-demo.yml \
  config --quiet

echo "Public demo Compose configuration is valid."
