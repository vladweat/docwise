#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found. Install Node.js 20+."
  exit 1
fi

# Нативные gnu+musl бинарники — прямые зависимости: хост glibc, образ node:20-alpine (musl).
# Версии SWC = next; lightningcss/oxide = tailwindcss; rollup/esbuild = vitest/vite.
echo "Installing frontend dependencies..."
# --force позволяет npm установить обе целевые версии нативных пакетов на хосте glibc.
npm ci --omit=optional --no-audit --no-fund --force

mkdir -p public
if [[ -f node_modules/pdfjs-dist/build/pdf.worker.min.mjs ]]; then
  cp node_modules/pdfjs-dist/build/pdf.worker.min.mjs public/pdf.worker.min.mjs
elif [[ -f node_modules/pdfjs-dist/build/pdf.worker.min.js ]]; then
  cp node_modules/pdfjs-dist/build/pdf.worker.min.js public/pdf.worker.min.js
fi

echo ""
echo "OK: frontend/node_modules ready"
echo "Next (offline): make up"
